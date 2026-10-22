"""Langfuse integration behaviour plus the single-source-of-truth consolidations
(employee directory, policy numbers) and the removal of hardcoded recall rules."""

import json
import types

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core import directory, policy_facts
from app.core.config import settings
from app.observability import langfuse_client
from app.observability.langsmith_tracer import langsmith_tracer, resolve_user_email
from app.evaluations.llm_judge_service import llm_judge_service
from app.services.langfuse_prompt_service import langfuse_prompt_service, ManagedPrompt
from app.agents.orchestrator import LLMRootOrchestratorAgent
from app.memory.conversation_memory import ConversationMemoryManager


# ── Employee directory ────────────────────────────────────────────────────────

def test_directory_is_consistent_with_seed_data():
    # EMP-004 used to be "Rahul Sharma" in some copies and "Aarav Sharma" in others.
    assert directory.name_for("EMP-004") == "Aarav Sharma"
    assert directory.name_for("emp-004") == "Aarav Sharma"
    assert directory.email_for("EMPLOYEE") == "aarav.sharma@intelera.com"
    assert directory.email_for("USR-EMP-004") == "aarav.sharma@intelera.com"
    assert directory.email_for("aarav.sharma@intelera.com") == "aarav.sharma@intelera.com"
    assert directory.email_prefix_for("EMP-002") == "vikram.malhotra"
    assert directory.name_for("nobody") is None


def test_resolve_user_email_uses_directory_and_keeps_service_accounts():
    assert resolve_user_email("EMP-001") == "devansh.tyagi@intelera.com"
    assert resolve_user_email("USR-EVAL-999") == "eval.benchmarks@intelera.com"
    assert resolve_user_email("ADMIN") == "devansh.tyagi@intelera.com"
    assert resolve_user_email(None) == "system.orchestrator@intelera.com"
    assert resolve_user_email("New Hire") == "newhire@intelera.com"


# ── Policy numbers come from the policy file ──────────────────────────────────

def test_policy_facts_match_company_policy_file():
    assert policy_facts.quota("EL") == 18
    assert policy_facts.quota("CL") == 8
    assert policy_facts.quota("SL") == 10  # agents used to claim 12
    assert policy_facts.max_accumulation("EL") == 45
    assert policy_facts.max_accumulation("SL") == 20
    assert policy_facts.quota("LWP") is None
    assert policy_facts.days(18.0) == "18" and policy_facts.days(None) == "n/a"


def test_agent_texts_use_policy_numbers():
    from app.agents.llm_provider import MockLLMProvider
    import asyncio

    text = asyncio.run(MockLLMProvider().generate_response("", "what is the leave policy"))
    assert "18 days/year" in text and "10 days/year" in text


# ── Hardcoded recall rules are gone ───────────────────────────────────────────

def test_recall_fallback_is_generic_not_topic_specific():
    turns = [
        {"user_turn": "My emergency contact is my brother Arjun", "assistant_turn": "Noted"},
        {"user_turn": "I like to work from home on Fridays", "assistant_turn": "Noted"},
        {"user_turn": "What is the weather", "assistant_turn": "n/a"},
    ]
    picked = LLMRootOrchestratorAgent._select_relevant_recall("Who is my emergency contact?", turns)
    assert picked == ["• You mentioned: My emergency contact is my brother Arjun"]
    # No canned answers: unrelated memory yields nothing instead of invented facts.
    assert LLMRootOrchestratorAgent._select_relevant_recall("What is my neck strain history?", turns) == []
    assert LLMRootOrchestratorAgent._select_relevant_recall("anything", []) == []


# ── Langfuse client configuration ─────────────────────────────────────────────

def test_langfuse_is_disabled_under_testing_environment():
    assert settings.ENVIRONMENT == "testing"
    assert langfuse_client.is_enabled() is False
    assert langfuse_client.get_langfuse() is None
    assert langsmith_tracer.current_trace_id() is None


@pytest.mark.parametrize("raw,expected", [
    ("production", "production"),
    ("Staging EU", "staging-eu"),
    ("langfuse-internal", "development"),
    ("", "development"),
])
def test_langfuse_environment_is_sanitised(monkeypatch, raw, expected):
    monkeypatch.setattr(settings, "ENVIRONMENT", raw)
    assert langfuse_client.langfuse_environment() == expected


def test_langfuse_masks_pii_in_nested_payloads():
    masked = langfuse_client._mask(data={"q": "my aadhaar is 1234 5678 9012", "n": [1, "ok"], "x": 3})
    assert "1234 5678 9012" not in json.dumps(masked)
    assert masked["x"] == 3 and masked["n"][1] == "ok"


# ── Tracer: errors inside a span must propagate ───────────────────────────────

