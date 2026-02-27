"""
需求分析师智能体
职责：检查脚本是否覆盖用户需求
"""
import json
from typing import Dict, Any, List
from .base_agent import BaseAuditAgent
from app.services.ai_service import zhipu_client


class RequirementAnalyst(BaseAuditAgent):
    """需求分析师"""
    
    def __init__(self):
        super().__init__(
            agent_id="requirement_analyst",
            agent_name="需求分析师",
            emoji="📋"
        )
    
    async def audit(
        self, 
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行需求覆盖度审核"""
        
        # 1. 从对话历史中提取用户需求
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation_history
        ])
        
        # 2. 提取脚本内容
        script_content = " ".join([
            node["voice_text"] for node in script.get("timeline", [])
        ])
        
        # 2.5 检查是否有前面的讨论（多智能体模式）
        previous_discussions = context.get("previous_discussions", []) if context else []
        discussion_context = ""
        
        if previous_discussions:
            discussion_context = "\n\n【前面专家的讨论】\n"
            for disc in previous_discussions:
                discussion_context += f"{disc['emoji']} {disc['agent_name']}: 评分{disc['score']}/100\n"
                if disc['issues']:
                    discussion_context += f"  问题: {', '.join(disc['issues'][:2])}\n"
            discussion_context += "\n作为需求分析师，请给出你的专业意见。如果你同意或不同意前面的观点，请说明理由。"
        
        # 3. 使用AI提取需求清单
        extract_prompt = f"""从以下对话中提取用户明确提出的所有讲解要求和重点主题。

对话历史：
{history_text}
{discussion_context}

请返回JSON格式：
{{
  "focus_topics": ["重点主题1", "重点主题2"],
  "special_requirements": ["特殊要求1"],
  "target_audience": "受众类型"
}}

只返回JSON，不要其他内容。"""
        
        try:
            extract_res = zhipu_client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": extract_prompt}],
                temperature=0.1,
            )
            requirements_json = extract_res.choices[0].message.content.strip()
            requirements_json = requirements_json.replace("```json", "").replace("```", "").strip()
            requirements = json.loads(requirements_json)
            
            focus_topics = requirements.get("focus_topics", [])
            special_requirements = requirements.get("special_requirements", [])
            all_requirements = focus_topics + special_requirements
            
            # 4. 逐项检查需求覆盖
            matched = []
            missing = []
            evidence = []
            
            for req in all_requirements:
                check_prompt = f"""判断以下脚本内容是否覆盖了用户的需求。

用户需求：{req}

脚本内容（前1000字）：
{script_content[:1000]}

请只回答"是"或"否"，并简要说明原因（20字内）。
格式：是/否 - 原因"""
                
                try:
                    check_res = zhipu_client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": check_prompt}],
                        temperature=0.1,
                    )
                    answer = check_res.choices[0].message.content.strip()
                    
                    if "是" in answer:
                        matched.append(req)
                        evidence.append(f"✓ 已覆盖：{req} ({answer})")
                    else:
                        missing.append(req)
                        evidence.append(f"✗ 缺失：{req} ({answer})")
                except Exception as e:
                    print(f"[需求分析师] 检查失败: {e}")
                    missing.append(req)
            
            # 5. 计算评分和生成报告
            total = len(all_requirements)
            coverage = len(matched) / total if total > 0 else 1.0
            score = int(coverage * 100)
            
            issues = [f"未覆盖需求：{req}" for req in missing]
            
            if score >= 90:
                content = f"需求覆盖度优秀！{len(matched)}/{total} 项需求已完整体现在脚本中。"
            elif score >= 70:
                content = f"需求覆盖度良好。{len(matched)}/{total} 项需求已覆盖，建议补充缺失的 {len(missing)} 项。"
            else:
                content = f"需求覆盖度不足！仅覆盖 {len(matched)}/{total} 项，有 {len(missing)} 项重要需求缺失。"
            
            return self.create_message(
                phase="independent",
                content=content,
                evidence=evidence,
                score=score,
                issues=issues,
                confidence=0.85,
                # 新增：详细匹配明细
                details={
                    "matched_requirements": matched,  # 已覆盖的需求列表
                    "missing_requirements": missing,  # 未覆盖的需求列表
                    "total_requirements": total,
                    "coverage_rate": coverage
                }
            )
        
        except Exception as e:
            print(f"[需求分析师] 审核失败: {e}")
            return self.create_message(
                phase="independent",
                content=f"审核失败：{str(e)}",
                evidence=[],
                score=0,
                issues=["AI服务调用失败"],
                confidence=0.0
            )
