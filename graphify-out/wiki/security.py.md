# security.py

> 36 nodes · cohesion 0.07

## Key Concepts

- **security.py** (13 connections) — `backend/app/core/security.py`
- **os** (10 connections)
- **mask_all_pii()** (9 connections) — `backend/app/core/security.py`
- **langsmith_tracer.py** (8 connections) — `backend/app/observability/langsmith_tracer.py`
- **app_core_security** (7 connections)
- **guardrails_manager.py** (7 connections) — `backend/app/guardrails/guardrails_manager.py`
- **GuardrailsManager** (6 connections) — `backend/app/guardrails/guardrails_manager.py`
- **mask_pan()** (5 connections) — `backend/app/core/security.py`
- **config.py** (4 connections) — `backend/app/core/config.py`
- **mask_aadhaar()** (4 connections) — `backend/app/core/security.py`
- **LangSmithTracer** (4 connections) — `backend/app/observability/langsmith_tracer.py`
- **re** (4 connections)
- **.check_output()** (3 connections) — `backend/app/guardrails/guardrails_manager.py`
- **.trace_agent_run()** (3 connections) — `backend/app/observability/langsmith_tracer.py`
- **Settings** (2 connections) — `backend/app/core/config.py`
- **repl()** (2 connections) — `backend/app/core/security.py`
- **.check_input()** (2 connections) — `backend/app/guardrails/guardrails_manager.py`
- **.__init__()** (2 connections) — `backend/app/guardrails/guardrails_manager.py`
- **._init_nemo()** (2 connections) — `backend/app/guardrails/guardrails_manager.py`
- **time** (2 connections)
- **repl()** (1 connections) — `backend/app/core/security.py`
- **Masks 12-digit Indian Aadhaar numbers, revealing only the last 4 digits.** (1 connections) — `backend/app/core/security.py`
- **Masks Indian PAN numbers, e.g. ABCDE1234F -> ABXXXXXX4F.** (1 connections) — `backend/app/core/security.py`
- **Recursively scrub high-risk PII before returning or sending to observability.** (1 connections) — `backend/app/core/security.py`
- **Enterprise safety manager running NeMo Guardrails and deterministic DPDP…** (1 connections) — `backend/app/guardrails/guardrails_manager.py`
- *... and 11 more nodes in this community*

## Relationships

- [timesheets.py](timesheets.py.md) (7 shared connections)
- [UserRole](UserRole.md) (5 shared connections)
- [models/__init__.py](models-__init__.py.md) (4 shared connections)
- [app_models_user](app_models_user.md) (4 shared connections)
- [User](User.md) (3 shared connections)
- [main.py](main.py.md) (3 shared connections)
- [get_llm_provider](get_llm_provider.md) (1 shared connections)

## Source Files

- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/guardrails/guardrails_manager.py`
- `backend/app/observability/langsmith_tracer.py`

## Audit Trail

- EXTRACTED: 69 (97%)
- INFERRED: 2 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*