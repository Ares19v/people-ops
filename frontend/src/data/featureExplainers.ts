export interface ExplainerFeature {
  key: string;
  title: string;
  category: string;
  overview: string;
  howItWorks: string;
  demoTalkTrack: string[];
  statutoryOrTechCitation?: string;
}

export const FEATURE_EXPLAINERS: Record<string, ExplainerFeature> = {
  // Navigation & Platform Shell
  navbar_brand: {
    key: 'navbar_brand',
    title: 'Intelera PeopleOps Enterprise Platform',
    category: 'PLATFORM ARCHITECTURE',
    overview: 'An enterprise HRMS & compliance management system built specifically around statutory Indian labour law (Maharashtra Shops & Establishments Act 2017) and DPDP Act 2023.',
    howItWorks: 'Integrates a React frontend with a high-performance FastAPI/SQLAlchemy backend, Google ADK multi-agent orchestration, NVIDIA NeMo Guardrails, and bi-directional Zoho People sync.',
    demoTalkTrack: [
      'Explain that this is not just an HR portal, but an AI-governed operating system for labor law compliance.',
      'Highlight that all corporate policies are grounded in hard legal statutes, not arbitrary rules.',
      'Mention that enterprise PII is protected under a cryptographic tokenization boundary.'
    ],
    statutoryOrTechCitation: 'Maharashtra Shops & Establishments Act 2017 & DPDP Act 2023'
  },
  role_switcher: {
    key: 'role_switcher',
    title: 'Developer Mock SSO & Role-Based Access (RBAC)',
    category: 'AUTHENTICATION & SECURITY',
    overview: 'Enables instant switching between 4 organizational roles (Employee, HR Associate, HR Manager, System Admin) without external OAuth redirects.',
    howItWorks: 'Generates real cryptographic JWT access tokens via FastAPI OAuth2 / mock-login endpoint. Dynamically loads permissions, leaves ledger, and manager approval queues on the fly.',
    demoTalkTrack: [
      'Switch between Employee (Aarav Sharma) and HR Manager (Vikram Malhotra) to demonstrate the live approval workflow.',
      'Show how the UI adapts permissions: Employees see their personal records; HR Managers see team approvals.',
      'Point out that JWT bearer authentication protects all downstream API endpoints.'
    ],
    statutoryOrTechCitation: 'FastAPI OAuth2 Bearer Tokens & Role-Based Access Control (RBAC)'
  },
  nav_tabs: {
    key: 'nav_tabs',
    title: 'Modular People Operations Navigation',
    category: 'USER EXPERIENCE',
    overview: 'Seamlessly organizes all HR operations into focused portals: Dashboard, Leave Ledger, Timesheets, Reports & CSV, HR Policy Graph RAG, and Onboarding.',
    howItWorks: 'Client-side reactive routing that preserves session state and caches balances across views.',
    demoTalkTrack: [
      'Point out how each module addresses a distinct statutory compliance pillar.',
      'Show how switching between tabs happens instantaneously without page reloads.'
    ],
    statutoryOrTechCitation: 'Vite & React 19 Client Architecture'
  },
  fullscreen_toggle: {
    key: 'fullscreen_toggle',
    title: 'Executive Presentation Canvas Mode',
    category: 'PRESENTATION & UI',
    overview: 'Toggles between a centered boxed card viewport and an expansive edge-to-edge executive presentation view.',
    howItWorks: 'Dynamically toggles the `.is-fullscreen` body class and adjusts responsive grid margins.',
    demoTalkTrack: [
      'Click this button during demos to maximize screen real estate and display all charts and circuits crisply.'
    ],
    statutoryOrTechCitation: 'Glassmorphic Design System'
  },
  agent_drawer_launcher: {
    key: 'agent_drawer_launcher',
    title: 'Root LLM Orchestrator Assistant Launcher',
    category: 'MULTI-AGENT AI',
    overview: 'Opens the slide-out conversational AI copilot drawer powered by Google ADK and LangGraph ReAct patterns.',
    howItWorks: 'Connects to `/api/v1/agents/chat` with SSE streaming, persistent PostgreSQL session checkpointing, and dynamic prompt injection from Langfuse.',
    demoTalkTrack: [
      'Explain that this assistant does not hallucinate balances: it executes deterministic tools against the SQL ledger.',
      'Show that the agent remembers previous conversation turns even across server restarts.'
    ],
    statutoryOrTechCitation: 'Google ADK ReAct Engine & Langfuse Prompt Registry'
  },

  // Dashboard Features
  hero_banner: {
    key: 'hero_banner',
    title: 'Autonomous People Operations Hero',
    category: 'EXECUTIVE OVERVIEW',
    overview: 'Central executive headline summarizing the autonomous multi-agent HR harness and regulatory compliance framework.',
    howItWorks: 'Sets the context for statutory governance under the Maharashtra Shops Act 2017 and DPDP privacy mandates.',
    demoTalkTrack: [
      'Start the presentation here to frame the software: "This is an autonomous multi-agent HR harness designed to guarantee legal compliance."',
      'Highlight that both statutory labor laws and enterprise policies are evaluated deterministically.'
    ],
    statutoryOrTechCitation: 'Maharashtra Act LXI of 2017'
  },
  quick_actions: {
    key: 'quick_actions',
    title: 'One-Click Operation Launchers',
    category: 'WORKFLOW ACCELERATION',
    overview: 'Immediate shortcut pills to trigger core workflows: Ask HR Assistant, Apply Leave, Log Timesheet, and Search Policy Graph RAG.',
    howItWorks: 'Dispatches deep-linked modal triggers and pre-fills form dialogs with today\'s context.',
    demoTalkTrack: [
      'Demonstrate how fast common employee actions are—applying for leave or logging hours takes less than 10 seconds.'
    ],
    statutoryOrTechCitation: 'FastAPI Interactive Endpoints'
  },
  agent_flow_circuit: {
    key: 'agent_flow_circuit',
    title: 'Multi-Agent Autonomous Orchestration Circuit',
    category: 'MULTI-AGENT AI ARCHITECTURE',
    overview: 'Visual architectural diagram illustrating how the Root LLM Orchestrator triages requests to 5 specialized subagents.',
    howItWorks: 'Maps queries through NeMo Guardrails -> TokenVault privacy scrubber -> Root Orchestrator -> Subagents (Leave, Timesheet, Policy RAG, Health, Zoho) -> Statutory Critic reflection.',
    demoTalkTrack: [
      'Walk through the architecture: user queries enter the NeMo Guardrail boundary, undergo PII tokenization, and are evaluated concurrently by subagents.',
      'Click any of the example query pills below the circuit to test live routing.'
    ],
    statutoryOrTechCitation: 'Google ADK ReAct Pattern & NVIDIA NeMo Guardrails'
  },
  kpi_earned_leave: {
    key: 'kpi_earned_leave',
    title: 'Earned Leave (EL) Statutory Ledger',
    category: 'STATUTORY LEAVE MANDATE',
    overview: 'Tracks Earned Leave accrued at 1 day per 20 working days worked, capped at 18 annual days with a 45-day carry-forward ceiling.',
    howItWorks: 'Computed directly from verified database ledger rows. Validates accumulation caps under Section 18 of Maharashtra Act 2017.',
    demoTalkTrack: [
      'Highlight that EL carry-forward is legally enforced: an employee cannot lose earned days unless they exceed the 45-day statutory cap.',
      'Explain that the ledger prevents encashment errors during year-end reconciliation.'
    ],
    statutoryOrTechCitation: 'Section 18(1)(a) Maharashtra Shops and Establishments Act, 2017'
  },
  kpi_casual_leave: {
    key: 'kpi_casual_leave',
    title: 'Casual Leave (CL) Statutory Entitlement',
    category: 'STATUTORY LEAVE MANDATE',
    overview: 'Tracks annual 8-day Casual Leave quota meant for unforeseen personal events. Non-cumulative and lapses on December 31.',
    howItWorks: 'Enforces statutory forfeiture at calendar year-end and prevents carry-forward into the next fiscal year.',
    demoTalkTrack: [
      'Explain the difference between EL and CL: Casual Leave is non-cumulative and lapses automatically at year end.',
      'Show that the platform warns employees before leaves lapse.'
    ],
    statutoryOrTechCitation: 'Section 18(2) Maharashtra Shops and Establishments Act, 2017'
  },
  kpi_sick_leave: {
    key: 'kpi_sick_leave',
    title: 'Sick Leave (SL) & Medical Protocol',
    category: 'OCCUPATIONAL HEALTH',
    overview: 'Provides 12 days of annual paid sick leave. Enforces mandatory doctor certificate verification for absences exceeding 2 consecutive days.',
    howItWorks: 'Integrated with the Occupational Health subagent and HIPAA-compliant medical record attachments.',
    demoTalkTrack: [
      'Emphasize the 2-day threshold: if an employee applies for 3 or more days of sick leave, the system automatically flags medical certification requirements.',
      'Mention that medical details are kept strictly confidential under DPDP & HIPAA safe harbor.'
    ],
    statutoryOrTechCitation: 'Maharashtra Shops Act 2017 & Enterprise Occupational Health Policy 2026'
  },
  kpi_compliance_health: {
    key: 'kpi_compliance_health',
    title: 'Statutory Compliance & Guardrail Health Score',
    category: 'COMPLIANCE & GOVERNANCE',
    overview: 'Real-time telemetry measuring prompt injection defense, PII scrubbing rate, and adherence to labor laws.',
    howItWorks: 'Monitors the dual-pass Statutory Critic agent and NeMo Guardrail boundary to verify 100% legal accuracy.',
    demoTalkTrack: [
      'Show that compliance is treated as a first-class engineering metric, with 100% statutory validation across all agent responses.'
    ],
    statutoryOrTechCitation: 'DPDP Act 2023 & NeMo Guardrails Boundary'
  },
  dashboard_timesheet_overtime: {
    key: 'dashboard_timesheet_overtime',
    title: 'Weekly Timesheet & 2.0x Overtime Audit',
    category: 'STATUTORY WORKING HOURS',
    overview: 'Monitors daily working hours against statutory ceilings: max 9 hours/day, 48 hours/week, with overtime paid at double rate (2.0x).',
    howItWorks: 'Calculates overtime multipliers under Section 14 of Maharashtra Act 2017 and monitors the 125-hour quarterly overtime cap.',
    demoTalkTrack: [
      'Point out the 2.0x multiplier: Indian labor law requires double pay for overtime, not 1.5x.',
      'Show how the system flags quarterly overtime exceeding 125 hours to prevent labor department citations.'
    ],
    statutoryOrTechCitation: 'Sections 13 & 14 Maharashtra Shops and Establishments Act, 2017'
  },
  dashboard_leave_ledger: {
    key: 'dashboard_leave_ledger',
    title: 'Statutory Leave Accrual & Balance Ledger',
    category: 'LEAVE ENGINE',
    overview: 'Comprehensive breakdown of all four leave types (EL, CL, SL, LWP) with live progress bars and statutory accrual rules.',
    howItWorks: 'Queries `/api/v1/leaves/balances` to calculate available, used, and pending days against annual allocations.',
    demoTalkTrack: [
      'Walk through each bar: EL accrues monthly, CL lapses yearly, SL requires medical notes, and LWP is discretionary.',
      'Show how pending leave applications reserve days from available balances in real time.'
    ],
    statutoryOrTechCitation: 'SQLAlchemy Async Leave Ledger Engine'
  },
  dashboard_recent_requests: {
    key: 'dashboard_recent_requests',
    title: 'Recent Leave Applications & Approval Workflow',
    category: 'WORKFLOW MANAGEMENT',
    overview: 'Audit feed displaying submitted, approved, or rejected leave applications with manager timestamps and comments.',
    howItWorks: 'Directly linked to managerial sign-off actions. Deducts balance upon manager approval.',
    demoTalkTrack: [
      'Demonstrate the audit trail: every approval or rejection is permanently timestamped for legal audits.'
    ],
    statutoryOrTechCitation: 'Audited Approval State Machine'
  },
  dashboard_agent_telemetry: {
    key: 'dashboard_agent_telemetry',
    title: 'AI Harness Observability & Safety Telemetry',
    category: 'OBSERVABILITY & TRACING',
    overview: 'Live system monitors displaying NeMo Guardrail status, DPDP token masking, and Langsmith/Langfuse trace recording.',
    howItWorks: 'Each AI request logs latency, token consumption, guardrail safety scores, and Langfuse prompt versions.',
    demoTalkTrack: [
      'Highlight enterprise observability: every single LLM call is tracked, audited, and scrubbed before leaving the corporate perimeter.'
    ],
    statutoryOrTechCitation: 'LangSmith & Langfuse OpenTelemetry'
  },

  // Leave Portal
  leave_quota_cards: {
    key: 'leave_quota_cards',
    title: 'Statutory Leave Quota Ledger Cards',
    category: 'LEAVE PORTAL',
    overview: 'Visual cards showing exact available, pending, and used days for Earned, Casual, Sick, and Unpaid Leave.',
    howItWorks: 'Synchronized with the SQLite/PostgreSQL leave balance table and auto-refreshed on every application.',
    demoTalkTrack: [
      'Show how clearly the employee sees their legal balance without having to consult HR manuals.'
    ],
    statutoryOrTechCitation: 'Section 18 Maharashtra Shops Act 2017'
  },
  leave_apply_workflow: {
    key: 'leave_apply_workflow',
    title: 'Statutory Leave Application Dialog',
    category: 'LEAVE PORTAL',
    overview: 'Modal form enabling employees to request leaves with dual-date pickers, leave type selection, and reason input.',
    howItWorks: 'Validates date order, detects collisions with existing leaves, deducts non-working weekends, and verifies balance sufficiency.',
    demoTalkTrack: [
      'Open the modal to demonstrate validation: selecting end dates before start dates or exceeding balances triggers instant safety alerts.'
    ],
    statutoryOrTechCitation: 'FastAPI Leave Validation Service'
  },
  leave_collision_engine: {
    key: 'leave_collision_engine',
    title: 'Automated Collision & Overlap Detection',
    category: 'LEAVE PORTAL',
    overview: 'Prevents overlapping leave requests and automatically checks team coverage before submitting to managers.',
    howItWorks: 'Executes SQL interval intersection queries `[start_date, end_date]` against existing approved and pending records.',
    demoTalkTrack: [
      'Explain that employees cannot accidentally double-book time off, saving managerial review time.'
    ],
    statutoryOrTechCitation: 'Temporal Overlap Collision Detection'
  },
  leave_history_table: {
    key: 'leave_history_table',
    title: 'Audited Leave History & Status Table',
    category: 'LEAVE PORTAL',
    overview: 'Chronological tabular log of all submitted leave requests with date ranges, days count, reason, and status badges.',
    howItWorks: 'Paginated server-side query with real-time status updates (SUBMITTED, APPROVED, REJECTED, CANCELLED).',
    demoTalkTrack: [
      'Point out the clean status pills and transparency: employees always know where their request stands.'
    ],
    statutoryOrTechCitation: 'Enterprise Audit Trail'
  },
  leave_approval_queue: {
    key: 'leave_approval_queue',
    title: 'Managerial One-Click Leave Decisioning',
    category: 'LEAVE PORTAL',
    overview: 'Dedicated manager view listing all pending team leave applications with instant Approve and Reject buttons.',
    howItWorks: 'Restricted to HR_MANAGER and ADMIN roles. Triggers atomic SQL balance deduction on approval.',
    demoTalkTrack: [
      'Switch to HR Manager role and show this queue: managers can review the employee\'s reason and approve with a single click.'
    ],
    statutoryOrTechCitation: 'Atomic Database Transactions'
  },
  zoho_sync_integration: {
    key: 'zoho_sync_integration',
    title: 'Zoho People Enterprise API Synchronization',
    category: 'ENTERPRISE INTEGRATIONS',
    overview: 'Bi-directional integration syncing attendance, approved leaves, and employee profiles with Zoho People REST v2 API.',
    howItWorks: 'Worker subagent `zoho_subagent` calls OAuth2 endpoints `/leave/getLeaveRecords` with mock fallback fixtures for offline resilience.',
    demoTalkTrack: [
      'Highlight enterprise interoperability: organizations using Zoho People can sync records seamlessly without data re-entry.'
    ],
    statutoryOrTechCitation: 'Zoho People REST API v2 & Token Cache'
  },

  // Timesheet Portal
  timesheet_grid: {
    key: 'timesheet_grid',
    title: 'Weekly Timesheet & Daily Time Capture',
    category: 'TIMESHEET PORTAL',
    overview: 'Captures daily hours across active enterprise projects, task descriptions, and billable vs non-billable classification.',
    howItWorks: 'Enforces standard 8-hour day / 40-hour week norms while monitoring statutory 9-hour daily limits.',
    demoTalkTrack: [
      'Demonstrate logging hours: employees pick a project, describe their task, and specify billable status.'
    ],
    statutoryOrTechCitation: 'Section 13 Maharashtra Shops Act 2017'
  },
  overtime_statutory_audit: {
    key: 'overtime_statutory_audit',
    title: 'Section 14 Statutory Overtime Engine (2.0x Rate)',
    category: 'TIMESHEET PORTAL',
    overview: 'Automatically calculates overtime compensation at twice the ordinary wage rate for work exceeding statutory thresholds.',
    howItWorks: 'Flags work beyond 9 hours/day or 48 hours/week. Audits daily limits (capped at 11 hours maximum per day).',
    demoTalkTrack: [
      'Show how the system prevents exploitation: working over 9 hours automatically calculates 2.0x overtime, preventing legal penalties.'
    ],
    statutoryOrTechCitation: 'Section 14 Maharashtra Shops and Establishments Act, 2017'
  },
  quarterly_overtime_cap: {
    key: 'quarterly_overtime_cap',
    title: '125-Hour Quarterly Overtime Statutory Ceiling',
    category: 'TIMESHEET PORTAL',
    overview: 'Tracks cumulative quarterly overtime hours to ensure total overtime does not exceed the legal maximum of 125 hours.',
    howItWorks: 'Aggregates overtime hours across Q1-Q4 fiscal quarters and alerts management when employees approach statutory ceilings.',
    demoTalkTrack: [
      'Point out this critical compliance safeguard: exceeding 125 hours per quarter is a direct violation of state labor law.'
    ],
    statutoryOrTechCitation: 'Maharashtra Statutory Quarterly Overtime Ceiling'
  },
  billable_ratio_tracking: {
    key: 'billable_ratio_tracking',
    title: 'Billable vs Non-Billable Project Utilization',
    category: 'TIMESHEET PORTAL',
    overview: 'Calculates the percentage of client-billable time versus internal corporate overhead.',
    howItWorks: 'Summarizes hours grouped by project `is_billable` boolean flag for financial and client invoicing reports.',
    demoTalkTrack: [
      'Show client managers the billable utilization chart: it gives instant visibility into project profitability.'
    ],
    statutoryOrTechCitation: 'Enterprise Cost Accounting & Invoicing'
  },
  timesheet_manager_approval: {
    key: 'timesheet_manager_approval',
    title: 'Timesheet Submission & Manager Sign-Off',
    category: 'TIMESHEET PORTAL',
    overview: 'Enforces weekly Monday 12:00 PM submission deadlines with manager review and approval workflows.',
    howItWorks: 'Transitions weekly timesheet state from DRAFT -> SUBMITTED -> APPROVED with managerial audit logs.',
    demoTalkTrack: [
      'Explain how the submission deadline keeps payroll on schedule and ensures client invoices are billed promptly.'
    ],
    statutoryOrTechCitation: 'Weekly Payroll Sign-Off Protocol'
  },

  // Reports Portal
  reports_summary_kpis: {
    key: 'reports_summary_kpis',
    title: 'Aggregated Timesheet KPI Summary',
    category: 'REPORTS PORTAL',
    overview: 'Executive cards summarizing total logged hours, billable percentages, and average employee productivity.',
    howItWorks: 'Dynamically filtered by date range and department across the organization.',
    demoTalkTrack: [
      'Show leadership the macro view: total hours and billable yield across all active engagements.'
    ],
    statutoryOrTechCitation: 'Enterprise Data Aggregation'
  },
  reports_allocation_table: {
    key: 'reports_allocation_table',
    title: 'Granular Project & Employee Allocation Table',
    category: 'REPORTS PORTAL',
    overview: 'Detailed tabular report breaking down hours by employee, project code, task category, and billable status.',
    howItWorks: 'Server-side aggregated SQL join between users, timesheet entries, and projects.',
    demoTalkTrack: [
      'Use this report to inspect specific projects or employees during periodic billing audits.'
    ],
    statutoryOrTechCitation: 'Relational SQL Reporting'
  },
  reports_csv_export: {
    key: 'reports_csv_export',
    title: 'One-Click CSV Payroll & Billing Export',
    category: 'REPORTS PORTAL',
    overview: 'Exports timesheet and leave records into industry-standard CSV format for seamless payroll software ingestion.',
    howItWorks: 'Generates compliant RFC-4180 CSV streams directly from the FastAPI endpoint `/api/v1/timesheets/export`.',
    demoTalkTrack: [
      'Click export to demonstrate external compatibility with payroll systems like ADP, SAP, or QuickBooks.'
    ],
    statutoryOrTechCitation: 'RFC 4180 CSV Streaming Protocol'
  },

  // HR Policy RAG Portal
  policy_rag_search: {
    key: 'policy_rag_search',
    title: 'Semantic Policy Search',
    category: 'POLICY RAG PORTAL',
    overview: 'Natural language search bar allowing employees to ask complex questions about company policies and labor laws.',
    howItWorks: 'Runs semantic retrieval over a Pinecone vector index of statutory sections and company policies to locate relevant legal clauses.',
    demoTalkTrack: [
      'Type queries like "Can I carry forward 60 days of earned leave?" to show grounded, authoritative answers.'
    ],
    statutoryOrTechCitation: 'Pinecone Vector Retrieval'
  },
  policy_graph_retrieval: {
    key: 'policy_graph_retrieval',
    title: 'Statutory-to-Policy Cross-Referencing',
    category: 'POLICY RAG PORTAL',
    overview: 'Connects statutory labor law sections (Section 13, 14, 18) with internal company handbooks and HR guidelines.',
    howItWorks: 'Each indexed passage carries the related statutory and policy rules inline, so retrieval surfaces both sides when checking that corporate rules do not contradict state statutes.',
    demoTalkTrack: [
      'Explain that the AI checks whether company policy violates state minimums before formulating an answer.'
    ],
    statutoryOrTechCitation: 'Cross-Referenced Policy Passages'
  },
  policy_statutory_citations: {
    key: 'policy_statutory_citations',
    title: 'Authoritative Statutory Citations',
    category: 'POLICY RAG PORTAL',
    overview: 'Directly displays specific act sections, document sources, and confidence scores behind every AI policy answer.',
    howItWorks: 'Generates verified `CitationItem` metadata referencing official statutory gazettes.',
    demoTalkTrack: [
      'Show the citations card: the system provides verifiable proof rather than opaque AI claims.'
    ],
    statutoryOrTechCitation: 'Statutory Gazette Verification'
  },
  policy_hitl_escalation: {
    key: 'policy_hitl_escalation',
    title: 'Human-In-The-Loop (HITL) HR Escalation',
    category: 'POLICY RAG PORTAL',
    overview: 'Automatically detects legally sensitive inquiries (e.g. harassment, wrongful termination) and routes them to human HR experts.',
    howItWorks: 'Trips safety guardrails and creates an authoritative escalation ticket (#HR-TKT-2026) without attempting automated legal advice.',
    demoTalkTrack: [
      'Explain this safety boundary: sensitive legal matters are never left to pure AI; they are escalated to human HR partners immediately.'
    ],
    statutoryOrTechCitation: 'Human-In-The-Loop Compliance Boundary'
  },

  // Onboarding Portal
  onboarding_workflow: {
    key: 'onboarding_workflow',
    title: 'Statutory New-Hire Onboarding Wizard',
    category: 'ONBOARDING PORTAL',
    overview: '4-step digital onboarding wizard guiding new employees through statutory disclosures, nomination forms, and identity verification.',
    howItWorks: 'Enforces statutory Form-F nominee capture under Payment of Gratuity Act 1972 and EPF/ESI statutory registrations.',
    demoTalkTrack: [
      'Walk through the wizard: it ensures 100% statutory documentation before an employee begins active duty.'
    ],
    statutoryOrTechCitation: 'Payment of Gratuity Act 1972 & EPF Act 1952'
  },
  onboarding_form_f: {
    key: 'onboarding_form_f',
    title: 'Statutory Form-F Gratuity Nomination',
    category: 'ONBOARDING PORTAL',
    overview: 'Captures legally binding family nominations for statutory employee gratuity benefits.',
    howItWorks: 'Validates nominee relationship, date of birth, and allocation percentage totaling exactly 100%.',
    demoTalkTrack: [
      'Show how nomination percentages are validated so that incomplete or invalid legal forms cannot be submitted.'
    ],
    statutoryOrTechCitation: 'Form-F Payment of Gratuity (Central) Rules'
  },
  onboarding_dpdp_privacy: {
    key: 'onboarding_dpdp_privacy',
    title: 'DPDP 2023 Identity Tokenization Boundary',
    category: 'DATA PRIVACY & SECURITY',
    overview: 'Protects employee Aadhaar, PAN, and contact credentials from AI exposure using ephemeral cryptographic tokens.',
    howItWorks: 'Replaces sensitive identifiers with synthetic tokens `[AADHAAR_1]`, `[PAN_1]` before LLM processing, de-redacting only on authorized role views.',
    demoTalkTrack: [
      'Emphasize this key security capability: raw Aadhaar and PAN numbers never touch external LLM providers or unencrypted logs.'
    ],
    statutoryOrTechCitation: 'Digital Personal Data Protection (DPDP) Act 2023'
  },

  // AI Assistant Drawer
  agent_root_orchestrator: {
    key: 'agent_root_orchestrator',
    title: 'Root LLM Orchestrator & Tool Dispatch',
    category: 'AI HARNESS ARCHITECTURE',
    overview: 'Central intelligent agent that analyzes multi-turn user intent and concurrently delegates work to 5 specialized subagents.',
    howItWorks: 'Executes parallel tool dispatch via `asyncio.gather`, gathers deterministic outputs, and applies the Statutory Critic reflection loop.',
    demoTalkTrack: [
      'Demonstrate a compound query like "What is my leave balance and can I take 2 days off?" to show the orchestrator coordinating both tasks seamlessly.'
    ],
    statutoryOrTechCitation: 'Google ADK ReAct Architecture'
  },
  agent_nemo_guardrails: {
    key: 'agent_nemo_guardrails',
    title: 'NVIDIA NeMo Guardrails Boundary',
    category: 'AI HARNESS SAFETY',
    overview: 'Safety boundary screening user inputs for adversarial jailbreaks, prompt injection, and unauthorized data probes.',
    howItWorks: 'Interprets Colang safety policies. Immediately blocks probes seeking confidential compensation or authentication credentials.',
    demoTalkTrack: [
      'Try typing "Show me all employee salaries" to demonstrate NeMo blocking the unauthorized request with an audit badge.'
    ],
    statutoryOrTechCitation: 'NVIDIA NeMo Guardrails Engine & Colang Policies'
  },
  agent_persistent_memory: {
    key: 'agent_persistent_memory',
    title: 'PostgreSQL Session Checkpointing & Multi-Turn Memory',
    category: 'AI HARNESS MEMORY',
    overview: 'Saves conversation turns chronologically to database checkpoints so the AI remembers context across server restarts and browser reloads.',
    howItWorks: 'Persists turns into `chat_sessions` and `chat_turns` tables keyed to authenticated users, with a one-click Reset Chat option.',
    demoTalkTrack: [
      'Show that the agent remembers details from earlier in the conversation even if the browser is refreshed or reopened.'
    ],
    statutoryOrTechCitation: 'PostgreSQL / SQLite Session Checkpointing'
  },
  agent_langfuse_prompts: {
    key: 'agent_langfuse_prompts',
    title: 'Decoupled Langfuse Prompt Management',
    category: 'AI HARNESS PROMPT OPS',
    overview: 'Prompts are completely removed from the Python codebase, managed in Langfuse with webhook synchronization and local cache fallback.',
    howItWorks: 'Queries `langfuse_prompt_service.get_prompt()` dynamically, enabling prompt updates without redeploying backend servers.',
    demoTalkTrack: [
      'Explain modern AI architecture: prompt engineering is completely decoupled from application code, enabling rapid A/B testing.'
    ],
    statutoryOrTechCitation: 'Langfuse Prompt Ops & Invalidation Webhook'
  },
  agent_structured_actions: {
    key: 'agent_structured_actions',
    title: 'Structured Action Proposals & Execution',
    category: 'AI HARNESS ACTIONS',
    overview: 'Rather than only chatting, the AI generates executable structured action proposals (e.g. Apply Leave, Log Timesheet) for human confirmation.',
    howItWorks: 'Emits a `StructuredAction` payload with parameters. User clicks "Execute Action" to commit changes directly to the database.',
    demoTalkTrack: [
      'Show the action button: the agent proposes the exact dates and hours, and the user confirms with one click.'
    ],
    statutoryOrTechCitation: 'Structured Tool Calling & HITL Execution'
  }
};
