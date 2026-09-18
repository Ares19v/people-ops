# UserRole

> 28 nodes · cohesion 0.15

## Key Concepts

- **UserRole** (36 connections) — `backend/app/models/user.py`
- **schemas/__init__.py** (33 connections) — `backend/app/schemas/__init__.py`
- **v1/auth.py** (24 connections) — `backend/app/api/v1/auth.py`
- **test_auth_rbac.py** (11 connections) — `backend/tests/test_auth_rbac.py`
- **mock_login()** (9 connections) — `backend/app/api/v1/auth.py`
- **create_access_token()** (9 connections) — `backend/app/core/security.py`
- **schemas/auth.py** (9 connections) — `backend/app/schemas/auth.py`
- **login_for_access_token()** (8 connections) — `backend/app/api/v1/auth.py`
- **decode_access_token()** (7 connections) — `backend/app/core/security.py`
- **TokenResponse** (7 connections) — `backend/app/schemas/auth.py`
- **verify_password()** (6 connections) — `backend/app/core/security.py`
- **MockLoginRequest** (6 connections) — `backend/app/schemas/auth.py`
- **UserResponse** (6 connections) — `backend/app/schemas/auth.py`
- **BaseModel** (4 connections)
- **test_jwt_token_generation_and_decode()** (4 connections) — `backend/tests/test_auth_rbac.py`
- **app_schemas_auth** (3 connections)
- **get_current_user_profile()** (3 connections) — `backend/app/api/v1/auth.py`
- **LoginRequest** (3 connections) — `backend/app/schemas/auth.py`
- **test_password_hashing()** (3 connections) — `backend/tests/test_auth_rbac.py`
- **AsyncSession** (2 connections)
- **post** (2 connections)
- **Any** (2 connections)
- **test_invalid_token_decode()** (2 connections) — `backend/tests/test_auth_rbac.py`
- **fastapi_security** (2 connections)
- **get** (1 connections)
- *... and 3 more nodes in this community*

## Relationships

- [timesheets.py](timesheets.py.md) (27 shared connections)
- [User](User.md) (20 shared connections)
- [leaves.py](leaves.py.md) (13 shared connections)
- [app_models_user](app_models_user.md) (11 shared connections)
- [models/__init__.py](models-__init__.py.md) (10 shared connections)
- [security.py](security.py.md) (5 shared connections)
- [main.py](main.py.md) (2 shared connections)
- [test_api_endpoints.py](test_api_endpoints.py.md) (1 shared connections)

## Source Files

- `backend/app/api/v1/auth.py`
- `backend/app/core/security.py`
- `backend/app/models/user.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/auth.py`
- `backend/tests/test_auth_rbac.py`

## Audit Trail

- EXTRACTED: 123 (84%)
- INFERRED: 24 (16%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*