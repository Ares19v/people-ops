# Intelera PeopleOps — Master Conversation & Architecture Context

> **Instructions for Any Future AI / Pair Programmer:**
> Read this document first when starting a new conversation. It represents the complete source of truth regarding the codebase architecture, design choices, implementation details, past refactorings, security audits, Render PostgreSQL database views, Neo4j Graph RAG, Zoho People integration, NVIDIA NeMo Guardrails, and Langfuse Cloud Observability Suite for the **PeopleOps Enterprise Multi-Agent Platform**.

---

## 1. Project Overview & Tech Stack

* **Project Name**: PeopleOps Enterprise Multi-Agent HR Platform
* **Repository Root**: `C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops`
* **Remote Git**: `https://github.com/Ares19v/people-ops.git` (branch: `main`)
* **Operating System**: Windows (PowerShell / `pwsh`)
* **Default Project Location**: `C:\Users\Devansh Tyagi\Desktop\Code\Antigravity_def\<project-name>` (or `C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops`)

### Core Architecture Components
1. **Backend**:
   - **Framework**: FastAPI (Python 3.11) with Uvicorn
   - **Virtual Environment**: `C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\backend\.venv\Scripts\python.exe`
   - **Relational Database**: Render Managed PostgreSQL 16 (`postgresql+asyncpg://...render.com/peopleops_postgres`)
   - **Clean Database Views**: `v_employees_overview`, `v_leaves_summary`, `v_timesheets_active` (automatically initialized in `app.core.db_views`)
   - **Graph RAG**: Neo4j AuraDB (`neo4j+s://e4ab5ba2.databases.neo4j.io`) for Maharashtra Labour Laws & Company Policy Knowledge Graphs
   - **Multi-Agent Framework**: Google Agent Development Kit (**Google ADK** / `adk-python` / `adk.dev`)
   - **LLM Provider Bridge**: `backend/app/core/llm_bridge.py` supporting OpenAI `gpt-4o-mini` / `gpt-4o` via LiteLLM with fallback to Google Gemini 2.5 (`gemini-2.5-flash`)
   - **Safety & Guardrails**: NVIDIA NeMo Guardrails (`rails.co` & `config.yml`) + DPDP Act 2023 TokenVault reversible PII scrubbing + OWASP LLM01 injection defense
   - **Observability & Prompt Registry**: Langfuse Cloud (`https://us.cloud.langfuse.com`) with OpenTelemetry hierarchical waterfall tracing, prompt hot-reloading, 5 registered LLM-as-a-judge evaluators, 5 automated evaluation rules, and live alert webhook automation.

2. **Frontend**:
   - **Framework**: React 19 + Vite + TypeScript + Tailwind CSS + Lucide Icons
   - **Styling**: Formal Olixer dark theme (`#0b1329`)
   - **Dev Server**: `http://localhost:5173`
   - **Proxy**: `/api` routes forwarded directly to `http://127.0.0.1:8000`

3. **Public Tunnel**:
   - **Ngrok Static Domain**: `https://upcountry-scarcity-hatchery.ngrok-free.dev` forwarding to `http://localhost:5173`

---

## 2. Directory & File Map (Clean Decoupled Architecture)

