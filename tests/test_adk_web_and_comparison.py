"""Google ADK Web integration and the ADK-vs-Langfuse comparison (no LLM calls)."""

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.evaluations import adk_comparison, adk_support
from app.evaluations.adk_expectations import (
    EXPECTATIONS, MUTATING_TOOLS, adk_cases, build_eval_config, rubrics_for, to_eval_set,
)
from app.evaluations.adk_support import (
    AdkCase, AdkCaseResult, identity_shim, install_identity_shim,
)
from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25
from app.services.dataset_sync_service import langfuse_dataset_service

BACKEND = Path(__file__).resolve().parents[1] / "backend"
PREFIX = "/api/v1/agents"


def call(name, **kw):
    return {"tool_name": name, "tool_input": kw}


T_LEAVE = call("transfer_to_agent", agent_name="leave_agent")
BALANCES = call("get_leave_balances", user_id="EMP-004")


# ── Identity shim ─────────────────────────────────────────────────────────────

class FakeAgent:
    def __init__(self, *subs):
        self.sub_agents = list(subs)
        self.before_model_callback = None


class FakeRequest:
    def __init__(self):
        self.added = []

    def append_instructions(self, lines):
        self.added.extend(lines)


def test_identity_shim_adds_employee_and_time_context_and_restores():
    leaf = FakeAgent()
    root = FakeAgent(FakeAgent(leaf))
    with identity_shim(root):
        assert root.before_model_callback is not None and leaf.before_model_callback is not None
        request = FakeRequest()
        ctx = types.SimpleNamespace(state={"user_id": "EMP-002"})
        assert leaf.before_model_callback(ctx, request) is None
        assert "Vikram Malhotra (ID: EMP-002)" in request.added[0] and request.added[1].startswith("CURRENT_TIME:")
        fallback = FakeRequest()
        root.before_model_callback(types.SimpleNamespace(state={}), fallback)
        assert "EMP-004" in fallback.added[0]  # default evaluation user
    assert root.before_model_callback is None and leaf.before_model_callback is None


def test_shim_header_is_identical_to_the_production_header():
    from app.core.employee_context import build_employee_header

    assert build_employee_header("EMP-004") == "[Active Employee: Aarav Sharma (ID: EMP-004) - Address as Aarav, NEVER call by ID code]"
    assert build_employee_header("UNKNOWN-1") == "[Active Employee ID: UNKNOWN-1]"


def test_permanent_shim_can_refresh_prompts():
    root = FakeAgent(FakeAgent())
    install_identity_shim(root, refresh_prompts=True)
    assert root.before_model_callback is adk_support._identity_and_prompt_refresh_callback
    assert root.sub_agents[0].before_model_callback is adk_support._identity_and_prompt_refresh_callback


# ── Expectations and eval-set files ───────────────────────────────────────────

def test_every_golden_case_has_an_expectation():
    assert {tc.test_id for tc in GOLDEN_BENCHMARK_25} == set(EXPECTATIONS)


def test_expectation_tags():
    mutating = {i for i, e in EXPECTATIONS.items() if e.mutating}
    assert mutating == {"BENCH-02-LEAVE-APPLY-CASUAL", "BENCH-03-LEAVE-APPLY-EARNED", "BENCH-09-TIMESHEET-LOG-HOURS",
                        "BENCH-10-TIMESHEET-MULTI-PROJECT", "BENCH-14-ZOHO-LEAVE-SYNC"}
    assert len([e for e in EXPECTATIONS.values() if e.deterministic]) == 10
    # Free-text arguments make a case non-deterministic for ADK's exact-match metric.
    assert not EXPECTATIONS["BENCH-05-PARENTAL-LEAVE-POLICY"].deterministic
    assert EXPECTATIONS["BENCH-01-LEAVE-BALANCES"].deterministic and not EXPECTATIONS["BENCH-01-LEAVE-BALANCES"].mutating
    assert {"apply_leave", "log_work_hours"} <= MUTATING_TOOLS


def test_cases_can_exclude_data_writing_trajectories():
    everything = adk_cases()
    safe = adk_cases(include_mutating=False)
    assert len(everything) == 25 and len(safe) == 20
    assert not any(c.test_id in {"BENCH-02-LEAVE-APPLY-CASUAL", "BENCH-14-ZOHO-LEAVE-SYNC"} for c in safe)
    assert [c.test_id for c in adk_cases(["BENCH-07-OVERTIME-RATE-CALC"])] == ["BENCH-07-OVERTIME-RATE-CALC"]


