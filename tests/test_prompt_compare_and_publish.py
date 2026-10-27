"""Prompt-vs-prompt comparison config/summary logic and the "GEPA Optimized" Langfuse publish (all offline)."""
from types import SimpleNamespace

import pytest

from app.evaluations.prompt_optimizer import GEPA_DEFAULT_LABEL, GEPA_OPTIMIZED_TAG, PROTECTED_LABELS
from app.optimization import adk_prompt_compare as pc


def _fleet():
    leave = SimpleNamespace(name="leave_agent", sub_agents=[], instruction="leave")
    policy = SimpleNamespace(name="policy_agent", sub_agents=[], instruction="policy")
    return SimpleNamespace(name="hr_root_orchestrator", sub_agents=[leave, policy], instruction="root"), leave, policy


# ── contestant parsing ───────────────────────────────────────────────────────

def test_parse_spec_and_defaults_to_the_agents_own_prompt():
    spec = pc.parse_contestant_spec("agent=leave,version=v3,model=openai/gpt-4o-mini")
    out = pc.normalize_contestants([spec, {"agent": "root"}])
    assert out[0]["prompt_name"] == "leave-subagent" and out[0]["variant"] == {"version": 3}
    assert out[0]["model"] == "openai/gpt-4o-mini"
    assert out[1]["prompt_name"] == "peopleops-root-orchestrator" and out[1]["variant"] == {"label": "live"}


def test_any_prompt_can_run_on_any_agent_and_text_needs_no_prompt_name():
    out = pc.normalize_contestants([
        {"agent": "policy", "prompt": "health-subagent", "label": "gepa-optimized"},
        {"agent": "leave", "text": "You are a leave bot."},
    ])
    assert out[0]["agent"] == "policy" and out[0]["prompt_name"] == "health-subagent"
    assert out[1]["variant"] == {"text": "You are a leave bot."}


def test_config_errors_are_reported_together():
    with pytest.raises(pc.CompareConfigError) as exc:
        pc.normalize_contestants([{"agent": "leave", "version": 1, "label": "live"}, {"agent": "root", "version": "x"}])
    assert len(exc.value.problems) == 2
    with pytest.raises(pc.CompareConfigError):
        pc.normalize_contestants([{"agent": "root"}])          # fewer than two
    with pytest.raises(pc.CompareConfigError):
        pc.parse_contestant_spec("agent")                      # not key=value


def test_identical_contestants_get_distinct_names():
    out = pc.normalize_contestants([{"agent": "root", "label": "live"}, {"agent": "root", "label": "live", "model": "m"}])
    assert out[0]["name"] != out[1]["name"]


def test_find_agent_resolves_short_and_full_names():
    root, leave, policy = _fleet()
    assert pc.find_agent(root, "root") is root
    assert pc.find_agent(root, "leave") is leave
    assert pc.find_agent(root, "policy_agent") is policy
    with pytest.raises(pc.CompareConfigError):
        pc.find_agent(root, "nope")


# ── summary ──────────────────────────────────────────────────────────────────

def _result(name, composite, per_case):
    scored = sum(1 for v in per_case.values() if v is not None)
    return {"name": name, "agent": "root", "prompt_name": "p", "prompt": 1, "model": "m", "status": "ok", "composite": composite,
            "scored_cases": scored, "errored_cases": len(per_case) - scored,
            "pass_rate_percent": 50.0, "metrics": {"tool_trajectory_avg_score": composite}, "average_latency_ms": 10,
            "cases": {cid: {"score": s, "tools": [], "status": "ok", "error": None} for cid, s in per_case.items()}}


META = {"evalset": "x", "metrics_preset": "fast", "judge": "j", "duration_sec": 1, "warnings": []}


def test_summary_ranks_counts_wins_and_calls_a_clear_winner():
    a = _result("A", 0.8, {"c1": 1.0, "c2": 0.6})
    b = _result("B", 0.55, {"c1": 0.5, "c2": 0.6})
    report = pc._summarise([b, a], ["c1", "c2"], None, META)
    assert report["status"] == "compare_complete" and report["ranking"] == ["A", "B"]
    assert report["verdict"]["winner"] == "A" and report["verdict"]["reliable"] and report["verdict"]["within_noise"] is False
    assert report["head_to_head"] == {"a": "A", "b": "B", "a_wins": 1, "b_wins": 0, "ties": 1}
    md = pc.to_markdown(report)
    assert "**Winner: A**" in md and "| c1 |" in md


