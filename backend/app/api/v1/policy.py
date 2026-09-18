from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Query
from app.services.auth_service import get_current_user
from app.models.user import User
from app.services.graph_rag_service import graph_rag_service

router = APIRouter(prefix="/policy", tags=["HR Policy & Graph RAG"])

@router.get("/search")
async def search_policies(
    q: str = Query(..., min_length=2, description="Search term for HR policy or labour law"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    result = await graph_rag_service.search_policies(q)
    return result
