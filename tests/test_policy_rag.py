"""Policy RAG: corpus loading, Pinecone path (fake client), and the offline fallback."""
import pytest

from app.core.config import settings
from app.rag.corpus import load_corpus
from app.rag import pinecone_retriever as pr
from app.rag.pinecone_retriever import PineconeRetriever


class FakeIndex:
    def __init__(self, hits=None, fail=False):
        self.hits, self.fail, self.upserts = hits or [], fail, []

    def upsert_records(self, namespace, records):
        self.upserts.append((namespace, records))

    def search(self, namespace, query, fields=None):
        if self.fail:
            raise RuntimeError("pinecone down")
        return {"result": {"hits": self.hits}}


class FakeClient:
    def __init__(self, index, exists=True):
        self.index, self.exists, self.created = index, exists, None

    def has_index(self, name):
        return self.exists

    def create_index_for_model(self, **kwargs):
        self.created = kwargs

    def describe_index(self, name):
        return type("D", (), {"host": "fake-host"})()

    def Index(self, host):
        return self.index


def _hit(chunk_id="law_sec_13", score=0.8):
    return {"_id": chunk_id, "_score": score,
            "fields": {"chunk_text": "Overtime is paid at twice the rate.", "section": "Section 13", "source": "Maharashtra Act"}}


def test_corpus_has_unique_ids_and_all_sources():
    chunks = load_corpus()
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert any(i.startswith("policy_") for i in ids)
    assert any(i.startswith("law_sec_") for i in ids)
    assert any(i.startswith("Health_Policy_2026") for i in ids)
    assert any(i.startswith("kb_") for i in ids)


def test_local_fallback_finds_relevant_chunk_without_api_key():
    passages = PineconeRetriever().search("casual leave quota maharashtra", top_k=2)
    assert passages and passages[0].score > 0
    assert "Casual Leave" in passages[0].content or "Maharashtra" in passages[0].content


def test_pinecone_path_maps_hits(monkeypatch):
    monkeypatch.setattr(settings, "PINECONE_API_KEY", "test-key")
    retriever = PineconeRetriever(client=FakeClient(FakeIndex([_hit()])))
    passages = retriever.search("overtime rate", top_k=3)
    assert [p.chunk_id for p in passages] == ["law_sec_13"]
    assert passages[0].section == "Section 13" and passages[0].citation == "Maharashtra Act"
    assert passages[0].score == pytest.approx(0.8)


def test_pinecone_failure_falls_back_and_backs_off(monkeypatch):
    monkeypatch.setattr(settings, "PINECONE_API_KEY", "test-key")
    index = FakeIndex(fail=True)
    retriever = PineconeRetriever(client=FakeClient(index))
    passages = retriever.search("casual leave quota", top_k=2)
    assert passages  # served from the local corpus
    assert retriever._unavailable_until > 0  # skips Pinecone for a while after a failure


def test_empty_pinecone_result_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings, "PINECONE_API_KEY", "test-key")
    retriever = PineconeRetriever(client=FakeClient(FakeIndex(hits=[])))
    assert retriever.search("casual leave quota", top_k=2)


def test_index_corpus_upserts_every_chunk_and_creates_missing_index(monkeypatch):
    index = FakeIndex()
    client = FakeClient(index, exists=False)
    retriever = PineconeRetriever(client=client)
    count = retriever.index_corpus()
    assert client.created["embed"]["field_map"] == {"text": pr.TEXT_FIELD}
    assert sum(len(records) for _, records in index.upserts) == count == len(load_corpus())
    assert all(ns == pr.NAMESPACE for ns, _ in index.upserts)


async def test_policy_service_returns_citations_and_escalates():
    from app.services.policy_rag_service import PolicyRAGService
    service = PolicyRAGService()
    res = await service.search_policies("overtime wage rate under the Maharashtra act")
    assert res["citations"] and res["context"]
    assert not res["requires_escalation"]

    esc = await service.search_policies("sexual harassment complaint")
    assert esc["requires_escalation"]


def test_pinecone_sdk10_hit_shape_id_and_score_are_read(monkeypatch):
    """pinecone SDK 10 returns hits with .id/.score instead of _id/_score; scores must not silently become 0."""
    from types import SimpleNamespace

    hit = SimpleNamespace(id="law_sec_13", score=0.61, fields={"chunk_text": "Overtime pay.", "section": "Section 13", "source": "Act"})
    monkeypatch.setattr(settings, "PINECONE_API_KEY", "test-key")
    index = FakeIndex()
    index.search = lambda namespace, query, fields=None: SimpleNamespace(result=SimpleNamespace(hits=[hit]))
    passages = PineconeRetriever(client=FakeClient(index)).search("overtime", top_k=1)
    assert passages[0].chunk_id == "law_sec_13" and passages[0].score == pytest.approx(0.61)
