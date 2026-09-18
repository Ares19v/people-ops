# get_llm_provider

> 13 nodes · cohesion 0.24

## Key Concepts

- **get_llm_provider()** (10 connections) — `backend/app/agents/llm_provider.py`
- **llm_provider.py** (8 connections) — `backend/app/agents/llm_provider.py`
- **BaseLLMProvider** (6 connections) — `backend/app/agents/llm_provider.py`
- **MockLLMProvider** (6 connections) — `backend/app/agents/llm_provider.py`
- **VertexGeminiProvider** (6 connections) — `backend/app/agents/llm_provider.py`
- **ABC** (2 connections)
- **.generate_response()** (2 connections) — `backend/app/agents/llm_provider.py`
- **.__init__()** (2 connections) — `backend/app/agents/timesheet_agent.py`
- **.generate_response()** (1 connections) — `backend/app/agents/llm_provider.py`
- **.generate_response()** (1 connections) — `backend/app/agents/llm_provider.py`
- **Deterministic local LLM provider for rapid development, testing, and offline…** (1 connections) — `backend/app/agents/llm_provider.py`
- **Production provider using Google Vertex AI / Gemini via Google GenAI SDK.** (1 connections) — `backend/app/agents/llm_provider.py`
- **.__init__()** (1 connections) — `backend/app/agents/llm_provider.py`

## Relationships

- [app_models_user](app_models_user.md) (4 shared connections)
- [timesheets.py](timesheets.py.md) (3 shared connections)
- [security.py](security.py.md) (1 shared connections)
- [main.py](main.py.md) (1 shared connections)

## Source Files

- `backend/app/agents/llm_provider.py`
- `backend/app/agents/timesheet_agent.py`

## Audit Trail

- EXTRACTED: 28 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*