# JobPilot — Coding Rules & Project Structure

## Why This Doc Exists

Docs 00–18 tell Antigravity *what* to build. This doc tells it *how to actually write the code* — style, naming, and structural conventions — so the output reads like code a real developer wrote deliberately, not like AI-generated boilerplate. This matters beyond aesthetics: overly "clever" or over-abstracted AI-style code is harder for Gaurav to debug, extend, and explain in interviews when this project comes up as a portfolio piece.

## 1. Core Principle: Write Like a Human, Not Like an AI Showing Off

**The single biggest rule: use the simplest approach that actually solves the problem.** Don't reach for a design pattern, abstraction layer, or "enterprise" structure unless the problem genuinely needs it. A lot of AI-generated code over-engineers small problems — factories for one implementation, interfaces with a single class implementing them, config systems for values that never change. None of that here.

**Concretely, avoid:**
- Unnecessary abstraction layers ("just in case we need to swap this later" — don't build for a future that isn't specified in the docs).
- Overly generic function signatures with 6 optional parameters when the actual use case only ever calls it 2 ways.
- Deep inheritance hierarchies or heavy use of design patterns (Strategy, Factory, Observer, etc.) where a plain function or a simple `if`/`match` does the job.
- Excessive defensive code for scenarios that can't actually occur given how the function is called internally (validate at system boundaries — API input, external data — not everywhere).
- Comments that restate what the code obviously does (`# increment counter` above `counter += 1`). Comment on *why*, not *what*, and only when the why isn't obvious from context.
- Long, over-explained docstrings for small internal helper functions. Save real documentation for public-facing functions/endpoints where someone genuinely needs the context.

**Do instead:**
- Write the straightforward version first. A `for` loop instead of a clever one-liner if the loop is clearer. A plain `if/elif` chain instead of a dispatch dictionary for 3 cases.
- Functions do one thing, are named clearly, and are short enough to read in one screen — not because "clean code" says so abstractly, but because that's what makes this maintainable by Gaurav months later without re-reading the whole module.
- Prefer explicit over implicit. If a function has a side effect (writes to DB, calls an external API), that should be obvious from its name and its place in the code, not buried inside a "helper."

## 2. Naming Conventions — Sound Like a Real Codebase, Not a Textbook

- **Variables/functions:** plain, descriptive, no unnecessary jargon. `get_matching_jobs()` not `retrieveRelevantJobPostingsForCandidate()`. `resume_pdf_path` not `generatedResumeDocumentFileSystemPath`.
- **No AI-tell naming patterns** — avoid names like `process_data_v2`, `handle_utils`, `manager_helper_service`, or generic catch-all files like `utils.py` / `helpers.py` growing into 2000-line dumping grounds. If something needs its own file, name the file after what it actually does (`resume_tailor.py`, not `ai_utils.py`).
- **Booleans read like yes/no questions:** `is_remote`, `has_contact`, `is_ready_to_apply` — matches what's already used in the DB schema (docs 11/17), keep it consistent in code.
- **No cutesy or overly clever names.** Not `JobWhisperer`, not `MagicMatcher`. Just `matcher.py`, `MatchingService`, `discover_tier_a_jobs()`.
- **Consistent casing per language convention:** `snake_case` in Python (backend/workers/bot), `camelCase` in TypeScript/JS (frontend), `PascalCase` for classes/React components in both. Don't mix.
- **File/module names describe content, not layer jargon.** `applications.py` (the applications logic), not `application_business_logic_layer.py`.

## 3. Comments & Documentation Style

- Write comments the way a developer leaves notes for their future self — short, practical, occasional. Not a comment above every line.
- Use a comment when a decision isn't obvious from the code itself — e.g., "// LinkedIn returns stale results if we don't wait here, tested this" — that's a real, useful comment. "// filter the list" above a filter call is not.
- Docstrings on public functions (things another module or the API layer calls) should state what it does and any non-obvious behavior — not restate the parameter types (type hints already do that).
- No emoji in code comments. No exclamation marks. Plain, dry, functional tone — like Gaurav's own commit messages or notes, not marketing copy.

