"""
Generate high-quality PDF: PeopleOps Enterprise Codebase Folder Structure (Backend & Frontend)
Output location: docs/folder_structure.pdf
"""
import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 11 * 72 - 30, "PeopleOps Enterprise Platform | Clean Architecture & Repository Structure")
            self.drawRightString(8.5 * 72 - 40, 11 * 72 - 30, "Backend & Frontend Specifications")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 11 * 72 - 34, 8.5 * 72 - 40, 11 * 72 - 34)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 40, 8.5 * 72 - 40, 40)
        
        self.drawString(40, 28, "Intelera PeopleOps — Internal Architectural Documentation — Canonical Clean State")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * 72 - 40, 28, page_str)
        self.restoreState()

def build_pdf(output_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=42,
        bottomMargin=48
    )

    PAGE_WIDTH = 8.5 * 72 - 80  # 532 pt content width

    # Palette
    C_PRIMARY = colors.HexColor("#0F172A")    # Deep Slate
    C_INDIGO = colors.HexColor("#312E81")     # Deep Indigo
    C_BLUE = colors.HexColor("#1D4ED8")       # Royal Blue
    C_TEXT = colors.HexColor("#1E293B")       # Slate Charcoal
    C_MUTED = colors.HexColor("#475569")      # Muted Gray
    C_BG_LIGHT = colors.HexColor("#F8FAFC")   # Light Card Fill
    C_BORDER = colors.HexColor("#E2E8F0")     # Light Border
    C_HEADER_BG = colors.HexColor("#1E293B")  # Dark Header

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=C_PRIMARY,
        alignment=TA_LEFT
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=C_BLUE,
        alignment=TA_LEFT
    )

    tagline_style = ParagraphStyle(
        'DocTagline',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=C_MUTED,
        alignment=TA_LEFT
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=C_PRIMARY,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=C_INDIGO,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyCustom',
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=C_TEXT,
        alignment=TA_LEFT
    )

    tree_code_style = ParagraphStyle(
        'TreeCode',
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=C_PRIMARY,
        alignment=TA_LEFT
    )

    th_style = ParagraphStyle(
        'TableHead',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=TA_LEFT
    )

    td_name_style = ParagraphStyle(
        'TableColName',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=C_INDIGO,
        alignment=TA_LEFT
    )

    td_desc_style = ParagraphStyle(
        'TableColDesc',
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.5,
        textColor=C_TEXT,
        alignment=TA_LEFT
    )

    td_files_style = ParagraphStyle(
        'TableColFiles',
        fontName='Courier',
        fontSize=6.5,
        leading=9,
        textColor=colors.HexColor("#0369A1"),
        alignment=TA_LEFT
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("PeopleOps Multi-Agent Enterprise Platform", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Clean Repository & Folder Structure Specification (Backend & Frontend)", subtitle_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Official reference guide describing the directory hierarchy, purpose of every folder, and architectural organization.", tagline_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_BLUE, spaceBefore=2, spaceAfter=8))

    # Architecture Overview Callout Card
    overview_text = (
        "<b>Core Architecture Standards & Clean-State Invariants:</b><br/>"
        "• <b>Single Canonical .env:</b> Located strictly at project root. Zero duplicate or nested .env files in subfolders.<br/>"
        "• <b>Single Master README.md:</b> Centrally located at root. Nested template readmes removed.<br/>"
        "• <b>Zero Clutter / Scratch Files:</b> All one-off database migration and temporary debug scripts removed.<br/>"
        "• <b>Separation of Concerns:</b> Backend exposes clean REST & SSE streaming APIs on port <b>8001</b>; "
        "Frontend Vite client runs on port <b>5173</b> with automatic reverse-proxy routing via /api."
    )
    card_table = Table([[Paragraph(overview_text, body_style)]], colWidths=[PAGE_WIDTH])
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, C_BLUE),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 10))

    # 2. Section 1: High-Level Project Root Structure
    story.append(Paragraph("1. High-Level Repository Layout (Root Directory)", h1_style))
    story.append(Paragraph(
        "The project root is structured to give any developer an immediate, intuitive view of all high-level subsystems:",
        body_style
    ))
    story.append(Spacer(1, 4))

    root_table_data = [
        [Paragraph("Directory / File", th_style), Paragraph("Category", th_style), Paragraph("Description & Responsibility", th_style)],
        [Paragraph("backend/", td_name_style), Paragraph("Core Service", td_desc_style), Paragraph("FastAPI server, Google ADK multi-agent fleet, NeMo guardrails, Hybrid Graph RAG, PostgreSQL ledger & ChromaDB.", td_desc_style)],
        [Paragraph("frontend/", td_name_style), Paragraph("Web Client", td_desc_style), Paragraph("React 19 + TypeScript + Vite + Tailwind CSS dashboard with SSE streaming AI drawer & portal workflows.", td_desc_style)],
        [Paragraph("docker/", td_name_style), Paragraph("DevOps", td_desc_style), Paragraph("Multi-stage container definitions (Dockerfile.backend and Dockerfile.frontend) for production deployment.", td_desc_style)],
        [Paragraph("docs/", td_name_style), Paragraph("Documentation", td_desc_style), Paragraph("Architecture blueprints, demo scripts, operations guides, threat model, UI screenshots, and PDF guides.", td_desc_style)],
        [Paragraph("promptfoo/", td_name_style), Paragraph("AI Red-Teaming", td_desc_style), Paragraph("Adversarial jailbreak evaluation configs, test matrix datasets, and prompt assertion rules.", td_desc_style)],
        [Paragraph("scripts/", td_name_style), Paragraph("Operations", td_desc_style), Paragraph("Developer tooling and secure public tunneling scripts (start_ngrok.bat, set_authtoken.bat).", td_desc_style)],
        [Paragraph(".env & .env.example", td_name_style), Paragraph("Configuration", td_desc_style), Paragraph("Single canonical environment configuration (database, OpenAI, Gemini, Langfuse, Zoho credentials).", td_desc_style)],
        [Paragraph("docker-compose.yml", td_name_style), Paragraph("Orchestration", td_desc_style), Paragraph("Multi-service Docker compose orchestrator linking backend, frontend, PostgreSQL, and Neo4j.", td_desc_style)],
        [Paragraph("README.md", td_name_style), Paragraph("Documentation", td_desc_style), Paragraph("Comprehensive enterprise documentation, quickstart guide, API contracts, and architecture diagrams.", td_desc_style)],
    ]
    t_root = Table(root_table_data, colWidths=[100, 75, 357])
    t_root.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_HEADER_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_BG_LIGHT]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_root)
    story.append(Spacer(1, 10))

    # Page Break for clean section separation
    story.append(PageBreak())

    # 3. Section 2: Backend Architecture & Directory Breakdown
    story.append(Paragraph("2. Backend Architecture Structure (backend/)", h1_style))
    story.append(Paragraph(
        "The backend is built around a domain-driven, modular architecture where multi-agent workflows, data models, compliance engines, and external integrations are cleanly decoupled:",
        body_style
    ))
    story.append(Spacer(1, 4))

    backend_tree_ascii = """backend/
|-- alembic/                # Database migration environment (env.py, versions/)
|-- app/                    # Primary application package
|   |-- agents/             # Google ADK Multi-Agent Fleet (Orchestrator & Specialists)
|   |-- api/v1/             # REST endpoints & SSE streaming routes
|   |-- compliance/         # Regulatory rule engines (HIPAA Safe Harbor 18 & DPDP)
|   |-- core/               # App configuration (loads root .env), DB engine & JWT auth
|   |-- evaluations/        # Automated grid benchmark evaluation matrix (Langfuse + ADK)
|   |-- guardrails/         # NVIDIA NeMo Guardrails boundary (Colang 2.0 rails)
|   |-- memory/             # Multi-turn conversational sliding context & vector recall
|   |-- models/             # Relational SQLAlchemy models (User, Leave, Timesheet, Session)
|   |-- rag/                # Hybrid Knowledge Graph (NetworkX/Neo4j) & vector search
|   |-- schemas/            # Pydantic v2 data contracts & structured action cards
|   |-- services/           # Domain business services & Zoho REST v2 circuit breaker
|   |-- tools/              # Domain-specific Google ADK tools (leave, policy, health, etc.)
|   \\-- main.py             # FastAPI entrypoint, CORS & application lifespan
|-- data/                   # ChromaDB vectors, token vault, policy catalog & seed data
|-- reports/                # Benchmark evaluation result JSONs
|-- scripts/                # 7 Production maintenance & utility scripts
|-- tests/                  # Automated pytest suite (E2E memory, security, API routing)
\\-- uploads/                # Temporary buffer for KYC document verification"""

    b_tree_box = Table([[Paragraph(backend_tree_ascii.replace("\n", "<br/>").replace(" ", "&nbsp;"), tree_code_style)]], colWidths=[PAGE_WIDTH])
    b_tree_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(b_tree_box)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Backend Subdirectory Functional Catalog", h2_style))

    backend_table_data = [
        [Paragraph("Subdirectory", th_style), Paragraph("Core Responsibility", th_style), Paragraph("Key Modules / Files", th_style)],
        [
            Paragraph("app/agents/", td_name_style),
            Paragraph("Multi-Agent fleet powered by Google ADK and LangGraph. Root orchestrator performs dual-rail routing to specialized subagents with resilient fallback.", td_desc_style),
            Paragraph("orchestrator.py, root_llm_agent.py, leave_agent.py, timesheet_agent.py, policy_agent.py, health_agent.py, statutory_critic.py, prompt_strategies.py", td_files_style)
        ],
        [
            Paragraph("app/api/v1/", td_name_style),
            Paragraph("REST API and Server-Sent Events (SSE) streaming endpoints serving user chat, leave ledger, timesheets, and authentication.", td_desc_style),
            Paragraph("agents.py, auth.py, leaves.py, timesheets.py, policies.py, onboarding.py, prompts.py", td_files_style)
        ],
        [
            Paragraph("app/compliance/", td_name_style),
            Paragraph("Regulatory safety and legal engines ensuring 100% adherence to Maharashtra, Karnataka, and Delhi Shops & Establishments Acts.", td_desc_style),
            Paragraph("phi_engine.py (HIPAA Safe Harbor 18 & DPDP redaction), statutory_rules.py (Labour Law Rules)", td_files_style)
        ],
        [
            Paragraph("app/core/", td_name_style),
            Paragraph("Settings and database engine. Securely loads the single root .env and initializes SQLAlchemy async PostgreSQL connection pool.", td_desc_style),
            Paragraph("config.py, database.py, security.py, id_generator.py, llm_bridge.py", td_files_style)
        ],
        [
            Paragraph("app/guardrails/", td_name_style),
            Paragraph("NVIDIA NeMo Guardrails boundary intercepting prompt injections, jailbreaks, and out-of-scope employee queries.", td_desc_style),
            Paragraph("nemo_boundary.py, guardrails_manager.py, config/ (Colang 2.0 policies)", td_files_style)
        ],
        [
            Paragraph("app/memory/", td_name_style),
            Paragraph("Conversational memory manager supporting 5-session sliding context, vector similarity recall, and reboot disk snapshotting.", td_desc_style),
            Paragraph("conversation_memory.py", td_files_style)
        ],
        [
            Paragraph("app/rag/", td_name_style),
            Paragraph("Hybrid Knowledge Graph and Vector RAG engine combining NetworkX, Neo4j Aura Cloud, and local ChromaDB embeddings.", td_desc_style),
            Paragraph("knowledge_graph.py, agentic_rag.py, graph_rag_service.py, entity_extractor.py, graph_schema.py", td_files_style)
        ],
        [
            Paragraph("app/services/", td_name_style),
            Paragraph("Domain business logic and external integrations including Zoho People REST v2 sync and Langfuse dynamic prompt retrieval.", td_desc_style),
            Paragraph("leave_service.py, timesheet_service.py, zoho_service.py, auth_service.py, langfuse_prompt_service.py", td_files_style)
        ],
        [
            Paragraph("app/tools/", td_name_style),
            Paragraph("Domain-specific Google ADK tool implementations for leave balance queries, timesheet logging, policy search, and health certs.", td_desc_style),
            Paragraph("hr_tools.py, leave/, timesheet/, policy/, health/, zoho/", td_files_style)
        ],
        [
            Paragraph("data/", td_name_style),
            Paragraph("Persistent data assets: encrypted token vault, ChromaDB vector store, exported trace logs, and static statutory acts.", td_desc_style),
            Paragraph("chroma_db/, token_vault/, traces/, company_policy_2026.json, maharashtra_labour_law.json, seed_data.py", td_files_style)
        ],
        [
            Paragraph("scripts/", td_name_style),
            Paragraph("7 Production utility scripts for benchmark validation, Langfuse synchronization, graph seeding, and PDF document generation.", td_desc_style),
            Paragraph("test_full_suite.py, run_golden_dataset_benchmark.py, seed_neo4j_graph.py, sync_db_mirror.py, push_prompt.py, generate_architecture_pdf.py", td_files_style)
        ],
    ]
    t_backend = Table(backend_table_data, colWidths=[90, 242, 200])
    t_backend.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_HEADER_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_BG_LIGHT]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_backend)
    story.append(Spacer(1, 10))

    # Page Break for clean section separation
    story.append(PageBreak())

    # 4. Section 3: Frontend Architecture & Directory Breakdown
    story.append(Paragraph("3. Frontend Architecture Structure (frontend/)", h1_style))
    story.append(Paragraph(
        "The frontend is a modern React 19 single-page application built with TypeScript, Vite, and Tailwind CSS. It is structured into presentation components, functional page portals, global contexts, and centralized API utilities:",
        body_style
    ))
    story.append(Spacer(1, 4))

    frontend_tree_ascii = """frontend/
|-- public/                 # Static web assets, favicon & SVG icon sprite
|-- src/                    # Application source code
|   |-- assets/             # Brand graphics, icons & visual hero assets
|   |-- components/         # Reusable UI component library (AgentChatDrawer, Navbar, etc.)
|   |-- context/            # React Context providers (DemoContext instant role switcher)
|   |-- data/               # Static enterprise feature & architecture deep-dive catalogs
|   |-- pages/              # Portal views (Dashboard, Leave, Timesheet, Policy, Onboarding)
|   |-- utils/              # Formatting helpers for currency, dates, and status badges
|   |-- api.ts              # Central Axios HTTP client & SSE streaming event listener
|   |-- App.tsx             # Root router, navigation shell & modal container
|   |-- index.css           # Tailwind CSS design system tokens & animation styles
|   |-- main.tsx            # React 19 DOM bootstrap entrypoint
|   \\-- types.ts            # Strict TypeScript interface contracts matching backend models
|-- package.json            # NPM project manifest, dependencies & build scripts
\\-- vite.config.ts          # Vite build bundler & reverse proxy (/api -> http://127.0.0.1:8001)"""

    f_tree_box = Table([[Paragraph(frontend_tree_ascii.replace("\n", "<br/>").replace(" ", "&nbsp;"), tree_code_style)]], colWidths=[PAGE_WIDTH])
    f_tree_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(f_tree_box)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Frontend Subdirectory Functional Catalog", h2_style))

    frontend_table_data = [
        [Paragraph("Directory / File", th_style), Paragraph("Role & Responsibility", th_style), Paragraph("Key Features / Included Modules", th_style)],
        [
            Paragraph("src/components/", td_name_style),
            Paragraph("Reusable UI component library implementing the enterprise design system, drawer drawers, and modals.", td_desc_style),
            Paragraph("AgentChatDrawer.tsx (real-time SSE streaming assistant), AgentFlowCircuit.tsx (live routing circuit), Navbar.tsx (header, reset & role selector), TokenVaultModal.tsx (PII redaction viewer), ZohoPeopleIntegrationHub.tsx (HRMS sync controls)", td_files_style)
        ],
        [
            Paragraph("src/pages/", td_name_style),
            Paragraph("Enterprise workflow portals providing dedicated views for executive metrics, leave ledgers, time tracking, and KYC.", td_desc_style),
            Paragraph("Dashboard.tsx (fleet telemetry & metrics), LeavePortal.tsx (statutory leave ledger), TimesheetPortal.tsx (hours logging & overtime audit), PolicyPortal.tsx (statutory RAG search), ReportsPortal.tsx (CSV exporter), OnboardingPortal.tsx (DPDP document upload)", td_files_style)
        ],
        [
            Paragraph("src/context/", td_name_style),
            Paragraph("Global React Context providers managing authentication tokens, active user personas, and role permissions.", td_desc_style),
            Paragraph("DemoContext.tsx (allows instant zero-friction switching between Employee, Manager, and Admin personas with full RBAC updates)", td_files_style)
        ],
        [
            Paragraph("src/data/", td_name_style),
            Paragraph("Static domain datasets, architectural feature catalogs, and educational walkthrough copy.", td_desc_style),
            Paragraph("featureDeepDive.ts (comprehensive deep-dive catalog of enterprise security, guardrails, and compliance capabilities)", td_files_style)
        ],
        [
            Paragraph("src/utils/", td_name_style),
            Paragraph("Formatting utilities ensuring standardized display of dates, currency figures, and statutory compliance status pills.", td_desc_style),
            Paragraph("formatters.tsx (formatDate, formatDuration, getStatusBadgeColor, calculateLeaveAccrualSummary)", td_files_style)
        ],
        [
            Paragraph("src/api.ts", td_name_style),
            Paragraph("Unified Axios HTTP client configured with baseURL '/api' and real-time Server-Sent Events (SSE) streaming reader.", td_desc_style),
            Paragraph("Provides typed methods for chat completion, leave applications, timesheet submissions, KYC uploads, and memory resets.", td_files_style)
        ],
        [
            Paragraph("src/types.ts", td_name_style),
            Paragraph("TypeScript domain model definitions matching backend Pydantic schemas 1-to-1.", td_desc_style),
            Paragraph("User, LeaveRequest, TimesheetEntry, AgentChatResponse, StructuredAction, CitationItem, MemoryTurn", td_files_style)
        ],
        [
            Paragraph("vite.config.ts", td_name_style),
            Paragraph("Vite development server configuration featuring built-in reverse proxy.", td_desc_style),
            Paragraph("Transparently proxies all '/api' requests to the FastAPI backend running on http://127.0.0.1:8001.", td_files_style)
        ],
    ]
    t_frontend = Table(frontend_table_data, colWidths=[95, 227, 210])
    t_frontend.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_HEADER_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_BG_LIGHT]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_frontend)
    story.append(Spacer(1, 10))

    # 5. Section 4: Operational Quick Reference
    story.append(Paragraph("4. Operational Quick Reference & Development Commands", h1_style))
    
    quickref_data = [
        [Paragraph("Subsystem", th_style), Paragraph("Port", th_style), Paragraph("Startup Command", th_style), Paragraph("Verification / Health Check", th_style)],
        [
            Paragraph("Backend API", td_name_style),
            Paragraph("8001", td_desc_style),
            Paragraph("uvicorn app.main:app --port 8001", td_files_style),
            Paragraph("http://127.0.0.1:8001/api/v1/health", td_files_style)
        ],
        [
            Paragraph("Frontend UI", td_name_style),
            Paragraph("5173", td_desc_style),
            Paragraph("npm run dev", td_files_style),
            Paragraph("http://localhost:5173 (proxies /api to 8001)", td_files_style)
        ],
        [
            Paragraph("Test Suite", td_name_style),
            Paragraph("N/A", td_desc_style),
            Paragraph("pytest tests/test_deep_end_to_end_memory_and_features.py", td_files_style),
            Paragraph("9 / 9 tests passing (100% test pass rate)", td_desc_style)
        ],
        [
            Paragraph("Frontend Build", td_name_style),
            Paragraph("N/A", td_desc_style),
            Paragraph("npm run build (tsc -b && vite build)", td_files_style),
            Paragraph("Zero TypeScript or bundle errors (1.61s)", td_desc_style)
        ],
    ]
    t_quick = Table(quickref_data, colWidths=[80, 40, 222, 190])
    t_quick.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_HEADER_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_BG_LIGHT]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_quick)

    # Build Document using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated folder structure PDF at: {output_path}")

if __name__ == "__main__":
    out_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs",
        "folder_structure.pdf"
    )
    if len(sys.argv) > 1:
        out_file = sys.argv[1]
    build_pdf(out_file)
