# Production HR Multi-Agent Platform (Google ADK & NVIDIA NeMo Guardrails)

A production-oriented, enterprise Human Resources platform featuring a hierarchical multi-agent architecture built with **Google Agent Development Kit (Google ADK)**, **FastAPI**, **React 18 + TypeScript (Vite)**, and a dual-boundary defense powered by **NVIDIA NeMo Guardrails** (`nemoguardrails==0.24.1`).

Compliant with India's **Digital Personal Data Protection (DPDP) Act, 2023** and benchmarked against the **Maharashtra Shops and Establishments (Regulation of Employment and Conditions of Service) Act, 2017**.

---

## 🏗️ Architecture Overview

```
                                  +-----------------------------+
                                  |   React 18 + Vite Frontend  |
                                  | (Google SSO / RBAC Switcher)|
                                  +--------------+--------------+
                                                 | HTTPS / JWT
                                  +--------------v--------------+
                                  |     FastAPI ASGI Backend    |
                                  |   (Pydantic v2 / Uvicorn)   |
                                  +--------------+--------------+
                                                 |
                                 [ NVIDIA NeMo Input Guardrail ]
                                 (Jailbreak, Injection, Scope)
                                                 |
                                  +--------------v--------------+
                                  |   Root Orchestrator Agent   |
                                  |        (Google ADK)         |
                                  +-------+------+-------+------+
                                          |      |       |
                 +------------------------+      |       +-------------------------+
                 |                               |                                 |
      +----------v-----------+       +-----------v----------+          +-----------v----------+
      |Leave Management Agent|       | HR Policy Graph RAG  |          |   Timesheet Agent    |
      | - Authoritative check|       | - Neo4j Knowledge    |          | - Daily hours cap    |
      | - Overlap validation |       | - MH Labour Law 2017 |          | - Duplicate check    |
      | - Manager approvals  |       | - Exact citations    |          | - CSV export engine  |
      +----------+-----------+       +-----------+----------+          +-----------+----------+
                 |                               |                                 |
                 +------------------------+      |       +-------------------------+
                                          |      |       |
                                  +-------v------v-------v------+
                                  |  Deterministic Core Services|
                                  | (PostgreSQL Ledger / ACID)  |
                                  +--------------+--------------+
                                                 |
                                 [ NVIDIA NeMo Output Guardrail]
                                 (DPDP Aadhaar/PAN Redaction)
                                                 |
                                  +--------------v--------------+
                                  |   LangSmith Observability   |
                                  |     (PII-Scrubbed Traces)   |
                                  +-----------------------------+
```

---

## 🚀 Key Features

1. **Google ADK Hierarchical Multi-Agent System**:
   - **Root Orchestrator**: High-precision intent classifier that routes requests to specialized domain agents.
   - **Leave Management Agent**: Retrieves authoritative balances directly from the database ledger for **EL**, **CL**, **SL**, and **LWP**. Never hallucinates balances; validates date order, overlapping requests, and routes approvals to reporting managers.
   - **HR Policy Graph RAG Agent**: Synthesizes company policies and statutory provisions from the *Maharashtra Shops and Establishments Act, 2017* (Section 18 for leave entitlements, Section 13 for working hours and 2.0x overtime, Section 15 for spread-over). Automatically attaches statutory disclaimers and escalates contentious matters to human HR.
   - **Timesheet Agent**: Tracks project hours, enforces daily 16-hour ceilings, prevents duplicate task entries, and generates downloadable CSV reports.

2. **NVIDIA NeMo Guardrails (`nemoguardrails==0.24.1`)**:
   - **Input Rails**: Blocks prompt injection, jailbreak tokens ("ignore previous instructions", "DAN mode"), and unauthorized probes seeking confidential records or salaries of other employees.
   - **Output Rails & DPDP Redaction**: Automatically identifies and masks 12-digit Indian Aadhaar numbers (`XXXX-XXXX-1234`) and 10-digit PAN cards (`ABXXXXXX4F`) before responses reach the UI or observability platforms.

3. **Prompt Management & CI Testing (Promptfoo)**:
   - Versioned prompt repository in `promptfoo/prompts/` with semantic owners, versions, and change notes.
   - Automated assertions for intent routing, statutory factuality, citation quality, injection resistance, and regression detection.

