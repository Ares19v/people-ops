from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.models.user import User, UserRole, DocumentType, Document, EmployeeProfile
from app.schemas.onboarding import (
    OnboardingStep1Request, DocumentUploadResponse, ResumeExtractionResponse, OnboardingConfirmRequest
)
from app.schemas.auth import UserResponse
from app.services.auth_service import get_current_user, require_role
from app.services.onboarding_service import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["Employee Onboarding"])

@router.post("/initiate", response_model=UserResponse)
async def initiate_employee_onboarding(
    payload: OnboardingStep1Request,
    current_user: User = Depends(require_role([UserRole.HR_ASSOCIATE, UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    user = await OnboardingService.create_or_update_employee(db, current_user, payload)
    return user

@router.post("/upload-document", response_model=DocumentUploadResponse)
async def upload_onboarding_document(
    user_id: str = Form(...),
    doc_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate MIME types
    allowed_types = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Only PDF, JPEG, and PNG are permitted."
        )

    doc = await OnboardingService.upload_document(db, current_user, user_id, doc_type, file)
    return DocumentUploadResponse(
        document_id=doc.id,
        user_id=doc.user_id,
        doc_type=doc.doc_type,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        checksum=doc.checksum,
        is_verified=doc.is_verified
    )

@router.post("/extract-resume/{document_id}", response_model=ResumeExtractionResponse)
async def extract_resume_details(
    document_id: str,
    current_user: User = Depends(require_role([UserRole.HR_ASSOCIATE, UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    extracted = await OnboardingService.extract_resume(document_id, db)
    return extracted

@router.post("/confirm")
async def confirm_onboarding_profile(
    payload: OnboardingConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Ensure user can confirm for self or HR can confirm
    if current_user.id != payload.user_id and current_user.role not in [UserRole.HR_ASSOCIATE, UserRole.HR_MANAGER, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot confirm profile for another user.")

    profile = await OnboardingService.confirm_onboarding(db, current_user, payload)
    return {
        "status": "SUCCESS",
        "message": "Employee onboarding completed with explicit DPDP Act consent.",
        "profile_id": profile.id,
        "onboarding_status": profile.onboarding_status.value
    }
