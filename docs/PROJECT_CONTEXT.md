# Intelera PeopleOps — Master Conversation & Architecture Context

> **Instructions for Any Future AI / Pair Programmer:**
> Read this document first when starting a new conversation. It represents the complete, up-to-date source of truth regarding the codebase architecture, design choices, implementation details, multi-model failover, 5-session cross-conversation memory, bidirectional PostgreSQL $\leftrightarrow$ Langfuse prompt sync, TablePlus latest-first ordering, Neo4j Graph RAG, Zoho People integration, NVIDIA NeMo Guardrails, and Langfuse Cloud Observability Suite for the **PeopleOps Enterprise Multi-Agent Platform**.

---

## 1. Project Overview & Tech Stack

* **Project Name**: PeopleOps Enterprise Multi-Agent HR Platform
* **Repository Root**: `C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops`
* **Remote Git**: `https://github.com/Ares19v/people-ops.git` (branch: `main`)
* **Operating System**: Windows (PowerShell / `pwsh`)
* **Default Project Location**: `C:\Users\Devansh Tyagi\Desktop\Code\Antigravity_def\<project-name>` (or `C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops`)

### Core Architecture Components
1. **Backend**:
   - **Framework**: FastAPI (Python 3.11) with Uvicorn (`http://localhost:8000`)
   - **Python Interpreter**: `C:\Users\Devansh Tyagi\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe` with `PYTHONPATH=C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\backend\.venv\Lib\site-packages`
   - **Relational Database**: Render Managed PostgreSQL 16 (`postgresql+asyncpg://...singapore-postgres.render.com/peopleops_postgres`) with `statement_cache_size: 0` for schema/trigger resilience
   - **Clean Database Views**: `v_employees_overview`, `v_leaves_summary`, `v_timesheets_active`, `v_chat_sessions_overview`, `v_conversation_memory_window`, `v_zoho_sync_status`, `v_employee_documents`, `v_security_audit_trail` (automatically initialized in `app.core.db_views`)
   - **Latest-to-Oldest Ordering**: All 10 operational tables use sequence `latest_first_seq` and `BEFORE INSERT OR UPDATE` trigger `trg_set_latest_first_sort_order()` on `sort_order BIGINT` so both **TablePlus** and the **PeopleOps UI** display the newest / most recently updated rows at the top (`latest to oldest`).
   - **Graph RAG**: Neo4j AuraDB (`neo4j+s://e4ab5ba2.databases.neo4j.io`) + ChromaDB dense vectors + BM25 + Local NetworkX ontology graph for Maharashtra Labour Laws & Company Policy Knowledge Graphs
   - **Multi-Agent Framework**: Google Agent Development Kit (**Google ADK** / `google.adk`) with autonomous root agent `hr_root_orchestrator` and 5 specialist sub-agents
   - **LLM Provider Bridge (`backend/app/core/llm_bridge.py`)**:
     - Primary provider: **Groq via LiteLLM** (`groq/llama-3.3-70b-versatile`) with automatic multi-model failover across `groq/llama-3.3-70b-versatile` $\rightarrow$ `groq/openai/gpt-oss-20b` $\rightarrow$ `groq/llama-3.1-8b-instant` $\rightarrow$ `groq/openai/gpt-oss-120b`
     - Tracks `_exhausted_groq_models` in-process so rate-limited models are skipped immediately without retry latency
     - Offloads background rolling session summarization (`generate_summary`) to `groq/llama-3.1-8b-instant` (separate 500k TPD bucket)
     - Cross-provider fallback chain: Groq $\rightarrow$ OpenAI (`gpt-4o`) $\rightarrow$ Google Gemini (`gemini-2.5-flash` / `gemini-3.5-flash`) $\rightarrow$ `MockLLMProvider`
   - **Safety & Guardrails**: NVIDIA NeMo Guardrails (`rails.co` & `config.yml`) + DPDP Act 2023 TokenVault reversible PII scrubbing + OWASP LLM01 injection defense + Statutory Critic Agent (`statutory_critic.py`)
   - **Observability & Bidirectional Prompt Registry**: Langfuse Cloud (`https://us.cloud.langfuse.com`) with OpenTelemetry hierarchical waterfall tracing, bidirectional PostgreSQL (`agent_prompts`) $\leftrightarrow$ Langfuse Cloud live prompt sync, 5 registered LLM-as-a-judge evaluators, and live alert webhook automation.

