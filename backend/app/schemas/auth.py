from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.user import UserRole

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class MockLoginRequest(BaseModel):
    role: UserRole
    email: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    role: UserRole

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    department: str
    designation: str
    manager_id: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
