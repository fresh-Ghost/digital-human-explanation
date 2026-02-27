"""
审核智能体服务
功能：自动审核生成的脚本质量，确保内容准确性和需求匹配度
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.services.ai_service import zhipu_client
from app.services.knowledge_service import knowledge_service
from app.models.schemas import (
    AuditReport, RequirementCoverage, KnowledgeConsistency, DurationCheck
)


class AuditService:
    def __init__(self):
        self.audit_reports = {}  # 内存存储审核报告，script_id -> AuditReport
    
    async def audit_script(
        self, 
        script_id: str, 
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str
    ) -> AuditReport:
        """
        执行脚本审核
        
        Args:
            script_id: 脚本 ID
            script: 生成的脚本 JSON
            conversation_history: 对话历史
            kb_id: 知识库 ID
        
        Returns:
            AuditReport: 审核报告
        """
        print(f"\n开始审核脚本 {script_id}...", flush=True)
        print(f"脚本类型: {type(script)}", flush=True)
        print(f"脚本内容: {list(script.keys()) if isinstance(script, dict) else 'Not a dict'}", flush=True)
        
        issues = []
        audit_failed = False  # 标记审核是否因API失败而无法完成
        
        # 1. 需求匹配度检查
        requirement_coverage = await self._check_requirement_coverage(
            conversation_history, script
        )
        
        # 检查是否因API失败导致无法提取需求
        if not requirement_coverage.matched and not requirement_coverage.missing:
            print(f"[审核警告] 未提取到任何需求，可能API调用失败", flush=True)
            audit_failed = True
            issues.append("⚠️ 审核未完成：无法连接AI服务提取需求（可能智谱清言API暂时不可用）")
        elif requirement_coverage.missing:
            issues.extend([f"未覆盖需求：{req}" for req in requirement_coverage.missing])
        
        # 2. 知识一致性验证
        knowledge_consistency = await self._check_knowledge_consistency(
            script, kb_id
        )
        
        # 检查是否因API失败导致无法验证知识
        if knowledge_consistency.verified_facts == 0 and not knowledge_consistency.inconsistent_facts:
            print(f"[审核警告] 未验证任何事实，可能API调用失败", flush=True)
            audit_failed = True
            issues.append("⚠️ 审核未完成：无法连接AI服务验证知识一致性（可能智谱清言API暂时不可用）")
        elif knowledge_consistency.inconsistent_facts:
            issues.extend([f"知识不一致：{fact}" for fact in knowledge_consistency.inconsistent_facts])
        
        # 3. 时长合理性评估
        duration_check = self._check_duration(script)
        if duration_check.deviation_percent > 10:
            issues.append(
                f"时长偏离：实际 {duration_check.actual_minutes:.1f} 分钟 "
                f"vs 要求 {duration_check.expected_minutes:.1f} 分钟 "
                f"(偏差 {duration_check.deviation_percent:.1f}%)"
            )
        
        # 4. 计算总分
        # 如果审核因API失败而无法完成，返回-1表示审核失败
        if audit_failed:
            overall_score = -1
            suggestions = ["⚠️ 审核失败：AI服务暂时不可用，请稍后重试。如果问题持续，请检查智谱清言API配置和网络连接。"]
        else:
            overall_score = self._calculate_score(
                requirement_coverage, knowledge_consistency, duration_check
            )
            # 5. 生成改进建议
            suggestions = self._generate_suggestions(issues)
        
        # 6. 构建审核报告
        audit_report = AuditReport(
            script_id=script_id,
            audit_time=datetime.now().isoformat(),
            overall_score=overall_score,
            requirement_coverage=requirement_coverage,
            knowledge_consistency=knowledge_consistency,
            duration_check=duration_check,
            issues=issues,
            suggestions=suggestions
        )
        
        # 保存报告
        self.audit_reports[script_id] = audit_report
        
        print(f"审核完成，评分：{overall_score}/100")
        return audit_report
    
    async def _check_requirement_coverage(
        self, 
        conversation_history: List[Dict[str, str]], 
        script: Dict[str, Any]
    ) -> RequirementCoverage:
        """检查需求覆盖度"""
        # 提取用户需求清单
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation_history
        ])
        
        # 提取脚本中的实际内容
        script_content = " ".join([
            node["voice_text"] for node in script.get("timeline", [])
        ])
        
        # 调试输出
        print(f"[审核调试] 脚本内容长度: {len(script_content)} 字符", flush=True)
        print(f"[审核调试] 脚本前200字: {script_content[:200]}", flush=True)
        print(f"[审核调试] timeline节点数: {len(script.get('timeline', []))}", flush=True)
        
        extract_prompt = f"""从以下对话中提取用户明确提出的所有讲解要求和重点主题。

对话历史：
{history_text}

请返回 JSON 格式：
{{
  "focus_topics": ["重点主题1", "重点主题2"],
  "special_requirements": ["特殊要求1"]
}}

