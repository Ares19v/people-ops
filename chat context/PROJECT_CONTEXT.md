# Intelera PeopleOps — Master Conversation & Architecture Context

> **Instructions for Any Future AI / Pair Programmer:**
> Read this document first when starting a new conversation. It represents the complete source of truth regarding the codebase architecture, design choices, implementation details, past refactorings, security audits, and operating instructions for the **PeopleOps Enterprise Multi-Agent Platform**.

---

## 1. Project Overview & Tech Stack

* **Project Name**: PeopleOps Enterprise Multi-Agent HR Platform
* **Repository Root**: `C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops`
* **Backend**:
  * **Framework**: FastAPI (Python 3.11) with Uvicorn
  * **Virtual Environment**: `backend/.venv/Scripts/python.exe`
  * **Database**: SQLite (`backend/hr_platform.db`) via SQLAlchemy Async (`aiosqlite`) + PostgreSQL 16 ready
  * **Agent Framework**: Google Agent Development Kit (**Google ADK** / [`adk-python`](https://github.com/google/adk-python) / [adk.dev](https://adk.dev/agents/llm-agents/))
  * **Safety & Guardrails**: NVIDIA NeMo Guardrails + OWASP LLM01 boundary heuristics
  * **Observability & Prompt Management**: Langfuse Cloud + LangSmith
* **Frontend**:
  * **Framework**: React 18 + Vite + TypeScript + Tailwind CSS
  * **Port**: `http://localhost:5173`
  * **Backend Port**: `http://127.0.0.1:8000`

---

## 2. Directory & File Map (Decoupled Architecture)

The codebase strictly enforces **one file per agent** and **one file per tool in domain folders**:

```
people-ops/
├── chat context/
│   └── PROJECT_CONTEXT.md            # THIS FILE (Master Project Context)
│
├── backend/
│   ├── app/
│   │   ├── agents/                   # Agent Layer (One file per agent)
│   │   │   ├── root_orchestrator.py  # Google ADK Root LLM Agent declaration (Agent class)
│   │   │   ├── root_llm_agent.py     # Enterprise Runtime Execution Engine (Redact -> Rails -> Gather -> Critic)
│   │   │   ├── leave_agent.py        # Leave Management Agent (Google ADK Agent + tool handlers)
│   │   │   ├── timesheet_agent.py    # Timesheet & Overtime Agent (Google ADK Agent + tool handlers)
│   │   │   ├── health_agent.py       # Occupational Health Agent (Google ADK Agent + tool handlers)
│   │   │   ├── policy_agent.py       # Statutory Labour Law Graph RAG Agent (Google ADK Agent + tool handlers)
│   │   │   ├── zoho_agent.py         # Zoho People HRMS Live Sync Agent (Google ADK Agent + tool handlers)
│   │   │   ├── adk_fleet.py          # Runner factory, session service & live prompt sync
│   │   │   ├── intent_router.py      # Semantic & grammatical subjectivity intent router
│   │   │   ├── statutory_critic.py   # Reflection & self-correction critic agent
│   │   │   ├── langgraph_orchestrator.py # Comparative LangGraph StateGraph pipeline (/langgraph-chat)
│   │   │   └── orchestrator.py       # Backward-compatible API facade (forwards to root_llm_agent)
│   │   │
│   │   ├── tools/                    # Tool Layer (One file per tool in domain folders)
│   │   │   ├── leave/
│   │   │   │   ├── get_leave_balances.py            # Balance ledger retrieval
│   │   │   │   ├── calculate_leave_eligibility.py   # Sufficiency & date collision checking
│   │   │   │   └── apply_leave.py                   # Formal leave application submission
│   │   │   ├── timesheet/
│   │   │   │   ├── get_timesheet_summary.py         # Logged & billable hours aggregation
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
│   │   │   └── phi_engine.py         # Reversible DPDP Act 2023 TokenVault ([AADHAAR_1])
│   │   ├── guardrails/
│   │   │   ├── guardrails_manager.py # NeMo Guardrails, injection defense & acute emergency triage
│   │   │   └── config/               # rails.co and config.yml
│   │   ├── memory/
│   │   │   └── conversation_memory.py# Multi-turn conversational memory with DB checkpoints
│   │   ├── observability/
│   │   │   └── langsmith_tracer.py   # Token usage, latency, guardrail tracing for LangSmith/Langfuse
│   │   ├── evaluations/
│   │   │   └── grid_evaluator.py     # Prompt evaluation matrix (EVAL-01 to EVAL-05)
│   │   ├── services/
│   │   │   ├── langfuse_prompt_service.py # Decoupled prompt manager with webhook invalidation
│   │   │   ├── leave_service.py      # Core leave calculations & DB ledger
│   │   │   ├── timesheet_service.py  # Hours aggregation & CSV reporting
│   │   │   ├── graph_rag_service.py  # Neo4j & statutory knowledge graph query service
│   │   │   └── zoho_service.py       # Zoho People REST API v2 client
│   │   ├── api/v1/                   # FastAPI endpoints (agents, auth, leaves, timesheets, etc.)
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   ├── schemas/                  # Pydantic schemas
│   │   └── main.py                   # FastAPI application factory
│   │
│   ├── data/
│   │   ├── prompts_registry.json     # Decoupled prompts (offline fallback)
│   │   ├── maharashtra_labour_law.json
│   │   └── company_policy_2026.json
│   ├── reports/
│   │   └── benchmark_60_results.json # 60-scenario automated benchmark output (100% pass)
│   └── tests/
│       ├── run_60_scenario_benchmark.py # Automated 60-scenario benchmark
│       ├── test_security_audit.py    # Defensive security regression suite
│       └── test_*.py                 # Unit & integration test suites
│
├── frontend/
│   ├── src/
│   │   ├── pages/                    # Portals (Leave, Timesheet, Policy, Onboarding, Reports)
│   │   ├── components/               # AgentChatDrawer, AgentFlowCircuit, Navbar
│   │   └── api.ts                    # Backend client integration
│
└── docs/
    └── architecture.md               # Architecture documentation & diagrams
```

---

## 3. Decoupled Prompt Management (Langfuse Integration)

* **Zero Hardcoded Prompts in Code**:
  All string literals have been removed from agent Python files.
  Every agent initializes its instruction dynamically via:
  ```python
  instruction = langfuse_prompt_service.get_prompt("<prompt-key>")
  ```
* **Prompt Source Hierarchy**:
  1. **Langfuse Cloud (Primary)**: When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are provided in `.env`, prompts are pulled directly from Langfuse Cloud via the official Langfuse SDK.
  2. **Webhook Invalidation**: `POST /api/v1/agents/prompts/webhook` (protected by `X-Webhook-Secret`) receives Langfuse prompt publication events, flushes the in-memory cache, and triggers `sync_agent_instructions()` to hot-reload agents without restarting the server.
  3. **Offline Fallback**: [`backend/data/prompts_registry.json`](file:///C:/Users/Devansh%20Tyagi/Desktop/Intelera/people-ops/backend/data/prompts_registry.json) serves as the local cache fallback when offline or in test environments.
* **Inspect Prompts**:
  Admins can inspect active prompt templates, versions, labels, and sources via `GET /api/v1/agents/prompts`.

---

## 4. Multi-Agent Flow & Execution Pipeline

Incoming messages to `/api/v1/agents/chat` execute through this deterministic pipeline:

```mermaid
sequenceDiagram
    autonumber
    actor User as Employee / HR
    participant Compliance as ComplianceEngine (TokenVault)
    participant Rails as GuardrailsManager (NeMo)
    participant Memory as ConversationMemory
    participant Router as SemanticIntentRouter
    participant Root as Root LLM Agent
    participant Critic as StatutoryCriticAgent
    participant Tracer as Observability Tracer

    User->>Compliance: 1. Raw user message
    Compliance->>Rails: 2. Redact PII into ephemeral tokens ([NAME_1], [AADHAAR_1])
    Rails->>Memory: 3. Verify OWASP LLM01, BOLA & acute emergency triage
    Memory->>Router: 4. Load multi-turn history from DB
    Router->>Root: 5. Classify intent via grammatical subjectivity & semantics
    Root->>Root: 6. Execute domain subagent tools concurrently (asyncio.gather)
    Root->>Critic: 7. Validate statutory claims (Maharashtra Act Sec 13, 14, 15, 18)
    Critic->>Rails: 8. Correct errors, append statutory notes
    Rails->>Compliance: 9. Run output safety check & append disclaimers
    Compliance->>Tracer: 10. De-redact tokens for authorized user roles
    Tracer-->>User: 11. Log latency, tokens & safety score; return human response
```

---

## 5. Security & Guardrails Architecture

The platform has undergone rigorous adversarial red-teaming and defensive hardening:

1. **WebSocket Authentication Enforcement (CWE-306)**:
   Anonymous connections are rejected immediately with close code `4001`. No fallback impersonation is permitted.
2. **File Upload Path Traversal Defense (CWE-22)**:
   Filenames sanitized using `os.path.basename` and regex stripping of traversal sequences (`../`).
3. **Webhook Security**:
   Webhook endpoints require `X-Webhook-Secret` verification (returns HTTP 401 on unauthorized calls).
4. **RBAC & Prompt Disclosure Prevention (CWE-200)**:
   Endpoints `/prompts` and `/prompts/reload` require `HR_MANAGER` or `ADMIN` roles. Regular employees receive HTTP 403.
5. **CORS Hardening**:
   Restricted to explicit trusted origins (`http://localhost:5173`, `http://127.0.0.1:5173`).
6. **OWASP LLM01 Prompt Injection & Jailbreak Defense**:
   NeMo guardrails intercept and block adversarial attempts (`"ignore all rules"`, `"dump passwords"`, `"DAN mode"`).
7. **Acute Emergency Clinical Triage**:
   Red-flag symptoms (chest pain, breathing distress, stroke) trigger an immediate redirect to emergency services (112 / 911).

---

## 6. Indian Statutory Labour Law Compliance Engine

The agents are rigorously aligned with Indian state statutory mandates:

* **Maharashtra Shops & Establishments (Regulation of Employment and Conditions of Service) Act, 2017**:
  * **Section 13**: Standard work hours (max 9 hours/day, 48 hours/week).
  * **Section 14**: Overtime compensation mandated at **twice the ordinary rate (2.0x)**; daily working cap strictly capped at **11 hours/day**; quarterly overtime capped at **125 hours**.
  * **Section 15**: Mandatory rest intervals of at least **30 minutes after 5 continuous hours of work**.
  * **Section 18**:
    * **Earned Leave (EL)**: 1 day per 20 days worked (statutory min 12, company provides 18/yr). Maximum accumulation / carry-forward capped at **45 days**.
    * **Casual Leave (CL)**: 8 days/yr, non-cumulative, lapses December 31, max 3 consecutive days.
    * **Sick Leave (SL)**: 12 days/yr. Any absence **exceeding 2 consecutive days** mandates a registered medical practitioner's certificate.
* **Notice Periods**:
  * >1 year of service: **30 days written notice** or wages in lieu.
  * <1 year of service: **15 days written notice**.
* **Bereavement Leave**: 3 to 5 days compassionate paid leave for immediate family.

---

## 7. Test Suites & Benchmarks

All test suites currently pass at **100%**:

| Suite | Runner Command | Result |
| :--- | :--- | :--- |
| **Full Pytest Suite** | `pytest tests/` | **49 / 49 Passed** |
| **60-Scenario Comprehensive Benchmark** | `python tests/run_60_scenario_benchmark.py` | **60 / 60 Passed (100.0%)** |
| **Defensive Security Audit Suite** | `python tests/test_security_audit.py` | **8 / 8 Passed (100%)** |

Benchmark results are stored in [`backend/reports/benchmark_60_results.json`](file:///C:/Users/Devansh%20Tyagi/Desktop/Intelera/people-ops/backend/reports/benchmark_60_results.json).

---

## 8. Operating & Launch Instructions

### Fast Launch (Both Daemons)

1. **Backend**:
   ```powershell
   cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\backend"
   & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. **Frontend**:
   ```powershell
   cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\frontend"
   npm run dev
   ```

### Default Pre-Seeded Users

* **Employee**: `Aarav Sharma` (ID: `67dc5027-a6d7-4505-a3aa-f45d184cca49`, Role: `EMPLOYEE`)
* **HR Associate**: `Priya Patel` (Role: `HR_ASSOCIATE`)
* **HR Manager**: `Vikram Malhotra` (Role: `HR_MANAGER`)
* **Admin**: `Devansh Tyagi` (`admin@intelera.corp`, Role: `ADMIN`)
* **Mock Login Endpoint**: `POST /api/v1/auth/mock-login` with payload `{"role": "EMPLOYEE"}` or `{"role": "ADMIN"}` returns a valid JWT.

### Key Environment Flags (`backend/.env`)

```ini
ENVIRONMENT=development
MOCK_SSO_ENABLED=true
MOCK_LLM_ENABLED=true     # Set to false and provide GEMINI_API_KEY for live Google Gemini 2.5
# LANGFUSE_PUBLIC_KEY="pk-lf-..."
# LANGFUSE_SECRET_KEY="sk-lf-..."
# LANGFUSE_HOST="https://cloud.langfuse.com"
```
