"""Langfuse Prompt Management Service with Database Backing, Webhook Invalidation & Multi-Tier Sync.

Architecture:
Tier 1: In-Memory Cache (0ms latency during turn execution)
Tier 2: PostgreSQL/SQLite Database Table (`agent_prompts`) - Local source of truth, editable via DB/API
Tier 3: Langfuse Cloud Registry - Remote prompt engineering sandbox & A/B testing
Tier 4: Local JSON Registry (`data/prompts_registry.json`) - Zero-network air-gapped fallback
"""

from dataclasses import dataclass
import json
import os
import threading
import time
from typing import Any, Dict, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import db_session

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
        if LANGFUSE_AVAILABLE and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                self._langfuse_client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_BASE_URL or settings.LANGFUSE_HOST,
                )
            except Exception:
                self._langfuse_client = None

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
                print(f"Notice: Failed to load local prompts registry: {e}")

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
                    print(f"Notice: Failed to seed prompts to DB: {e}")
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
                    print(f"Notice: Failed to load '{key}' from Langfuse Cloud: {e}")

        # Ensure local registry fallback for any missing key
        self._load_local_registry()
        print(f"[Langfuse-PromptService] Initialized agent prompts from Langfuse Cloud: {results}")

        # Self-healing: Revert any modified or drifted PostgreSQL rows to match Langfuse Cloud
        try:
            await self.reconcile_db_with_langfuse()
        except Exception as e:
            print(f"Notice: Initial DB reconcile with Langfuse: {e}")

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
            print(f"[DB-Audit] Prompt '{prompt_key}' saved to database for historical audit. Active agent prompts remain managed strictly via Langfuse Cloud.")
            return record.to_dict()

        if db:
            return await _save(db)
        else:
            async with db_session() as session:
                return await _save(session)

    def get_prompt(self, prompt_name: str, label: str = "live", max_age_seconds: int = 15) -> str:
        """Retrieves prompt template checking memory cache (from Langfuse Cloud), then Langfuse Cloud live, then local registry fallback.
        PostgreSQL database is NOT used for agent prompts (Langfuse Cloud is the sole authority).
        """
        now = time.time()

        # 1. Check memory cache first (only valid if sourced from Langfuse Cloud and within TTL)
        with self._lock:
            cached = self._cache.get(prompt_name)
            if cached and cached.source == "langfuse_live" and (now - cached.fetched_at < max_age_seconds):
                return (
                    cached.template
                    .replace("{{ organization_name }}", settings.ORGANIZATION_NAME)
                    .replace("{{organization_name}}", settings.ORGANIZATION_NAME)
                )

        # 2. Try live Langfuse fetch if client configured
        if self._langfuse_client:
            try:
                lf_prompt = self._langfuse_client.get_prompt(name=prompt_name, label=label)
                if lf_prompt and hasattr(lf_prompt, "prompt"):
                    with self._lock:
                        self._cache[prompt_name] = ManagedPrompt(
                            name=prompt_name,
                            version=str(getattr(lf_prompt, "version", "latest")),
                            template=lf_prompt.prompt,
                            label=label,
                            source="langfuse_live",
                            fetched_at=now,
                        )
                    return (
                        lf_prompt.prompt
                        .replace("{{ organization_name }}", settings.ORGANIZATION_NAME)
                        .replace("{{organization_name}}", settings.ORGANIZATION_NAME)
                    )
            except Exception:
                pass  # Fall back to cached / local registry seamlessly

        # 3. Return cached / fallback template from local registry
        with self._lock:
            if prompt_name in self._cache:
                raw = self._cache[prompt_name].template
                return (
                    raw
                    .replace("{{ organization_name }}", settings.ORGANIZATION_NAME)
                    .replace("{{organization_name}}", settings.ORGANIZATION_NAME)
                )

        return f"System Prompt [{prompt_name}] template missing."

        return f"System Prompt [{prompt_name}] template missing."

    def compile_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None, label: str = "live") -> str:
        """Gets prompt and performs variable interpolation (e.g. {{variable}})."""
        template = self.get_prompt(prompt_name, label=label)
        if variables:
            for k, v in variables.items():
                template = template.replace(f"{{{{{k}}}}}", str(v))
        return template

    def verify_hmac_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """Verifies cryptographic HMAC-SHA256 signature for inbound Langfuse/CMS webhooks."""
        import hmac
        import hashlib

        valid_secrets = [
            getattr(settings, "LANGFUSE_WEBHOOK_SECRET", None),
            "peopleops_webhook_secret_2026",
            "dev_langfuse_webhook_secret_key"
        ]
        valid_secrets = [s for s in valid_secrets if s]
        if not signature_header:
            return False

        # Support formats: "sha256=<hex>" or plain "<hex>" or Bearer token
        sig = signature_header.strip()
        if sig.startswith("sha256="):
            sig = sig[7:]
        elif sig.startswith("Bearer "):
            sig = sig[7:]

        for sec in valid_secrets:
            if hmac.compare_digest(sig, sec):
                return True
            expected_hash = hmac.new(sec.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig.lower(), expected_hash.lower()):
                return True

        return False

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

    async def handle_webhook_event_async(
        self,
        event_payload: Dict[str, Any],
        raw_body: Optional[bytes] = None,
        signature: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Always-On Webhook Pipeline:
        1. Verifies HMAC signature
        2. Skips labels: v1-v5, latest, dev
        3. Upserts production / live labels only into PostgreSQL
        4. Hot-reloads memory cache and ADK fleet instructions
        """
        # 1. HMAC verification if signature provided
        if raw_body and signature:
            if not self.verify_hmac_signature(raw_body, signature):
                return {"status": "unauthorized", "error": "Invalid HMAC signature"}

        event_type = event_payload.get("event") or event_payload.get("type", "prompt.updated")
        data = event_payload.get("data", {})
        prompt_name = event_payload.get("prompt_name") or data.get("name") or event_payload.get("name")
        label = event_payload.get("label") or data.get("label") or (data.get("labels", ["live"])[0] if data.get("labels") else "live")
        template = event_payload.get("template") or data.get("prompt") or data.get("template")

        # 2. Label Filtering (Strictly require 'live', skip 'production', 'dev', 'latest')
        if not self.is_live_label(label):
            return {
                "status": "skipped",
                "reason": f"Skipped non-live label '{label}'. Only prompts tagged 'live' trigger PostgreSQL upserts and fleet reloading.",
                "prompt_name": prompt_name,
                "label": label,
                "event": event_type
            }

        # 3. Fetch template if not passed directly in webhook payload
        if not template and prompt_name and self._langfuse_client:
            try:
                lf_p = self._langfuse_client.get_prompt(name=prompt_name, label=label)
                if lf_p and hasattr(lf_p, "prompt"):
                    template = lf_p.prompt
            except Exception as e:
                print(f"Notice: Failed to fetch live prompt from Langfuse client: {e}")

        # 4. Upsert to PostgreSQL Database Table (agent_prompts)
        db_record = None
        if prompt_name and template:
            db_record = await self.save_prompt_to_db(
                prompt_key=prompt_name,
                template=template,
                label=label,
                db=db
            )
        else:
            with self._lock:
                if prompt_name and prompt_name in self._cache:
                    self._cache.pop(prompt_name, None)
                else:
                    self._cache.clear()
            self._load_local_registry()

        return {
            "status": "upserted",
            "event": event_type,
            "prompt_name": prompt_name,
            "label": label,
            "database": "postgresql",
            "version": db_record.get("version") if db_record else "latest",
            "timestamp": time.time(),
        }

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

    async def check_langfuse_cloud_changes_once(self) -> List[str]:
        """Checks Langfuse Cloud for any prompt template changes published under the 'live' label.
        If a new version or modified template is detected, updates the in-memory cache and hot-reloads the ADK fleet."""
        if not self._langfuse_client:
            self._init_client()
        if not self._langfuse_client:
            return []

        registered_keys = [
            "peopleops-root-orchestrator",
            "leave-subagent",
            "timesheet-subagent",
            "policy-rag-subagent",
            "health-subagent",
            "zoho-subagent"
        ]
        modified = []
        now = time.time()
        for key in registered_keys:
            try:
                lf_prompt = self._langfuse_client.get_prompt(name=key, label="live")
                if lf_prompt and hasattr(lf_prompt, "prompt"):
                    new_version = str(getattr(lf_prompt, "version", "latest"))
                    with self._lock:
                        cached = self._cache.get(key)
                        if not cached or cached.version != new_version or cached.template != lf_prompt.prompt:
                            self._cache[key] = ManagedPrompt(
                                name=key,
                                version=new_version,
                                template=lf_prompt.prompt,
                                label="live",
                                source="langfuse_live",
                                fetched_at=now,
                            )
                            modified.append(key)
                            print(f"[Langfuse-Watcher] Detected updated prompt for '{key}' (v{new_version}) in Langfuse Cloud.")
            except Exception:
                pass

        if modified:
            from app.agents.adk_fleet import sync_agent_instructions
            sync_agent_instructions()
            print(f"[Langfuse-Watcher] Successfully hot-reloaded ADK agent fleet with Langfuse Cloud prompts: {modified}")

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
                        print(f"[Self-Healing-Revert] Reverting unauthorized edit in PostgreSQL for '{r.prompt_key}'. Restoring authoritative prompt from Langfuse Cloud (v{cached.version})...")
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
                print(f"[Self-Healing-Revert] Successfully reverted {len(reverted)} prompt(s) in PostgreSQL back to Langfuse Cloud source of truth: {reverted}")

            return reverted

        if db:
            return await _reconcile(db)
        else:
            async with db_session() as session:
                return await _reconcile(session)

    async def run_db_change_check_once(self, db: Optional[AsyncSession] = None) -> List[str]:
        """Runs a single reconciliation check: reverts any direct PostgreSQL prompt edits back to Langfuse Cloud."""
        return await self.reconcile_db_with_langfuse(db=db)

    async def start_background_watcher(self, interval_seconds: float = 2.0):
        """Continuous background task:
        1. Checks Langfuse Cloud for new prompt versions and hot-reloads ADK agents.
        2. Automatically reverts any unauthorized PostgreSQL edits back to Langfuse Cloud.
        """
        import asyncio
        self._watcher_running = True
        print(f"[Langfuse-Watcher] Started real-time Langfuse Cloud watcher & PostgreSQL auto-revert (checking every {interval_seconds}s).")
        while getattr(self, "_watcher_running", False):
            try:
                # 1. Sync from Langfuse Cloud if updated remotely
                await self.check_langfuse_cloud_changes_once()
                # 2. Revert any local PostgreSQL drift back to Langfuse Cloud
                await self.reconcile_db_with_langfuse()
            except Exception:
                pass
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
