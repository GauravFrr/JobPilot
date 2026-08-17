import os
import logging
import httpx
import random
import re
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger("workers.llm.provider")

# Global clients cache
_gemini_client = None

def get_gemini_client() -> genai.Client:
    """Lazily initializes and returns the Google GenAI client."""
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment.")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

async def generate(prompt: str, task_type: str, model_tier: str = "cheap") -> str:
    """
    Unified entry point for LLM text generation.
    Reads LLM_PROVIDER from env ('gemini' or 'claude') and routes accordingly.
    
    model_tier options:
      - 'cheap': used for fast/structured tasks (keyword extraction, matching rerank)
      - 'premium': used for high-quality text rewriting (resume bullets, outreach emails)
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    
    if provider == "gemini":
        models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash"]
        logger.info(f"Routing task '{task_type}' to Gemini provider with fallbacks...")
        
        max_retries = 8
        model_idx = 0
        
        for attempt in range(max_retries):
            model_name = models[model_idx % len(models)]
            logger.info(f"Attempt {attempt + 1}/{max_retries}: Using model {model_name}...")
            try:
                client = get_gemini_client()
                import asyncio
                loop = asyncio.get_event_loop()
                
                response = await loop.run_in_executor(
                    None, 
                    lambda: client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                )
                
                if not response.text:
                    raise ValueError("Gemini returned an empty response.")
                return response.text
                
            except Exception as e:
                err_msg = str(e)
                logger.warning(f"Gemini API call with model {model_name} failed: {err_msg}")
                if attempt == max_retries - 1:
                    logger.error("Max retries exceeded for Gemini API call.")
                    raise e
                
                is_rate_limit = any(term in err_msg.lower() or term in type(e).__name__.lower() 
                                    for term in ["429", "resource_exhausted", "quota exceeded", "resource exhausted"])
                
                if is_rate_limit:
                    model_idx += 1
                    next_model = models[model_idx % len(models)]
                    logger.warning(f"Rate limit hit on {model_name}. Switching immediately to fallback model: {next_model}")
                    if model_idx >= len(models):
                        match = re.search(r"retry in (\d+\.?\d*)s", err_msg)
                        sleep_time = float(match.group(1)) + 1.0 if match else 5.0
                        logger.warning(f"All fallback models rate limited. Sleeping for {sleep_time:.2f} seconds before retrying...")
                        await asyncio.sleep(sleep_time)
                else:
                    sleep_time = (2 ** attempt) + random.random()
                    await asyncio.sleep(sleep_time)
            
    elif provider == "claude":
        # Claude provider integration
        api_key = os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY is not set in environment.")
            
        model_name = "claude-haiku-4-5-20251001" if model_tier == "cheap" else "claude-sonnet-5"
        logger.info(f"Routing task '{task_type}' to Claude provider (model: {model_name})...")
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "max_tokens": 1500 if model_tier == "premium" else 500,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        base_url = os.environ.get("CLAUDE_API_BASE", "https://api.anthropic.com").rstrip('/')
        if "/messages" in base_url:
            endpoint = base_url
        elif base_url.endswith("/v1"):
            endpoint = f"{base_url}/messages"
        else:
            endpoint = f"{base_url}/v1/messages"
        
        async with httpx.AsyncClient() as httpx_client:
            try:
                response = await httpx_client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                if response.status_code != 200:
                    raise ValueError(f"Claude API returned status code {response.status_code}: {response.text}")
                    
                result = response.json()
                return result["content"][0]["text"].strip()
                
            except Exception as e:
                logger.error(f"Claude API call failed: {str(e)}")
                raise e
                
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
