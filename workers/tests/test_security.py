import os
import sys

# Add api directory to path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.utils.security import encrypt_session_data, decrypt_session_data

def test_encryption():
    print("Running encryption tests...")
    
    # Set fallback key in environment
    os.environ["ENCRYPTION_KEY"] = "super-secret-key-12345"
    
    test_dict = {"cookies": [{"name": "li_at", "value": "mock_cookie_val"}], "localStorage": {}}
    
    # Encrypt
    enc_bytes = encrypt_session_data(test_dict)
    assert isinstance(enc_bytes, bytes)
    assert len(enc_bytes) > 0
    
    # Decrypt
    dec_dict = decrypt_session_data(enc_bytes)
    assert dec_dict == test_dict
    assert dec_dict["cookies"][0]["name"] == "li_at"
    
    print("Encryption tests passed successfully!")

if __name__ == "__main__":
    test_encryption()
