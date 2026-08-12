# JobPilot — Implementation Plan

## Why This Differs From Doc 14 (Build Roadmap)

Doc 14 sequences *phases* and states the milestone for each. This doc breaks each phase into **concrete, ordered tasks** an agent (Antigravity) can execute one at a time, with the specific doc(s) each task should be built against. Treat this as the literal task list to work through — doc 14 is the "why this order," this is the "do this, then this."

## Phase 0 — Foundation

1. Scaffold monorepo structure: `/api` (FastAPI), `/web` (Next.js), `/bot` (aiogram), `/workers` (discovery/matcher/tailor/apply/contacts), `/docker-compose.yml`.
2. Write DB migrations for all tables in doc 11/17 §2. Enable `pgvector` extension.
3. Stand up Postgres + Redis containers, confirm connectivity from a bare FastAPI health-check endpoint.
4. Build the Resume Profile data model + a minimal admin-only form (can be a rough internal page before the real dashboard exists) to input Gaurav's real experience/projects/skills/target roles into `resume_profile`.
5. Implement embedding generation for the resume profile (Gemini embeddings per doc 02/04) and confirm it's stored correctly in the `vector` column.
6. **Exit check:** `resume_profile` has one active row with a real, non-null embedding, computed from Gaurav's actual data — this blocks every later phase, so don't proceed until it's genuinely populated, not placeholder text.

## Phase 1 — Tier A Core Loop

1. Build `jobs_raw` ingestion functions for RemoteOK, We Work Remotely, Remotive (each a small adapter that normalizes source JSON into the common schema — doc 03 §"Common Normalization Schema").
2. Add Greenhouse + Lever adapters (these will be reused later for Tier C-reclassified companies, so build them generically, not hardcoded to specific companies).
2b. Build the Tier A+ dork search discovery worker: search API integration (Google Custom Search / Bing), seed `dork_queries` from `resume_profile.target_roles`, result parser that routes ATS-matched URLs into the Tier A adapters from step 2 and logs Tier B/career-page matches as leads (doc 03 Tier A+). Build this alongside Tier A since it's equally low-risk and meaningfully increases coverage from day one.
3. Implement dedup logic (`source` + `source_job_id` uniqueness, plus the fuzzy secondary check per doc 03).
4. Wire APScheduler jobs for each Tier A source per the cadence table in doc 12.
5. Build the matching engine: embedding similarity function against `resume_profile`, threshold check, `job_scores` row creation (doc 04 Stage 1–2; skip Stage 3 LLM rerank in this pass — add in step 9 below once the core loop works).
6. Build the resume tailoring worker: JD keyword extraction call, bullet rewriting call, WeasyPrint PDF render, `resume_versions` row creation (doc 05).
7. Build the Tier A apply worker: construct the full submission payload per the ATS's documented API and hold it (`status = 'ready_to_apply'`) — do not submit yet. Build the separate `apply`-endpoint-triggered submission function (the part that actually fires on a tap) as its own unit, since it's called later from the API, not from this worker's own schedule (doc 06 Tier A/A+ flow).
8. Wire the whole chain event-driven: new `jobs_raw` row → matcher picks it up → tailoring triggers on match → payload pre-build triggers on tailoring complete → `status = 'ready_to_apply'`, event fired (doc 16 Flow 2). Submission itself only happens later, via the `/apply` endpoint — don't wire it to fire automatically here.
9. Add Stage 3 LLM rerank for middle-band scores (doc 04) once the base loop is confirmed working end-to-end.
10. **Exit check:** run against real live sources; confirm at least one real job gets discovered, scored, tailored, and reaches `ready_to_apply` with a correct, non-fabricated resume attached — then manually trigger the `/apply` endpoint and confirm it actually submits and logs a full `applications` audit row. Nothing should submit on its own before that manual trigger.

## Phase 2 — Telegram Bot

