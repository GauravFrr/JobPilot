# JobPilot — Architecture & Tech Stack

## 1. High-Level System Diagram (textual)

```
[Schedulers: APScheduler/Celery beat]
        │
        ▼
[Discovery Workers] ──► Tier A sources (APIs)
        │               Tier A+ dork search (search engine API, feeds Tier A/B/C)
        │               Tier B sources (Playwright scrape)
        │               Tier C sources (career page crawl + ATS detection)
        │
        ▼
[Raw Job Store (Postgres: jobs_raw)]
        │
        ▼
[Matching Engine] ──uses──► [pgvector: resume/skills embeddings]
        │
        ▼ (score >= threshold)
[Resume Tailoring Worker] ──calls──► Claude API
        │
        ▼
[Application Router]
   ├─ Tier A → Auto-Apply Worker → submits directly (API/ATS)
   └─ Tier B/C(custom) → Form-Fill Worker → holds in Pending Queue
        │
        ▼
[Contact-Finder Worker] ──► LinkedIn public search, ATS metadata,
                             email inference, web verification
        │
        ▼
[Postgres: applications, contacts, resume_versions]
        │
        ├──► [Telegram Bot] — notifications + inline confirm
        └──► [Web Dashboard: Next.js] — full view + settings
```

## 2. Tech Stack (all choices reuse Gaurav's existing proven stack)

| Layer | Choice | Why |
|---|---|---|
| Backend API | **FastAPI** (Python) | Matches Retryv/existing RAG backend, async-native, good for scraping/LLM orchestration |
| Frontend | **Next.js 15** | Matches gauravxd.dev, familiar, fast to ship dashboard UI |
| Alt backend service (bot) | **NestJS** — optional, only if Telegram bot logic grows complex enough to want structured DI | Matches MemoryOS backend pattern |
| Database | **PostgreSQL + pgvector** | Same as Retryv/MemoryOS — one skillset for relational + vector data |
| Cache/Queue broker | **Redis** | Already used in Anti-Forward bot and MemoryOS |
| Task scheduling | **APScheduler** (simple) or **Celery + Redis** (if concurrency needs grow) | Start with APScheduler, upgrade only if discovery volume demands it |
| Browser automation | **Playwright** (Python) | Handles Tier B scraping + form-fill, headless, stealth-capable |
| Search API (dork discovery) | **Google Custom Search JSON API** or **Bing Web Search API** (SerpAPI as a paid fallback if free-tier quota is limiting) | Zero-risk discovery layer — public search only, no platform touched directly (doc 03 Tier A+) |
| LLM (tailoring, extraction, matching rerank) | **Claude API** (primary), cheaper model for high-volume extraction steps | Matches existing usage pattern across projects (Retryv, Brefly used Claude/Gemini for structured tasks) |
| Embeddings | Gemini embeddings (as used in MemoryOS) or Claude-compatible embedding model | Consistency with MemoryOS |
| PDF generation | **WeasyPrint** | Same as Brefly's report generation |
| Telegram bot | **aiogram 3** | Direct reuse of Anti-Forward bot's stack and patterns |
| Containerization | **Docker Compose** | Same deployment shape as everything else on the VPS |
| Hosting | **Webdock VPS** (backend, bot, workers, Postgres, Redis) | Existing infra, no new hosting to manage |
| Frontend hosting | **Vercel** (Next.js dashboard) | Matches AbleSpace project's planned deployment split |

## 3. Service Breakdown

1. **`jobpilot-api`** (FastAPI) — core REST API: jobs, applications, contacts, resume profile, settings. Serves the Next.js dashboard.
2. **`jobpilot-discovery`** — worker process(es) for Tier A/B/C job discovery, running on schedule.
3. **`jobpilot-matcher`** — embeds and scores new jobs against the resume/skills profile.
4. **`jobpilot-tailor`** — generates tailored resume + PDF per qualifying job.
5. **`jobpilot-apply`** — pre-builds Tier A submission payloads and pre-fills Tier B forms; completes actual submission only after a Gaurav's `Apply` tap (doc 06).
6. **`jobpilot-contacts`** — runs contact-discovery + verification pipeline.
7. **`jobpilot-bot`** — aiogram Telegram bot, subscribes to application/contact events, sends notifications with inline buttons.
8. **`jobpilot-web`** — Next.js dashboard.

These can run as separate Docker containers sharing the same Postgres/Redis, orchestrated via `docker-compose.yml`. For v1, discovery/matcher/tailor/apply/contacts can actually live in one worker codebase with separate scheduled jobs — split into distinct services only if load requires it. Avoid premature microservice overhead.

## 4. Data Flow — Single Job Lifecycle (concrete walkthrough)

1. Discovery worker pulls a new listing from RemoteOK API → inserts into `jobs_raw` with `source_tier = 'A'`, `status = 'discovered'`.
2. Matcher worker picks it up, embeds the JD, compares against the active resume/skills profile vector, computes a score. If `score < threshold` → `status = 'discarded'`, stop.
3. If `score >= threshold` → tailoring worker generates a tailored resume (Claude API call with JD + master profile), renders PDF, stores as `resume_versions` row linked to the job.
4. Application router checks `source_tier` and prepares — but does not submit — the application:
   - Tier A → apply worker pre-builds the full submission payload via the source's application API → `status = 'ready_to_apply'` → event fired.
   - Tier B/C-custom → form-fill worker fills the form via Playwright but does **not** submit → `status = 'ready_to_apply'` → event fired.
5. Contact-finder worker (runs in parallel, not blocking application) attempts to resolve a contact for the job's company/role → attaches to `contacts` table if found, with evidence.
6. Telegram bot receives the event, sends a "🟢 Ready to Apply" message with `Apply` / `Pass` inline buttons — Tier B messages additionally show a filled-form preview.
7. Gaurav taps `Apply` (in Telegram or the dashboard — same endpoint either way) → apply worker completes submission: an instant API call for Tier A, a Playwright click for Tier B → `status = 'applied'`. Tapping `Pass` instead sets `status = 'skipped'`, nothing submitted.
8. All state is visible in the dashboard's lanes at any time — per doc 06's core design decision, nothing reaches `applied` without a real tap from Gaurav, regardless of tier.

## 5. Environment & Config

- `.env` per service: DB connection string, Redis URL, Claude API key, Telegram bot token, per-platform credentials (only for Tier B, stored encrypted — see doc 13 for handling).
- Target company list, keyword filters, min match score, and platform toggles live in `settings` table, editable from the dashboard — not hardcoded.

## 6. Why Not a Single Monolith Script

Gaurav could technically write this as one big script, but the service breakdown above matters because:
- Discovery and apply need independent retry/backoff logic (scraping is flaky; a bad Playwright run shouldn't crash the whole pipeline).
- The bot needs to stay responsive even if a discovery run is mid-flight.
- Clear service boundaries make it easy to later split into containers or scale up/down (e.g., run more scraping workers, keep the bot as a single instance).
