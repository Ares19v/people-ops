# PeopleOps Enterprise — Architecture & Codebase Map

This document explains the multi-agent architecture, directory structure, data flows, and design rationale.

---

## 1. Directory & File Map

See the folder map in the top-level [README](../README.md#folder-map-read-top-to-bottom). It is the single source of truth, so it is not repeated here.

---

## 2. Demystifying the "Orchestrator" Files

To avoid confusion among the files with "orchestrator" in their name:

| File | Exact Purpose |
| :--- | :--- |
| **`root_orchestrator.py`** | **The Declarative Google ADK Agent**: Defines `hr_root_orchestrator = Agent(name="hr_root_orchestrator", model=..., sub_agents=[...])` following the Google ADK standard. |
| **`root_llm_agent.py`** | **The Runtime Execution Engine**: Implements the full production pipeline: Redact PII $\to$ Check Guardrails $\to$ Recall Memory $\to$ Parallel Tool Gather $\to$ Critic Loop $\to$ Formatting Sanitizer $\to$ Dual Tracing. |
| **`orchestrator.py`** | **The Backward-Compatible Facade**: A lightweight wrapper that forwards requests to `root_llm_agent.py`. Ensures legacy code and imports remain 100% intact. |
| **`adk_fleet.py`** | **Fleet Harness & Live Sync**: Assembles the ADK `Runner`, manages `InMemorySessionService`, and dynamically pulls new prompt instructions from Langfuse at runtime. |
| **`langgraph_orchestrator.py`** | **Comparative StateGraph Pipeline**: Alternative LangGraph implementation exposed on `/langgraph-chat` for side-by-side benchmarking against Google ADK. |

---

## 3. Demystifying PII Handling

* **`app.compliance.phi_engine.compliance_engine`**:
  * **Role**: Dynamic, stateful, reversible LLM context protection.
  * Replaces raw Aadhaar, PAN, emails, and names with ephemeral tokens (`[AADHAAR_1]`, `[NAME_1]`) stored in an in-memory `TokenVault`. The LLM **never sees raw identities**.
  * De-redaction is reversible only when returning the final response to an authorized user role.
* **`app.core.security.mask_all_pii`**:
  * **Role**: Static, irreversible regex scrubbing (`XXXX-XXXX-1234`).
  * Used for plain audit logging and output sanitization as a fail-safe backstop.

---

## 4. End-to-End Execution Flow (Google ADK Fleet)

```mermaid
sequenceDiagram
    autonumber
    actor Employee as Employee / User
    participant API as FastAPI (/api/v1/agents/chat)
    participant Redactor as Compliance Engine (TokenVault)
    participant Rails as NeMo Guardrails
    participant Memory as Conversation Memory
    participant Root as Root LLM Agent
    participant Critic as Statutory Critic Agent
    participant SubAgent as Specialist Subagents / Tools
    participant Tracer as Observability (LangSmith / Langfuse)

    Employee->>API: User Message ("Can I take 3 days EL next week?")
    API->>Redactor: Mask PII into ephemeral tokens ([NAME_1])
    Redactor->>Rails: Evaluate input against OWASP LLM01 & Clinical Red Flags
    Rails->>Memory: Load recent turn history for session
    Memory->>Root: Reason over intent & history using CoT
    Root->>SubAgent: Parallel dispatch to leave_agent & tools
    SubAgent-->>Root: Return balance status & eligibility
    Root->>Critic: Reflect & verify Section 18 statutory accuracy
    Critic-->>Root: Validated & corrected response
    Root->>Rails: Output compliance check & disclaimer append
    Rails->>Redactor: De-redact tokens for authorized user role
    Redactor->>Tracer: Log latency, tokens & guardrail metrics
    Tracer-->>Employee: Clean, human, empathetic response
```
