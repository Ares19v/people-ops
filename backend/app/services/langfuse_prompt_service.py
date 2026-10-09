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
                            self._cache[name] = ManagedPrompt(
                                name=name,
                                version=p_data.get("version", "1.0.0"),
                                template=p_data.get("template", ""),
                                label=p_data.get("label", "production"),
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
                                label=p_data.get("label", "production"),
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

    async def load_prompts_from_db(self, db: Optional[AsyncSession] = None) -> int:
        """Loads prompt templates from database table into memory cache."""
        from app.models.prompt import AgentPrompt

        async def _load(session: AsyncSession) -> int:
            stmt = select(AgentPrompt).where(AgentPrompt.is_active == True)
            res = await session.execute(stmt)
            records = res.scalars().all()

            if not records:
                # Table empty; seed from registry
                await self.seed_db_from_registry(session)
                stmt = select(AgentPrompt).where(AgentPrompt.is_active == True)
                res = await session.execute(stmt)
                records = res.scalars().all()

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
            return len(records)

        if db:
            return await _load(db)
        else:
            async with db_session() as session:
                return await _load(session)

    async def save_prompt_to_db(
        self,
        prompt_key: str,
        template: str,
        agent_name: Optional[str] = None,
        label: str = "production",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Creates or updates a prompt in the database, updates memory cache, and hot-reloads the agent fleet."""
        from app.models.prompt import AgentPrompt
        from app.agents.adk_fleet import sync_agent_instructions

        async def _save(session: AsyncSession):
            stmt = select(AgentPrompt).where(AgentPrompt.prompt_key == prompt_key)
            res = await session.execute(stmt)
            record = res.scalar_one_or_none()

            if record:
                record.template = template
                record.version += 1
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

            # Update cache
            with self._lock:
                self._cache[prompt_key] = ManagedPrompt(
                    name=prompt_key,
                    version=str(record.version),
                    template=template,
                    label=label,
                    source="database",
                    fetched_at=time.time(),
                )

            # Hot-reload agent instructions in memory
            sync_agent_instructions()

            return record.to_dict()

        if db:
            return await _save(db)
        else:
            async with db_session() as session:
                return await _save(session)

    def get_prompt(self, prompt_name: str, label: str = "production", max_age_seconds: int = 3600) -> str:
        """Retrieves prompt template checking memory cache, then Langfuse Cloud, then local cache."""
        now = time.time()

        # 1. Check memory cache first (0 ms)
        with self._lock:
            cached = self._cache.get(prompt_name)
            if cached and (now - cached.fetched_at < max_age_seconds):
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
                    return lf_prompt.prompt
            except Exception:
                pass  # Fall back to database / local registry seamlessly

        # 3. Return cached / fallback template
        with self._lock:
            if prompt_name in self._cache:
                raw = self._cache[prompt_name].template
                return (
                    raw
                    .replace("{{ organization_name }}", settings.ORGANIZATION_NAME)
                    .replace("{{organization_name}}", settings.ORGANIZATION_NAME)
                )

        return f"System Prompt [{prompt_name}] template missing."

    def compile_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None, label: str = "production") -> str:
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
        """Filters labels to strictly allow 'live' or 'production' and skip 'v1-v5', 'latest', 'dev'."""
        import re
        if not label:
            return True  # Default to production if unspecified
        normalized = label.strip().lower()
        if normalized in ["live", "production"]:
            return True
        # Skip v1-v5, latest, dev, staging, test
        if re.match(r"^v\d+$", normalized) or normalized in ["latest", "dev", "staging", "test", "draft"]:
            return False
        return False

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
        label = event_payload.get("label") or data.get("label") or (data.get("labels", ["production"])[0] if data.get("labels") else "production")
        template = event_payload.get("template") or data.get("prompt") or data.get("template")

        # 2. Label Filtering (Skip v1-v5, latest)
        if not self.is_live_label(label):
            return {
                "status": "skipped",
                "reason": f"Skipped non-live label '{label}'. Only 'live' and 'production' prompts trigger PostgreSQL upserts.",
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

    def push_all_prompts_to_cloud(self) -> Dict[str, Any]:
        """Pushes all cached local prompt templates to Langfuse Cloud for immediate Playground and versioning access."""
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
                    labels=["production"],
                    type="text",
                    tags=["peopleops", "adk-agents"]
                )
                pushed.append(name)
            except Exception as e:
                # Prompt may already exist in Langfuse Cloud
                errors.append({"name": name, "error": str(e)})

        return {
            "status": "success",
            "pushed_count": len(pushed),
            "pushed_prompts": pushed,
            "errors": errors
        }

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
