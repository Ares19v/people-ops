import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.core.security import mask_all_pii
from app.models.user import (
    User, EmployeeProfile, Document, AuditLog, UserRole, OnboardingStatus, DocumentType
)
from app.schemas.onboarding import (
    OnboardingStep1Request, ResumeExtractionResponse, OnboardingConfirmRequest
)

class OnboardingService:
    @staticmethod
    async def create_or_update_employee(
        db: AsyncSession, creator: User, data: OnboardingStep1Request
    ) -> User:
        # Check permissions: HR_ASSOCIATE, HR_MANAGER, ADMIN can onboard employees
        if creator.role not in [UserRole.HR_ASSOCIATE, UserRole.HR_MANAGER, UserRole.ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to onboard employees.")

        # Check existing email
        stmt = select(User).filter(User.email == data.email)
        res = await db.execute(stmt)
        existing_user = res.scalars().first()

        if existing_user:
            user = existing_user
        else:
            user = User(
                email=data.email,
                full_name=data.full_name,
                role=UserRole.EMPLOYEE,
                department=data.department,
                designation=data.designation,
                manager_id=data.manager_id
            )
            db.add(user)
            await db.flush()

        # Create or update profile
        prof_stmt = select(EmployeeProfile).filter(EmployeeProfile.user_id == user.id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalars().first()

        if not profile:
            profile = EmployeeProfile(
                user_id=user.id,
                date_of_birth=data.date_of_birth,
                address_encrypted=data.address, # In prod, symmetric AES-256
                phone_encrypted=data.phone,
                skills=data.skills,
                experience_years=data.experience_years,
                employment_type=data.employment_type,
                onboarding_status=OnboardingStatus.IN_PROGRESS
            )
            db.add(profile)
        else:
            profile.date_of_birth = data.date_of_birth
            profile.address_encrypted = data.address
            profile.phone_encrypted = data.phone
            profile.skills = data.skills
            profile.experience_years = data.experience_years
            profile.employment_type = data.employment_type
            profile.onboarding_status = OnboardingStatus.IN_PROGRESS

        # Audit
        audit = AuditLog(
            actor_id=creator.id,
            action="ONBOARDING_INITIATED",
            resource_type="user",
            resource_id=user.id,
            details={"email": data.email, "role": user.role.value}
        )
        db.add(audit)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def upload_document(
        db: AsyncSession, uploader: User, target_user_id: str, doc_type: DocumentType, file: UploadFile
    ) -> Document:
        # Check permissions: user can upload for self, or HR can upload
        if uploader.id != target_user_id and uploader.role not in [UserRole.HR_ASSOCIATE, UserRole.HR_MANAGER, UserRole.ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot upload documents for another employee.")

        content = await file.read()
        file_size = len(content)
        checksum = hashlib.sha256(content).hexdigest()

        # Save to local storage dir (or S3 in production)
        upload_dir = os.path.join(os.getcwd(), "uploads", target_user_id)
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{doc_type.value}_{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, "wb") as f:
            f.write(content)

        doc = Document(
            user_id=target_user_id,
            doc_type=doc_type,
            file_path=file_path,
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=float(file_size),
            checksum=checksum,
            is_verified=False
        )
        db.add(doc)

        audit = AuditLog(
            actor_id=uploader.id,
            action="DOCUMENT_UPLOADED",
            resource_type="document",
            resource_id=doc.id,
            details={"doc_type": doc_type.value, "checksum": checksum}
        )
        db.add(audit)
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def extract_resume(document_id: str, db: AsyncSession) -> ResumeExtractionResponse:
        """Controlled resume extraction service returning proposed fields with human-in-the-loop review."""
        stmt = select(Document).filter(Document.id == document_id)
        res = await db.execute(stmt)
        doc = res.scalars().first()
        if not doc or doc.doc_type != DocumentType.RESUME:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume document not found.")

        # Simulate intelligent extraction from resume text/pdf
        extracted = ResumeExtractionResponse(
            document_id=doc.id,
            extracted_name=doc.original_filename.replace(".pdf", "").replace("_", " ").title(),
            extracted_email=None,
            extracted_phone=None,
            extracted_skills=["Python", "FastAPI", "PostgreSQL", "React", "Docker", "Machine Learning"],
            extracted_experience_years=4.5,
            extracted_education=["B.Tech Computer Science, University of Mumbai"],
            confidence_score=0.92
        )

        # Update profile state to EXTRACTED_AWAITING_REVIEW
        prof_stmt = select(EmployeeProfile).filter(EmployeeProfile.user_id == doc.user_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalars().first()
        if profile:
            profile.onboarding_status = OnboardingStatus.EXTRACTED_AWAITING_REVIEW
            profile.extracted_resume_data = extracted.model_dump()
            await db.commit()

        return extracted

    @staticmethod
    async def confirm_onboarding(
        db: AsyncSession, reviewer: User, request: OnboardingConfirmRequest
    ) -> EmployeeProfile:
        if not request.user_consent_granted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DPDP Act Compliance: Explicit employee consent is required to process and store profile data."
            )

        prof_stmt = select(EmployeeProfile).filter(EmployeeProfile.user_id == request.user_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalars().first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

        # Update with confirmed values
        profile.skills = request.confirmed_skills
        profile.experience_years = request.confirmed_experience_years
        profile.address_encrypted = request.confirmed_address
        profile.phone_encrypted = request.confirmed_phone
        profile.onboarding_status = OnboardingStatus.COMPLETED

        # Audit
        audit = AuditLog(
            actor_id=reviewer.id,
            action="ONBOARDING_CONFIRMED_DPDP_CONSENT",
            resource_type="employee_profile",
            resource_id=profile.id,
            details={"consent_granted": True, "skills_count": len(request.confirmed_skills)}
        )
        db.add(audit)
        await db.commit()
        await db.refresh(profile)
        return profile
