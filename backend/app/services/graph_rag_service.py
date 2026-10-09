"""
PeopleOps — Statutory Knowledge Graph & Policy Retrieval Service
==================================================================
Manages local & Neo4j graph traversal for Maharashtra labour laws and HR Handbook rules.
Provides structured section citations (Sections 13, 14, 15, 18) and escalation checks.
For hybrid vector + BM25 chunk search, see `app.rag.hybrid_retriever`.
"""
import asyncio
import json
import os
import threading
import time
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
        self._search_cache: Dict[str, Dict[str, Any]] = {}
        self._graph_cache: Optional[Dict[str, Any]] = None
        self._graph_cache_time: float = 0.0
        self._lock = threading.Lock()
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
        if self._driver is not None:
            return self._driver
        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=5.0,
                max_connection_lifetime=300,
                max_connection_pool_size=50
            )
            self._driver.verify_connectivity()
            return self._driver
        except Exception:
            self._driver = None
            return None

    def _query_neo4j_sync(self, query: str) -> List[Dict[str, Any]]:
        """Synchronous Neo4j cypher runner designed for offloading to async threadpool."""
        driver = self._get_neo4j_driver()
        if not driver:
            return []
        try:
            with driver.session() as session:
                cypher = """
                MATCH (n)
                WHERE (n:PolicyNode OR n:Section OR n:StatutoryAct)
                  AND (
                    toLower(coalesce(n.title, '')) CONTAINS toLower($query) OR 
                    toLower(coalesce(n.name, '')) CONTAINS toLower($query) OR 
                    toLower(coalesce(n.provision, '')) CONTAINS toLower($query) OR 
                    toLower(coalesce(n.content, '')) CONTAINS toLower($query)
                  )
                OPTIONAL MATCH (n)-[r]->(target)
                RETURN coalesce(n.title, n.name) AS title,
                       coalesce(n.content, n.provision, n.description) AS content,
                       coalesce(n.citation, n.section_number, n.code) AS section,
                       labels(n)[0] AS source,
                       type(r) AS relation,
                       coalesce(target.title, target.name) AS related_to,
                       r.rule AS rule
                LIMIT 5
                """
                result = session.run(cypher, query=query)
                return [record.data() for record in result]
        except Exception:
            return []

    async def search_policies(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Ultra-fast hybrid retrieval combining ChromaDB dense vectors, BM25, and Neo4j/NetworkX ontology graph concurrently."""
        q_norm = query.strip().lower()
        now = time.time()

        # 0. Check in-memory query cache (TTL: 120 seconds)
        with self._lock:
            cached_entry = self._search_cache.get(q_norm)
            if cached_entry and (now - cached_entry["cached_at"] < 120):
                return cached_entry["data"]

        from app.rag.hybrid_retriever import hybrid_policy_retriever
        from app.rag.knowledge_graph import enterprise_knowledge_graph

        citations: List[CitationItem] = []
        is_ambiguous = False
        requires_escalation = False

        # 1. Escalation Checks
        escalation_keywords = [
            "termination without cause", "court", "lawsuit", "sexual harassment",
            "posh", "unfair dismissal", "dispute", "strike"
        ]
        if any(kw in q_norm for kw in escalation_keywords):
            requires_escalation = True
            is_ambiguous = True

        # 2, 3, 4. Run Neo4j Cypher traversal, ChromaDB+BM25 search, and NetworkX ontology concurrently!
        async def run_hybrid_vector():
            return await asyncio.to_thread(hybrid_policy_retriever.search_hybrid_rrf, query, top_k=top_k)

        async def run_networkx_graph():
            return await asyncio.to_thread(enterprise_knowledge_graph.search_graph, query)

        async def run_neo4j():
            return await asyncio.to_thread(self._query_neo4j_sync, query)

        retrieved_passages, graph_res, neo4j_matched = await asyncio.gather(
            run_hybrid_vector(),
            run_networkx_graph(),
            run_neo4j(),
            return_exceptions=True
        )

        if isinstance(retrieved_passages, Exception):
            retrieved_passages = []
        if isinstance(graph_res, Exception):
            graph_res = type('GraphRes', (), {'synthesis': '', 'statutory_mandates': [], 'health_entitlements': []})()
        if isinstance(neo4j_matched, Exception):
            neo4j_matched = []

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
                if ltype in q_norm or any(word in name for word in q_norm.split() if len(word) > 3):
                    citations.append(CitationItem(
                        source_title="Enterprise Leave Policy 2026",
                        section=pol.get("code", "General"),
                        document_type="COMPANY_POLICY",
                        citation_text=f"{pol['name']}: Quota {pol.get('annual_quota')} days ({pol.get('accrual_frequency')}).",
                        confidence_score=0.90
                    ))

        # 7. Synthesize Rich Context
        context_parts = []
        if getattr(graph_res, 'synthesis', None) and (getattr(graph_res, 'statutory_mandates', None) or getattr(graph_res, 'health_entitlements', None)):
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

        result_payload = {
            "query": query,
            "summary": summary_text,
            "answer": summary_text,
            "context": context_text,
            "citations": citations[:top_k],
            "requires_escalation": requires_escalation,
            "is_ambiguous": is_ambiguous,
            "legal_disclaimer": "Notice: Information provided is for internal policy guidance and statutory reference under the Maharashtra Shops & Establishments Act, 2017. It does not constitute formal legal advice."
        }

        # Cache result
        with self._lock:
            self._search_cache[q_norm] = {
                "data": result_payload,
                "cached_at": now
            }
            # Limit cache size to 500 items
            if len(self._search_cache) > 500:
                oldest_k = next(iter(self._search_cache))
                del self._search_cache[oldest_k]

        return result_payload

    def get_live_graph_data(self) -> Dict[str, Any]:
        """Fetches all live nodes and relationships with in-memory caching for zero-latency UI rendering."""
        now = time.time()
        with self._lock:
            if self._graph_cache and (now - self._graph_cache_time < 60.0):
                return self._graph_cache

        driver = self._get_neo4j_driver()
        if driver:
            try:
                with driver.session() as session:
                    nodes_res = session.run("MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props").data()
                    rels_res = session.run("""
                        MATCH (s)-[r]->(t)
                        RETURN elementId(r) AS id,
                               type(r) AS type,
                               properties(r) AS props,
                               elementId(s) AS source,
                               elementId(t) AS target,
                               coalesce(s.section_id, s.code, s.name) AS source_key,
                               coalesce(t.section_id, t.code, t.name) AS target_key
                    """).data()

                    formatted_nodes = []
                    for n in nodes_res:
                        props = n.get("props", {})
                        lbls = n.get("labels", [])
                        category = lbls[0] if lbls else "Entity"
                        title = props.get("title") or props.get("name") or props.get("code") or "Node"
                        short_label = props.get("section_number") or props.get("code") or props.get("name") or title
                        formatted_nodes.append({
                            "id": n["id"],
                            "key": props.get("section_id") or props.get("code") or props.get("name") or n["id"],
                            "title": title,
                            "label": short_label,
                            "category": category,
                            "labels": lbls,
                            "properties": props
                        })

                    formatted_rels = []
                    for r in rels_res:
                        formatted_rels.append({
                            "id": r["id"],
                            "source": r["source"],
                            "target": r["target"],
                            "source_key": r["source_key"],
                            "target_key": r["target_key"],
                            "type": r["type"],
                            "rule": r.get("props", {}).get("rule") or r.get("props", {}).get("protocol") or r.get("props", {}).get("standard") or "",
                            "properties": r.get("props", {})
                        })

                    res = {
                        "status": "connected",
                        "engine": "Neo4j Aura Cloud",
                        "database_uri": settings.NEO4J_URI.split("@")[-1] if "@" in settings.NEO4J_URI else settings.NEO4J_URI,
                        "nodes_count": len(formatted_nodes),
                        "relationships_count": len(formatted_rels),
                        "nodes": formatted_nodes,
                        "links": formatted_rels
                    }
                    with self._lock:
                        self._graph_cache = res
                        self._graph_cache_time = now
                    return res
            except Exception:
                pass

        return {
            "status": "fallback_local",
            "engine": "Local Statutory Graph",
            "database_uri": "in-memory-ontology",
            "nodes_count": 0,
            "relationships_count": 0,
            "nodes": [],
            "links": []
        }

graph_rag_service = GraphRAGService()
