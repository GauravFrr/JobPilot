import os
import json
import base64
import hashlib
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from cryptography.fernet import Fernet

def get_fernet(encryption_key: str) -> Fernet:
    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY is empty.")
    key_hash = hashlib.sha256(encryption_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(fernet_key)

def encrypt_session_data(data: dict, encryption_key: str) -> bytes:
    fernet = get_fernet(encryption_key)
    json_bytes = json.dumps(data).encode("utf-8")
    return fernet.encrypt(json_bytes)

def main():
    print("Loading environment variables from .env...")
    # Load .env relative to this script
    root_dir = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=root_dir / ".env")
    
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key:
        print("❌ Error: ENCRYPTION_KEY not found in .env file.")
        return
        
    print("Starting headed browser for manual login...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Navigating to LinkedIn login page...")
        page.goto("https://www.linkedin.com/login")
        
        print("\n👉 Please log in manually in the browser window.")
        print("Waiting for successful login (redirect to feed or homepage)...")
        
        # Poll URL state to detect login
        while True:
            try:
                current_url = page.url
                if "linkedin.com/feed" in current_url or "linkedin.com/mynetwork" in current_url:
                    print(f"🎉 Login detected! Current URL: {current_url}")
                    break
            except Exception:
                # Browser closed or navigated away
                print("❌ Browser closed before successful login.")
                return
            page.wait_for_timeout(1000)
            
        print("Waiting 5 seconds for session state and cookies to fully hydrate/settle...")
        page.wait_for_timeout(5000)
        
        print("Saving and encrypting storage state...")
        storage_state = context.storage_state()
        
        encrypted_bytes = encrypt_session_data(storage_state, encryption_key)
        
        # Write to storage_state/linkedin.enc
        output_dir = root_dir / "storage_state"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "linkedin.enc"
        
        with open(output_file, "wb") as f:
            f.write(encrypted_bytes)
            
        print(f"✅ Success! Session state encrypted and saved to {output_file}")
        browser.close()

if __name__ == "__main__":
    main()
