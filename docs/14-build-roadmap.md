# JobPilot — Build Roadmap

## Why This Order

Sequenced to get real, usable value as early as possible (Tier A auto-apply is the lowest-risk, highest-immediate-payoff piece) while deferring the highest-effort/most-fragile pieces (Tier B scraping, Tier C crawling) until the core pipeline is proven end-to-end on safer sources. This also matches the pattern already used for Brefly/Nyxleads — ship the core loop first, expand coverage after.

## Phase 0 — Foundation (before any feature work)
- Repo scaffold: FastAPI backend, Next.js frontend, Docker Compose skeleton.
- Postgres + pgvector setup, run schema from doc 11.
- `resume_profile` populated with Gaurav's real data (experience, projects, skills, target roles) — this blocks everything downstream, so it's the true first task.

## Phase 1 — Tier A Core Loop (discovery → match → tailor → auto-apply)
- Tier A discovery workers: RemoteOK, We Work Remotely, Remotive, Greenhouse/Lever APIs.
- Matching engine: embedding similarity + threshold (defer LLM rerank to Phase 1.5 if needed for quality).
- Resume tailoring: Claude API integration, WeasyPrint rendering.
- Tier A apply worker: pre-builds submission payload, holds for `Apply`/`Pass` tap (doc 06).
- **Milestone: a real Tier A job gets discovered, scored, tailored, and reaches `ready_to_apply` with a working `Apply` button that submits near-instantly on tap — no auto-submission without Gaurav's action.**

## Phase 2 — Telegram Bot
- aiogram bot, paired to Gaurav's chat.
- "Ready to Apply" notifications with inline `Apply`/`Pass` buttons (Phase 1's output becomes actionable in real time).
- `/today`, `/pending` commands.
- **Milestone: Gaurav gets a phone notification the moment a Tier A job is ready, taps `Apply`, and it submits — entirely from Telegram, zero dashboard interaction needed.**

## Phase 3 — Web Dashboard (core views)
- Applications board (Ready to Apply lane functional first, with working `Apply`/`Pass` buttons; Applied/Manual lanes stubbed until their data exists).
- Job detail page.
- Settings: resume profile editor, thresholds.
- **Milestone: Gaurav can review and act on everything from Phase 1 without touching the database directly.**

## Phase 4 — Contact-Finder Module
- JD/ATS metadata parsing, LinkedIn public search, email inference + verification.
- Attach to job cards + Telegram notifications.
- **Milestone: a meaningful share of Ready to Apply jobs now show a discovered contact.**

## Phase 5 — Outreach Module
- Draft generation (Claude API), surfaced in dashboard + Telegram.
- **Milestone: Gaurav can go from "job applied" to "outreach message drafted" in one tap.**

## Phase 6 — Tier B (Scrape + Human-in-Loop)
- Playwright scraping for LinkedIn, Naukri, Wellfound, Instahyre discovery.
- Form pre-fill, holding in the same Ready to Apply lane (dashboard + Telegram inline buttons) — per doc 06, this is now the same lane and tap action as Tier A, just with a filled-form preview shown first.
- Rate limiting, daily caps, CAPTCHA hard-stop logic (doc 06).
- **This phase gets the most testing time before trusting it at volume — start with a very low daily cap and raise gradually.**
- **Milestone: a Tier B job gets pre-filled, and a real `Apply` tap (via Telegram button) completes the Playwright submission — with zero platform friction observed over a trial period.**

## Phase 7 — Tier C (Career Page Crawl)
- `target_companies` table + seed list (from existing outreach tracker).
- ATS-fingerprint detection (reclassify to Tier A where possible).
- Custom-page extraction via Claude, routed to Tier B-style or Tier D based on apply-method complexity.
- **Milestone: at least a handful of applications originate from a company career page that wasn't indexed anywhere else.**

## Phase 8 — Polish & Feedback Loops
- Weekly summary view + Telegram digest.
- Discarded-jobs review flow for threshold tuning.
- Source health monitoring + alerting (doc 12).
- Backup automation.

## Explicitly Deferred (not in v1 roadmap at all)
- Multi-user/SaaS auth and billing (doc 01's non-goals).
- Auto-adjusting match scoring from Gaurav's manual overrides (mentioned as a possible v2 idea in doc 04).
- Auto-improving outreach copy from response-rate data (doc 08).
- Any expansion of the security boundary in doc 13 — this is not a "roadmap item," it's a permanent constraint.

## Suggested Cadence

Given Gaurav's current parallel workload (AbleSpace assessment due Aug 21, OIBSIP due Aug 15), this roadmap should run **after** those deadlines clear, or strictly in small time-boxed sessions alongside them — Phase 1 alone is a real multi-day build, not a side-project-in-an-evening scope.
