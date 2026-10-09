"""
PeopleOps — Prompt Push & Sync CLI Utility
==========================================
Implements Step 1 of the Prompt Push & Sync Pipeline:
1. Pushes prompt template to Langfuse Cloud
2. Sets label ('live', 'production', 'v2', 'latest')
3. Triggers Webhook Receiver with HMAC-SHA256 signature
4. Webhook filters non-live labels and upserts 'live'/'production' into PostgreSQL
5. Hot-reloads in-memory fleet instructions for runtime execution
"""

import os
import sys
import json
import time
import hmac
import hashlib
import httpx
from typing import Optional
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

from langfuse import Langfuse
from app.core.config import settings

def push_and_sync_prompt(
    prompt_name: str,
    template: str,
    label: str = "live",
    backend_url: str = "http://localhost:8000"
):
    print("=" * 70)
    print("STEP 1: DEVELOPER / SCRIPT (Push Prompt + Set Label)")
    print("=" * 70)
    print(f"Prompt Name : {prompt_name}")
    print(f"Label       : {label}")
    print(f"Template    : {template[:80]}...\n")

    # 1. Push to Langfuse Cloud
    lf = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )
    print(f"Pushing [{prompt_name}] to Langfuse Cloud with label='{label}'...")
    try:
        p = lf.create_prompt(
            name=prompt_name,
            prompt=template,
            labels=[label],
            type="text"
        )
        print(f"✅ Created in Langfuse Cloud (Version: {getattr(p, 'version', 'latest')})\n")
    except Exception as e:
        print(f"Notice from Langfuse Cloud: {e}\n")

    # 2. Trigger Webhook with HMAC Signature
    print("=" * 70)
    print("STEP 2 & 3: WEBHOOK RECEIVER (HMAC Verification + Label Filter)")
    print("=" * 70)
    secret = getattr(settings, "LANGFUSE_WEBHOOK_SECRET", "peopleops_webhook_secret_2026")
    payload = {
        "event": "prompt.updated",
        "prompt_name": prompt_name,
        "label": label,
        "template": template,
        "timestamp": time.time()
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    webhook_url = f"{backend_url}/api/v1/agents/webhooks/langfuse"
    headers = {
        "Content-Type": "application/json",
        "X-Langfuse-Signature": f"sha256={signature}",
        "X-Webhook-Secret": secret
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook_url, content=raw_body, headers=headers)
            print(f"Webhook HTTP Status: {resp.status_code}")
            res_data = resp.json()
            print(f"Webhook Response   : {res_data}\n")

            if res_data.get("status") == "skipped":
                print(f"⚠️  FILTER WORKED: Non-live label '{label}' skipped from database upsert.")
            elif res_data.get("status") == "upserted":
                print(f"✅ STEP 4 & 5: Upserted into PostgreSQL `agent_prompts` and hot-reloaded fleet in memory!")
    except Exception as err:
        print(f"Webhook dispatch notice (server may not be running on {backend_url}): {err}")
        print("Executing in-process async sync directly...")
        import asyncio
        from app.services.langfuse_prompt_service import langfuse_prompt_service
        from app.core.database import db_session

        async def run_direct():
            async with db_session() as db:
                res = await langfuse_prompt_service.handle_webhook_event_async(
                    event_payload=payload,
                    raw_body=raw_body,
                    signature=f"sha256={signature}",
                    db=db
                )
                print("Direct In-Process Result:", res)
        asyncio.run(run_direct())

    print("=" * 70)
    print("PIPELINE EXECUTION COMPLETE!")
    print("=" * 70)

if __name__ == "__main__":
    prompt_key = sys.argv[1] if len(sys.argv) > 1 else "leave-subagent"
    label_arg = sys.argv[2] if len(sys.argv) > 2 else "live"
    custom_template = sys.argv[3] if len(sys.argv) > 3 else (
        "You are the Authoritative Leave Subagent. Adhere strictly to the Maharashtra Shops & Establishments Act, 2017 Section 18. "
        "EL is capped at 45 days. CL is 8 days."
    )

    push_and_sync_prompt(prompt_key, custom_template, label=label_arg)
