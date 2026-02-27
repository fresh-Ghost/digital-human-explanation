"""
运行时播放器 WebSocket 接口
实现智能打断、RAG 问答和状态控制
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import json
import asyncio
from app.services.voice_service import voice_service
from app.services.rag_service import rag_service
from app.services.ai_service import zhipu_client

router = APIRouter()

# 存储活跃的 WebSocket 连接
active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/runtime/{session_id}")
async def websocket_runtime_endpoint(websocket: WebSocket, session_id: str):
    """
    运行时 WebSocket 端点
    处理智能打断、语音问答和播放控制
    
    通信协议：
    Client -> Server:
        - {"type": "vad_event", "status": "start"}  # 开始说话
        - {"type": "vad_event", "status": "end", "audio_data": "base64..."}  # 说话结束，附带音频
        - {"type": "control", "command": "pause"}  # 暂停播放
        - {"type": "control", "command": "resume"}  # 恢复播放
    
    Server -> Client:
        - {"type": "control", "command": "pause"}  # 指令暂停
        - {"type": "control", "command": "resume", "seek_time": 12000}  # 指令恢复
        - {"type": "status", "state": "listening"}  # 状态更新
        - {"type": "subtitle", "text": "正在查询..."}  # 字幕
        - {"type": "answer", "text": "...", "audio_url": "..."}  # 回答
    """
    await websocket.accept()
    active_connections[session_id] = websocket
    
    print(f"[WebSocket] 会话 {session_id} 已连接")
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            
            if msg_type == "vad_event":
                await handle_vad_event(websocket, session_id, message)
            
            elif msg_type == "control":
                await handle_control_event(websocket, session_id, message)
            
            elif msg_type == "ping":
                # 心跳响应
                await websocket.send_text(json.dumps({"type": "pong"}))
    
    except WebSocketDisconnect:
        print(f"[WebSocket] 会话 {session_id} 已断开")
        if session_id in active_connections:
            del active_connections[session_id]
    
    except Exception as e:
        print(f"[WebSocket] 会话 {session_id} 发生错误: {e}")
        if session_id in active_connections:
            del active_connections[session_id]


async def handle_vad_event(websocket: WebSocket, session_id: str, message: dict):
    """
    处理 VAD 事件（语音活动检测）
    """
    status = message.get("status")
    
    if status == "start":
        # 用户开始说话 -> 暂停播放
        print(f"[VAD] 会话 {session_id}: 检测到说话开始，暂停播放")
        await websocket.send_text(json.dumps({
            "type": "control",
            "command": "pause"
        }))
        await websocket.send_text(json.dumps({
            "type": "status",
            "state": "listening"
        }))
    
    elif status == "end":
        # 用户停止说话 -> 处理语音问答
        print(f"[VAD] 会话 {session_id}: 检测到说话结束，开始处理问答")
        
        # 获取音频数据
        audio_data = message.get("audio_data")  # base64 编码的音频
        kb_id = message.get("kb_id", "default")
        
        if not audio_data:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "未接收到音频数据"
            }))
            return
        
        # 更新状态为"思考中"
        await websocket.send_text(json.dumps({
            "type": "status",
            "state": "thinking"
        }))
        await websocket.send_text(json.dumps({
            "type": "subtitle",
            "text": "正在识别您的问题..."
        }))
        
        # 1. ASR 识别音频
        try:
            import base64
            audio_bytes = base64.b64decode(audio_data)
            
            # 调用 ASR 服务
            user_question = await voice_service.asr_audio_bytes(audio_bytes)
            
            print(f"[ASR] 识别结果: {user_question}")
            
            await websocket.send_text(json.dumps({
                "type": "subtitle",
                "text": f"您问：{user_question}"
            }))
            
        except Exception as e:
            print(f"[ASR] 识别失败: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"语音识别失败: {str(e)}"
            }))
            await websocket.send_text(json.dumps({
                "type": "control",
                "command": "resume"
            }))
            return
        
        # 2. RAG 检索知识库并生成回答
        try:
            await websocket.send_text(json.dumps({
                "type": "subtitle",
                "text": "正在查询知识库..."
            }))
            
            # 使用 RAG 服务检索相关内容
            answer_text = await generate_rag_answer(user_question, kb_id)
            
            print(f"[RAG] 生成回答: {answer_text[:100]}...")
            
            # 3. TTS 生成语音回答
            await websocket.send_text(json.dumps({
                "type": "status",
                "state": "answering"
            }))
            
            audio_url = await voice_service.generate_tts(answer_text)
            
            # 发送回答
            await websocket.send_text(json.dumps({
                "type": "answer",
                "text": answer_text,
                "audio_url": audio_url
            }))
            
            # 4. 询问是否继续讲解
            await asyncio.sleep(0.5)  # 短暂延迟
            await websocket.send_text(json.dumps({
                "type": "subtitle",
                "text": "回答完毕，点击继续按钮恢复讲解"
            }))
            
        except Exception as e:
            print(f"[RAG] 问答失败: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"问答生成失败: {str(e)}"
            }))
            await websocket.send_text(json.dumps({
                "type": "control",
                "command": "resume"
            }))


async def handle_control_event(websocket: WebSocket, session_id: str, message: dict):
    """
    处理控制事件
    """
    command = message.get("command")
    
    if command == "pause":
        print(f"[Control] 会话 {session_id}: 暂停播放")
        # 客户端请求暂停，可以记录状态
    
    elif command == "resume":
        print(f"[Control] 会话 {session_id}: 恢复播放")
        # 客户端请求恢复
        await websocket.send_text(json.dumps({
            "type": "status",
            "state": "narrating"
        }))


async def generate_rag_answer(question: str, kb_id: str) -> str:
    """
    使用 RAG 生成回答
    """
    # 检索知识库
    relevant_docs = rag_service.retrieve(question, kb_id=kb_id, k=5)
    
    # 构建上下文
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    # 生成回答
    prompt = f"""你是专业的讲解员。根据以下知识库内容回答用户的问题。

知识库内容：
{context}

用户问题：{question}

请用简洁、准确的语言回答（控制在100字以内）。如果知识库中没有相关内容，请诚实说明。"""
    
    try:
        response = zhipu_client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        print(f"[GLM] 生成回答失败: {e}")
        return "抱歉，我暂时无法回答这个问题。"
