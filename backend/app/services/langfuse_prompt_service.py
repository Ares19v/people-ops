"""Langfuse Prompt Management Service with Database Backing, Webhook Invalidation & Multi-Tier Sync.

Architecture:
Tier 1: In-Memory Cache (0ms latency during turn execution)
Tier 2: PostgreSQL/SQLite Database Table (`agent_prompts`) - Local source of truth, editable via DB/API
Tier 3: Langfuse Cloud Registry - Remote prompt engineering sandbox & A/B testing
Tier 4: Local JSON Registry (`data/prompts_registry.json`) - Zero-network air-gapped fallback
"""

import logging
from dataclasses import dataclass
import json
import os
import threading
import time
from typing import Any, Dict, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.observability.langfuse_client import get_langfuse
from app.core.database import db_session

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

# Severed link toggle: Setting this to False stops PostgreSQL DB prompt edits from pushing to Langfuse Cloud.
# Set to True to re-enable automated PostgreSQL -> Langfuse Cloud prompt syncing.
ENABLE_POSTGRES_TO_LANGFUSE_SYNC: bool = False


@dataclass
class ManagedPrompt:
    name: str
    version: str
    template: str
    label: str
    source: str  # "database", "langfuse_live", or "local_cache"
    fetched_at: float
    client: Optional[Any] = None  # Langfuse prompt client when fetched from Langfuse