```
people-ops/
├── docs/
│   ├── chat_context/
│   │   └── PROJECT_CONTEXT.md        # MASTER SOURCE OF TRUTH (Always read first)
│   ├── PROJECT_CONTEXT.md            # Mirror copy
│   └── architecture.md               # Architecture diagrams & design specs
│
├── backend/
│   ├── .env                          # SINGLE authoritative environment file
│   ├── app/
│   │   ├── agents/                   # Agent Fleet (One agent per file)
│   │   │   ├── orchestrator.py       # LLMRootOrchestratorAgent & ADK Root Fleet Orchestrator
│   │   │   ├── leave_agent.py        # Leave Management Agent (balances, eligibility, applications)
│   │   │   ├── timesheet_agent.py    # Timesheet & Overtime Agent (daily 11h caps, overtime calculations)
│   │   │   ├── health_agent.py       # Occupational Health Agent (sick leave protocols, medical certs)
│   │   │   ├── policy_agent.py       # Statutory Labour Law Graph RAG Agent
│   │   │   ├── zoho_agent.py         # Zoho People HRMS Live Sync Agent
│   │   │   ├── adk_fleet.py          # Runner factory, session manager & prompt synchronization
│   │   │   ├── intent_router.py      # Semantic & grammatical intent classifier
│   │   │   ├── statutory_critic.py   # Reflection & self-correction critic agent (Maharashtra Act)
│   │   │   └── langgraph_orchestrator.py # Comparative LangGraph StateGraph pipeline
│   │   │
│   │   ├── tools/                    # Tool Layer (One tool per file under domain packages)
│   │   │   ├── leave/                # get_leave_balances.py, calculate_leave_eligibility.py, apply_leave.py
│   │   │   ├── timesheet/            # get_timesheet_summary.py, log_work_hours.py
│   │   │   ├── health/               # get_occupational_health_guidelines.py
│   │   │   ├── policy/               # check_statutory_compliance.py, query_company_policy.py
│   │   │   ├── zoho/                 # sync_zoho_leave_records.py
│   │   │   └── hr_tools.py           # Barrel export
│   │   │
│   │   ├── compliance/
│   │   │   ├── phi_engine.py         # Reversible DPDP Act 2023 TokenVault ([NAME_1], [AADHAAR_1])
│   │   │   └── statutory_rules.py    # Hardcoded legal invariants (Maharashtra Shops & Estab. 2017)
│   │   ├── guardrails/
│   │   │   ├── guardrails_manager.py # NeMo Guardrails, injection defense & acute emergency triage
│   │   │   └── config/               # rails.co and config.yml
│   │   ├── memory/
│   │   │   └── conversation_memory.py# Multi-turn memory with database checkpoints
│   │   ├── observability/
│   │   │   ├── langsmith_tracer.py   # Langfuse v4 OpenTelemetry waterfall tracer & session propagator
│   │   │   └── evaluators_and_alerts.py # 5 Evaluators, 4 Alert Rules & Live Alert Manager
│   │   ├── services/
│   │   │   ├── dataset_sync_service.py # 25-Prompt Golden Dataset benchmark sync
│   │   │   ├── langfuse_prompt_service.py # Decoupled prompt manager with live cache invalidation
│   │   │   ├── graph_rag_service.py  # Neo4j Graph RAG knowledge graph engine
│   │   │   ├── zoho_service.py       # Zoho People REST v2 API integration
│   │   │   ├── leave_service.py      # Leave ledger calculation logic
│   │   │   └── timesheet_service.py  # Timesheet calculation logic
│   │   ├── api/v1/                   # FastAPI Endpoints
│   │   │   ├── agents.py             # Chat, streaming, prompt sync, observability endpoints & alert webhook
│   │   │   ├── auth.py               # JWT authentication (/auth/login)
│   │   │   ├── health.py             # Health status & system readiness
│   │   │   ├── leaves.py             # Leave application & balance APIs
│   │   │   ├── timesheets.py         # Timesheet entry & approval APIs
│   │   │   ├── reports.py            # Departmental analytics & DB inspector views
│   │   │   ├── policy.py             # Policy search endpoints
│   │   │   └── onboarding.py         # Employee onboarding workflows
│   │   ├── models/                   # SQLAlchemy ORM models (User, LeaveRecord, TimesheetEntry, ChatSession)
│   │   ├── core/
│   │   │   ├── config.py             # App settings & pydantic environment loader
│   │   │   ├── database.py           # Async engine & sessionmaker (Render PostgreSQL)
│   │   │   ├── db_views.py           # PostgreSQL database views (v_employees_overview, etc.)
│   │   │   └── security.py           # Password hashing, JWT token creation, PII scrubber
│   │   └── main.py                   # FastAPI Application Factory & Lifespan Hooks
│   │
│   └── data/
│       ├── prompts_registry.json     # Decoupled prompts local backup
│       ├── golden_dataset_25.json    # 25-Prompt Golden Benchmark test cases
│       └── company_policy_2026.json  # Enterprise policy handbook
│
└── frontend/
    ├── src/
    │   ├── pages/                    # Portal views (Dashboard, Leave, Timesheet, Policy, Onboarding, Observability)
    │   ├── components/               # AgentChatDrawer, AgentFlowCircuit, FeatureExplainerModal
    │   ├── api.ts                    # Axios / Fetch client calling /api/v1
    │   └── main.tsx                  # App entry point
    └── vite.config.ts                # Vite config with /api proxy to localhost:8000
```

