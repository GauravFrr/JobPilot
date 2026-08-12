import os
import sys
import json
import logging
import httpx
from typing import Dict, Any, Tuple

# Add api folder to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))
from app.config import settings

logger = logging.getLogger("workers.matching.rerank")

from workers.llm.provider import generate

async def get_llm_rerank_score(job_title: str, job_description: str, resume_profile: Dict[str, Any]) -> Tuple[float, str]:
    """
    Calls unified LLM provider to rerank a job based on the target profile.
    Returns: Tuple of (relevance_score, rationale) where relevance_score is between 0 and 100.
    """
    # Construct matching prompt
    prompt = f"""
You are an expert technical recruiter analyzing a job posting for Gaurav.
Based on his master profile (skills, projects, education), score this job posting from 0 to 100 on how relevant it is for him.

Gaurav's Master Profile:
{json.dumps(resume_profile, indent=2)}

Job Details:
Title: {job_title}
Description:
{job_description}

Instructions:
1. Provide a numerical score from 0 (completely irrelevant) to 100 (perfect match).
2. Consider actual stack alignment: Gaurav primarily works with Python (FastAPI, LangChain), TypeScript (Next.js, NestJS), pgvector/PostgreSQL, Redis. If a role is heavily centered on Java, Go, Ruby, or C++ and does not match his stack, the score should be low.
3. Consider experience level: Gaurav is an Engineer with ~2-3 years of experience.
4. Output your response strictly in the following JSON format:
{{
  "score": <integer from 0 to 100>,
  "rationale": "<brief, 2-3 sentence explanation of the score, focusing on technology fit>"
}}
"""

    logger.info(f"Invoking LLM for reranking of job: '{job_title}'...")
    try:
        response_content = await generate(prompt, "matching_rerank", "cheap")
        
        # Find and parse JSON from LLM response
        json_match = re_search_json(response_content)
        if json_match:
            parsed = json.loads(json_match)
            score = float(parsed.get("score", 0.0))
            rationale = parsed.get("rationale", "No rationale provided.")
            logger.info(f"LLM Rerank complete. Score: {score}, Rationale: {rationale}")
            return score, rationale
        else:
            logger.error(f"Failed to find JSON in LLM response: {response_content}")
            return 0.0, "Failed to parse structured response from LLM."
            
    except Exception as e:
        logger.error(f"Error during LLM rerank call: {str(e)}")
        return 0.0, f"Error calling rerank model: {str(e)}"

def re_search_json(text: str) -> str:
    import re
    # Look for anything between { and }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else ""
