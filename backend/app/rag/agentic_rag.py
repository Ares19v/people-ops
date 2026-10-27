"""Policy RAG orchestrator: Pinecone retrieval, escalation detection, and statutory synthesis (sync API)."""

from dataclasses import dataclass
from typing import List
from app.rag.pinecone_retriever import policy_retriever, RetrievedPolicyPassage
from app.schemas.agent import CitationItem
from app.services.policy_rag_service import ESCALATION_KEYWORDS, confidence_for, document_type_for

@dataclass
class AgenticPolicyResponse:
    query: str
    passages: List[RetrievedPolicyPassage]
    synthesis: str
    citations: List[CitationItem]
    is_ambiguous: bool
    requires_escalation: bool

class AgenticPolicyOrchestrator:
    """Policy RAG engine used by the synchronous LangGraph and health agents."""

    def __init__(self):
        self.retriever = policy_retriever

    def search_and_synthesize(self, query: str, top_k: int = 3) -> AgenticPolicyResponse:
        requires_escalation = any(kw in query.lower() for kw in ESCALATION_KEYWORDS)

        passages = self.retriever.search(query, top_k=top_k)

        citations = [
            CitationItem(
                source_title=p.citation,
                section=p.section,
                document_type=document_type_for(p.section, p.citation),
                citation_text=p.content,
                confidence_score=confidence_for(p.score),
            )
            for p in passages
        ]

        synth_lines = [f"### Policy & Statutory Analysis for: '{query}'\n"]
        if passages:
            synth_lines.append("### Authoritative Passages:")
            for p in passages:
                synth_lines.append(f"- **{p.section}** ({p.citation}):\n  {p.content}\n")
        else:
            synth_lines.append("No direct policy documents matched.")

        if requires_escalation:
            synth_lines.append("\n⚠️ **ESCALATION MANDATED**: This matter involves sensitive legal/statutory dispute clauses. It has been routed to the Senior HR Legal Compliance Officer.")

        return AgenticPolicyResponse(
            query=query,
            passages=passages,
            synthesis="\n".join(synth_lines),
            citations=citations,
            is_ambiguous=requires_escalation,
            requires_escalation=requires_escalation,
        )

agentic_policy_rag = AgenticPolicyOrchestrator()
