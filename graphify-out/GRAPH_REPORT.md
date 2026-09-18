# Graph Report - people-ops  (2026-09-18)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 466 nodes · 1240 edges · 19 communities (15 shown, 4 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 136 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e488e432`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app_models_user
- timesheets.py
- App.tsx
- package.json
- security.py
- leaves.py
- User
- models/__init__.py
- UserRole
- main.py
- compilerOptions
- compilerOptions
- test_api_endpoints.py
- get_llm_provider
- .oxlintrc.json
- tsconfig.json
- hr-multiagent-platform-backend

## God Nodes (most connected - your core abstractions)
1. `User` - 65 edges
2. `UserRole` - 36 edges
3. `TimesheetService` - 25 edges
4. `LeaveService` - 25 edges
5. `OnboardingService` - 20 edges
6. `seed_initial_data()` - 17 edges
7. `compilerOptions` - 17 edges
8. `LeaveType` - 16 edges
9. `AuditLog` - 16 edges
10. `TimesheetStatus` - 15 edges

## Surprising Connections (you probably didn't know these)
- `run()` --calls--> `User`  [INFERRED]
  promptfoo/promptfoo_provider.py → backend/app/models/user.py
- `call_api()` --uses--> `UserRole`  [INFERRED]
  promptfoo/promptfoo_provider.py → backend/app/models/user.py
- `call_api()` --uses--> `User`  [INFERRED]
  promptfoo/promptfoo_provider.py → backend/app/models/user.py
- `LeaveAgent` --uses--> `LeaveType`  [INFERRED]
  backend/app/agents/leave_agent.py → backend/app/models/leave.py
- `LeaveAgent` --uses--> `User`  [INFERRED]
  backend/app/agents/leave_agent.py → backend/app/models/user.py

## Import Cycles
- None detected.

## Communities (19 total, 4 thin omitted)

### Community 0 - "app_models_user"
Cohesion: 0.05
Nodes (41): app_agents_leave_agent, app_agents_llm_provider, app_agents_orchestrator, app_agents_policy_agent, app_agents_timesheet_agent, app_guardrails_guardrails_manager, app_models_user, app_observability_langsmith_tracer (+33 more)

### Community 1 - "timesheets.py"
Cohesion: 0.10
Nodes (43): app_models_timesheet, app_schemas_timesheet, app_services_timesheet_service, Any, AsyncSession, Agent assisting employees with time logging, submission, and managers with…, TimesheetAgent, export_timesheet_csv() (+35 more)

### Community 2 - "App.tsx"
Cohesion: 0.14
Nodes (34): api, apiClient, App(), AgentChatDrawer(), ChatDrawerProps, Message, Navbar(), NavbarProps (+26 more)

### Community 3 - "package.json"
Cohesion: 0.05
Nodes (41): dependencies, axios, clsx, lucide-react, react, react-dom, tailwind-merge, devDependencies (+33 more)

### Community 4 - "security.py"
Cohesion: 0.07
Nodes (25): app_core_security, Settings, mask_aadhaar(), repl(), mask_all_pii(), mask_pan(), Masks 12-digit Indian Aadhaar numbers, revealing only the last 4 digits., Masks Indian PAN numbers, e.g. ABCDE1234F -> ABXXXXXX4F. (+17 more)

### Community 5 - "leaves.py"
Cohesion: 0.17
Nodes (27): app_models_leave, app_schemas_leave, app_services_leave_service, apply_for_leave(), decide_leave_application(), get_my_leave_balances(), list_leave_applications(), AsyncSession (+19 more)

### Community 6 - "User"
Cohesion: 0.16
Nodes (28): app_schemas_onboarding, app_services_onboarding_service, confirm_onboarding_profile(), extract_resume_details(), initiate_employee_onboarding(), AsyncSession, post, UploadFile (+20 more)

### Community 7 - "models/__init__.py"
Cohesion: 0.15
Nodes (21): app_core_database, app_models_policy, get_password_hash(), LeaveBalance, Base, PolicyChunk, PolicyDocument, PolicyStatus (+13 more)

### Community 8 - "UserRole"
Cohesion: 0.15
Nodes (24): app_schemas_auth, get_current_user_profile(), login_for_access_token(), mock_login(), AsyncSession, get, post, Developer mock login for instant role switching without requiring external… (+16 more)

### Community 9 - "main.py"
Cohesion: 0.12
Nodes (17): app_api_v1_agents, app_api_v1_auth, app_api_v1_health, app_api_v1_leaves, app_api_v1_onboarding, app_api_v1_policy, app_api_v1_reports, app_api_v1_timesheets (+9 more)

### Community 10 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, jsx, lib, module, moduleDetection, moduleResolution (+10 more)

### Community 11 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 12 - "test_api_endpoints.py"
Cohesion: 0.15
Nodes (9): async_client(), asyncio, fixture, test_agent_chat_routing_and_guardrail_block(), test_health_check(), test_mock_login_flow(), test_policy_search_citations(), httpx (+1 more)

### Community 13 - "get_llm_provider"
Cohesion: 0.24
Nodes (7): ABC, BaseLLMProvider, get_llm_provider(), MockLLMProvider, Deterministic local LLM provider for rapid development, testing, and offline…, Production provider using Google Vertex AI / Gemini via Google GenAI SDK., VertexGeminiProvider

### Community 14 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

## Knowledge Gaps
- **77 isolated node(s):** `ChatDrawerProps`, `LeaveBalanceItem`, `allowArbitraryExtensions`, `allowImportingTsExtensions`, `jsx` (+72 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 172 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `User` to `app_models_user`, `timesheets.py`, `leaves.py`, `models/__init__.py`, `UserRole`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Why does `UserRole` connect `UserRole` to `timesheets.py`, `leaves.py`, `User`, `models/__init__.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `mask_all_pii()` connect `security.py` to `User`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `User` (e.g. with `LeaveAgent` and `RootOrchestrator`) actually correct?**
  _`User` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `UserRole` (e.g. with `TimesheetAgent` and `mock_login()`) actually correct?**
  _`UserRole` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `TimesheetService` (e.g. with `TimesheetAgent` and `export_timesheet_csv()`) actually correct?**
  _`TimesheetService` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `LeaveService` (e.g. with `LeaveAgent` and `apply_for_leave()`) actually correct?**
  _`LeaveService` has 16 INFERRED edges - model-reasoned connections that need verification._