2. **Frontend**:
   - **Framework**: React 19 + Vite + TypeScript + Tailwind CSS + Lucide Icons
   - **Styling**: Formal enterprise dark theme (`#0b1329`) with opaque formal past-conversation cards and subtle grey **Purge** button in `AgentChatDrawer.tsx`
   - **Role Switcher (`Navbar.tsx`)**: All 5 database personas selectable in the top dropdown (`Admin`, `Manager`, `HR Ops`, `Employee`, `Employee 2`)
   - **Dev Server**: `http://localhost:5173` (proxies `/api` to `http://127.0.0.1:8000`)

3. **Public Tunnel**:
   - **Ngrok Static Domain**: `https://upcountry-scarcity-hatchery.ngrok-free.dev` forwarding to `http://localhost:5173`

---

## 2. Directory & File Map (Clean Decoupled Architecture)

```
people-ops/
├── docs/
│   ├── PROJECT_CONTEXT.md            # MASTER SOURCE OF TRUTH (Always read first)
│   └── architecture.md               # Architecture diagrams & design specs
│
├── backend/
│   ├── .env                          # Environment configuration (Groq, Render PG, Neo4j, Langfuse, Zoho)
│   ├── app/
│   │   ├── agents/                   # Agent Fleet (One agent per file)
│   │   │   ├── orchestrator.py       # LLMRootOrchestratorAgent & ADK Root Fleet Orchestrator
│   │   │   ├── leave_agent.py        # Leave Management Agent (balances, eligibility, applications)
│   │   │   ├── timesheet_agent.py    # Timesheet & Overtime Agent (daily 11h caps, overtime calculations)
│   │   │   ├── health_agent.py       # Occupational Health Agent (sick leave protocols, medical certs)
│   │   │   ├── policy_agent.py       # Statutory Labour Law Graph RAG Agent
│   │   │   ├── zoho_agent.py         # Zoho People HRMS Live Sync Agent
│   │   │   ├── adk_fleet.py          # Runner factory, model failover & Langfuse prompt synchronization
│   │   │   ├── intent_router.py      # Semantic & pragmatic intent classifier (with conversational routing)
│   │   │   ├── statutory_critic.py   # Reflection & self-correction critic agent (Maharashtra Act 2017)
│   │   │   ├── llm_provider.py       # Provider abstraction & deterministic MockLLMProvider
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
│   │   │   └── statutory_rules.py    # Legal invariants (Maharashtra Shops & Estab. Act 2017)
│   │   ├── guardrails/
│   │   │   ├── guardrails_manager.py # NeMo Guardrails, injection defense & acute emergency triage
│   │   │   └── config/               # rails.co and config.yml
│   │   ├── memory/
│   │   │   └── conversation_memory.py# 5-Session Sliding Window, episodic turn recall & full DB purge
│   │   ├── observability/
│   │   │   ├── langsmith_tracer.py   # Langfuse OpenTelemetry waterfall tracer & session propagator
│   │   │   └── evaluators_and_alerts.py # 5 Evaluators, 4 Alert Rules & Live Alert Manager
│   │   ├── services/
│   │   │   ├── dataset_sync_service.py # 25-Prompt Golden Dataset benchmark sync
│   │   │   ├── langfuse_prompt_service.py # 4-Tier Prompt Manager + DB-to-Langfuse real-time watcher
│   │   │   ├── graph_rag_service.py  # Triple-Engine Neo4j + ChromaDB/BM25 + NetworkX Graph RAG
│   │   │   ├── zoho_service.py       # Zoho People REST v2 API integration with Circuit Breaker
│   │   │   ├── leave_service.py      # Leave ledger calculation logic (latest-first ordering)
│   │   │   └── timesheet_service.py  # Timesheet calculation logic (latest-first ordering)
│   │   ├── api/v1/endpoints/         # FastAPI Endpoints
│   │   │   ├── agents.py             # Chat, streaming, session delete/purge, prompt sync & webhooks
│   │   │   ├── auth.py               # JWT & mock SSO authentication (/auth/login, /auth/mock-login)
│   │   │   ├── leaves.py             # Leave application & balance APIs
│   │   │   ├── timesheets.py         # Timesheet entry & approval APIs
│   │   │   ├── reports.py            # Departmental analytics & DB inspector views
│   │   │   ├── policy.py             # Policy search endpoints
│   │   │   └── onboarding.py         # Employee onboarding & document OCR workflows
│   │   ├── models/                   # SQLAlchemy ORM models (User, LeaveApplication, TimesheetEntry, ChatSession, AgentPrompt)
│   │   ├── core/
│   │   │   ├── config.py             # App settings & pydantic environment loader
│   │   │   ├── database.py           # Async engine & sessionmaker (Render PostgreSQL)
│   │   │   ├── db_views.py           # PostgreSQL database views (v_employees_overview, etc.)
│   │   │   ├── llm_bridge.py         # Multi-model LiteLLM / ADK bridge with automatic Groq model rotation
│   │   │   └── security.py           # Password hashing, JWT token creation, PII scrubber
│   │   └── main.py                   # FastAPI Application Factory & Lifespan Hooks (starts DB prompt watcher)
│   │
│   └── data/
│       ├── prompts_registry.json     # Decoupled prompts local air-gapped backup
│       ├── golden_dataset_25.json    # 25-Prompt Golden Benchmark test cases
│       ├── maharashtra_labour_law.json # Statutory provisions local dataset
│       ├── company_policy_2026.json  # Enterprise policy handbook
│       └── zoho_mock_fixtures.json   # Circuit-breaker fallback fixtures for Zoho People
│
└── frontend/
    ├── src/
    │   ├── pages/                    # Portal views (Dashboard, Leave, Timesheet, Policy, Onboarding, Observability)
    │   ├── components/               # Navbar (5-user switcher), AgentChatDrawer (opaque history + Purge), AgentFlowCircuit
    │   ├── api.ts                    # Typed API client calling /api/v1
    │   └── App.tsx                   # Role-aware routing & state management
    └── vite.config.ts                # Vite config with /api proxy to localhost:8000
```