1. Register bot with BotFather, set up aiogram project structure (reuse Anti-Forward bot's scaffold as a starting point).
2. Implement `/start` pairing flow consuming a token from `settings.telegram_chat_id` (doc 17 §3.5 pairing endpoint).
3. Subscribe to Redis `jobpilot:events` channel (doc 17 §4); implement the `job.ready_to_apply` notification template with working `Apply`/`Pass` inline buttons first (doc 10's event table) — this is the bot's core function, build it before the passive `job.applied` confirmation template.
4. Implement `/today` and `/pending` commands — `/pending` should already return real results once Phase 1 is producing `ready_to_apply` jobs, since there's no longer a "waiting on Tier B" gate before it's useful.
5. **Exit check:** a real Tier A job from Phase 1 produces a real Telegram message with working `Apply`/`Pass` buttons; tapping `Apply` actually triggers the submission end-to-end from the phone, with zero dashboard involvement.

## Phase 3 — Web Dashboard (Core Views)

1. Scaffold Next.js app, apply design tokens from doc 15 §1.
2. Build the Applications Board with the Ready to Apply lane fully functional, including working `Apply`/`Pass` buttons wired to `/api/v1/applications/{id}/apply` and `/pass` (Applied/Manual lanes render empty states per doc 15 §6 until their data exists).
3. Build the Job Detail Page: Overview, Resume (PDF viewer), Match Details tabs functional; Contact and Application Log tabs can render "coming soon" until Phase 4/is trivial to fill from existing `applications` data — Application Log tab should actually be buildable now since `applications` already has audit data from Phase 1.
4. Build Settings: Resume Profile editor (replaces the rough admin form from Phase 0 step 4), Thresholds page.
5. Wire all pages to the `/api/v1` endpoints defined in doc 17 §3.
6. **Exit check:** Gaurav can see a real Ready to Apply job from Phase 1 in the dashboard, tap `Apply` directly in the UI, and watch it move to the Applied lane — entirely through the browser, no bot needed for this path.

## Phase 4 — Contact-Finder Module

1. Build the JD/ATS-metadata parser (cheapest, build first) — checks `jobs_raw.raw_payload` for named recruiter/hiring-manager fields.
2. Build LinkedIn public search + extraction, with the evidence-tagging requirement from doc 07 enforced at the data-model level (no `contacts` field written without a corresponding `evidence` entry).
3. Build email pattern inference + Hunter.io free-tier verification call.
4. Wire contact-finder to run in parallel with tailoring (non-blocking, per doc 03/07/16 Flow 5) for every matched job.
5. Add the Contact tab to the Job Detail Page (deferred from Phase 3) and the contact chip to job cards (doc 15 §3).
6. **Exit check:** across a batch of ~20 real matched jobs, contact-finder returns a result with valid evidence for a meaningful fraction (validates against the ≥40–50% target in the PRD, though early volume may be lower until tuned).

## Phase 5 — Outreach Module

1. Build the draft-generation endpoint (`POST /api/v1/outreach/{job_id}/draft`) calling Claude per doc 08.
2. Add "Message Contact" button to job cards (dashboard) and "Draft Message" inline button (Telegram, extending Phase 2's bot).
3. Build the `outreach_drafts` mark-as-sent flow (`PATCH` endpoint + dashboard toggle).
4. **Exit check:** Gaurav can go from a real contact found in Phase 4 to a genuinely usable, personalized draft message in one tap, with zero fabricated claims in the draft (spot-check against his actual resume/project data).

## Phase 6 — Tier B (Scrape + Human-in-Loop)

1. Build Playwright discovery scrapers for LinkedIn, Naukri, Wellfound, Instahyre — public search pages only, per doc 03 Tier B discovery logic. Start with just one platform (recommend LinkedIn, highest yield) before adding the rest.
2. Build the form-fill worker: fills known fields from `resume_profile`/`default_answers`, uploads tailored resume, screenshots the filled state, sets `status = 'ready_to_apply'` — does not submit (doc 06 Tier B flow). These land in the exact same lane as Tier A jobs from Phase 1/3 — no separate lane needs building, just the form-preview UI element on the existing card (doc 15 §3).
3. Implement the CAPTCHA/bot-challenge hard-stop (TRD REQ-SEC-4) — this must be tested deliberately (trigger a challenge scenario if possible in a safe way, confirm the worker halts and alerts rather than retrying).
4. Implement rate limiting/daily caps at the code level, starting conservative (e.g., 2–3/day) per TRD REQ-SEC-5.
5. Extend the existing `Apply`/`Pass` buttons (already built in Phase 2/3) to handle the Tier B mechanism — same endpoint, worker resolves it internally as a Playwright submit rather than an API call (doc 06).
6. Confirm the `/applications/{id}/apply` endpoint correctly routes to the Playwright submission path for Tier B jobs and completes it asynchronously.
7. **Trial period:** run Tier B at the conservative cap for at least 1–2 weeks, monitoring `source_health` closely, before considering raising the daily cap (doc 14's explicit caution).
8. Once LinkedIn is stable, repeat steps 1–2 for Naukri, Wellfound, Instahyre one at a time — not in parallel, so any platform-specific issue is isolated and easy to diagnose.
9. **Exit check:** at least one real Tier B job reaches `ready_to_apply` with a correct form preview, and a real `Apply` tap (via Telegram or dashboard) completes the Playwright submission — zero account warnings/blocks observed during the trial period.

## Phase 7 — Tier C (Career Page Crawl)

1. Build `target_companies` seed import (from Gaurav's existing outreach tracker) and the Settings UI for managing it.
2. Build the careers-URL resolver (pattern guessing + search fallback per doc 03).
3. Build ATS-fingerprint detection; confirm reclassification to Tier A works correctly for a known test company (e.g., a company known to run Greenhouse under a custom domain).
4. Build the custom-page extraction path (Claude-based listing extraction) for companies with no detected ATS.
5. Build apply-method classification (simple form → Tier B-style; email/complex → Tier D) per doc 03 Tier C logic.
6. **Exit check:** at least one job sourced purely from a company career page (not indexed on any aggregator) makes it through the full pipeline to at least `matched` status.

## Phase 8 — Polish & Feedback Loops

1. Build the Weekly Summary aggregation job + Telegram digest template + dashboard view (doc 16 Flow 6).
2. Build the Discarded Jobs view with score/rationale display (doc 04, doc 15).
3. Build `source_health` banner on the dashboard (doc 15 §6, doc 16 Flow 7).
4. Set up nightly `pg_dump` backup cron (doc 12 §"Backup").
5. Review LLM cost logs (TRD REQ-OBS-2) — confirm cheap-vs-expensive model routing is actually behaving as designed across all modules, adjust if drift is found.

## Cross-Phase Notes for the Agent

- Do not skip a phase's exit check to move faster — each one is a genuine correctness gate, not a formality (especially Phase 1's resume-profile check and Phase 6's trial period, where skipping the gate has real downside).
- Every task above references the doc that defines its detailed behavior — when in doubt about *why* a task is structured a certain way, that doc is the source of truth, not this list's phrasing.