## 4. Complexity Discipline

- Match the tool to the problem's actual size. A 5-line script doesn't need a class. A single scheduled job doesn't need a plugin architecture.
- Don't add configuration knobs, feature flags, or extensibility points that nothing in the docs (00–18) actually asks for. If `18-implementation-plan.md` doesn't call for a feature, don't quietly build the scaffolding for it "for later."
- Prefer standard library / already-chosen stack tools (per doc 02) over pulling in a new dependency for something simple. If FastAPI + SQLAlchemy + Playwright + aiogram already cover it, don't add another library for a one-off task.
- If a genuinely complex problem needs a non-trivial algorithm (e.g., the fuzzy dedup check in doc 03, or the embedding similarity + rerank in doc 04), that's fine — complexity is warranted there because the problem is actually complex, not for its own sake. The rule is "no *unnecessary* complexity," not "never write anything non-trivial."

## 5. Error Handling — Practical, Not Paranoid

- Handle errors where they can plausibly occur (external API calls, scraping, file I/O, LLM calls) — not everywhere defensively.
- Fail loudly and log clearly during development; in production paths that matter (payload pre-build, form pre-fill, the actual submit-on-tap step), fail gracefully per the specific behavior defined in doc 06 (surface the failure back to Gaurav rather than crash or silently retry, hard-stop on CAPTCHA, etc.) — the *behavior* is spec'd in doc 06, this doc just says: implement it plainly, don't wrap it in unnecessary try/except layers "to be safe" beyond what's actually needed.

## 6. Testing Style

- Write tests for behavior that matters (dedup logic, threshold boundaries, the no-fabrication check on tailored resumes, the CAPTCHA hard-stop) per doc 00-TRD §10 — not exhaustive tests for trivial getters/setters.
- Test names describe the scenario in plain language: `test_duplicate_job_from_two_sources_is_merged`, not `test_case_1`.

## 7. Production-Level Project Structure

