from fastapi import APIRouter, UploadFile, File, Form
from app.models.schemas import CuratorChatRequest, CuratorChatResponse
from app.services.knowledge_service import knowledge_service
from langchain_community.vectorstores import Chroma
from app.services.ai_service import zhipu_client, embeddings
from app.services.voice_service import voice_service
import os
import uuid
import json

router = APIRouter()

@router.post("/chat", response_model=CuratorChatResponse)
async def curator_chat(req: CuratorChatRequest):
    """使用 LLM 生成策展回复（支持多轮追问 + RAG）。"""
    audience = req.audience or "通用观众"
    duration = req.duration_minutes or 5
    kb_id = req.knowledge_base_id or "default"
    
    # 1. RAG 检索：基于用户最新输入检索知识库
    context = ""
    if kb_id:
        active_vectorstore = knowledge_service.vectorstore
        temp_vectorstore = None
        
        # 如果不是当前激活的知识库，临时加载
        if kb_id != knowledge_service.current_kb_id:
            temp_vectorstore = knowledge_service.load_vectorstore(kb_id)
            if temp_vectorstore:
                active_vectorstore = temp_vectorstore
        
        if active_vectorstore is not None:
            try:
                # 检索 5 条相关内容辅助对话
                docs = active_vectorstore.similarity_search(req.message, k=5)
                context = "\n".join([f"- {doc.page_content}" for doc in docs])
            except Exception as e:
                print(f"Curator RAG 检索失败: {e}")
        
        # 立即释放临时加载的知识库锁
        if temp_vectorstore:
            knowledge_service.close_vectorstore(temp_vectorstore)
            temp_vectorstore = None
            import gc
            gc.collect()

    # 2. 构建对话历史
    chat_history = []
    if req.history:
        for msg in req.history:
            if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                chat_history.append({"role": msg["role"], "content": msg["content"]})
    
    system_prompt = (
        f"你是灵境公司的专业策展人。你的任务是通过对话收集用户的演示需求（受众、时长、重点）。\n"
        f"基本配置：受众为「{audience}」，讲解时长约 {duration} 分钟。\n\n"
        f"【核心：你的背景知识库 (KMS)】\n"
        f"你拥有来自知识库「{kb_id}」的权威资料。以下是与用户当前输入最相关的片段：\n"
        f"{context if context else '（当前问题在知识库中未找到直接对应内容，请引导用户提供更多信息或基于常识回答）'}\n\n"
        f"行为准则：\n"
        f"1. **主动引导对话**：如果是对话开始或用户回答了前一个问题，请立即提出下一个问题来收集信息。不要被动等待，要主动追问。\n"
        f"2. **必须收集的信息**：受众类型、讲解时长、重点内容、特殊要求。如果这些信息还不完整，必须继续提问。\n"
        f"3. **严格基于知识库**：你的回答必须体现出你已经“读过”上述背景资料。如果知识库提到了特定功能（如：APAS 5.0、避障系统等），请直接在对话中引用，以展现专业度。\n"
        f"4. **禁止虚假追问**：不要问知识库中已经明确给出答案的问题。例如，如果资料显示这是民用无人机，就不要问“是民用还是军用”。\n"
        f"5. **上下文感知的追问**：检查对话历史，严禁重复问题。如果你已经了解了某个方面，请转向下一个未知的方面。\n"
        f"6. **自然交流**：回复要自然，对用户的回答表示认可，然后引出下一个问题。\n"
        f"7. **策略总结**：掌握足够信息后，总结策展策略摘要，并明确提示对话已完成，可以生成脚本了。\n"
        f"8. **简洁专业**：回复请控制在 150 字以内。\n\n"
        f"重要：每次回复都应该以问题结束，主动引导用户继续提供信息，直到收集到所有必要信息。"
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": req.message})
    
    try:
        response = zhipu_client.chat.completions.create(
            model="glm-4-flash",
            messages=messages,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        print(f"LLM 调用失败: {e}")
        reply = f"收到。关于给「{audience}」的讲解，您还有哪些特别想强调的内容吗？"
    
    return CuratorChatResponse(reply=reply)

@router.post("/voice-chat", response_model=CuratorChatResponse)
async def curator_voice_chat(
    file: UploadFile = File(...),
    audience: str = Form(None),
    duration_minutes: int = Form(None),
    voice_id: str = Form("zh-CN-YunxiNeural"),
    history: str = Form(None),  # 接收 JSON 字符串
    knowledge_base_id: str = Form("default")
):
    """语音版策展对话：接收语音 -> ASR -> LLM -> TTS -> 返回文本和音频。"""
    # 1. 保存临时语音文件
    temp_dir = "temp_voice"
    os.makedirs(temp_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(temp_dir, f"{file_id}_{file.filename}")
    
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    file_size = os.path.getsize(temp_path)
    print(f"收到语音文件: {temp_path}, 大小: {file_size} bytes, MIME: {file.content_type}")
    
    if file_size < 100:
        return CuratorChatResponse(reply="语音文件太小，请按住麦克风更长时间后松开。")
    
    # 2. ASR 语音转文字
    user_text = await voice_service.transcribe_audio(temp_path)
    if not user_text:
        return CuratorChatResponse(reply="抱歉，我没听清，请再说一遍。")
    
    # 3. 解析历史记录
    parsed_history = []
    if history:
        try:
            parsed_history = json.loads(history)
        except Exception as e:
            print(f"解析对话历史失败: {e}")

    # 4. LLM 对话
    chat_req = CuratorChatRequest(
        message=user_text,
        audience=audience,
        duration_minutes=duration_minutes,
        history=parsed_history,
        knowledge_base_id=knowledge_base_id
    )
    chat_res = await curator_chat(chat_req)
    
    # 5. TTS 文字转语音
    # 清洗 Markdown 标点符号，避免 TTS 读出来
    clean_reply = chat_res.reply.replace("*", "").replace("#", "").replace("- ", "").replace(">", "").strip()
    audio_path = await voice_service.generate_audio(clean_reply, voice_id)
    audio_filename = os.path.basename(audio_path)
    
    # 6. 清理临时文件
    if os.path.exists(temp_path):
        os.remove(temp_path)
        
    return CuratorChatResponse(
        reply=f"[你听起来在说：{user_text}]\n{chat_res.reply}",
        audio_url=f"/api/v1/tts/cache/{audio_filename}"
    )