---

## 3. Multi-Turn & Cross-Session Conversation Memory (`conversation_memory.py`)

1. **5-Session Sliding Window (`conversation_summaries`)**:
   - Every employee has an isolated rolling window of their latest 5 conversation summaries stored in PostgreSQL (`conversation_summaries`).
   - Summaries are generated via `generate_summary()` (using `groq/llama-3.1-8b-instant` after each assistant turn so background summarization never consumes primary 70B/120B agent quota).
2. **Deep Episodic Turn Recall (`recall_relevant_past_turns`)**:
   - Scans historical `chat_turns` across past sessions for the authenticated user, scoring statement/preference turns (e.g., location, pet name, emergency contact, WFH day, project lead, health symptoms, logged hours) and injecting exact historical dialogue excerpts into the Root Orchestrator context.
3. **Conversational & Recall Intent Routing (`intent_router.py` & `orchestrator.py`)**:
   - Personal facts (`"I live in Pune"`, `"my pet's name is Vivan"`), greetings, and cross-session recall inquiries (`"Where did I tell you I live?"`, `"Who is my emergency contact?"`, `"Summarize our past conversations"`) route directly to `hr_root_orchestrator` (`QueryScope.GENERAL_HELP`).
   - Fallback routing never scans across the 5-session summary window for domain keywords, preventing old medical/leave summaries from poisoning unrelated conversational turns.
4. **Session Deletion & Full User Chat Purge**:
   - **Single Session Delete** (`DELETE /api/v1/agents/sessions/{session_id}`): Deletes the session and its turns/summary from PostgreSQL (`chat_turns`, `conversation_summaries`, `chat_sessions`), RAM cache, and ADK `InMemorySessionService`.
   - **Full User Purge Button** (`DELETE /api/v1/agents/sessions`): Subtle formal grey **Purge** button in `AgentChatDrawer.tsx` that permanently wipes all `chat_turns`, `conversation_summaries`, and `chat_sessions` for that user from PostgreSQL, local snapshot disk, and ADK memory.

---

## 4. Bidirectional Prompt Management & Langfuse Cloud Observability

### Credentials & Project Configuration
* **Dashboard Base URL**: `https://us.cloud.langfuse.com`
* **Public Key**: `pk-lf-106c7f65-93af-401e-b5b5-3e68742d926c`
* **Secret Key**: `sk-lf-d83aaacf-94dd-45e4-8f3e-71e0ac0ff249`
* **Webhook Secret**: `lf-whsec_0a07efcdb14e85bd67251e6b6d6a672bcbf72cfc94777a16a530e59916d150a9`

