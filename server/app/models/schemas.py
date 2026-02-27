from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class ScriptMeta(BaseModel):
    title: str
    target_audience: str
    estimated_duration: int  # minutes

class Hotspot(BaseModel):
    time_offset: int
    x: float
    y: float
    width: float
    height: float
    style: str

class ScriptNode(BaseModel):
    seq_id: int
    type: str  # "image" | "video"
    url: str
    voice_text: str
    voice_id: Optional[str] = None
    duration_ms: int
    hotspots: Optional[List[Hotspot]] = None
    rag_tags: List[str] = []

class PresentationScript(BaseModel):
    id: str
    meta: ScriptMeta
    timeline: List[ScriptNode]

class ScriptGenerateRequest(BaseModel):
    audience: str
    duration_minutes: int
    requirement: Optional[str] = ""
    voice_id: Optional[str] = "zh-CN-YunxiNeural"
    knowledge_base_id: Optional[str] = "default"

class CuratorChatRequest(BaseModel):
    message: str
    audience: Optional[str] = None
    duration_minutes: Optional[int] = None
    focus: Optional[str] = None
    history: Optional[List[dict]] = []  # [{role: "user", content: "..."}, ...]
    knowledge_base_id: Optional[str] = "default"

class CuratorChatResponse(BaseModel):
    reply: str
    audio_url: Optional[str] = None

# 审核相关 Schema
class RequirementCoverage(BaseModel):
    matched: List[str]  # 已满足的需求
    missing: List[str]  # 缺失的需求

class KnowledgeConsistency(BaseModel):
    verified_facts: int  # 验证通过的事实数量
    verified_facts_list: List[str]  # 验证通过的事实列表（详细）
    inconsistent_facts: List[str]  # 与知识库不一致的陈述

class DurationCheck(BaseModel):
    expected_minutes: float
    actual_minutes: float
    deviation_percent: float

class AuditReport(BaseModel):
    script_id: str
    audit_time: str
    overall_score: int  # 0-100 分
    requirement_coverage: RequirementCoverage
    knowledge_consistency: KnowledgeConsistency
    duration_check: DurationCheck
    issues: List[str]  # 问题列表
    suggestions: List[str]  # 改进建议

class AuditRequest(BaseModel):
    script_id: str
    conversation_history: List[dict]  # 对话历史
    knowledge_base_id: str

class AuditFixRequest(BaseModel):
    script_id: str
    audit_report: AuditReport

class UploadResponse(BaseModel):
    file_id: str
    filename: str

class FileListResponse(BaseModel):
    files: List[dict]
    total_count: int

class KnowledgeBaseInfo(BaseModel):
    id: str
    name: str
    collection_name: str
    total_documents: Any  # 支持数字或"未加载"等字符串
    uploaded_files: List[dict]
    is_active: bool
    created_at: Optional[float] = None

class KnowledgeBaseListResponse(BaseModel):
    knowledge_bases: List[KnowledgeBaseInfo]


# 多智能体审核相关Schema
class AgentMessage(BaseModel):
    """智能体消息"""
    agent_id: str
    agent_name: str
    emoji: str
    timestamp: str
    phase: str  # independent | discussion | consensus
    content: str
    evidence: List[str]
    score: int
    issues: List[str]
    confidence: float

class ConsensusIssue(BaseModel):
    """共识问题"""
    severity: str  # high | medium | low
    description: str
    suggested_by: List[str]
    accepted: bool

class FinalReport(BaseModel):
    """最终审核报告"""
    overall_score: int
    agent_scores: Dict[str, int]
    consensus_issues: List[ConsensusIssue]
    suggestions: List[str]

class MultiAgentAuditSession(BaseModel):
    """多智能体审核会话"""
    session_id: str
    script_id: str
    start_time: str
    end_time: Optional[str] = None
    status: str  # running | completed | error
    messages: List[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]] = None
    modification_suggestions: Optional[List[Dict[str, Any]]] = None

class ModificationSuggestion(BaseModel):
    suggestion_id: str
    agent_id: str
    agent_name: str
    issue_type: str
    severity: str
    description: str
    suggested_action: str
    evidence: List[str] = []

class ModificationSuggestionResponse(BaseModel):
    session_id: str
    script_id: str
    suggestions: List[ModificationSuggestion]

class ApplyModificationRequest(BaseModel):
    selected_suggestions: Optional[List[str]] = None
    regenerate_all: Optional[bool] = False

class ScriptChange(BaseModel):
    node_id: int
    change_type: str  # added | modified | deleted | unchanged
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    reason: Optional[str] = None

class ApplyModificationResponse(BaseModel):
    script_id: str
    version: int
    summary: str
    changes: List[ScriptChange]
    new_script: PresentationScript

class MultiAgentAuditRequest(BaseModel):
    """启动多智能体审核请求"""
    conversation_history: List[Dict[str, str]]
    knowledge_base_id: str