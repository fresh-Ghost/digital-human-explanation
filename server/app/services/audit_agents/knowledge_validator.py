"""
知识审查官智能体
职责：验证脚本中的事实性陈述
"""
import json
from typing import Dict, Any, List
from .base_agent import BaseAuditAgent
from app.services.ai_service import zhipu_client
from app.services.knowledge_service import knowledge_service


class KnowledgeValidator(BaseAuditAgent):
    """知识审查官"""
    
    def __init__(self):
        super().__init__(
            agent_id="knowledge_validator",
            agent_name="知识审查官",
            emoji="🔍"
        )
    
    async def audit(
        self, 
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行知识一致性审核"""
        
        # 1. 提取脚本内容
        script_content = "\n".join([
            node["voice_text"] for node in script.get("timeline", [])
        ])
        
        # 2. 提取事实性陈述
        fact_extract_prompt = f"""从以下脚本中提取所有事实性陈述（数据、参数、技术指标、功能描述）。

脚本内容：
{script_content}

请返回 JSON 格式：
{{
  "facts": ["陈述1", "陈述2", "陈述3"]
}}

只返回 JSON，不要其他内容。每条陈述应该是一个完整的句子，限制在10条以内。"""
        
        try:
            fact_res = zhipu_client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": fact_extract_prompt}],
                temperature=0.1,
            )
            facts_json = fact_res.choices[0].message.content.strip()
            facts_json = facts_json.replace("```json", "").replace("```", "").strip()
            facts_data = json.loads(facts_json)
            facts = facts_data.get("facts", [])[:10]  # 限制数量
            
            # 3. 加载知识库
            actual_kb_id = script.get('_kb_id') or kb_id
            vectorstore = None
            if actual_kb_id == "default":
                vectorstore = knowledge_service.vectorstore
            else:
                vectorstore = knowledge_service.load_vectorstore(actual_kb_id)
                if not vectorstore:
                    vectorstore = knowledge_service.vectorstore
            
            # 4. 验证每条事实
            verified = []
            inconsistent = []
            evidence = []
            
            for idx, fact in enumerate(facts, 1):
                try:
                    kb_docs = vectorstore.similarity_search(fact, k=3)
                    
                    if not kb_docs:
                        inconsistent.append(fact)
                        evidence.append(f"✗ 无依据：{fact[:50]}...")
                        continue
                    
                    # 使用AI判断一致性
                    kb_context = "\n\n".join([doc.page_content[:300] for doc in kb_docs])
                    verify_prompt = f"""判断脚本中的陈述是否与知识库内容一致。

脚本陈述：{fact}

知识库内容：
{kb_context}

请只回答"一致"或"不一致"，并简要说明原因（20字内）。
格式：一致/不一致 - 原因"""
                    
                    verify_res = zhipu_client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": verify_prompt}],
                        temperature=0.1,
                    )
                    answer = verify_res.choices[0].message.content.strip()
                    
                    if "一致" in answer:
                        verified.append(fact)
                        evidence.append(f"✓ 已验证：{fact[:50]}... ({answer})")
                    else:
                        inconsistent.append(fact)
                        evidence.append(f"✗ 不一致：{fact[:50]}... ({answer})")
                
                except Exception as e:
                    print(f"[知识审查官] 验证失败: {e}")
                    inconsistent.append(fact)
            
            # 5. 计算评分
            total = len(facts)
            accuracy = len(verified) / total if total > 0 else 1.0
            score = int(accuracy * 100)
            
            issues = [f"知识不一致：{fact[:50]}..." for fact in inconsistent]
            
            if score >= 90:
                content = f"知识准确度优秀！{len(verified)}/{total} 条事实陈述经知识库验证无误。"
            elif score >= 70:
                content = f"知识准确度良好。{len(verified)}/{total} 条事实已验证，{len(inconsistent)} 条存疑。"
            else:
                content = f"知识准确度不足！{len(inconsistent)}/{total} 条事实陈述与知识库不符。"
            
            # 释放知识库
            if kb_id != knowledge_service.current_kb_id and vectorstore:
                knowledge_service.close_vectorstore(vectorstore)
                import gc
                gc.collect()
            
            return self.create_message(
                phase="independent",
                content=content,
                evidence=evidence,
                score=score,
                issues=issues,
                confidence=0.9,
                # 新增：详细匹配明细
                details={
                    "verified_facts": verified,  # 已验证的知识点
                    "inconsistent_facts": inconsistent,  # 不一致的知识点
                    "total_facts": total,
                    "accuracy_rate": accuracy
                }
            )
        
        except Exception as e:
            print(f"[知识审查官] 审核失败: {e}")
            return self.create_message(
                phase="independent",
                content=f"审核失败：{str(e)}",
                evidence=[],
                score=0,
                issues=["AI服务调用失败或知识库不可用"],
                confidence=0.0
            )