### 4-Tier Prompt Architecture & Real-Time TablePlus $\leftrightarrow$ Langfuse Sync (`langfuse_prompt_service.py`)
1. **Tier 1 — In-Memory Cache (`0ms`)**: Serves active prompts during turn execution.
2. **Tier 2 — PostgreSQL Table (`agent_prompts`)**: Local authoritative store editable via the PeopleOps UI or directly in **TablePlus**.
   - **PostgreSQL Trigger (`trg_agent_prompts_auto_version_and_notify`)**: Any `UPDATE` to `template` in `agent_prompts` (e.g., from TablePlus) automatically increments `version = COALESCE(OLD.version, 1) + 1`, updates `updated_at = NOW()`, and fires `pg_notify('agent_prompt_changed', ...)`.
   - **Background Watcher (`start_db_prompt_watcher`)**: Runs every `3.0s` in FastAPI's lifespan, detects any DB version/template change, updates the in-memory cache, hot-reloads the Google ADK agent instructions (`sync_agent_instructions()`), and pushes a new version with labels `["live", "production", "latest"]` to **Langfuse Cloud**.
3. **Tier 3 — Langfuse Cloud Registry**: Remote prompt versioning & webhook invalidation (`/api/v1/agents/prompts/webhook`).
4. **Tier 4 — Local JSON Registry (`backend/data/prompts_registry.json`)**: Air-gapped fallback and initial DB seed source.

### Complete Tab Coverage in Langfuse Cloud
* **`Tracing` (Waterfall View)**: Full round-trip hierarchy (`TOTAL ROUND-TRIP` $\rightarrow$ `Input Guardrails` $\rightarrow$ `Orchestrator` $\rightarrow$ `Subagent` $\rightarrow$ `Tool Selection` $\rightarrow$ `Tool Execution` $\rightarrow$ `Output Guardrails`) with latency, cost, and DPDP PII scrubbing.
* **`Sessions` & `Users` Tabs**: Attributed by official corporate email (`devansh.tyagi@intelera.com`, `rahul.sharma@intelera.com`, `sneha.kulkarni@intelera.com`, etc.).
* **`Evaluators` & `Datasets`**: 5 LLM-as-a-Judge metrics (`policy_groundedness`, `safety_and_pii_zero_leakage`, `helpfulness_and_clarity`, `statutory_compliance`, `latency_sla`) and the 25-Prompt Golden Benchmark (`peopleops-golden-benchmark-25`).

---

## 5. Database Schema, TablePlus Latest-First Ordering & 5 Personas

The primary database is **Render PostgreSQL 16** (`peopleops_postgres`):

### Latest-to-Oldest Ordering in TablePlus & UI
* TablePlus sorts table rows by the first column of the table's `PRIMARY KEY`.
* All 10 tables (`chat_sessions`, `chat_turns`, `conversation_summaries`, `employee_documents`, `leave_applications`, `timesheet_entries`, `security_trail`, `zoho_sync_records`, `agent_prompts`, `employee_profiles`) have:
  - `id` preserved as **Column 1** (`UNIQUE NOT NULL`)
  - `sort_order BIGINT` as the first column in `PRIMARY KEY (sort_order, id)`
  - Sequence `latest_first_seq` (`INCREMENT BY -1`) and `BEFORE INSERT OR UPDATE` trigger `trg_set_latest_first_sort_order()` (checking `to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)`) so every newly inserted or modified record automatically jumps to the **top row** in TablePlus.

### Clean PostgreSQL Views (`app/core/db_views.py`)
* `v_employees_overview`, `v_leaves_summary`, `v_timesheets_active`, `v_chat_sessions_overview`, `v_conversation_memory_window`, `v_zoho_sync_status`, `v_employee_documents`, `v_security_audit_trail`.

### The 5 Role-Switched Employee Personas
| Employee ID | Full Name | Corporate Email | Navbar Role Label | System Role | Department |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`EMP-001`** | Devansh Tyagi | `devansh.tyagi@intelera.com` | **Admin** | `ADMIN` | Executive |
| **`EMP-002`** | Vikram Malhotra | `vikram.malhotra@intelera.com` | **Manager** | `MANAGER` | Engineering |
| **`EMP-003`** | Priya Patel | `priya.patel@intelera.com` | **HR Ops** | `HR_OPS` | Human Resources |
| **`EMP-004`** | Rahul Sharma | `rahul.sharma@intelera.com` | **Employee** | `EMPLOYEE` | Engineering |
| **`EMP-005`** | Sneha Kulkarni | `sneha.kulkarni@intelera.com` | **Employee 2** | `EMPLOYEE` | Operations |

