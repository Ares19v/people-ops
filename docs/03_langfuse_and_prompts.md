# Langfuse integration: prompts, experiments, grid testing

How Langfuse talks to the PeopleOps backend, where each endpoint lives, and how to run grid tests.
All routes are under `/api/v1/agents` in `backend/app/api/v1/agents.py`.

## 1. Architecture

```
                         LANGFUSE CLOUD
     ┌───────────────────────┬──────────────────────────┬──────────────────────┐
     │ Prompt Management     │ Datasets / Experiments   │ Tracing / Scores     │
     └──────┬────────────────┴──────────┬───────────────┴───────────▲──────────┘
   (A) prompt-version webhook     (B) "Custom experiment"           │ (C) traces, generations,
            │                          button / API                 │     scores (outbound only)
            ▼                                 ▼                     │
        https://<static-domain>.ngrok-free.dev ──► localhost:38290 (backend)
            │
   ┌────────▼──────────────────────────────────────────────────────────────────────┐
   │ FastAPI backend                                                               │
   │  (A) POST /webhooks/langfuse         verify → reload live prompt → audit row  │
   │  (B) POST /webhooks/experiment       verify → single run OR grid (background) │
   │      POST /experiments/grid          same grid, role-gated, optional ?wait    │
   │      GET  /experiments/grid/latest   status/result of the last grid           │
   │  (C) langfuse_client (one shared client) ← tracer, judge, prompts, datasets   │
   └───────────────────────────────────────────────────────────────────────────────┘
```

ngrok is only needed for (A) and (B), where Langfuse calls your machine. Tracing (C) is outbound and
needs no tunnel. `npm run dev:all` starts the backend, Vite and ngrok together; `GET /webhooks/status`
(admin) reports the live tunnel URL and the exact webhook URLs to paste into Langfuse.

## 2. Endpoint map (Langfuse related)

| Endpoint | Purpose | Auth |
|---|---|---|
| `POST /webhooks/langfuse` (alias `/prompts/webhook`) | Prompt-version events | Langfuse signature or shared secret |
| `POST /webhooks/experiment` | Remote experiment trigger (single run or grid) | same |
| `POST /observability/alerts/webhook` | Inbound alerts | same |
| `POST /experiments/grid` | Prompt × model grid (`?wait=true` to block) | HR manager / admin |
| `GET /experiments/grid/latest` | Latest background grid result | HR manager / admin |
| `POST /experiments/compare` | Baseline vs challenger | HR manager / admin |
| `POST /evaluations/benchmark-25` | Run the 25-case golden set once | HR manager / admin |
| `POST /prompts/sync-cloud`, `PUT /prompts/{key}` | Push prompts to Langfuse | manager roles |
| `POST /observability/sync-all` | Push prompts + golden dataset | HR manager / admin |
| `GET /webhooks/status` | Tunnel + webhook URLs | admin |
| `POST /feedback` | Thumbs up/down becomes a `user_feedback` score on the chat's trace | logged in |
| `GET /observability/{users,sessions,alerts}`, `/analytics/token-usage` | Live usage from stored chat turns | HR manager / admin |

## 3. Webhook authentication

`app/services/webhook_auth.py`. Langfuse signs every delivery:

```
x-langfuse-signature: t=<unix ts>,v1=<hex HMAC-SHA256(secret, "<ts>.<raw body>")>
```

Timestamps older than `LANGFUSE_WEBHOOK_TOLERANCE_SECONDS` (default 600) are rejected. Tools that cannot sign
(curl, scripts) may send the shared secret itself, or a plain body HMAC, in `x-webhook-secret` or `Authorization`.
Every credential header present is tried. Set `LANGFUSE_WEBHOOK_SECRET` (required in production).

```bash
curl -X POST "$BASE/api/v1/agents/webhooks/experiment" \
  -H "x-webhook-secret: $LANGFUSE_WEBHOOK_SECRET" -H "content-type: application/json" \
  -d @grid.json
```

## 4. Prompt sync

Langfuse (label `live`) is the source of truth. PostgreSQL `agent_prompts` is an audit mirror.

```
Langfuse ──webhook──► handle_webhook_event_async ─► fetch live version (cache bypass) ─► ADK fleet reloaded
    ▲                                              └► audit row in PostgreSQL
    └── safety net: watcher every PROMPT_WATCH_INTERVAL_SECONDS (default 30) + 15 s cache on every chat turn
```

* Events for other labels (`dev`, `baseline`, …) are ignored; `deleted` drops the cached copy.
* If Langfuse is unreachable, agents run the cached copy, then `data/prompts_registry.json`.
* Direct DB edits are reverted by the watcher. DB → Langfuse pushing is off
  (`ENABLE_POSTGRES_TO_LANGFUSE_SYNC = False`) and is no longer triggered by `GET /prompts`.

## 5. Experiments and evaluators

