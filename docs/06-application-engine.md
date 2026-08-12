# JobPilot — Application Engine

## Why This Module Exists

This is the highest-risk module in the system — it's the one that actually acts on Gaurav's behalf on external platforms. Its design is entirely driven by one constraint: **never risk Gaurav's real accounts** while still maximizing genuinely safe automation. The tiering decided in Discovery (doc 03) is consumed here to route each job down the correct path.

## Core Design Decision: Nothing Submits Without a Tap

**Revised from an earlier version of this doc:** originally Tier A was fully automatic, submitting the moment a job cleared matching + tailoring, with no human step at all. That's been changed — **every job that reaches application-ready state, regardless of tier, is shown on screen with an `Apply` / `Pass` choice, and nothing gets submitted anywhere until Gaurav taps `Apply`.**

**Why this is a better design than pure auto-apply, not just a safety compromise:**
- Gaurav stays in control of exactly which companies he's applied to — a fully automatic system could apply to a job he'd actually rather skip (e.g., a company he has a specific reason to avoid) before he ever sees it.
- It gives him a last look at the tailored resume before it goes out, catching any tailoring mistake before submission rather than after.
- It costs almost nothing in speed — Tier A submission is a single API call once triggered, so tapping `Apply` still results in near-instant submission. The system does all the discovery/matching/tailoring work upfront; Gaurav's tap is the last, cheap step, not a bottleneck.

So the tier distinction now governs **what happens after the tap**, not **whether a tap is required**:

## Tier A / Tier A+ / ATS-backed Tier C — One-Tap Apply (Instant Submission)

**Applies to:** RemoteOK/We Work Remotely/Remotive listings, any Greenhouse/Lever/Ashby/SmartRecruiters-backed posting (including dork-discovered and Tier C-reclassified ones).

**Flow:**
1. Apply worker picks up `status = 'matched'` jobs with `source_tier = 'A'` that have a completed `resume_versions` entry, and **pre-constructs** the full application payload per the ATS's documented API (name, email, phone, resume file, cover note if required, answers to screening questions from `resume_profile.default_answers`) — but does not submit yet.
2. `status = 'ready_to_apply'`. Job appears on the dashboard's **Ready to Apply** lane and in a Telegram notification, with `Apply` / `Pass` buttons.
3. **On `Apply` tap:** apply worker submits the pre-built payload via the ATS's public application-submission endpoint immediately. On success → `status = 'applied'`, log full request/response, fire confirmation event. This is fast — the payload was already built in step 1, so the tap-to-submitted latency is just the API call itself.
4. **On `Pass` tap:** `status = 'skipped'`, no submission attempted.
5. On submission failure (e.g., a required field JobPilot can't answer confidently): `status` reverts to a needs-attention state with a note on what's missing — surfaced back to Gaurav rather than silently failing or guessing.

**On "apply via email" within these sources:** JobPilot pre-drafts the email (tailored resume attached, short cover note). Tapping `Apply` sends it (this is the one case where "submission" means sending an email rather than calling an API) — still gated behind the same tap, no different treatment needed since the human-confirm step is now universal anyway.

## Tier B / scraped Tier C — One-Tap Apply (Form Pre-Fill + Submission)

**Applies to:** LinkedIn, Naukri, Wellfound, Instahyre, and Tier C custom pages with simple forms.

**Flow:**
1. Playwright opens the application form using Gaurav's own logged-in session in a controlled browser context (his own account, his own session — not session-hijacking a third party's system; see doc 13).
2. Fills all fields it can confidently answer from `resume_profile` (name, contact info, experience, uploads tailored resume, answers standard screening questions from `default_answers`).
3. **Does not click submit.** Takes a screenshot of the filled form, stores it alongside the draft state, sets `status = 'ready_to_apply'`.
4. Same as Tier A: appears in the **Ready to Apply** lane with `Apply` / `Pass` buttons, plus the filled-form preview so Gaurav can glance at exactly what will be submitted.
5. **On `Apply` tap:** apply worker re-opens the same session state and clicks submit → `status = 'applied'`.
6. **On `Pass` tap:** `status = 'skipped'`, form draft discarded.
7. **Rate limiting is enforced even for the pre-fill step** — no more than a small number of form-fills per platform per day, spaced out, to avoid pattern-based bot detection regardless of the human gate.

