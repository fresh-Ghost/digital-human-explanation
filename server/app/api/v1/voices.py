from fastapi import APIRouter
from app.core.config import AVAILABLE_VOICES

router = APIRouter()

@router.get("/list")
async def list_voices():
    return {"voices": AVAILABLE_VOICES}
