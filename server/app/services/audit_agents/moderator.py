"""
仲裁主席智能体
职责：协调讨论流程，综合各方意见
"""
from typing import Dict, Any, List
from .base_agent import BaseAuditAgent


class Moderator(BaseAuditAgent):
    """仲裁主席"""
    
    def __init__(self):
        super().__init__(
            agent_id="moderator",
            agent_name="仲裁主席",
            emoji="⚖️"
        )
    
    async def audit(
        self, 
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """综合各智能体意见，生成最终报告"""
        
        if not context or "agent_results" not in context:
            return self.create_message(
                phase="consensus",
                content="缺少其他智能体的审核结果，无法生成综合报告",
                evidence=[],
                score=0,
                issues=["数据不完整"],
                confidence=0.0
            )
        
        agent_results = context["agent_results"]
        
        # 1. 收集各智能体的评分和问题
        scores = {}
        all_issues = []
        all_evidence = []
        
        for agent_id, result in agent_results.items():
            scores[agent_id] = result.get("score", 0)
            all_issues.extend(result.get("issues", []))
            all_evidence.extend(result.get("evidence", []))
        
        # 2. 计算加权总分
        # 需求覆盖30%、知识准确30%、用户体验25%、语言表达15%
        weights = {
            "requirement_analyst": 0.30,
            "knowledge_validator": 0.30,
            "experience_designer": 0.25,
            "language_polisher": 0.15
        }
        
        overall_score = 0
        for agent_id, score in scores.items():
            weight = weights.get(agent_id, 0.25)
            overall_score += score * weight
        
        overall_score = int(overall_score)
        
        # 3. 分析争议点（评分差异较大的项）
        score_values = list(scores.values())
        max_score = max(score_values) if score_values else 0
        min_score = min(score_values) if score_values else 0
        score_variance = max_score - min_score
        
        # 4. 生成综合评价
        if overall_score >= 85:
            grade = "优秀"
            recommendation = "脚本质量优秀，可以直接使用。"
        elif overall_score >= 70:
            grade = "良好"
            recommendation = "脚本质量良好，建议根据专家意见优化后使用。"
        elif overall_score >= 60:
            grade = "及格"
            recommendation = "脚本存在一些问题，建议按照专家意见进行修改。"
        else:
            grade = "不及格"
            recommendation = "脚本质量不达标，建议重新生成。"
        
        # 5. 构建最终报告内容
        content = f"""
【审核会议总结】

综合评分：{overall_score}/100 ({grade})

各专家评分：
- 📋 需求分析师：{scores.get('requirement_analyst', 0)}/100
- 🔍 知识审查官：{scores.get('knowledge_validator', 0)}/100
- 🎨 体验设计师：{scores.get('experience_designer', 0)}/100
- ✍️ 语言润色师：{scores.get('language_polisher', 0)}/100

评分差异：{score_variance}分 {'（各专家意见较为一致）' if score_variance < 20 else '（存在分歧，建议重点关注）'}

主要问题（共{len(all_issues)}项）：
{chr(10).join([f'- {issue}' for issue in all_issues[:5]])}
{'...' if len(all_issues) > 5 else ''}

最终建议：{recommendation}
        """.strip()
        
        # 6. 对问题按严重程度分类
        consensus_issues = []
        for issue in all_issues:
            severity = "high"
            if "缺失需求" in issue or "不一致" in issue:
                severity = "high"
            elif "偏差" in issue or "需改进" in issue:
                severity = "medium"
            else:
                severity = "low"
            
            consensus_issues.append({
                "severity": severity,
                "description": issue,
                "accepted": True
            })
        
        return self.create_message(
            phase="consensus",
            content=content,
            evidence=all_evidence[:10],  # 限制证据数量
            score=overall_score,
            issues=all_issues,
            confidence=0.95
        )
    
    def create_discussion_prompt(self, agent_results: Dict[str, Any]) -> str:
        """生成讨论阶段的引导语（用于智能体间辩论）"""
        
        # 找出分歧最大的两个智能体
        scores = {aid: r.get("score", 0) for aid, r in agent_results.items()}
        sorted_agents = sorted(scores.items(), key=lambda x: x[1])
        
        if len(sorted_agents) >= 2:
            lowest = sorted_agents[0]
            highest = sorted_agents[-1]
            
            if highest[1] - lowest[1] > 20:
                return f"""各位专家，我注意到评分存在较大分歧：
{agent_results[highest[0]]['agent_name']}给出了{highest[1]}分（较高）
{agent_results[lowest[0]]['agent_name']}给出了{lowest[1]}分（较低）

请两位专家就分歧点展开讨论，其他专家也可以补充意见。"""
        
        return "各位专家的评估基本一致，现在进入最终总结阶段。"