只返回 JSON，不要其他内容。"""
        
        try:
            extract_res = zhipu_client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": extract_prompt}],
                temperature=0.1,
            )
            requirements_json = extract_res.choices[0].message.content.strip()
            # 清理可能的 markdown 代码块标记
            requirements_json = requirements_json.replace("```json", "").replace("```", "").strip()
            requirements = json.loads(requirements_json)
            
            focus_topics = requirements.get("focus_topics", [])
            special_requirements = requirements.get("special_requirements", [])
            all_requirements = focus_topics + special_requirements
            
            print(f"[审核调试] 提取到的需求: {all_requirements}")
            
            matched = []
            missing = []
            
            for req in all_requirements:
                # 使用AI进行语义匹配判断（避免简单关键词匹配的局限性）
                check_prompt = f"""判断以下脚本内容是否覆盖了用户的需求。

用户需求：{req}

脚本内容（前1000字）：
{script_content[:1000]}

请只回答"是"或"否"，不要有其他内容。如果脚本中有相关内容（即使措辞不同），回答"是"。"""
                
                try:
                    check_res = zhipu_client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": check_prompt}],
                        temperature=0.1,
                    )
                    answer = check_res.choices[0].message.content.strip().lower()
                    
                    if "是" in answer or "yes" in answer:
                        matched.append(req)
                        print(f"[审核调试] ✓ 需求已覆盖: {req}", flush=True)
                    else:
                        missing.append(req)
                        print(f"[审核调试] ✗ 需求缺失: {req}", flush=True)
                except Exception as e:
                    print(f"[审核调试] 需求匹配检查失败: {e}", flush=True)
                    # 出错时保守处理，认为未覆盖
                    missing.append(req)
            
            return RequirementCoverage(matched=matched, missing=missing)
        
        except Exception as e:
            print(f"需求提取失败: {e}")
            return RequirementCoverage(matched=[], missing=[])
    
    async def _check_knowledge_consistency(
        self, 
        script: Dict[str, Any], 
        kb_id: str
    ) -> KnowledgeConsistency:
        """检查知识一致性"""
        script_content = "\n".join([
            node["voice_text"] for node in script.get("timeline", [])
        ])
        
        # 提取脚本中的事实性陈述
        fact_extract_prompt = f"""从以下脚本中提取所有事实性陈述（数据、参数、技术指标、功能描述）。

脚本内容：
{script_content}

请返回 JSON 格式：
{{
  "facts": ["陈述1", "陈述2", "陈述3"]
}}

只返回 JSON，不要其他内容。每条陈述应该是一个完整的句子。"""
        
        try:
            fact_res = zhipu_client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": fact_extract_prompt}],
                temperature=0.1,
            )
            facts_json = fact_res.choices[0].message.content.strip()
            facts_json = facts_json.replace("```json", "").replace("```", "").strip()
            facts_data = json.loads(facts_json)
            facts = facts_data.get("facts", [])
            
            # 在知识库中验证每条事实
            # 优先使用脚本生成时使用的知识库ID（必须使用，不然审核会失败）
            actual_kb_id = script.get('_kb_id')
            if not actual_kb_id:
                print(f"[审核错误] 脚本中未存储知识库ID，请重新生成脚本！", flush=True)
                # 回退：使用当前激活的知识库
                actual_kb_id = knowledge_service.current_kb_id
            
            print(f"[审核调试] 请求的kb_id: {kb_id}, 脚本中存储的kb_id: {script.get('_kb_id')}", flush=True)
            print(f"[审核调试] 实际使用的kb_id: {actual_kb_id}", flush=True)
            
            vectorstore = None
            if actual_kb_id == "default":
                # 先尝试使用当前激活的知识库
                vectorstore = knowledge_service.vectorstore
                print(f"[审核调试] 使用当前激活知识库: {knowledge_service.current_kb_id}", flush=True)
            else:
                vectorstore = knowledge_service.load_vectorstore(actual_kb_id)
                if not vectorstore:
                    vectorstore = knowledge_service.vectorstore
                print(f"[审核调试] 加载脚本指定知识库: {actual_kb_id}", flush=True)
            
            # 测试知识库是否可用
            print(f"[审核调试] 使用知识库: {kb_id}")
            print(f"[审核调试] 知识库对象: {vectorstore}")
            try:
                test_docs = vectorstore.similarity_search("无人机", k=1)
                print(f"[审核调试] 知识库测试查询结果数: {len(test_docs)}")
                if test_docs:
                    print(f"[审核调试] 测试文档示例: {test_docs[0].page_content[:100]}")
            except Exception as e:
                print(f"[审核调试] 知识库测试查询失败: {e}")
            
            inconsistent_facts = []
            verified_count = 0
            verified_facts_list = []  # 记录验证通过的事实
            
            print(f"[审核调试] 提取到 {len(facts)} 条事实陈述，将验证前10条")
            
            for idx, fact in enumerate(facts[:10], 1):  # 限制验证数量以控制时间
                try:
                    kb_docs = vectorstore.similarity_search(fact, k=3)
                    
                    if not kb_docs:
                        print(f"[审核调试] 事实{idx}: 知识库无相关内容 - {fact[:50]}", flush=True)
                        inconsistent_facts.append(fact)
                        continue
                    
                    # 使用AI判断语义一致性（而非简单的词汇重叠）
                    kb_context = "\n\n".join([doc.page_content[:300] for doc in kb_docs])
                    verify_prompt = f"""判断脚本中的陈述是否与知识库内容一致（允许措辞不同，但不能有事实性错误）。

