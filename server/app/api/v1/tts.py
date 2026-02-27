from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.voice_service import voice_service

router = APIRouter()

@router.get("/generate")
async def generate_tts(text: str, voice_id: str = "zh-CN-YunxiNeural"):
    """生成 TTS 音频流"""
    audio_path = await voice_service.generate_audio(text, voice_id)
    
    def iterfile():
        with open(audio_path, mode="rb") as f:
            yield from f
            
    return StreamingResponse(iterfile(), media_type="audio/mpeg")
