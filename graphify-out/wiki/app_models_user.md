# app_models_user

> 59 nodes · cohesion 0.05

## Key Concepts

- **app_models_user** (23 connections)
- **orchestrator.py** (16 connections) — `backend/app/agents/orchestrator.py`
- **leave_agent.py** (15 connections) — `backend/app/agents/leave_agent.py`
- **agents.py** (13 connections) — `backend/app/api/v1/agents.py`
- **StructuredAction** (13 connections) — `backend/app/schemas/agent.py`
- **policy_agent.py** (10 connections) — `backend/app/agents/policy_agent.py`
- **LeaveAgent** (8 connections) — `backend/app/agents/leave_agent.py`
- **v1/policy.py** (8 connections) — `backend/app/api/v1/policy.py`
- **graph_rag_service.py** (8 connections) — `backend/app/services/graph_rag_service.py`
- **promptfoo_provider.py** (8 connections) — `promptfoo/promptfoo_provider.py`
- **app_schemas_agent** (7 connections)
- **app_services_auth_service** (7 connections)
- **agent.py** (7 connections) — `backend/app/schemas/agent.py`
- **AgentChatResponse** (7 connections) — `backend/app/schemas/agent.py`
- **CitationItem** (7 connections) — `backend/app/schemas/agent.py`
- **.handle_request()** (6 connections) — `backend/app/agents/leave_agent.py`
- **RootOrchestrator** (6 connections) — `backend/app/agents/orchestrator.py`
- **HRPolicyAgent** (6 connections) — `backend/app/agents/policy_agent.py`
- **GraphRAGService** (6 connections) — `backend/app/services/graph_rag_service.py`
- **.handle_request()** (5 connections) — `backend/app/agents/policy_agent.py`
- **chat_with_multi_agent_system()** (5 connections) — `backend/app/api/v1/agents.py`
- **AgentChatRequest** (5 connections) — `backend/app/schemas/agent.py`
- **pydantic** (5 connections)
- **.process_message()** (4 connections) — `backend/app/agents/orchestrator.py`
- **search_policies()** (4 connections) — `backend/app/api/v1/policy.py`
- *... and 34 more nodes in this community*

## Relationships

- [timesheets.py](timesheets.py.md) (27 shared connections)
- [User](User.md) (19 shared connections)
- [leaves.py](leaves.py.md) (12 shared connections)
- [UserRole](UserRole.md) (11 shared connections)
- [models/__init__.py](models-__init__.py.md) (7 shared connections)
- [security.py](security.py.md) (4 shared connections)
- [get_llm_provider](get_llm_provider.md) (4 shared connections)
- [main.py](main.py.md) (3 shared connections)
- [test_api_endpoints.py](test_api_endpoints.py.md) (1 shared connections)

## Source Files

- `backend/app/agents/leave_agent.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/agents/policy_agent.py`
- `backend/app/api/v1/agents.py`
- `backend/app/api/v1/policy.py`
- `backend/app/schemas/agent.py`
- `backend/app/services/graph_rag_service.py`
- `promptfoo/promptfoo_provider.py`

## Audit Trail

- EXTRACTED: 161 (93%)
- INFERRED: 13 (7%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*