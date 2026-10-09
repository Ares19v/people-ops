from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password, get_password_hash
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse, MockLoginRequest, LoginRequest, UserResponse
from app.services.auth_service import get_current_user, get_role_permissions

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
async def login_json(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Standard JSON login endpoint accepting email and password."""
    stmt = select(User).filter(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id, role=user.role.value)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=get_role_permissions(user.role)
    )

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).filter(User.email == form_data.username)
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if not user or not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id, role=user.role.value)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=get_role_permissions(user.role)
    )

@router.post("/mock-login", response_model=TokenResponse)
async def mock_login(
    payload: MockLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Developer mock login for instant role switching with full RBAC permissions."""
    if not settings.MOCK_SSO_ENABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mock SSO is disabled in production.")

    stmt = select(User).filter(User.role == payload.role)
    if payload.email:
        stmt = stmt.filter(User.email == payload.email)
    
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        # Create default user for this role on the fly if seed not run
        email_map = {
            UserRole.EMPLOYEE: "employee@intelera.corp",
            UserRole.HR_ASSOCIATE: "associate@intelera.corp",
            UserRole.HR_MANAGER: "manager@intelera.corp",
            UserRole.ADMIN: "admin@intelera.corp",
        }
        name_map = {
            UserRole.EMPLOYEE: "Aarav Sharma (Staff Engineer)",
            UserRole.HR_ASSOCIATE: "Priya Patel (HR Associate)",
            UserRole.HR_MANAGER: "Vikram Malhotra (HR Operations Manager)",
            UserRole.ADMIN: "Devansh Tyagi (System Admin)",
        }
        user = User(
            email=payload.email or email_map.get(payload.role, "user@intelera.corp"),
            full_name=name_map.get(payload.role, "Test User"),
            role=payload.role,
            department="Human Resources" if payload.role != UserRole.EMPLOYEE else "Engineering",
            designation=name_map.get(payload.role, "Staff").split("(")[-1].replace(")", "")
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(subject=user.id, role=user.role.value)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=get_role_permissions(user.role)
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        department=current_user.department,
        designation=current_user.designation,
        manager_id=current_user.manager_id,
        is_active=current_user.is_active,
        permissions=get_role_permissions(current_user.role)
    )
