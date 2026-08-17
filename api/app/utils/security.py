import os
import json
import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings

def get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        key = os.environ.get("ENCRYPTION_KEY", "")
        
    if not key:
        raise ValueError("ENCRYPTION_KEY setting or environment variable is missing.")
        
    # Derive a valid key from the user-configured string using SHA256.
    key_hash = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(fernet_key)

def encrypt_session_data(data: dict) -> bytes:
    """Encrypts session dict data to encrypted bytes."""
    fernet = get_fernet()
    json_bytes = json.dumps(data).encode("utf-8")
    return fernet.encrypt(json_bytes)

def decrypt_session_data(encrypted_data: bytes) -> dict:
    """Decrypts session encrypted bytes back to dict data."""
    fernet = get_fernet()
    decrypted_bytes = fernet.decrypt(encrypted_data)
    return json.loads(decrypted_bytes.decode("utf-8"))
