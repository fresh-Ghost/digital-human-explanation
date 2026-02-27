"""
智能体基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime


class BaseAuditAgent(ABC):
    """审核智能体基类"""
    
    def __init__(self, agent_id: str, agent_name: str, emoji: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.emoji = emoji
        
    @abstractmethod
    async def audit(
        self, 
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行审核
        
        Args:
            script: 脚本数据
            conversation_history: 对话历史
            kb_id: 知识库ID
            context: 其他智能体的审核结果（用于讨论阶段）
            
        Returns:
            审核结果字典，包含：
            - agent_id: 智能体ID
            - agent_name: 智能体名称
            - timestamp: 时间戳
            - phase: 阶段（independent/discussion/consensus）
            - content: 发言内容
            - evidence: 证据列表
            - score: 评分（0-100）
            - issues: 问题列表
            - confidence: 置信度（0-1）
        """
        pass
    
    def create_message(
        self,
        phase: str,
        content: str,
        evidence: List[str],
        score: int,
        issues: List[str],
        confidence: float = 0.8,
        details: Dict[str, Any] = None  # 新增：详细信息字典
    ) -> Dict[str, Any]:
        """创建标准的智能体消息"""
        message = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "emoji": self.emoji,
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "content": content,
            "evidence": evidence,
            "score": score,
            "issues": issues,
            "confidence": confidence
        }
        
        # 如果提供了详细信息，添加到消息中
        if details:
            message["details"] = details
        
        return message
