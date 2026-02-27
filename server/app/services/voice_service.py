import os
import uuid
import edge_tts
import io
from app.core.config import TTS_CACHE_DIR, ZHIPUAI_API_KEY
from zhipuai import ZhipuAI

class VoiceService:
    def __init__(self):
        self.client = ZhipuAI(api_key=ZHIPUAI_API_KEY)

    @staticmethod
    async def generate_audio(text: str, voice_id: str) -> str:
        """生成语音文件并返回路径"""
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
        file_id = str(uuid.uuid4())
        file_path = os.path.join(TTS_CACHE_DIR, f"{file_id}.mp3")
        
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(file_path)
        return file_path

    async def transcribe_audio(self, audio_file_path: str) -> str:
        """语音转文字 (ASR)"""
        print(f"开始 ASR 识别: {audio_file_path}")
        try:
            with open(audio_file_path, "rb") as f:
                response = self.client.audio.transcriptions.create(
                    model="glm-asr-2512",  # 智谱最新 ASR 模型
                    file=f
                )
            print(f"ASR 成功: {response.text}")
            return response.text
        except Exception as e:
            print(f"ASR 失败 (model=glm-asr-2512): {e}")
            # 尝试回退到旧模型名或其他可用名
            for fallback_model in ["cogvoice-7b", "whisper-1", "zhipu-asr"]:
                try:
                    with open(audio_file_path, "rb") as f:
                        response = self.client.audio.transcriptions.create(
                            model=fallback_model,
                            file=f
                        )
                    print(f"ASR 成功 (fallback={fallback_model}): {response.text}")
                    return response.text
                except Exception as fe:
                    print(f"ASR 失败 (fallback={fallback_model}): {fe}")
            return ""
    
    async def asr_audio_bytes(self, audio_bytes: bytes) -> str:
        """
        从bytes数据进行 ASR 识别（用于 WebSocket 音频流）
        """
        print(f"[语音识别] 处理 {len(audio_bytes)} 字节的音频数据")
        try:
            # 将 bytes 包装为类文件对象
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.wav"  # 设置一个文件名以通过校验
            
            response = self.client.audio.transcriptions.create(
                model="glm-asr-2512",
                file=audio_file
            )
            print(f"[语音识别] 成功: {response.text}")
            return response.text
        except Exception as e:
            print(f"[语音识别] 失败: {e}")
            # 回退逻辑
            for fallback_model in ["cogvoice-7b", "whisper-1"]:
                try:
                    audio_file = io.BytesIO(audio_bytes)
                    audio_file.name = "audio.wav"
                    response = self.client.audio.transcriptions.create(
                        model=fallback_model,
                        file=audio_file
                    )
                    print(f"[语音识别] 成功 (fallback={fallback_model}): {response.text}")
                    return response.text
                except Exception as fe:
                    print(f"[语音识别] 失败 (fallback={fallback_model}): {fe}")
            return ""
    
    async def generate_tts(self, text: str, voice_id: str = "zh-CN-YunxiNeural") -> str:
        """
        生成 TTS 音频并返回 URL
        """
        # 清除 Markdown 符号
        clean_text = text.replace("*", "").replace("#", "").replace("-", "").replace(">", "")
        
        file_path = await self.generate_audio(clean_text, voice_id)
        
        # 返回相对 URL
        file_name = os.path.basename(file_path)
        return f"/static/audio/{file_name}"

voice_service = VoiceService()
