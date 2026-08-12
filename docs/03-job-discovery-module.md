# JobPilot — Job Discovery Module

## Why This Module Exists

Every downstream feature (matching, tailoring, applying, contact-finding) needs a normalized stream of job postings. Because sources vary wildly in structure and risk profile, discovery is split into four tiers by **how safely and reliably** a job can be pulled and later submitted for, once Gaurav taps `Apply`. This tiering decision made upstream in discovery is what lets the Application Engine (doc 06) later decide which submission mechanism to use — instant API call vs. Playwright form click — without re-evaluating risk per job. Every tier still requires that same tap; only the mechanism behind it differs.

## Tier A — Open APIs & Known ATS Platforms

**Sources:**
- RemoteOK (public JSON API)
- We Work Remotely (RSS/API)
- Remotive (public API)
- Greenhouse job boards (`boards-api.greenhouse.io`)
- Lever (`api.lever.co`)
- Ashby, SmartRecruiters, Workday — where a public job-list API exists

**Why Tier A is safe:** these are either explicitly public APIs meant for third-party consumption, or ATS platforms that expose a documented, intended-for-integration application API. No ToS is being bypassed — this is the intended use of these endpoints.

**Discovery logic:**
1. Poll each source on a schedule (e.g., every 2–4 hours).
2. Normalize each listing into the common `jobs_raw` schema (see doc 11): title, company, description, location, remote flag, source, source_url, source_job_id, posted_date, raw_payload (JSONB for anything source-specific).
3. Deduplicate against existing `jobs_raw` rows using `(source, source_job_id)` uniqueness, and a secondary fuzzy check on `(company, title, posted_date)` to catch cross-posted listings.

## Tier A+ — Search Dork Discovery (parallel, zero-risk discovery layer)

**Why this exists / gap it fills:** Tier A's API list only covers companies JobPilot already knows to poll (a fixed set of ATS instances/company list). It misses ATS-hosted postings from companies **not** in that list, and it misses public-indexed listings on platforms JobPilot doesn't want to scrape directly (Tier B). Search dorks close this gap using only a public search engine — no platform is ever touched directly, so this is arguably **safer than Tier A itself**, since not even a documented API is being called; it's pure public search.

**Method:** query a search API (Google Custom Search API, Bing Web Search API, or an aggregator like SerpAPI) with targeted dork queries, then parse the result snippets/links — no scraping of the target platform at all, only of the search engine's own results page, which is exactly what it's designed to return to third parties via its API.

**Dork query patterns used:**
- ATS-hosted postings not in the known company list:
  `site:boards.greenhouse.io "backend engineer" remote`
  `site:jobs.lever.co "AI engineer" OR "machine learning engineer"`
  `site:jobs.ashbyhq.com "full stack" remote`
  `site:jobs.smartrecruiters.com "python" backend`
- Public-indexed listings on Tier B platforms, read-only via search snippet (no visit/scrape required to log the lead):
  `site:linkedin.com/jobs/view "backend engineer" remote India`
  `site:naukri.com/job-listings "AI engineer"`
  `site:wellfound.com/jobs "full stack engineer"`