脚本陈述：{fact}

知识库内容：
{kb_context}

请只回答"一致"或"不一致"，不要有其他内容。如果脚本陈述的内容与知识库相符或是知识库内容的合理推论，回答"一致"。"""
                    
                    try:
                        verify_res = zhipu_client.chat.completions.create(
                            model="glm-4-flash",
                            messages=[{"role": "user", "content": verify_prompt}],
                            temperature=0.1,
                        )
                        answer = verify_res.choices[0].message.content.strip()
                        
                        if "一致" in answer or "consistent" in answer.lower():
                            verified_count += 1
                            verified_facts_list.append(fact)  # 记录验证通过的事实
                            print(f"[审核调试] 事实{idx}: 验证通过 - {fact[:50]}", flush=True)
                        else:
                            inconsistent_facts.append(fact)
                            print(f"[审核调试] 事实{idx}: 不一致 - {fact[:50]}", flush=True)
                    except Exception as e:
                        print(f"[审核调试] 事实{idx}: AI验证失败 - {e}", flush=True)
                        # 验证失败时保守处理，认为不一致
                        inconsistent_facts.append(fact)
                except Exception as e:
                    print(f"[审核调试] 事实{idx}: 验证失败 - {e}")
            
            # 释放临时加载的知识库
            if kb_id != knowledge_service.current_kb_id and vectorstore:
                knowledge_service.close_vectorstore(vectorstore)
                import gc
                gc.collect()
            
            return KnowledgeConsistency(
                verified_facts=verified_count,
                verified_facts_list=verified_facts_list,
                inconsistent_facts=inconsistent_facts
            )
        
        except Exception as e:
            print(f"知识一致性检查失败: {e}")
            return KnowledgeConsistency(verified_facts=0, verified_facts_list=[], inconsistent_facts=[])
    
    def _check_duration(self, script: Dict[str, Any]) -> DurationCheck:
        """检查时长合理性"""
        expected_minutes = script.get("meta", {}).get("estimated_duration", 5)
        
        total_duration_ms = sum([
            node.get("duration_ms", 0) for node in script.get("timeline", [])
        ])
        actual_minutes = total_duration_ms / 60000
        
        deviation = abs(actual_minutes - expected_minutes) / expected_minutes * 100
        
        return DurationCheck(
            expected_minutes=float(expected_minutes),
            actual_minutes=actual_minutes,
            deviation_percent=deviation
        )
    
    def _calculate_score(
        self,
        requirement_coverage: RequirementCoverage,
        knowledge_consistency: KnowledgeConsistency,
        duration_check: DurationCheck
    ) -> int:
        """计算总分（0-100）"""
        score = 100
        
        # 需求覆盖度扣分（每缺失一项扣 10 分）
        score -= len(requirement_coverage.missing) * 10
        
        # 知识一致性扣分（每发现一条不一致扣 5 分）
        score -= len(knowledge_consistency.inconsistent_facts) * 5
        
        # 时长偏差扣分
        if duration_check.deviation_percent > 20:
            score -= 20
        elif duration_check.deviation_percent > 10:
            score -= 10
        
        return max(0, min(100, score))
    
    def _generate_suggestions(self, issues: List[str]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if any("未覆盖需求" in issue for issue in issues):
            suggestions.append("建议：重新生成脚本时，明确要求覆盖所有用户提出的重点主题。")
        
        if any("知识不一致" in issue for issue in issues):
            suggestions.append("建议：检查知识库内容是否完整，或调整脚本中的事实性陈述以匹配知识库。")
        
        if any("时长偏离" in issue for issue in issues):
            suggestions.append("建议：调整脚本节点数量或每页内容长度，使总时长更接近用户要求。")
        
        if not suggestions:
            suggestions.append("脚本质量良好，无重大问题。")
        
        return suggestions
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """简单的文本相似度计算（基于词汇重叠）"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def get_audit_report(self, script_id: str) -> Optional[AuditReport]:
        """获取审核报告"""
        return self.audit_reports.get(script_id)


# 全局实例
audit_service = AuditService()
