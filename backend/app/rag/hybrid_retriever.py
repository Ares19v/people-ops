"""Hybrid Vector (ChromaDB) + BM25 Sparse Retriever with Reciprocal Rank Fusion (RRF)."""

from dataclasses import dataclass
import json
import os
from typing import Any, Dict, List, Optional
import chromadb
from rank_bm25 import BM25Okapi
from app.rag.chunking import PolicyChunk, hierarchical_chunker

@dataclass
class RetrievedPolicyPassage:
    chunk_id: str
    content: str
    section: str
    dense_score: float
    bm25_score: float
    rrf_score: float
    citation: str

HEALTH_AND_BENEFITS_MARKDOWN = """
# Enterprise Occupational Health and Medical Benefits Policy 2026
All full-time employees are covered under the Group Medical Insurance scheme with sum insured up to INR 5,00,000.
Dependents including spouse and up to 2 children are covered from day one of employment.

## Sick Leave and Medical Certification Rules
Employees are entitled to 12 days of paid Sick Leave (SL) per calendar year.
If an employee is absent due to illness for more than 2 consecutive days, a certified medical certificate from a registered medical practitioner (MBBS/MD) must be submitted via the portal.

## Workplace Ergonomics and Occupational Hazard Support
The organization provides ergonomic consultations, standing desk allowances, and mental wellness counseling through accredited partners.
In case of workplace injuries or acute medical incidents on premises, the company covers 100% of emergency medical evaluation expenses.

## Maternity and Parental Medical Benefits
In accordance with Section 5 of the Maternity Benefit Act 1961, female employees receive 26 weeks of fully paid maternity leave.
Pre-natal care expenses up to INR 50,000 are directly reimbursable under the enterprise health plan.
"""

class HybridPolicyRetriever:
    """Enterprise hybrid search engine combining persistent ChromaDB dense vectors and BM25 keywords."""

    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        chroma_path = os.path.join(base_dir, "data", "chroma_db")
        os.makedirs(chroma_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.chroma_client.get_or_create_collection(name="enterprise_policies")
        self.chunks: List[PolicyChunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self._index_all_policies()

    def _index_all_policies(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        law_path = os.path.join(base_dir, "data", "maharashtra_labour_law.json")
        pol_path = os.path.join(base_dir, "data", "company_policy_2026.json")

        all_chunks: List[PolicyChunk] = []

        # 1. Index Occupational Health Markdown
        health_chunks = hierarchical_chunker.chunk_markdown(HEALTH_AND_BENEFITS_MARKDOWN, doc_name="Health_Policy_2026")
        all_chunks.extend(health_chunks)

        # 2. Index Company Policies JSON
        if os.path.exists(pol_path):
            with open(pol_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for p in data.get("policies", []):
                    content = (
                        f"Policy: {p['name']} ({p.get('code')})\n"
                        f"Annual Quota: {p.get('annual_quota')} days. Accrual: {p.get('accrual_frequency')}. "
                        f"Carry Forward: {p.get('carry_forward_rules')}. Statutory Baseline: {p.get('statutory_comparison')}"
                    )
                    all_chunks.append(
                        PolicyChunk(
                            chunk_id=f"policy_{p.get('code', 'gen')}",
                            content=content,
                            section_title=p.get("name", "Policy"),
                            document_source=p.get("citation", "Company Policy Manual 2026"),
                            token_count=len(content.split())
                        )
                    )

        # 3. Index Maharashtra Labour Law JSON
        if os.path.exists(law_path):
            with open(law_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for sec in data.get("sections", []):
                    content = (
                        f"Statutory Provision: {sec['title']} (Section {sec['section']})\n"
                        f"{sec['content']}\nReference: {sec.get('act', 'Maharashtra Shops and Establishments Act 2017')}"
                    )
                    all_chunks.append(
                        PolicyChunk(
                            chunk_id=f"law_sec_{sec['section'].replace('(', '_').replace(')', '_')}",
                            content=content,
                            section_title=f"Section {sec['section']}: {sec['title']}",
                            document_source=sec.get("citation", "Maharashtra Act LXI of 2017"),
                            token_count=len(content.split())
                        )
                    )

        self.chunks = all_chunks

        # Build BM25
        tokenized_corpus = [c.content.lower().split() for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # Populate ChromaDB
        ids = [c.chunk_id for c in self.chunks]
        docs = [c.content for c in self.chunks]
        metas = [{"section": c.section_title, "source": c.document_source} for c in self.chunks]

        self.collection.upsert(
            ids=ids,
            documents=docs,
            metadatas=metas,
        )

    def search_dense(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, len(self.chunks))
        )
        hits = []
        if results and results["ids"] and len(results["ids"][0]) > 0:
            for idx, chunk_id in enumerate(results["ids"][0]):
                hits.append({
                    "chunk_id": chunk_id,
                    "content": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx],
                    "distance": results["distances"][0][idx] if results.get("distances") else 0.0,
                    "rank": idx + 1
                })
        return hits

    def search_sparse_bm25(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        tokenized_q = query.lower().split()
        scores = self.bm25.get_scores(tokenized_q)
        scored_pairs = list(enumerate(scores))
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        hits = []
        for rank, (chunk_idx, score) in enumerate(scored_pairs[:top_k]):
            chunk = self.chunks[chunk_idx]
            hits.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "metadata": {"section": chunk.section_title, "source": chunk.document_source},
                "score": float(score),
                "rank": rank + 1
            })
        return hits

    def search_hybrid_rrf(self, query: str, top_k: int = 3, k_constant: int = 60) -> List[RetrievedPolicyPassage]:
        """Combines ChromaDB dense rankings and BM25 sparse rankings using Reciprocal Rank Fusion."""
        dense_hits = self.search_dense(query, top_k=5)
        bm25_hits = self.search_sparse_bm25(query, top_k=5)

        rrf_scores: Dict[str, float] = {}
        passages_map: Dict[str, Dict[str, Any]] = {}

        for hit in dense_hits:
            cid = hit["chunk_id"]
            passages_map[cid] = hit
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_constant + hit["rank"]))

        for hit in bm25_hits:
            cid = hit["chunk_id"]
            if cid not in passages_map:
                passages_map[cid] = hit
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_constant + hit["rank"]))

        sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        passages: List[RetrievedPolicyPassage] = []
        for cid in sorted_cids[:top_k]:
            hit = passages_map[cid]
            passages.append(
                RetrievedPolicyPassage(
                    chunk_id=cid,
                    content=hit["content"],
                    section=hit["metadata"].get("section", "General"),
                    dense_score=round(1.0 - hit.get("distance", 0.0), 4),
                    bm25_score=round(hit.get("score", 0.0), 4),
                    rrf_score=round(rrf_scores[cid], 5),
                    citation=hit["metadata"].get("source", "Enterprise Policy")
                )
            )

        return passages

hybrid_policy_retriever = HybridPolicyRetriever()
