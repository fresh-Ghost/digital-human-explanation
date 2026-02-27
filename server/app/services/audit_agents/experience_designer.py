"""
体验设计师智能体
职责：评估用户体验质量
"""
from typing import Dict, Any, List
from .base_agent import BaseAuditAgent
from app.services.ai_service import zhipu_client


class ExperienceDesigner(BaseAuditAgent):
    """体验设计师"""
    
    def __init__(self):
        super().__init__(
            agent_id="experience_designer",
            agent_name="体验设计师",
            emoji="🎨"
        )
    
    async def audit(
        self, 
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行用户体验审核"""
        
        # 1. 检查时长合理性
        expected_minutes = script.get("meta", {}).get("estimated_duration", 5)
        total_duration_ms = sum([
            node.get("duration_ms", 0) for node in script.get("timeline", [])
        ])
        actual_minutes = total_duration_ms / 60000
        duration_deviation = abs(actual_minutes - expected_minutes) / expected_minutes * 100
        
        # 2. 提取脚本内容用于流畅性和重点评估
        pages = [node["voice_text"] for node in script.get("timeline", [])]
        script_content = "\n\n---分页---\n\n".join(pages)
        
        # 3. 使用AI评估叙事流畅性和重点突出度
        ux_prompt = f"""作为用户体验设计师，评估以下讲解脚本的用户体验质量。

脚本内容（共{len(pages)}页）：
{script_content[:1500]}

评估维度：
1. 叙事流畅性：页面之间的逻辑连贯性（1-10分）
2. 重点突出程度：关键信息是否突出（1-10分）
3. 节奏控制：信息密度是否合理（1-10分）

请返回JSON格式：
{{
  "narrative_score": 8,
  "highlight_score": 7,
  "pace_score": 9,
  "summary": "简要评价（50字内）",
  "issues": ["问题1", "问题2"]
}}

只返回JSON。"""
        
        try:
            ux_res = zhipu_client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": ux_prompt}],
                temperature=0.3,
            )
            ux_json = ux_res.choices[0].message.content.strip()
            ux_json = ux_json.replace("```json", "").replace("```", "").strip()
            
            import json
            ux_data = json.loads(ux_json)
            
            narrative_score = ux_data.get("narrative_score", 7)
            highlight_score = ux_data.get("highlight_score", 7)
            pace_score = ux_data.get("pace_score", 7)
            summary = ux_data.get("summary", "")
            ux_issues = ux_data.get("issues", [])
            
            # 4. 综合评分
            # 时长占30%，叙事/重点/节奏各占23.33%
            duration_score = 100 if duration_deviation <= 10 else (80 if duration_deviation <= 20 else 60)
            ux_score = (narrative_score + highlight_score + pace_score) / 30 * 70
            
            score = int(duration_score * 0.3 + ux_score)
            
            # 5. 构建证据和问题列表
            evidence = [
                f"时长：预期{expected_minutes}分钟，实际{actual_minutes:.1f}分钟，偏差{duration_deviation:.1f}%",
                f"叙事流畅性：{narrative_score}/10",
                f"重点突出度：{highlight_score}/10",
                f"节奏控制：{pace_score}/10"
            ]
            
            issues = []
            if duration_deviation > 20:
                issues.append(f"时长偏差过大：{duration_deviation:.1f}%")
            elif duration_deviation > 10:
                issues.append(f"时长略有偏差：{duration_deviation:.1f}%")
            
            issues.extend(ux_issues)
            
            if score >= 85:
                content = f"用户体验优秀！{summary}"
            elif score >= 70:
                content = f"用户体验良好。{summary}"
            else:
                content = f"用户体验需改进。{summary}"
            
            return self.create_message(
                phase="independent",
                content=content,
                evidence=evidence,
                score=score,
                issues=issues,
                confidence=0.8
            )
        
        except Exception as e:
            print(f"[体验设计师] 审核失败: {e}")
            # 回退到简单评估
            duration_score = 100 if duration_deviation <= 10 else (80 if duration_deviation <= 20 else 60)
            evidence = [f"时长：预期{expected_minutes}分钟，实际{actual_minutes:.1f}分钟，偏差{duration_deviation:.1f}%"]
            issues = [] if duration_deviation <= 10 else [f"时长偏差：{duration_deviation:.1f}%"]
            
            return self.create_message(
                phase="independent",
                content=f"基础体验评估完成（详细评估失败：{str(e)}）",
                evidence=evidence,
                score=duration_score,
                issues=issues,
                confidence=0.5
            )
