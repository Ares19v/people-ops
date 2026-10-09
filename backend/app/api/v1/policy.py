from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, Header
from app.services.graph_rag_service import graph_rag_service

router = APIRouter(prefix="/policy", tags=["HR Policy & Graph RAG"])

@router.get("/search")
async def search_policies(
    q: str = Query(..., min_length=2, description="Search term for HR policy or labour law"),
) -> Dict[str, Any]:
    result = await graph_rag_service.search_policies(q)
    return result

@router.get("/graph")
async def get_live_knowledge_graph() -> Dict[str, Any]:
    """Returns live nodes, relationships, and property schemas directly from Neo4j Aura Cloud."""
    return graph_rag_service.get_live_graph_data()