def test_evalset_matches_adks_schema_and_the_checked_in_files_are_current():
    from google.adk.evaluation.eval_config import EvalConfig, get_eval_metrics_from_config
    from google.adk.evaluation.eval_set import EvalSet

    document = to_eval_set()
    parsed = EvalSet.model_validate(document)  # ADK's own schema
    assert len(parsed.eval_cases) == 25
    first = parsed.eval_cases[0]
    assert first.session_input.user_id == "EMP-004" and first.session_input.state == {"user_id": "EMP-004"}
    assert first.conversation[0].intermediate_data.tool_uses and first.rubrics
    folder = BACKEND / "adk_web" / "peopleops"
    on_disk = json.loads((folder / "peopleops_golden.evalset.json").read_text(encoding="utf-8"))
    # entry_date for the log-hours cases is "today" when generated, so compare everything but those
    skip = {"BENCH-09-TIMESHEET-LOG-HOURS", "BENCH-10-TIMESHEET-MULTI-PROJECT"}
    strip = lambda cases: [c for c in cases if c["eval_id"] not in skip]
    assert strip(on_disk["eval_cases"]) == strip(document["eval_cases"]), "regenerate with: python scripts/build_adk_evalset.py"
    deterministic = EvalSet.model_validate_json((folder / "peopleops_deterministic.evalset.json").read_text(encoding="utf-8"))
    assert len(deterministic.eval_cases) == 10 and all(EXPECTATIONS[c.eval_id].deterministic for c in deterministic.eval_cases)
    config = EvalConfig.model_validate_json((folder / "eval_config.json").read_text(encoding="utf-8"))
    # ADK adds its efficiency metrics (tokens, tool calls, duration) on top of the configured criteria
    assert set(build_eval_config()["criteria"]) <= {m.metric_name for m in get_eval_metrics_from_config(config)}


def test_eval_config_covers_the_adk_evaluators_and_uses_an_llm_judge():
    criteria = build_eval_config("openai/gpt-4o-mini")["criteria"]
    assert set(criteria) == {
        "tool_trajectory_avg_score", "response_match_score", "final_response_match_v2",
        "rubric_based_final_response_quality_v1", "rubric_based_tool_use_quality_v1", "hallucinations_v1",
    }
    assert criteria["tool_trajectory_avg_score"]["match_type"] == "EXACT"
    for name in ("final_response_match_v2", "rubric_based_final_response_quality_v1", "rubric_based_tool_use_quality_v1", "hallucinations_v1"):
        assert criteria[name]["judge_model_options"]["judge_model"] == "openai/gpt-4o-mini"
    assert "safety_v1" not in criteria  # Vertex-only, opt-in
    assert "safety_v1" in build_eval_config(include_vertex_metrics=True)["criteria"]


def test_every_case_has_case_specific_rubrics_in_addition_to_the_global_ones():
    for test_id in EXPECTATIONS:
        rubrics = rubrics_for(test_id)
        assert rubrics and len({r["rubric_id"] for r in rubrics}) == len(rubrics)
    criteria = build_eval_config()["criteria"]
    assert criteria["rubric_based_final_response_quality_v1"]["rubrics"] and criteria["rubric_based_tool_use_quality_v1"]["rubrics"]


# ── Provider plumbing for ADK 2.x ─────────────────────────────────────────────

def test_export_provider_keys_never_overrides_and_fills_missing(monkeypatch):
    from app.core import llm_bridge

    monkeypatch.setattr(llm_bridge, "_get_openai_key", lambda: "sk-test-openai")
    monkeypatch.setattr(llm_bridge, "_get_groq_key", lambda: "gsk-test")
    monkeypatch.setattr(llm_bridge, "_get_gemini_key", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "already-set")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    llm_bridge.export_provider_keys_to_env()
    assert os.environ["OPENAI_API_KEY"] == "sk-test-openai" and os.environ["GROQ_API_KEY"] == "already-set"
    assert "GOOGLE_API_KEY" not in os.environ


