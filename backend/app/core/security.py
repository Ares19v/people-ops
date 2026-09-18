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

# PII Masking Utilities for DPDP Act Compliance
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
