# JobPilot — Project Overview & Vision

> Working name: **JobPilot**. Rename freely — this doc suite treats it as a placeholder.

## 1. Problem Statement

Gaurav is actively job hunting for remote AI Engineer / Backend / Full-Stack / Mobile roles while also managing freelance work and internship deadlines. The current process is manual and fragmented:

- Relevant jobs are scattered across 10+ platforms (Wellfound, RemoteOK, Naukri, LinkedIn, Instahyre, company career pages) with no single view.
- Every application needs a resume tailored to that specific JD — done by hand each time, which is slow and inconsistent.
- Applying is repetitive manual form-filling across platforms with different UIs.
- There's no way to know who's actually behind a job post, so outreach (which increases response rate significantly) rarely happens.
- No system tracks what was applied to, with what resume version, and what happened next.

**Core insight:** this is the same shape of problem as Retryv (retrieval + relevance) and MemoryOS (structured personal data layer) combined with an automation/orchestration layer. Gaurav already owns every sub-skill needed to build this.

## 2. Why Build This (Not Just Use Existing Tools)

Existing tools solve pieces, not the whole flow:

| Tool | What it does | What it's missing |
|---|---|---|
| Teal / Simplify | Resume tailoring, tracking | No auto-apply, no contact-finding, not tuned to Gaurav's specific stack/keywords |
| LazyApply / Jobright | Auto-apply bots | Blunt-force, high ban risk, no human-in-loop safety net, no contact discovery |
| Hunter.io / RocketReach | Contact-finding | Standalone, not wired into an application pipeline |
| Manual process (current) | Full control | Doesn't scale past ~5 quality applications/day, error-prone, no learning loop |

JobPilot's differentiation: **tiered automation that respects platform risk**, a **resume-tailoring engine that reuses Gaurav's actual RAG stack**, and a **contact-finder that stays within public-data methods** (explicitly avoiding session-hijacking / reverse-engineered private API approaches — see `13-security-compliance.md` for the reasoning behind this boundary).

## 3. Goals (in priority order)

1. **Increase quality applications per week** without increasing manual hours spent per application.
2. **Never get Gaurav's real accounts (LinkedIn, Naukri) banned** — automation risk must be tier-gated, never blanket.
3. **Every application uses a resume tailored to that specific JD**, not a generic one.
4. **Surface a human contact for as many applications as possible**, with evidence, so outreach becomes a one-tap action instead of a research task.
5. **Full visibility** — nothing gets auto-submitted into a black hole; everything is logged, versioned, and viewable.

## 4. Non-Goals (explicitly out of scope for v1)

- No fully unattended apply-to-everything mode for platforms that ban bots (LinkedIn, Naukri, Wellfound, Instahyre) — these always route through the human-confirm lane.
- No session-hijacking, cookie-theft, or reverse-engineered private API usage against any platform — explicitly rejected as a method, regardless of coverage gain (see doc 13).
- No auto-sending of outreach messages to discovered contacts — drafts only, human sends.
- Not being built as a commercial SaaS in v1 — this is a personal tool first. SaaS-ification is a possible v2 decision after it proves itself on Gaurav's own job search.

## 5. Success Criteria

- System discovers and scores jobs from all configured sources on a running schedule without manual triggering.
- Tier A applications are pre-built (payload ready, resume tailored, waiting on a tap) within minutes of discovery; tapping `Apply` submits them near-instantly, logged with full audit trail.
- Tier B applications are pre-filled and waiting in a queue; a single tap in the web dashboard or Telegram bot submits them.
- At least 40–50% of applications have a discovered contact (name + one of: LinkedIn / email) with visible evidence.
- Zero platform bans across the life of the tool.
- Gaurav can see, at a glance, in Telegram: what's ready for a tap, what he's already applied to, and who to message next.

## 6. Relationship to Gaurav's Existing Stack

This project deliberately reuses infrastructure already proven in other projects rather than reinventing it:

- **Matching/relevance** → same embedding + rerank pattern as Retryv (pgvector, hybrid scoring).
- **Personal data layer** (resume profile, skills, preferences) → same shape as MemoryOS's structured memory layer.
- **Telegram bot** → same aiogram + async SQLAlchemy pattern as the Anti-Forward bot already built and deployed.
- **PDF generation** → same WeasyPrint approach as Brefly's report generation.
- **Deployment** → Webdock VPS, Docker Compose, same as everything else — no new infra pattern introduced.

This keeps the build fast: most of it is composition of known-good patterns, not new R&D.
