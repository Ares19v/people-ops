import json
import os
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.schemas.agent import CitationItem

try:
    from neo4j import AsyncGraphDatabase, GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

class GraphRAGService:
    def __init__(self):
        self._driver = None
        self._local_graph = None
        self._load_local_data()

    def _load_local_data(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        law_path = os.path.join(base_dir, "data", "maharashtra_labour_law.json")
        pol_path = os.path.join(base_dir, "data", "company_policy_2026.json")
        
        self.law_data = {}
        self.policy_data = {}

        if os.path.exists(law_path):
            with open(law_path, "r", encoding="utf-8") as f:
                self.law_data = json.load(f)
        if os.path.exists(pol_path):
            with open(pol_path, "r", encoding="utf-8") as f:
                self.policy_data = json.load(f)

    def _get_neo4j_driver(self):
        if not NEO4J_AVAILABLE:
            return None
        if not self._driver:
            try:
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                    connection_timeout=2.0
                )
                self._driver.verify_connectivity()
            except Exception:
                self._driver = None
        return self._driver

    async def search_policies(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Hybrid retrieval combining graph ontology and policy documents."""
        q_lower = query.lower()
        citations: List[CitationItem] = []
        matched_chunks = []
        is_ambiguous = False
        requires_escalation = False

        # Check for sensitive/escalation terms (termination disputes, disciplinary actions, legal notice)
        escalation_keywords = ["termination without cause", "court", "lawsuit", "sexual harassment", "posh", "unfair dismissal", "dispute", "strike"]
        if any(kw in q_lower for kw in escalation_keywords):
            requires_escalation = True
            is_ambiguous = True

        # Search company policies
        for pol in self.policy_data.get("policies", []):
            code = pol.get("code", "").lower()
            name = pol.get("name", "").lower()
            ltype = pol.get("leave_type", "").lower()
            
            if ltype in q_lower or any(word in name for word in q_lower.split() if len(word) > 3):
                content = (
                    f"Policy: {pol['name']} ({pol['code']})\n"
                    f"- Quota: {pol.get('annual_quota')}\n"
                    f"- Accrual: {pol.get('accrual_frequency')}\n"
                    f"- Max Accumulation: {pol.get('max_accumulation')} days\n"
                    f"- Carry Forward: {pol.get('carry_forward_rules')}\n"
                    f"- Statutory Baseline: {pol.get('statutory_comparison')}"
                )
                matched_chunks.append({
                    "title": pol["name"],
                    "content": content,
                    "type": "COMPANY_POLICY",
                    "citation": pol.get("citation", "Company Policy Manual 2026")
                })
                citations.append(CitationItem(
                    source_title="Enterprise Leave Policy 2026",
                    section=pol.get("code", "General"),
                    document_type="COMPANY_POLICY",
                    citation_text=f"{pol['name']}: Annual quota of {pol.get('annual_quota')} days ({pol.get('accrual_frequency')}). {pol.get('carry_forward_rules', '')} Statutory baseline: {pol.get('statutory_comparison', '')}",
                    confidence_score=0.98
                ))

        # Search Maharashtra Labour Law provisions
        for sec in self.law_data.get("sections", []):
            sec_num = sec.get("section", "").lower()
            sec_title = sec.get("title", "").lower()
            sec_ltype = sec.get("leave_type", "").lower()

            matches_law = (
                "maharashtra" in q_lower or
                "labour law" in q_lower or
                "statutory" in q_lower or
                "act" in q_lower or
                "overtime" in q_lower or
                sec_ltype in q_lower
            )

            if matches_law and (sec_ltype in q_lower or any(word in sec_title for word in q_lower.split() if len(word) > 3)):
                content = (
                    f"Statutory Provision: {sec['title']} (Section {sec['section']})\n"
                    f"{sec['content']}\n"
                    f"Act: {self.law_data.get('source')}"
                )
                matched_chunks.append({
                    "title": f"Maharashtra Act LXI of 2017 - Section {sec['section']}",
                    "content": content,
                    "type": "STATUTORY_LAW",
                    "citation": sec.get("citation", "Maharashtra Act LXI of 2017")
                })
                citations.append(CitationItem(
                    source_title=self.law_data.get("source", "Maharashtra Labour Law"),
                    section=f"Section {sec['section']}",
                    document_type="STATUTORY_LAW",
                    citation_text=f"Section {sec['section']} ({sec['title']}): {sec['content']}",
                    confidence_score=0.95
                ))

        # Synthesize context and rich summary
        context_text = "\n\n---\n\n".join(c["content"] for c in matched_chunks[:top_k])
        if not context_text:
            summary_text = "No direct policy match found in the current index. Escalating to human HR advisor."
            context_text = summary_text
            requires_escalation = True
        else:
            summary_parts = []
            for chunk in matched_chunks[:top_k]:
                summary_parts.append(f"• {chunk['title']}: {chunk['content'].splitlines()[1] if len(chunk['content'].splitlines()) > 1 else chunk['content']}")
            summary_text = f"Synthesized analysis for '{query}':\n" + "\n".join(summary_parts)

        return {
            "query": query,
            "summary": summary_text,
            "answer": summary_text,
            "context": context_text,
            "citations": citations[:top_k],
            "requires_escalation": requires_escalation,
            "is_ambiguous": is_ambiguous,
            "legal_disclaimer": "Notice: Information provided is for internal policy guidance and statutory reference under the Maharashtra Shops & Establishments Act, 2017. It does not constitute formal legal advice."
        }

graph_rag_service = GraphRAGService()
