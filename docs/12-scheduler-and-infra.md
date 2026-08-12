# JobPilot — Scheduler & Infrastructure

## Why This Module Exists

Every other module (discovery, matching, tailoring, applying, contact-finding) needs to run continuously and unattended, on a cadence that balances freshness against platform-risk (aggressive polling on Tier B sources is exactly the kind of pattern that gets accounts flagged). The scheduler is what turns the individual modules into an actual "keeps working while I sleep" system rather than a set of scripts Gaurav has to trigger manually.

## Scheduling Approach

**Start with APScheduler** (in-process, simple, matches the complexity level actually needed for a single-user tool) rather than Celery+Redis task queue, **unless/until** concurrency needs grow (e.g., wanting to run multiple scrapers in true parallel with retry/backoff at scale) — avoid the added operational complexity of a full task queue until the simpler option proves insufficient. Redis is still used for caching and the Telegram bot's state, just not necessarily as a Celery broker in v1.

## Job Schedule (defaults, all configurable via `settings`)

| Job | Cadence | Notes |
|---|---|---|
| Tier A discovery (API sources) | Every 2 hours | Cheap, low-risk, can run frequently |
| Tier A+ dork search discovery | Every 4–6 hours | Runs against a search API, not the target platforms — safe to run often, kept slightly less frequent than raw Tier A mainly to manage search-API quota, not risk |
| Tier B discovery (scrape) | Every 6 hours | Rate-limited per doc 03, deliberately less frequent |
| Tier C career-page crawl | Once daily, per company, staggered | Avoid hitting all target companies simultaneously |
| Matching engine | Runs continuously on new `jobs_raw` rows (event-driven, not polling) | |
| Resume tailoring | Triggered immediately after a job clears matching threshold | |
| Tier A auto-apply | Triggered immediately after tailoring completes | |
| Tier B form pre-fill | Triggered immediately after tailoring completes, subject to daily cap | |
| Contact-finder | Runs in parallel with tailoring, doesn't block application | |
| Source health check | After every discovery run | Feeds `source_health` table and failure alerts |
| Weekly summary | Once weekly (e.g., Sunday evening) | Sent via Telegram + available in dashboard |

## Deployment

- **Backend + workers + bot + Postgres + Redis**: Docker Compose on the existing Webdock VPS (8-core/32GB Ubuntu) — same pattern as Gaurav's other self-hosted projects (Anti-Forward bot, Brefly).
- **Frontend dashboard**: Vercel, matching the AbleSpace project's planned frontend/backend split.
- **Environment separation**: a single `docker-compose.yml` with named services (`api`, `discovery`, `matcher`, `tailor`, `apply`, `contacts`, `bot`, `postgres`, `redis`), each with its own `.env` for secrets.

## Resource Considerations

- Playwright browser instances are the heaviest resource consumer (each headless browser context uses real memory) — cap concurrent Playwright sessions (e.g., max 2–3 at once) to stay well within the VPS's 32GB, especially since Postgres/Redis/other services share the same box.
- LLM API calls (Claude) are the main cost driver, not compute — cost management principles from docs 04/05/07 (cheap model for extraction, stronger model only where output quality is user-facing) apply system-wide, not per-module.

## Monitoring & Alerting

- `source_health` table (doc 11) tracks consecutive failures per source; 3+ consecutive failures triggers a Telegram alert (per doc 10) rather than failing silently.
- Basic uptime check on `jobpilot-api` and `jobpilot-bot` (simple cron-based ping, or reuse whatever lightweight monitoring Gaurav already has on the VPS) — if the bot goes down, Gaurav has no visibility into the system at all, so this is the single most important process to keep alive.

## Backup

- Nightly `pg_dump` of the Postgres database to the VPS filesystem (and optionally synced off-box) — the `resume_profile`, `applications`, and `contacts` data represents real accumulated job-search history and should not be casually losable.

## Why Not Cloud-Managed Services (e.g., managed Postgres, serverless functions)

Consistent with Gaurav's existing infra choices across all his other projects — self-hosting on the Webdock VPS keeps this at zero incremental infra cost and reuses operational knowledge he already has (Docker Compose, xrdp/XFCE environment already configured), rather than introducing a new platform to learn and pay for.
