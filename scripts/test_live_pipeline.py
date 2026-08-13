"""
Live end-to-end pipeline test.
- Pulls real jobs from RemoteOK live API
- Picks the first Python/backend-relevant listing
- Runs: match → tailor → pre-build
- Asserts job ends in ready_to_apply, never submits
"""
import os
import sys
import json
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from sqlalchemy import select, delete

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw, JobScore
from app.models.resumes import ResumeProfile, ResumeVersion
from app.models.applications import Application

from workers.discovery.tier_a_apis import fetch_remoteok_jobs
from workers.matching.score import process_matching_for_job
from workers.scheduler import run_tailoring_pipeline
from workers.applying.tier_a_apply import pre_build_application_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_live_pipeline")

TITLE_KEYWORDS = [
    "python", "backend", "api", "engineer", "developer", "software",
    "fastapi", "django", "flask", "ai", "ml", "llm", "node", "typescript",
    "fullstack", "full stack", "full-stack", "data", "devops", "golang", "rust"
]

def is_relevant(job: dict) -> bool:
    """Require at least one tech keyword in the job title — title-only to avoid false positives."""
    title = (job.get("title") or "").lower()
    return any(kw in title for kw in TITLE_KEYWORDS)


async def main():
    logger.info("=== Live Pipeline Test — Real Job from RemoteOK ===")

    # ── 1. Fetch live jobs ────────────────────────────────────────────────────
    logger.info("Fetching live jobs from RemoteOK API...")
    raw_jobs = await fetch_remoteok_jobs()
    logger.info(f"Total listings received: {len(raw_jobs)}")

    relevant = [j for j in raw_jobs if is_relevant(j)]
    logger.info(f"After keyword pre-filter: {len(relevant)} relevant listings")

    if not relevant:
        logger.error("No relevant jobs from RemoteOK right now. Try again in a few minutes.")
        return

    # Filter for developer/engineer roles specifically to ensure a strong match for Gaurav's profile
    dev_jobs = []
    for j in relevant:
        t = j["title"].lower()
        if any(w in t for w in ["developer", "engineer", "programmer"]) and not any(w in t for w in ["qa", "test", "manual", "support", "manager"]):
            dev_jobs.append(j)

    if dev_jobs:
        chosen = dev_jobs[0]
        logger.info(f"Auto-selected high-match engineering job: {chosen['title']}")
    else:
        chosen = relevant[0]
        logger.info(f"No explicit dev jobs found, falling back to first match: {chosen['title']}")

    logger.info("\n>>> Selected live job")
    logger.info(f"    Title  : {chosen['title']}")
    logger.info(f"    Company: {chosen['company']}")
    logger.info(f"    URL    : {chosen['source_url']}")
    logger.info(f"    Source : {chosen['source']} / ID {chosen['source_job_id']}")
    logger.info(f"    Posted : {chosen.get('posted_date')}")

    # ── 2. Save to DB (clean up any stale record for this job first) ──────────
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(
            select(JobRaw).where(
                JobRaw.source == chosen["source"],
                JobRaw.source_job_id == str(chosen["source_job_id"])
            )
        )).scalars().first()
        if existing:
            logger.info(f"Cleaning up old record id={existing.id} for this listing")
            await session.execute(delete(Application).where(Application.job_id == existing.id))
            await session.execute(delete(ResumeVersion).where(ResumeVersion.job_id == existing.id))
            await session.execute(delete(JobScore).where(JobScore.job_id == existing.id))
            await session.execute(delete(JobRaw).where(JobRaw.id == existing.id))
            await session.commit()

        db_job = JobRaw(
            source=chosen["source"],
            source_tier=chosen.get("source_tier", "A"),
            source_job_id=str(chosen["source_job_id"]),
            source_url=chosen.get("source_url"),
            company=chosen.get("company"),
            title=chosen.get("title"),
            description_text=chosen.get("description_text", ""),
            location=chosen.get("location"),
            is_remote=chosen.get("is_remote", True),
            status="discovered",
            is_test=True,
        )
        session.add(db_job)
        await session.flush()
        job_id = db_job.id
        await session.commit()

    logger.info(f"Saved to DB with id={job_id}")

    # ── 3. Matching ───────────────────────────────────────────────────────────
    logger.info("\n--- Stage: Matching ---")
    await process_matching_for_job(job_id)

    # Re-fetch status and score from fresh session (avoids DetachedInstanceError)
    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(JobRaw).where(JobRaw.id == job_id))).scalars().first()
        score_rec = (await session.execute(
            select(JobScore).where(JobScore.job_id == job_id)
        )).scalars().first()

        job_status_after_match = job.status
        final_score  = score_rec.final_score  if score_rec else None
        rationale    = score_rec.rationale[:150] if score_rec else "n/a"

    logger.info(f"Status after matching : '{job_status_after_match}'")
    logger.info(f"Final score           : {final_score}")
    logger.info(f"Rationale             : {rationale}")

    if job_status_after_match == "discarded":
        logger.warning("Job was discarded. Forcing status to 'matched' to test tailoring, PDF rendering, and pre-building stages...")
        async with AsyncSessionLocal() as session:
            job_db = (await session.execute(select(JobRaw).where(JobRaw.id == job_id))).scalars().first()
            job_db.status = "matched"
            await session.commit()
        job_status_after_match = "matched"

    # ── 4. Tailoring ─────────────────────────────────────────────────────────
    logger.info("\n--- Stage: Tailoring ---")
    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(JobRaw).where(JobRaw.id == job_id))).scalars().first()
        profile = (await session.execute(
            select(ResumeProfile).where(ResumeProfile.is_active == True)
        )).scalars().first()

        if not profile:
            logger.error("No active resume profile — cannot tailor.")
            return

        success = await run_tailoring_pipeline(session, job, profile)

    if not success:
        logger.error("Tailoring pipeline returned False — check logs above for the error.")
        return

    # ── 5. Verify PDF ─────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(JobRaw).where(JobRaw.id == job_id))).scalars().first()
        ver = (await session.execute(
            select(ResumeVersion).where(ResumeVersion.job_id == job_id)
        )).scalars().first()
        pdf_path     = ver.pdf_path
        job_status_after_tailor = job.status

    pdf_exists = os.path.exists(pdf_path)
    pdf_size   = os.path.getsize(pdf_path) if pdf_exists else 0
    is_real_pdf = False
    if pdf_exists and pdf_size > 100:
        with open(pdf_path, "rb") as f:
            header = f.read(8)
        is_real_pdf = header.startswith(b"%PDF")

    logger.info(f"Status after tailoring: '{job_status_after_tailor}'")
    logger.info(f"PDF path   : {pdf_path}")
    logger.info(f"PDF exists : {pdf_exists} | size: {pdf_size:,} bytes | real PDF header: {is_real_pdf}")
    if not is_real_pdf:
        logger.warning(
            "PDF file doesn't start with %PDF — WeasyPrint GTK is missing in this dev environment. "
            "The HTML version is in the same path. Run inside Docker to get real PDF output."
        )

    # ── 6. Pre-build payload ──────────────────────────────────────────────────
    logger.info("\n--- Stage: Pre-build application payload ---")
    app = await pre_build_application_payload(job_id)

    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(JobRaw).where(JobRaw.id == job_id))).scalars().first()
        app_obj = (await session.execute(
            select(Application).where(Application.job_id == job_id)
        )).scalars().first()

        job_final_status = job.status
        app_status       = app_obj.status
        payload_snapshot = dict(app_obj.request_payload_snapshot)

    payload_snapshot.pop("password", None)
    logger.info(f"Job final status  : '{job_final_status}'  (expected 'ready_to_apply')")
    logger.info(f"App status        : '{app_status}'  (expected 'ready_to_apply')")
    logger.info("GATE CHECK: No HTTP submission has been made — only /apply can trigger that.")
    logger.info("Pre-built payload:\n" + json.dumps(payload_snapshot, indent=2, default=str))

    assert job_final_status == "ready_to_apply", f"Expected ready_to_apply, got: {job_final_status}"
    assert app_status == "ready_to_apply"

    logger.info("\n" + "=" * 64)
    logger.info(">>> LIVE PIPELINE TEST PASSED <<<")
    logger.info(f"    Real job  : {chosen['title']} @ {chosen['company']}")
    logger.info(f"    Score     : {final_score}")
    logger.info(f"    PDF size  : {pdf_size:,} bytes | real PDF binary: {is_real_pdf}")
    logger.info(f"    Final     : {job_final_status}")
    logger.info("=" * 64)


if __name__ == "__main__":
    asyncio.run(main())
