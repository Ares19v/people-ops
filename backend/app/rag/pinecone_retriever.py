"""Pinecone policy retriever (integrated inference) with an offline keyword fallback."""

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.rag.chunking import PolicyChunk
from app.rag.corpus import load_corpus

logger = logging.getLogger(__name__)

NAMESPACE = "policies"
TEXT_FIELD = "chunk_text"
RETRY_AFTER_SECONDS = 60.0  # how long to skip Pinecone after a failure before trying again


@dataclass
class RetrievedPolicyPassage:
    chunk_id: str
    content: str
    section: str
    citation: str
    score: float


def _tokens(text: str) -> List[str]:
    return [t for t in re.sub(r"[^a-z0-9\s]", " ", text.lower()).split() if len(t) >= 3]


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Pinecone responses expose fields as attributes or dict keys depending on the SDK version."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first(obj: Any, *names: str) -> Any:
    for name in names:
        value = _field(obj, name)
        if value is not None:
            return value
    return None


class PineconeRetriever:
    """Dense retrieval over the policy corpus using a Pinecone index with a hosted embedding model."""

    def __init__(self, client: Optional[Any] = None):
        self._client = client
        self._index = None
        self._lock = threading.Lock()
        self._unavailable_until = 0.0
        self._chunks: Optional[List[PolicyChunk]] = None

    # ── corpus & local fallback ─────────────────────────────────────────────
    @property
    def chunks(self) -> List[PolicyChunk]:
        if self._chunks is None:
            self._chunks = load_corpus()
        return self._chunks

    def search_local(self, query: str, top_k: int = 3) -> List[RetrievedPolicyPassage]:
        """Token-overlap ranking over the local corpus; used when Pinecone is unconfigured or unreachable."""
        q_tokens = set(_tokens(query))
        if not q_tokens:
            return []
        scored = []
        for chunk in self.chunks:
            overlap = len(q_tokens & set(_tokens(f"{chunk.section_title} {chunk.content}")))
            if overlap:
                scored.append((overlap / len(q_tokens), chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            RetrievedPolicyPassage(c.chunk_id, c.content, c.section_title, c.document_source, round(s, 4))
            for s, c in scored[:top_k]
        ]

    # ── Pinecone ────────────────────────────────────────────────────────────
    def _get_client(self):
        if self._client is None:
            from pinecone import Pinecone
            self._client = Pinecone(api_key=settings.PINECONE_API_KEY)
        return self._client

    def _get_index(self):
        with self._lock:
            if self._index is None:
                host = self._get_client().describe_index(settings.PINECONE_INDEX).host
                self._index = self._get_client().Index(host=host)
            return self._index

    def ensure_index(self) -> None:
        """Creates the integrated-inference index if it doesn't exist yet (idempotent)."""
        pc = self._get_client()
        if not pc.has_index(settings.PINECONE_INDEX):
            pc.create_index_for_model(
                name=settings.PINECONE_INDEX,
                cloud=settings.PINECONE_CLOUD,
                region=settings.PINECONE_REGION,
                embed={"model": settings.PINECONE_EMBED_MODEL, "field_map": {"text": TEXT_FIELD}},
            )

    def index_corpus(self) -> int:
        """Embeds and upserts every corpus chunk. Chunk ids are stable, so re-running overwrites in place."""
        self.ensure_index()
        index = self._get_index()
        records = [
            {"_id": c.chunk_id, TEXT_FIELD: c.content, "section": c.section_title, "source": c.document_source}
            for c in self.chunks
        ]
        for start in range(0, len(records), 90):
            index.upsert_records(NAMESPACE, records[start:start + 90])
        return len(records)

    def search_pinecone(self, query: str, top_k: int = 3) -> List[RetrievedPolicyPassage]:
        res = self._get_index().search(
            namespace=NAMESPACE,
            query={"inputs": {"text": query}, "top_k": top_k},
            fields=[TEXT_FIELD, "section", "source"],
        )
        hits = _field(_field(res, "result"), "hits", []) or []
        passages = []
        for hit in hits:
            fields = _field(hit, "fields", {}) or {}
            passages.append(RetrievedPolicyPassage(
                chunk_id=_first(hit, "_id", "id"),   # SDK 8 names these _id/_score, SDK 10 id/score
                content=_field(fields, TEXT_FIELD, ""),
                section=_field(fields, "section", ""),
                citation=_field(fields, "source", ""),
                score=float(_first(hit, "_score", "score") or 0.0),
            ))
        return passages

    # ── public API ──────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 3) -> List[RetrievedPolicyPassage]:
        """Pinecone dense search; falls back to local keyword ranking if unconfigured, failing, or empty."""
        if settings.PINECONE_API_KEY and time.time() >= self._unavailable_until:
            try:
                passages = self.search_pinecone(query, top_k)
                if passages:
                    return passages
            except Exception as exc:
                self._unavailable_until = time.time() + RETRY_AFTER_SECONDS
                logger.warning("Pinecone search failed, using local fallback for %.0fs: %s", RETRY_AFTER_SECONDS, exc)
        return self.search_local(query, top_k)

    def health(self) -> Dict[str, Any]:
        if not settings.PINECONE_API_KEY:
            return {"status": "local_fallback", "engine": "Local keyword search (PINECONE_API_KEY not set)"}
        try:
            stats = self._get_index().describe_index_stats()
            namespaces = _field(stats, "namespaces", {}) or {}
            count = _field(namespaces.get(NAMESPACE), "vector_count", 0) if NAMESPACE in namespaces else 0
            return {"status": "connected", "engine": f"Pinecone ({settings.PINECONE_INDEX})", "records": count}
        except Exception as exc:
            return {"status": "unavailable", "engine": "Pinecone", "error": str(exc)}


policy_retriever = PineconeRetriever()