---

## 3. Langfuse Cloud Observability & Prompt Management

### Credentials & Project Configuration
* **Dashboard Base URL**: `https://us.cloud.langfuse.com`
* **Public Key**: `pk-lf-106c7f65-93af-401e-b5b5-3e68742d926c`
* **Secret Key**: `sk-lf-d83aaacf-94dd-45e4-8f3e-71e0ac0ff249`
* **Webhook Secret**: `lf-whsec_0a07efcdb14e85bd67251e6b6d6a672bcbf72cfc94777a16a530e59916d150a9`

### Complete Tab Coverage in Langfuse Cloud
1. **`Tracing` (Waterfall View)**:
   - Full round-trip trace hierarchy: `Root Request` $\rightarrow$ `Input Guardrails` $\rightarrow$ `LLM Root Orchestrator` $\rightarrow$ `Subagent Turn` $\rightarrow$ `Tool Selection & Execution` $\rightarrow$ `Output Guardrails`.
   - Displays **Total Latency** (e.g., `1.53s`), **Total Cost** (e.g., `$0.00124`), and **Token Usage** (input/output) on the root span.
   - PII is scrubbed before leaving the host machine via `mask_all_pii()`.

2. **`Sessions` Tab**:
   - Multi-turn conversation threads tracked with `session_id` and user attribution (e.g., `sess_emp004_leave_and_statutory_2026`).
   - Tracks session-level token accumulation, latency progression, and LLM-Judge scores across turns.

3. **`Users` Tab**:
   - Employee profiles (`EMP-001` through `EMP-005`) tracking individual token spend, active sessions, and departmental consumption.

4. **`Evaluators` & `Rules` Tab**:
   - 5 LLM-as-a-Judge / Rule Evaluators registered in Cloud:
     * `policy_groundedness` (0.0 to 1.0)
     * `safety_and_pii_zero_leakage` (0.0 to 1.0)
     * `helpfulness_and_clarity` (0.0 to 1.0)
     * `statutory_compliance` (0.0 to 1.0)
     * `latency_sla` (0.0 to 1.0)
   - 5 Evaluation Rules running with **100% trace sampling** (`sampling=1.0`) and mapped prompt variables (`{{input}}`, `{{output}}`).

5. **`Alerts` & `Automations` Tab**:
   - Automation destination: `PeopleOps Alert Receiver`
   - Inbound Webhook: `https://upcountry-scarcity-hatchery.ngrok-free.dev/api/v1/agents/observability/alerts/webhook`
   - Monitored alerts: Traffic Volume Spikes (`> 50`), Quality Drops (`policy_groundedness < 0.8`), PII Violations (`< 1.0`), Latency SLA Breaches (`> 2000 ms`).

6. **`Datasets` (25-Prompt Golden Benchmark)**:
   - Dataset name: `peopleops-golden-benchmark-25`
   - Covers 25 rigorous test queries across Casual Leave, Earned Leave, Overtime Caps (11h), DPDP Masking, Prompt Injections, and Statutory Law.
   - Passed with **100% accuracy (25/25)**, 0 PII leaks, and 100% injection defense.

7. **`Prompts` Registry (8 Decoupled Templates)**:
   - Prompts for Orchestrator, Leave Agent, Timesheet Agent, Health Agent, Policy Agent, Zoho Agent, Onboarding Agent, and Statutory Critic.
   - Promoted prompts in the Langfuse Playground sync instantly to production with zero code deployment.

---

## 4. Database & Relational Views

The primary database is **Render PostgreSQL 16**:
* Clean views created for optimized multi-agent reasoning and HR reporting:
  - **`v_employees_overview`**: Aggregates employee profile, department, role, leave counts, and active timesheets.
  - **`v_leaves_summary`**: Summarizes approved, pending, and rejected leave applications per employee.
  - **`v_timesheets_active`**: Aggregates regular, overtime, and billable hours across current billing periods.
