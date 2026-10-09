from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token, verify_password, create_access_token
from app.models.user import User, UserRole

import time
import threading
from typing import List, Optional, Dict, Tuple

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token", auto_error=False)

_user_cache: Dict[str, Tuple[User, float]] = {}
_cache_lock = threading.Lock()

def invalidate_user_cache(user_id: Optional[str] = None):
    with _cache_lock:
        if user_id:
            _user_cache.pop(user_id, None)
        else:
            _user_cache.clear()

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    
    now = time.time()
    with _cache_lock:
        cached = _user_cache.get(user_id)
        if cached and (now - cached[1] < 60.0):
            return cached[0]

    result = await db.execute(select(User).filter(User.id == user_id, User.is_active == True))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive.")

    with _cache_lock:
        _user_cache[user_id] = (user, now)
        if len(_user_cache) > 200:
            oldest = next(iter(_user_cache))
            del _user_cache[oldest]

    return user

def get_role_permissions(role: UserRole) -> List[str]:
    """Returns granular RBAC permissions list for a user role."""
    ROLE_PERMISSIONS_MAP = {
        UserRole.EMPLOYEE: [
            "leaves:read_own", "leaves:apply",
            "timesheets:read_own", "timesheets:log",
            "documents:read_own", "documents:upload_own",
            "chat:interact", "policies:read"
        ],
        UserRole.HR_ASSOCIATE: [
            "leaves:read_own", "leaves:apply", "leaves:read_all",
            "timesheets:read_own", "timesheets:log",
            "documents:read_all", "documents:upload_all", "documents:verify",
            "onboarding:create", "onboarding:read",
            "chat:interact", "policies:read"
        ],
        UserRole.HR_MANAGER: [
            "leaves:read_own", "leaves:apply", "leaves:read_department", "leaves:approve",
            "timesheets:read_department", "timesheets:approve",
            "reports:read_department", "reports:export",
            "documents:read_all", "onboarding:review",
            "chat:interact", "policies:read"
        ],
        UserRole.ADMIN: [
            "leaves:read_all", "leaves:manage_all",
            "timesheets:read_all", "timesheets:manage_all",
            "reports:read_all", "reports:export",
            "documents:read_all", "documents:manage_all",
            "prompts:read", "prompts:write", "system:sync",
            "audit:read", "users:manage",
            "chat:interact", "policies:read", "policies:write"
        ]
    }
    return ROLE_PERMISSIONS_MAP.get(role, ["chat:interact", "policies:read"])

def require_role(allowed_roles: List[UserRole]):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {[r.value for r in allowed_roles]}, user has {current_user.role.value}"
            )
        return current_user
    return role_checker
