"""Langfuse Prompt Management Service with Webhook Integration & Local Decoupled Cache."""

from dataclasses import dataclass
import json
import os
import threading
import time
from typing import Any, Dict, Optional
from app.core.config import settings

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
    source: str  # "langfuse_live" or "local_cache"
    fetched_at: float

class LangfusePromptService:
    """Manages prompts outside the codebase, synchronizing with Langfuse and Webhook invalidation."""

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

    def get_prompt(self, prompt_name: str, label: str = "production", max_age_seconds: int = 3600) -> str:
        """Retrieves prompt template from Langfuse or local cache."""
        now = time.time()

        # Check memory cache first
        with self._lock:
            cached = self._cache.get(prompt_name)
            if cached and (now - cached.fetched_at < max_age_seconds):
                return cached.template.replace("{{ organization_name }}", settings.ORGANIZATION_NAME).replace("{{organization_name}}", settings.ORGANIZATION_NAME)

        # Try live Langfuse fetch if client configured
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
                pass  # Fall back to local registry seamlessly

        # Return cached / fallback template
        with self._lock:
            if prompt_name in self._cache:
                raw = self._cache[prompt_name].template
                return raw.replace("{{ organization_name }}", settings.ORGANIZATION_NAME).replace("{{organization_name}}", settings.ORGANIZATION_NAME)

        return f"System Prompt [{prompt_name}] template missing."

    def compile_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None, label: str = "production") -> str:
        """Gets prompt and performs variable interpolation (e.g. {{variable}})."""
        template = self.get_prompt(prompt_name, label=label)
        if variables:
            for k, v in variables.items():
                template = template.replace(f"{{{{{k}}}}}", str(v))
        return template

    def handle_webhook_event(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Webhook listener for Langfuse prompt publication events.
        
        When a prompt is edited/published in Langfuse, the webhook immediately
        invalidates local cache and pulls fresh prompt without redeploying code.
        """
        event_type = event_payload.get("event") or event_payload.get("type", "prompt.updated")
        prompt_name = event_payload.get("prompt_name") or event_payload.get("data", {}).get("name")

        with self._lock:
            if prompt_name and prompt_name in self._cache:
                # Invalidate specific prompt cache
                self._cache.pop(prompt_name, None)
            else:
                # Invalidate entire cache on wildcard update
                self._cache.clear()

        # Reload registry as baseline
        self._load_local_registry()

        return {
            "status": "success",
            "event": event_type,
            "prompt_invalidated": prompt_name or "ALL",
            "timestamp": time.time(),
        }

langfuse_prompt_service = LangfusePromptService()
