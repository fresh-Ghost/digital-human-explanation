from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1 import knowledge, files, rag, voices, curator, script, tts, audit, runtime
from app.core.config import TTS_CACHE_DIR
import os

app = FastAPI(title="Lingjing-Lite MVP API")

# 确保 TTS 缓存目录存在
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/api/v1/tts/cache", StaticFiles(directory=TTS_CACHE_DIR), name="tts_cache")
app.mount("/static/audio", StaticFiles(directory=TTS_CACHE_DIR), name="audio")  # 增强版使用

# 注册路由
app.include_router(knowledge.router, prefix="/api/v1/knowledge-bases", tags=["Knowledge Base"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge-base", tags=["Knowledge Base"]) # 兼容旧路径
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(files.router, prefix="/api/v1", tags=["Upload"]) # 兼容 /api/v1/upload
app.include_router(rag.router, prefix="/api/v1/rag", tags=["RAG"])
app.include_router(voices.router, prefix="/api/v1/voices", tags=["Voices"])
app.include_router(curator.router, prefix="/api/v1/curator", tags=["Curator"])
app.include_router(script.router, prefix="/api/v1/script", tags=["Script"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["TTS"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])
app.include_router(runtime.router, tags=["Runtime"])  # WebSocket 路由，不需要 prefix

@app.get("/")
async def root():
    return {"status": "ok", "message": "Lingjing-Lite MVP running (Modularized)"}

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Lingjing-Lite MVP running (Modularized)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
