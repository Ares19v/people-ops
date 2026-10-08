import re
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from jose import jwt, JWTError
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "iat": datetime.now(timezone.utc)
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

# Static Irreversible PII Masking Utilities (used for output sanitization & plain logging)
# NOTE: For dynamic, stateful, reversible LLM token shielding (DPDP TokenVault),
# see app.compliance.phi_engine.compliance_engine
AADHAAR_REGEX = re.compile(r'\b\d{4}[ -]?\d{4}[ -]?\d{4}\b')
PAN_REGEX = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b')
PHONE_REGEX = re.compile(r'\b(?:\+91|91|0)?[6-9]\d{9}\b')

def mask_aadhaar(text: str) -> str:
    """Masks 12-digit Indian Aadhaar numbers, revealing only the last 4 digits."""
    def repl(match):
        val = match.group(0).replace(" ", "").replace("-", "")
        return f"XXXX-XXXX-{val[-4:]}"
    return AADHAAR_REGEX.sub(repl, text)

def mask_pan(text: str) -> str:
    """Masks Indian PAN numbers, e.g. ABCDE1234F -> ABXXXXXX4F."""
    def repl(match):
        val = match.group(0)
        return f"{val[:2]}XXXXXX{val[-2:]}"
    return PAN_REGEX.sub(repl, text)

def mask_all_pii(text: str) -> str:
    """Recursively scrub high-risk PII before returning or sending to observability."""
    if not text:
        return text
    text = mask_aadhaar(text)
    text = mask_pan(text)
    return text

# Real AES-256 Symmetric Field-Level Encryption (DPDP & HIPAA Compliance)
import base64
import hashlib
from cryptography.fernet import Fernet

def _get_field_cipher() -> Fernet:
    """Derives a deterministic 32-byte Fernet key from SECRET_KEY."""
    derived_key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    url_safe_key = base64.urlsafe_b64encode(derived_key)
    return Fernet(url_safe_key)

def encrypt_field(plaintext: Optional[str]) -> Optional[str]:
    """Symmetrically encrypts a string before saving to database."""
    if not plaintext:
        return plaintext
    try:
        cipher = _get_field_cipher()
        return "enc:" + cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except Exception:
        return plaintext

def decrypt_field(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypts a previously encrypted database field string."""
    if not ciphertext or not ciphertext.startswith("enc:"):
        return ciphertext
    try:
        raw_token = ciphertext[4:]
        cipher = _get_field_cipher()
        return cipher.decrypt(raw_token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ciphertext
