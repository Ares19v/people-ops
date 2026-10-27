from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["Health & Status"])

@router.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {
        "status": "HEALTHY",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "multi_agent_framework": "Google ADK (Agent Development Kit)",
        "guardrails_engine": "NVIDIA NeMo Guardrails",
        "graph_rag_engine": "Pinecone (integrated inference) Policy RAG",
        "observability": "LangSmith (DPDP Scrubbed)"
    }
