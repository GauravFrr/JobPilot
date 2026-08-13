# AGENT.md — Instructions for Antigravity (JobPilot)

> [!IMPORTANT]
> **MANDATORY CONTEXT READ FIRST**: Every time the user assigns a task, before making any changes, running any terminal commands, or generating code, the agent MUST first read all relevant design documents, modules specs, plans, and instructions in the `docs/` folder and this `AGENT.md` file. Always cross-reference instructions, variables, paths, and behavioral rules with the original docs rather than proceeding from memory or making assumptions.

This file is the operating manual for whichever agent (Antigravity) is doing the actual build work on JobPilot. Read this before touching code, and re-check it whenever a task feels ambiguous.

## 1. Doc Suite — Read Order & Authority

Full spec lives in `/jobpilot-docs/`, 22 files, numbered. Authority order when docs seem to conflict: **00-PRD/00-TRD (requirements) → numbered module docs (03–13, 15–17, 19) → 14/18 (roadmap/plan)**. If the roadmap says to do something the module doc doesn't support, the module doc wins — the roadmap is sequencing, not a spec override.

Before starting *any* task:
1. Check `18-implementation-plan.md` for the current phase's task list.
2. Read the specific module doc(s) that task references — don't build from memory of a summary, the module doc has the actual behavioral rules and the *why* behind them.
3. Check `00-TRD.md` §6 (Security Requirements) and §11 (Compliance Checklist) if the task touches any external platform automation — these are binding, not suggestions.
4. Check `19-coding-rules-and-project-structure.md` for style and file-placement — every task, no exceptions, since this governs how *all* code gets written, not just specific modules.

## 2. Non-Negotiable Rules (violating these is a stop-and-flag situation, not a judgment call)

- **Never call a platform's private/internal/reverse-engineered API**, even using the user's own authenticated session, at any tier, for any reason. Public APIs and rendering-what-a-logged-out-user-sees are fine. Session-hijacking a platform's internal systems is not, regardless of how the task is framed. (Full reasoning: `13-security-and-compliance.md`.)
- **Nothing submits anywhere without Gaurav's explicit `Apply` tap — this applies to every tier, not just Tier B/C.** Tier A/A+ pre-builds the payload and waits for a tap just like Tier B pre-fills a form and waits for a tap. No "just this once" exceptions, no confidence-based auto-submit override, ever (doc 06's core design decision).
- **Outreach messages are never sent programmatically.** Draft only. The send action is always a separate, explicit human step outside this codebase.
- **CAPTCHA/bot-challenge = immediate hard stop**, not a retry-with-backoff case. Log, alert, move on.
- **Resume tailoring never fabricates.** Every generated bullet must trace back to something actually present in `resume_profile`. If the JD calls for a skill genuinely not in the profile, don't invent it — leave it out.
- **Every contact field shown to the user must have a traceable evidence entry.** If you can't cite where a name/email/title came from, don't surface it.

If a task as described would require breaking one of the above, stop and flag it rather than finding a workaround — these aren't style preferences, they're the reason this project is safe to run unattended.

## 3. Workflow: Plan Review & Approval Gating

Gaurav's established pattern (used across his other projects) is: **Antigravity proposes a plan for a build phase, Claude reviews it, Gaurav approves, then Antigravity builds.** Follow this loop for every phase in `18-implementation-plan.md`:

1. Before writing code for a new phase (or a substantial task within one), write out a short plan: what you're building, which doc(s) it implements, what the exit check will be.
2. Surface that plan for review before proceeding — don't silently start a multi-file build on an unreviewed plan, especially for anything touching Tier B/C automation or the database schema.
3. Once approved, build. If you hit a design decision not covered by the docs, make a reasonable call, note the assumption clearly in your output, and keep moving — don't block on every small ambiguity (matches the general "sensible default + note the assumption" approach used throughout this project's own docs).
4. At the end of a phase, check it against that phase's exit check in `18-implementation-plan.md` before considering it done.

## 4. Code Conventions

- **Read `19-coding-rules-and-project-structure.md` before writing any code — this is not optional.** It defines the style bar (write like a human developer, not like AI showing off — no unnecessary abstractions, no over-engineering, plain clear naming) and the exact folder/file structure to follow. Every file you create should match that structure; don't invent a different layout.
- **Backend:** Python 3.11+, FastAPI, async where the workload is I/O-bound (API calls, scraping, DB queries) — matches Gaurav's existing FastAPI/RAG codebase conventions (Retryv).
- **Frontend:** Next.js 15, TypeScript, Tailwind for styling — apply the design tokens from `15-ui-ux-specification.md` §1 rather than inventing new colors/spacing ad hoc.
- **Bot:** aiogram 3, async SQLAlchemy — reuse patterns from the existing Anti-Forward Telegram bot rather than a fresh architecture.
- **DB:** all schema changes go through migrations, never manual ALTER statements against the running DB. Schema itself is defined in `11-database-schema.md` / `17-backend-schema.md` — don't add tables/columns not reflected there without updating the doc first.
- **Secrets:** never hardcode API keys, DB credentials, or platform passwords in source. `.env` per service, and Tier B platform credentials specifically must be encrypted at rest (TRD REQ-SEC-2) — flag if you're unsure how to implement this correctly rather than shipping a plaintext stopgap.
- **Commits/PRs:** reference which doc + which phase/task number (per `18-implementation-plan.md`) a change implements, so the history stays traceable back to the spec.

## 5. Cost Discipline (LLM calls)

Per `05-resume-tailoring-module.md` and `07-contact-finder-module.md`: use a cheaper/faster model for short structured-extraction tasks (JD keyword extraction, contact-evidence extraction), reserve stronger models for user-facing generation quality (resume bullet rewriting, outreach drafts). Don't default every call to the most expensive model available — this is a stated requirement (TRD REQ-OBS-2 expects this to be monitorable), not just a cost nicety.

## 6. When Something Isn't Covered by the Docs

The doc suite is thorough but not exhaustive — implementation will surface real decisions (exact Playwright selectors, specific prompt wording, precise retry timing) that the docs deliberately leave open (see `17-backend-schema.md` §6, "What This Doc Does Not Cover"). For these:
- Make the call that best serves the *principles* in section 2 above, even if the exact mechanism isn't spelled out.
- Prefer the more conservative option when automation risk is ambiguous (e.g., when in doubt about whether a scraping pattern looks bot-like, slow it down further rather than optimizing for speed).
- Note the decision in your plan/PR so Gaurav or Claude can review it, not just silently.

## 7. Testing Before Marking a Phase Done

Check `00-TRD.md` §10 (Testing Requirements) and the specific phase's exit check in `18-implementation-plan.md`. Do not mark a phase complete on "the code runs without errors" alone — the exit checks are about correctness against real data (e.g., Phase 1 requires a real job to make it through the full pipeline with a non-fabricated resume, not just a passing unit test).

## 8. Golden Rule

If you're ever choosing between "ship this faster" and "keep Gaurav's real accounts and this system's trustworthiness intact," the second one wins every time. The entire architecture (tiering, human-confirm gates, hard stops, audit logging) exists to make that choice automatic rather than something that has to be re-litigated per task.
