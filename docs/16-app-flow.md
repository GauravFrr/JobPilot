# JobPilot — App Flow (User Journeys)

## Why This Doc Exists

Doc 02 shows how *data* moves through the system. Doc 15 shows what each *screen* looks like. Neither shows what **Gaurav actually does, in order, across a session** — the real journeys a person takes through the app. This doc fills that gap so Antigravity can wire screens/notifications together in the right sequence, not just build each piece in isolation.

## Flow 1 — First-Time Setup (one-time, before anything else works)

```
1. Deploy JobPilot (Docker Compose on Webdock VPS)
2. Open dashboard → Settings → Resume Profile
3. Fill in: experience, projects (Retryv, MemoryOS, Scoutr, ChatWidget AI...),
   skills, target roles, default answers (work auth, notice period, etc.)
4. Click "Recompute embeddings" → resume_profile.embedding populated
5. Settings → Target Companies → seed list (import from existing
   LinkedIn outreach tracker or add manually)
6. Settings → Platform Toggles → enable Tier A sources first
   (leave Tier B/C off until Phase 6/7 per roadmap)
7. Settings → Thresholds & Caps → set min_match_score, daily caps
8. Settings → Telegram Link → /start in bot, paste pairing code
   from dashboard → chat_id linked
9. Done — scheduler begins running on next cycle, no further action needed
```

**Key point:** this is the only flow that's a "wizard-like" sequence. Everything after this is event-driven, not step-driven — matches doc 15 §5's decision not to build a recurring onboarding flow.

## Flow 2 — Discovery to Ready-to-Apply (Tier A/A+, fast path to a tap)

```
Scheduler triggers Tier A / Tier A+ discovery
        │
        ▼
New job found → jobs_raw (status: discovered)
        │
        ▼
Matcher scores it
        │
   ┌────┴────┐
score < threshold   score >= threshold
   │                    │
   ▼                    ▼
status: discarded   Tailoring worker generates resume
(visible in                  │
Discarded tab,               ▼
no notification)     Apply worker pre-builds the application
                      payload (does NOT submit)
                              │
                              ▼
                      status: ready_to_apply
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
          Contact-finder runs   Telegram notification sent
          (parallel, non-blocking)   "🟢 Ready to Apply: Backend Eng @ Acme
                                       [Apply] [Pass]"
                    │
                    ▼
          If found → attached to job,
          included in the notification or
          a follow-up message if it landed late
```

**Gaurav's involvement:** one tap. Per doc 06's core design decision, nothing submits itself — but because the payload is already fully built by the time the notification lands, tapping `Apply` results in near-instant submission. This is still the "fast path": minimal review overhead, maximum speed once he decides.

## Flow 3 — Discovery to Ready-to-Apply (Tier B, review-then-tap)

```
Scheduler triggers Tier B discovery (scrape)
        │
        ▼
New job found → matched → tailored (same as Flow 2 up to here)
        │
        ▼
Form-fill worker fills the application (does NOT submit)
        │
        ▼
status: ready_to_apply
        │
        ▼
Telegram message sent:
"🟢 Ready to Apply: AI Engineer @ Beta Co — Match 91
 Form preview: Name ✓ · Email ✓ · Resume ✓
 [Apply] [Pass] [View in Dashboard]"
        │
   ┌────┴────┬──────────────┐
   ▼          ▼               ▼
Gaurav taps  Gaurav taps    Gaurav ignores it,
Apply        Pass           opens dashboard later
   │          │               │
   ▼          ▼               ▼
Apply worker  status:        Sees it in Ready to Apply
completes     skipped        tab, taps Apply/Pass there —
submission                   same result either interface
(Playwright
clicks submit)
   │
   ▼
status: applied
   │
   ▼
Telegram follow-up: "✅ Applied"
```

**Key point:** Telegram and Dashboard are interchangeable entry points into the same action — this is called out explicitly in doc 09 and doc 10, and this flow shows why: Gaurav might be on his phone when the notification lands, or reviewing the board later; either path reaches the same `apply` endpoint. The only real difference from Flow 2 is that Tier B cards show a filled-form preview first (since there's an actual form behind it, not just an API payload) — the tap itself behaves identically.

## Flow 4 — Manual Lead Follow-Through (Tier D / complex Tier C)

```
Job discovered → matched → tailored
        │
        ▼
Application router determines: no safe automation path
        │
        ▼
status: manual_lead (no form-fill attempted)
        │
        ▼
Appears in dashboard's Manual Leads lane with:
  tailored resume (already generated) + direct apply link + contact if found
        │
        ▼
Gaurav opens the link, applies manually on his own time
        │
        ▼
Gaurav taps "Mark as Applied" in dashboard (self-tracking only,
no system action tied to this — just keeps his records complete)
```

## Flow 5 — Discovering & Acting on a Contact

```
Contact-finder resolves a contact for a job (any tier, any lane)
        │
        ▼
contacts row created, evidence attached
        │
        ▼
Job card (any lane) now shows a contact chip
        │
        ▼
Gaurav taps "Message Contact" (dashboard) or "Draft Message" (Telegram)
        │
        ▼
Outreach module generates draft (Claude API call)
        │
        ▼
Draft shown to Gaurav — editable, NOT sent automatically
        │
        ▼
Gaurav copies draft → sends manually via LinkedIn/email
        │
        ▼
Gaurav optionally marks "sent" in dashboard (outreach_drafts.sent = true)
        │
        ▼
Feeds Weekly Summary stats (Flow 6)
```

## Flow 6 — Weekly Review

```
Sunday evening (scheduled)
        │
        ▼
Weekly summary job runs: aggregates counts across the week
        │
        ▼
Telegram digest sent:
"📊 This week: 34 discovered, 11 matched, 8 applied (via one-tap),
 5 ready to apply, 3 skipped, 6 contacts found, 4 outreach drafts"
        │
        ▼
Gaurav optionally opens dashboard's Weekly Summary view for detail
        │
        ▼
If application volume/quality looks off → adjusts Settings
(min_match_score, resume profile, target companies) → next week's
run reflects the change
```

This is the system's only built-in feedback loop in v1 (per doc 04 and doc 14's "explicitly deferred" auto-tuning note) — tuning is manual and deliberate, not automatic.

## Flow 7 — Source Failure & Recovery

```
Tier B scraper hits a block page / CAPTCHA on a run
        │
        ▼
Hard stop (no retry) — per doc 06's hard-stop rule
        │
        ▼
source_health.consecutive_failures += 1
        │
   ┌────┴────┐
< 3 failures   >= 3 failures
   │               │
   ▼               ▼
Silent, retried  Telegram alert sent + dashboard banner
next cycle       "⚠ LinkedIn scraper failing — check Settings"
                       │
                       ▼
              Gaurav investigates (site change? credentials
              expired? platform actively blocking?)
                       │
                       ▼
              Fixes root cause or disables that source
              in Platform Toggles until fixed
```

## Cross-Flow Principle

Every flow above terminates in one of three states from Gaurav's point of view: **(1) it's waiting on his `Apply`/`Pass` tap**, **(2) it's already applied because he tapped `Apply`**, or **(3) it needs his manual action outside the system**. No flow should ever leave him unsure which of these three states a given job is in — this is the single UX invariant every other doc's design decisions trace back to.
