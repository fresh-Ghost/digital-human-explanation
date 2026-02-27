"""
审核智能体 API 路由
提供脚本审核、报告查询、一键修复功能和多智能体审核
"""
import uuid
import asyncio
import json
import os
import re
from copy import deepcopy
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from app.models.schemas import (
    AuditReport, AuditRequest, AuditFixRequest, PresentationScript,
    MultiAgentAuditRequest, MultiAgentAuditSession,
    ModificationSuggestionResponse, ApplyModificationRequest, ApplyModificationResponse
)
from app.services.audit_service import audit_service
from app.services.multi_agent_audit_service import multi_agent_audit_service
from app.services.ai_service import zhipu_client

router = APIRouter()

# 内存存储脚本（实际应用中应使用数据库）
scripts_storage = {}

@router.post("/script/{script_id}", response_model=AuditReport)
async def audit_script(script_id: str, request: AuditRequest):
    """
    触发脚本审核
    
    Args:
        script_id: 脚本 ID
        request: 审核请求（包含对话历史和知识库 ID）
    
    Returns:
        AuditReport: 审核报告
    """
    # 获取脚本数据
    script = scripts_storage.get(script_id)
    print(f"\n========== 审核开始 =========", flush=True)
    print(f"脚本ID: {script_id}", flush=True)
    print(f"脚本对象类型: {type(script)}", flush=True)
    print(f"脚本keys: {script.keys() if script else 'None'}", flush=True)
    print(f"对话历史长度: {len(request.conversation_history)}", flush=True)
    print(f"知识库ID: {request.knowledge_base_id}", flush=True)
    
    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")
    
    # 执行审核
    try:
        audit_report = await audit_service.audit_script(
            script_id=script_id,
            script=script,
            conversation_history=request.conversation_history,
            kb_id=request.knowledge_base_id
        )
        return audit_report
    except Exception as e:
        print(f"审核失败: {e}")
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


@router.get("/report/{script_id}", response_model=AuditReport)
async def get_audit_report(script_id: str):
    """
    获取审核报告
    
    Args:
        script_id: 脚本 ID
    
    Returns:
        AuditReport: 审核报告
    """
    audit_report = audit_service.get_audit_report(script_id)
    if not audit_report:
        raise HTTPException(status_code=404, detail=f"Audit report for script {script_id} not found")
    
    return audit_report


@router.post("/fix/{script_id}", response_model=PresentationScript)
async def fix_script(script_id: str, request: AuditFixRequest):
    """
    一键修复脚本问题
    
    Args:
        script_id: 脚本 ID
        request: 修复请求（包含审核报告）
    
    Returns:
        PresentationScript: 修复后的脚本
    """
    # 获取原始脚本
    original_script = scripts_storage.get(script_id)
    if not original_script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")
    
    # 构建修复提示
    issues_text = "\n".join([f"- {issue}" for issue in request.audit_report.issues])
    suggestions_text = "\n".join([f"- {sug}" for sug in request.audit_report.suggestions])
    
    fix_prompt = f"""以下是审核发现的问题和建议：

问题列表：
{issues_text}

改进建议：
{suggestions_text}

请根据这些反馈重新生成一个更好的脚本。保持原有的受众、时长等基本配置。
"""
    
    # 调用脚本生成逻辑，注入修复提示
    try:
        # 这里简化实现，实际应该调用完整的脚本生成流程
        # 并将 fix_prompt 注入到生成 Prompt 中
        
        # 暂时返回原脚本（实际应重新生成）
        print(f"修复提示: {fix_prompt}")
        
        raise HTTPException(
            status_code=501, 
            detail="一键修复功能正在开发中，请根据审核报告手动调整脚本"
        )
    
    except Exception as e:
        print(f"修复失败: {e}")
        raise HTTPException(status_code=500, detail=f"Fix failed: {str(e)}")


def store_script(script_id: str, script: dict):
    """存储脚本到内存（供审核使用）"""
    scripts_storage[script_id] = script


def get_stored_script(script_id: str) -> dict:
    """获取存储的脚本"""
    return scripts_storage.get(script_id)


# ================== 多智能体审核 API ==================