class _FakeObservation:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        self.log.append("enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.log.append(f"exit:{exc_type.__name__ if exc_type else None}")
        return False


def test_span_propagates_exceptions_from_caller_block(monkeypatch):
    log = []
    fake = types.SimpleNamespace(start_as_current_observation=lambda **kw: _FakeObservation(log))
    monkeypatch.setattr(langsmith_tracer, "_langfuse", fake)

    # Previously the broad except swallowed this and tried to yield twice
    # ("generator didn't stop after throw()").
    with pytest.raises(ValueError, match="boom"):
        with langsmith_tracer.span("unit", metadata={}):
            raise ValueError("boom")
    assert log == ["enter", "exit:ValueError"]


def test_span_falls_back_to_local_store_when_langfuse_setup_fails(monkeypatch):
    def broken(**kw):
        raise RuntimeError("langfuse down")

    monkeypatch.setattr(langsmith_tracer, "_langfuse", types.SimpleNamespace(start_as_current_observation=broken))
    with langsmith_tracer.span("unit-fallback", metadata={}) as obs:
        obs.update(output="done")
    assert obs.output == "done"


def test_record_generation_links_prompt_and_reports_cost(monkeypatch):
    captured = {}

    def start_observation(**kw):
        captured.update(kw)
        return types.SimpleNamespace(end=lambda: captured.setdefault("ended", True))

    monkeypatch.setattr(langsmith_tracer, "_langfuse", types.SimpleNamespace(start_observation=start_observation))
    sentinel_prompt = object()
    cost = langsmith_tracer.record_generation(
        model="gemini-3.8-flash", input_text="q", output_text="a",
        prompt_tokens=1_000_000, completion_tokens=1_000_000, prompt=sentinel_prompt,
    )
    assert cost == pytest.approx(4.5)  # 0.75 + 3.75 per 1M tokens
    assert captured["prompt"] is sentinel_prompt
    assert captured["usage_details"]["total"] == 2_000_000 and captured["ended"] is True


def test_score_uses_deterministic_ids(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(create_score=lambda **kw: calls.append(kw))
    monkeypatch.setattr(langsmith_tracer, "_langfuse", fake)
    langsmith_tracer.score("user_feedback", 1.0, trace_id="abc123abc123", data_type="BOOLEAN")
    assert calls[0]["score_id"] == "abc123abc123-user_feedback" and calls[0]["data_type"] == "BOOLEAN"


# ── Judge: live traffic only pushes measured scores ───────────────────────────

def test_judge_live_scores_are_limited_and_linked_to_trace(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_judge_service, "_langfuse", types.SimpleNamespace(create_score=lambda **kw: calls.append(kw)))
    res = llm_judge_service.evaluate_response(
        query="how many leaves", response_text="You have 18 days of Earned Leave.",
        trace_id="0123456789abcdef0123456789abcdef", latency_ms=900, live=True,
    )
    assert res.passed
    assert {c["name"] for c in calls} == {"latency_sla", "safety_and_pii_zero_leakage"}
    assert all(c["trace_id"] == "0123456789abcdef0123456789abcdef" for c in calls)
    assert all(c["score_id"].startswith("0123456789abcdef0123456789abcdef-") for c in calls)


def test_judge_benchmark_scores_include_overall(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_judge_service, "_langfuse", types.SimpleNamespace(create_score=lambda **kw: calls.append(kw)))
    llm_judge_service.evaluate_response(query="q", response_text="A structured answer: item one.", trace_id="t" * 32)
    names = {c["name"] for c in calls}
    assert "overall_quality" in names and "policy_groundedness" in names


# ── Prompt service: Langfuse outage + prompt/generation linking ───────────────

class _FakeLangfusePrompt:
    def __init__(self, text, version=7, is_fallback=False):
        self.prompt, self.version, self.is_fallback = text, version, is_fallback


def test_prompt_service_exposes_prompt_client_for_linking(monkeypatch):
    fake_prompt = _FakeLangfusePrompt("LIVE {{ organization_name }}")
    seen = {}

    def get_prompt(name, label=None, **kw):
        seen.update(kw)
        return fake_prompt

    monkeypatch.setattr(langfuse_prompt_service, "_langfuse_client", types.SimpleNamespace(get_prompt=get_prompt))
    monkeypatch.setitem(langfuse_prompt_service._cache, "unit-prompt", ManagedPrompt(
        "unit-prompt", "1", "LOCAL", "live", "local_cache", 0.0))

    text = langfuse_prompt_service.get_prompt("unit-prompt", max_age_seconds=1)
    assert text == f"LIVE {settings.ORGANIZATION_NAME}"
    assert langfuse_prompt_service.get_prompt_client("unit-prompt") is fake_prompt
    # Local template is handed to the SDK as the outage fallback, with a bounded timeout.
    assert seen["fallback"] == "LOCAL" and seen["fetch_timeout_seconds"] == 3


def test_prompt_service_survives_langfuse_outage(monkeypatch):
    def get_prompt(name, label=None, **kw):
        raise TimeoutError("langfuse unreachable")

    monkeypatch.setattr(langfuse_prompt_service, "_langfuse_client", types.SimpleNamespace(get_prompt=get_prompt))
    monkeypatch.setitem(langfuse_prompt_service._cache, "unit-outage", ManagedPrompt(
        "unit-outage", "1", "LOCAL TEMPLATE", "live", "local_cache", 0.0))
    assert langfuse_prompt_service.get_prompt("unit-outage", max_age_seconds=1) == "LOCAL TEMPLATE"
    assert langfuse_prompt_service.get_prompt_client("unit-outage") is None


def test_prompt_service_ignores_sdk_fallback_as_live(monkeypatch):
    fallback = _FakeLangfusePrompt("LOCAL", is_fallback=True)
    monkeypatch.setattr(langfuse_prompt_service, "_langfuse_client",
                        types.SimpleNamespace(get_prompt=lambda name, label=None, **kw: fallback))
    monkeypatch.setitem(langfuse_prompt_service._cache, "unit-fb", ManagedPrompt(
        "unit-fb", "1", "LOCAL", "live", "local_cache", 0.0))
    langfuse_prompt_service.get_prompt("unit-fb", max_age_seconds=1)
    assert langfuse_prompt_service._cache["unit-fb"].source == "local_cache"
    assert langfuse_prompt_service.get_prompt_client("unit-fb") is None


# ── HTTP: trace id + feedback ─────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _auth(client, role="EMPLOYEE"):
    res = await client.post("/api/v1/auth/mock-login", json={"role": role})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_chat_response_includes_trace_id_field(client):
    res = await client.post("/api/v1/agents/chat", json={"message": "How many leave days do I have?"},
                            headers=await _auth(client))
    assert res.status_code == 200
    assert "trace_id" in res.json()  # None while tracing is disabled (testing env)


async def test_feedback_requires_auth(client):
    res = await client.post("/api/v1/agents/feedback", json={"trace_id": "a" * 32, "helpful": True})
    assert res.status_code in (401, 403)


async def test_feedback_skipped_when_tracing_disabled(client):
    res = await client.post("/api/v1/agents/feedback", json={"trace_id": "a" * 32, "helpful": False},
                            headers=await _auth(client))
    assert res.status_code == 200 and res.json()["status"] == "skipped"


async def test_feedback_records_score_and_masks_pii(client, monkeypatch):
    scored = {}
    monkeypatch.setattr(langfuse_client, "get_langfuse", lambda: object())
    monkeypatch.setattr(langsmith_tracer, "score", lambda **kw: scored.update(kw))
    res = await client.post(
        "/api/v1/agents/feedback",
        json={"trace_id": "b" * 32, "helpful": True, "comment": "great, my aadhaar 1234 5678 9012"},
        headers=await _auth(client),
    )
    assert res.status_code == 200 and res.json()["status"] == "recorded"
    assert scored["name"] == "user_feedback" and scored["value"] == 1.0
    assert scored["trace_id"] == "b" * 32 and scored["data_type"] == "BOOLEAN"
    assert "1234 5678 9012" not in scored["comment"]


async def test_feedback_validates_trace_id(client):
    res = await client.post("/api/v1/agents/feedback", json={"trace_id": "bad id!", "helpful": True},
                            headers=await _auth(client))
    assert res.status_code == 422


# ── Memory persistence ────────────────────────────────────────────────────────

def test_memory_persistence_is_atomic_and_round_trips(tmp_path):
    mem = ConversationMemoryManager()
    mem._persistence_file = str(tmp_path / "sessions.json")
    mem.add_turn("sess-persist", "user", "My project lead is Meera")
    assert not list(tmp_path.glob("*.tmp"))  # temp file replaced, not left behind

    reloaded = ConversationMemoryManager()
    reloaded._persistence_file = mem._persistence_file
    reloaded._load_from_disk()
    assert any("Meera" in t.content for t in reloaded.get_turns("sess-persist"))


# ── LangGraph sync bridge ─────────────────────────────────────────────────────

async def test_run_sync_works_inside_a_running_event_loop():
    from app.agents.langgraph_orchestrator import _run_sync

    async def answer():
        return 42

    assert _run_sync(answer()) == 42


def test_run_sync_works_without_a_running_loop():
    from app.agents.langgraph_orchestrator import _run_sync

    async def answer():
        return "ok"

    assert _run_sync(answer()) == "ok"
