import os
import sys
from zhipuai import ZhipuAI

# 将项目根目录添加到路径以便导入配置
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.core.config import ZHIPUAI_API_KEY

def diagnostic():
    client = ZhipuAI(api_key=ZHIPUAI_API_KEY)
    print(f"Using API Key: {ZHIPUAI_API_KEY[:5]}...{ZHIPUAI_API_KEY[-5:]}")
    
    # 1. 检查可用模型 (如果 API 支持列出模型)
    print("\n--- Testing Model Access ---")
    models_to_test = ["glm-asr-2512", "cogvoice-7b", "whisper-1"]
    
    # 由于智谱 SDK 可能没有 list_models，我们尝试用一个极小的音频测试，或者检查文档中的权限
    print("ASR models typically require specific audio formats (16k, 16bit, mono, wav/mp3/m4a/webm).")
    
    # 2. 检查最近生成的语音文件
    voice_dir = os.path.join(os.path.dirname(__file__), "temp_voice")
    if os.path.exists(voice_dir):
        files = os.listdir(voice_dir)
        print(f"\nRecent voice files in {voice_dir}: {files}")
        if files:
            latest_file = os.path.join(voice_dir, files[-1])
            print(f"Testing file: {latest_file}, Size: {os.path.getsize(latest_file)} bytes")
            
            # 检查文件头
            with open(latest_file, "rb") as f:
                header = f.read(12)
                print(f"File Header: {header}")
            
            for model in models_to_test:
                print(f"Trying ASR with model: {model}...")
                try:
                    with open(latest_file, "rb") as f:
                        response = client.audio.transcriptions.create(
                            model=model,
                            file=f
                        )
                    print(f"SUCCESS with {model}: {response.text}")
                    return
                except Exception as e:
                    print(f"FAILED with {model}: {e}")
    else:
        print(f"\nNo temp_voice directory found at {voice_dir}")
        print("Please try to record once in the UI first to generate a test file.")

if __name__ == "__main__":
    diagnostic()