@router.post("/multi-agent/{script_id}", response_model=dict)
async def start_multi_agent_audit(script_id: str, request: MultiAgentAuditRequest):
    """
    启动多智能体审核
    
    Args:
        script_id: 脚本 ID
        request: 审核请求（包含对话历史和知识库 ID）
    
    Returns:
        会话信息（包含session_id）
    """
    # 获取脚本数据
    script = scripts_storage.get(script_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")
    
    try:
        # 【关键修改】只创建会话，不启动审核！WebSocket连接后才真正开始
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "script_id": script_id,
            "conversation_history": request.conversation_history,
            "kb_id": request.knowledge_base_id,
            "status": "pending",  # 初始状态为pending，等待WebSocket连接
            "start_time": None,
            "end_time": None,
            "messages": [],
            "agent_results": {},
            "final_report": None
        }
        multi_agent_audit_service.audit_sessions[session_id] = session_data
        print(f"[会话创建] session_id={session_id}, status=pending, 等待WebSocket连接")
        
        return {
            "session_id": session_id,
            "status": "pending",
            "message": "会话已创建，请连接WebSocket开始审核"
        }
    except Exception as e:
        print(f"启动多智能体审核失败: {e}")
        raise HTTPException(status_code=500, detail=f"Audit start failed: {str(e)}")


@router.get("/multi-agent/session/{session_id}", response_model=MultiAgentAuditSession)
async def get_audit_session(session_id: str):
    """
    获取审核会话信息
    
    Args:
        session_id: 会话 ID
    
    Returns:
        审核会话数据
    """
    session = multi_agent_audit_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    return MultiAgentAuditSession(**session)


