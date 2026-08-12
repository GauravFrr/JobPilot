import os
import sys
import asyncio
import json
import logging
from sqlalchemy import select

# Add the api directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.db import AsyncSessionLocal
from app.models.resumes import ResumeProfile

async def verify():
    print("--- Phase 0 Exit Check Verification ---")
    async with AsyncSessionLocal() as session:
        # 1. Fetch active profiles
        stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
        result = await session.execute(stmt)
        active_profiles = result.scalars().all()
        
        print(f"1. Active rows in resume_profile table: {len(active_profiles)}")
        if len(active_profiles) != 1:
            print("ERROR: Expected exactly 1 active profile!")
            sys.exit(1)
            
        profile = active_profiles[0]
        
        # 2. Check embedding
        embedding = profile.embedding
        if embedding is None:
            print("ERROR: Embedding column is NULL!")
            sys.exit(1)
            
        print(f"2. Embedding type: {type(embedding)}")
        print(f"   Embedding dimension: {len(embedding)}")
        
        # Check first 5 dimensions to verify it is a real float vector
        sample = list(embedding[:5])
        is_all_zeros = all(v == 0.0 for v in embedding)
        print(f"   Sample values (first 5): {sample}")
        print(f"   Is it a zero vector? {is_all_zeros}")
        if is_all_zeros:
            print("ERROR: Embedding is a zero vector!")
            sys.exit(1)
            
        # 3. Print content_json details
        print("3. Stored content_json details:")
        print(json.dumps(profile.content_json, indent=2))
        
        # Final confirmation
        if len(embedding) == 768 and not is_all_zeros and len(active_profiles) == 1:
            print("\n>>> Phase 0 Exit Check: SUCCESS <<<")
        else:
            print("\n>>> Phase 0 Exit Check: FAILED <<<")

if __name__ == "__main__":
    asyncio.run(verify())
