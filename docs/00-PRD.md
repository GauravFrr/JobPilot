# JobPilot — Product Requirements Document (PRD)

## 1. Product Summary

JobPilot is a personal job-application automation system for Gaurav. It discovers relevant AI/Backend/Full-Stack/Mobile roles across public APIs, dork-based search, scraped platforms, and company career pages; scores them for relevance against his real skill profile; generates a JD-tailored resume for each qualifying role; pre-builds the application (instant-ready for API/ATS sources, pre-filled for scraped platforms) and surfaces it with `Apply`/`Pass` controls — nothing is ever submitted without that tap, regardless of source; finds a human contact behind the posting where possible; and drafts (but never auto-sends) outreach messages — all surfaced through a Telegram bot and a web dashboard.

## 2. Problem

See doc 01 §1 for full detail. In short: quality remote AI/Backend/Full-Stack roles exist across 10+ fragmented sources; manually tailoring a resume and applying to each is slow, so real application volume stays low; and cold outreach — which meaningfully raises response rates — almost never happens because finding the right contact is its own research task.

## 3. Target User

Gaurav only, v1. Single-user tool, not a multi-tenant product (see doc 01 §4 — non-goals explicitly exclude SaaS-ification in v1).

## 4. Goals & Success Metrics

| Goal | Metric |
|---|---|
| Increase quality applications/week without more manual hours | Applications/week with match score ≥ threshold, tracked in Weekly Summary |
| Never risk real platform accounts | Zero bans across LinkedIn/Naukri/Wellfound/Instahyre, tracked via source_health uptime |
| Every application uses a JD-tailored resume | 100% of `applications` rows have a linked `resume_versions` row |
| Surface a human contact where possible | ≥ 40–50% of applications have an attached `contacts` record |
| Full visibility, nothing silently lost | 100% of jobs that reach application-ready state land in one of: ready_to_apply / applied / skipped / manual_lead — never stuck in an ambiguous state |

(Full detail and rationale for each goal: doc 01 §3/§5.)

## 5. Functional Requirements

### 5.1 Job Discovery
- FR-1: System discovers jobs from Tier A (open APIs/ATS), Tier B (scrape-gated platforms), Tier C (career pages), Tier D (manual-only sources) on independent schedules.
- FR-2: Every discovered job is deduplicated against existing records before insertion.
- FR-3: Tier C companies are checked for underlying known-ATS fingerprints and reclassified to Tier A when detected.
- Full spec: doc 03.

### 5.2 Matching
- FR-4: Every new job is scored for relevance against the active resume profile.
- FR-5: Jobs below `min_match_score` are discarded (not deleted) and viewable, not surfaced as active leads.
- FR-6: Ambiguous-score jobs get a secondary LLM rerank pass before final classification.
- Full spec: doc 04.

### 5.3 Resume Tailoring
- FR-7: Every job clearing the match threshold gets a tailored resume generated before any application step.
- FR-8: Tailoring never fabricates experience, tools, or metrics not present in the master resume profile.
- FR-9: Every tailored resume is versioned and permanently linked to the job it was generated for.
- Full spec: doc 05.

### 5.4 Application Submission
- FR-10: Every job (any tier) that clears matching + tailoring is pre-built to the point of being one tap from submission, and shown with `Apply`/`Pass` controls — nothing submits without that tap.
- FR-11: Tier A/A+ jobs submit near-instantly on `Apply` (a single pre-built API call); Tier B/complex-Tier C jobs submit via a pre-filled form on the same `Apply` tap. Neither ever submits without it.
- FR-12: Daily application caps are enforced per platform, independently configurable.
- FR-13: Any bot-challenge/CAPTCHA encounter halts that source immediately, no auto-retry.
- Full spec: doc 06.

### 5.5 Contact Discovery
- FR-14: System attempts to resolve a human contact (name, title, LinkedIn, email) for each matched job using public-data methods only.
- FR-15: Every contact field shown must have a traceable evidence source; unverifiable claims are dropped, not shown unlabeled.
- Full spec: doc 07.

### 5.6 Outreach
- FR-16: System drafts a personalized outreach message when a contact is found.
- FR-17: No outreach message is ever sent automatically — human sends manually, always.
- Full spec: doc 08.

### 5.7 Dashboard & Notifications
- FR-18: Web dashboard shows all applications across three lanes (Ready to Apply, Applied, Manual Leads) plus a Discarded view.
- FR-19: Telegram bot mirrors key actions (confirm/skip) so either interface can complete the same workflow.
- FR-20: Weekly summary digest sent automatically.
- Full spec: docs 09, 10, 15, 16.

## 6. Non-Functional Requirements

- **NFR-1 (Safety):** No platform automation may use session-hijacked private/internal APIs at any tier, ever (doc 13).
- **NFR-2 (Auditability):** Every application action is logged with full request/response snapshot, redacted of credentials (doc 06, 13).
- **NFR-3 (Cost control):** LLM calls use tiered model selection — cheap models for extraction/classification, stronger models only for user-facing generation (doc 05 §"Cost Management").
- **NFR-4 (Resilience):** A failure in one source/module must not cascade — discovery, matching, tailoring, applying, and the bot are independently fault-tolerant (doc 12).
- **NFR-5 (Data integrity):** Nightly backups of Postgres; no unrecoverable loss of application history or resume profile (doc 12).

## 7. Out of Scope (v1)

- Multi-user/SaaS auth, billing, tenant isolation.
- No fully automatic submission on any platform without Gaurav's explicit `Apply` tap — this applies uniformly across all tiers, not only ones that prohibit automation in their ToS (doc 06's core design decision).
- Auto-sending outreach messages.
- Auto-tuning match scoring or outreach copy from behavioral feedback (flagged as possible v2 only).
(Full list: doc 01 §4, doc 14 "Explicitly Deferred.")

## 8. Assumptions & Dependencies

- Gaurav maintains his own accounts on Tier B platforms; JobPilot automates his own session, not a shared/pooled account.
- Claude API and an embedding provider (Gemini, per existing MemoryOS usage) are available and budgeted for.
- Webdock VPS has sufficient headroom (8-core/32GB) for Postgres, Redis, workers, and a small number of concurrent Playwright sessions.

## 9. Open Decisions (flagged, not yet resolved)

- Final daily cap values per Tier B platform — start conservative, tune after Phase 6 trial period (doc 14).
- Whether Celery/Redis task queue is ever needed over APScheduler — deferred until load requires it (doc 12).
