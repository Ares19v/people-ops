"""Auth coverage for the webhook and experiment endpoints, and model-state rollback."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.core import llm_bridge
from app.services.dataset_sync_service import langfuse_dataset_service
from app.services.langfuse_prompt_service import langfuse_prompt_service

PREFIX = "/api/v1/agents"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _headers(client, role):
    res = await client.post("/api/v1/auth/mock-login", json={"role": role})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ── Experiment webhook ────────────────────────────────────────────────────────

async def test_experiment_webhook_rejects_missing_or_wrong_secret(client):
    res = await client.post(f"{PREFIX}/webhooks/experiment", json={})
    assert res.status_code == 401
    res = await client.post(
        f"{PREFIX}/webhooks/experiment", json={}, headers={"x-webhook-secret": "wrong"}
    )
    assert res.status_code == 401


async def test_experiment_webhook_accepts_valid_secret_and_runs_in_background(client, monkeypatch):
    calls = []

    async def fake_run(**kwargs):
        calls.append(kwargs)
        return {"run_name": kwargs.get("experiment_run_name"), "dataset_run_url": None}

    monkeypatch.setattr(langfuse_dataset_service, "run_golden_benchmark_experiment", fake_run)
    res = await client.post(
        f"{PREFIX}/webhooks/experiment",
        json={"run_name": "r1", "limit": "2", "prompt_version": "13", "model": "gemini-3.8-flash"},
        headers={"x-webhook-secret": settings.LANGFUSE_WEBHOOK_SECRET},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ACCEPTED"
    # BackgroundTasks run before the ASGI response completes under httpx's transport.
    assert calls and calls[0]["limit"] == 2 and calls[0]["prompt_version"] == 13


async def test_experiment_webhook_rejects_non_integer_limit(client):
    res = await client.post(
        f"{PREFIX}/webhooks/experiment",
        json={"limit": "many"},
        headers={"x-webhook-secret": settings.LANGFUSE_WEBHOOK_SECRET},
    )
    assert res.status_code == 422


def test_prompt_webhook_no_longer_accepts_hardcoded_secrets():
    for legacy in ("peopleops_webhook_secret_2026", "dev_langfuse_webhook_secret_key"):
        if legacy == settings.LANGFUSE_WEBHOOK_SECRET:
            continue  # configured value is legitimately the default in dev
        assert not langfuse_prompt_service.verify_hmac_signature(b"{}", legacy)
    assert langfuse_prompt_service.verify_hmac_signature(b"{}", settings.LANGFUSE_WEBHOOK_SECRET)


# ── Zoho webhook ──────────────────────────────────────────────────────────────

async def test_zoho_webhook_disabled_without_configured_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "ZOHO_WEBHOOK_SECRET", None)
    res = await client.post(f"{PREFIX}/webhooks/zoho", json={"record_id": "R1"})
    assert res.status_code == 503


async def test_zoho_webhook_requires_matching_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "ZOHO_WEBHOOK_SECRET", "zoho-test-secret")
    assert (await client.post(f"{PREFIX}/webhooks/zoho", json={})).status_code == 401
    bad = await client.post(f"{PREFIX}/webhooks/zoho", json={}, headers={"x-webhook-secret": "nope"})
    assert bad.status_code == 401
    ok = await client.post(
        f"{PREFIX}/webhooks/zoho",
        json={"record_id": "R1", "status": "Approved"},
        headers={"x-webhook-secret": "zoho-test-secret"},
    )
    assert ok.status_code == 200
    assert ok.json()["record_id"] == "R1"


# ── Role-gated experiment / status endpoints ──────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("POST", "/experiments/compare"),
    ("POST", "/evaluations/benchmark-25"),
    ("GET", "/webhooks/status"),
])
async def test_expensive_or_sensitive_endpoints_reject_employees_and_anonymous(client, method, path):
    anon = await client.request(method, f"{PREFIX}{path}")
    assert anon.status_code in (401, 403)
    emp = await client.request(method, f"{PREFIX}{path}", headers=await _headers(client, "EMPLOYEE"))
    assert emp.status_code == 403


async def test_webhook_status_does_not_leak_secrets(client):
    res = await client.get(f"{PREFIX}/webhooks/status", headers=await _headers(client, "ADMIN"))
    assert res.status_code == 200
    assert settings.LANGFUSE_WEBHOOK_SECRET not in res.text


# ── Model state rollback ──────────────────────────────────────────────────────

def test_model_state_snapshot_restores_overrides(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    before = llm_bridge.snapshot_model_state()
    try:
        llm_bridge.set_active_model("gemini-3.8-flash-experiment")
        llm_bridge.set_active_model("groq/openai/gpt-oss-20b")
        assert llm_bridge.snapshot_model_state() != before
    finally:
        llm_bridge.restore_model_state(before)
    assert llm_bridge.snapshot_model_state() == before


async def test_experiment_wrapper_restores_state_even_when_run_fails(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM_ENABLED", False)
    before = llm_bridge.snapshot_model_state()

    async def boom(self, **kwargs):
        llm_bridge.set_active_model("gemini-3.8-flash-experiment")
        raise RuntimeError("judge exploded")

    monkeypatch.setattr(
        type(langfuse_dataset_service), "_run_golden_benchmark_experiment_impl", boom
    )
    with pytest.raises(RuntimeError):
        await langfuse_dataset_service.run_golden_benchmark_experiment(model_name="x")
    assert llm_bridge.snapshot_model_state() == before


# ── Production settings validation ────────────────────────────────────────────

def _prod_settings(**overrides):
    from app.core.config import Settings
    base = dict(
        ENVIRONMENT="production",
        SECRET_KEY="x" * 48,
        LANGFUSE_WEBHOOK_SECRET="y" * 48,
        MOCK_SSO_ENABLED=False,
        NEO4J_PASSWORD="n" * 24,
        S3_SECRET_KEY="s" * 24,
        DATABASE_URL="postgresql+asyncpg://u:strongpw@db/hr",
        SYNC_DATABASE_URL="postgresql://u:strongpw@db/hr",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_production_settings_accept_hardened_config():
    _prod_settings()


@pytest.mark.parametrize("override", [
    {"MOCK_SSO_ENABLED": True},
    {"NEO4J_PASSWORD": "hr_neo4j_password"},
    {"S3_SECRET_KEY": "minio_secret_password"},
    {"DATABASE_URL": "postgresql+asyncpg://hr_user:hr_password@db/hr"},
    {"SYNC_DATABASE_URL": "postgresql://hr_user:hr_password@db/hr"},
    {"SECRET_KEY": "dev_super_secret_jwt_key_at_least_32_characters_long"},
    {"LANGFUSE_WEBHOOK_SECRET": "dev_langfuse_webhook_secret_key"},
])
def test_production_settings_reject_insecure_defaults(override):
    with pytest.raises(ValueError):
        _prod_settings(**override)
