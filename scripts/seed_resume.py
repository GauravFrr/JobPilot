import os
import sys
import json
import asyncio
import logging
from sqlalchemy import select

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_resume")

# Add the api directory to the Python path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.config import settings
from app.db import AsyncSessionLocal
from app.models.resumes import ResumeProfile

# Import Gemini SDK
from google import genai

def get_resume_text_representation(profile: dict) -> str:
    """Constructs a clean text representation of the resume for embedding."""
    parts = []
    parts.append(f"Name: {profile.get('name', '')}")
    parts.append(f"Target Roles: {', '.join(profile.get('target_roles', []))}")
    
    skills = profile.get('skills', {})
    skills_str = "\n".join(f"- {category}: {', '.join(items)}" for category, items in skills.items())
    parts.append(f"Skills:\n{skills_str}")
    
    experience = profile.get('experience', [])
    exp_str = "\n\n".join(
        f"Role: {e.get('role')}\nCompany: {e.get('company')}\nDate: {e.get('date')}\nLocation: {e.get('location')}\nBullets:\n" + 
        "\n".join(f"- {b}" for b in e.get('bullets', []))
        for e in experience
    )
    parts.append(f"Experience:\n{exp_str}")
    
    projects = profile.get('projects', [])
    projects_str = "\n\n".join(
        f"Project: {p.get('name')}\nSummary: {p.get('summary', p.get('bullets', [''])[0])}\nBullets:\n" + 
        "\n".join(f"- {b}" for b in p.get('bullets', []))
        for p in projects
    )
    parts.append(f"Projects:\n{projects_str}")
    
    add_projects = profile.get('additional_projects', [])
    add_proj_str = "\n".join(f"- {p.get('name')} ({p.get('tech')}): {p.get('summary')}" for p in add_projects)
    parts.append(f"Additional Projects:\n{add_proj_str}")
    
    education = profile.get('education', [])
    edu_str = "\n".join(f"- {e.get('degree')} at {e.get('institution')} ({e.get('start')}, {e.get('status')})" for e in education)
    parts.append(f"Education:\n{edu_str}")
    
    certs = profile.get('certifications', [])
    certs_str = "\n".join(f"- {c}" for c in certs)
    parts.append(f"Certifications:\n{certs_str}")
    
    return "\n\n".join(parts)

async def generate_embedding(text: str) -> list[float]:
    """Generates a 768-dimensional embedding using Gemini's gemini-embedding-2."""
    api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment or settings.")
    
    # Initialize modern genai client
    client = genai.Client(api_key=api_key)
    
    logger.info("Calling Gemini API to generate embedding...")
    response = client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config={"output_dimensionality": 768}
    )
    
    if not response.embeddings or not response.embeddings[0].values:
        raise ValueError("Could not extract embedding from Gemini API response.")
    
    embedding = response.embeddings[0].values
    logger.info(f"Successfully generated embedding (dimensions: {len(embedding)})")
    return embedding

async def main():
    json_path = os.path.join(os.path.dirname(__file__), "resume_profile.json")
    if not os.path.exists(json_path):
        logger.error(f"Could not find resume profile JSON at {json_path}")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
        
    # Check for placeholder strings before seeding
    placeholders = ["REPLACE_WITH_YOUR_EMAIL", "REPLACE_WITH_YOUR_PHONE", "REPLACE_WITH_YOUR_LINKEDIN_URL"]
    for ph in placeholders:
        if ph in json.dumps(profile_data):
            logger.warning(f"Placeholder '{ph}' detected in resume_profile.json. Please update the file with your real details if this is a production run.")
            
    # Generate text representation and get embedding
    resume_text = get_resume_text_representation(profile_data)
    try:
        embedding = await generate_embedding(resume_text)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {str(e)}")
        sys.exit(1)
        
    # Connect to DB and insert/update
    async with AsyncSessionLocal() as session:
        try:
            # Check if there's already an active profile
            stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
            result = await session.execute(stmt)
            existing_profile = result.scalars().first()
            
            if existing_profile:
                logger.info(f"Deactivating existing profile version {existing_profile.version}")
                existing_profile.is_active = False
                session.add(existing_profile)
                new_version = existing_profile.version + 1
            else:
                new_version = 1
                
            new_profile = ResumeProfile(
                version=new_version,
                content_json=profile_data,
                embedding=embedding,
                is_active=True
            )
            session.add(new_profile)
            await session.commit()
            logger.info(f"Successfully seeded resume profile version {new_version} into the database.")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error during seeding: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
