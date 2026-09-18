# main.py

> 19 nodes · cohesion 0.12

## Key Concepts

- **main.py** (19 connections) — `backend/app/main.py`
- **FastAPI** (14 connections)
- **app_core_config** (10 connections)
- **health.py** (3 connections) — `backend/app/api/v1/health.py`
- **lifespan()** (3 connections) — `backend/app/main.py`
- **health_check()** (2 connections) — `backend/app/api/v1/health.py`
- **root()** (2 connections) — `backend/app/main.py`
- **app_api_v1_agents** (1 connections)
- **app_api_v1_auth** (1 connections)
- **app_api_v1_health** (1 connections)
- **app_api_v1_leaves** (1 connections)
- **app_api_v1_onboarding** (1 connections)
- **app_api_v1_policy** (1 connections)
- **app_api_v1_reports** (1 connections)
- **app_api_v1_timesheets** (1 connections)
- **get** (1 connections)
- **get** (1 connections)
- **contextlib** (1 connections)
- **fastapi_middleware_cors** (1 connections)

## Relationships

- [timesheets.py](timesheets.py.md) (6 shared connections)
- [models/__init__.py](models-__init__.py.md) (4 shared connections)
- [security.py](security.py.md) (3 shared connections)
- [app_models_user](app_models_user.md) (3 shared connections)
- [User](User.md) (3 shared connections)
- [UserRole](UserRole.md) (2 shared connections)
- [leaves.py](leaves.py.md) (2 shared connections)
- [get_llm_provider](get_llm_provider.md) (1 shared connections)
- [test_api_endpoints.py](test_api_endpoints.py.md) (1 shared connections)

## Source Files

- `backend/app/api/v1/health.py`
- `backend/app/main.py`

## Audit Trail

- EXTRACTED: 45 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*