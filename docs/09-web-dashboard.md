# JobPilot — Web Dashboard

## Why This Module Exists

Telegram is great for real-time nudges but bad for browsing, filtering, and editing settings. The dashboard is the system of record — the place Gaurav goes when he wants the full picture (weekly review, adjusting the resume profile, tuning thresholds) rather than reacting to a single notification.

## Tech

Next.js 15, same visual system as gauravxd.dev where sensible (clean, purposeful, not over-designed) but functionally dashboard-first, not marketing-site-first. Talks to `jobpilot-api` (FastAPI) over REST.

## Core Views

### 1. Applications Board (primary view, three lanes)

**Per doc 06's core design decision, nothing submits without a tap — so the board reflects that: there is no lane where jobs appear already-submitted without Gaurav's action.**

- **Ready to Apply** — every job (any tier) that's been matched and tailored and is waiting on Gaurav's decision. Card shows: company, role, match score, tailored resume link, contact (if found), source, and **`Apply`** / **`Pass`** buttons directly in the UI (mirrors the Telegram flow — either surface can be used interchangeably). Tier A/A+ cards submit near-instantly on `Apply` tap (single API call); Tier B cards additionally show a filled-form preview before the tap, since Gaurav is reviewing actual form contents, not just an API payload — same tap action either way, just more to glance at first.
- **Applied** — jobs Gaurav has tapped `Apply` on and that submitted successfully. Card shows company, role, match score, `applied_at` timestamp, tailored resume link, contact (if found), source. This is the historical record, not an action queue.
- **Manual Leads** — Tier D + complex Tier C. Card shows company, role, tailored resume (pre-generated), direct apply link, contact if found. No `Apply` button (JobPilot has nothing to submit) — just "Mark as Applied" for Gaurav's own tracking once he's applied manually outside the system.

Each lane is filterable by: source platform, match score range, date range, has-contact (yes/no).

### 2. Discarded Jobs View
- Shows jobs the matching engine scored below threshold, with score + rationale. Lets Gaurav spot-check whether the threshold or resume profile needs tuning (per doc 04's reasoning).

### 3. Job Detail Page
- Full JD, match score breakdown (embedding score + LLM rerank rationale if applicable), tailored resume preview (PDF viewer), full contact evidence trail (per doc 07's evidence schema — shown transparently, not just the final answer), outreach draft if generated, and full application audit log (per doc 06).

### 4. Settings
- **Resume Profile** — structured editor for master resume data (experience, projects, skills, target roles) — this is what feeds doc 04's matching and doc 05's tailoring. Includes a "recompute embeddings" trigger after edits.
- **Target Companies** — manage the Tier C company list (add/remove, see doc 03).
- **Platform Toggles** — enable/disable individual sources per tier.
- **Thresholds & Caps** — `min_match_score`, daily application caps per tier/platform (per doc 06).
- **Default Answers** — common screening-question answers (work authorization, notice period, salary expectations if asked) so Tier A/B forms can be filled confidently without per-job guessing.
- **Telegram Bot Link** — connect/reconnect the Telegram chat ID for notifications.

### 5. Weekly Summary View
- Simple stats: jobs discovered, jobs matched, applications by tier, contacts found, outreach drafts generated, response/interview rate if tracked. Useful for Gaurav's own sense of whether the system and the job search overall are working, separate from any single day's activity.

## Theming

- Light and dark theme, **system-default on first load**, manual toggle persisted per-user (localStorage-equivalent — note: if any part of this is built as a Claude Artifact/demo instead of the real Next.js app, avoid `localStorage` there per platform constraints; the real app has no such restriction).
- Palette: strict black & white (light: white bg/black text/black accent; dark: black bg/white text/white accent) — full token table in `15-ui-ux-specification.md` §1.

## Auth

Single-user tool (Gaurav only) — simple session-based auth is sufficient, no need for multi-tenant user management in v1. If this ever becomes a SaaS (explicitly out of scope per doc 01), auth would need to be revisited entirely at that point, not designed for prematurely now.

## API Surface (consumed from `jobpilot-api`)

- `GET /jobs?status=&tier=&source=` — board views
- `GET /jobs/:id` — detail page
- `POST /applications/:id/apply` — universal Apply tap, any tier (doc 17 §3.2)
- `POST /applications/:id/pass` — universal Pass tap, any tier
- `POST /applications/:id/mark-applied` — manual leads only, self-tracking
- `GET /contacts/:job_id`
- `POST /outreach/:job_id/draft`
- `GET/PUT /settings/resume-profile`
- `GET/PUT /settings/target-companies`
- `GET/PUT /settings/thresholds`
- `GET /stats/weekly-summary`
