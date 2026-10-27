import asyncio
import json
import logging
import time
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.auth_service import get_current_user, require_role
from app.agents.orchestrator import orchestrator
from app.agents.langgraph_orchestrator import enterprise_agent_graph
from app.compliance.phi_engine import compliance_engine
from app.observability.langsmith_tracer import resolve_user_email, resolve_clean_session_id
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from app.services.langfuse_prompt_service import langfuse_prompt_service
from app.services.webhook_auth import require_langfuse_webhook
from app.services.dataset_sync_service import langfuse_dataset_service
from app.agents.adk_fleet import sync_agent_instructions

logger = logging.getLogger(__name__)

class RedactPayload(BaseModel):
    text: str
    session_id: Optional[str] = None

class DeRedactPayload(BaseModel):
    text: str
    session_id: str

router = APIRouter(prefix="/agents", tags=["Multi-Agent System"])

class UpdatePromptPayload(BaseModel):
    template: str
    label: Optional[str] = "live"
    agent_name: Optional[str] = None


@router.get("/prompts")
async def list_agent_prompts(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Inspect all decoupled subagent prompts, version, and database sync status."""
    from app.models.prompt import AgentPrompt
    from sqlalchemy import select

    db_records = {}
    try:
        stmt = select(AgentPrompt)
        res = await db.execute(stmt)
        records = res.scalars().all()
        db_records = {p.prompt_key: p.to_dict() for p in records}

        # Auto-detect if any prompt was modified directly in DB (e.g. in TablePlus)
        # Langfuse is the source of truth: DB edits are ignored (and reverted by the watcher) unless the
        # DB -> Langfuse sync has been explicitly re-enabled.
        from app.services.langfuse_prompt_service import ENABLE_POSTGRES_TO_LANGFUSE_SYNC
        modified_records = []
        with langfuse_prompt_service._lock:
            for r in (records if ENABLE_POSTGRES_TO_LANGFUSE_SYNC else []):
                cached = langfuse_prompt_service._cache.get(r.prompt_key)
                if not cached or cached.template != r.template:
                    langfuse_prompt_service._cache[r.prompt_key] = ManagedPrompt(
                        name=r.prompt_key,
                        version=str(r.version),
                        template=r.template,
                        label=r.label,
                        source="database",
                        fetched_at=time.time(),
                    )
                    modified_records.append(r)

        if modified_records:
            from app.agents.adk_fleet import sync_agent_instructions
            sync_agent_instructions()
            if langfuse_prompt_service._langfuse_client:
                for mod_r in modified_records:
                    try:
                        lf_p = langfuse_prompt_service._langfuse_client.create_prompt(
                            name=mod_r.prompt_key,
                            prompt=mod_r.template,
                            labels=["live", "production"],
                            type="text",
                            tags=["peopleops", "adk-agents"]
                        )
                        new_v = getattr(lf_p, "version", None)
                        if new_v:
                            mod_r.version = new_v
                            db_records[mod_r.prompt_key]["version"] = new_v
                            with langfuse_prompt_service._lock:
                                if mod_r.prompt_key in langfuse_prompt_service._cache:
                                    langfuse_prompt_service._cache[mod_r.prompt_key].version = str(new_v)
                    except Exception as err:
                        logger.warning(f"Notice: Auto-syncing TablePlus prompt to Langfuse: {err}")
                await db.commit()
    except Exception:
        db_records = {}

    prompts_info = {}
    with langfuse_prompt_service._lock:
        for k, v in langfuse_prompt_service._cache.items():
            prompts_info[k] = {
                "name": v.name,
                "version": v.version,
                "label": v.label,
                "source": v.source,
                "template": v.template,
                "cached_at": v.fetched_at,
                "stored_in_db": k in db_records
            }
    return {
        "status": "success",
        "langfuse_connected": langfuse_prompt_service._langfuse_client is not None,
        "database_records_count": len(db_records),
        "prompts_count": len(prompts_info),
        "prompts": prompts_info,
        "db_records": db_records
    }


@router.get("/prompts/{prompt_key}")
async def get_agent_prompt(
    prompt_key: str,
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves a single prompt template by key."""
    from app.models.prompt import AgentPrompt
    from sqlalchemy import select
    try:
        stmt = select(AgentPrompt).where(AgentPrompt.prompt_key == prompt_key)
        res = await db.execute(stmt)
        record = res.scalars().first()
        if record:
            return {
                "status": "success",
                "prompt_key": record.prompt_key,
                "template": record.template,
                "version": str(record.version),
                "label": record.label,
                "agent_name": record.agent_name,
                "updated_at": record.updated_at
            }
    except Exception:
        logger.debug("Suppressed non-fatal error", exc_info=True)

    with langfuse_prompt_service._lock:
        cached = langfuse_prompt_service._cache.get(prompt_key)
        if cached:
            return {
                "status": "success",
                "prompt_key": prompt_key,
                "template": cached.template,
                "version": cached.version,
                "label": cached.label,
                "agent_name": prompt_key,
                "updated_at": None
            }
    raise HTTPException(status_code=404, detail=f"Prompt '{prompt_key}' not found.")


@router.put("/prompts/{prompt_key}")
async def update_agent_prompt(
    prompt_key: str,
    payload: UpdatePromptPayload,
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Updates an agent prompt in Langfuse Cloud (the sole authority for agent prompts) and reloads the ADK fleet immediately."""
    if not langfuse_prompt_service._langfuse_client:
        langfuse_prompt_service._init_client()

    if langfuse_prompt_service._langfuse_client:
        try:
            lf_p = langfuse_prompt_service._langfuse_client.create_prompt(
                name=prompt_key,
                prompt=payload.template,
                labels=[payload.label or "live"],
                type="text",
                tags=["peopleops", "adk-agents"]
            )
            new_version = getattr(lf_p, "version", "latest")
            with langfuse_prompt_service._lock:
                from app.services.langfuse_prompt_service import ManagedPrompt
                langfuse_prompt_service._cache[prompt_key] = ManagedPrompt(
                    name=prompt_key,
                    version=str(new_version),
                    template=payload.template,
                    label=payload.label or "live",
                    source="langfuse_live",
                    fetched_at=time.time(),
                )
            from app.agents.adk_fleet import sync_agent_instructions
            sync_agent_instructions()
            # Also log to DB for historical audit only
            await langfuse_prompt_service.save_prompt_to_db(
                prompt_key=prompt_key,
                template=payload.template,
                agent_name=payload.agent_name,
                label=payload.label or "live",
                db=db
            )
            return {
                "status": "success",
                "message": f"Prompt '{prompt_key}' successfully updated in Langfuse Cloud as version {new_version} and reloaded in the ADK fleet.",
                "version": str(new_version)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update prompt in Langfuse Cloud: {e}")
    else:
        raise HTTPException(
            status_code=400,
            detail="Agent prompts can only be changed through Langfuse Cloud, but Langfuse client is not connected."
        )

@router.post("/prompts/webhook")
@router.post("/webhooks/langfuse")
async def langfuse_prompt_webhook(
    raw_body: bytes = Depends(require_langfuse_webhook),
    db: AsyncSession = Depends(get_db),
):
    """
    Prompt change webhook (Langfuse -> ngrok -> here). The request is authenticated by
    `require_langfuse_webhook` (Langfuse `t=..,v1=..` signature, shared secret, or body HMAC), then:
    1. Events that do not concern the 'live' label are skipped
    2. The new live version is pulled from Langfuse and the ADK fleet is hot-reloaded
    3. An audit row is written to PostgreSQL (history only)
    """
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    return await langfuse_prompt_service.handle_webhook_event_async(event_payload=payload, db=db)

@router.post("/prompts/reload")
async def reload_prompts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Force reloads all agent prompts from database/Langfuse (picks up TablePlus changes)."""
    refreshed = await langfuse_prompt_service.check_langfuse_cloud_changes_once()
    sync_agent_instructions()
    return {
        "status": "success",
        "changed": refreshed,
        "message": "Agent prompts re-fetched from Langfuse and reloaded across the ADK fleet.",
    }


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_multi_agent_system(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    response = await orchestrator.process_message(
        db=db,
        user=current_user,
        message=payload.message,
        session_id=payload.session_id,
        target_agent=payload.target_agent
    )
    return response

@router.post("/langgraph-chat")
async def chat_with_langgraph(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user)
):
    user_email = current_user.email or resolve_user_email(current_user.id)
    session_id = resolve_clean_session_id(payload.session_id, user_email)
    initial_state = {
        "session_id": session_id,
        "user_id": user_email,
        "employee_id": current_user.id,
        "user_role": current_user.role.value,
        "raw_input": payload.message,
        "redacted_input": "",
        "phi_detected_count": 0,
        "guardrail_status": "",
        "guardrail_tripped": None,
        "routed_agent": payload.target_agent or "",
        "agent_output": "",
        "citations": [],
        "structured_action": None,
        "requires_hitl_approval": False,
        "is_approved": False,
        "final_response": "",
        "duration_ms": 0.0,
    }

    result = enterprise_agent_graph.invoke(initial_state)
    return {
        "session_id": session_id,
        "response": result.get("final_response"),
        "agent_routed": result.get("routed_agent"),
        "guardrail_status": result.get("guardrail_status"),
        "guardrail_tripped": result.get("guardrail_tripped"),
        "phi_detected_count": result.get("phi_detected_count"),
        "requires_hitl_approval": result.get("requires_hitl_approval"),
        "citations": result.get("citations"),
    }

@router.post("/compliance/redact")
async def compliance_redact(
    payload: RedactPayload,
    current_user: User = Depends(get_current_user)
):
    user_email = current_user.email or resolve_user_email(current_user.id)
    session_id = resolve_clean_session_id(payload.session_id, user_email)
    res = compliance_engine.redact(payload.text, session_id=session_id)
    return {
        "session_id": session_id,
        "redacted_text": res.redacted_text,
        "entities_count": len(res.entities_detected),
        "tokens": res.tokens_created
    }

from app.services.langfuse_prompt_service import langfuse_prompt_service

@router.post("/compliance/de-redact")
async def compliance_deredact(
    payload: DeRedactPayload,
    current_user: User = Depends(get_current_user)
):
    user_email = current_user.email or resolve_user_email(current_user.id)
    clean_session_id = resolve_clean_session_id(payload.session_id, user_email)
    restored = compliance_engine.de_redact(payload.text, session_id=clean_session_id, user_role=current_user.role.value)
    return {
        "session_id": clean_session_id,
        "user_role": current_user.role.value,
        "restored_text": restored
    }


from fastapi.responses import StreamingResponse
from app.agents.orchestrator import llm_root_orchestrator
from app.services.zoho_service import zoho_service
from app.memory.conversation_memory import conversation_memory

@router.post("/chat/stream")
async def stream_chat_with_multi_agent_system(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Real-time Server-Sent Events (SSE) streaming thought traces, tool runs, and response tokens."""
    return StreamingResponse(
        llm_root_orchestrator.stream_message(
            db=db,
            user=current_user,
            message=payload.message,
            session_id=payload.session_id,
            target_agent=payload.target_agent
        ),
        media_type="text/event-stream"
    )

class FeedbackPayload(BaseModel):
    trace_id: str = Field(..., min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$",
                          description="`trace_id` returned by /chat")
    helpful: bool = Field(..., description="True = thumbs up, False = thumbs down")
    comment: Optional[str] = Field(None, max_length=1000)


@router.post("/feedback")
async def submit_chat_feedback(
    payload: FeedbackPayload,
    current_user: User = Depends(get_current_user),
):
    """Records end-user feedback on a chat answer as a `user_feedback` score on its Langfuse trace."""
    from app.core.security import mask_all_pii
    from app.observability import langfuse_client
    from app.observability.langsmith_tracer import langsmith_tracer

    if langfuse_client.get_langfuse() is None:
        return {"status": "skipped", "reason": "Langfuse tracing is disabled", "trace_id": payload.trace_id}

    comment = mask_all_pii(payload.comment) if payload.comment else None
    langsmith_tracer.score(
        name="user_feedback",
        value=1.0 if payload.helpful else 0.0,
        comment=comment,
        trace_id=payload.trace_id,
        data_type="BOOLEAN",
    )
    return {"status": "recorded", "trace_id": payload.trace_id, "helpful": payload.helpful}


@router.post("/webhooks/zoho")
async def zoho_inbound_webhook(
    payload: Dict[str, Any],
    x_webhook_secret: Optional[str] = Header(None, alias="x-webhook-secret"),
):
    """Receives real-time attendance and leave approval webhooks from Zoho People.

    Requires the shared secret in `x-webhook-secret` (ZOHO_WEBHOOK_SECRET).
    """
    from app.core.config import settings
    import hmac

    expected = settings.ZOHO_WEBHOOK_SECRET
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Zoho webhook is disabled: ZOHO_WEBHOOK_SECRET is not configured."
        )
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid webhook secret."
        )
    res = zoho_service.handle_inbound_webhook(payload)
    return res

@router.post("/webhooks/experiment")
async def langfuse_remote_experiment_webhook(
    background_tasks: BackgroundTasks,
    raw_body: bytes = Depends(require_langfuse_webhook),
):
    """
    Langfuse Remote Experiment Webhook Handler:
    Receives remote experiment triggers from Langfuse Cloud UI via ngrok.
    Returns 200 OK immediately within Langfuse's 10-second timeout window,
    and runs the full suite of LLM evaluators across dataset items in the background.
    """
    from app.services.dataset_sync_service import langfuse_dataset_service

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    from app.evaluations.grid_config import GridConfigError, is_grid_request, normalize_grid_config, normalize_trigger_body

    payload = normalize_trigger_body(payload)  # Langfuse sends the config as a JSON string under "payload"
    if is_grid_request(payload):
        try:
            plan = normalize_grid_config(payload)
        except GridConfigError as exc:
            # Rejected synchronously so the Langfuse UI shows the problem instead of a silent failure.
            raise HTTPException(status_code=422, detail={"message": "Invalid grid config", "problems": exc.problems})
        background_tasks.add_task(langfuse_dataset_service.run_grid_tracked, payload)
        return {
            "status": "ACCEPTED",
            "mode": "grid",
            "message": "Grid accepted and running in the background; poll GET /api/v1/agents/experiments/grid/latest.",
            "run_prefix": plan["run_prefix"],
            "prompts": [langfuse_dataset_service._variant_tag(v) for v in plan["variants"]],
            "models": [m or "default" for m in plan["models"]],
            "cells": len(plan["variants"]) * len(plan["models"]),
            "judge": plan["judge"] or "heuristic",
            "optimization_enabled": plan["optimization"] is not None,
            "timestamp": time.time(),
        }

    dataset_name = payload.get("dataset_name") or payload.get("datasetName") or "peopleops-golden-benchmark-25"
    run_name = payload.get("run_name") or payload.get("runName")
    limit = payload.get("limit") or payload.get("count")
    model = payload.get("model") or payload.get("model_name")
    prompt_name = payload.get("prompt_name") or payload.get("promptName")
    prompt_version = payload.get("prompt_version") or payload.get("promptVersion")
    prompt_label = payload.get("prompt_label") or payload.get("promptLabel")

    try:
        limit = int(limit) if limit is not None else None
        prompt_version = int(prompt_version) if prompt_version is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="'limit' and 'prompt_version' must be integers.")

    async def _run_experiment():
        logger.info(
            "[Remote-Experiment] Starting: %s (dataset: %s) | model: %s | prompt: %s (v%s)",
            run_name or "auto", dataset_name, model or "default",
            prompt_name or "orchestrator", prompt_version or prompt_label or "live",
        )
        try:
            res = await langfuse_dataset_service.run_golden_benchmark_experiment(
                experiment_run_name=run_name,
                limit=limit,
                model_name=model,
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                prompt_label=prompt_label,
            )
            logger.info("[Remote-Experiment] Completed: %s | URL: %s", res.get("run_name"), res.get("dataset_run_url"))
        except Exception:
            logger.exception("[Remote-Experiment] Error running experiment")

    background_tasks.add_task(_run_experiment)

    return {
        "status": "ACCEPTED",
        "message": f"Experiment accepted. Running LLM evaluators on '{dataset_name}' in background.",
        "dataset_name": dataset_name,
        "run_name": run_name,
        "model": model,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "timestamp": time.time()
    }


class CompareExperimentPayload(BaseModel):
    limit: Optional[int] = 3
    test_id: Optional[str] = None
    baseline_model: Optional[str] = "groq/openai/gpt-oss-120b"
    baseline_prompt: Optional[str] = "peopleops-root-orchestrator"
    baseline_version: Optional[int] = 1
    challenger_model: Optional[str] = "gemini-3.8-flash"
    challenger_prompt: Optional[str] = "peopleops-root-orchestrator"
    challenger_version: Optional[int] = 13


@router.post("/experiments/compare")
async def trigger_model_and_prompt_comparison(
    payload: Optional[CompareExperimentPayload] = None,
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
):
    """
    Triggers an automated side-by-side A/B comparison experiment in Langfuse:
    Compares Baseline (e.g. Model A + Prompt v1) against Challenger (e.g. Model B + Prompt v13).
    Evaluates both on the golden dataset and uploads comparison results to Langfuse.
    """
    from app.services.dataset_sync_service import langfuse_dataset_service
    p = payload or CompareExperimentPayload()

    baseline_cfg = {
        "model_name": p.baseline_model,
        "prompt_name": p.baseline_prompt,
        "prompt_version": p.baseline_version,
        "run_name": f"exp-{p.baseline_model.split('/')[-1]}-prompt-v{p.baseline_version}-{int(time.time())}"
    }
    challenger_cfg = {
        "model_name": p.challenger_model,
        "prompt_name": p.challenger_prompt,
        "prompt_version": p.challenger_version,
        "run_name": f"exp-{p.challenger_model.split('/')[-1]}-prompt-v{p.challenger_version}-{int(time.time())}"
    }

    try:
        return await langfuse_dataset_service.run_comparison_experiment(
            baseline=baseline_cfg,
            challenger=challenger_cfg,
            limit=p.limit or 3,
            test_id=p.test_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/experiments/grid")
async def run_prompt_model_grid(
    config: Dict[str, Any],
    background_tasks: BackgroundTasks,
    wait: bool = Query(False, description="Block until the whole grid finishes (can take minutes)"),
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
):
    """Grid test: every prompt version/label x every model on the golden dataset, scored by the judge.

    Body: {"config": {"prompt_label": "baseline", "prompt_versions": ["v1","v2"], "models": [...],
    "items": [...], "judge": "openai/gpt-4o-mini", "run_prefix": "...", "optimization": {...}}}
    """
    from app.evaluations.grid_config import GridConfigError, normalize_grid_config

    try:
        plan = normalize_grid_config(config)
    except GridConfigError as exc:
        raise HTTPException(status_code=422, detail={"message": "Invalid grid config", "problems": exc.problems})

    if wait:
        return await langfuse_dataset_service.run_grid_tracked(config)
    background_tasks.add_task(langfuse_dataset_service.run_grid_tracked, config)
    return {
        "status": "ACCEPTED",
        "cells": len(plan["variants"]) * len(plan["models"]),
        "prompts": [langfuse_dataset_service._variant_tag(v) for v in plan["variants"]],
        "models": [m or "default" for m in plan["models"]],
        "poll": "/api/v1/agents/experiments/grid/latest",
    }


class AdkComparePayload(BaseModel):
    items: Optional[List[str]] = Field(None, description="Golden test ids (default: every case that is safe to run)")
    model: Optional[str] = Field(None, description="e.g. openai/gpt-4o-mini (default: the backend's current model)")
    judge: Optional[str] = Field(None, description="LLM judge for the Langfuse leg (default: gpt-4o-mini if an OpenAI key exists, else Groq; 'heuristic' forces keyword rules)")
    limit: Optional[int] = Field(None, ge=1, le=25)


async def _run_adk_comparison_tracked(payload: AdkComparePayload) -> Dict[str, Any]:
    from app.evaluations import adk_comparison

    adk_comparison.set_last_comparison({"status": "running", "started_at": time.time()})
    try:
        result = await adk_comparison.run_adk_langfuse_comparison(
            payload.items, model=payload.model, judge=payload.judge, limit=payload.limit
        )
    except Exception as exc:
        logger.exception("ADK vs Langfuse comparison failed")
        result = {"status": "error", "error": str(exc)}
    result["finished_at"] = time.time()
    adk_comparison.set_last_comparison(result)
    return result


@router.post("/experiments/adk-compare")
async def run_adk_vs_langfuse_comparison(
    payload: AdkComparePayload,
    background_tasks: BackgroundTasks,
    wait: bool = Query(False, description="Block until the comparison finishes (minutes)"),
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
):
    """Run the same golden cases through Google ADK's evaluators and the Langfuse pipeline, and compare.

    Cases whose trajectories write data (apply leave, log hours, Zoho sync) are skipped unless the backend
    runs on a throwaway SQLite database; use `python scripts/run_adk_comparison.py` for those.
    """
    from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25

    known = {tc.test_id for tc in GOLDEN_BENCHMARK_25}
    unknown = [i for i in (payload.items or []) if i not in known]
    if unknown:
        raise HTTPException(status_code=422, detail={"message": "Unknown golden test ids", "unknown": unknown})
    if wait:
        return await _run_adk_comparison_tracked(payload)
    background_tasks.add_task(_run_adk_comparison_tracked, payload)
    return {"status": "ACCEPTED", "poll": "/api/v1/agents/experiments/adk-compare/latest"}


@router.get("/experiments/adk-compare/latest")
async def get_latest_adk_comparison(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
):
    """Status/result of the most recent ADK vs Langfuse comparison (in memory; lost on restart)."""
    from app.evaluations import adk_comparison

    return adk_comparison.last_comparison()


@router.get("/experiments/grid/latest")
async def get_latest_grid_run(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
):
    """Status/result of the most recent grid run started in the background (in memory; lost on restart)."""
    return langfuse_dataset_service.last_grid_run


@router.get("/webhooks/status")
async def get_webhooks_and_ngrok_status(
    request: Request,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Detects the active ngrok tunnel and lists the public webhook URLs to give Langfuse and Zoho."""
    import httpx
    public_url = None
    tunnel_target = None

    try:
        # trust_env=False: this is a loopback call and must never be routed through HTTP(S)_PROXY.
        async with httpx.AsyncClient(timeout=1.5, trust_env=False) as client:
            resp = await client.get("http://127.0.0.1:4040/api/tunnels")
            if resp.status_code == 200:
                tunnels = resp.json().get("tunnels", [])
                # Prefer the https tunnel; ngrok lists http and https variants of the same forward.
                tunnel = next((t for t in tunnels if str(t.get("public_url", "")).startswith("https://")), None) or (tunnels[0] if tunnels else None)
                if tunnel:
                    public_url = tunnel.get("public_url")
                    tunnel_target = (tunnel.get("config") or {}).get("addr")
    except Exception:
        logger.debug("ngrok local API not reachable", exc_info=True)

    local_base = str(request.base_url).rstrip("/")
    backend_port = request.url.port or 80
    base = public_url or local_base
    langfuse_auth = "x-langfuse-signature (set automatically by Langfuse) or x-webhook-secret: <LANGFUSE_WEBHOOK_SECRET>"

    return {
        "ngrok_tunnel_active": public_url is not None,
        "ngrok_forwards_to": tunnel_target,
        "public_base_url": public_url or f"Tunnel not detected (run 'ngrok http {backend_port}' or npm run dev:ngrok)",
        "webhooks": {
            "langfuse_remote_experiment": {
                "url": f"{base}/api/v1/agents/webhooks/experiment",
                "method": "POST",
                "auth": langfuse_auth,
                "purpose": "Run a golden-dataset experiment or a prompt x model grid from the Langfuse UI",
                "body": "flat keys (model, prompt_version, limit, ...) or {\"config\": {models, prompt_versions, items, judge, optimization}}",
            },
            "langfuse_prompts": {
                "url": f"{base}/api/v1/agents/webhooks/langfuse",
                "method": "POST",
                "auth": langfuse_auth,
                "purpose": "Prompt-version events: reload the live prompt into the ADK fleet",
            },
            "langfuse_alerts": {
                "url": f"{base}/api/v1/agents/observability/alerts/webhook",
                "method": "POST",
                "auth": langfuse_auth,
                "purpose": "Inbound latency / safety alerts from Langfuse Cloud",
            },
            "zoho_people": {
                "url": f"{base}/api/v1/agents/webhooks/zoho",
                "method": "POST",
                "auth": "x-webhook-secret: <ZOHO_WEBHOOK_SECRET>",
                "purpose": "Inbound leave approvals and attendance sync from Zoho People",
            },
        },
    }

@router.get("/zoho/status")
async def get_zoho_integration_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns live Zoho People HRMS connection state, circuit breaker health, and synced audit records."""
    from app.models.zoho import ZohoSyncRecord
    from sqlalchemy import select, desc
    
    emp_record = await zoho_service.get_employee_record(current_user.email)
    
    sync_records = []
    try:
        stmt = select(ZohoSyncRecord).order_by(desc(ZohoSyncRecord.created_at)).limit(10)
        res = await db.execute(stmt)
        sync_records = [
            {
                "id": r.id,
                "user_id": r.user_id,
                "record_type": r.record_type,
                "zoho_record_id": r.zoho_record_id,
                "status": r.status,
                "sync_payload": r.sync_payload,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in res.scalars().all()
        ]
    except Exception:
        sync_records = []

    return {
        "status": "connected",
        "provider": "ZOHO_PEOPLE_REST_V2",
        "base_url": zoho_service.base_url,
        "circuit_breaker": {
            "state": zoho_service.circuit_breaker.state.value,
            "failure_count": zoho_service.circuit_breaker.failure_count,
            "recovery_timeout_sec": zoho_service.circuit_breaker.recovery_timeout_sec
        },
        "employee_profile": {
            "zoho_id": emp_record.zoho_id if emp_record else "N/A",
            "employee_id": emp_record.employee_id if emp_record else current_user.id,
            "email": current_user.email,
            "department": emp_record.department if emp_record else "Engineering",
            "designation": emp_record.designation if emp_record else "Staff Engineer",
            "manager_name": emp_record.manager_name if emp_record else "Rajesh Verma (HR Director)",
            "status": emp_record.status if emp_record else "Active"
        },
        "sync_records_count": len(sync_records),
        "recent_syncs": sync_records
    }

@router.post("/zoho/sync-attendance")
async def trigger_zoho_attendance_sync(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Manually triggers an attendance/timesheet sync to Zoho People API."""
    date = payload.get("date", "2026-10-09")
    hours = float(payload.get("hours", 8.0))
    res = await zoho_service.sync_attendance_entry(
        employee_id=current_user.id,
        date=date,
        hours=hours
    )
    return res


@router.get("/memory/{session_id}")
async def get_session_memory(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Inspects multi-turn conversational turns and active extracted entity states.
    Strictly user-scoped to guarantee private employee isolation.
    """
    from app.models.chat_session import ChatSession
    from sqlalchemy import select

    # Verify session ownership
    sess_stmt = select(ChatSession).filter(ChatSession.id == session_id)
    sess_res = await db.execute(sess_stmt)
    chat_sess = sess_res.scalar_one_or_none()
    if chat_sess and chat_sess.user_id and chat_sess.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You cannot view another employee's private chat memory."
        )

    history = await conversation_memory.get_history_async(session_id, db=db, limit=10)
    entities = conversation_memory.get_all_entities(session_id)
    return {
        "session_id": session_id,
        "turns_count": len(history),
        "history": history,
        "entities": entities,
        "storage_mode": "POSTGRESQL_CHECKPOINT"
    }

@router.delete("/memory/{session_id}")
async def clear_session_memory(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Flushes active multi-turn session memory with ownership verification."""
    from app.models.chat_session import ChatSession
    from sqlalchemy import select

    sess_stmt = select(ChatSession).filter(ChatSession.id == session_id)
    sess_res = await db.execute(sess_stmt)
    chat_sess = sess_res.scalar_one_or_none()
    if chat_sess and chat_sess.user_id and chat_sess.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You cannot clear another employee's private chat memory."
        )

    await conversation_memory.clear_session_async(session_id, db=db)
    return {"status": "CLEARED", "session_id": session_id}

@router.get("/sessions")
async def get_user_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves all past checkpointed conversation sessions for the active user from PostgreSQL.
    Strictly isolated to current_user.id.
    """
    sessions = await conversation_memory.get_user_sessions_db(db, current_user.id)
    return {"user_id": current_user.id, "sessions_count": len(sessions), "sessions": sessions}

@router.get("/sessions/{session_id}")
async def get_chat_session_turns(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches complete message turns for a historical session with strict privacy verification."""
    from app.models.chat_session import ChatSession, ChatTurn
    from sqlalchemy import select

    sess_stmt = select(ChatSession).filter(ChatSession.id == session_id)
    sess_res = await db.execute(sess_stmt)
    chat_sess = sess_res.scalar_one_or_none()

    if not chat_sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    
    # Strict privacy guard: Only owner can view turns
    if chat_sess.user_id and chat_sess.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Private employee chat sessions are strictly protected under DPDP regulations."
        )

    turns_stmt = select(ChatTurn).filter(ChatTurn.session_id == session_id).order_by(ChatTurn.created_at.asc())
    turns_res = await db.execute(turns_stmt)
    turns = turns_res.scalars().all()

    return {
        "session_id": chat_sess.id,
        "title": chat_sess.title,
        "user_id": chat_sess.user_id,
        "created_at": chat_sess.created_at.isoformat() if chat_sess.created_at else None,
        "turns_count": len(turns),
        "messages": [
            {
                "id": t.id,
                "role": t.role,
                "content": t.content,
                "metadata": t.turn_metadata or {},
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in turns
        ]
    }

@router.delete("/sessions/purge-history")
async def purge_user_chat_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Completely purges all chat sessions, messages, and memory summaries for the authenticated employee from database and memory (DPDP Right to Erasure)."""
    return await conversation_memory.purge_user_chat_history_db(db, current_user.id, current_user.email)


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Securely deletes a session owned by the authenticated employee."""
    deleted = await conversation_memory.delete_user_session_db(db, session_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or you do not have permission to delete it."
        )
    return {"status": "DELETED", "session_id": session_id}

@router.get("/memory/window/active")
async def get_active_memory_window(
    session_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns the current 5-session sliding window memory context for this employee."""
    summaries = await conversation_memory.get_user_sliding_window_summaries(
        db=db,
        user_id=current_user.id,
        current_session_id=session_id,
        limit=5
    )
    return {
        "user_id": current_user.id,
        "window_capacity": 5,
        "retained_summaries_count": len(summaries),
        "summaries": summaries
    }

@router.post("/sessions/{session_id}/summarize")
async def trigger_session_summary(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explicitly triggers session summarization to slide it into the rolling window on New Chat."""
    res = await conversation_memory.generate_and_save_session_summary(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        force=True
    )
    return {"status": "SUMMARIZED" if res else "SKIPPED", "summary": res}


from app.evaluations.grid_evaluator import grid_evaluator
from app.core.config import settings

@router.post("/evaluations/run")
async def run_grid_evaluations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Executes automated Grid Evaluation matrix across statutory & safety benchmarks."""
    summary = await grid_evaluator.run_evaluation_summary(db)
    return summary

@router.get("/presets")
async def get_flow_circuit_presets():
    """Returns dynamic flow circuit presets configured for the active jurisdiction and organization."""
    jurisdiction = settings.DEFAULT_JURISDICTION.title()
    return {
        "organization": settings.ORGANIZATION_NAME,
        "jurisdiction": jurisdiction,
        "presets": [
            {
                "id": "leave",
                "label": "Leave Application",
                "sub": "EL / CL / SL Statutory Request",
                "query": "I want to apply for 3 days Casual Leave from next Monday",
                "targetAgent": "Leave Subagent",
                "targetId": "leave",
                "railStatus": "Input Rail: 0 Policy Conflicts",
                "icon": "Calendar"
            },
            {
                "id": "policy",
                "label": f"{jurisdiction} Law Graph RAG",
                "sub": "Statutory Overtime & Hours",
                "query": f"What is the maximum daily working hours and overtime pay under {jurisdiction} labor act?",
                "targetAgent": "Policy Graph RAG Subagent",
                "targetId": "policy",
                "railStatus": "Output Rail: Legal Citations Extracted",
                "icon": "FileText"
            },
            {
                "id": "timesheet",
                "label": "Timesheet Entry & Overtime",
                "sub": "Hours Logging & Audit",
                "query": "What is the statutory overtime rate if I work 11 hours on a project?",
                "targetAgent": "Timesheet Subagent",
                "targetId": "timesheet",
                "railStatus": "Dual Rail: Statutory Max & DPDP Scrubbed",
                "icon": "Clock"
            },
            {
                "id": "health",
                "label": "Occupational Health",
                "sub": "Sick Protocols & Doctor Certificate",
                "query": "Employee requesting 4 days of sick leave with fever, do I need a medical certificate?",
                "targetAgent": "Occupational Health Subagent",
                "targetId": "health",
                "railStatus": "Clinical Triage & HIPAA Sanitized",
                "icon": "HeartPulse"
            },
            {
                "id": "zoho",
                "label": "Zoho People HRMS Sync",
                "sub": "Live REST v2 Attendance & Records",
                "query": "Sync my attendance and leave records with Zoho People API.",
                "targetAgent": "Zoho People Subagent",
                "targetId": "zoho",
                "railStatus": "REST v2 Integration & Zero Raw PII",
                "icon": "RefreshCw"
            }
        ]
    }


# ── WebSocket Bidirectional Chat Endpoint (Google ADK Stream) ─────────────────

@router.websocket("/ws")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Bi-directional real-time chat via WebSocket.
    Client frame (JSON): {"message": "..."}
    Server frame (JSON): {"type": "connected"|"typing"|"chunk"|"done"|"error", ...}
    """
    await websocket.accept()

    # Authenticate or resolve demo user
    from app.core.security import decode_access_token
    from sqlalchemy.future import select

    current_user = None
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            res = await db.execute(select(User).filter(User.id == payload.get("sub"), User.is_active == True))
            current_user = res.scalar_one_or_none()

    if not current_user:
        await websocket.send_text(json.dumps({"type": "error", "message": "Unauthorized: A valid authentication token is required to establish a WebSocket session."}))
        await websocket.close(code=4001)
        return

    actual_session = session_id or f"ws_{current_user.id[:8]}_{int(time.time())}"
    await websocket.send_text(json.dumps({
        "type": "connected",
        "session_id": actual_session,
        "message": f"Connected to PeopleOps ADK Multi-Agent Fleet as {current_user.full_name}.",
    }))

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                user_msg = data.get("message", "").strip()
                target_agent = data.get("target_agent")
            except Exception:
                user_msg = raw_text.strip()
                target_agent = None

            if not user_msg:
                continue

            # Send typing feedback
            await websocket.send_text(json.dumps({"type": "typing", "session_id": actual_session}))

            # Process turn via root orchestrator
            response = await orchestrator.process_message(
                db=db,
                user=current_user,
                message=user_msg,
                session_id=actual_session,
                target_agent=target_agent,
            )

            # Stream words
            words = response.response.split(" ")
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i:i+3]) + " "
                await websocket.send_text(json.dumps({"type": "chunk", "text": chunk}))
                await asyncio.sleep(0.015)

            # Send completion frame with telemetry
            await websocket.send_text(json.dumps({
                "type": "done",
                "session_id": actual_session,
                "agent_routed": response.agent_routed,
                "guardrail_status": response.guardrail_status,
                "citations": [c.model_dump() if hasattr(c, "model_dump") else c for c in response.citations],
                "structured_action": response.structured_action.model_dump() if response.structured_action and hasattr(response.structured_action, "model_dump") else response.structured_action,
                "latency_ms": response.latency_ms,
                "cost_usd": response.cost_usd,
                "waterfall_diagram": response.waterfall_diagram
            }))

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            logger.debug("Suppressed non-fatal error", exc_info=True)


@router.post("/evaluations/benchmark-25")
async def trigger_25_benchmark_experiment(
    run_name: Optional[str] = Query(None, description="Custom name for the experiment run"),
    limit: Optional[int] = Query(None, description="Number of test items to evaluate (default: 25)"),
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Triggers the automated Golden Dataset benchmark experiment via Langfuse Experiments tab and evaluates with LLM evaluators."""
    from app.services.dataset_sync_service import langfuse_dataset_service
    res = await langfuse_dataset_service.run_golden_benchmark_experiment(
        experiment_run_name=run_name,
        limit=limit,
        db_session=db
    )
    return res


@router.post("/prompts/sync-cloud")
async def sync_prompts_to_cloud(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Pushes all prompts from PostgreSQL to Langfuse Cloud under 'live' and 'production' labels."""
    from app.services.dataset_sync_service import langfuse_dataset_service
    from app.services.langfuse_prompt_service import langfuse_prompt_service
    
    p_res = await langfuse_prompt_service.sync_db_prompts_to_cloud(db=db)
    d_res = langfuse_dataset_service.sync_golden_dataset_to_langfuse(archive_legacy_duplicates=archive_legacy_duplicates)
    return {
        "prompts_cloud_sync": p_res,
        "dataset_cloud_sync": d_res,
        "message": f"Successfully synced {p_res.get('pushed_count', 0)} prompts from database to Langfuse Cloud under 'live' and 'production' labels."
    }


@router.post("/prompts/{prompt_key}/sync-cloud")
async def sync_single_prompt_to_cloud(
    prompt_key: str,
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Syncs a single prompt from PostgreSQL to Langfuse Cloud under 'live' and 'production' labels."""
    from app.services.langfuse_prompt_service import langfuse_prompt_service
    return await langfuse_prompt_service.sync_single_prompt_to_cloud(prompt_key=prompt_key, db=db)


@router.get("/analytics/token-usage")
async def get_token_usage_analytics(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Live token usage and cost per department, aggregated from persisted chat turns."""
    from app.core.llm_bridge import get_active_groq_model, resolve_llm_provider
    from app.observability.langsmith_tracer import MODEL_PRICING
    from app.observability.usage_analytics import token_usage_by_department

    provider = resolve_llm_provider()
    model = get_active_groq_model() if provider == "groq" else (settings.OPENAI_MODEL if provider == "openai" else settings.GEMINI_MODEL)
    analytics = await token_usage_by_department(db)
    analytics.update({
        "model_pricing_rates_per_1m_tokens": MODEL_PRICING,
        "provider": f"{provider} / {model}",
    })
    return analytics

@router.get("/observability/sessions")
async def get_langfuse_sessions(
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Live conversation session aggregates (turns, latency, tokens, cost, guardrail blocks)."""
    from app.observability.usage_analytics import sessions_summary
    sessions = await sessions_summary(db, limit=limit)
    return {"status": "success", "total_sessions": len(sessions), "sessions": sessions}

@router.get("/observability/users")
async def get_langfuse_users(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Live per-user usage and spend aggregates."""
    from app.observability.usage_analytics import users_summary
    users = await users_summary(db)
    return {"status": "success", "total_users": len(users), "users": users}

@router.get("/observability/alerts")
async def get_langfuse_alerts(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN]))
):
    """Returns configured alert rules and real-time alert events for the Langfuse Alerts tab."""
    from app.observability.evaluators_and_alerts import evaluators_and_alerts_manager
    return {
        "status": "success",
        "alert_rules": evaluators_and_alerts_manager.get_alerts_config(),
        "recent_alert_events": evaluators_and_alerts_manager.get_recent_alerts()
    }


@router.get("/observability/evaluators")
async def get_langfuse_evaluators(
    current_user: User = Depends(get_current_user)
):
    """Returns evaluator configurations and scoring criteria for the Langfuse Evaluators tab."""
    from app.observability.evaluators_and_alerts import evaluators_and_alerts_manager
    return {
        "status": "success",
        "evaluators": evaluators_and_alerts_manager.get_evaluators()
    }


@router.post("/observability/sync-all")
async def sync_all_observability(
    archive_legacy_duplicates: bool = Query(False, description="Archive id-less dataset items created by older syncs"),
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN]))
):
    """One-click synchronization of Prompts, Golden Datasets, Evaluators, Users, and Sessions to Langfuse Cloud."""
    from app.services.dataset_sync_service import langfuse_dataset_service
    from app.services.langfuse_prompt_service import langfuse_prompt_service
    from app.observability.evaluators_and_alerts import evaluators_and_alerts_manager
    
    p_res = langfuse_prompt_service.push_all_prompts_to_cloud()
    d_res = langfuse_dataset_service.sync_golden_dataset_to_langfuse(archive_legacy_duplicates=archive_legacy_duplicates)
    evals = evaluators_and_alerts_manager.get_evaluators()
    rules = evaluators_and_alerts_manager.get_alerts_config()
    
    return {
        "status": "synchronized" if d_res.get("status") == "success" else "partial",
        "prompts_synced": p_res,
        "dataset_synced": d_res,
        "evaluators_registered": len(evals),
        "alert_rules_registered": len(rules),
        "message": "Full Observability Suite (Sessions, Users, Alerts, Evaluators, Prompts, Datasets) synced with Langfuse Cloud."
    }


@router.post("/observability/alerts/webhook")
async def receive_langfuse_alert_webhook(
    payload: Dict[str, Any],
    _raw_body: bytes = Depends(require_langfuse_webhook),
):
    """Receives inbound alert notifications from Langfuse Cloud webhooks (authenticated like the other webhooks)."""
    from app.observability.evaluators_and_alerts import evaluators_and_alerts_manager
    alert_name = payload.get("alertName") or payload.get("name") or "Langfuse Cloud Alert"
    severity = payload.get("severity") or "WARNING"
    details = payload.get("details") or payload
    
    event = evaluators_and_alerts_manager.trigger_alert(
        rule_name=alert_name,
        severity=severity,
        session_id=str(payload.get("sessionId") or payload.get("traceId") or "system"),
        user_id=str(payload.get("userId") or "langfuse-cloud"),
        message=str(payload.get("message") or f"Alert triggered: {alert_name}"),
        details=details
    )
    return {
        "status": "received",
        "alert_id": event.alert_id,
        "rule_name": event.rule_name,
        "timestamp": event.timestamp
    }


