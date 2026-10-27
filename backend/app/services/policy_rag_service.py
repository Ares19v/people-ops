"""
PeopleOps — Policy & Statutory Retrieval Service
================================================
Pinecone-backed RAG over Maharashtra labour law and the company HR handbook.
Provides structured section citations and escalation checks. Retrieval itself lives in
`app.rag.pinecone_retriever` (with an offline keyword fallback).
"""
import asyncio
import json
import os
import threading
import time
from typing import List, Dict, Any

from app.rag.pinecone_retriever import policy_retriever
from app.schemas.agent import CitationItem

ESCALATION_KEYWORDS = [
    "termination without cause", "court", "lawsuit", "sexual harassment",
    "posh", "unfair dismissal", "dispute", "strike",
]

LEGAL_DISCLAIMER = (
    "Notice: Information provided is for internal policy guidance and statutory reference under the "
    "Maharashtra Shops & Establishments Act, 2017. It does not constitute formal legal advice."
)


def document_type_for(section: str, citation: str) -> str:
    return "STATUTORY_LAW" if "Section" in section or "Act" in citation else "COMPANY_POLICY"


def confidence_for(score: float) -> float:
    """Retrieval similarity as the citation confidence (dense scores are typically 0.3-0.7, so no artificial floor)."""
    return round(min(0.99, max(0.0, score)), 2)


class PolicyRAGService:
    def __init__(self):
        self._search_cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._load_local_data()

    def _load_local_data(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pol_path = os.path.join(base_dir, "data", "company_policy_2026.json")
        self.policy_data = {}
        if os.path.exists(pol_path):
            with open(pol_path, "r", encoding="utf-8") as f:
                self.policy_data = json.load(f)

    async def search_policies(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Retrieves policy / statutory passages from Pinecone and assembles cited context."""
        q_norm = query.strip().lower()
        now = time.time()

        # Check in-memory query cache (TTL: 120 seconds)
        with self._lock:
            cached_entry = self._search_cache.get(q_norm)
            if cached_entry and (now - cached_entry["cached_at"] < 120):
                return cached_entry["data"]

        requires_escalation = any(kw in q_norm for kw in ESCALATION_KEYWORDS)
        is_ambiguous = requires_escalation

        try:
            passages = await asyncio.to_thread(policy_retriever.search, query, top_k)
        except Exception:
            passages = []

        citations: List[CitationItem] = [
            CitationItem(
                source_title=p.citation,
                section=p.section,
                document_type=document_type_for(p.section, p.citation),
                citation_text=p.content,
                confidence_score=confidence_for(p.score),
            )
            for p in passages
        ]

        # Last-resort scan of the policy JSON if retrieval returned nothing
        if not citations:
            for pol in self.policy_data.get("policies", []):
                name = pol.get("name", "").lower()
                ltype = pol.get("leave_type", "").lower()
                if (ltype and ltype in q_norm) or any(word in name for word in q_norm.split() if len(word) > 3):
                    citations.append(CitationItem(
                        source_title="Enterprise Leave Policy 2026",
                        section=pol.get("code", "General"),
                        document_type="COMPANY_POLICY",
                        citation_text=f"{pol['name']}: Quota {pol.get('annual_quota')} days ({pol.get('accrual_frequency')}).",
                        confidence_score=0.90,
                    ))

        context_text = "\n\n".join(f"• [{p.section}] ({p.citation}):\n{p.content}" for p in passages)
        if not context_text:
            summary_text = "No direct statutory policy match found in the current index. Escalating to human HR advisor."
            context_text = summary_text
            requires_escalation = True
        else:
            summary_text = f"Synthesized analysis for '{query}':\n" + "\n".join(
                f"• {c.section}: {c.citation_text[:140]}..." for c in citations[:max(top_k, 5)]
            )

        result_payload = {
            "query": query,
            "summary": summary_text,
            "answer": summary_text,
            "context": context_text,
            "citations": citations[:max(top_k, 5)],
            "requires_escalation": requires_escalation,
            "is_ambiguous": is_ambiguous,
            "legal_disclaimer": LEGAL_DISCLAIMER,
        }

        with self._lock:
            self._search_cache[q_norm] = {"data": result_payload, "cached_at": now}
            if len(self._search_cache) > 500:  # limit cache size
                del self._search_cache[next(iter(self._search_cache))]

        return result_payload


policy_rag_service = PolicyRAGService()
