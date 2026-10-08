"""
PeopleOps — Statutory Knowledge Graph & Policy Retrieval Service
==================================================================
Manages local & Neo4j graph traversal for Maharashtra labour laws and HR Handbook rules.
Provides structured section citations (Sections 13, 14, 15, 18) and escalation checks.
For hybrid vector + BM25 chunk search, see `app.rag.hybrid_retriever`.
"""
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
        self._neo4j_tested = False
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
        if not NEO4J_AVAILABLE or self._neo4j_tested:
            return self._driver
        self._neo4j_tested = True
        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=0.3
            )
            self._driver.verify_connectivity()
        except Exception:
            self._driver = None
        return self._driver

    async def search_policies(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Hybrid retrieval combining ChromaDB dense vectors, BM25, and NetworkX ontology graph."""
        from app.rag.hybrid_retriever import hybrid_policy_retriever
        from app.rag.knowledge_graph import enterprise_knowledge_graph

        q_lower = query.lower()
        citations: List[CitationItem] = []
        is_ambiguous = False
        requires_escalation = False

        # 1. Escalation Checks
        escalation_keywords = [
            "termination without cause", "court", "lawsuit", "sexual harassment",
            "posh", "unfair dismissal", "dispute", "strike"
        ]
        if any(kw in q_lower for kw in escalation_keywords):
            requires_escalation = True
            is_ambiguous = True

        # 2. Live Neo4j Cypher Traversal (if live database connected)
        driver = self._get_neo4j_driver()
        neo4j_matched = []
        if driver:
            try:
                with driver.session() as session:
                    cypher = """
                    MATCH (n:PolicyNode)
                    WHERE toLower(n.name) CONTAINS toLower($query) OR toLower(n.content) CONTAINS toLower($query)
                    RETURN n.title AS title, n.content AS content, n.section AS section, n.source AS source
                    LIMIT 3
                    """
                    result = session.run(cypher, query=query)
                    for record in result:
                        neo4j_matched.append(record.data())
            except Exception:
                pass

        # 3. Real ChromaDB Dense Vector + BM25 Sparse Search with RRF
        retrieved_passages = hybrid_policy_retriever.search_hybrid_rrf(query, top_k=top_k)

        # 4. Real NetworkX Knowledge Graph Traversal
        graph_res = enterprise_knowledge_graph.search_graph(query)

        # 5. Assemble Citations
        for p in retrieved_passages:
            citations.append(CitationItem(
                source_title=p.citation,
                section=p.section,
                document_type="STATUTORY_LAW" if "Section" in p.section or "Act" in p.citation else "COMPANY_POLICY",
                citation_text=p.content,
                confidence_score=round(min(0.99, max(0.85, p.rrf_score * 35)), 2)
            ))

        # Include any live Neo4j citations
        for nr in neo4j_matched:
            citations.append(CitationItem(
                source_title=nr.get("source", "Neo4j Knowledge Graph"),
                section=nr.get("section", "General"),
                document_type="ENTERPRISE_GRAPH",
                citation_text=nr.get("content", ""),
                confidence_score=0.99
            ))

        # 6. Fallback local scan if neither vector nor graph matched
        if not citations:
            for pol in self.policy_data.get("policies", []):
                name = pol.get("name", "").lower()
                ltype = pol.get("leave_type", "").lower()
                if ltype in q_lower or any(word in name for word in q_lower.split() if len(word) > 3):
                    citations.append(CitationItem(
                        source_title="Enterprise Leave Policy 2026",
                        section=pol.get("code", "General"),
                        document_type="COMPANY_POLICY",
                        citation_text=f"{pol['name']}: Quota {pol.get('annual_quota')} days ({pol.get('accrual_frequency')}).",
                        confidence_score=0.90
                    ))

        # 7. Synthesize Rich Context
        context_parts = []
        if graph_res.synthesis and (graph_res.statutory_mandates or graph_res.health_entitlements):
            context_parts.append(graph_res.synthesis)

        for p in retrieved_passages:
            context_parts.append(f"• [{p.section}] ({p.citation}):\n{p.content}")

        context_text = "\n\n".join(context_parts)
        if not context_text:
            summary_text = "No direct statutory policy match found in the current index. Escalating to human HR advisor."
            context_text = summary_text
            requires_escalation = True
        else:
            summary_text = f"Synthesized analysis for '{query}':\n" + "\n".join(
                [f"• {c.section}: {c.citation_text[:140]}..." for c in citations[:top_k]]
            )

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