* Standard Human-Readable IDs & Official Corporate Emails:
  - `EMP-001`: Devansh Tyagi (`devansh.tyagi@intelera.com`) — Chief Technology Officer / Admin
  - `EMP-002`: Vikram Malhotra (`vikram.malhotra@intelera.com`) — HR Operations Manager
  - `EMP-003`: Priya Patel (`priya.patel@intelera.com`) — HR Operations Associate
  - `EMP-004`: Aarav Sharma (`aarav.sharma@intelera.com`) — Senior Software Engineer
  - `EMP-005`: Sneha Kulkarni (`sneha.kulkarni@intelera.com`) — Operations Associate
  - Leave Requests: `LV-2026-001`, `LV-2026-002`, etc.
  - Timesheet Entries: `TS-2026-001`, `TS-2026-002`, etc.

---

## 5. Indian Statutory Labour Law Compliance Rules

All agents strictly enforce statutory invariants (Maharashtra Shops & Establishments Act, 2017):
* **Section 13**: Standard work hours (max 9 hours/day, 48 hours/week).
* **Section 14**: Overtime compensation mandated at **2.0x (double ordinary rate)**; daily working cap strictly capped at **11 hours/day**; quarterly overtime capped at **125 hours**.
* **Section 15**: Mandatory rest intervals of at least **30 minutes after 5 continuous hours of work**.
* **Section 18**:
  - **Earned Leave (EL)**: Statutory minimum 12, company provides 18/yr. Maximum accumulation / carry-forward capped at **45 days**.
  - **Casual Leave (CL)**: 8 days/yr, non-cumulative, lapses December 31, max 3 consecutive days.
  - **Sick Leave (SL)**: 12 days/yr. Any absence **exceeding 2 consecutive days** mandates a registered medical practitioner's certificate.
* **Notice Periods**:
  - >1 year service: **30 days written notice** or wages in lieu.
  - <1 year service: **15 days written notice**.
* **Bereavement Leave**: 3 to 5 days compassionate paid leave for immediate family.

---

## 6. Critical Technical Gotchas & Engineering Rules

> [!CAUTION]
> Always follow these engineering rules when editing the codebase:

1. **Single Environment File**:
   - Maintain ONLY `backend/.env`. Do NOT create `.env` files in other directories.
2. **Google ADK Type Annotations**:
   - **DO NOT** use `from __future__ import annotations` in `backend/app/tools/*`. Google ADK runtime type inspection fails when type hints are turned into string literals.
3. **SQLAlchemy 2.0 Async `case()`**:
   - In tool aggregation queries, always use `from sqlalchemy import case; case((...), else_=0.0)` instead of `func.case(...)`.
4. **Langfuse v4 Observation Context & Attribution**:
   - Use `from langfuse import propagate_attributes(user_id=..., session_id=..., tags=..., metadata=...)` and context managers `with client.start_as_current_observation(...)`.
   - Pass `user_id = <official_employee_email>` (e.g., `devansh.tyagi@intelera.com`) so user spend and sessions are strictly attributed by corporate email.
   - Pass `usage_details={"input": ..., "output": ...}` and `cost_details={"total": ...}` to register token analytics and costs accurately.
5. **FastAPI Route Prefixing**:
   - Sub-routers under `app.api.v1` have their own prefixes (e.g. `agents_router` has prefix `/agents`, so endpoints mounted with `prefix="/api/v1"` become `/api/v1/agents/...`).

---

## 7. How to Run & Verify All Services

### Fast Launch Commands

```powershell
# 1. Backend FastAPI Service (Port 8000)
cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\backend"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. Frontend React / Vite Service (Port 5173)
cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\frontend"
npm run dev

# 3. Ngrok Public Webhook Tunnel
& "C:\Users\Devansh Tyagi\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 5173 --log=stdout
```

### Key Verification URLs
- **Backend Health**: `http://localhost:8000/health`
- **Frontend UI**: `http://localhost:5173`
- **Public Ngrok**: `https://upcountry-scarcity-hatchery.ngrok-free.dev`
- **Langfuse Cloud Dashboard**: `https://us.cloud.langfuse.com`
- **Langfuse Alerts Webhook**: `https://upcountry-scarcity-hatchery.ngrok-free.dev/api/v1/agents/observability/alerts/webhook`
- **Default Admin Login**: `devansh.tyagi@intelera.com` / `password123`
