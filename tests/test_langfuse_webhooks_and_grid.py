"""Langfuse webhook authentication, prompt-sync wiring, grid testing, LLM judge, optimiser,
dataset sync and live dashboards."""

import hashlib
import hmac
import json
import time
import types

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.evaluations import grid_config
from app.evaluations.grid_config import GridConfigError, extract_config, is_grid_request, normalize_grid_config
from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25
from app.evaluations.llm_judge_service import llm_judge_service
from app.evaluations.prompt_optimizer import EvalOutcome, ReflectivePromptOptimizer, candidate_is_valid
from app.models.chat_session import ChatSession, ChatTurn
from app.services import dataset_sync_service as dss
from app.services.dataset_sync_service import langfuse_dataset_service
from app.services.langfuse_prompt_service import langfuse_prompt_service, ManagedPrompt
from app.services.webhook_auth import verify_langfuse_signature, verify_webhook_credentials

PREFIX = "/api/v1/agents"
SECRET = "unit-test-webhook-secret"
ID_A = GOLDEN_BENCHMARK_25[0].test_id
ID_B = GOLDEN_BENCHMARK_25[1].test_id


def sign(body: bytes, secret: str = SECRET, ts: float = None) -> str:
    stamp = str(int(ts if ts is not None else time.time()))
    digest = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={digest}"


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "LANGFUSE_WEBHOOK_SECRET", SECRET)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def auth(client, role="HR_MANAGER"):
    res = await client.post("/api/v1/auth/mock-login", json={"role": role})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ── Signature verification ────────────────────────────────────────────────────

def test_langfuse_signature_format_is_accepted():
    body = b'{"type":"prompt-version"}'
    assert verify_langfuse_signature(body, sign(body), SECRET)


def test_langfuse_signature_rejects_wrong_secret_tampering_and_replays():
    body = b'{"type":"prompt-version"}'
    assert not verify_langfuse_signature(body, sign(body, secret="other"), SECRET)
    assert not verify_langfuse_signature(body + b" ", sign(body), SECRET)
    stale = sign(body, ts=time.time() - 3600)
    assert not verify_langfuse_signature(body, stale, SECRET, tolerance_seconds=600)
    assert verify_langfuse_signature(body, stale, SECRET, tolerance_seconds=0)  # check disabled
    assert not verify_langfuse_signature(body, "t=notanumber,v1=abc", SECRET)


