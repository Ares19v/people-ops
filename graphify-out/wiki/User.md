# User

> 36 nodes · cohesion 0.16

## Key Concepts

- **User** (65 connections) — `backend/app/models/user.py`
- **v1/onboarding.py** (28 connections) — `backend/app/api/v1/onboarding.py`
- **onboarding_service.py** (24 connections) — `backend/app/services/onboarding_service.py`
- **OnboardingService** (20 connections) — `backend/app/services/onboarding_service.py`
- **AuditLog** (16 connections) — `backend/app/models/user.py`
- **DocumentType** (10 connections) — `backend/app/models/user.py`
- **schemas/onboarding.py** (10 connections) — `backend/app/schemas/onboarding.py`
- **upload_onboarding_document()** (9 connections) — `backend/app/api/v1/onboarding.py`
- **EmployeeProfile** (9 connections) — `backend/app/models/user.py`
- **confirm_onboarding_profile()** (8 connections) — `backend/app/api/v1/onboarding.py`
- **initiate_employee_onboarding()** (8 connections) — `backend/app/api/v1/onboarding.py`
- **OnboardingConfirmRequest** (8 connections) — `backend/app/schemas/onboarding.py`
- **OnboardingStep1Request** (8 connections) — `backend/app/schemas/onboarding.py`
- **.upload_document()** (8 connections) — `backend/app/services/onboarding_service.py`
- **extract_resume_details()** (7 connections) — `backend/app/api/v1/onboarding.py`
- **Document** (7 connections) — `backend/app/models/user.py`
- **ResumeExtractionResponse** (7 connections) — `backend/app/schemas/onboarding.py`
- **.confirm_onboarding()** (7 connections) — `backend/app/services/onboarding_service.py`
- **DocumentUploadResponse** (6 connections) — `backend/app/schemas/onboarding.py`
- **require_role()** (6 connections) — `backend/app/services/auth_service.py`
- **.create_or_update_employee()** (6 connections) — `backend/app/services/onboarding_service.py`
- **.extract_resume()** (5 connections) — `backend/app/services/onboarding_service.py`
- **AsyncSession** (4 connections)
- **post** (4 connections)
- **Base** (4 connections)
- *... and 11 more nodes in this community*

## Relationships

- [timesheets.py](timesheets.py.md) (33 shared connections)
- [models/__init__.py](models-__init__.py.md) (21 shared connections)
- [UserRole](UserRole.md) (20 shared connections)
- [app_models_user](app_models_user.md) (19 shared connections)
- [leaves.py](leaves.py.md) (16 shared connections)
- [main.py](main.py.md) (3 shared connections)
- [security.py](security.py.md) (3 shared connections)

## Source Files

- `backend/app/api/v1/onboarding.py`
- `backend/app/models/user.py`
- `backend/app/schemas/onboarding.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/onboarding_service.py`
- `promptfoo/promptfoo_provider.py`

## Audit Trail

- EXTRACTED: 159 (74%)
- INFERRED: 57 (26%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*