async def test_groq_safe_model_drops_thought_parts_before_the_request():
    from google.adk.models.lite_llm import LiteLlm
    from google.genai import types as genai_types
    from app.core import llm_bridge

    model = llm_bridge._groq_safe_litellm("groq/test-model")
    assert isinstance(model, LiteLlm)
    seen = {}

    async def fake_super(self, llm_request, stream=False):
        seen["contents"] = llm_request.contents
        yield "done"

    request = types.SimpleNamespace(contents=[
        genai_types.Content(role="model", parts=[genai_types.Part(text="thinking...", thought=True)]),
        genai_types.Content(role="model", parts=[genai_types.Part(text="thinking", thought=True), genai_types.Part(text="answer")]),
        genai_types.Content(role="user", parts=[genai_types.Part(text="question")]),
    ])
    original = LiteLlm.generate_content_async
    LiteLlm.generate_content_async = fake_super
    try:
        out = [r async for r in model.generate_content_async(request)]
    finally:
        LiteLlm.generate_content_async = original
    assert out == ["done"]
    texts = [[p.text for p in c.parts] for c in seen["contents"]]
    assert texts == [["answer"], ["question"]]  # reasoning gone, empty turn removed


async def test_session_calls_work_with_sync_and_async_services():
    from app.agents.adk_fleet import _maybe_await

    async def later():
        return 7

    assert await _maybe_await(3) == 3 and await _maybe_await(later()) == 7


# ── ADK Web package: same agent, isolated database ────────────────────────────

def test_adk_web_agent_is_the_same_object_and_cannot_reach_the_real_database(tmp_path):
    script = (
        "import json, os, sys\n"
        f"sys.path.insert(0, {str(BACKEND / 'adk_web')!r})\n"
        "os.environ['DATABASE_URL'] = 'postgresql+asyncpg://real:secret@prod.example.com/hr'\n"  # what .env would load
        "os.environ['SYNC_DATABASE_URL'] = 'postgresql://real:secret@prod.example.com/hr'\n"
        "import peopleops.agent as adk_agent\n"
        "from app.core.config import settings\n"
        "from app.agents.adk_fleet import hr_root_orchestrator\n"
        "agents = [hr_root_orchestrator, *hr_root_orchestrator.sub_agents]\n"
        "print(json.dumps({'db': settings.DATABASE_URL, 'env': settings.ENVIRONMENT,\n"
        "  'same_agent': adk_agent.root_agent is hr_root_orchestrator,\n"
        "  'shimmed': all(a.before_model_callback is not None for a in agents), 'n_agents': len(agents)}))\n"
    )
    env = {**os.environ, "ADK_WEB_DB_FILE": str(tmp_path / "adk.db"), "LANGFUSE_ENABLED": "false",
           "PYTHONPATH": str(BACKEND), "MOCK_LLM_ENABLED": "true"}
    env.pop("ADK_WEB_ALLOW_REAL_DB", None)
    out = subprocess.run([sys.executable, "-W", "ignore", "-c", script], capture_output=True, text=True, env=env, cwd=str(BACKEND), timeout=240)
    assert out.returncode == 0, out.stderr[-1500:]
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert "prod.example.com" not in data["db"] and "sqlite" in data["db"] and str(tmp_path.name) in data["db"]
    assert data["env"] == "adk-web" and data["same_agent"] is True
    assert data["shimmed"] is True and data["n_agents"] == 6
    assert (tmp_path / "adk.db").exists()  # tables and demo employees were created locally


# ── Comparison report ─────────────────────────────────────────────────────────

def adk_result(test_id, *, traj, names, rouge, actual=None, expected=None, error=None, rubric=1.0):
    metrics = {}
    if traj is not None:
        metrics = {
            "tool_trajectory_avg_score": {"score": traj, "status": "PASSED" if traj >= 1.0 else "FAILED", "threshold": 1.0},
            "response_match_score": {"score": rouge, "status": "PASSED" if rouge >= 0.3 else "FAILED", "threshold": 0.3},
            "rubric_based_final_response_quality_v1": {
                "score": rubric, "status": "PASSED" if rubric >= 0.7 else "FAILED", "threshold": 0.7,
                "rubrics": [{"rubric_id": "no_invented_facts", "score": rubric, "rationale": ""}],
            },
        }
    passed = all(m["status"] == "PASSED" for m in metrics.values()) if metrics else None
    return AdkCaseResult(
        test_id=test_id, status=None if passed is None else ("PASSED" if passed else "FAILED"), response="x",
        actual_tool_use=actual or [], expected_tool_use=expected or [], metrics=metrics,
        efficiency={"token_usage_v1": 100.0}, latency_ms=100.0, error=error,
    )


def lf_item(test_id, score, passed):
    prompt = next(tc.prompt for tc in GOLDEN_BENCHMARK_25 if tc.test_id == test_id)
    return {"prompt": prompt, "overall_score": score, "passed": passed, "agent_routed": "LEAVE_SUBAGENT",
            "latency_ms": 5000.0, "evaluations": {"policy_groundedness": score}}


