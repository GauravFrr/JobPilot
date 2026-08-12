# JobPilot — Technical Requirements Document (TRD)

## 1. Purpose

Where the PRD defines *what* the product must do, this TRD defines *how* it must be built — the technical constraints, standards, and requirements every module must satisfy. Antigravity should treat this as the checklist a build isn't "done" without.

## 2. System Requirements

### 2.1 Platform & Runtime
- Backend: Python 3.11+, FastAPI.
- Frontend: Next.js 15, TypeScript.
- Bot: Python 3.11+, aiogram 3.
- Database: PostgreSQL 15+ with `pgvector` extension enabled.
- Cache/broker: Redis 7+.
- Browser automation: Playwright (Python bindings), Chromium headless.
- Containerization: Docker + Docker Compose, single `docker-compose.yml` orchestrating all services (doc 02 §3).

### 2.2 Hosting
- Backend, workers, bot, Postgres, Redis: self-hosted on existing Webdock VPS (8-core/32GB Ubuntu).
- Frontend: Vercel.
- No managed cloud DB/serverless functions in v1 (doc 12 — consistency with existing infra choices).

## 3. Data Requirements

- All persistent state lives in PostgreSQL per the schema in doc 11 (referenced here, not duplicated) — full DDL in doc 17 (Backend Schema).
- Vector similarity search via `pgvector`, HNSW index (matches MemoryOS precedent).
- All timestamps stored as `TIMESTAMPTZ`, UTC.
- All monetary/salary fields (if captured from JDs) stored as structured `{min, max, currency}` JSONB, never free text, to keep filtering reliable.

## 4. API Requirements

- REST, JSON, versionless in v1 (single consumer — the dashboard — so no versioning overhead needed yet).
- Full endpoint contract: doc 17 (Backend Schema).
- All endpoints require session auth (single-user; see PRD NFR and doc 09 §"Auth").
- Every mutating endpoint (`POST`/`PUT`) must be idempotent where the action could plausibly be double-triggered (e.g., double-tapping `Apply` in Telegram must not double-submit an application) — enforce via a status-check guard before acting (doc 06, doc 10 §"Security").

## 5. Integration Requirements

| Integration | Requirement |
|---|---|
| Claude API | Used for: JD keyword extraction, resume tailoring, contact evidence extraction/verification, outreach drafting, LLM rerank in matching. Model tier selected per task per doc 05/07's cost-management principle — not a single fixed model across all calls. |
| Embedding provider (Gemini) | Used for: resume profile embedding, job description embedding. Must be consistent between the two (same model) since they're compared via cosine similarity. |
| RemoteOK / We Work Remotely / Remotive APIs | Public, documented, no auth required or simple key-based auth — poll per doc 03 Tier A. |
| Greenhouse / Lever / Ashby / SmartRecruiters | Public job-board APIs where available; used both directly (known companies) and via ATS-fingerprint detection from Tier C crawling (doc 03). |
| Telegram Bot API | Via aiogram; single bot instance, paired to one chat ID (doc 10 §"Security"). |
| Hunter.io (or equivalent free-tier email verifier) | Used only for email pattern verification, not for scraping/purchasing contact lists (doc 07 — public-methods boundary). |

## 6. Security Requirements

(Full reasoning: doc 13. This section states the binding requirements only.)

- REQ-SEC-1: No module may call a platform's private/internal/reverse-engineered API endpoints, under any session, at any tier. This applies regardless of technical feasibility.
- REQ-SEC-2: Tier B platform credentials stored encrypted at rest; never logged in plaintext, including in error traces.
- REQ-SEC-3: `applications.request_payload_snapshot` and any stored form-fill data must have credential/PII fields redacted before persistence.
- REQ-SEC-4: Any CAPTCHA/bot-challenge encountered during automation halts that source's run immediately — no retry loop, no workaround logic.
- REQ-SEC-5: Rate limits and daily caps are enforced per-platform at the code level (not just as a UI suggestion) — a hard stop in the worker, not merely a dashboard warning.
- REQ-SEC-6: Outreach messages are never sent programmatically under any condition — the send action must always require an explicit, separate human action outside JobPilot's own automation (copy-paste into LinkedIn/email client).

## 7. Performance & Scale Requirements

- v1 scale target: single user, expected volume in the tens of jobs discovered per day, single-digit to low-double-digit applications per day across all tiers. This is explicitly not a high-throughput system — do not over-engineer for scale that isn't needed (doc 12 §"Why Not Cloud-Managed Services").
- Playwright concurrency capped at 2–3 simultaneous sessions (doc 12 §"Resource Considerations") to protect shared VPS resources.
- Dashboard board views must load in a reasonable time (<2s) at expected data volumes (hundreds, not tens of thousands, of job rows) — standard indexed Postgres queries are sufficient, no need for a search engine layer in v1.

## 8. Reliability Requirements

- REQ-REL-1: A failure in any single discovery source must not halt discovery for other sources (doc 03 §"Failure Handling").
- REQ-REL-2: The Telegram bot process must run independently of worker processes — a slow/stuck scraping job must never make the bot unresponsive (doc 10 §"Reliability Notes").
- REQ-REL-3: Every action reachable via Telegram must have an equivalent path in the dashboard, and vice versa — no action is exclusively available in only one interface (doc 09, doc 16 Flow 3).
- REQ-REL-4: Nightly `pg_dump` backup, retained on-box (and ideally synced off-box) (doc 12 §"Backup").

## 9. Observability Requirements

- REQ-OBS-1: `source_health` tracks consecutive failures per source; 3+ consecutive failures triggers an alert (doc 03, doc 10, doc 16 Flow 7).
- REQ-OBS-2: All LLM calls logged with: task type, model used, token count/cost estimate — needed to monitor the cost-management principle isn't silently drifting toward always using the expensive model.
- REQ-OBS-3: Basic uptime check on `jobpilot-api` and `jobpilot-bot`.

## 10. Testing Requirements (minimum bar before each phase ships)

- Discovery: verify dedup logic against known duplicate-listing scenarios (same job cross-posted to multiple Tier A sources).
- Matching: verify threshold behavior at boundary scores; verify LLM rerank only triggers within the defined middle band, not on every job (cost control check).
- Tailoring: verify no fabricated content — spot-check generated resumes against the master profile for factual grounding.
- Application Engine: Tier A tested against a sandbox/test posting before enabling on real listings; Tier B tested with a very low daily cap and close monitoring for the first trial period (doc 14 Phase 6) before raising limits.
- Contact-Finder: verify every returned field has a non-empty `evidence` entry; verify no result is shown when evidence can't be traced (doc 07 §"Verification Step").

## 11. Compliance Checklist (must be true before any Tier B/C automation goes live)

- [ ] No code path calls an undocumented/private platform API.
- [ ] Rate limits enforced in code, not just configured as intent.
- [ ] CAPTCHA hard-stop implemented and tested.
- [ ] Credentials encrypted at rest, confirmed via a manual check of the database and logs.
- [ ] Outreach send action requires explicit action outside JobPilot.