**Note on lane naming:** since every lane now requires a tap, "Auto-Applied" is no longer an accurate label anywhere. Dashboard/Telegram terminology updates to **"Ready to Apply"** for all tiers — both land in `status = 'applied'` after the same `Apply` action; the difference is purely presentational (whether a form screenshot is shown alongside) and mechanical (API call vs. Playwright click) underneath, not behavioral from Gaurav's side.

## Tier C (Custom, Complex) & Tier D — Manual Leads Only

Unchanged — no fill/submit automation attempted at all, not even pre-built-and-gated. Dashboard surfaces: company, role, tailored resume (pre-generated), direct apply link, and any discovered contact. Gaurav applies manually outside the system; there's no `Apply` button here since JobPilot has nothing to submit on his behalf.

## Notification / Card Detail (Telegram + Dashboard)

```
🟢 Ready to Apply
Backend Engineer @ Acme Inc
Match score: 88/100
Source: Greenhouse (direct)
Resume: [tailored_v2.pdf]
Contact found: Jane Doe, Talent Lead → LinkedIn

[Apply]  [Pass]  [View in Dashboard]
```

```
🟢 Ready to Apply
AI Engineer @ Beta Co
Match score: 92/100
Source: LinkedIn
Resume: [tailored_v3.pdf]
Form preview: Name ✓ · Email ✓ · Resume ✓ · Work auth: Yes

[Apply]  [Pass]  [View Filled Form]  [View in Dashboard]
```

Tapping `Apply` on either triggers the same `POST /applications/{id}/apply` endpoint (doc 17); the worker resolves what "submit" actually means based on `tier`/`method` internally — Gaurav doesn't need to know or care which mechanism runs underneath.

## Audit Trail

Every application (any tier) logs: `job_id, resume_version_id, tier, status, applied_at, method (api|form|email|manual), request_payload_snapshot, result`. Non-negotiable — Gaurav needs to be able to answer "what exactly did I submit, and when" for any application if it comes up in an interview or follow-up. `applied_at` is now always a genuine human-triggered timestamp, not a scheduler timestamp — this is a meaningful improvement to the audit trail's honesty, since every row now reflects an actual decision Gaurav made.

## Rate Limits & Daily Caps (configurable in settings)

- These now govern the **pre-fill/payload-build step**, not submission volume directly (since submission only happens on tap) — but still matter, because building payloads and pre-filling forms at high frequency is itself a scraping/API-hit pattern that should stay bounded.
- Tier A/A+: higher daily cap (e.g., 15–20/day) since the underlying risk is near-zero.
- Tier B: lower daily cap (e.g., 5–8/day), specifically to avoid platform-side bot-pattern detection on the pre-fill actions themselves.
- Caps are enforced per-platform, not just globally, since detection systems operate per-platform.

## What Happens on Platform Errors / CAPTCHA

If Playwright hits a CAPTCHA or a clear bot-challenge page on a Tier B platform (at pre-fill time or at submit-on-tap time): **stop immediately, do not retry automatically**, flag the job as `status = 'manual_lead'` with a note, and alert Gaurav. Retrying against a challenge page is exactly the pattern that gets accounts flagged — this is a hard stop, not a retry-with-backoff case.

## Stale Ready-to-Apply Jobs

Because nothing submits without a tap, jobs can now sit in `ready_to_apply` for a while if Gaurav is busy. Add a light staleness rule: if a `ready_to_apply` job's underlying posting is later detected as removed/closed (checked opportunistically, not on a tight poll), mark it `status = 'expired'` rather than leaving a dead `Apply` button in the queue — surfaced in the dashboard as a distinct (greyed-out) state, not deleted, so the history stays intact.
