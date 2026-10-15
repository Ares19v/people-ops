import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(45, 11 * inch - 30, "PeopleOps Enterprise — GraphRAG with Neo4j Guide")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(45, 11 * inch - 34, 8.5 * inch - 45, 11 * inch - 34)

        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 45, 25, footer_text)
        self.drawString(45, 25, "Intelera PeopleOps • Statutory Knowledge Graph & Hybrid Retrieval")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(45, 35, 8.5 * inch - 45, 35)
        self.restoreState()

def build_pdf(dest_path: str):
    doc = SimpleDocTemplate(
        dest_path,
        pagesize=letter,
        leftMargin=45,
        rightMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        'Header1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=10,
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#2563EB'),
        spaceBefore=7,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6
    )

    body_bold = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        leftIndent=15,
        spaceAfter=3
    )

    quote_style = ParagraphStyle(
        'DocQuote',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E3A8A'),
        leftIndent=12,
        spaceBefore=4,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'DocCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#0F172A')
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#334155')
    )

    table_code_style = ParagraphStyle(
        'TableCode',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#1E40AF')
    )

    story = []

    # Title Block
    story.append(Paragraph("What is GraphRAG with Neo4j?", title_style))
    story.append(Paragraph("Knowledge Graph Retrieval-Augmented Generation • Architecture & Implementation Guide", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    # Introduction
    intro_p1 = "<b>Traditional RAG (Retrieval-Augmented Generation)</b> converts policy documents into text chunks, turns them into numbers (vectors), and looks for paragraphs that <i>'sound similar'</i> to the user's question."
    story.append(Paragraph(intro_p1, body_style))

    # The Problem Callout Box
    prob_title = "<font color='#991B1B'><b>The Problem with Traditional Vector RAG:</b></font>"
    prob_desc = "In legal and HR compliance, <i>'similar-sounding'</i> is not enough. If an employee asks:"
    prob_query = '<b>&ldquo;I worked 11 hours today. How much overtime do I get under Maharashtra law?&rdquo;</b>'
    prob_reason = "A standard vector search might return random mentions of overtime, but it doesn't understand the relationship between:"
    prob_b1 = "&bull; <b>The Act:</b> Maharashtra Shops & Establishments Act 2017"
    prob_b2 = "&bull; <b>Section 13:</b> Daily work limit is 9 hours"
    prob_b3 = "&bull; <b>Section 14:</b> Hours beyond 9 mandate 2.0x double hourly pay"
    prob_b4 = "&bull; <b>Company Overtime Policy:</b> Must be pre-approved by the manager"

    prob_box_content = [
        [Paragraph(prob_title, body_style)],
        [Paragraph(prob_desc, body_style)],
        [Paragraph(prob_query, quote_style)],
        [Paragraph(prob_reason, body_style)],
        [Paragraph(prob_b1, bullet_style)],
        [Paragraph(prob_b2, bullet_style)],
        [Paragraph(prob_b3, bullet_style)],
        [Paragraph(prob_b4, bullet_style)]
    ]
    prob_table = Table(prob_box_content, colWidths=[7.2 * inch])
    prob_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF2F2')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FCA5A5')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(prob_table)
    story.append(Spacer(1, 8))

    # The Solution Callout Box
    sol_title = "<font color='#065F46'><b>The GraphRAG Solution:</b></font>"
    sol_desc = "GraphRAG connects the dots as a web of facts (a Knowledge Graph in Neo4j). Instead of just searching text, the system traverses exact relationships between legal sections, statutory acts, and company policies to produce deterministic, non-hallucinated answers."
    sol_table = Table([[Paragraph(sol_title, body_style)], [Paragraph(sol_desc, body_style)]], colWidths=[7.2 * inch])
    sol_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ECFDF5')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#6EE7B7')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sol_table)
    story.append(Spacer(1, 10))

    # Section 1: The Schema
    story.append(Paragraph("1. The Schema (Nodes & Relationships in Neo4j)", h1_style))
    story.append(Paragraph("Our Neo4j Aura cloud database stores an ontology graph with <b>18 Nodes</b> and <b>16 Relationships</b>:", body_style))

    # Visual Schema Diagram in Box
    diagram_lines = (
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>(StatutoryAct)</b><br/>"
        "&nbsp;&nbsp;&nbsp;\"Maharashtra Act 2017\"<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼ <b>CONTAINS_SECTION</b><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>(Section)</b><br/>"
        "&nbsp;&nbsp;&nbsp;\"Section 14: Overtime\"<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼ <b>GOVERNS_POLICY</b><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>(PolicyNode)</b><br/>"
        "\"Intelera Overtime Policy\"<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼ <b>MANDATES_INVARIANT</b><br/>"
        "&nbsp;&nbsp;&nbsp;<b>[2.0x Double Wage Rate]</b>"
    )
    diagram_table = Table([[Paragraph(diagram_lines, code_style)]], colWidths=[7.2 * inch])
    diagram_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
    ]))
    story.append(diagram_table)
    story.append(Spacer(1, 6))

    # Node Types
    story.append(Paragraph("<b>Node Types (What exists):</b>", h2_style))
    story.append(Paragraph("&bull; <b>StatutoryAct:</b> The governing legal framework (e.g., <i>Maharashtra Shops & Establishments Act 2017</i>, <i>DPDP Act 2023</i>, <i>Maternity Benefit Act 1961</i>).", bullet_style))
    story.append(Paragraph("&bull; <b>Section:</b> The exact legal clauses (e.g., <i>Section 18: Leave Accrual & Accumulation</i>, <i>Section 13: Standard Hours</i>, <i>Section 14: Overtime</i>).", bullet_style))
    story.append(Paragraph("&bull; <b>PolicyNode:</b> Company-specific handbooks (e.g., <i>Earned Leave Policy</i>, <i>Sick Leave Policy</i>, <i>Health Benefits Plan</i>).", bullet_style))

    # Relationship Types
    story.append(Paragraph("<b>Relationship Types (How they connect):</b>", h2_style))
    story.append(Paragraph("&bull; <b>CONTAINS_SECTION:</b> An Act contains specific statutory sections.", bullet_style))
    story.append(Paragraph("&bull; <b>GOVERNS_POLICY:</b> A statutory law governs a company internal policy.", bullet_style))
    story.append(Paragraph("&bull; <b>MANDATES_INVARIANT:</b> A statutory rule that cannot be broken (e.g., minimum 1 day leave per 20 days worked, overtime at 2.0x).", bullet_style))
    story.append(Paragraph("&bull; <b>REQUIRES_DOCUMENT:</b> (e.g., Sick leave &gt; 2 days &rarr; requires medical certificate from registered doctor).", bullet_style))

    story.append(Spacer(1, 8))

    # Section 2: Entity Extraction Logic
    story.append(Paragraph("2. Entity Extraction Logic (How Queries are Understood)", h1_style))
    story.append(Paragraph("When a user types a question in the chat:", body_style))
    story.append(Paragraph("&bull; <b>Regex & Keyword Scanning:</b> Fast regex matches statutory terms like <code>Section 18</code>, <code>Section 14</code>, <code>overtime</code>, <code>sick leave</code>, <code>Aadhaar</code>.", bullet_style))
    story.append(Paragraph("&bull; <b>Entity Mapper (entity_extractor.py):</b> Maps the user's terms to canonical node IDs in the graph (e.g., <code>\"sick leave\"</code> &rarr; <code>sec_sick_leave_cert</code> + <code>intelera_sick_leave_policy</code>).", bullet_style))
    story.append(Paragraph("&bull; <b>Multi-Hop Traversal:</b> Once the starting node is found, it traverses 1 or 2 hops outwards to pull connected statutory rules, caps, and required documents.", bullet_style))
    story.append(Paragraph("&bull; <b>Context Synthesis:</b> Combines the graph path into clear facts injected directly into the Policy Agent's prompt.", bullet_style))

    story.append(Spacer(1, 8))

    # Section 3: Libraries Table
    story.append(Paragraph("3. Which Libraries Are We Using?", h1_style))
    
    lib_data = [
        [Paragraph("Library", table_header_style), Paragraph("Role in the System", table_header_style)],
        [Paragraph("neo4j", table_code_style), Paragraph("Official Python driver connecting via TLS (<code>neo4j+s://</code>) to our Neo4j Aura Cloud cluster to execute Cypher queries.", table_cell_style)],
        [Paragraph("networkx", table_code_style), Paragraph("Fast in-memory Python graph library used as an ultra-fast local cache for instant multi-hop traversals.", table_cell_style)],
        [Paragraph("chromadb", table_code_style), Paragraph("Local vector database for dense semantic embeddings.", table_cell_style)],
        [Paragraph("rank-bm25", table_code_style), Paragraph("BM25 sparse keyword search algorithm.", table_cell_style)],
        [Paragraph("pydantic (v2)", table_code_style), Paragraph("Validates schemas (<code>NodeSchema</code>, <code>RelationshipSchema</code>, <code>GraphTraversalResult</code>).", table_cell_style)]
    ]
    lib_table = Table(lib_data, colWidths=[1.5 * inch, 5.7 * inch])
    lib_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#94A3B8')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(lib_table)

    story.append(Spacer(1, 8))

    # Section 4: The 3-Way Hybrid Retrieval Pipeline
    story.append(Paragraph("4. The 3-Way Hybrid Retrieval Pipeline", h1_style))
    story.append(Paragraph("When the Policy Agent answers a question, it queries three engines concurrently:", body_style))
    story.append(Paragraph("&bull; <b>Neo4j / NetworkX Graph &rarr;</b> Provides the exact legal sections, caps, and relationships.", bullet_style))
    story.append(Paragraph("&bull; <b>ChromaDB Vector Search &rarr;</b> Finds semantically relevant policy passages.", bullet_style))
    story.append(Paragraph("&bull; <b>BM25 Keyword Search &rarr;</b> Matches exact policy phrases.", bullet_style))
    
    pipeline_summary = (
        "<b>Result Synthesis:</b> The results from all three engines are merged using "
        "<b>Reciprocal Rank Fusion (RRF)</b> to deliver a grounded, non-hallucinated response "
        "with authoritative statutory legal citations."
    )
    story.append(Spacer(1, 4))
    story.append(Paragraph(pipeline_summary, body_style))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    desktop_dir = os.path.join(os.environ["USERPROFILE"], "Desktop")
    desktop_pdf = os.path.join(desktop_dir, "GraphRAG_with_Neo4j_Guide.pdf")
    
    # Also save to docs
    repo_docs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(repo_docs, exist_ok=True)
    docs_pdf = os.path.join(repo_docs, "GraphRAG_with_Neo4j_Guide.pdf")

    print(f"Generating PDF to Desktop: {desktop_pdf}")
    build_pdf(desktop_pdf)
    print(f"Successfully generated: {desktop_pdf}")

    print(f"Generating copy to docs: {docs_pdf}")
    build_pdf(docs_pdf)
    print(f"Successfully generated: {docs_pdf}")
