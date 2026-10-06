"""Hierarchical Markdown Chunking Strategies for Statutory Labor Acts and Health Policies."""

from dataclasses import dataclass
import re
from typing import List

@dataclass
class PolicyChunk:
    chunk_id: str
    content: str
    section_title: str
    document_source: str
    token_count: int

class HierarchicalChunker:
    """Chunks legal acts and enterprise policy handbooks by statutory headings and sections."""

    @staticmethod
    def chunk_markdown(text: str, doc_name: str = "statutory_act") -> List[PolicyChunk]:
        """Preserves legal clause integrity by splitting at Markdown headers (# or ## or ###)."""
        header_pattern = re.compile(r"(^#{1,3}\s+.+$)", re.MULTILINE)
        parts = header_pattern.split(text)

        chunks: List[PolicyChunk] = []
        current_section = "General Overview"
        chunk_idx = 0

        for part in parts:
            part_clean = part.strip()
            if not part_clean:
                continue

            if part_clean.startswith("#"):
                current_section = part_clean.lstrip("#").strip()
            else:
                chunk_idx += 1
                chunks.append(
                    PolicyChunk(
                        chunk_id=f"{doc_name}_chunk_{chunk_idx}",
                        content=part_clean,
                        section_title=current_section,
                        document_source=doc_name,
                        token_count=len(part_clean.split()),
                    )
                )

        return chunks

hierarchical_chunker = HierarchicalChunker()
