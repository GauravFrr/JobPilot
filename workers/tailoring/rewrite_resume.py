import os
import sys
import json
import logging
import httpx
from typing import Dict, Any, List

# Add api folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))
from app.config import settings

logger = logging.getLogger("workers.tailoring.rewrite_resume")

from workers.llm.provider import generate

async def generate_tailored_resume_json(
    job_title: str,
    job_description: str,
    keywords: List[str],
    resume_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calls unified LLM provider to rewrite resume bullets and reorder sections/skills based on the JD.
    Strictly enforces no-fabrication constraints.
    """
    prompt = f"""
You are a career development expert and professional resume writer.
Tailor the candidate's master resume profile to match the target job description while strictly adhering to the truthfulness constraint.

TRUTH AND NO-FABRICATION CONSTRAINT (CRITICAL RULE):
- You may only rephrase, restructure, and re-prioritize the experience, achievements, metrics, and technologies that are ALREADY present in the candidate's profile.
- NEVER fabricate metrics, numbers, technologies, projects, or job experience.
- If the job description requires a technology (e.g. Java, AWS, Kubernetes) that is NOT present in the candidate's profile, DO NOT ADD IT to the tailored resume. Leave it out.
- Every rewritten bullet point must be factually grounded in the original bullets of the same project.

Resume Overhaul Format & Phrasing:
- Rewrite the bullet points using the Google XYZ structure (accomplishment, measurable outcome, method), but write them in a varied, natural, and professional resume tone.
- CRITICAL: DO NOT start every bullet with "Accomplished" or use the literal phrases "measured by" or "by doing" in every bullet. Vary the sentence structure and starting action verbs naturally.
- Keep the number of bullets per project to 2-3.

Few-shot examples of correct, naturally-phrased XYZ bullets (observe how they do NOT repeat the same opening words):
* "Reduced database query latency by 45% (from 180ms to 99ms) by implementing HNSW index structures and optimizing PostgreSQL query plans."
* "Shipped 5 production Telegram bots for international clients, achieving a 100% gateway integration success rate through event-driven Python backends."
* "Eliminated repetitive customer support work for 3+ clients, yielding a 35% ticket deflection rate by building an automated RAG document Q&A chatbot."

Master Resume Profile:
{json.dumps(resume_profile, indent=2)}

Target Job:
Title: {job_title}
Description:
{job_description}

Extracted Keywords:
{json.dumps(keywords, indent=2)}

Instructions:
1. Keep the projects and experience entries in their exact original order as in the Master Resume Profile. Do NOT reorder them.
2. For each project, rewrite its bullet points to align with the keywords and responsibilities in the JD where truthfully possible.
3. For each experience entry, rewrite its bullet points to align with the keywords and responsibilities in the JD where truthfully possible. Keep the role, company, date, location, and summary unchanged.
4. Reorder the skills list categories and items within them to lead with the technologies most relevant to the JD.
5. Maintain all contact info, education, and certifications exactly as is.
6. Return the response strictly as a JSON object matching this structure:
{{
  "name": "...",
  "email": "...",
  "phone": "...",
  "linkedin": "...",
  "github": "...",
  "website": "...",
  "skills": {{
    "languages": [...],
    "frameworks": [...],
    "databases": [...],
    "tools": [...],
    "concepts": [...]
  }},
  "education": [
    {{ "degree": "...", "institution": "...", "start": "...", "status": "..." }}
  ],
  "certifications": [...],
  "experience": [
    {{
      "role": "...",
      "company": "...",
      "date": "...",
      "location": "...",
      "summary": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "projects": [
    {{
      "name": "...",
      "summary": "...",
      "bullets": ["...", "..."]
    }}
  ]
}}
No other text, preamble, or formatting.
"""

    logger.info(f"Generating tailored resume bullets using LLM...")
    try:
        response_content = await generate(prompt, "tailor_resume", "premium")
        
        # Find and parse JSON
        import re
        json_match = re.search(r"\{.*\}", response_content, re.DOTALL)
        if json_match:
            tailored_profile = json.loads(json_match.group(0))
            
            # 1. Merge and re-order experience entries to match the original order exactly
            orig_exp_list = resume_profile.get("experience", [])
            tailored_exp_map = {e["company"].lower(): e for e in tailored_profile.get("experience", [])}
            ordered_experience = []
            for orig in orig_exp_list:
                company_lower = orig["company"].lower()
                tailored_entry = tailored_exp_map.get(company_lower)
                if tailored_entry:
                    entry = {
                        "role": orig.get("role", ""),
                        "company": orig.get("company", ""),
                        "date": orig.get("date", ""),
                        "location": orig.get("location", ""),
                        "summary": orig.get("summary", ""),
                        "bullets": tailored_entry.get("bullets", orig.get("bullets", []))
                    }
                    ordered_experience.append(entry)
                else:
                    ordered_experience.append(orig)
            tailored_profile["experience"] = ordered_experience
            
            # 2. Merge and re-order projects to match the original order exactly
            orig_proj_list = resume_profile.get("projects", [])
            tailored_proj_map = {p["name"].lower(): p for p in tailored_profile.get("projects", [])}
            ordered_projects = []
            for orig in orig_proj_list:
                name_lower = orig["name"].lower()
                tailored_entry = tailored_proj_map.get(name_lower)
                if tailored_entry:
                    entry = {
                        "name": orig.get("name", ""),
                        "tech": orig.get("tech", ""),
                        "date": orig.get("date", ""),
                        "repo": orig.get("repo", ""),
                        "bullets": tailored_entry.get("bullets", orig.get("bullets", []))
                    }
                    ordered_projects.append(entry)
                else:
                    ordered_projects.append(orig)
            tailored_profile["projects"] = ordered_projects
            
            # 3. Copy additional projects directly from the master profile
            tailored_profile["additional_projects"] = resume_profile.get("additional_projects", [])
            
            logger.info("Successfully generated, ordered, and merged tailored resume profile JSON.")
            return tailored_profile
            
        logger.error(f"Could not parse JSON from LLM response: {response_content}")
        return resume_profile
        
    except Exception as e:
        logger.error(f"Error calling LLM resume tailoring: {str(e)}")
        return resume_profile
