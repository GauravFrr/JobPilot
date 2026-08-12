# JobPilot — Backend Schema (Database + API Contract)

## 1. Purpose

Doc 11 covered database tables. This doc is the complete backend contract Antigravity builds against: the same DB schema (restated here for a single source of truth) **plus the full REST API contract** — every endpoint, request/response shape, status codes, and error handling. Doc 09's "API Surface" section was a summary list; this is the actual implementation-ready spec.

## 2. Database Schema (authoritative — supersedes doc 11 as the reference copy)

See doc 11 for the full DDL with inline rationale per table. Table list, unchanged:

`jobs_raw`, `resume_profile`, `job_scores`, `resume_versions`, `applications`, `contacts`, `outreach_drafts`, `target_companies`, `settings`, `source_health`.

No schema changes here — doc 11 remains correct. This doc adds the API layer on top of it.

## 3. REST API Contract

Base URL: `/api/v1` (versioned prefix even though doc 15 TRD §4 notes v1 has one consumer — cheap to add now, expensive to retrofit).

Auth: session cookie (single-user). All endpoints below require an authenticated session unless noted.

### 3.1 Jobs

**`GET /api/v1/jobs`**
Query params: `status`, `tier`, `source`, `min_score`, `max_score`, `has_contact` (bool), `date_from`, `date_to`, `page`, `page_size` (default 20).
Response `200`:
```json
{
  "results": [
    {
      "id": "uuid", "company": "Acme Inc", "title": "Backend Engineer",
      "tier": "A", "status": "applied", "match_score": 88,
      "source": "greenhouse:acme", "discovered_at": "iso8601",
      "has_resume_version": true, "has_contact": true
    }
  ],
  "total": 42, "page": 1, "page_size": 20
}
```

**`GET /api/v1/jobs/{job_id}`**
Response `200`: full job object — `jobs_raw` fields + latest `job_scores` + `resume_versions` list + `contacts` (if any) + `applications` history + `outreach_drafts` (if any).
Response `404` if not found.

**`GET /api/v1/jobs/{job_id}/resume/{version_id}/pdf`**
Returns the PDF file (`Content-Type: application/pdf`) for inline viewer rendering.

### 3.2 Applications

**`POST /api/v1/applications/{application_id}/apply`**
The universal "Apply" tap — works identically for Tier A (instant API/email submission) and Tier B (Playwright clicks submit on the pre-filled form). The worker resolves the correct mechanism internally based on `tier`/`method`; the client doesn't need to know which (doc 06 "Core Design Decision").
Guard: only valid if `status == 'ready_to_apply'` — else `409 Conflict` with `{"error": "not_ready"}` (idempotency requirement, TRD §4) — this is what prevents a double-tap or a stale button from double-submitting.
Response `202 Accepted`: `{"application_id": "uuid", "status": "applying"}` — actual submission is async; client polls or awaits the follow-up event/webhook. Tier A resolves near-instantly; Tier B may take a few seconds (real Playwright click).

**`POST /api/v1/applications/{application_id}/pass`**
The universal "Pass" tap — skips the job without submitting anything, any tier.
Guard: same as above (`status == 'ready_to_apply'`).
Response `200`: `{"application_id": "uuid", "status": "skipped"}`

**`POST /api/v1/applications/{application_id}/mark-applied`**
For Tier D/manual leads only — self-tracking, no automation triggered.
Response `200`: `{"application_id": "uuid", "status": "applied", "method": "manual"}`

**`GET /api/v1/applications/{application_id}`**
Full audit record: `request_payload_snapshot` (redacted per TRD REQ-SEC-3), `result`, timestamps.

### 3.3 Contacts

**`GET /api/v1/contacts/{job_id}`**
Response `200`: contact object with full `evidence` array, or `404` if none found (not an error state — expected per doc 07's failure mode; frontend should render this as "no contact" not as an error banner).

### 3.4 Outreach

**`POST /api/v1/outreach/{job_id}/draft`**
Body: `{"channel": "linkedin" | "email"}`
Response `201`: `{"draft_id": "uuid", "draft_text": "...", "channel": "linkedin"}`
Requires an existing `contacts` row for the job — `404` if none.

**`PATCH /api/v1/outreach/{draft_id}`**
Body: `{"sent": true}` — Gaurav marking a draft as manually sent.
Response `200`.

### 3.5 Settings

**`GET /api/v1/settings/resume-profile`** → current active `resume_profile`.
**`PUT /api/v1/settings/resume-profile`** → updates content, increments `version`, marks embedding stale (`embedding = NULL` until recompute).
**`POST /api/v1/settings/resume-profile/recompute-embedding`** → triggers embedding job, response `202`.

**`GET/PUT /api/v1/settings/target-companies`** → list/replace `target_companies`.
**`GET/PUT /api/v1/settings/thresholds`** → `min_match_score`, `daily_caps_by_platform`.
**`GET/PUT /api/v1/settings/platform-toggles`** → per-source enable/disable.
**`GET/PUT /api/v1/settings/default-answers`** → screening-question defaults (doc 06).
**`POST /api/v1/settings/telegram/pair`** → generates a one-time pairing token consumed by the bot's `/start` command.

### 3.6 Stats

**`GET /api/v1/stats/weekly-summary`**
Response `200`:
```json
{
  "week_start": "iso8601", "discovered": 34, "matched": 11,
  "ready_to_apply": 11, "applied": 8, "skipped": 3,
  "manual_leads": 4, "contacts_found": 6, "outreach_drafts": 4
}
```

### 3.7 Source Health (internal/admin use, still exposed for dashboard banner per doc 15 §6)

**`GET /api/v1/source-health`** → list of `source_health` rows, used to render the "scraper failing" banner.

## 4. Internal Worker-to-API Contract (not public-facing, used between services)

Workers (`jobpilot-discovery`, `jobpilot-matcher`, `jobpilot-tailor`, `jobpilot-apply`, `jobpilot-contacts`) write directly to Postgres rather than going through the REST API (they're trusted internal services on the same network) — but every write that changes a job's `status` must also publish an event to Redis pub/sub, which both `jobpilot-api` (for any live dashboard updates, if implemented) and `jobpilot-bot` (for Telegram notifications) subscribe to.

**Event schema (Redis pub/sub, channel `jobpilot:events`):**
```json
{
  "event_type": "job.ready_to_apply" | "job.applied" |
                "job.contact_found" | "job.application_failed" |
                "source.failing" | "summary.weekly",
  "job_id": "uuid (nullable for summary/source events)",
  "payload": { "...event-specific fields..." },
  "timestamp": "iso8601"
}
```

This event contract is what doc 10's Telegram notification table (§"Notification Events") actually consumes — each `event_type` maps 1:1 to a notification template.

## 5. Error Handling Standard

All API errors follow a consistent shape:
```json
{ "error": "short_code", "message": "human readable", "detail": {} }
```
Standard codes used across the API: `not_found`, `not_pending` (idempotency guard), `validation_error`, `upstream_failure` (e.g., Claude API or platform API call failed), `rate_limited` (internal daily cap hit, not an HTTP 429 from an external platform — those are logged in `applications.result` instead).

## 6. What This Doc Does Not Cover

- Playwright scraping selectors/logic — that's implementation detail within `jobpilot-discovery`/`jobpilot-apply`, not part of the API contract, and will necessarily evolve as platforms change their DOM (doc 03/06 already cover the behavioral rules; exact selectors are a living implementation concern, not a spec artifact).
- LLM prompt templates — covered conceptually in docs 04/05/07/08; exact prompt text is an implementation/tuning detail, iterated during Phase 1+ of the roadmap (doc 14), not fixed upfront.
