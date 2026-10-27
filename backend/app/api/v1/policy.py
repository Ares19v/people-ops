from typing import Dict, Any
from fastapi import APIRouter, Query
from app.services.policy_rag_service import policy_rag_service

router = APIRouter(prefix="/policy", tags=["HR Policy RAG"])

@router.get("/search")
async def search_policies(
    q: str = Query(..., min_length=2, description="Search term for HR policy or labour law"),
) -> Dict[str, Any]:
    result = await policy_rag_service.search_policies(q)
    return result