@router.get("/multi-agent/report/{session_id}", response_model=dict)
async def get_multi_agent_report(session_id: str):
    """
    获取最终审核报告
    """
    report = multi_agent_audit_service.get_final_report(session_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report for session {session_id} not found")
    
    return report


@router.get("/multi-agent/{session_id}/suggestions", response_model=ModificationSuggestionResponse)
async def get_modification_suggestions_api(session_id: str):
    """获取审核会话的修改建议列表"""
    session = multi_agent_audit_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    suggestions = multi_agent_audit_service.get_modification_suggestions(session_id) or []
    return ModificationSuggestionResponse(
        session_id=session_id,
        script_id=session.get("script_id"),
        suggestions=suggestions
    )


@router.post("/multi-agent/{session_id}/apply-modifications", response_model=ApplyModificationResponse)
async def apply_modifications_api(session_id: str, request: ApplyModificationRequest):
    """
    应用审核建议，基于增强版需求重新调用生成接口
    
    方案 A：复用原始脚本生成逻辑（RAG + Prompt 模板），确保修改后脚本与初次生成的质量标准一致
    """
    # 1. 验证会话状态
    session = multi_agent_audit_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if session.get("status") != "completed":
        raise HTTPException(status_code=400, detail="审核尚未完成，无法应用修改")
    
    script_id = session.get("script_id")
    script = scripts_storage.get(script_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")
    
    # 2. 获取审核建议
    suggestions = multi_agent_audit_service.get_modification_suggestions(session_id) or []
    if not suggestions and not request.regenerate_all:
        raise HTTPException(status_code=400, detail="当前会话没有可用的修改建议")
    
    selected_ids = request.selected_suggestions or [s["suggestion_id"] for s in suggestions]
    selected_map = {s["suggestion_id"]: s for s in suggestions}
    selected = [selected_map[sid] for sid in selected_ids if sid in selected_map]
    
    if not selected and not request.regenerate_all:
        raise HTTPException(status_code=400, detail="未选择任何需要应用的修改建议")
    
    print(f"\n[apply_modifications] 开始应用修改，会话ID: {session_id}", flush=True)
    print(f"[apply_modifications] 脚本ID: {script_id}", flush=True)
    print(f"[apply_modifications] 选中建议数: {len(selected)}", flush=True)
    
    # 3. 构造增强版需求（原对话历史 + 审核意见）
    conversation_history = session.get("conversation_history", [])
    original_requirement = "\n".join([
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in conversation_history
    ])
    
    suggestion_text = "\n".join([
        f"{idx+1}. [{s.get('agent_name', '')}] {s.get('description', '')} \u2192 建议：{s.get('suggested_action', '')}"
        for idx, s in enumerate(selected)
    ])
    
    enhanced_requirement = f"""【原始需求】
{original_requirement}

【审核发现的问题及改进方向】
{suggestion_text if suggestion_text else '（无明确问题，请从整体叙事、事实准确性和需求覆盖度三个方面提升质量）'}

请基于以上问题重新生成脚本，确保满足所有审核要求。"""
    
    print(f"[apply_modifications] 增强版需求示例:\n{enhanced_requirement[:200]}...", flush=True)
    
    # 4. 调用原始生成接口（复用 RAG + Prompt 逻辑）
    from app.api.v1.script import generate_script
    from app.models.schemas import ScriptGenerateRequest
    
    original_meta = script.get("meta", {})
    kb_id = session.get("kb_id") or script.get("_kb_id") or "default"
    
    print(f"[apply_modifications] 准备调用 generate_script", flush=True)
    print(f"[apply_modifications] 受众: {original_meta.get('target_audience', 'unknown')}", flush=True)
    print(f"[apply_modifications] 时长: {original_meta.get('estimated_duration', 5)}分钟", flush=True)
    print(f"[apply_modifications] 知识库: {kb_id}", flush=True)
    
    try:
        new_script_response = await generate_script(ScriptGenerateRequest(
            audience=original_meta.get("target_audience", "通用观众"),
            duration_minutes=original_meta.get("estimated_duration", 5),
            requirement=enhanced_requirement,
            voice_id=original_meta.get("voice_id", "zh-CN-YunxiNeural"),
            knowledge_base_id=kb_id
        ))
        print(f"[apply_modifications] 脚本重新生成成功，节点数: {len(new_script_response.timeline)}", flush=True)
    except Exception as e:
        print(f"[apply_modifications] 调用 generate_script 失败: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"重新生成脚本失败：{str(e)}")
    
    # 5. 计算变更差异
    base_timeline = script.get("timeline", [])
    new_timeline = [node.dict() for node in new_script_response.timeline]
    reason_summary = "; ".join([s.get("description", "") for s in selected]) if selected else "整体优化脚本结构与事实准确性"
    changes = _compute_script_changes(base_timeline, new_timeline, reason_summary)
    
    print(f"[apply_modifications] 变更节点数: {len(changes)}", flush=True)
    
    # 6. 版本化保存
    previous_version = script.get("_version", 1)
    history_entry = {
        "version": previous_version,
        "timeline": deepcopy(base_timeline),
        "saved_at": datetime.now().isoformat(),
        "source_session": session_id,
        "applied_suggestions": selected_ids,
        "method": "regenerate_with_enhanced_requirement"  # 标记修改方法
    }
    script.setdefault("_history", []).append(history_entry)
    script["timeline"] = new_timeline
    script["_version"] = previous_version + 1
    script["_last_modified_session"] = session_id
    script["_last_modified_time"] = datetime.now().isoformat()
    script["_applied_suggestions"] = selected_ids
    script["_kb_id"] = kb_id  # 保持知识库 ID 一致
    
    # 7. 构造返回结果
    presentation_script = PresentationScript(**{
        "id": script["id"],
        "meta": script["meta"],
        "timeline": script["timeline"]
    })
    summary = f"参考{len(selected)}条审核建议，基于知识库重新生成脚本，共调整{len(changes)}处内容。"
    
    print(f"[apply_modifications] 应用修改完成，新版本: v{script['_version']}", flush=True)
    
    return ApplyModificationResponse(
        script_id=script_id,
        version=script["_version"],
        summary=summary,
        changes=changes,
        new_script=presentation_script
    )


@router.websocket("/ws/multi-agent/{session_id}")
async def websocket_multi_agent_audit(websocket: WebSocket, session_id: str):
    """
    WebSocket端点：实时推送多智能体审核进度
    
    使用方法：
    1. 先调用 POST /multi-agent/{script_id} 启动审核，获取session_id
    2. 连接 ws://host/api/v1/audit/ws/multi-agent/{session_id}
    3. 接收实时消息
    """
    await websocket.accept()
    
    try:
        # 检查会话是否存在
        session = multi_agent_audit_service.get_session(session_id)
        if not session:
            await websocket.send_json({
                "type": "error",
                "content": f"Session {session_id} not found"
            })
            await websocket.close()
            return
        
        # 定义消息回调函数
        async def message_callback(message: dict):
            try:
                await websocket.send_json(message)
                # 【关键】立即yield，确保消息真正发送出去
                await asyncio.sleep(0)  # 让出控制权，刷新WebSocket缓冲区
                print(f"[WebSocket] 发送消息: {message.get('type')}")
            except Exception as e:
                print(f"WebSocket发送消息失败: {e}")
        
        # 【关键修改】如果会话还没开始，在后台启动（不阻塞WebSocket）
        if session.get("status") == "pending":
            script = scripts_storage.get(session.get("script_id"))
            if script:
                # 使用create_task让审核在后台运行，不阻塞WebSocket
                asyncio.create_task(
                    multi_agent_audit_service.start_audit(
                        script_id=session.get("script_id"),
                        script=script,
                        conversation_history=session.get("conversation_history", []),
                        kb_id=session.get("kb_id", "default"),
                        message_callback=message_callback,
                        session_id=session_id
                    )
                )
                print(f"[WebSocket] 审核任务已在后台启动")
        else:
            # 会话已完成，发送历史消息
            for msg in session.get("messages", []):
                await websocket.send_json(msg)
        
        # 保持连接直到审核完成
        while True:
            # 检查会话状态
            current_session = multi_agent_audit_service.get_session(session_id)
            if current_session and current_session.get("status") in ["completed", "error"]:
                await websocket.send_json({
                    "type": "complete",
                    "status": current_session.get("status")
                })
                break
            
            # 【关键修改】使用asyncio.sleep而不是receive_text，避免阻塞
            await asyncio.sleep(1)  # 每1秒检查一次状态
    
    except WebSocketDisconnect:
        print(f"WebSocket连接断开: {session_id}")
    except Exception as e:
        print(f"WebSocket错误: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


def _format_script_for_prompt(script: Dict[str, Any]) -> str:
    lines = []
    timeline = script.get("timeline", [])
    for node in timeline:
        seq = node.get("seq_id") or len(lines) + 1
        voice_text = node.get("voice_text", "").strip()
        lines.append(f"节点{seq}|讲解词: {voice_text}")
    return "\n".join(lines[:40])


def _format_conversation_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return ""
    lines = []
    for item in history[-12:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _format_suggestions_for_prompt(suggestions: List[Dict[str, Any]]) -> str:
    if not suggestions:
        return ""
    lines = []
    for idx, sug in enumerate(suggestions, 1):
        lines.append(
            f"{idx}. [{sug.get('agent_name','')}] {sug.get('description','')} → 建议：{sug.get('suggested_action','')}"
        )
    return "\n".join(lines)


def _parse_nodes_from_output(output: str) -> List[Dict[str, str]]:
    pattern = r"节点\s*(\d+)\s*\|\s*标题[:：]\s*(.+?)\s*\|\s*讲解词[:：]\s*(.+?)(?=\s*节点\s*\d+\s*\||$)"
    matches = re.findall(pattern, output, re.S)
    nodes = []
    if matches:
        for _, title, content in matches:
            nodes.append({
                "title": title.strip(),
                "voice_text": content.strip()
            })
    else:
        # fallback: split by blank lines
        parts = [seg.strip() for seg in output.split("节点") if seg.strip()]
        for idx, part in enumerate(parts, 1):
            nodes.append({
                "title": f"节点{idx}",
                "voice_text": part
            })
    return nodes


def _build_new_timeline(parsed_nodes: List[Dict[str, str]], base_timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    new_timeline: List[Dict[str, Any]] = []
    if not base_timeline:
        return new_timeline
    max_len = max(len(parsed_nodes), len(base_timeline))
    for idx in range(max_len):
        template_index = idx if idx < len(base_timeline) else -1
        template = deepcopy(base_timeline[template_index])
        template["seq_id"] = idx + 1
        if idx < len(parsed_nodes):
            template["voice_text"] = parsed_nodes[idx].get("voice_text", template.get("voice_text", ""))
        template["duration_ms"] = max(1500, len(template.get("voice_text", "")) * 80)
        new_timeline.append(template)
    return new_timeline


def _compute_script_changes(
    old_timeline: List[Dict[str, Any]],
    new_timeline: List[Dict[str, Any]],
    reason: str
) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    max_len = max(len(old_timeline), len(new_timeline))
    for idx in range(max_len):
        old_text = old_timeline[idx]["voice_text"] if idx < len(old_timeline) else None
        new_text = new_timeline[idx]["voice_text"] if idx < len(new_timeline) else None
        if old_text == new_text:
            continue
        if old_text is None:
            change_type = "added"
        elif new_text is None:
            change_type = "deleted"
        else:
            change_type = "modified"
        changes.append({
            "node_id": idx + 1,
            "change_type": change_type,
            "old_text": old_text,
            "new_text": new_text,
            "reason": reason
        })
    return changes
