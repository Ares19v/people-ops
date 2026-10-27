"""Policy corpus loader: turns the statutory / policy data files into retrievable chunks."""

import json
import os
from typing import List

from app.rag.chunking import PolicyChunk, hierarchical_chunker

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")


def _read_json(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_corpus() -> List[PolicyChunk]:
    """Builds every chunk that gets indexed. Chunk ids are stable so re-indexing is an idempotent upsert."""
    chunks: List[PolicyChunk] = []

    # 1. Occupational health markdown, split on headings
    health_path = os.path.join(DATA_DIR, "health_policy_2026.md")
    if os.path.exists(health_path):
        with open(health_path, "r", encoding="utf-8") as f:
            chunks.extend(hierarchical_chunker.chunk_markdown(f.read(), doc_name="Health_Policy_2026"))

    # 2. Company policies
    for p in _read_json("company_policy_2026.json").get("policies", []):
        content = (
            f"Policy: {p['name']} ({p.get('code')})\n"
            f"Annual Quota: {p.get('annual_quota')} days. Accrual: {p.get('accrual_frequency')}. "
            f"Carry Forward: {p.get('carry_forward_rules')}. Statutory Baseline: {p.get('statutory_comparison')}"
        )
        chunks.append(PolicyChunk(
            chunk_id=f"policy_{p.get('code', 'gen')}",
            content=content,
            section_title=p.get("name", "Policy"),
            document_source=p.get("citation", "Company Policy Manual 2026"),
            token_count=len(content.split()),
        ))

    # 3. Maharashtra labour law sections
    for sec in _read_json("maharashtra_labour_law.json").get("sections", []):
        content = (
            f"Statutory Provision: {sec['title']} (Section {sec['section']})\n"
            f"{sec['content']}\nReference: {sec.get('act', 'Maharashtra Shops and Establishments Act 2017')}"
        )
        chunks.append(PolicyChunk(
            chunk_id=f"law_sec_{sec['section'].replace('(', '_').replace(')', '_')}",
            content=content,
            section_title=f"Section {sec['section']}: {sec['title']}",
            document_source=sec.get("citation", "Maharashtra Act LXI of 2017"),
            token_count=len(content.split()),
        ))

    # 4. Cross-linked statutory / policy knowledge base (each entry carries its related rules inline)
    for entry in _read_json("policy_knowledge_base.json").get("entries", []):
        chunks.append(PolicyChunk(
            chunk_id=entry["id"],
            content=entry["content"],
            section_title=entry["title"],
            document_source=entry.get("citation", "Policy Knowledge Base"),
            token_count=len(entry["content"].split()),
        ))

    return chunks