---

## 6. Complete Enterprise Fallback Matrix

1. **LLM Model & Provider Failover (`llm_bridge.py` & `adk_fleet.py`)**:
   - Rotates automatically across `groq/llama-3.3-70b-versatile` $\rightarrow$ `groq/openai/gpt-oss-20b` $\rightarrow$ `groq/llama-3.1-8b-instant` $\rightarrow$ `groq/openai/gpt-oss-120b` on rate limits, then OpenAI $\rightarrow$ Gemini $\rightarrow$ `MockLLMProvider`.
2. **Orchestrator Execution Fallback (`orchestrator.py`)**:
   - Google ADK Multi-Agent Runner $\rightarrow$ Semantic Intent Router concurrent tool dispatch $\rightarrow$ Conversational / Episodic Memory synthesis.
3. **Prompt Management Fallback (`langfuse_prompt_service.py`)**:
   - In-Memory Cache $\rightarrow$ PostgreSQL `agent_prompts` $\rightarrow$ Langfuse Cloud $\rightarrow$ `data/prompts_registry.json`.
4. **Policy RAG & Knowledge Graph Fallback (`graph_rag_service.py`)**:
   - 120s TTL Cache $\rightarrow$ Concurrent Neo4j Aura + ChromaDB/BM25 + NetworkX Graph $\rightarrow$ Local JSON statutory files (`maharashtra_labour_law.json`, `company_policy_2026.json`).
5. **Zoho People HRMS Circuit Breaker (`zoho_service.py`)**:
   - 3-state Circuit Breaker (`CLOSED` $\rightarrow$ `OPEN` after 3 failures for 30s $\rightarrow$ `HALF_OPEN`) falling back to `data/zoho_mock_fixtures.json` and PostgreSQL `zoho_sync_records`.
6. **Memory Summarization Fallback (`conversation_memory.py`)**:
   - LLM summary (`groq/llama-3.1-8b-instant`) $\rightarrow$ Deterministic heuristic topic/entity summary.
7. **Storage & OCR Fallback (`onboarding.py`)**:
   - MinIO / S3 bucket (`hr-documents`) $\rightarrow$ Local `backend/uploads/` storage + PostgreSQL `employee_documents`; Vision/Tesseract OCR $\rightarrow$ Structured stream extraction.
8. **Statutory Critic Verification (`statutory_critic.py`)**:
   - Deterministic regex & statutory rule engine verifying and auto-correcting legal numbers (e.g., enforcing `2.0x` overtime rate and `45-day` EL cap under Maharashtra Act 2017) with zero LLM dependency.

---

## 7. Indian Statutory Labour Law Compliance Rules (Maharashtra Act 2017)

* **Section 13**: Standard work hours (max **9 hours/day**, **48 hours/week**).
* **Section 14**: Overtime compensation mandated at **2.0x (double ordinary rate)**; daily working cap strictly **11 hours/day**; quarterly overtime capped at **125 hours**.
* **Section 15**: Mandatory rest interval of at least **30 minutes after 5 continuous hours of work**; daily spread-over capped at **10.5 hours**.
* **Section 18**:
  - **Earned Leave (EL)**: 18 days/yr (statutory min 1 day per 20 days worked). Maximum accumulation / carry-forward capped at **45 days**.
  - **Casual Leave (CL)**: 8 days/yr, non-cumulative, lapses December 31.
  - **Sick Leave (SL)**: 10–12 days/yr. Absence **exceeding 2 consecutive days** requires a registered medical practitioner's certificate.
* **Notice Periods**: **30 days** for confirmed full-time employees; **15 days** during probation.

---

## 8. How to Run & Verify All Services

```powershell
# 1. Backend FastAPI Service (Port 8000)
cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\backend"
$env:PYTHONPATH="C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\backend\.venv\Lib\site-packages"
& "C:\Users\Devansh Tyagi\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. Frontend React / Vite Service (Port 5173)
cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops\frontend"
npm run dev

# 3. Ngrok Public Webhook Tunnel
& "C:\Users\Devansh Tyagi\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 5173 --log=stdout
```
