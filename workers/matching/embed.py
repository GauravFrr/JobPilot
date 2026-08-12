import os
import sys
import logging
from typing import List

# Add api folder to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))
from app.config import settings

from google import genai

logger = logging.getLogger("workers.matching.embed")

async def get_job_description_embedding(title: str, description_text: str) -> List[float]:
    """
    Generates a 768-dimensional embedding using Gemini's gemini-embedding-2
    for the text representation of the job (title + description_text).
    """
    api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
        
    client = genai.Client(api_key=api_key)
    
    # Construct search text representation of job
    search_text = f"Title: {title}\nDescription:\n{description_text}"
    
    logger.info(f"Generating embedding for job title: '{title}'...")
    response = client.models.embed_content(
        model="gemini-embedding-2",
        contents=search_text,
        config={"output_dimensionality": 768}
    )
    
    if not response.embeddings or not response.embeddings[0].values:
        raise ValueError("Failed to extract embedding from Gemini API.")
        
    embedding = response.embeddings[0].values
    logger.info(f"Embedding generated successfully (dimension: {len(embedding)})")
    return embedding
