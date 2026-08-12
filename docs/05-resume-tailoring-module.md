# JobPilot — Resume Tailoring Module

## Why This Module Exists

A generic resume underperforms a tailored one — recruiters and ATS keyword filters both respond to JD-specific language. Doing this manually per application is the single biggest time cost in job hunting, and it's the reason application volume stays low. Automating this step is the highest-leverage part of the whole system.

## Input

- `resume_profile` — Gaurav's master data: work history, projects (Retryv, MemoryOS, Scoutr, ChatWidget AI, etc.) each with a bank of pre-written bullet variants where possible, skills list, education (BCA starting Oct 2026), certifications, contact info.
- The matched job's `title` + `description_text` (from doc 04's output).

## Tailoring Logic

1. **Keyword extraction from JD** — Claude API call extracts the JD's key required skills, tools, and responsibilities as a structured list.
2. **Bullet selection & rewriting** — for each relevant project/experience in the resume profile, Claude rewrites 2–4 bullets to:
   - Mirror JD keywords/terminology where truthfully applicable (never fabricate skills or experience not present in the profile — this is a hard constraint, not a style preference).
   - Follow Gaurav's existing **Jake Ryan / Google XYZ format** ("Accomplished X, measured by Y, by doing Z") already used in his resume overhaul.
   - Prioritize the most JD-relevant projects first (e.g., a RAG-heavy JD surfaces Retryv bullets first; a full-stack JD surfaces ChatWidget AI/MemoryOS front-end work first).
3. **Section reordering** — if the JD is backend-heavy vs. full-stack vs. AI-specific, reorder resume sections/skills list to lead with the most relevant category.
4. **Truthfulness constraint (hard rule, not adjustable per-job):** the tailoring prompt explicitly instructs the model to only rephrase/reprioritize real experience — never invent metrics, tools, or claims not present in the master profile. This matters both ethically and practically: a fabricated claim that comes up in an interview costs far more than a slightly-less-optimized bullet.
5. **Render to PDF** — WeasyPrint renders the tailored content into Gaurav's existing resume template/design (same visual identity across versions, only content changes).

## Output & Versioning

- Each tailored resume is stored as a `resume_versions` row: `id, job_id, generated_at, content_json (structured bullets used), pdf_path, model_used`.
- PDFs stored on the VPS filesystem (or object storage if volume grows), linked from the job/application record so Gaurav can always see exactly what was submitted for any given application — critical for interview prep (matches his existing habit of prepping specifics like the Retryv recall numbers before interviews).

## Quality Control

- **Preview before auto-submit is not required for Tier A** (speed is the point), but every generated resume is logged and viewable after the fact — if Gaurav spots a bad tailoring output, he can flag it and the master profile / prompt gets refined.
- **For Tier B (human-confirm lane)**, the tailored resume PDF is shown alongside the pending application in the dashboard/Telegram, so Gaurav reviews it as part of the confirm step — this is a natural checkpoint, not an extra chore, since he's already confirming the application itself.

## Cost Management

- Use a cheaper/faster Claude tier for keyword extraction (Stage 1) where output is short and structured; reserve a stronger model for the actual bullet-rewriting step where quality matters most for output the reader will actually judge.
- Cache keyword-extraction results per unique JD text hash — if the same JD text appears from multiple sources (common with cross-posted listings), skip redundant extraction calls.

## Why Not Just Use One Generic "AI-optimized" Resume

A single AI-optimized resume is a modest improvement over a static one, but it can't lead with Retryv for a RAG-heavy role and ChatWidget AI for a full-stack SaaS role simultaneously — per-JD tailoring is what makes the ATS keyword match and the human skim-read both land well, and that's only possible by regenerating per application.