def test_small_gaps_are_flagged_as_noise():
    a = _result("A", 0.65, {"c1": 0.7, "c2": 0.6})
    b = _result("B", 0.625, {"c1": 0.65, "c2": 0.6})
    report = pc._summarise([a, b], ["c1", "c2"], None, META)
    assert report["verdict"]["within_noise"] is True and "within noise" in pc.to_markdown(report)


def test_errored_cases_are_excluded_and_make_the_result_inconclusive():
    """A rate-limited case must not flatter one side: only shared, scored cases count, and the verdict says so."""
    a = _result("A", 1.0, {"c1": 1.0, "c2": None, "c3": 1.0})        # c2 errored
    b = _result("B", 0.5, {"c1": 0.0, "c2": 1.0, "c3": 1.0})
    report = pc._summarise([a, b], ["c1", "c2", "c3"], None, META)
    assert report["status"] == "compare_partial"
    assert report["verdict"]["reliable"] is False and report["verdict"]["compared_cases"] == 2
    by_name = {r["name"]: r for r in report["contestants"]}
    assert by_name["A"]["paired_composite"] == 1.0 and by_name["B"]["paired_composite"] == 0.5
    md = pc.to_markdown(report)
    assert "Inconclusive" in md and "ERROR (not scored)" in md and "(winner)" not in md


def test_a_failed_contestant_does_not_break_the_report():
    ok = _result("A", 0.9, {"c1": 0.9})
    bad = {"name": "B", "agent": "root", "prompt_name": "p", "prompt": 2, "model": "m", "status": "error", "error": "prompt v2 missing"}
    report = pc._summarise([ok, bad], ["c1"], None, META)
    assert report["status"] == "compare_partial" and report["verdict"]["reliable"] is False
    assert "FAILED: prompt v2 missing" in pc.to_markdown(report)


# ── GEPA publish ─────────────────────────────────────────────────────────────

class FakeLangfuse:
    def __init__(self, existing_tags=None, fail_get=False):
        self.existing_tags, self.fail_get, self.created = existing_tags or [], fail_get, None

    def get_prompt(self, name, label=None, cache_ttl_seconds=None):
        if self.fail_get:
            raise RuntimeError("not found")
        return SimpleNamespace(tags=self.existing_tags)

    def create_prompt(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(version=14)

    def flush(self):
        pass


def _service(fake):
    from app.services.dataset_sync_service import LangfuseDatasetSyncService

    svc = LangfuseDatasetSyncService()
    svc._langfuse = fake
    return svc


def test_publish_tags_the_prompt_and_keeps_existing_tags_and_never_goes_live():
    fake = FakeLangfuse(existing_tags=["peopleops", "adk-agents"])
    version = _service(fake)._publish_optimized_prompt("peopleops-root-orchestrator", "new text", GEPA_DEFAULT_LABEL, "msg")
    assert version == 14
    assert fake.created["tags"] == ["peopleops", "adk-agents", GEPA_OPTIMIZED_TAG]
    assert fake.created["labels"] == [GEPA_DEFAULT_LABEL] and GEPA_DEFAULT_LABEL not in PROTECTED_LABELS


def test_publish_works_for_a_brand_new_prompt_name():
    fake = FakeLangfuse(fail_get=True)
    _service(fake)._publish_optimized_prompt("brand-new", "text", GEPA_DEFAULT_LABEL, "msg")
    assert fake.created["tags"] == [GEPA_OPTIMIZED_TAG]


def test_publish_without_langfuse_returns_none():
    assert _service(None)._publish_optimized_prompt("p", "t", GEPA_DEFAULT_LABEL, "m") is None


def test_pick_items_handles_unhashable_adk_agents():
    """ADK agents are pydantic models (unhashable); item selection must not put them in a set."""
    class Unhashable(SimpleNamespace):
        __hash__ = None

    leave = Unhashable(name="leave_agent", sub_agents=[], instruction="x")
    root = Unhashable(name="hr_root_orchestrator", sub_agents=[leave], instruction="y")
    contestants = pc.normalize_contestants([{"agent": "leave", "version": 1}, {"agent": "leave", "version": 2}])
    items, note = pc.pick_items(contestants, root, None, deterministic_only=False, limit=None)
    assert items and note and "leave_agent" in note