def test_report_classifies_agreement_and_flags_duplicate_calls():
    ids = ["BENCH-01-LEAVE-BALANCES", "BENCH-07-OVERTIME-RATE-CALC", "BENCH-11-TIMESHEET-UTILIZATION",
           "BENCH-13-ZOHO-ATTENDANCE-SYNC", "BENCH-15-ZOHO-REGULARIZATION"]
    cases = adk_cases(ids)
    adk = [
        adk_result(ids[0], traj=1.0, names=1.0, rouge=0.5),                              # ADK pass
        adk_result(ids[1], traj=1.0, names=1.0, rouge=0.05),                             # ADK fail (text overlap)
        adk_result(ids[2], traj=0.0, names=0.0, rouge=0.4,
                   actual=[BALANCES, BALANCES]),                                         # duplicate call, ADK fail
        adk_result(ids[3], traj=1.0, names=1.0, rouge=0.4),                              # ADK pass
        adk_result(ids[4], traj=None, names=None, rouge=None, error="RuntimeError: no final response"),
    ]
    lf = [lf_item(ids[0], 0.95, True), lf_item(ids[1], 0.9, True), lf_item(ids[2], 0.3, False),
          lf_item(ids[3], 0.4, False), lf_item(ids[4], 0.8, True)]
    report = adk_comparison.build_report(cases, adk, lf)
    by_id = {r["test_id"]: r for r in report["rows"]}
    assert by_id[ids[0]]["agreement"] == "both_pass"
    assert by_id[ids[1]]["agreement"] == "langfuse_only"   # judge fine with the answer, ADK's ROUGE disagrees
    assert by_id[ids[2]]["agreement"] == "both_fail"
    assert by_id[ids[3]]["agreement"] == "adk_only"
    assert by_id[ids[4]]["agreement"] == "not_comparable" and "error" in by_id[ids[4]]["adk"]
    agg = report["aggregate"]
    assert agg["agreement"] == {"both_pass": 1, "langfuse_only": 1, "both_fail": 1, "adk_only": 1, "not_comparable": 1}
    assert agg["adk"]["errors"] == 1 and agg["adk"]["evaluated"] == 4
    assert agg["adk"]["tool_trajectory_avg_score"] == pytest.approx(0.75)
    assert agg["adk"]["metrics"]["rubric_based_final_response_quality_v1"] == pytest.approx(1.0)
    assert agg["adk"]["total_tokens"] == 400
    assert agg["langfuse"]["overall_score"] == pytest.approx(0.639, abs=1e-3) or agg["langfuse"]["evaluated"] == 5
    assert agg["correlation"]["n"] == 4 and agg["correlation"]["langfuse_overall_vs_adk_response_match"] is not None


def test_report_with_missing_legs_does_not_crash():
    cases = adk_cases(["BENCH-01-LEAVE-BALANCES"])
    report = adk_comparison.build_report(cases, [], [])
    assert report["rows"][0]["agreement"] == "not_comparable" and report["aggregate"]["adk"]["tool_trajectory_avg_score"] is None
    assert adk_comparison._pearson([1, 2], [1, 2]) is None and adk_comparison._pearson([1, 1, 1], [1, 2, 3]) is None


# ── Orchestration (both legs stubbed) ─────────────────────────────────────────

@pytest.fixture
def stubbed_legs(monkeypatch):
    seen = {"scores": []}

    async def fake_adk(eval_set, eval_config, **k):
        seen["adk_cases"] = [c["eval_id"] for c in eval_set["eval_cases"]]
        seen["adk_judge"] = eval_config["criteria"]["final_response_match_v2"]["judge_model_options"]["judge_model"]
        return [adk_result(i, traj=1.0, names=1.0, rouge=0.5) for i in seen["adk_cases"]]

    async def fake_langfuse(**kw):
        seen["langfuse_kwargs"] = kw
        results = [lf_item(i, 0.9, True) for i in kw["test_ids"]]
        return {"results": results, "run_name": kw["experiment_run_name"], "dataset_run_url": "https://lf/run",
                "dataset_run_id": "run-123", "model": "m", "judge": "heuristic"}

    fake_client = types.SimpleNamespace(create_score=lambda **kw: seen["scores"].append(kw), flush=lambda: None)
    monkeypatch.setattr(adk_comparison, "run_adk_evaluation", fake_adk)
    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", fake_langfuse)
    from app.observability import langfuse_client
    monkeypatch.setattr(langfuse_client, "get_langfuse", lambda: fake_client)
    return seen