def test_signature_alias_key_and_multiple_candidates():
    body = b"{}"
    header = sign(body).replace("v1=", "s=")
    assert verify_langfuse_signature(body, header, SECRET)
    stamp = str(int(time.time()))
    good = hmac.new(SECRET.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    assert verify_langfuse_signature(body, f"t={stamp},v1=deadbeef,v1={good}", SECRET)


def test_valid_secret_is_not_masked_by_a_failing_signature_header():
    """The old code took the first header present, so a bad x-langfuse-signature hid a valid x-webhook-secret."""
    body = b"{}"
    assert verify_webhook_credentials(body, ["t=1,v1=bad", SECRET], secret=SECRET)
    assert not verify_webhook_credentials(body, ["t=1,v1=bad", "wrong"], secret=SECRET)
    assert not verify_webhook_credentials(body, [None, ""], secret=SECRET)


def test_shared_secret_forms():
    body = b'{"a":1}'
    body_hmac = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    for token in (SECRET, f"Bearer {SECRET}", body_hmac, f"sha256={body_hmac}"):
        assert verify_webhook_credentials(body, [token], secret=SECRET)


# ── Prompt webhook (real Langfuse payload) ────────────────────────────────────

def langfuse_event(action="created", labels=("live",), name="leave-subagent", version=5, text="NEW LEAVE PROMPT"):
    return {
        "id": "evt-1", "timestamp": "2026-10-22T10:00:00Z", "type": "prompt-version", "apiVersion": "v1",
        "action": action,
        "prompt": {"id": "p1", "name": name, "version": version, "projectId": "proj", "labels": list(labels),
                   "tags": [], "prompt": text, "type": "text", "config": {}, "commitMessage": "m"},
    }


def test_parse_webhook_event_understands_langfuse_and_legacy_shapes():
    parsed = langfuse_prompt_service.parse_webhook_event(langfuse_event(labels=("live", "dev")))
    assert parsed["prompt_name"] == "leave-subagent" and parsed["version"] == 5
    assert parsed["labels"] == ["live", "dev"] and parsed["template"] == "NEW LEAVE PROMPT" and parsed["langfuse_format"]
    legacy = langfuse_prompt_service.parse_webhook_event({"event": "prompt.updated", "prompt_name": "x", "label": "live", "template": "T"})
    assert legacy["prompt_name"] == "x" and legacy["labels"] == ["live"] and legacy["template"] == "T"


async def test_prompt_webhook_accepts_real_langfuse_signature_and_reloads(client, monkeypatch):
    calls = {}

    async def fake_check(names=None):
        calls["names"] = names
        return list(names or [])

    monkeypatch.setattr(langfuse_prompt_service, "check_langfuse_cloud_changes_once", fake_check)
    monkeypatch.setattr(langfuse_prompt_service, "_reload_fleet", lambda: calls.setdefault("reloaded", True))
    body = json.dumps(langfuse_event()).encode()
    res = await client.post(f"{PREFIX}/webhooks/langfuse", content=body,
                            headers={"x-langfuse-signature": sign(body), "content-type": "application/json"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "upserted" and data["reloaded"] == ["leave-subagent"]
    assert calls["names"] == ["leave-subagent"]


async def test_prompt_webhook_rejects_bad_signature_but_accepts_secret_beside_it(client):
    body = json.dumps(langfuse_event(labels=("dev",))).encode()
    bad = await client.post(f"{PREFIX}/webhooks/langfuse", content=body,
                            headers={"x-langfuse-signature": "t=1,v1=bad", "content-type": "application/json"})
    assert bad.status_code == 401
    both = await client.post(f"{PREFIX}/webhooks/langfuse", content=body,
                             headers={"x-langfuse-signature": "t=1,v1=bad", "x-webhook-secret": SECRET,
                                      "content-type": "application/json"})
    assert both.status_code == 200 and both.json()["status"] == "skipped"


async def test_prompt_webhook_skips_non_live_and_handles_delete(client, monkeypatch):
    monkeypatch.setattr(langfuse_prompt_service, "_reload_fleet", lambda: None)
    monkeypatch.setitem(langfuse_prompt_service._cache, "leave-subagent", ManagedPrompt(
        "leave-subagent", "1", "T", "live", "langfuse_live", time.time()))
    body = json.dumps(langfuse_event(action="deleted")).encode()
    res = await client.post(f"{PREFIX}/webhooks/langfuse", content=body,
                            headers={"x-webhook-secret": SECRET, "content-type": "application/json"})
    assert res.json()["status"] == "invalidated"
    # The deleted Langfuse copy is dropped; agents fall back to the local registry template.
    assert langfuse_prompt_service._cache["leave-subagent"].source == "local_cache"


async def test_check_changes_forces_fresh_fetch_and_reloads(monkeypatch):
    seen = {}

    def get_prompt(name, label=None, **kw):
        seen[name] = kw
        return types.SimpleNamespace(prompt="FRESH TEXT", version=9, is_fallback=False)

    reloaded = []
    monkeypatch.setattr(langfuse_prompt_service, "_langfuse_client", types.SimpleNamespace(get_prompt=get_prompt))
    monkeypatch.setattr(langfuse_prompt_service, "_reload_fleet", lambda: reloaded.append(True))
    monkeypatch.setitem(langfuse_prompt_service._cache, "zoho-subagent", ManagedPrompt(
        "zoho-subagent", "1", "OLD", "live", "local_cache", 0.0))
    changed = await langfuse_prompt_service.check_langfuse_cloud_changes_once(names=["zoho-subagent"])
    assert changed == ["zoho-subagent"] and reloaded
    assert seen["zoho-subagent"]["cache_ttl_seconds"] == 0  # bypasses the SDK cache
    assert langfuse_prompt_service.get_prompt_client("zoho-subagent") is not None


async def test_listing_prompts_does_not_push_db_edits_to_langfuse(client):
    async with AsyncSessionLocal() as db:
        await langfuse_prompt_service.save_prompt_to_db(prompt_key="flag-test-prompt", template="EDITED IN TABLEPLUS", db=db)
    res = await client.get(f"{PREFIX}/prompts", headers=await auth(client))
    assert res.status_code == 200
    assert "flag-test-prompt" not in langfuse_prompt_service._cache


# ── Alerts webhook ────────────────────────────────────────────────────────────

async def test_alerts_webhook_requires_authentication(client):
    payload = {"alertName": "Latency", "severity": "WARNING", "message": "slow"}
    assert (await client.post(f"{PREFIX}/observability/alerts/webhook", json=payload)).status_code == 401
    body = json.dumps(payload).encode()
    ok = await client.post(f"{PREFIX}/observability/alerts/webhook", content=body,
                           headers={"x-langfuse-signature": sign(body), "content-type": "application/json"})
    assert ok.status_code == 200 and ok.json()["status"] == "received"


# ── Grid config ───────────────────────────────────────────────────────────────

SAMPLE = {"config": {
    "prompt_label": "baseline", "run_prefix": "clinical-gepa-openai",
    "models": ["openai/gpt-4o-mini"], "items": [ID_A, ID_B], "judge": "openai/gpt-4o-mini",
    "optimization": {"enabled": True, "threshold": 0.8, "budget": "light", "max_metric_calls": 10,
                     "model": "openai/gpt-4o-mini", "optimizer_model": "gemini-2.0-flash",
                     "judge": "openai/gpt-4o-mini", "output_label": "gepa-clinical-v1"}}}


def test_sample_config_from_the_brief_is_understood():
    cfg = normalize_grid_config(SAMPLE)
    assert cfg["variants"] == [{"label": "baseline"}]
    assert cfg["models"] == ["openai/gpt-4o-mini"] and cfg["items"] == [ID_A, ID_B]
    assert cfg["judge"] == "openai/gpt-4o-mini" and cfg["run_prefix"] == "clinical-gepa-openai"
    assert cfg["optimization"]["output_label"] == "gepa-clinical-v1" and cfg["optimization"]["max_metric_calls"] == 10
    assert cfg["optimization"]["optimizer_model"] == "gemini-2.0-flash"


def test_prompt_versions_and_models_form_a_matrix():
    cfg = normalize_grid_config({"prompt_versions": ["v1", 2, "3"], "models": ["gpt-4o-mini", "gemini-2.0-flash"]})
    assert cfg["variants"] == [{"version": 1}, {"version": 2}, {"version": 3}]
    assert len(cfg["variants"]) * len(cfg["models"]) == 6


def test_config_defaults_to_live_prompt_and_default_model():
    cfg = normalize_grid_config({"config": {"run_prefix": "x"}})
    assert cfg["variants"] == [{"label": "live"}] and cfg["models"] == [None] and cfg["optimization"] is None


def test_envelopes_and_detection():
    assert extract_config({"payload": {"config": {"models": ["a"]}}}) == {"models": ["a"]}
    assert extract_config({"datasetName": "d", "payload": {"models": ["a"]}}) == {"models": ["a"]}
    assert is_grid_request({"config": {}}) and is_grid_request({"models": ["a"]})
    assert not is_grid_request({"model": "gemini-3.8-flash", "limit": 3, "run_name": "r"})


@pytest.mark.parametrize("body,fragment", [
    ({"items": ["NOPE"]}, "unknown items"),
    ({"prompt_versions": ["latest"]}, "not a version"),
    ({"prompt_versions": [1, 2, 3, 4], "models": ["a", "b", "c", "d"]}, "maximum"),
    ({"run_prefix": "bad prefix!"}, "run_prefix"),
    ({"optimization": {"enabled": True, "output_label": "live"}}, "never published as live"),
    ({"optimization": {"enabled": True, "budget": "enormous"}}, "budget"),
    ({"optimization": {"enabled": True, "threshold": 5}}, "threshold"),
    ({"optimization": {"enabled": True, "max_metric_calls": 0}}, "max_metric_calls"),
    ({"limit": 0}, "limit"),
])
def test_invalid_configs_report_every_problem(body, fragment):
    with pytest.raises(GridConfigError) as err:
        normalize_grid_config(body)
    assert any(fragment in p for p in err.value.problems)


# ── Grid execution ────────────────────────────────────────────────────────────

def _fake_result(model, version, score):
    return {
        "dataset_run_url": f"https://lf/run/{model}-{version}", "average_overall_score": score,
        "pass_rate_percent": 100.0 if score >= 0.8 else 50.0, "average_latency_ms": 120.0, "total_cost_usd": 0.01,
        "total_cases": 2, "judge": "heuristic", "model": model, "prompt_text": f"PROMPT v{version} {{{{ organization_name }}}}",
        "results": [{"prompt": "q", "response_preview": "a", "overall_score": score, "evaluations": {}, "latency_ms": 1.0}],
    }


async def test_grid_runs_every_cell_ranks_them_and_survives_a_failing_cell(monkeypatch):
    calls = []

    async def fake_run(**kw):
        calls.append(kw)
        if kw["prompt_version"] == 2 and kw["model_name"] == "m2":
            raise RuntimeError("prompt v2 does not exist")
        return _fake_result(kw["model_name"], kw["prompt_version"] or kw["prompt_label"],
                            {("m1", 1): 0.6, ("m2", 1): 0.9, ("m1", 2): 0.7}[(kw["model_name"], kw["prompt_version"])])

    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", fake_run)
    result = await langfuse_dataset_service.run_grid_experiment(
        {"config": {"prompt_versions": [1, 2], "models": ["m1", "m2"], "items": [ID_A], "judge": "judge-x", "run_prefix": "px"}})

    assert result["status"] == "grid_complete" and result["cells_total"] == 4 and result["cells_succeeded"] == 3
    assert result["best"]["model"] == "m2" and result["best"]["prompt"] == "v1" and result["best"]["average_score"] == 0.9
    assert result["matrix"]["v1"] == {"m1": 0.6, "m2": 0.9} and result["matrix"]["v2"]["m2"] is None
    failed = next(c for c in result["cells"] if c["status"] == "error")
    assert "does not exist" in failed["error"]
    # explicit versions are strict (never silently fall back); the judge and items are forwarded
    assert all(c["strict_prompt"] is True and c["judge_model"] == "judge-x" and c["test_ids"] == [ID_A] for c in calls)
    assert calls[0]["experiment_run_name"].startswith("px-m1-v1-")
    assert not any(k.startswith("_") for cell in result["cells"] for k in cell)  # internals not leaked


async def test_live_label_is_not_strict_so_grids_work_without_langfuse(monkeypatch):
    seen = []

    async def fake_run(**kw):
        seen.append(kw["strict_prompt"])
        return _fake_result(kw["model_name"], "live", 0.9)

    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", fake_run)
    await langfuse_dataset_service.run_grid_experiment({"config": {"models": ["m1"]}})
    await langfuse_dataset_service.run_grid_experiment({"config": {"prompt_label": "baseline", "models": ["m1"]}})
    assert seen == [False, True]


async def test_grid_invalid_config_runs_nothing(monkeypatch):
    async def boom(**kw):
        raise AssertionError("must not run")

    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", boom)
    with pytest.raises(GridConfigError):
        await langfuse_dataset_service.run_grid_experiment({"config": {"items": ["NOPE"]}})


async def test_unknown_item_ids_are_an_error_not_a_silent_substitution():
    with pytest.raises(ValueError, match="Unknown golden test ids"):
        await langfuse_dataset_service.run_golden_benchmark_experiment(test_ids=["NOPE"])


# ── Grid endpoints ────────────────────────────────────────────────────────────

async def test_grid_endpoint_is_role_gated_and_validates(client):
    assert (await client.post(f"{PREFIX}/experiments/grid", json=SAMPLE)).status_code in (401, 403)
    emp = await client.post(f"{PREFIX}/experiments/grid", json=SAMPLE, headers=await auth(client, "EMPLOYEE"))
    assert emp.status_code == 403
    bad = await client.post(f"{PREFIX}/experiments/grid", json={"config": {"items": ["NOPE"]}}, headers=await auth(client))
    assert bad.status_code == 422 and "unknown items" in json.dumps(bad.json())


async def test_grid_endpoint_runs_in_background_and_reports_latest(client, monkeypatch):
    async def fake_run(**kw):
        return _fake_result(kw["model_name"], kw["prompt_version"] or "base", 0.85)

    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", fake_run)
    headers = await auth(client)
    accepted = await client.post(f"{PREFIX}/experiments/grid",
                                 json={"config": {"prompt_versions": [1, 2], "models": ["m1"]}}, headers=headers)
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACCEPTED" and accepted.json()["cells"] == 2
    latest = await client.get(f"{PREFIX}/experiments/grid/latest", headers=headers)
    assert latest.json()["status"] == "grid_complete" and latest.json()["cells_succeeded"] == 2

    waited = await client.post(f"{PREFIX}/experiments/grid?wait=true",
                               json={"config": {"models": ["m1"]}}, headers=headers)
    assert waited.json()["status"] == "grid_complete" and waited.json()["best"]["model"] == "m1"


async def test_experiment_webhook_runs_the_grid_for_config_bodies(client, monkeypatch):
    ran = {}

    async def fake_tracked(body):
        ran["body"] = body
        return {}

    monkeypatch.setattr(langfuse_dataset_service, "run_grid_tracked", fake_tracked)
    body = json.dumps(SAMPLE).encode()
    res = await client.post(f"{PREFIX}/webhooks/experiment", content=body,
                            headers={"x-langfuse-signature": sign(body), "content-type": "application/json"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "grid" and data["cells"] == 1 and data["optimization_enabled"] is True
    assert data["run_prefix"] == "clinical-gepa-openai" and ran["body"] == SAMPLE


async def test_experiment_webhook_rejects_an_invalid_grid_synchronously(client):
    body = json.dumps({"config": {"items": ["NOPE"]}}).encode()
    res = await client.post(f"{PREFIX}/webhooks/experiment", content=body,
                            headers={"x-webhook-secret": SECRET, "content-type": "application/json"})
    assert res.status_code == 422 and res.json()["detail"]["problems"]


async def test_compare_endpoint_turns_bad_ids_into_422(client):
    res = await client.post(f"{PREFIX}/experiments/compare", json={"test_id": "NOPE", "limit": 1}, headers=await auth(client))
    assert res.status_code == 422


async def test_webhook_status_lists_every_endpoint_without_hardcoded_port(client):
    res = await client.get(f"{PREFIX}/webhooks/status", headers=await auth(client, "ADMIN"))
    data = res.json()
    assert res.status_code == 200
    urls = {k: v["url"] for k, v in data["webhooks"].items()}
    assert set(urls) == {"langfuse_remote_experiment", "langfuse_prompts", "langfuse_alerts", "zoho_people"}
    assert all(u.startswith("http") and ":8000" not in u for u in urls.values())
    assert settings.LANGFUSE_WEBHOOK_SECRET not in res.text


# ── Optimiser ─────────────────────────────────────────────────────────────────

SEED = "Be helpful. {{ organization_name }} policy applies."


def make_optimizer(scores, **kw):
    evaluated, reflected = [], []
    queue = list(scores)

    async def evaluate(text):
        evaluated.append(text)
        return EvalOutcome(avg_score=queue.pop(0), failures=[{"prompt": "q"}], metric_calls=2)

    async def reflect(prompt, failures):
        reflected.append(prompt)
        return f"{prompt} v{len(reflected) + 1}"

    return ReflectivePromptOptimizer(evaluate, reflect, **kw), evaluated, reflected


async def test_optimizer_keeps_improvements_and_stops_at_threshold():
    opt, evaluated, _ = make_optimizer([0.7, 0.85], threshold=0.8, budget="heavy", max_metric_calls=20)
    res = await opt.optimize(SEED, EvalOutcome(0.5, [{"prompt": "q"}], 2))
    assert res.improved and res.best_score == 0.85 and res.stopped_reason == "threshold_met"
    assert res.best_prompt.endswith("v3") and res.metric_calls == 4 and len(res.rounds) == 2


async def test_optimizer_rejects_regressions_and_respects_round_budget():
    opt, _, _ = make_optimizer([0.4, 0.45], threshold=0.9, budget="light", max_metric_calls=50)
    res = await opt.optimize(SEED, EvalOutcome(0.5, [], 2))
    assert not res.improved and res.best_prompt == SEED and res.stopped_reason == "rounds_exhausted"
    assert [r["accepted"] for r in res.rounds] == [False, False]


async def test_optimizer_respects_metric_call_budget():
    opt, evaluated, _ = make_optimizer([0.6, 0.7, 0.75], threshold=0.95, budget="heavy", max_metric_calls=5)
    res = await opt.optimize(SEED, EvalOutcome(0.5, [], 2))
    assert res.metric_calls == 4 and len(evaluated) == 2 and res.stopped_reason == "metric_call_budget"


async def test_optimizer_noop_when_already_above_threshold_and_on_unusable_rewrite():
    opt, evaluated, _ = make_optimizer([], threshold=0.8)
    res = await opt.optimize(SEED, EvalOutcome(0.95, [], 2))
    assert res.stopped_reason == "threshold_met" and not evaluated and res.metric_calls == 0

    async def reflect_drops_placeholder(prompt, failures):
        return "A prompt without the template placeholder"

    async def evaluate(text):
        raise AssertionError("an invalid rewrite must not be evaluated")

    opt2 = ReflectivePromptOptimizer(evaluate, reflect_drops_placeholder, threshold=0.9)
    res2 = await opt2.optimize(SEED, EvalOutcome(0.5, [], 2))
    assert res2.stopped_reason == "no_candidate" and not res2.improved


def test_candidate_validation():
    assert candidate_is_valid(SEED, SEED + " Also cite sections.")
    assert not candidate_is_valid(SEED, SEED)
    assert not candidate_is_valid(SEED, "")
    assert not candidate_is_valid(SEED, "x" * 9000 + "{{ organization_name }}")
    assert not candidate_is_valid(SEED, "no placeholder")


def _best_cell(score=0.5):
    return {"prompt": "v1", "model": "m1", "_model": "m1", "average_score": score, "pass_rate_percent": 0.0,
            "_prompt_text": SEED, "_results": [{"prompt": "q1", "response_preview": "a", "overall_score": score, "evaluations": {"x": 1}}]}


async def test_optimisation_publishes_only_under_the_output_label(monkeypatch):
    published = {}
    scores = iter([0.9])

    async def fake_eval(text, **kw):
        return EvalOutcome(avg_score=next(scores), failures=[], metric_calls=1)

    monkeypatch.setattr(langfuse_dataset_service, "_evaluate_prompt_text", fake_eval)
    monkeypatch.setattr(langfuse_dataset_service, "_reflect_on_failures", lambda model, prompt, failures: prompt + " Cite the statute.")
    monkeypatch.setattr(langfuse_dataset_service, "_publish_optimized_prompt",
                        lambda name, text, label, message: published.update(name=name, label=label, text=text, message=message) or 7)

    cfg = normalize_grid_config({"config": {"items": [ID_A], "optimization": {
        "enabled": True, "threshold": 0.8, "output_label": "gepa-v1", "max_metric_calls": 5}}})
    out = await langfuse_dataset_service._optimize_best_cell(cfg, _best_cell())
    assert out["improved"] and out["published"] and out["published_prompt_version"] == 7
    assert published["label"] == "gepa-v1" and published["label"] not in {"live", "production"}
    assert out["seed_score"] == 0.5 and out["best_score"] == 0.9 and out["stopped_reason"] == "threshold_met"
    assert out["optimized_prompt"].endswith("Cite the statute.")


async def test_optimisation_does_not_publish_without_improvement_and_skips_other_prompts(monkeypatch):
    monkeypatch.setattr(langfuse_dataset_service, "_publish_optimized_prompt",
                        lambda *a, **k: pytest.fail("must not publish a non-improvement"))

    async def worse(text, **kw):
        return EvalOutcome(avg_score=0.1, failures=[], metric_calls=1)

    monkeypatch.setattr(langfuse_dataset_service, "_evaluate_prompt_text", worse)
    monkeypatch.setattr(langfuse_dataset_service, "_reflect_on_failures", lambda model, prompt, failures: prompt + " more")
    cfg = normalize_grid_config({"config": {"items": [ID_A], "optimization": {"enabled": True, "max_metric_calls": 3}}})
    out = await langfuse_dataset_service._optimize_best_cell(cfg, _best_cell())
    assert not out["improved"] and not out["published"] and out["optimized_prompt"] is None

    other = normalize_grid_config({"config": {"prompt_name": "leave-subagent", "optimization": {"enabled": True}}})
    skipped = await langfuse_dataset_service._optimize_best_cell(other, _best_cell())
    assert skipped["ran"] is False and "root orchestrator" in skipped["reason"]


def test_reflection_is_disabled_in_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", True)
    assert langfuse_dataset_service._reflect_on_failures("m", SEED, []) is None


def test_publish_uses_only_the_given_label(monkeypatch):
    created = {}
    fake = types.SimpleNamespace(create_prompt=lambda **kw: created.update(kw) or types.SimpleNamespace(version=12),
                                 flush=lambda: None)
    monkeypatch.setattr(langfuse_dataset_service, "_langfuse", fake)
    assert langfuse_dataset_service._publish_optimized_prompt("p", "T", "gepa-v1", "msg") == 12
    assert created["labels"] == ["gepa-v1"] and created["commit_message"] == "msg"
    monkeypatch.setattr(langfuse_dataset_service, "_langfuse", None)
    assert langfuse_dataset_service._publish_optimized_prompt("p", "T", "gepa-v1", "msg") is None


# ── LLM judge ─────────────────────────────────────────────────────────────────

VERDICT = {"policy_groundedness": 0.4, "helpfulness_and_clarity": 0.5, "statutory_compliance": 0.3,
           "safety_and_pii_zero_leakage": 1.0, "rationale": "Invents a leave quota."}


@pytest.fixture
def live_judge(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    monkeypatch.setattr(llm_judge_service, "judge_model", "judge-model")
    monkeypatch.setattr(llm_judge_service, "_langfuse", None)
    llm_judge_service._judgement_cache.clear()
    yield
    llm_judge_service._judgement_cache.clear()


def test_judge_verdict_parsing():
    parse = llm_judge_service.parse_judgement
    assert parse("Sure! " + json.dumps(VERDICT) + " done")["policy_groundedness"] == 0.4
    assert parse(json.dumps({**VERDICT, "policy_groundedness": 7}))["policy_groundedness"] == 1.0  # clamped
    assert parse("not json") is None
    assert parse(json.dumps({k: v for k, v in VERDICT.items() if k != "statutory_compliance"})) is None
    assert parse(json.dumps({**VERDICT, "policy_groundedness": "high"})) is None
    assert parse(json.dumps({**VERDICT, "policy_groundedness": True})) is None


def test_llm_judge_overrides_quality_metrics_but_rules_keep_safety(live_judge, monkeypatch):
    seen = []
    monkeypatch.setattr(llm_judge_service, "_complete", lambda model, messages: seen.append((model, messages)) or json.dumps(VERDICT))
    res = llm_judge_service.evaluate_response(
        query="How many casual leaves?", response_text="You get 40 casual leaves, call me at secret-token-123",
        expected_keywords=["8"], forbidden_terms=["secret-token-123"], statutory_clause="Sec 18",
        reference_answer="8 days per year", push_to_langfuse=False)
    assert res.judge == "judge-model"
    assert res.metrics["policy_groundedness"] == 0.4 and res.metrics["statutory_compliance"] == 0.3
    assert res.metrics["safety_and_pii_zero_leakage"] == 0.0  # forbidden term found by rules, judge said 1.0
    assert "Invents a leave quota" in res.feedback and not res.passed
    prompt = seen[0][1][1]["content"]
    assert "8 days per year" in prompt and "Sec 18" in prompt and "secret-token-123" in prompt


def test_llm_judge_is_cached_per_response(live_judge, monkeypatch):
    calls = []
    monkeypatch.setattr(llm_judge_service, "_complete", lambda m, msgs: calls.append(1) or json.dumps(VERDICT))
    for _ in range(6):  # six evaluators score the same item
        llm_judge_service.evaluate_response(query="q", response_text="answer text here", push_to_langfuse=False, reference_answer="r")
    assert len(calls) == 1


def test_llm_judge_failure_falls_back_to_heuristics(live_judge, monkeypatch):
    def boom(model, messages):
        raise TimeoutError("provider down")

    monkeypatch.setattr(llm_judge_service, "_complete", boom)
    res = llm_judge_service.evaluate_response(query="q", response_text="A reasonable structured answer: yes.", push_to_langfuse=False)
    assert res.judge == "heuristic (judge unavailable)" and res.metrics["policy_groundedness"] == 1.0

    monkeypatch.setattr(llm_judge_service, "_complete", lambda m, msgs: "garbage")
    llm_judge_service._judgement_cache.clear()
    assert llm_judge_service.evaluate_response(query="q2", response_text="Another decent answer: ok.", push_to_langfuse=False).judge.startswith("heuristic")


def test_llm_judge_never_runs_in_mock_mode_or_on_live_traffic(live_judge, monkeypatch):
    monkeypatch.setattr(llm_judge_service, "_complete", lambda m, msgs: pytest.fail("no provider call expected"))
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", True)
    assert llm_judge_service.evaluate_response(query="q", response_text="An answer: fine.", push_to_langfuse=False).judge.startswith("heuristic")
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    assert llm_judge_service.evaluate_response(query="q", response_text="An answer: fine.", push_to_langfuse=False, live=True).judge == "heuristic"


def test_judge_model_names_are_routed_for_litellm():
    assert llm_judge_service._litellm_target("gemini-2.0-flash") == "gemini/gemini-2.0-flash"
    assert llm_judge_service._litellm_target("openai/gpt-4o-mini") == "openai/gpt-4o-mini"
    assert llm_judge_service._litellm_target("groq/openai/gpt-oss-120b") == "groq/openai/gpt-oss-120b"


async def test_experiment_wrapper_sets_and_resets_the_judge_model(monkeypatch):
    seen = {}

    async def fake_impl(self, **kw):
        seen["judge"] = llm_judge_service.judge_model
        raise RuntimeError("stop")

    monkeypatch.setattr(type(langfuse_dataset_service), "_run_golden_benchmark_experiment_impl", fake_impl)
    with pytest.raises(RuntimeError):
        await langfuse_dataset_service.run_golden_benchmark_experiment(judge_model="judge-x")
    assert seen["judge"] == "judge-x" and llm_judge_service.judge_model is None


# ── Dataset sync ──────────────────────────────────────────────────────────────

class FakeDatasetClient:
    def __init__(self, fail_ids=(), existing=()):
        self.items, self.fail_ids, self.existing = [], set(fail_ids), existing
        self.flushed = False

    def create_dataset(self, **kw):
        raise RuntimeError("already exists")

    def create_dataset_item(self, **kw):
        if kw.get("id") in self.fail_ids:
            raise RuntimeError("boom")
        self.items.append(kw)

    def get_dataset(self, name):
        return types.SimpleNamespace(items=list(self.existing))

    def flush(self):
        self.flushed = True


def test_dataset_sync_is_idempotent_and_counts_failures(monkeypatch):
    bad = langfuse_dataset_service.dataset_item_id(ID_A)
    fake = FakeDatasetClient(fail_ids=[bad])
    monkeypatch.setattr(langfuse_dataset_service, "_langfuse", fake)
    result = langfuse_dataset_service.sync_golden_dataset_to_langfuse()
    assert result["status"] == "partial" and result["synced_items"] == 24
    assert result["failed_items"][0]["test_id"] == ID_A
    ids = [i["id"] for i in fake.items]
    assert len(ids) == len(set(ids)) == 24 and all(i.startswith(f"{dss.DATASET_NAME}:") for i in ids)
    again = FakeDatasetClient()
    monkeypatch.setattr(langfuse_dataset_service, "_langfuse", again)
    assert [i["id"] for i in again.items] == []  # fresh fake untouched
    assert langfuse_dataset_service.sync_golden_dataset_to_langfuse()["status"] == "success"
    assert [i["id"] for i in again.items][:2] == [langfuse_dataset_service.dataset_item_id(t.test_id) for t in GOLDEN_BENCHMARK_25[:2]]


def test_dataset_sync_archives_legacy_duplicates_only_when_asked(monkeypatch):
    legacy = types.SimpleNamespace(id="legacy-1", input={"test_id": ID_A})
    current = types.SimpleNamespace(id=langfuse_dataset_service.dataset_item_id(ID_A), input={"test_id": ID_A})
    fake = FakeDatasetClient(existing=[legacy, current])
    monkeypatch.setattr(langfuse_dataset_service, "_langfuse", fake)
    assert langfuse_dataset_service.sync_golden_dataset_to_langfuse()["archived_legacy_duplicates"] == 0
    assert not any(i.get("status") == "ARCHIVED" for i in fake.items)
    fake.items.clear()
    assert langfuse_dataset_service.sync_golden_dataset_to_langfuse(archive_legacy_duplicates=True)["archived_legacy_duplicates"] == 1
    archived = [i for i in fake.items if i.get("status") == "ARCHIVED"]
    assert archived == [{"id": "legacy-1", "dataset_name": dss.DATASET_NAME, "status": "ARCHIVED"}]


async def test_sync_all_is_manager_only(client):
    assert (await client.post(f"{PREFIX}/observability/sync-all", headers=await auth(client, "EMPLOYEE"))).status_code == 403


def test_langfuse_sdk_still_has_the_async_experiment_api_we_rely_on():
    """requirements pin langfuse<6 because the runner uses the SDK's async experiment entry point."""
    langfuse = pytest.importorskip("langfuse")
    for name in ("_run_experiment_async", "_create_experiment_run_name", "run_experiment", "create_score", "create_prompt"):
        assert hasattr(langfuse.Langfuse, name), f"langfuse.Langfuse.{name} disappeared; update dataset_sync_service"


# ── Live dashboards ───────────────────────────────────────────────────────────

async def test_dashboards_compute_real_usage_and_are_manager_only(client):
    session_id = "sess_analytics_probe_1"
    async with AsyncSessionLocal() as db:
        db.add(ChatSession(id=session_id, user_id="EMP-004", user_email="aarav.sharma@intelera.com", title="Probe"))
        await db.flush()
        db.add(ChatTurn(session_id=session_id, role="user", content="how many leaves"))
        db.add(ChatTurn(session_id=session_id, role="assistant", content="18",
                        turn_metadata={"agent_name": "LEAVE_SUBAGENT", "latency_ms": 250, "tokens_used": 1234,
                                       "cost_usd": 0.5, "guardrail_status": "PASSED"}))
        db.add(ChatTurn(session_id=session_id, role="assistant", content="blocked",
                        turn_metadata={"agent_name": "ROOT_LLM_ORCHESTRATOR", "latency_ms": 50, "tokens_used": 10,
                                       "cost_usd": 0.0, "guardrail_status": "INPUT_BLOCKED"}))
        await db.commit()

    for path in ("/observability/sessions", "/observability/users", "/analytics/token-usage", "/observability/alerts"):
        assert (await client.get(f"{PREFIX}{path}", headers=await auth(client, "EMPLOYEE"))).status_code == 403

    headers = await auth(client, "ADMIN")
    sessions = (await client.get(f"{PREFIX}/observability/sessions?limit=500", headers=headers)).json()["sessions"]
    probe = next(s for s in sessions if s["session_id"] == session_id)
    assert probe["turns_count"] == 3 and probe["total_tokens"] == 1244 and probe["total_cost_usd"] == 0.5
    assert probe["blocked_requests"] == 1 and probe["total_duration_sec"] == 0.3
    assert probe["agents_involved"] == ["LEAVE_SUBAGENT", "ROOT_LLM_ORCHESTRATOR"] or set(probe["agents_involved"]) == {"LEAVE_SUBAGENT", "ROOT_LLM_ORCHESTRATOR"}

    users = (await client.get(f"{PREFIX}/observability/users", headers=headers)).json()["users"]
    aarav = next(u for u in users if u["email"] == "aarav.sharma@intelera.com")
    assert aarav["full_name"] == "Aarav Sharma" and aarav["total_tokens"] >= 1244 and aarav["total_queries"] >= 1

    usage = (await client.get(f"{PREFIX}/analytics/token-usage", headers=headers)).json()
    assert usage["overall_total_tokens"] >= 1244 and usage["turns_scanned"] >= 3
    assert not (usage["overall_total_tokens"] == 364000)  # the old canned number
    assert "gemini 2.5" not in usage["provider"].lower() and "model_pricing_rates_per_1m_tokens" in usage


# ── Mock mode never reaches a live provider, even for explicit per-run models ─

def test_explicit_model_override_cannot_leave_mock_mode(monkeypatch):
    from app.core import llm_bridge

    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", True)
    before = llm_bridge.snapshot_model_state()
    assert llm_bridge.set_active_model("gemini-3.8-flash") == "gemini-3.8-flash"
    assert llm_bridge.set_active_model("openai/gpt-4o-mini") == "openai/gpt-4o-mini"
    assert llm_bridge.snapshot_model_state() == before  # provider and models untouched

    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    try:
        llm_bridge.set_active_model("gemini-3.8-flash")
        assert llm_bridge.snapshot_model_state() != before  # with mock off the override applies
    finally:
        llm_bridge.restore_model_state(before)


async def test_grid_flags_results_produced_on_the_mock_provider(monkeypatch):
    async def fake_run(**kw):
        return _fake_result(kw["model_name"], "live", 0.9)

    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", fake_run)
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", True)
    mocked = await langfuse_dataset_service.run_grid_experiment({"config": {"models": ["m1"]}})
    assert mocked["mock_mode"] is True and "mock provider" in mocked["warnings"][0]

    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    real = await langfuse_dataset_service.run_grid_experiment({"config": {"models": ["m1"]}})
    assert real["mock_mode"] is False and real["warnings"] == []


# ── Evaluation runs must not touch real employee data ─────────────────────────

def test_eval_sessions_are_isolated_from_real_session_ids():
    from app.evaluations.eval_isolation import EVAL_USER_EMAIL, eval_session_id
    from app.observability.langsmith_tracer import resolve_clean_session_id

    sid = eval_session_id("BENCH-01")
    assert sid.startswith("test_eval_BENCH-01_")
    assert resolve_clean_session_id(sid, "aarav.sharma@intelera.com") == sid  # not folded into sess_aarav.sharma_N
    assert EVAL_USER_EMAIL != "aarav.sharma@intelera.com"


async def test_discard_eval_session_deletes_database_rows():
    from sqlalchemy import select
    from app.evaluations.eval_isolation import discard_eval_session

    sid = "test_eval_discard_probe_1"
    async with AsyncSessionLocal() as db:
        db.add(ChatSession(id=sid, user_id="EMP-004", user_email="x@y.z", title="probe"))
        await db.flush()
        db.add(ChatTurn(session_id=sid, role="user", content="hi"))
        await db.commit()
    await discard_eval_session(sid)
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(ChatSession).where(ChatSession.id == sid))).first() is None
        assert (await db.execute(select(ChatTurn).where(ChatTurn.session_id == sid))).first() is None


async def test_grid_evaluator_runs_in_an_isolated_session_and_cleans_up(monkeypatch):
    from app.evaluations import grid_evaluator as ge

    seen = {}

    async def fake_process(db, user, message, session_id, **kw):
        seen["session"], seen["email"] = session_id, user.email
        return types.SimpleNamespace(response="Maharashtra Earned Leave Sec 18 Section 14 2.0x twice Section 13", agent_routed="HR_ROOT")

    discarded = []

    async def fake_discard(session_id):
        discarded.append(session_id)

    monkeypatch.setattr(ge.llm_root_orchestrator, "process_message", fake_process)
    monkeypatch.setattr(ge, "discard_eval_session", fake_discard)
    await ge.grid_evaluator.run_single_eval(ge.GRID_DATASET[0], db=None)
    assert seen["session"].startswith("test_eval_") and seen["email"] == "eval.benchmarks@intelera.com"
    assert discarded == [seen["session"]]


# ── The body Langfuse's remote-experiment trigger really sends ────────────────

REAL_TRIGGER = {
    "projectId": "cmuz8zyf5003had0e7nxd8ohm",
    "datasetId": "cmv0mxeqz08g4ad0ejsyrvm9r",
    "datasetName": "peopleops-golden-benchmark-25",
    "payload": json.dumps({"config": {"run_prefix": "ui-grid", "models": ["openai/gpt-4o-mini", "groq/openai/gpt-oss-120b"],
                                      "items": [ID_A], "judge": "openai/gpt-4o-mini"}}, indent=2),
}


def test_real_langfuse_trigger_body_is_unwrapped():
    from app.evaluations.grid_config import normalize_trigger_body

    assert is_grid_request(REAL_TRIGGER)
    cfg = normalize_grid_config(REAL_TRIGGER)
    assert cfg["models"] == ["openai/gpt-4o-mini", "groq/openai/gpt-oss-120b"] and cfg["items"] == [ID_A]
    assert normalize_trigger_body(REAL_TRIGGER)["datasetName"] == "peopleops-golden-benchmark-25"
    flat = normalize_trigger_body({"datasetName": "d", "payload": '{"limit": 5}'})
    assert flat["limit"] == 5 and not is_grid_request(flat)
    assert normalize_trigger_body({"payload": "not json"}) == {"payload": "not json"}  # left alone, never crashes


async def test_webhook_accepts_the_real_langfuse_trigger_with_a_custom_header(client, monkeypatch):
    ran = {}

    async def fake_tracked(body):
        ran["body"] = body
        return {}

    monkeypatch.setattr(langfuse_dataset_service, "run_grid_tracked", fake_tracked)
    res = await client.post(f"{PREFIX}/webhooks/experiment", json=REAL_TRIGGER, headers={"x-webhook-secret": SECRET})
    assert res.status_code == 200 and res.json()["mode"] == "grid" and res.json()["cells"] == 2
    wrong = await client.post(f"{PREFIX}/webhooks/experiment", json=REAL_TRIGGER,
                              headers={"x-webhook-secret": "sk-lf-looks-like-an-api-key"})
    assert wrong.status_code == 401


async def test_webhook_flat_limit_payload_from_langfuse_runs_a_single_experiment(client, monkeypatch):
    seen = {}

    async def fake_run(**kw):
        seen.update(kw)
        return {"run_name": "r", "dataset_run_url": None}

    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", fake_run)
    body = {"projectId": "p", "datasetId": "d", "datasetName": "peopleops-golden-benchmark-25", "payload": '{"limit": 5}'}
    res = await client.post(f"{PREFIX}/webhooks/experiment", json=body, headers={"x-webhook-secret": SECRET})
    assert res.status_code == 200 and res.json()["status"] == "ACCEPTED" and res.json()["dataset_name"] == "peopleops-golden-benchmark-25"
    assert seen["limit"] == 5
