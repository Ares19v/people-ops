from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from app.models.user import OnboardingStatus, DocumentType

class OnboardingStep1Request(BaseModel):
    full_name: str
    email: EmailStr
    department: str
    designation: str
    manager_id: Optional[str] = None
    date_of_birth: str
    address: str
    phone: str
    skills: List[str] = []
    experience_years: float = 0.0
    employment_type: str = "Full-Time Permanent"

class DocumentUploadResponse(BaseModel):
    document_id: str
    user_id: str
    doc_type: DocumentType
    original_filename: str
    file_size: float
    checksum: str
    is_verified: bool

class ResumeExtractionResponse(BaseModel):
    document_id: str
    extracted_name: Optional[str] = None
    extracted_email: Optional[str] = None
    extracted_phone: Optional[str] = None
    extracted_skills: List[str] = []
    extracted_experience_years: Optional[float] = None
    extracted_education: List[str] = []
    confidence_score: float = 0.95

class OnboardingConfirmRequest(BaseModel):
    user_id: str
    confirmed_skills: List[str]
    confirmed_experience_years: float
    confirmed_address: str
    confirmed_phone: str
    user_consent_granted: bool # DPDP Act consent requirement