4. **Observability (LangSmith)**:
   - Zero raw PII sent to observability. Traces agent trajectories, latency, token usage, and guardrail trips.

5. **Role-Based Access Control (RBAC) & Developer Mock SSO**:
   - One-click role switching between **Employee**, **HR Associate**, **HR Manager**, and **Admin** for instant local evaluation without requiring external GCP credentials.

---

## ⚡ Quickstart

### Prerequisites
- Python 3.11+ (or uv package manager)
- Node.js 18+ and npm
- Docker & Docker Compose (optional for containerized deployment)

### 1. Backend Setup
```bash
cd backend
# Create virtual environment with Python 3.11
uv venv .venv --python 3.11
# Install dependencies
uv pip install -e .
# Run unit & adversarial tests
.venv/Scripts/pytest -v
# Start development server
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```
*The backend automatically seeds initial demo accounts (Employee, HR Associate, HR Manager, Admin), active projects, and leave ledger records.*

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run build
npm run dev -- --port 3000
```
Open **`http://localhost:3000`** in your browser.

---

## 🐳 Docker Compose Deployment

To spin up the entire cluster (PostgreSQL with `pgvector`, Neo4j 5.x, MinIO S3-compatible storage, FastAPI backend, and Vite frontend):

```bash
docker compose up --build -d
```

| Service | Endpoint | Credentials |
| :--- | :--- | :--- |
| **Frontend Web UI** | `http://localhost:3000` | Mock SSO enabled |
| **Backend API & Swagger Docs** | `http://localhost:8000/api/v1/docs` | Bearer Auth / Mock SSO |
| **Neo4j Browser** | `http://localhost:7474` | `neo4j` / `hr_neo4j_password` |
| **MinIO Console** | `http://localhost:9001` | `minio_admin` / `minio_secret_password` |
| **PostgreSQL Database** | `localhost:5432` | `hr_user` / `hr_password` / `hr_db` |

---

## 🧪 Testing & Verification

### Automated Backend Tests
Run the comprehensive test suite (15 unit, integration, RBAC, and adversarial security tests):
```bash
cd backend
.venv/Scripts/pytest -v
```
Verified Test Cases:
- `test_password_hashing` & `test_jwt_token_generation_and_decode`
- `test_prompt_injection_detection` (Blocks jailbreaks & system prompt exfiltration)
- `test_unauthorized_probe_detection` (Blocks salary & colleague Aadhaar probes)
- `test_output_pii_masking_dpdp` (Verifies Aadhaar and PAN redaction)
- `test_legal_disclaimer_attachment` (Verifies Maharashtra Labour Law citations)
- `test_leave_application_and_overlap_validation` (Deterministic overlap check)
- `test_generate_csv_format` (Timesheet payroll export formatting)
- `test_api_endpoints.py` (Full FastAPI mock login, health, and multi-agent chat)

### Promptfoo Prompt Regression Suite
```bash
cd promptfoo
npx promptfoo eval
```

---

## 🔐 Threat Model & Security Compliance

Detailed threat modeling documentation is available at [docs/threat_model.md](docs/threat_model.md), addressing:
- **OWASP LLM01 (Prompt Injection)**: Neutralized via NeMo input guardrails.
- **OWASP LLM02 (Sensitive Information Disclosure / DPDP Act 2023)**: Dual-layer regex and Colang masking for Aadhaar/PAN.
- **OWASP API1 (Broken Object Level Authorization / BOLA)**: All mutations check validated JWT identity at the service layer, preventing prompt spoofing.
- **OWASP LLM09 (Hallucinations)**: Grounded Graph RAG citations with mandatory statutory disclaimers.

---

## 👥 Demo User Personas

| Persona | Role | Default Email | Capabilities |
| :--- | :--- | :--- | :--- |
| **Aarav Sharma** | `EMPLOYEE` | `employee@intelera.corp` | View personal balances, apply for leave, submit daily timesheet entries. |
| **Priya Patel** | `HR_ASSOCIATE` | `associate@intelera.corp` | Initiate employee onboarding, review resume extraction, upload KYC. |
| **Vikram Malhotra**| `HR_MANAGER` | `manager@intelera.corp` | Approve/reject leaves, review team timesheets, download CSV reports. |
| **Devansh Tyagi** | `ADMIN` | `admin@intelera.corp` | Full platform access, security configurations, policy approvals. |
