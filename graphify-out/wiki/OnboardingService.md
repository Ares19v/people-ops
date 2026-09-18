# OnboardingService

> God node · 20 connections · `backend/app/services/onboarding_service.py`

**Community:** [User](User.md)

## Connections by Relation

### contains
- onboarding_service.py `EXTRACTED`

### imports
- v1/onboarding.py `EXTRACTED`

### method
- .upload_document() `EXTRACTED`
- .confirm_onboarding() `EXTRACTED`
- .create_or_update_employee() `EXTRACTED`
- .extract_resume() `EXTRACTED`

### uses
- [User](User.md) `INFERRED`
- [UserRole](UserRole.md) `INFERRED`
- [AuditLog](AuditLog.md) `INFERRED`
- DocumentType `INFERRED`
- upload_onboarding_document() `INFERRED`
- EmployeeProfile `INFERRED`
- confirm_onboarding_profile() `INFERRED`
- initiate_employee_onboarding() `INFERRED`
- OnboardingConfirmRequest `INFERRED`
- OnboardingStep1Request `INFERRED`
- OnboardingStatus `INFERRED`
- extract_resume_details() `INFERRED`
- ResumeExtractionResponse `INFERRED`
- Document `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*