async def test_comparison_runs_both_legs_and_attaches_adk_scores_to_the_langfuse_run(stubbed_legs):
    report = await adk_comparison.run_adk_langfuse_comparison(["BENCH-01-LEAVE-BALANCES", "BENCH-07-OVERTIME-RATE-CALC"], judge="judge-x")
    assert stubbed_legs["adk_cases"] == ["BENCH-01-LEAVE-BALANCES", "BENCH-07-OVERTIME-RATE-CALC"]
    assert stubbed_legs["langfuse_kwargs"]["test_ids"] == stubbed_legs["adk_cases"] and stubbed_legs["langfuse_kwargs"]["judge_model"] == "judge-x"
    assert report["status"] == "complete" and report["aggregate"]["agreement"] == {"both_pass": 2}
    assert report["langfuse_run"]["url"] == "https://lf/run" and report["metric_guide"]
    names = {s["name"]: s for s in stubbed_legs["scores"]}
    assert stubbed_legs["adk_judge"] == "judge-x" and report["adk_judge"] == "judge-x"
    assert set(names) == {
        "adk_tool_trajectory_avg_score", "adk_response_match_score", "adk_rubric_based_final_response_quality_v1",
        "adk_pass_rate",
    }
    assert all(s["dataset_run_id"] == "run-123" for s in names.values()) and names["adk_response_match_score"]["value"] == 0.5
    assert report["adk_scores_attached_to_langfuse_run"]["attached"] is True