class LangfusePromptService:
    """Manages prompts across memory, PostgreSQL/SQLite database, and Langfuse Cloud with zero-downtime hot reloading."""

    def __init__(self):
        self._cache: Dict[str, ManagedPrompt] = {}
        self._lock = threading.Lock()
        self._langfuse_client: Optional[Any] = None
        self._registry_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "prompts_registry.json"
        )
        self._init_client()
        self._load_local_registry()

    def _init_client(self):
        self._langfuse_client = get_langfuse()

    def _load_local_registry(self):
        """Loads prompt templates decoupled from codebase into local memory."""
        if os.path.exists(self._registry_path):
            try:
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    with self._lock:
                        for name, p_data in data.get("prompts", {}).items():
                            if name not in self._cache:
                                self._cache[name] = ManagedPrompt(
                                    name=name,
                                    version=p_data.get("version", "1.0.0"),
                                    template=p_data.get("template", ""),
                                    label=p_data.get("label", "live"),
                                    source="local_cache",
                                    fetched_at=time.time(),
                                )
            except Exception as e:
                logger.warning(f"Notice: Failed to load local prompts registry: {e}")

    async def seed_db_from_registry(self, db: Optional[AsyncSession] = None) -> int:
        """Seeds the agent_prompts table from local registry if the database table is empty."""
        from app.models.prompt import AgentPrompt

        async def _seed(session: AsyncSession) -> int:
            stmt = select(AgentPrompt)
            res = await session.execute(stmt)
            existing = res.scalars().all()
            if existing:
                return len(existing)

            count = 0
            if os.path.exists(self._registry_path):
                try:
                    with open(self._registry_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for name, p_data in data.get("prompts", {}).items():
                            clean_id = f"PRM-{name.upper().replace('-', '_')[:24]}"
                            prompt_record = AgentPrompt(
                                id=clean_id,
                                prompt_key=name,
                                agent_name=p_data.get("agent_name", name),
                                template=p_data.get("template", ""),
                                version=1,
                                label=p_data.get("label", "live"),
                                is_active=True
                            )
                            session.add(prompt_record)
                            count += 1
                        await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.warning(f"Notice: Failed to seed prompts to DB: {e}")
            return count

        if db:
            return await _seed(db)
        else:
            async with db_session() as session:
                return await _seed(session)

    async def load_prompts_from_langfuse(self) -> Dict[str, Any]:
        """Loads prompt templates directly from Langfuse Cloud into memory cache.
        Langfuse Cloud is the single authoritative source of truth for all agent prompts.
        """
        registered_keys = [
            "peopleops-root-orchestrator",
            "leave-subagent",
            "timesheet-subagent",
            "policy-rag-subagent",
            "health-subagent",
            "zoho-subagent"
        ]
        results = {}
        if not self._langfuse_client:
            self._init_client()

        if self._langfuse_client:
            now = time.time()
            for key in registered_keys:
                try:
                    lf_prompt = self._langfuse_client.get_prompt(name=key, label="live")
                    if lf_prompt and hasattr(lf_prompt, "prompt"):
                        with self._lock:
                            self._cache[key] = ManagedPrompt(
                                name=key,
                                version=str(getattr(lf_prompt, "version", "latest")),
                                template=lf_prompt.prompt,
                                label="live",
                                source="langfuse_live",
                                fetched_at=now,
                            )
                        results[key] = f"v{getattr(lf_prompt, 'version', 'latest')}"
                except Exception as e:
                    logger.warning(f"Notice: Failed to load '{key}' from Langfuse Cloud: {e}")

        # Ensure local registry fallback for any missing key
        self._load_local_registry()
        logger.info(f"[Langfuse-PromptService] Initialized agent prompts from Langfuse Cloud: {results}")

        # Self-healing: Revert any modified or drifted PostgreSQL rows to match Langfuse Cloud
        try:
            await self.reconcile_db_with_langfuse()
        except Exception as e:
            logger.warning(f"Notice: Initial DB reconcile with Langfuse: {e}")

        return results

    async def load_prompts_from_db(self, db: Optional[AsyncSession] = None) -> int:
        """DEPRECATED: Agent prompts are managed strictly via Langfuse Cloud.
        Database records exist for historical audit only."""
        return len(self._cache)

    async def save_prompt_to_db(
        self,
        prompt_key: str,
        template: str,
        agent_name: Optional[str] = None,
        label: str = "live",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Saves a prompt to the database table for historical/audit logging only.
        NOTE: Active agent prompts are strictly managed in Langfuse Cloud, so DB edits
        do NOT update the active agent memory cache or trigger instruction reloading."""
        from app.models.prompt import AgentPrompt

        async def _save(session: AsyncSession):
            stmt = select(AgentPrompt).where(AgentPrompt.prompt_key == prompt_key)
            res = await session.execute(stmt)
            record = res.scalar_one_or_none()

            if record:
                record.template = template
                record.version = int(record.version or 0) + 1
                record.label = label
                if agent_name:
                    record.agent_name = agent_name
            else:
                record = AgentPrompt(
                    prompt_key=prompt_key,
                    agent_name=agent_name or prompt_key,
                    template=template,
                    version=1,
                    label=label,
                    is_active=True
                )
                session.add(record)

            await session.commit()
            await session.refresh(record)
            logger.info(f"[DB-Audit] Prompt '{prompt_key}' saved to database for historical audit. Active agent prompts remain managed strictly via Langfuse Cloud.")
            return record.to_dict()

        if db:
            return await _save(db)
        else:
            async with db_session() as session:
                return await _save(session)

    def _render(self, template: str) -> str:
        return (
            template
            .replace("{{ organization_name }}", settings.ORGANIZATION_NAME)
            .replace("{{organization_name}}", settings.ORGANIZATION_NAME)
        )

    def get_prompt(self, prompt_name: str, label: str = "live", max_age_seconds: int = 15) -> str:
        """Retrieves a prompt template: fresh memory cache, then Langfuse Cloud, then the local registry.

        Langfuse is the authority for agent prompts. If it is unreachable, the SDK serves its own cached
        copy or the local-registry fallback passed below, so a Langfuse outage never breaks the agents.
        """
        now = time.time()

        # 1. Fresh copy fetched from Langfuse within the TTL
        with self._lock:
            cached = self._cache.get(prompt_name)
            if cached and cached.source == "langfuse_live" and (now - cached.fetched_at < max_age_seconds):
                return self._render(cached.template)
            local_template = cached.template if cached else None

        # 2. Live Langfuse fetch (SDK handles caching, retries and the fallback template)
        if self._langfuse_client:
            try:
                kwargs: Dict[str, Any] = {
                    "cache_ttl_seconds": max_age_seconds,
                    "fetch_timeout_seconds": 3,
                    "max_retries": 1,
                }
                if local_template:
                    kwargs["fallback"] = local_template
                lf_prompt = self._langfuse_client.get_prompt(name=prompt_name, label=label, **kwargs)
                if lf_prompt and hasattr(lf_prompt, "prompt"):
                    from_langfuse = not getattr(lf_prompt, "is_fallback", False)
                    with self._lock:
                        self._cache[prompt_name] = ManagedPrompt(
                            name=prompt_name,
                            version=str(getattr(lf_prompt, "version", "latest")),
                            template=lf_prompt.prompt,
                            label=label,
                            source="langfuse_live" if from_langfuse else "local_cache",
                            fetched_at=now,
                            client=lf_prompt if from_langfuse else None,
                        )
                    return self._render(lf_prompt.prompt)
            except Exception as exc:
                logger.warning("Langfuse prompt '%s' (label=%s) unavailable, using cached/local copy: %s", prompt_name, label, exc)

        # 3. Cached / local registry template
        with self._lock:
            if prompt_name in self._cache:
                return self._render(self._cache[prompt_name].template)

        return f"System Prompt [{prompt_name}] template missing."

    def get_prompt_client(self, prompt_name: str) -> Optional[Any]:
        """Langfuse prompt client last fetched for `prompt_name` (None if served locally).

        Pass it to `langsmith_tracer.record_generation(prompt=...)` to link generations to a prompt version.
        """
        with self._lock:
            cached = self._cache.get(prompt_name)
            return cached.client if cached else None

    def compile_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None, label: str = "live") -> str:
        """Gets prompt and performs variable interpolation (e.g. {{variable}})."""
        template = self.get_prompt(prompt_name, label=label)
        if variables:
            for k, v in variables.items():
                template = template.replace(f"{{{{{k}}}}}", str(v))
        return template

    def verify_hmac_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """Verifies a webhook credential: Langfuse `t=..,v1=..` signature, shared secret, or body HMAC."""
        from app.services.webhook_auth import verify_webhook_credentials
        return verify_webhook_credentials(raw_body, [signature_header])

    def is_live_label(self, label: Optional[str]) -> bool:
        """Filters labels to strictly allow 'live' and skip 'production', 'v1-v5', 'latest', 'dev'."""
        if not label:
            return True  # Default to live if unspecified
        normalized = label.strip().lower()
        return normalized == "live"

    def handle_webhook_event(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous webhook event handler for cache invalidation & updates."""
        prompt_name = event_payload.get("prompt_name") or event_payload.get("name")
        with self._lock:
            if prompt_name and prompt_name in self._cache:
                self._cache.pop(prompt_name, None)
            else:
                self._cache.clear()
        self._load_local_registry()
        return {
            "status": "success",
            "prompt_name": prompt_name,
            "prompt_key": prompt_name,
            "event": event_payload.get("event", "prompt.updated")
        }

    @staticmethod
    def parse_webhook_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise a webhook body.

        Langfuse sends {"type": "prompt-version", "action": created|updated|deleted,
        "prompt": {"name", "version", "labels", "prompt", ...}}. The older flat shape
        ({"prompt_name", "label", "template"} / {"data": {...}}) is still understood.
        """
        prompt_obj = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        name = prompt_obj.get("name") or payload.get("prompt_name") or data.get("name") or payload.get("name")
        labels = prompt_obj.get("labels")
        if labels is None:
            single = payload.get("label") or data.get("label")
            labels = [single] if single else (data.get("labels") or [])
        template = prompt_obj.get("prompt") or payload.get("template") or data.get("prompt") or data.get("template")
        return {
            "event": payload.get("type") or payload.get("event") or "prompt.updated",
            "action": payload.get("action") or "updated",
            "prompt_name": name,
            "version": prompt_obj.get("version") or data.get("version"),
            "labels": [str(l) for l in labels],
            "template": template if isinstance(template, str) else None,
            "langfuse_format": bool(prompt_obj),
        }

    async def handle_webhook_event_async(
        self,
        event_payload: Dict[str, Any],
        raw_body: Optional[bytes] = None,
        signature: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Prompt webhook pipeline (the caller has already authenticated the request):
        1. Ignore events that do not concern the 'live' label
        2. Pull the new live version from Langfuse (or take the template from the payload)
        3. Hot-reload the ADK fleet so the next turn uses it
        4. Record an audit row in PostgreSQL (history only; Langfuse stays the authority)
        """
        if raw_body and signature and not self.verify_hmac_signature(raw_body, signature):
            return {"status": "unauthorized", "error": "Invalid webhook signature"}

        event = self.parse_webhook_event(event_payload)
        prompt_name, labels, template = event["prompt_name"], event["labels"], event["template"]
        base = {"event": event["event"], "action": event["action"], "prompt_name": prompt_name, "timestamp": time.time()}

        # 1. Only changes to the live label matter. With no label information at all, assume live.
        concerns_live = (not labels) or any(self.is_live_label(l) for l in labels)
        if not concerns_live:
            return {**base, "status": "skipped", "label": labels[0] if labels else None,
                    "reason": f"Skipped labels {labels}: only prompts tagged 'live' trigger a reload."}

        # 2./3. Refresh the cache and the agents
        if event["action"] == "deleted" and prompt_name:
            with self._lock:
                self._cache.pop(prompt_name, None)
            self._load_local_registry()
            self._reload_fleet()
            return {**base, "status": "invalidated", "label": "live"}

        refreshed: List[str] = []
        if prompt_name:
            refreshed = await self.check_langfuse_cloud_changes_once(names=[prompt_name])
            if not refreshed and template and not self._langfuse_client:
                with self._lock:
                    self._cache[prompt_name] = ManagedPrompt(
                        name=prompt_name, version=str(event["version"] or "latest"), template=template,
                        label="live", source="langfuse_live", fetched_at=time.time(),
                    )
                self._reload_fleet()
                refreshed = [prompt_name]
        else:
            with self._lock:
                self._cache.clear()
            self._load_local_registry()
            refreshed = await self.check_langfuse_cloud_changes_once()
            self._reload_fleet()

        # 4. Audit trail
        db_record = None
        if prompt_name and template:
            db_record = await self.save_prompt_to_db(prompt_key=prompt_name, template=template, label="live", db=db)

        return {
            **base,
            "status": "upserted",
            "label": "live",
            "reloaded": refreshed,
            "database": "postgresql",
            "version": (db_record or {}).get("version") or event["version"] or "latest",
        }

    def _reload_fleet(self) -> None:
        try:
            from app.agents.adk_fleet import sync_agent_instructions
            sync_agent_instructions()
        except Exception as exc:
            logger.warning("Could not hot-reload ADK fleet instructions: %s", exc)

    async def sync_db_prompts_to_cloud(self, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """Loads all active prompts directly from PostgreSQL, updates local cache and ADK fleet,
        and pushes them to Langfuse Cloud under ['live', 'production'] labels, updating the version in DB."""
        from app.models.prompt import AgentPrompt
        from app.agents.adk_fleet import sync_agent_instructions

        if not self._langfuse_client:
            self._init_client()

        async def _sync(session: AsyncSession) -> Dict[str, Any]:
            stmt = select(AgentPrompt).where(AgentPrompt.is_active == True)
            res = await session.execute(stmt)
            records = res.scalars().all()

            pushed = []
            errors = []
            version_map = {}

            with self._lock:
                for r in records:
                    self._cache[r.prompt_key] = ManagedPrompt(
                        name=r.prompt_key,
                        version=str(r.version),
                        template=r.template,
                        label=r.label,
                        source="database",
                        fetched_at=time.time(),
                    )

            # Hot-reload agent instructions in memory
            sync_agent_instructions()

            # Push to Langfuse Cloud
            if self._langfuse_client:
                for r in records:
                    try:
                        lf_p = self._langfuse_client.create_prompt(
                            name=r.prompt_key,
                            prompt=r.template,
                            labels=["live", "production"],
                            type="text",
                            tags=["peopleops", "adk-agents"]
                        )
                        new_version = getattr(lf_p, "version", None)
                        if new_version:
                            r.version = new_version
                            version_map[r.prompt_key] = new_version
                            with self._lock:
                                if r.prompt_key in self._cache:
                                    self._cache[r.prompt_key].version = str(new_version)
                        pushed.append(r.prompt_key)
                    except Exception as e:
                        errors.append({"name": r.prompt_key, "error": str(e)})

                await session.commit()

            return {
                "status": "success" if not errors else "partial",
                "pushed_count": len(pushed),
                "pushed_prompts": pushed,
                "version_map": version_map,
                "errors": errors
            }

        if db:
            return await _sync(db)
        else:
            async with db_session() as session:
                return await _sync(session)

    async def sync_single_prompt_to_cloud(self, prompt_key: str, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """Syncs a single prompt from the database directly to Langfuse Cloud and updates its version."""
        from app.models.prompt import AgentPrompt
        from app.agents.adk_fleet import sync_agent_instructions

        if not self._langfuse_client:
            self._init_client()

        async def _sync_single(session: AsyncSession) -> Dict[str, Any]:
            stmt = select(AgentPrompt).where(AgentPrompt.prompt_key == prompt_key)
            res = await session.execute(stmt)
            record = res.scalar_one_or_none()
            if not record:
                raise ValueError(f"Prompt '{prompt_key}' not found in database.")

            with self._lock:
                self._cache[record.prompt_key] = ManagedPrompt(
                    name=record.prompt_key,
                    version=str(record.version),
                    template=record.template,
                    label=record.label,
                    source="database",
                    fetched_at=time.time(),
                )

            sync_agent_instructions()

            if not self._langfuse_client:
                return {
                    "status": "skipped",
                    "reason": "Langfuse client not configured",
                    "prompt_key": prompt_key,
                    "version": record.version
                }

            lf_p = self._langfuse_client.create_prompt(
                name=record.prompt_key,
                prompt=record.template,
                labels=["live", "production"],
                type="text",
                tags=["peopleops", "adk-agents"]
            )
            new_version = getattr(lf_p, "version", record.version)
            record.version = new_version
            with self._lock:
                if record.prompt_key in self._cache:
                    self._cache[record.prompt_key].version = str(new_version)
            await session.commit()

            return {
                "status": "success",
                "prompt_key": prompt_key,
                "version": new_version,
                "labels": ["live", "production"],
                "message": f"Prompt '{prompt_key}' successfully synced to Langfuse Cloud as version {new_version}."
            }

        if db:
            return await _sync_single(db)
        else:
            async with db_session() as session:
                return await _sync_single(session)

    def push_all_prompts_to_cloud(self) -> Dict[str, Any]:
        """Pushes cached local prompt templates to Langfuse Cloud under both 'live' and 'production' labels."""
        if not self._langfuse_client:
            return {"status": "skipped", "reason": "Langfuse client not configured"}

        pushed = []
        errors = []
        with self._lock:
            prompts_to_push = list(self._cache.items())

        for name, p_data in prompts_to_push:
            try:
                self._langfuse_client.create_prompt(
                    name=name,
                    prompt=p_data.template,
                    labels=["live"],
                    type="text",
                    tags=["peopleops", "adk-agents"]
                )
                pushed.append(name)
            except Exception as e:
                errors.append({"name": name, "error": str(e)})

        return {
            "status": "success",
            "pushed_count": len(pushed),
            "pushed_prompts": pushed,
            "errors": errors
        }

    REGISTERED_PROMPTS = (
        "peopleops-root-orchestrator",
        "leave-subagent",
        "timesheet-subagent",
        "policy-rag-subagent",
        "health-subagent",
        "zoho-subagent",
    )

    async def check_langfuse_cloud_changes_once(self, names: Optional[List[str]] = None) -> List[str]:
        """Fetches the 'live' prompts straight from Langfuse (bypassing the SDK cache) and, if any changed,
        updates the in-memory cache and hot-reloads the ADK fleet. Returns the names that changed."""
        if not self._langfuse_client:
            self._init_client()
        if not self._langfuse_client:
            return []

        modified: List[str] = []
        now = time.time()
        for key in (names or self.REGISTERED_PROMPTS):
            try:
                lf_prompt = self._langfuse_client.get_prompt(
                    name=key, label="live", cache_ttl_seconds=0, fetch_timeout_seconds=5, max_retries=1
                )
                if lf_prompt and hasattr(lf_prompt, "prompt") and not getattr(lf_prompt, "is_fallback", False):
                    new_version = str(getattr(lf_prompt, "version", "latest"))
                    with self._lock:
                        cached = self._cache.get(key)
                        if (not cached or cached.version != new_version or cached.template != lf_prompt.prompt
                                or cached.source != "langfuse_live"):
                            changed = not cached or cached.version != new_version or cached.template != lf_prompt.prompt
                            self._cache[key] = ManagedPrompt(
                                name=key,
                                version=new_version,
                                template=lf_prompt.prompt,
                                label="live",
                                source="langfuse_live",
                                fetched_at=now,
                                client=lf_prompt,
                            )
                            if changed:
                                modified.append(key)
                                logger.info(f"[Langfuse-Watcher] Detected updated prompt for '{key}' (v{new_version}) in Langfuse Cloud.")
            except Exception as exc:
                logger.debug("Langfuse prompt check for '%s' failed: %s", key, exc)

        if modified:
            self._reload_fleet()
            logger.info(f"[Langfuse-Watcher] Hot-reloaded ADK agent fleet with Langfuse Cloud prompts: {modified}")

        return modified

    async def reconcile_db_with_langfuse(self, db: Optional[AsyncSession] = None) -> List[str]:
        """Checks PostgreSQL agent_prompts table against authoritative Langfuse Cloud templates.
        If any row was modified or drifted in PostgreSQL, it automatically REVERTS the PostgreSQL
        row back to the exact authoritative template from Langfuse Cloud.
        """
        from app.models.prompt import AgentPrompt
        from datetime import datetime, timezone

        async def _reconcile(session: AsyncSession) -> List[str]:
            reverted = []
            stmt = select(AgentPrompt).where(AgentPrompt.is_active == True)
            res = await session.execute(stmt)
            records = res.scalars().all()
            if not records:
                return []

            for r in records:
                with self._lock:
                    cached = self._cache.get(r.prompt_key)

                if cached and cached.template:
                    # Detect drift in template or version
                    template_drifted = (r.template != cached.template)
                    version_drifted = False
                    try:
                        version_drifted = (int(r.version or 0) != int(cached.version))
                    except (ValueError, TypeError):
                        version_drifted = (str(r.version) != str(cached.version))

                    if template_drifted or version_drifted:
                        logger.info(f"[Self-Healing-Revert] Reverting unauthorized edit in PostgreSQL for '{r.prompt_key}'. Restoring authoritative prompt from Langfuse Cloud (v{cached.version})...")
                        r.template = cached.template
                        try:
                            r.version = int(cached.version)
                        except (ValueError, TypeError):
                            pass
                        r.label = cached.label or "live"
                        r.updated_at = datetime.now(timezone.utc)
                        reverted.append(r.prompt_key)

            if reverted:
                await session.commit()
                logger.info(f"[Self-Healing-Revert] Successfully reverted {len(reverted)} prompt(s) in PostgreSQL back to Langfuse Cloud source of truth: {reverted}")

            return reverted

        if db:
            return await _reconcile(db)
        else:
            async with db_session() as session:
                return await _reconcile(session)

    async def run_db_change_check_once(self, db: Optional[AsyncSession] = None) -> List[str]:
        """Runs a single reconciliation check: reverts any direct PostgreSQL prompt edits back to Langfuse Cloud."""
        return await self.reconcile_db_with_langfuse(db=db)

    async def start_background_watcher(self, interval_seconds: Optional[float] = None):
        """Continuous background task:
        1. Checks Langfuse Cloud for new prompt versions and hot-reloads ADK agents.
        2. Automatically reverts any unauthorized PostgreSQL edits back to Langfuse Cloud.
        """
        import asyncio
        interval_seconds = interval_seconds or settings.PROMPT_WATCH_INTERVAL_SECONDS
        self._watcher_running = True
        logger.info(f"[Langfuse-Watcher] Started real-time Langfuse Cloud watcher & PostgreSQL auto-revert (checking every {interval_seconds}s).")
        while getattr(self, "_watcher_running", False):
            try:
                # 1. Sync from Langfuse Cloud if updated remotely
                await self.check_langfuse_cloud_changes_once()
                # 2. Revert any local PostgreSQL drift back to Langfuse Cloud
                await self.reconcile_db_with_langfuse()
            except Exception:
                logger.debug("Suppressed non-fatal error", exc_info=True)
            await asyncio.sleep(interval_seconds)

    def stop_background_watcher(self):
        """Stops the real-time background watcher."""
        self._watcher_running = False

    def list_prompts(self) -> Dict[str, Any]:
        """Returns all registered prompt templates in memory cache and database."""
        with self._lock:
            return {
                name: {
                    "name": p.name,
                    "version": p.version,
                    "label": p.label,
                    "source": p.source,
                    "fetched_at": p.fetched_at,
                    "template_preview": p.template[:120] + "..." if len(p.template) > 120 else p.template
                }
                for name, p in self._cache.items()
            }


langfuse_prompt_service = LangfusePromptService()
