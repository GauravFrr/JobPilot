# JobPilot — Telegram Bot

## Why This Module Exists

Gaurav shouldn't need to open the dashboard to know what's happening or to act on a job waiting for his decision — the bot is the low-friction, always-on interface, matching the same reasoning behind his existing Anti-Forward bot and Paid Content Gate Bot builds. Reuses the same **aiogram 3 + async SQLAlchemy** pattern directly.

## Core Responsibilities

1. **Notify** on key pipeline events (not everything — see "Notification Discipline" below).
2. **Accept `Apply`/`Pass` actions** via inline buttons for any job in `ready_to_apply` state, without requiring the dashboard — this is the bot's most important job, per doc 06's core design decision that nothing submits without a tap.
3. **Surface outreach drafts** on request, inline.
4. **Answer simple status queries** (e.g., `/pending`, `/today`) without needing the web app.

## Notification Events

| Event | Message content | Actions |
|---|---|---|
| Job ready to apply (any tier) | Company, role, match score, resume version, contact if found. Tier B additionally shows a filled-form preview line. | Apply / Pass / View in Dashboard |
| Job applied (confirmation after a tap, from either interface) | Company, role, applied timestamp | View in Dashboard |
| Contact found (post-hoc, if discovery lagged the initial notification) | Contact name/title/LinkedIn/email + evidence summary | Draft Message |
| Application failed (submission error after `Apply` tap) | Company, role, error reason | Retry / Mark Manual Lead |
| Source scraper failing repeatedly (per doc 03's failure handling) | Source name, consecutive failure count | (informational only) |
| Daily/weekly summary | Counts: discovered, matched, ready to apply, applied, contacts found | View Full Summary in Dashboard |

## Notification Discipline (deliberately not everything)

Discarded (below-threshold) jobs do **not** trigger notifications — only the weekly summary references the discard count in aggregate. Flooding Telegram with every low-score job would train Gaurav to ignore the bot entirely, defeating its purpose as a trustworthy signal channel. This mirrors the general principle that a notification system's value depends on restraint, not completeness.

## Commands

- `/start` — link this Telegram chat to Gaurav's JobPilot account (one-time setup, generates/consumes a pairing token from the dashboard settings page).
- `/pending` — lists current `ready_to_apply` jobs (any tier) with inline `Apply`/`Pass` buttons — this is the queue Gaurav actually acts on day to day.
- `/today` — quick counts for today's activity.
- `/pause` — pause all notifications and discovery/pre-fill activity temporarily (e.g., during a busy week) without needing to touch the dashboard.
- `/resume` — resume normal operation.
- `/settings` — deep-links to the relevant dashboard settings page (bot itself doesn't handle complex settings editing — better suited to the dashboard UI).

## Inline Button Flow (Apply)

1. Button tap sends a callback query to the bot with `application_id`.
2. Bot calls `POST /applications/:id/apply` on `jobpilot-api` (doc 17 §3.2) — the same endpoint regardless of tier; the worker resolves the correct submission mechanism internally.
3. API triggers the apply worker to complete submission asynchronously — a direct API call for Tier A/A+ (near-instant), or a Playwright click for Tier B (per doc 06).
4. Bot edits the original message to show a "⏳ Applying..." state, then follows up with ✅ success or ❌ failure once the worker reports back (via a simple polling check or a callback webhook from the worker).

**Pass follows the same pattern**, calling `POST /applications/:id/pass` — no submission, just marks `status = 'skipped'` and removes it from the active queue.

## Reliability Notes

- Bot process (`jobpilot-bot`) runs independently of the discovery/apply workers — a slow scraping run should never make the bot unresponsive to `/pending` or button taps.
- If Telegram delivery fails (rare, network blip), the dashboard remains the source of truth — nothing is ever *only* actionable via Telegram; every action has a dashboard equivalent (per doc 09's API surface).

## Security

- Bot only responds to Gaurav's paired chat ID — reject any other chat interacting with it (single-user tool, no need for broader access control complexity).
- `Apply`/`Pass` actions validate that the `application_id` in a callback still belongs to a `ready_to_apply` job before acting, to avoid any stale-button double-submit issues if Gaurav taps an old message (this is the idempotency guard from TRD §4, enforced here at the bot's entry point too, not just the API).
