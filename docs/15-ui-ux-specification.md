# JobPilot — UI/UX Specification

## Why This Doc Exists (separate from doc 09)

Doc 09 defines *what views exist and what data they show*. This doc defines *how they actually look, flow, and feel* — layout, interaction patterns, states, and the design system — so Antigravity has enough to build pixel-real screens without guessing, the same way Gaurav's other projects had explicit palette/spacing decisions rather than "make it look nice."

## 1. Design System

**Strict black & white theme, as specified** — not JobPilot-specific branding, not borrowed from gauravxd.dev's Rust & Linen system. Monochrome base, with status colors used only as minimal functional signals (see below), not as decorative accents:

| Token | Light | Dark |
|---|---|---|
| Background | `#FFFFFF` | `#000000` |
| Surface (cards) | `#F5F5F5` | `#161616` |
| Text primary | `#111111` | `#F5F5F5` |
| Text secondary | `#666666` | `#999999` |
| Accent | `#000000` | `#FFFFFF` |
| Border | `#E0E0E0` | `#2A2A2A` |

**Status colors (functional signal only — kept minimal since the rest of the UI is strict monochrome; used purely so the lanes and error state are distinguishable at a glance, not for decoration):**
- Applied (submitted after Gaurav's tap): green (`#2E7D46` light / `#4CAF6D` dark)
- Ready to Apply (waiting on Gaurav): amber (`#C98E17` / `#E0AC3F`)
- Manual lead: neutral grey (`#555555` / `#AAAAAA`) — stays within the monochrome family since it's the "no automation happened" state
- Discarded/skipped: muted grey, low visual weight, same as manual lead treatment
- Failed/error: red (`#C0392B` / `#E0574A`)

**Button component spec (explicit, applies everywhere — cards, dashboard, settings):**
- **Primary action button** (Apply, Recompute embeddings, etc.): black background (`#000000`), white text (`#FFFFFF`), no border.
- **Secondary action button** (Skip, Cancel, etc.): white background, black text, black 1px border.
- In dark mode, this inverts: primary = white bg/black text, secondary = black bg/white border+text — keeps the same black/white contrast logic, just flipped.
- No other button colors (no colored buttons for actions) — status colors (above) are for badges/dots only, never for buttons, to keep the interaction layer strictly monochrome.

**Typography:** system font stack or the same font already used on gauravxd.dev (Inter or similar) — no new font decision needed here.

**Spacing/density:** dashboard, not marketing site — tighter spacing than a landing page, information-dense cards, no large hero sections. This is a working tool used daily, optimized for scanning many job cards quickly.

## 2. Primary Layout (Applications Board)

```
┌─────────────────────────────────────────────────────────┐
│ JobPilot        [Search/Filter bar]      🌙  [Gaurav ▾]  │
├─────────────────────────────────────────────────────────┤
│ [Ready to Apply 12] [Applied 8] [Manual Leads 5] [Discarded]│
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Acme Inc      │  │ Beta Co      │  │ Gamma Ltd    │   │
│  │ Backend Eng   │  │ AI Engineer  │  │ Full-Stack   │   │
│  │ Match: 88     │  │ Match: 92    │  │ Match: 76    │   │
│  │ 📄 Resume     │  │ 📄 Resume    │  │ 📄 Resume    │   │
│  │ 👤 Jane Doe   │  │ — no contact │  │ 👤 Raj Kumar │   │
│  │ [Apply][Pass] │  │ [Apply][Pass]│  │ [Apply][Pass]│   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

- **Tabs, not separate pages** — lane switching is instant, no reload, since Gaurav will flip between these constantly during a review session.
- Card grid, responsive (3 columns desktop, 1 column mobile — dashboard should work on his phone too, given the Telegram-first workflow already established).
- Each card is tappable (outside the button area) → opens Job Detail Page (doc 09 §3). The `Apply`/`Pass` buttons act directly on the card without navigating away, so a review session can move through many jobs quickly.

## 3. Job Card — Component Detail

**Ready to Apply card (the primary interaction surface — every job lands here before anything is submitted, per doc 06's core design decision):**
- Header: company + role, match score badge, resume icon (tap to preview PDF inline, not download), contact chip if found (name only, tap for full detail).
- **Tier A/A+ cards:** straightforward — header info plus `Apply` / `Pass` buttons. Tapping `Apply` submits near-instantly (single API call already pre-built server-side).
- **Tier B cards:** same header, plus a **visible preview of what will be filled** — a condensed line like "Name ✓ · Email ✓ · Resume ✓ · Work auth: Yes · Notice period: Immediate" — so Gaurav knows exactly what he's about to submit before tapping.
- Two prominent buttons at card bottom either way: **`Apply`** (primary, black-fill/white-text per §1's button spec) and **`Pass`** (secondary, white-fill/black-outline) — sized for confident tapping, no accidental-tap risk from being too close together.
- Tapping `Apply` shows an inline loading state on the button itself ("Applying...") rather than a full-page spinner — keeps Gaurav in the board view, able to act on the next card immediately.

**Applied card:**
- Status dot (green) + company + role, match score badge, `applied_at` relative timestamp, resume icon, contact chip if found. No action buttons — this is history, not a queue.

**Manual Lead card:**
- Same header, plus a clear **`Open & Apply →`** external-link button (goes to `source_url`), and a secondary **`Mark as Applied`** for his own tracking once done manually.

## 4. Job Detail Page — Layout

```
┌─────────────────────────────────────────┐
│ ← Back to board                          │
│                                           │
│ Acme Inc — Backend Engineer      [88]    │
│ Remote · Posted 2 days ago · LinkedIn    │
│                                           │
│ [Tabs: Overview | Resume | Contact |     │
│         Match Details | Application Log] │
│                                           │
│ (tab content area)                       │
└─────────────────────────────────────────┘
```

- **Overview tab:** full JD text (scrollable, not truncated — Gaurav needs the real JD for interview prep later, matching his existing habit of prepping specifics before interviews).
- **Resume tab:** embedded PDF viewer of the exact tailored resume version submitted, with a version history dropdown if multiple were generated.
- **Contact tab:** full evidence trail per doc 07's schema — each field shown with its source snippet and link, not just the final name/email, so Gaurav can judge confidence himself before reaching out.
- **Match Details tab:** score breakdown (embedding score, rerank score + rationale if applicable) — supports the threshold-tuning use case from doc 04.
- **Application Log tab:** full audit trail per doc 06 — timestamps, method, raw payload snapshot (redacted per doc 13).

## 5. Settings — Interaction Pattern

Settings is a **single scrollable page with anchored sections** (not a multi-step wizard) — Resume Profile, Target Companies, Platform Toggles, Thresholds & Caps, Default Answers, Telegram Link — left sidebar nav jumps to each section. This matches how a power-user tool should behave: everything reachable, nothing gated behind steps, since Gaurav will return to tune individual settings repeatedly rather than doing a one-time setup wizard.

**Resume Profile editor specifically:** structured form (not raw JSON editing) — sections for Experience, Projects (with a repeatable bullet-list editor per project), Skills (tag input), Target Roles (multi-select). A visible **"Recompute embeddings"** button appears whenever unsaved changes exist, with a clear "last computed: [timestamp]" indicator so Gaurav always knows if matching is running on stale data.

## 6. Empty & Error States

- **Empty Ready to Apply lane:** friendly, low-emphasis message ("Nothing waiting on you right now") — not a jarring empty-state illustration; this is a good state (means Gaurav is caught up), so it shouldn't visually read as an error.
- **Source failing repeatedly:** a small persistent banner at the top of the board ("⚠ Naukri scraper hasn't succeeded in 3 runs — check Settings") rather than only a Telegram alert, so it's visible even if he missed the notification.
- **No contact found:** simply omit the contact chip/section entirely rather than showing "No contact found" as a label everywhere — reduces visual noise across dozens of cards where this is the common case (per doc 07's expected failure mode).

## 7. Mobile Considerations

Given Gaurav operates heavily via phone (Telegram-first workflow, Claude mobile app usage), the dashboard needs to be genuinely usable on mobile, not just responsive-in-theory:
- Card grid collapses to single column.
- `Apply`/`Pass` buttons remain full-width and thumb-reachable at the bottom of each card.
- Job Detail Page tabs become a horizontal scroll strip rather than wrapping.

## 8. What's Deliberately Not Built

- No onboarding flow/wizard — single user, already knows the system (he's speccing it himself).
- No notification center within the dashboard — Telegram already owns that role (doc 10); duplicating it in-app would fragment where Gaurav actually checks for updates.
- No theming beyond light/dark — no per-user custom themes, this isn't a multi-tenant product in v1 (per doc 01's non-goals).
