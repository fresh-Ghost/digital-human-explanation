"""
语言润色师智能体
职责：审查语言表达质量
"""
from typing import Dict, Any, List
from .base_agent import BaseAuditAgent
from app.services.ai_service import zhipu_client


class LanguagePolisher(BaseAuditAgent):
    """语言润色师"""
    
    def __init__(self):
        super().__init__(
            agent_id="language_polisher",
            agent_name="语言润色师",
            emoji="✍️"
        )
    
    async def audit(
        self, 
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行语言质量审核"""
        
        # 1. 提取脚本内容
        pages = [node["voice_text"] for node in script.get("timeline", [])]
        script_content = "\n\n---分页---\n\n".join(pages)
        
        # 2. 使用AI评估语言质量
        language_prompt = f"""作为语言润色专家，评估以下讲解脚本的语言表达质量。

脚本内容（共{len(pages)}页）：
{script_content[:1500]}

评估维度：
1. 口语化程度：是否适合口述讲解（1-10分）
2. 专业术语使用：术语使用是否恰当（1-10分）
3. 逻辑连贯性：语句逻辑是否清晰（1-10分）

请返回JSON格式：
{{
  "colloquial_score": 8,
  "terminology_score": 7,
  "coherence_score": 9,
  "summary": "简要评价（50字内）",
  "suggestions": ["建议1", "建议2"]
}}

只返回JSON。"""
        
        try:
            lang_res = zhipu_client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": language_prompt}],
                temperature=0.3,
            )
            lang_json = lang_res.choices[0].message.content.strip()
            lang_json = lang_json.replace("```json", "").replace("```", "").strip()
            
            import json
            lang_data = json.loads(lang_json)
            
            colloquial_score = lang_data.get("colloquial_score", 7)
            terminology_score = lang_data.get("terminology_score", 7)
            coherence_score = lang_data.get("coherence_score", 7)
            summary = lang_data.get("summary", "")
            suggestions = lang_data.get("suggestions", [])
            
            # 3. 计算综合评分
            score = int((colloquial_score + terminology_score + coherence_score) / 30 * 100)
            
            # 4. 构建证据
            evidence = [
                f"口语化程度：{colloquial_score}/10",
                f"专业术语使用：{terminology_score}/10",
                f"逻辑连贯性：{coherence_score}/10"
            ]
            
            # 5. 构建问题列表
            issues = []
            if colloquial_score < 6:
                issues.append("口语化程度不足，建议使用更自然的表达")
            if terminology_score < 6:
                issues.append("专业术语使用不当，需要调整")
            if coherence_score < 6:
                issues.append("逻辑连贯性较差，需要重新组织")
            
            # 添加AI的具体建议
            for sug in suggestions:
                if sug and sug not in issues:
                    issues.append(sug)
            
            if score >= 85:
                content = f"语言表达优秀！{summary}"
            elif score >= 70:
                content = f"语言表达良好。{summary}"
            else:
                content = f"语言表达需改进。{summary}"
            
            return self.create_message(
                phase="independent",
                content=content,
                evidence=evidence,
                score=score,
                issues=issues,
                confidence=0.75
            )
        
        except Exception as e:
            print(f"[语言润色师] 审核失败: {e}")
            return self.create_message(
                phase="independent",
                content=f"审核失败：{str(e)}",
                evidence=[],
                score=70,  # 默认中等评分
                issues=["AI服务调用失败，无法完成详细评估"],
                confidence=0.3
            )
