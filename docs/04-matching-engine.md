# JobPilot — Matching Engine

## Why This Module Exists

Discovery will pull far more jobs than are actually relevant — without a filter, Gaurav would drown in noise (auto-applying to irrelevant roles wastes tailored-resume generation cost and burns Tier A application quota; surfacing irrelevant Tier B/D leads wastes his review time). The matching engine is the relevance gate between discovery and everything downstream.

This directly reuses the retrieval pattern from **Retryv** (hybrid BM25 + embedding + cross-encoder rerank that took recall from 23%→84%) — same core problem (find what's actually relevant from a noisy corpus), different domain.

## Inputs

1. **Resume/skills profile** — a structured representation of Gaurav's experience: stack (Python, FastAPI, LangChain, RAG, Next.js, NestJS, PostgreSQL/pgvector, Docker, Redis), project highlights (Retryv, MemoryOS, Scoutr, ChatWidget AI), target roles (AI Engineer, Backend Engineer, Full-Stack, Mobile Dev, Software Engineer), and experience level (~2–3 years). Stored in `resume_profile` table, editable via dashboard settings — not hardcoded, since target roles/keywords may shift over time.
2. **New job posting** — from `jobs_raw`, specifically `title` + `description_text`.

## Scoring Approach

**Stage 1 — Cheap filter (keyword/metadata):**
- Reject immediately if location/remote flag doesn't match preferences (e.g., on-site-only in a country Gaurav can't relocate to, unless dashboard settings allow it).
- Reject if title contains clear non-matches (e.g., "Senior Staff" roles requiring 8+ years, or entirely unrelated fields) via a simple keyword blocklist — cheap, avoids wasting embedding calls on obvious non-matches.

**Stage 2 — Embedding similarity:**
- Embed `title + description_text` using the same embedding model as MemoryOS (Gemini embeddings) for consistency across projects.
- Compare against pre-computed embeddings of the resume profile (stored in pgvector).
- Compute cosine similarity as a baseline relevance score.

**Stage 3 — LLM rerank (for borderline scores only):**
- Jobs scoring in a middle band (not obviously a strong match, not obviously irrelevant) get a Claude API call: given the JD and the resume profile, output a relevance score (0–100) plus a short rationale.
- This mirrors Retryv's cross-encoder rerank step — cheap embedding similarity gets you most of the way, but a smarter final pass catches nuance (e.g., a "Backend Engineer" posting that's actually pure Java/Spring, which an embedding might score deceptively high on title alone but Gaurav has zero Java experience).
- Only running the LLM rerank on the middle band (not every job) keeps API cost proportional to ambiguous cases, not total volume.

## Threshold & Output

- `min_match_score` is a dashboard setting (default suggestion: 70/100), adjustable by Gaurav.
- Jobs `>= threshold` → `status = 'matched'`, proceed to tailoring (doc 05).
- Jobs `< threshold` → `status = 'discarded'`, stored (not deleted) with score + rationale, viewable in a "Discarded" filter in the dashboard in case Gaurav wants to audit/tune the threshold.

## Why Store Discarded Jobs Instead of Dropping Them

Two reasons:
1. **Threshold tuning** — if Gaurav notices good jobs being discarded, he needs to see them to recalibrate `min_match_score` or the resume profile's keyword weighting.
2. **Feedback loop (future)** — if Gaurav manually applies to something JobPilot discarded, that's a signal the matching profile is miscalibrated; a v2 feature could let him mark discarded jobs as "actually relevant" to auto-adjust scoring.

## Resume Profile Freshness

The resume profile embedding is recomputed whenever Gaurav edits it in settings (new project added, new skill, updated target roles) — not on every match run, to avoid redundant compute. A `profile_version` field on `resume_profile` lets `jobs_raw` matches reference which profile version scored them, so historical scores remain interpretable even after the profile changes.

## Edge Cases

- **Very short/sparse JDs** (common on some career pages) — low signal for embedding similarity. Flag these for the LLM rerank stage regardless of initial score, since embeddings are unreliable on thin text.
- **Multiple roles matched at the same company** — dedupe isn't needed here (different roles are different opportunities), but the dashboard should group by company for readability.
