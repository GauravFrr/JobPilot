# JobPilot — Contact-Finder Module

## Why This Module Exists

Direct outreach to the actual hiring manager or recruiter meaningfully increases response rates over a cold application sitting in an ATS queue — this is standard, well-documented job-search practice. Building this in-house instead of paying for RocketReach/Hunter.io per-lookup keeps costs at zero and lets it plug directly into the application pipeline (contact appears right where Gaurav is about to hit confirm).

## Explicit Method Boundary

This module uses **only public-data methods**. It does not use authenticated session access to any platform's private/internal APIs to extract poster identity (the "Upwho" pattern Gaurav flagged and then explicitly ruled out). Every data source below is either public by design or intended for this kind of lookup. See doc 13 for the full reasoning on why this line is held even though it caps coverage somewhat.

## Data Sources & Method, Per Signal

**1. JD / ATS metadata (highest confidence, free)**
- Greenhouse/Lever/Ashby postings sometimes name the hiring manager or recruiter directly in the JD footer or in structured ATS metadata fields. Parse this first — zero cost, zero risk, often already correct.

**2. LinkedIn public search**
- Search (via public search, not authenticated scraping of private profile data) for `"[Company]" "Talent Acquisition" OR "Recruiter" OR "Technical Recruiter" OR "Hiring Manager" [role keyword]`.
- Extract name + title + public profile URL from public search results — this is the same information visible to any logged-out searcher.
- Confidence scoring: exact company + relevant title match = high confidence; company-only match = medium (flag as "likely, unverified").

**3. Company website / team page**
- If the target company has a public "Team" or "About" page, cross-check names found via LinkedIn search against it for additional verification.

**4. Email pattern inference**
- Once a name + company domain are known, infer likely email using common patterns (`first.last@`, `firstl@`, `first@`) — this is inference, not lookup of private data.
- Verify using a free-tier email-finding API (e.g., Hunter.io free tier) which confirms pattern validity against the domain, or via a lightweight SMTP-verification step where feasible (no send, just deliverability check) — falls back gracefully to "inferred, unverified" if verification isn't possible, and is always labeled as such in the UI.

**5. Social/public profile aggregation**
- If a personal website, X/Twitter, or GitHub is discoverable via public search under the same name (e.g., someone whose LinkedIn also links a personal site), attach as an additional contact channel.

## Verification Step (borrowed pattern, deliberately kept from what Gaurav flagged)

Every extracted claim is checked against its source before being shown as a result — this is the one piece of the "Upwho" workflow worth adopting regardless of the method-boundary difference: an AI extraction step is only useful if it doesn't hallucinate a plausible-sounding but wrong name/email. Concretely:
- Every field in the `contacts` output (`name`, `title`, `linkedin_url`, `email`, `evidence`) must have a corresponding `evidence` entry — a snippet + source URL showing where it came from.
- If a claim can't be traced to a specific source snippet, it's dropped rather than shown unverified-but-unlabeled.
- Use a cheaper/faster model for this extraction+verification pass (same cost-management principle as doc 05) since it runs at volume across every matched job.

## Output Schema (`contacts` table)

```
id, job_id, name, title, company, linkedin_url, email, email_confidence
  ('verified'|'inferred'|'unverified'), website, social_profiles (JSONB),
  evidence (JSONB — list of {field, snippet, source_url}), found_at
```

## Where It Surfaces

- Attached to the job card in the dashboard (all lanes — Ready to Apply, Applied, Manual Leads all show contact info if found).
- Included in Telegram notifications for both the initial "Ready to Apply" alert and any post-hoc contact-found follow-up.
- Feeds directly into the Outreach module (doc 08) as the "Message Contact" action's pre-fill data.

## Failure Mode (No Contact Found)

Common and expected — new companies, no posting history, no team page, no LinkedIn presence. In this case the job card simply shows no contact section; this is not treated as an error, just an expected gap in coverage (mirrors what Gaurav observed about the reference tool's own limitations).

## What This Module Deliberately Does Not Do

- Does not scrape private LinkedIn profile data requiring a logged-in session beyond what a normal public search surfaces.
- Does not purchase or use leaked/breached data sources for email verification.
- Does not attempt to bypass LinkedIn's own rate limits or authentication walls to enrich results.
