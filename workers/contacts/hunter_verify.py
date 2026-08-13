import httpx
import logging
from typing import Optional

logger = logging.getLogger("workers.contacts.hunter_verify")

async def verify_email_with_hunter(email: str, api_key: str) -> Optional[str]:
    """
    Calls Hunter.io Email Verifier API to verify an email address.
    Returns:
        - 'verified' if deliverable
        - 'inferred' if risky, unknown, or other non-deliverable state
        - None if API fails or rate limited
    """
    if not api_key:
        logger.warning("No Hunter.io API key provided. Skipping Hunter verify.")
        return None
        
    url = "https://api.hunter.io/v2/email-verifier"
    params = {
        "email": email,
        "api_key": api_key
    }
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Calling Hunter.io email verification for: {email}")
            response = await client.get(url, params=params, timeout=10)
            if response.status_code == 429:
                logger.warning("Hunter.io API rate limit hit.")
                return None
            elif response.status_code != 200:
                logger.error(f"Hunter.io API returned status {response.status_code}: {response.text}")
                return None
                
            data = response.json()
            result_data = data.get("data", {})
            result = result_data.get("result")
            
            logger.info(f"Hunter.io verification result for {email}: {result}")
            if result == "deliverable":
                return "verified"
            else:
                return "inferred"
                
        except Exception as e:
            logger.error(f"Hunter.io verification API error: {str(e)}")
            return None
