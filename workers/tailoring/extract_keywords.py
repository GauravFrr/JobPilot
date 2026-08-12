import os
import sys
import json
import logging
import httpx
from typing import List

# Add api folder to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))
from app.config import settings

logger = logging.getLogger("workers.tailoring.extract_keywords")

from workers.llm.provider import generate

async def extract_keywords_from_jd(job_title: str, job_description: str) -> List[str]:
    """
    Calls unified LLM provider to extract key required skills, tools, and responsibilities as a structured list.
    Uses the cheaper/faster model for structured extraction.
    """
    prompt = f"""
Analyze this job description and extract a list of the key required skills, programming languages, frameworks, databases, tools, and methodologies.

Job Title: {job_title}
Job Description:
{job_description}

Instructions:
1. Extract only specific, concrete technical terms (e.g. "FastAPI", "React", "Docker", "RAG", "CI/CD"). Avoid generic terms like "communication", "team player", "problem solver".
2. Output your response strictly as a JSON array of strings, like this:
[
  "keyword1",
  "keyword2"
]
No other text, explanations, or formatting.
"""

    logger.info(f"Extracting keywords from JD for '{job_title}' using LLM...")
    try:
        response_content = await generate(prompt, "extract_keywords", "cheap")
        
        # Find and parse JSON array
        import re
        array_match = re.search(r"\[.*\]", response_content, re.DOTALL)
        if array_match:
            keywords = json.loads(array_match.group(0))
            if isinstance(keywords, list):
                logger.info(f"Successfully extracted {len(keywords)} keywords: {keywords}")
                return [str(k).strip() for k in keywords]
        
        logger.error(f"Could not parse JSON array from LLM response: {response_content}")
        return []
        
    except Exception as e:
        logger.error(f"Error calling LLM keyword extraction: {str(e)}")
        return []