```
jobpilot/
├── AGENT.md
├── README.md
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .gitignore
│
├── docs/                              # this entire doc suite lives here (00–18 + AGENT.md)
│   ├── 00-PRD.md
│   ├── 00-TRD.md
│   ├── 01-overview-and-vision.md
│   ├── ...
│   └── 18-implementation-plan.md
│
├── api/                                # jobpilot-api (FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                        # DB migrations
│   │   ├── versions/
│   │   └── env.py
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py                   # env/settings loading
│   │   ├── db.py                       # SQLAlchemy session/engine setup
│   │   ├── models/                     # one file per table group
│   │   │   ├── jobs.py                 # jobs_raw, job_scores
│   │   │   ├── resumes.py              # resume_profile, resume_versions
│   │   │   ├── applications.py
│   │   │   ├── contacts.py
│   │   │   ├── outreach.py
│   │   │   └── settings.py             # settings, target_companies, dork_queries, source_health
│   │   ├── schemas/                    # Pydantic request/response models, mirrors doc 17 §3
│   │   │   ├── jobs.py
│   │   │   ├── applications.py
│   │   │   ├── contacts.py
│   │   │   └── outreach.py
│   │   ├── routes/                     # one file per resource, matches doc 17 endpoint groups
│   │   │   ├── jobs.py
│   │   │   ├── applications.py
│   │   │   ├── contacts.py
│   │   │   ├── outreach.py
│   │   │   ├── settings.py
│   │   │   └── stats.py
│   │   └── events.py                   # Redis pub/sub publisher (doc 17 §4)
│   └── tests/
│       ├── test_jobs.py
│       ├── test_applications.py
│       └── test_contacts.py
│
├── workers/                            # discovery, matching, tailoring, apply, contact-finder
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── scheduler.py                    # APScheduler job registration (doc 12)
│   ├── discovery/
│   │   ├── tier_a_apis.py              # RemoteOK, WWR, Remotive, Greenhouse, Lever adapters
│   │   ├── dork_search.py              # Tier A+ dork discovery (doc 03)
│   │   ├── tier_b_scrape.py            # LinkedIn, Naukri, Wellfound, Instahyre
│   │   ├── tier_c_crawler.py           # career page discovery + ATS detection
│   │   └── dedup.py
│   ├── matching/
│   │   ├── embed.py                    # embedding calls
│   │   ├── score.py                    # threshold + rerank logic
│   │   └── rerank.py
│   ├── tailoring/
│   │   ├── extract_keywords.py
│   │   ├── rewrite_resume.py
│   │   └── render_pdf.py
│   ├── applying/
│   │   ├── tier_a_apply.py             # direct API submission
│   │   ├── tier_b_form_fill.py         # Playwright fill, no submit
│   │   └── tier_b_submit.py            # Playwright submit, on confirm
│   ├── contacts/
│   │   ├── ats_metadata.py
│   │   ├── linkedin_search.py
│   │   ├── email_infer.py
│   │   └── verify.py
│   ├── outreach/
│   │   └── draft.py
│   └── tests/
│       ├── test_dedup.py
│       ├── test_scoring.py
│       └── test_tailoring.py
│
├── bot/                                 # jobpilot-bot (aiogram)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── handlers/
│   │   ├── start.py                     # pairing flow
│   │   ├── pending.py                   # /pending command
│   │   ├── today.py
│   │   └── callbacks.py                 # Confirm/Skip/Draft Message button handlers
│   ├── events_listener.py               # subscribes to Redis, sends notifications
│   └── templates.py                     # message templates per doc 10's event table
│
├── web/                                  # jobpilot-web (Next.js)
│   ├── Dockerfile
│   ├── package.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                      # Applications Board (default view)
│   │   ├── jobs/[id]/page.tsx            # Job Detail Page
│   │   ├── discarded/page.tsx
│   │   └── settings/
│   │       ├── page.tsx
│   │       ├── resume-profile/page.tsx
│   │       ├── target-companies/page.tsx
│   │       └── thresholds/page.tsx
│   ├── components/
│   │   ├── JobCard.tsx
│   │   ├── ApplicationsBoard.tsx
│   │   ├── ContactPanel.tsx
│   │   ├── ResumeViewer.tsx
│   │   └── ui/                           # small shared primitives (Button, Badge, Card)
│   │       ├── Button.tsx
│   │       ├── Badge.tsx
│   │       └── Card.tsx
│   ├── lib/
│   │   ├── api.ts                        # fetch wrapper for /api/v1
│   │   └── theme.ts                      # design tokens from doc 15
│   └── styles/
│       └── globals.css
│
└── scripts/
    ├── seed_target_companies.py
    ├── seed_dork_queries.py
    └── backup_db.sh
```

**Why this structure, not a flatter or more "clever" one:**
- Each top-level folder is a deployable service (matches the Docker Compose service list in doc 02 §3) — no ambiguity about what runs where.
- Inside `workers/`, folders map 1:1 to the modules in docs 03–08 (`discovery/`, `matching/`, `tailoring/`, `applying/`, `contacts/`, `outreach/`) — anyone (including Gaurav, months later) can find the code for a given doc by matching the folder name to the doc title.
- `routes/` and `schemas/` in the API mirror doc 17's endpoint groupings directly — the API contract doc and the code structure stay in lockstep.
- No `utils/` dumping ground at the top level. Small shared helpers live inside the module that actually owns that concept (e.g., `dedup.py` lives in `discovery/` since that's the only place it's used).

## 8. What "Done" Looks Like

Code that passes this doc's bar reads like something a competent developer wrote in a normal focused session — clear names, no unnecessary layers, comments only where they add real information, and a file/folder structure where the location of any given piece of logic is guessable just from knowing which doc describes its behavior.
