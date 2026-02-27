import uuid
import re
from fastapi import APIRouter
from langchain_community.vectorstores import Chroma
from app.models.schemas import ScriptGenerateRequest, PresentationScript, ScriptMeta, ScriptNode
from app.services.ai_service import zhipu_client, embeddings
from app.services.knowledge_service import knowledge_service
from app.api.v1.audit import store_script  # 导入审核模块

router = APIRouter()

@router.post("/generate", response_model=PresentationScript)
async def generate_script(req: ScriptGenerateRequest):
    """使用 LLM + RAG 生成讲解脚本。"""
    audience = req.audience
    duration_minutes = req.duration_minutes
    requirement = req.requirement or ""
    voice_id = req.voice_id or "zh-CN-YunxiNeural"
    kb_id = req.knowledge_base_id or "default"
    script_id = str(uuid.uuid4())
    
    print(f"\n========== 脚本生成开始 ==========", flush=True)
    print(f"脚本ID: {script_id}", flush=True)
    print(f"受众: {audience}", flush=True)
    print(f"时长: {duration_minutes}分钟", flush=True)
    print(f"知识库ID: {kb_id}", flush=True)
    print(f"当前激活知识库: {knowledge_service.current_kb_id}", flush=True)
    
    # 1. 提取核心需求（过滤对话噪音）
    refined_requirement = requirement
    try:
        extract_prompt = f"""请从以下策展对话历史中提取出用户最终确定的【讲解主题】和【核心需求】。
        对话历史：
        {requirement}
        
        只需返回提取后的核心需求文字，不要有任何多余的解释。
        例如：全面介绍大疆无人机的智能飞行功能，包括智能跟随、指点飞行、航线规划等。
        """
        extract_res = zhipu_client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": extract_prompt}],
            temperature=0.3,
        )
        refined_requirement = extract_res.choices[0].message.content.strip()
        print(f"提取后的核心需求: {refined_requirement}")
    except Exception as e:
        print(f"需求提取失败，使用原始历史: {e}")

    # 2. RAG 检索
    active_vectorstore = knowledge_service.vectorstore
    temp_vectorstore = None
    
    print(f"\n[RAG检索] 请求的kb_id: {kb_id}", flush=True)
    print(f"[RAG检索] 当前激活: {knowledge_service.current_kb_id}", flush=True)
    
    if kb_id != knowledge_service.current_kb_id:
        print(f"[RAG检索] 需要临时加载知识库: {kb_id}", flush=True)
        temp_vectorstore = knowledge_service.load_vectorstore(kb_id)
        if temp_vectorstore:
            active_vectorstore = temp_vectorstore
            print(f"[RAG检索] 临时知识库加载成功", flush=True)
        else:
            print(f"[RAG检索] 临时知识库加载失败，使用默认知识库", flush=True)
    else:
        print(f"[RAG检索] 直接使用当前激活知识库", flush=True)
            
    context = ""
    doc_sources = []
    if active_vectorstore is not None:
        try:
            # 使用提取后的核心需求进行检索，提高准确度
            search_query = refined_requirement if refined_requirement else f"面向{audience}的讲解内容"
            print(f"[RAG检索] 检索查询: {search_query[:100]}", flush=True)
            docs = active_vectorstore.similarity_search(search_query, k=10)
            print(f"[RAG检索] 检索到 {len(docs)} 个文档", flush=True)
            if docs:
                print(f"[RAG检索] 第1个文档示例: {docs[0].page_content[:100]}", flush=True)
            context = "\n\n".join([doc.page_content for doc in docs])
            doc_sources = list(set([doc.metadata.get("source", "unknown") for doc in docs]))
        except Exception as e:
            print(f"[RAG检索] 失败: {e}", flush=True)
    
    # 使用完检索后，如果是临时加载的，立即关闭以释放文件锁
    if temp_vectorstore:
        knowledge_service.close_vectorstore(temp_vectorstore)
        temp_vectorstore = None
        import gc
        gc.collect()
            
    # 3. 生成脚本逻辑
    # 根据时长动态计算节点数，每分钟约对应 0.8-1.2 个节点
    num_nodes = max(3, min(15, int(duration_minutes * 1.2))) 
    
    prompt = f"""你是一个专业的讲解脚本生成器。
    
    【目标受众】：{audience}
    【总时长】：{duration_minutes} 分钟
    【核心主题】：{refined_requirement}
    【参考资料】：
    {context if context else "暂无资料，请基于常识生成"}
    
    【生成要求】：
    1. **主题聚焦**：必须严格围绕【核心主题】生成内容。严禁包含与主题无关的内容（如：如果主题是智能飞行，不要讲基础起降或安全规定，除非它们是智能功能的一部分）。
    2. **内容密度**：由于是 {duration_minutes} 分钟的深度讲解，请生成恰好 {num_nodes} 个讲解节点，确保内容详实。
    3. **逻辑结构**：按逻辑顺序排列（如：引言 -> 核心功能1 -> 核心功能2 -> ... -> 总结）。
    
    【输出格式】：
    请严格按以下格式输出，每个节点占一行：
    节点1|标题: [简短标题]|讲解词: [详细的讲解文案，风格应匹配受众]
    节点2|标题: [简短标题]|讲解词: [详细的讲解文案]
    ...
    """
    
    timeline = []
    try:
        response = zhipu_client.chat.completions.create(
            model="glm-4-plus",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        output = response.choices[0].message.content
        full_text = output.replace("\n", " ").strip()
        node_pattern = r'节点(\d+)\|标题[:：]\s*(.+?)\|?讲解词[:：]\s*(.+?)(?=\s*节点\d+|$)'
        matches = re.findall(node_pattern, full_text, re.DOTALL)
        
        for match in matches:
            node_num, title, content = match
            timeline.append(ScriptNode(
                seq_id=len(timeline) + 1,
                type="image",
                url=f"https://via.placeholder.com/800x450?text={title.strip()}",
                voice_text=content.strip(),
                voice_id=voice_id,
                duration_ms=len(content.strip()) * 300,
                rag_tags=[f"slide_{len(timeline) + 1}", audience]
            ))
    except Exception as e:
        print(f"生成脚本失败: {e}")
        # 回退逻辑...
    
    # 构建脚本对象
    script_obj = PresentationScript(
        id=script_id,
        meta=ScriptMeta(title=f"面向{audience}的脚本", target_audience=audience, estimated_duration=duration_minutes),
        timeline=timeline
    )
    
    # 存储脚本供审核使用（包含使用的知识库ID）
    try:
        script_with_kb = script_obj.dict()
        script_with_kb['_kb_id'] = kb_id  # 记录使用的知识库ID
        store_script(script_id, script_with_kb)
        print(f"脚本 {script_id} 已存储，使用知识库: {kb_id}")
    except Exception as e:
        print(f"存储脚本失败: {e}")
    
    return script_obj