async def test_comparison_skips_data_writing_cases_on_a_real_database(stubbed_legs, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://real@prod.example.com/hr")
    report = await adk_comparison.run_adk_langfuse_comparison(["BENCH-01-LEAVE-BALANCES", "BENCH-09-TIMESHEET-LOG-HOURS"])
    assert stubbed_legs["adk_cases"] == ["BENCH-01-LEAVE-BALANCES"]
    assert report["skipped_cases"] == ["BENCH-09-TIMESHEET-LOG-HOURS"] and "Skipped 1 case" in " ".join(report["warnings"])
    with pytest.raises(ValueError, match="No runnable cases"):
        await adk_comparison.run_adk_langfuse_comparison(["BENCH-09-TIMESHEET-LOG-HOURS"])


async def test_comparison_includes_data_writing_cases_on_throwaway_sqlite(stubbed_legs):
    assert "sqlite" in settings.DATABASE_URL
    await adk_comparison.run_adk_langfuse_comparison(["BENCH-09-TIMESHEET-LOG-HOURS"])
    assert stubbed_legs["adk_cases"] == ["BENCH-09-TIMESHEET-LOG-HOURS"]


async def test_comparison_warns_in_mock_mode_and_survives_missing_langfuse(stubbed_legs, monkeypatch):
    from app.observability import langfuse_client
    monkeypatch.setattr(langfuse_client, "get_langfuse", lambda: None)
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", True)
    report = await adk_comparison.run_adk_langfuse_comparison(["BENCH-01-LEAVE-BALANCES"])
    assert report["mock_mode"] is True and any("mock provider" in w for w in report["warnings"])
    assert report["adk_scores_attached_to_langfuse_run"]["attached"] is False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _auth(client, role):
    res = await client.post("/api/v1/auth/mock-login", json={"role": role})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_adk_compare_endpoints_are_role_gated_and_validated(client):
    body = {"items": ["BENCH-01-LEAVE-BALANCES"]}
    assert (await client.post(f"{PREFIX}/experiments/adk-compare", json=body)).status_code in (401, 403)
    assert (await client.post(f"{PREFIX}/experiments/adk-compare", json=body, headers=await _auth(client, "EMPLOYEE"))).status_code == 403
    assert (await client.get(f"{PREFIX}/experiments/adk-compare/latest", headers=await _auth(client, "EMPLOYEE"))).status_code == 403
    bad = await client.post(f"{PREFIX}/experiments/adk-compare", json={"items": ["NOPE"]}, headers=await _auth(client, "HR_MANAGER"))
    assert bad.status_code == 422 and bad.json()["detail"]["unknown"] == ["NOPE"]


async def test_adk_compare_runs_in_background_and_reports_latest(client, monkeypatch):
    async def fake(items, *, model=None, judge=None, limit=None):
        return {"status": "complete", "model": model, "aggregate": {"cases": len(items or [])}}

    monkeypatch.setattr(adk_comparison, "run_adk_langfuse_comparison", fake)
    headers = await _auth(client, "HR_MANAGER")
    accepted = await client.post(f"{PREFIX}/experiments/adk-compare", json={"items": ["BENCH-01-LEAVE-BALANCES"], "model": "m1"}, headers=headers)
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACCEPTED"
    latest = (await client.get(f"{PREFIX}/experiments/adk-compare/latest", headers=headers)).json()
    assert latest["status"] == "complete" and latest["model"] == "m1" and "finished_at" in latest

    waited = await client.post(f"{PREFIX}/experiments/adk-compare?wait=true", json={"model": "m2"}, headers=headers)
    assert waited.json()["model"] == "m2"


async def test_adk_compare_failure_is_reported_not_raised(client, monkeypatch):
    async def boom(items, **kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr(adk_comparison, "run_adk_langfuse_comparison", boom)
    res = await client.post(f"{PREFIX}/experiments/adk-compare?wait=true", json={}, headers=await _auth(client, "ADMIN"))
    assert res.status_code == 200 and res.json()["status"] == "error" and "provider down" in res.json()["error"]


# ── Rate-limit retries ────────────────────────────────────────────────────────

def test_llm_retries_are_off_by_default_and_opt_in(monkeypatch):
    from app.core import llm_bridge

    assert settings.LLM_NUM_RETRIES == 0 and llm_bridge._retry_kwargs() == {}  # the API keeps failing fast
    monkeypatch.setattr(settings, "LLM_NUM_RETRIES", 5)
    assert llm_bridge._retry_kwargs() == {"num_retries": 5}


# ── The comparison uses an LLM judge unless told otherwise ────────────────────

def test_default_judge_prefers_an_independent_llm(monkeypatch):
    from app.core import llm_bridge
    from app.evaluations.llm_judge_service import resolve_default_judge

    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    monkeypatch.setattr(llm_bridge, "_get_openai_key", lambda: "sk-proj-x")
    monkeypatch.setattr(llm_bridge, "_get_groq_key", lambda: "gsk_x")
    assert resolve_default_judge() == "openai/gpt-4o-mini"
    monkeypatch.setattr(llm_bridge, "_get_openai_key", lambda: None)
    assert resolve_default_judge() == "groq/openai/gpt-oss-120b"
    monkeypatch.setattr(llm_bridge, "_get_groq_key", lambda: None)
    assert resolve_default_judge() is None
    monkeypatch.setattr(llm_bridge, "_get_openai_key", lambda: "sk-proj-x")
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", True)
    assert resolve_default_judge() is None  # mock mode never reaches a provider


async def test_comparison_defaults_to_the_llm_judge_and_heuristic_is_opt_in(stubbed_legs, monkeypatch):
    monkeypatch.setattr(adk_comparison, "resolve_default_judge", lambda: "openai/gpt-4o-mini")
    report = await adk_comparison.run_adk_langfuse_comparison(["BENCH-01-LEAVE-BALANCES"])
    assert stubbed_legs["langfuse_kwargs"]["judge_model"] == "openai/gpt-4o-mini"
    assert not any("keyword-heuristic" in w for w in report["warnings"])

    forced = await adk_comparison.run_adk_langfuse_comparison(["BENCH-01-LEAVE-BALANCES"], judge="heuristic")
    assert stubbed_legs["langfuse_kwargs"]["judge_model"] is None
    assert any("keyword-heuristic" in w for w in forced["warnings"])

    explicit = await adk_comparison.run_adk_langfuse_comparison(["BENCH-01-LEAVE-BALANCES"], judge="groq/openai/gpt-oss-20b")
    assert stubbed_legs["langfuse_kwargs"]["judge_model"] == "groq/openai/gpt-oss-20b"


async def test_comparison_warns_when_no_llm_judge_is_available(stubbed_legs, monkeypatch):
    monkeypatch.setattr(adk_comparison, "resolve_default_judge", lambda: None)
    report = await adk_comparison.run_adk_langfuse_comparison(["BENCH-01-LEAVE-BALANCES"])
    assert stubbed_legs["langfuse_kwargs"]["judge_model"] is None
    assert any("keyword-heuristic" in w for w in report["warnings"])


def test_session_db_url_is_converted_to_an_async_driver():
    from app.agents.adk_fleet import _async_session_url

    assert _async_session_url("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert _async_session_url("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert _async_session_url("sqlite:///x.db") == "sqlite+aiosqlite:///x.db"
    assert _async_session_url("postgresql+asyncpg://u@h/db") == "postgresql+asyncpg://u@h/db"