- Company career pages not yet in `target_companies` (feeds Tier C's company discovery too):
  `intitle:"careers" OR intitle:"we're hiring" "RAG" OR "LLM engineer" remote`
  `site:*.com/careers "backend engineer" remote -site:linkedin.com`

**Discovery logic:**
1. Maintain a `dork_queries` table — a list of query templates (role keywords come from `resume_profile.target_roles`, so queries stay in sync with Gaurav's actual target roles rather than being hardcoded separately).
2. Run each query template on a schedule (e.g., every 4–6 hours, cheap and safe enough to run as often as Tier A).
3. Parse results: title, snippet, URL. If URL matches a known ATS pattern (`boards.greenhouse.io/...`, `jobs.lever.co/...`) → extract the job ID from the URL and fetch full details via that ATS's actual Tier A API (reuses Tier A adapters, doesn't scrape) → insert as `source_tier = 'A'`, `source = 'dork:greenhouse'`.
4. If URL matches a Tier B platform (LinkedIn/Naukri/Wellfound/Instahyre) → log title, company, snippet, and URL only (from the search result, not from visiting the page) as a **Tier D-style lead**, tagged `source = 'dork:linkedin'` etc. — full JD text isn't available from a snippet, so these get a "fetch full JD" step at match-time only if the job clears an initial coarse relevance check on title+snippet, minimizing unnecessary visits to the platform.
5. If URL is a company career page not already in `target_companies` → feed it into Tier C's company list as a discovered candidate (doc 03 Tier C §1) rather than processing it separately — avoids duplicating Tier C's ATS-detection logic.
6. Deduplicate against existing `jobs_raw` using the same `(source, source_job_id)` / fuzzy match rules as Tier A.

**Why this is genuinely zero-risk:** the only system being called programmatically is the search engine's own API, used exactly as intended (this is what Google/Bing Search APIs are for — third-party programmatic search). No platform's rate limits, bot detection, or ToS around scraping/automation is ever invoked, because no platform is being directly queried or automated at this stage — only its publicly indexed, search-engine-visible existence.

## Tier B — Scrape + Human-in-Loop Platforms

**Sources:** LinkedIn, Naukri, Wellfound, Instahyre.

**Why these are Tier B, not Tier A:** these platforms explicitly prohibit automated scraping/applying in their ToS and actively detect bot behavior. Discovery (reading public listing pages) is lower-risk than applying, but still needs care:

**Discovery logic:**
1. Playwright browses using a **logged-out or minimally-authenticated session** where possible — reading public search-result pages, not private authenticated API calls.
2. Respect `robots.txt` per domain; if a path is disallowed, don't crawl it — use the platform's own job search UI as a human would, at human-like pace (randomized delays, no parallel hammering).
3. Rate-limit aggressively: a handful of searches per hour, not continuous crawling. This is discovery, not real-time scraping — jobs don't need second-by-second freshness.
4. Extract into the same normalized `jobs_raw` schema, tagged `source_tier = 'B'`.

**Important distinction from the "Upwho" approach Gaurav flagged:** this discovery step does *not* use an authenticated session to call internal/private APIs. It reads what's publicly rendered on search pages, the same information visible to any logged-out visitor or search engine crawler. This keeps discovery itself low-risk even though *application* on these platforms (doc 06) requires a human-confirm gate.

## Tier C — Company Career Pages

**Why this tier is necessary:** a large share of open roles never get posted to aggregators at all — company career pages are often the only source. But there's no standard structure, so this tier needs a detection step before it can be treated as A, B, or D.

**Discovery logic:**
1. Maintain a `target_companies` table (seeded from Gaurav's existing LinkedIn outreach tracker + curated lists of AI/dev-hiring companies). Start with 50–100 companies, expand over time — not "crawl the entire internet," which is unmanageable and low-yield.
2. For each company, resolve a careers URL: try known patterns (`/careers`, `/jobs`, `/join-us`) plus a search fallback (`site:company.com careers`).
3. Fetch the page and inspect network requests / page source for known ATS fingerprints (`boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`, etc.). **If detected → reclassify this company's postings as Tier A** and use that ATS's API directly. This single detection step is what gives Tier C most of its coverage cheaply — a large fraction of "custom-looking" career pages are actually white-labeled ATS instances underneath.
4. If no known ATS is detected, it's a true custom page: render with Playwright, pass the extracted text to Claude with a structured-extraction prompt (title, description, location, apply-method) to parse listings. Output classified as Tier C-custom.
5. From there, inspect the apply mechanism:
   - Simple form (name, email, resume upload, few fields) → route to **Tier B behavior** (form pre-fill + human confirm) at application time.
   - "Apply via email" or complex multi-step / login-required flow → route to **Tier D** (manual lead only, no automation attempted).

## Tier D — Manual Leads

No scraping automation attempted beyond initial listing capture. These surface in the dashboard as a card with company, role, JD summary, and a direct link — Gaurav applies manually. Still gets matching + resume tailoring + contact-finding applied, just not auto-fill/auto-submit.

## Common Normalization Schema (`jobs_raw`)

All discovery methods write into one table so downstream modules don't need tier-specific logic:

```
id, source, source_tier ('A'|'B'|'C'|'D'), source_job_id, source_url,
company, title, description_text, location, is_remote,
posted_date, discovered_at, raw_payload (JSONB), status
```

Note: `source_tier` reflects the *risk/automation tier* (A/B/C/D per doc 06's application routing), not the discovery *method*. Dork-discovered jobs are tagged with whatever tier their resolved source actually is — an ATS-hosted job found via a dork query is still `source_tier = 'A'` (auto-applies safely via the ATS API), while a LinkedIn job found via a dork query is still `source_tier = 'B'` (still needs human-confirm at apply time, since finding it via search doesn't change LinkedIn's own automation risk). The `source` field (e.g., `dork:greenhouse`, `dork:linkedin`) simply records *how* it was found, for coverage tracking.

`status` values: `discovered` → `matched` / `discarded` → `tailored` → `ready_to_apply` → `applied` / `skipped` / `manual_lead` / `expired`.

## Failure Handling

- Per-source scraper failures (site layout change, block page, CAPTCHA) should log and skip, not crash the discovery run. Alert via Telegram if a source fails repeatedly (e.g., 3 consecutive runs) so Gaurav knows a scraper needs fixing rather than silently losing coverage.
- Respect exponential backoff on repeated failures per source to avoid hammering a platform that may be actively blocking.

## Explicitly Rejected Approach

Using an authenticated session to call a platform's private/internal APIs (reverse-engineered, not publicly documented) is **not used at any tier**, including for discovery. This is the core boundary distinguishing this module from tools like "Upwho." See doc 13 for the full reasoning.
