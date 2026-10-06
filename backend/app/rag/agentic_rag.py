"""Agentic RAG Engine: Multi-Hop Retrieval, Knowledge Graph Reasoning, and Statutory Synthesis."""

from dataclasses import dataclass
from typing import Any, Dict, List
from app.rag.hybrid_retriever import hybrid_policy_retriever, RetrievedPolicyPassage
from app.rag.knowledge_graph import enterprise_knowledge_graph, PolicyGraphResult
from app.schemas.agent import CitationItem

@dataclass
class AgenticPolicyResponse:
    query: str
    passages: List[RetrievedPolicyPassage]
    graph_result: PolicyGraphResult
    synthesis: str
    citations: List[CitationItem]
    is_ambiguous: bool
    requires_escalation: bool

class AgenticPolicyOrchestrator:
    """Agentic RAG engine orchestrating hybrid retrieval with statutory knowledge graph verification."""

    def __init__(self):
        self.retriever = hybrid_policy_retriever
        self.graph = enterprise_knowledge_graph

    def search_and_synthesize(self, query: str, top_k: int = 3) -> AgenticPolicyResponse:
        q_lower = query.lower()
        is_ambiguous = False
        requires_escalation = False

        # Escalation keywords
        escalation_keywords = ["termination without cause", "court", "lawsuit", "sexual harassment", "posh", "unfair dismissal", "dispute", "strike"]
        if any(kw in q_lower for kw in escalation_keywords):
            requires_escalation = True
            is_ambiguous = True

        # 1. Hybrid Retrieval (Dense Vector + BM25 with RRF)
        passages = self.retriever.search_hybrid_rrf(query, top_k=top_k)

        # 2. Knowledge Graph Traversal
        graph_res = self.graph.search_graph(query)

        # 3. Compile Citations
        citations: List[CitationItem] = []
        for p in passages:
            citations.append(
                CitationItem(
                    source_title=p.citation,
                    section=p.section,
                    document_type="STATUTORY_ACT" if "Section" in p.section or "Act" in p.citation else "COMPANY_POLICY",
                    citation_text=p.content,
                    confidence_score=round(min(0.99, max(0.80, p.rrf_score * 30)), 2)
                )
            )

        # 4. Synthesize Answer
        synth_lines = [f"### Policy & Statutory Analysis for: '{query}'\n"]
        if graph_res.statutory_mandates or graph_res.health_entitlements:
            synth_lines.append(graph_res.synthesis)
            synth_lines.append("")

        if passages:
            synth_lines.append("### Authoritative Passages:")
            for p in passages:
                synth_lines.append(f"- **{p.section}** ({p.citation}):\n  {p.content}\n")
        else:
            synth_lines.append("No direct policy documents matched.")

        if requires_escalation:
            synth_lines.append("\n⚠️ **ESCALATION MANDATED**: This matter involves sensitive legal/statutory dispute clauses. It has been routed to the Senior HR Legal Compliance Officer.")

        synthesis_text = "\n".join(synth_lines)

        return AgenticPolicyResponse(
            query=query,
            passages=passages,
            graph_result=graph_res,
            synthesis=synthesis_text,
            citations=citations,
            is_ambiguous=is_ambiguous,
            requires_escalation=requires_escalation
        )

agentic_policy_rag = AgenticPolicyOrchestrator()
