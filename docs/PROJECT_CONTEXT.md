# Intelera PeopleOps — Master Conversation & Architecture Context

> **Instructions for Any Future AI / Pair Programmer:**
> Read this document first when starting a new conversation. It represents the complete source of truth regarding the codebase architecture, design choices, implementation details, past refactorings, security audits, and operating instructions for the **PeopleOps Enterprise Multi-Agent Platform**.

---

## 1. Project Overview & Tech Stack

* **Project Name**: PeopleOps Enterprise Multi-Agent HR Platform
* **Repository Root**: `C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops`
* **Remote Git**: `https://github.com/Ares19v/people-ops.git` (branch: `main`)
* **Backend**:
  * **Framework**: FastAPI (Python 3.11) with Uvicorn
  * **Virtual Environment**: `backend/.venv/Scripts/python.exe`
  * **Database**: SQLite (`backend/hr_platform.db`) via SQLAlchemy Async (`aiosqlite`) + PostgreSQL 16 ready with `chat_sessions` table
  * **Agent Framework**: Google Agent Development Kit (**Google ADK** / [`adk-python`](https://github.com/google/adk-python) / [adk.dev](https://adk.dev/agents/llm-agents/))
  * **LLM Provider Bridge**: `backend/app/core/llm_bridge.py` (failover support across OpenAI `gpt-4o` via LiteLLM, Google Gemini 2.5 `gemini-2.5-flash`, and local Mock fallback)
  * **Safety & Guardrails**: NVIDIA NeMo Guardrails + OWASP LLM01 boundary heuristics
  * **Observability & Prompt Management**: Langfuse Cloud (OpenTelemetry hierarchical waterfall traces + decoupled prompts)
* **Frontend**:
  * **Framework**: React 18 + Vite + TypeScript + Tailwind CSS
  * **Dev Server**: `http://localhost:5173`
  * **Backend API**: `http://127.0.0.1:8000`

---

## 2. Directory & File Map (Decoupled & Clean Architecture)

The codebase strictly enforces **one file per agent** and **one file per tool in domain folders**, with a single unified root orchestrator:

```
people-ops/
├── docs/
│   └── PROJECT_CONTEXT.md            # THIS FILE (Master Project Context & Source of Truth)
│
├── docker/                           # Centralized Docker Configuration
│   ├── Dockerfile.backend            # Production Python backend container
│   └── Dockerfile.frontend           # Production React/Nginx frontend container
│
├── scripts/                          # Root Utilities & Tunnels
│   ├── start_ngrok.bat               # Starts Ngrok public tunnel
│   └── set_authtoken.bat             # Configures Ngrok auth token
│
├── backend/
│   ├── .env                          # SINGLE authoritative environment file (DO NOT create duplicates)
│   ├── scripts/                      # Operational, Diagnostic & Benchmark Scripts
│   │   ├── run_golden_dataset_benchmark.py  # 25-Prompt Golden Evaluation Battery
│   │   ├── test_full_suite.py        # 10-Prompt Full Diagnostic Suite
│   │   ├── test_all_services_and_prompts.py # Comprehensive System Tests
│   │   ├── populate_langfuse_sessions_and_users.py # Langfuse Cloud Seeder
│   │   ├── sync_db_mirror.py         # PostgreSQL -> SQLite Mirror Syncer
│   │   ├── seed_neo4j_graph.py       # Neo4j Knowledge Graph Seeder
│   │   ├── push_prompt.py            # Langfuse Prompt Pusher
│   │   └── generate_architecture_pdf.py # Technical Architecture PDF Generator
│   ├── app/
│   │   ├── agents/                   # Agent Layer (One file per domain agent)
│   │   │   ├── orchestrator.py       # Canonical Unified Orchestrator: hr_root_orchestrator (ADK) + LLMRootOrchestratorAgent (Pipeline)
│   │   │   ├── leave_agent.py        # Leave Management Agent (Google ADK Agent + tool handlers)
│   │   │   ├── timesheet_agent.py    # Timesheet & Overtime Agent (Google ADK Agent + tool handlers)
│   │   │   ├── health_agent.py       # Occupational Health Agent (Google ADK Agent + tool handlers)
│   │   │   ├── policy_agent.py       # Statutory Labour Law Graph RAG Agent (Google ADK Agent + tool handlers)
│   │   │   ├── zoho_agent.py         # Zoho People HRMS Live Sync Agent (Google ADK Agent + tool handlers)
│   │   │   ├── adk_fleet.py          # Runner factory, session service & live prompt sync
│   │   │   ├── intent_router.py      # Semantic & grammatical subjectivity intent router
│   │   │   ├── statutory_critic.py   # Reflection & self-correction critic agent (Maharashtra Act)
│   │   │   └── langgraph_orchestrator.py # Comparative LangGraph StateGraph pipeline (/langgraph-chat)
│   │   │
│   │   ├── tools/                    # Tool Layer (One tool per file under domain packages)
│   │   │   ├── leave/
│   │   │   │   ├── get_leave_balances.py            # Balance ledger retrieval
│   │   │   │   ├── calculate_leave_eligibility.py   # Sufficiency & date collision checking
│   │   │   │   └── apply_leave.py                   # Formal leave application submission
│   │   │   ├── timesheet/
│   │   │   │   ├── get_timesheet_summary.py         # Logged & billable hours aggregation (uses SQLAlchemy case())
│   │   │   │   └── log_work_hours.py                # Task hours logging & 11h daily cap validation
│   │   │   ├── health/
│   │   │   │   └── get_occupational_health_guidelines.py # Sick leave & medical certificate protocol
│   │   │   ├── policy/
│   │   │   │   ├── check_statutory_compliance.py    # Indian state labour law compliance check
│   │   │   │   └── query_company_policy.py          # Graph RAG policy search
│   │   │   ├── zoho/
│   │   │   │   └── sync_zoho_leave_records.py       # Zoho People REST v2 live sync
│   │   │   └── hr_tools.py                          # Re-export compatibility barrel file
│   │   │
│   │   ├── compliance/
│   │   │   ├── phi_engine.py         # Reversible DPDP Act 2023 TokenVault ([NAME_1], [AADHAAR_1])
│   │   │   └── statutory_rules.py    # Hardcoded legal invariants (Maharashtra Shops & Estab. 2017)
│   │   ├── guardrails/
│   │   │   ├── guardrails_manager.py # NeMo Guardrails, injection defense & acute emergency triage
│   │   │   └── config/               # rails.co and config.yml
│   │   ├── memory/
│   │   │   └── conversation_memory.py# Multi-turn conversational memory with DB checkpoints
│   │   ├── observability/
│   │   │   └── langsmith_tracer.py   # Langfuse v4 OpenTelemetry hierarchical waterfall tracer
│   │   ├── evaluations/
│   │   │   └── grid_evaluator.py     # Prompt evaluation matrix (EVAL-01 to EVAL-05)
│   │   ├── services/
│   │   │   ├── langfuse_prompt_service.py # Decoupled prompt manager with webhook invalidation
│   │   │   ├── leave_service.py      # Core leave calculations & DB ledger
│   │   │   ├── timesheet_service.py  # Hours aggregation & CSV reporting
│   │   │   ├── graph_rag_service.py  # Neo4j & statutory knowledge graph query service
│   │   │   └── zoho_service.py       # Zoho People REST API v2 client
│   │   ├── api/v1/                   # FastAPI endpoints (agents, auth, leaves, timesheets, etc.)
│   │   ├── models/                   # SQLAlchemy ORM models (user, leave, timesheet, chat_session)
│   │   ├── schemas/                  # Pydantic schemas (AgentChatRequest, AgentChatResponse, etc.)
│   │   ├── core/
│   │   │   ├── config.py             # Settings, env loader, production validator
│   │   │   ├── database.py           # AsyncSessionLocal, engine, db_session
│   │   │   ├── llm_bridge.py         # Failover probe for OpenAI / Gemini / Mock
│   │   │   ├── logging_config.py     # Structlog, AgentLogger, log_tool_call
│   │   │   └── security.py           # JWT, password hashing, mask_all_pii
│   │   └── main.py                   # FastAPI application factory
│   │
│   ├── data/
│   │   ├── prompts_registry.json     # Decoupled prompts (offline fallback)
│   │   ├── conversation_sessions.json# Local memory snapshot backup
│   │   ├── zoho_mock_fixtures.json   # Zoho People offline fixtures
│   │   ├── maharashtra_labour_law.json
│   │   └── company_policy_2026.json
│   ├── reports/
│   │   └── benchmark_60_results.json # 60-scenario automated benchmark output (100% pass)
│   └── tests/
│       ├── run_60_scenario_benchmark.py # Automated 60-scenario benchmark
│       ├── test_security_audit.py    # Defensive security regression suite
│       └── test_*.py                 # Unit & integration test suites (49 tests, all passing)
│
├── frontend/
│   ├── src/
│   │   ├── pages/                    # Portals (Leave, Timesheet, Policy, Onboarding, Reports, Dashboard)
│   │   ├── components/               # AgentChatDrawer, AgentFlowCircuit, DemoModeToggleBar, FeatureExplainerModal
│   │   ├── context/                  # DemoModeContext
│   │   ├── data/                     # featureExplainers
│   │   └── api.ts                    # Backend client integration
│
└── docs/
    ├── architecture.md               # Architecture documentation & diagrams
    └── images/                       # UI & trace diagrams
```

---

## 3. Langfuse Cloud & Hierarchical Waterfall Tracing

### Dashboard Details
* **Base URL**: `https://us.cloud.langfuse.com`
* **Project ID**: `cmuz8zyf5003had0e7nxd8ohm`
* **Traces Dashboard**: `https://us.cloud.langfuse.com/project/cmuz8zyf5003had0e7nxd8ohm/traces`
* **Public Key**: `pk-lf-e4ae49c6-7ecf-44d8-9214-314d3319f1cf`
* **Secret Key**: `sk-lf-8db8857c-956a-40c6-b264-d21cbeadef08`

### OpenTelemetry Waterfall Hierarchy
Every incoming query to `orchestrator.process_message()` triggers an OpenTelemetry nested observation tree rendered as a waterfall in Langfuse:

```text
TOTAL ROUND-TRIP (as_type="chain")
│
├── Input Guardrails (as_type="guardrail")
│     └── Evaluates DPDP 2023 TokenVault redaction + NeMo adversarial injection / emergency triage
│
├── Orchestrator (as_type="agent")
│   ├── Subagent ({subagent_name}) (as_type="agent")
│   │     └── Google ADK Agent turn or semantic intent resolution
│   │
│   └── Tool Selection (as_type="chain")
│       └── Tool Execution ({tool_name}) (as_type="tool")
│             └── Concrete database query or external API sync (get_leave_balances, etc.)
│
└── Output Guardrails (as_type="guardrail")
      └── Statutory Critic reflection loop + Role-based reversible de-redaction + clean formatting sanitization
```

### Privacy & Cloud Telemetry Rule
All data sent to Langfuse spans passes through `mask_all_pii()` in `backend/app/observability/langsmith_tracer.py`. Zero unmasked Aadhaar, Phone, PAN, or employee secrets ever leave the machine.

---

## 4. Multi-Turn Memory & Data Persistence

1. **Working Context Window**:
   - In-memory sliding window retained in `conversation_memory.py`.
   - `get_formatted_history(session_id, limit=4)` injects prior turns into the subagent prompt context.
2. **PostgreSQL / SQLite Database Checkpointing**:
   - Persisted via `chat_sessions` table (`backend/app/models/chat_session.py`).
   - Every user turn and sanitized assistant reply is committed with `session_id`, `user_id`, `role`, `content`, `timestamp`, and `metadata`.
   - `conversation_memory.load_session_from_db(db, session_id)` reloads past conversation state on server restart.
3. **Local JSON Backup**:
   - `backend/data/conversation_sessions.json` acts as an offline snapshot backup.
4. **Conversation Reset Behavior**:
   - Generating a new `session_id` or clearing the active session starts a clean slate for the LLM while preserving past historical records in the database.

---

## 5. Decoupled Prompt Management (Langfuse)

* **Zero Hardcoded Prompts**:
  All agent system instructions are dynamically loaded via `langfuse_prompt_service.get_prompt("<prompt-id>")`.
* **Prompt Registry Keys**:
  - `peopleops-root-orchestrator`: Root Orchestrator instructions.
  - `leave-subagent`: Leave policies, balances, accruals, application rules.
  - `timesheet-subagent`: Overtime rules, 11-hour daily caps, billable hour tracking.
  - `health-subagent`: Occupational health protocols, sick leave medical certificate thresholds.
  - `policy-rag-subagent`: Indian statutory labour law & graph RAG policies.
  - `zoho-subagent`: Zoho People HRMS bi-directional sync rules.
* **Hot Reloading Without Redeploying**:
  - When prompts are updated on Langfuse Cloud, a webhook hits `POST /api/v1/agents/prompts/webhook` (with `X-Webhook-Secret`).
  - It invalidates the in-memory cache and triggers `sync_agent_instructions()` across the ADK fleet immediately.
  - Fallback: Local cache is stored in `backend/data/prompts_registry.json`.

---

## 6. Indian Statutory Labour Law Compliance Engine

All agents strictly enforce statutory invariants (Maharashtra Shops & Establishments Act, 2017):

* **Section 13**: Standard work hours (max 9 hours/day, 48 hours/week).
* **Section 14**: Overtime compensation mandated at **2.0x (double ordinary rate)**; daily working cap strictly capped at **11 hours/day**; quarterly overtime capped at **125 hours**.
* **Section 15**: Mandatory rest intervals of at least **30 minutes after 5 continuous hours of work**.
* **Section 18**:
  * **Earned Leave (EL)**: Statutory min 12, company provides 18/yr. Maximum accumulation / carry-forward capped at **45 days**.
  * **Casual Leave (CL)**: 8 days/yr, non-cumulative, lapses December 31, max 3 consecutive days.
  * **Sick Leave (SL)**: 12 days/yr. Any absence **exceeding 2 consecutive days** mandates a registered medical practitioner's certificate.
* **Notice Periods**:
  * >1 year service: **30 days written notice** or wages in lieu.
  * <1 year service: **15 days written notice**.
* **Bereavement Leave**: 3 to 5 days compassionate paid leave for immediate family.

---

## 7. Critical Technical Gotchas for Future Pair Programmers

> [!CAUTION]
> Keep these exact engineering rules in mind when making code modifications:

1. **Single `.env` File**:
   - Maintain ONLY `backend/.env`. Never create multiple `.env` files in other directories.
2. **Google ADK Type Annotations**:
   - **DO NOT** use `from __future__ import annotations` in `backend/app/tools/*`.
   - Google ADK uses runtime type inspection (`func.__annotations__`) to generate JSON schemas for Gemini/LiteLLM tools. `from __future__ import annotations` converts type objects into string literals (`'str'`), which breaks ADK schema parsing.
3. **SQLAlchemy 2.0 Async `case()`**:
   - In `backend/app/tools/timesheet/get_timesheet_summary.py` and other tool files, always use `from sqlalchemy import case; case((...), else_=0.0)` instead of `func.case(...)`.
4. **Langfuse v4 Observation Context**:
   - In Langfuse SDK v4, legacy `client.trace(...)` is removed. Always use `with client.start_as_current_observation(...) as obs:` with context managers.
   - Always call `langsmith_tracer.flush()` after request completion so observations are pushed to the cloud without delay.
5. **FastAPI & React Ports**:
   - Backend: Port `8000` (`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`)
   - Frontend: Port `5173` (`npm run dev`)

---

## 8. Test Suites & Benchmarks

All test suites currently pass at **100%**:

| Suite | Command | Status |
| :--- | :--- | :--- |
| **Full Pytest Suite** | `pytest backend/tests -v` | **49 / 49 Passed** |
| **60-Scenario Comprehensive Benchmark** | `python backend/tests/run_60_scenario_benchmark.py` | **60 / 60 Passed (100%)** |
| **Defensive Security Audit Suite** | `python backend/tests/test_security_audit.py` | **8 / 8 Passed (100%)** |

---

## 9. Launching & Verifying the Application

### Launch Backend
```powershell
cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\backend"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Launch Frontend
```powershell
cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\frontend"
npm run dev
```

### Verify Observability in Browser
1. Open `http://localhost:5173` and submit any chat query.
2. Open `https://us.cloud.langfuse.com/project/cmuz8zyf5003had0e7nxd8ohm/traces` to view the live waterfall trace.