`LangfuseDatasetSyncService` (`app/services/dataset_sync_service.py`):

* **Dataset:** the 25 golden cases (`app/evaluations/golden_dataset_25.py`). `sync_golden_dataset_to_langfuse`
  upserts them by the stable id `peopleops-golden-benchmark-25:<test_id>`, so re-syncing never duplicates.
  `POST /observability/sync-all?archive_legacy_duplicates=true` archives id-less duplicates from older syncs.
* **Run:** each item goes through the real orchestrator under a lock that applies the model/prompt override and
  always restores it. Results appear in Langfuse → Datasets → Runs.
* **Item evaluators:** policy_groundedness, safety_and_pii_zero_leakage, helpfulness_and_clarity,
  statutory_compliance, latency_sla, overall_quality. Run-level: pass rate, average groundedness, average latency.
* **Judge:** keyword/rule heuristics by default. With `judge` set (e.g. `openai/gpt-4o-mini`) groundedness,
  helpfulness and statutory compliance come from that model (cached per answer). PII/forbidden-term safety stays
  rule-based and the model can only lower it. Judge failures fall back to the heuristic and say so (`judge` field).
* **Live chat traffic** only receives the objectively measured scores (latency, PII safety) plus user feedback.

## 6. Grid testing: prompt versions × models

```json
{
  "config": {
    "prompt_label": "baseline",
    "prompt_versions": ["v1", "v2", "v3"],
    "models": ["openai/gpt-4o-mini", "gemini-2.0-flash"],
    "items": ["BENCH-01-LEAVE-BALANCES", "BENCH-03-LEAVE-APPLY-EARNED"],
    "judge": "openai/gpt-4o-mini",
    "run_prefix": "peopleops-grid",
    "optimization": {
      "enabled": true, "threshold": 0.8, "budget": "light", "max_metric_calls": 10,
      "optimizer_model": "gemini-2.0-flash", "output_label": "gepa-v1"
    }
  }
}
```

| Field | Meaning |
|---|---|
| `prompt_label`, `prompt_labels`, `prompt_versions` | Prompt variants to test (labels and/or versions). Default: the `live` label. |
| `models` | Models to test. Default: the current model. |
| `items` | Golden test ids (default: all 25, or the first `limit`). |
| `judge` | LLM judge model; omit for heuristic scoring. |
| `run_prefix` | Prefix for the Langfuse run names (`<prefix>-<model>-<prompt>-<timestamp>`). |
| `optimization` | Optional prompt refinement, see below. |

Every (prompt × model) pair is one cell and one Langfuse run, executed sequentially (max 12 cells). A failing
cell is reported and the grid continues. An explicitly requested label/version that cannot be fetched fails that
cell instead of silently testing a different prompt. Response: `cells`, a `matrix` (prompt → model → score),
`best`, `judge`, `warnings`. With `MOCK_LLM_ENABLED=true` every cell runs on the mock provider and the
response says so (`mock_mode`, `warnings`); set it to `false` for a meaningful grid.

**Optimization** (`app/evaluations/prompt_optimizer.py`) is a GEPA-style reflective loop, not the full GEPA
algorithm. If the best cell scores below `threshold`, `optimizer_model` rewrites that prompt using the failing
cases and the judge's feedback; each candidate is re-scored on the same items and kept only if it improves.
Bounded by `budget` (light 2 / medium 4 / heavy 8 rounds) and `max_metric_calls` (one call = one item evaluated).
Currently supports the root orchestrator prompt. An improved prompt is published **only** under `output_label`
(`live`, `production`, `latest` are rejected); promote it manually after review.

Run it: `POST /experiments/grid` (add `?wait=true` to block), from Langfuse's custom-experiment trigger
(`/webhooks/experiment`, which accepts the same body, flat or wrapped in `config`/`payload`), then watch
`GET /experiments/grid/latest`. Invalid configs return 422 immediately with every problem listed.

## 7. Configuration

| Setting | Default | Purpose |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | – | Credentials. Tracing is always off when `ENVIRONMENT=testing`. |
| `LANGFUSE_ENABLED` | `true` | Master switch. |
| `LANGFUSE_SAMPLE_RATE` | `1.0` | Trace sampling. |
| `LANGFUSE_RELEASE` | `APP_VERSION` | Release tag on traces. |
| `LANGFUSE_WEBHOOK_SECRET` | dev default | Webhook secret (must be rotated in production). |
| `LANGFUSE_WEBHOOK_TOLERANCE_SECONDS` | `600` | Max age of a signed webhook; `0` disables the check. |
| `PROMPT_WATCH_INTERVAL_SECONDS` | `30` | Watcher poll interval (safety net behind the webhook). |
| `MOCK_LLM_ENABLED` | `true` | Mock mode: no live provider is ever called. |

`langfuse` is pinned to `>=5.0,<6` because the experiment runner uses the SDK's async experiment entry point
(a test fails if an upgrade removes it).
