import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from workers.discovery.tier_a_apis import fetch_remoteok_jobs
from scripts.test_live_pipeline import is_relevant

async def run():
    jobs = await fetch_remoteok_jobs()
    relevant = [j for j in jobs if is_relevant(j)]
    for i, j in enumerate(relevant):
        print(f"{i}: {j.get('title')} @ {j.get('company')}")

if __name__ == "__main__":
    asyncio.run(run())
