import pytest
from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password
from app.models.user import UserRole

def test_password_hashing():
    pwd = "SecurePassword@123"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_token_generation_and_decode():
    user_id = "test-user-12345"
    role = UserRole.EMPLOYEE.value
    token = create_access_token(subject=user_id, role=role)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["role"] == role

def test_invalid_token_decode():
    payload = decode_access_token("invalid.token.signature")
    assert payload is None
