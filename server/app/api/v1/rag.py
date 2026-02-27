from fastapi import APIRouter
from app.services.rag_service import rag_service

router = APIRouter()

@router.get("/search")
async def search(query: str, top_k: int = 10):
    return await rag_service.search(query, top_k)
