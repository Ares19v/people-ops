import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.guardrails.guardrails_manager import guardrails_manager
from app.agents.orchestrator import orchestrator
from app.models.user import User, UserRole
from app.core.database import AsyncSessionLocal

def call_api(prompt, options, context):
    user_query = context.get('vars', {}).get('user_query', prompt)
    
    async def run():
        async with AsyncSessionLocal() as db:
            mock_user = User(
                id="eval-user-id",
                email="eval@antigravity.corp",
                full_name="Evaluation Evaluator",
                role=UserRole.EMPLOYEE,
                department="QA",
                designation="Test Runner"
            )
            resp = await orchestrator.process_message(db, mock_user, user_query)
            return f"[{resp.guardrail_status}] [ROUTED:{resp.agent_routed}] {resp.response}"

    result = asyncio.run(run())
    return {"output": result}
