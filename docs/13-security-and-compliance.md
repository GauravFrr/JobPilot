# JobPilot — Security, Compliance & Risk Boundaries

## Why This Doc Exists

This project sits close to several platforms' Terms of Service by design — that's inherent to any automated job-application tool. This doc exists to make the risk boundaries explicit and permanent, so they don't quietly erode as the system evolves ("just one more automation" creep is how these tools usually end up getting accounts banned).

## The Core Boundary: Public Data & Own-Session Automation, Never Session-Hijacking of Private APIs

This distinction came up directly during scoping (the "Upwho" reference tool) and is worth stating precisely, since it governs multiple modules:

**What JobPilot does:**
- Reads publicly rendered pages (job search results, career pages) — the same data visible to a logged-out visitor or a search engine.
- Uses Gaurav's **own** logged-in session, through his **own** browser automation, to fill out forms on platforms **he** has an account on — functionally similar to using a browser extension or autofill tool on his own account.
- Uses documented, publicly-intended APIs (RemoteOK, Greenhouse, Lever, etc.) exactly as they're meant to be used by third-party integrations.

**What JobPilot does not do, on any platform, at any tier:**
- Reverse-engineer and call a platform's private/internal API endpoints that aren't meant for third-party or programmatic use, even using Gaurav's own authenticated session.
- Attempt to extract another party's private data (e.g., a client's identity on a platform where that identity is deliberately anonymized/intermediated by the platform) via session-based access to internal systems.
- Bypass CAPTCHA/bot-challenge systems programmatically (doc 06's hard-stop rule).

**Why this line matters practically, not just in principle:** the risk profile is genuinely different. Using a public API as intended, or automating one's own account through the same UI a human would use, is a ToS/rate-limit risk (account could still be flagged for automation patterns) but not the same category as accessing a system's internal APIs without authorization — the latter is a materially different kind of risk to both the account and, depending on jurisdiction and platform, potentially beyond just "account banned." JobPilot only ever operates in the former category.

## Credential Handling

- Tier B platform credentials (LinkedIn, Naukri, etc.) are Gaurav's own, stored encrypted at rest (e.g., via a secrets manager pattern or encrypted `.env`/vault, not plaintext in the database).
- Playwright sessions persist cookies/session state locally on the VPS, not transmitted anywhere beyond what's needed for the automation itself.
- No credentials are ever logged in plaintext, including in error logs or the `applications.request_payload_snapshot` field (redact sensitive fields before storage).

## Platform ToS Risk — Managed, Not Eliminated

Even within the above boundary, Tier B automation (auto-filling forms, scraping search pages) still carries *some* residual ToS risk on platforms that prohibit any automation. This is why:
- Tier B never auto-submits (doc 06) — a human decision precedes every actual action taken on these platforms.
- Rate limits and daily caps are enforced even on the pre-fill step, not just the submit step (doc 06).
- Any bot-challenge/CAPTCHA encounter triggers an immediate stop, not a retry (doc 06).

This doesn't reduce risk to zero, but it keeps the risk proportional and bounded, with Gaurav always the final actor on the platforms most likely to react to automation.

## Data the System Collects — Personal Data Handling

- `resume_profile` and `applications` contain Gaurav's own personal/career data — standard handling (encrypted backups per doc 12, no third-party sharing).
- `contacts` contains third parties' names, titles, and inferred/verified contact info sourced from public data. This data is used solely to enable Gaurav's own outreach, not stored/sold/shared beyond that purpose, and not retained indefinitely without reason — a reasonable future addition would be a retention policy (e.g., purge contact records for jobs older than N months that were never acted on).

## What Happens If a Platform Changes Its Detection or Blocks the Bot

- Discovery/apply workers should fail gracefully (per doc 03's failure handling and doc 06's hard-stop-on-challenge rule) — the correct response to increased friction from a platform is to reduce or pause automation on that source, not to engineer around the block. If a platform tightens detection to the point that even careful Tier B automation is unreliable, that source degrades to Tier D (manual leads only) rather than escalating countermeasures.

## Summary Principle

The system is designed so that **the worst-case failure mode is "this source stops working and Gaurav does it manually again,"** never "Gaurav's account gets banned" or "the system accessed something it shouldn't have." Every design decision in docs 03, 06, and 07 traces back to protecting that invariant.
