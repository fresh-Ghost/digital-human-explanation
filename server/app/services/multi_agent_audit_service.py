"""
多智能体审核协调器
负责协调多个审核智能体的工作流程
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from app.services.audit_agents import (
    RequirementAnalyst,
    KnowledgeValidator,
    ExperienceDesigner,
    LanguagePolisher,
    Moderator
)


class MultiAgentAuditService:
    """多智能体审核服务"""
    
    def __init__(self):
        # 初始化所有智能体
        self.agents = {
            "requirement_analyst": RequirementAnalyst(),
            "knowledge_validator": KnowledgeValidator(),
            "experience_designer": ExperienceDesigner(),
            "language_polisher": LanguagePolisher(),
        }
        self.moderator = Moderator()
        
        # 存储审核会话
        self.audit_sessions = {}  # session_id -> session_data
    
    async def start_audit(
        self,
        script_id: str,
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        message_callback: Optional[Callable] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        启动多智能体审核 - 聊天室式讨论
        """
        # 如果传入已有session，则复用（用于pending -> running）
        if session_id and session_id in self.audit_sessions:
            session_data = self.audit_sessions[session_id]
            session_data["start_time"] = datetime.now().isoformat()
            session_data["end_time"] = None
            session_data["status"] = "running"
            session_data["messages"] = []
            session_data["agent_results"] = {}
            session_data["final_report"] = None
            session_data.pop("modification_suggestions", None)
            # 确保脚本/上下文信息是最新的
            session_data["script_id"] = script_id
            session_data["conversation_history"] = conversation_history
            session_data["kb_id"] = kb_id
        else:
            session_id = session_id or str(uuid.uuid4())
            session_data = {
                "session_id": session_id,
                "script_id": script_id,
                "conversation_history": conversation_history,
                "kb_id": kb_id,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "messages": [],
                "agent_results": {},
                "final_report": None,
                "status": "running"
            }
            self.audit_sessions[session_id] = session_data
        
        # 发送脚本内容
        script_text = "\n\n".join([
            f"【第{i+1}页】\n{node['voice_text']}"
            for i, node in enumerate(script.get("timeline", [])[:3])
        ])
        
        await self._send_message(session_data, {
            "type": "script_preview",
            "session_id": session_id,
            "content": f"本次审核的脚本内容（共{len(script.get('timeline', []))}页，展示前3页）：\n\n{script_text}\n\n..."
        }, message_callback, delay=1.0)
        
        # 主席开场
        await self._send_message(session_data, {
            "type": "moderator_speak",
            "agent_id": "moderator",
            "agent_name": "仲裁主席",
            "emoji": "⚖️",
            "content": "⚖️ 主席：各位专家好，现在开始对这份讲解脚本进行审核。请各位从自己的专业角度进行评估，有什么发现请随时发言。"
        }, message_callback, delay=1.5)  # 主席开场延时1.5秒
        
        try:
            # 新流程：串行讨论式审核
            await self._chat_room_style_audit(
                session_data,
                script,
                conversation_history,
                kb_id,
                message_callback
            )
            
            session_data["status"] = "completed"
            session_data["end_time"] = datetime.now().isoformat()
            
        except Exception as e:
            session_data["status"] = "error"
            session_data["error"] = str(e)
            await self._send_message(session_data, {
                "type": "error",
                "content": f"审核过程出错：{str(e)}"
            }, message_callback, delay=0.5)  # 错误消息
        
        return session_id
    
    async def _chat_room_style_audit(
        self,
        session_data: Dict[str, Any],
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        message_callback: Optional[Callable]
    ):
        """聊天室式审核流程 - 真正的串行对话讨论"""
        
        agent_order = [
            ("requirement_analyst", self.agents["requirement_analyst"]),
            ("knowledge_validator", self.agents["knowledge_validator"]),
            ("experience_designer", self.agents["experience_designer"]),
            ("language_polisher", self.agents["language_polisher"])
        ]
        
        # 讨论历史：用于智能体之间的上下文传递
        discussion_history = []
        
        # 第一轮：每个专家逐个发言（真实串行，每人看到前面的讨论）
        for idx, (agent_id, agent) in enumerate(agent_order):
            # 显示"typing..."
            await self._send_message(session_data, {
                "type": "agent_typing",
                "agent_id": agent_id,
                "agent_name": agent.agent_name,
                "emoji": agent.emoji,
                "content": f"{agent.emoji} {agent.agent_name} 正在审核..."
            }, message_callback, delay=0.3)  # typing消息延时短一些
            
            # 构建当前智能体的审核上下文：
            # 1. 原始脚本
            # 2. 用户需求（conversation_history）
            # 3. 前面专家的讨论内容（discussion_history）
            audit_context = {
                "previous_discussions": discussion_history.copy(),  # 前面专家的意见
                "my_position": idx,  # 我是第几个发言的
                "total_agents": len(agent_order)
            }
            
            # 【关键改动】创建一个任务，在audit执行期间发送进度消息
            audit_task = asyncio.create_task(
                agent.audit(script, conversation_history, kb_id, context=audit_context)
            )
            
            # 在等待audit完成期间，每隔5秒发送一次进度提示
            progress_counter = 0
            while not audit_task.done():
                await asyncio.sleep(5)
                progress_counter += 1
                if not audit_task.done():  # 再次检查，避免刚完成就发消息
                    await self._send_message(session_data, {
                        "type": "agent_progress",
                        "agent_id": agent_id,
                        "agent_name": agent.agent_name,
                        "emoji": agent.emoji,
                        "content": f"{agent.emoji} {agent.agent_name} 正在深度分析中...（{progress_counter * 5}秒）"
                    }, message_callback, delay=0.3)  # 进度消息延时短
            
            # 获取审核结果
            result = await audit_task
            session_data["agent_results"][agent_id] = result
            
            # 提取审核结果
            score = result.get("score", 0)
            issues = result.get("issues", [])
            content = result.get("content", "")
            details = result.get("details", None)  # 【新增】提取details字段
            evidence = result.get("evidence", [])  # 【新增】提取evidence字段
            
            # 生成聊天式消息
            chat_message = f"{agent.emoji} {agent.agent_name}：\n"
            
            # 如果不是第一个专家，可以引用前面的讨论
            if idx > 0 and discussion_history:
                last_discussion = discussion_history[-1]
                # 智能判断是否需要回应前面的意见
                if abs(score - last_discussion['score']) > 15:
                    if score < last_discussion['score']:
                        chat_message += f"我注意到{last_discussion['agent_name']}给了{last_discussion['score']}分，但从我的专业角度，我有不同看法。\n\n"
                    else:
                        chat_message += f"我同意{last_discussion['agent_name']}的部分观点，不过我想补充一些内容。\n\n"
            
            chat_message += f"{content}\n\n"
            if issues:
                chat_message += f"发现{len(issues)}个问题：\n"
                for i, issue in enumerate(issues[:3], 1):
                    chat_message += f"{i}. {issue}\n"
            chat_message += f"\n我的评分：{score}/100"
            
            # 保存到讨论历史
            discussion_history.append({
                "agent_id": agent_id,
                "agent_name": agent.agent_name,
                "emoji": agent.emoji,
                "score": score,
                "content": content,
                "issues": issues,
                "full_message": chat_message
            })
            
            # 发送消息
            message_data = {
                "type": "agent_speak",
                "agent_id": agent_id,
                "agent_name": agent.agent_name,
                "emoji": agent.emoji,
                "score": score,
                "content": chat_message
            }
            
            # 【关键】如果有details字段，添加到消息中
            if details:
                message_data["details"] = details
            
            # 如果有evidence字段，也添加
            if evidence:
                message_data["evidence"] = evidence
            
            await self._send_message(session_data, message_data, message_callback, delay=1.5)  # 【关键】发言消息延时长，给用户阅读时间
        
        # 第二轮：如果有分歧，进行真实辩论（基于讨论历史）
        scores = [d['score'] for d in discussion_history]
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        score_variance = max_score - min_score
        
        if score_variance > 20:
            await self._send_message(session_data, {
                "type": "moderator_speak",
                "agent_id": "moderator",
                "agent_name": "仲裁主席",
                "emoji": "⚖️",
                "content": f"⚖️ 主席：我注意到各位专家的评分差异较大（{score_variance}分），让我们针对争议点进行讨论。"
            }, message_callback, delay=1.2)  # 主席插话
            
            # 找出分歧最大的两个专家
            sorted_discussions = sorted(discussion_history, key=lambda x: x['score'])
            
            if len(sorted_discussions) >= 2:
                critic = sorted_discussions[0]  # 最低分
                supporter = sorted_discussions[-1]  # 最高分
                
                # 批评者详细说明理由
                await self._send_message(session_data, {
                    "type": "agent_typing",
                    "agent_id": critic['agent_id'],
                    "agent_name": critic['agent_name'],
                    "emoji": critic['emoji'],
                    "content": f"{critic['emoji']} {critic['agent_name']} 正在详细说明..."
                }, message_callback, delay=0.3)
                
                # 这里应该再次调用AI，让智能体基于讨论历史生成回应
                # 为了演示，先用模板（后续可以改成AI生成）
                critic_debate = f"{critic['emoji']} {critic['agent_name']}：\n"
                critic_debate += f"我给出{critic['score']}分是有充分理由的。"
                if critic['issues']:
                    critic_debate += f"特别是这个问题：{critic['issues'][0]}。这会严重影响脚本质量。"
                
                await self._send_message(session_data, {
                    "type": "agent_debate",
                    "agent_id": critic['agent_id'],
                    "agent_name": critic['agent_name'],
                    "emoji": critic['emoji'],
                    "content": critic_debate
                }, message_callback, delay=1.5)  # 辩论消息
                
                # 支持者回应
                await self._send_message(session_data, {
                    "type": "agent_typing",
                    "agent_id": supporter['agent_id'],
                    "agent_name": supporter['agent_name'],
                    "emoji": supporter['emoji'],
                    "content": f"{supporter['emoji']} {supporter['agent_name']} 正在回应..."
                }, message_callback, delay=0.3)
                
                supporter_debate = f"{supporter['emoji']} {supporter['agent_name']}：\n"
                supporter_debate += f"@{critic['agent_name']} 我理解你的担忧，但从我的专业角度，我给出{supporter['score']}分是因为脚本也有很多优点。"
                supporter_debate += f"我们可以在保留优点的基础上，针对你提到的'{critic['issues'][0] if critic['issues'] else '问题'}'进行优化。"
                
                await self._send_message(session_data, {
                    "type": "agent_debate",
                    "agent_id": supporter['agent_id'],
                    "agent_name": supporter['agent_name'],
                    "emoji": supporter['emoji'],
                    "content": supporter_debate
                }, message_callback, delay=1.5)  # 辩论消息
                
                # 其他专家补充意见
                for discussion in discussion_history:
                    if discussion['agent_id'] not in [critic['agent_id'], supporter['agent_id']]:
                        if discussion['issues']:
                            await self._send_message(session_data, {
                                "type": "agent_debate",
                                "agent_id": discussion['agent_id'],
                                "agent_name": discussion['agent_name'],
                                "emoji": discussion['emoji'],
                                "content": f"{discussion['emoji']} {discussion['agent_name']}：\n我也想补充一点，关于{discussion['issues'][0]}这个问题，我认为需要重视。"
                            }, message_callback, delay=1.2)  # 补充意见
        
        # 第三轮：主席总结
        await self._send_message(session_data, {
            "type": "moderator_speak",
            "agent_id": "moderator",
            "agent_name": "仲裁主席",
            "emoji": "⚖️",
            "content": "⚖️ 主席：感谢各位专家的意见。现在我来综合大家的观点，生成最终报告..."
        }, message_callback, delay=2.0)  # 主席总结延时2秒
        
        # 主席生成最终报告
        context = {"agent_results": session_data["agent_results"]}
        final_report = await self.moderator.audit(
            script,
            conversation_history,
            kb_id,
            context
        )
        
        session_data["final_report"] = final_report
        session_data["modification_suggestions"] = self._extract_modification_suggestions(session_data)
        
        await self._send_message(session_data, {
            "type": "final_report",
            "agent_id": "moderator",
            "agent_name": "仲裁主席",
            "emoji": "⚖️",
            "score": final_report.get("score", 0),
            "content": final_report.get("content", "")
        }, message_callback, delay=2.5)  # 最终报告延时2.5秒
        
        await self._send_message(session_data, {
            "type": "session_complete",
            "content": "✅ 审核会议结束，感谢各位专家的参与！"
        }, message_callback, delay=1.0)  # 结束消息
    
    async def _phase_independent_audit(
        self,
        session_data: Dict[str, Any],
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        message_callback: Optional[Callable]
    ):
        """阶段1：独立审核"""
        
        await self._send_message(session_data, {
            "type": "phase_start",
            "phase": "independent",
            "content": "【阶段一：独立审核】各位专家开始独立评估脚本质量..."
        }, message_callback)
        
        # 并行执行所有智能体的审核
        tasks = []
        for agent_id, agent in self.agents.items():
            tasks.append(self._run_agent_audit(
                agent_id,
                agent,
                script,
                conversation_history,
                kb_id,
                session_data,
                message_callback
            ))
        
        # 等待所有智能体完成
        await asyncio.gather(*tasks)
    
    async def _run_agent_audit(
        self,
        agent_id: str,
        agent: Any,
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        session_data: Dict[str, Any],
        message_callback: Optional[Callable]
    ):
        """运行单个智能体的审核"""
        
        # 发送开始审核消息
        await self._send_message(session_data, {
            "type": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent.agent_name,
            "emoji": agent.emoji,
            "content": f"{agent.emoji} {agent.agent_name}开始审核..."
        }, message_callback)
        
        try:
            # 执行审核
            result = await agent.audit(script, conversation_history, kb_id)
            
            # 保存结果
            session_data["agent_results"][agent_id] = result
            session_data["messages"].append(result)
            
            # 发送审核结果
            await self._send_message(session_data, {
                "type": "agent_result",
                **result
            }, message_callback)
            
        except Exception as e:
            error_msg = {
                "type": "agent_error",
                "agent_id": agent_id,
                "agent_name": agent.agent_name,
                "content": f"{agent.emoji} {agent.agent_name}审核失败：{str(e)}"
            }
            await self._send_message(session_data, error_msg, message_callback)
    
    async def _phase_discussion(
        self,
        session_data: Dict[str, Any],
        message_callback: Optional[Callable]
    ):
        """阶段2：辩论讨论阶段 - 智能体之间相互质疑和回应"""
        
        agent_results = session_data.get("agent_results", {})
        
        # 检查是否有分歧
        scores = [r.get("score", 0) for r in agent_results.values()]
        if not scores:
            return
        
        max_score = max(scores)
        min_score = min(scores)
        score_variance = max_score - min_score
        
        if score_variance > 20:  # 分歧阈值
            await self._send_message(session_data, {
                "type": "phase_start",
                "phase": "discussion",
                "content": f"【阶段二：圆桌辩论】检测到评分差异（{score_variance}分），进入辩论环节..."
            }, message_callback)
            
            # 主席发起讨论
            discussion_summary = self._create_discussion_summary(agent_results)
            await self._send_message(session_data, {
                "type": "moderator_speak",
                "agent_id": "moderator",
                "agent_name": "仲裁主席",
                "emoji": "⚖️",
                "content": f"⚖️ 主席发言：我注意到各位专家的评分差异较大。{discussion_summary} 让我们逐一讨论这些分歧点。"
            }, message_callback)
            
            # 识别争议点
            controversial_topics = self._identify_controversial_topics(agent_results)
            
            # 针对每个争议点进行辩论
            for topic in controversial_topics:
                await self._debate_on_topic(
                    topic,
                    agent_results,
                    session_data,
                    message_callback
                )
            
            await self._send_message(session_data, {
                "type": "discussion_end",
                "content": "【辩论结束】各方观点已充分表达，进入共识阶段。"
            }, message_callback)
            
        else:
            await self._send_message(session_data, {
                "type": "phase_skip",
                "phase": "discussion",
                "content": "【跳过讨论】各专家意见较为一致，无需辩论。"
            }, message_callback)
    
    def _create_discussion_summary(self, agent_results: Dict[str, Any]) -> str:
        """创建讨论概述"""
        summaries = []
        for agent_id, result in agent_results.items():
            agent_name = result.get("agent_name", "未知")
            score = result.get("score", 0)
            issues_count = len(result.get("issues", []))
            summaries.append(f"{agent_name}给出{score}分（发现{issues_count}个问题）")
        return "、".join(summaries)
    
    def _identify_controversial_topics(self, agent_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别争议话题"""
        topics = []
        
        # 收集所有issue
        all_issues = {}
        for agent_id, result in agent_results.items():
            for issue in result.get("issues", []):
                # 按问题类型分组
                issue_type = self._classify_issue(issue)
                if issue_type not in all_issues:
                    all_issues[issue_type] = []
                all_issues[issue_type].append({
                    "agent_id": agent_id,
                    "agent_name": result.get("agent_name"),
                    "emoji": result.get("emoji"),
                    "issue": issue,
                    "score": result.get("score")
                })
        
        # 找出有争议的话题（有人认为是问题，有人不认为）
        for issue_type, items in all_issues.items():
            if len(items) >= 2:  # 至少两个专家提到此问题
                topics.append({
                    "type": issue_type,
                    "items": items
                })
        
        # 如果没有明显争议话题，创建一个基于评分差异的话题
        if not topics:
            scores = [(aid, r.get("score", 0), r.get("agent_name"), r.get("emoji")) 
                     for aid, r in agent_results.items()]
            scores.sort(key=lambda x: x[1])
            
            if len(scores) >= 2:
                topics.append({
                    "type": "overall_quality",
                    "lowest_scorer": {
                        "agent_id": scores[0][0],
                        "score": scores[0][1],
                        "agent_name": scores[0][2],
                        "emoji": scores[0][3],
                        "result": agent_results[scores[0][0]]
                    },
                    "highest_scorer": {
                        "agent_id": scores[-1][0],
                        "score": scores[-1][1],
                        "agent_name": scores[-1][2],
                        "emoji": scores[-1][3],
                        "result": agent_results[scores[-1][0]]
                    }
                })
        
        return topics[:3]  # 最多讨论3个话题
    
    def _classify_issue(self, issue: str) -> str:
        """分类问题类型"""
        issue_lower = issue.lower()
        if "需求" in issue or "requirement" in issue_lower or "缺失" in issue:
            return "requirement_coverage"
        elif "知识" in issue or "knowledge" in issue_lower or "事实" in issue:
            return "knowledge_accuracy"
        elif "时长" in issue or "duration" in issue_lower or "过长" in issue or "过短" in issue:
            return "duration_issue"
        elif "语言" in issue or "language" in issue_lower or "表达" in issue:
            return "language_quality"
        else:
            return "other"
    
    async def _debate_on_topic(
        self,
        topic: Dict[str, Any],
        agent_results: Dict[str, Any],
        session_data: Dict[str, Any],
        message_callback: Optional[Callable]
    ):
        """针对特定话题进行辩论"""
        
        topic_type = topic.get("type")
        
        if topic_type == "overall_quality":
            # 评分差异辩论
            await self._debate_score_difference(
                topic["lowest_scorer"],
                topic["highest_scorer"],
                session_data,
                message_callback
            )
        else:
            # 具体问题辩论
            await self._debate_specific_issue(
                topic,
                agent_results,
                session_data,
                message_callback
            )
    
    async def _debate_score_difference(
        self,
        critic: Dict[str, Any],
        supporter: Dict[str, Any],
        session_data: Dict[str, Any],
        message_callback: Optional[Callable]
    ):
        """评分差异辩论"""
        
        # 批评者发言（评分低的专家）
        critic_issues = critic["result"].get("issues", [])
        critic_statement = f"我给出{critic['score']}分，主要基于以下问题：" + "；".join(critic_issues[:2])
        
        await self._send_message(session_data, {
            "type": "agent_debate",
            "debate_role": "critic",
            "agent_id": critic["agent_id"],
            "agent_name": critic["agent_name"],
            "emoji": critic["emoji"],
            "content": f"{critic['emoji']} {critic['agent_name']}：{critic_statement}"
        }, message_callback)
        
        await asyncio.sleep(0.5)  # 模拟思考
        
        # 支持者回应（评分高的专家）
        supporter_evidence = supporter["result"].get("evidence", [])
        supporter_statement = f"我给出{supporter['score']}分，因为我看到了一些优点：" + "；".join(supporter_evidence[:2]) if supporter_evidence else "整体质量可以接受"
        
        await self._send_message(session_data, {
            "type": "agent_debate",
            "debate_role": "supporter",
            "agent_id": supporter["agent_id"],
            "agent_name": supporter["agent_name"],
            "emoji": supporter["emoji"],
            "content": f"{supporter['emoji']} {supporter['agent_name']}：{supporter_statement}"
        }, message_callback)
        
        await asyncio.sleep(0.5)
        
        # 主席总结
        await self._send_message(session_data, {
            "type": "moderator_summary",
            "agent_id": "moderator",
            "emoji": "⚖️",
            "content": f"⚖️ 主席：两位专家的观点都有道理。{critic['agent_name']}指出了具体问题，{supporter['agent_name']}看到了积极面。我们需要在最终评分中平衡这两方面。"
        }, message_callback)
    
    async def _debate_specific_issue(
        self,
        topic: Dict[str, Any],
        agent_results: Dict[str, Any],
        session_data: Dict[str, Any],
        message_callback: Optional[Callable]
    ):
        """针对具体问题的辩论"""
        
        items = topic.get("items", [])
        if len(items) < 2:
            return
        
        topic_name = {
            "requirement_coverage": "需求覆盖度",
            "knowledge_accuracy": "知识准确性",
            "duration_issue": "时长合理性",
            "language_quality": "语言质量"
        }.get(topic["type"], "其他问题")
        
        # 第一位专家提出问题
        first_agent = items[0]
        await self._send_message(session_data, {
            "type": "agent_debate",
            "debate_role": "raise_issue",
            "agent_id": first_agent["agent_id"],
            "agent_name": first_agent["agent_name"],
            "emoji": first_agent["emoji"],
            "content": f"{first_agent['emoji']} {first_agent['agent_name']}：关于{topic_name}，我发现：{first_agent['issue']}"
        }, message_callback)
        
        await asyncio.sleep(0.5)
        
        # 第二位专家回应
        second_agent = items[1]
        await self._send_message(session_data, {
            "type": "agent_debate",
            "debate_role": "respond",
            "agent_id": second_agent["agent_id"],
            "agent_name": second_agent["agent_name"],
            "emoji": second_agent["emoji"],
            "content": f"{second_agent['emoji']} {second_agent['agent_name']}：我同意这个观点。{second_agent['issue']}"
        }, message_callback)
    
    async def _phase_consensus(
        self,
        session_data: Dict[str, Any],
        script: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        kb_id: str,
        message_callback: Optional[Callable]
    ):
        """阶段3：共识达成"""
        
        await self._send_message(session_data, {
            "type": "phase_start",
            "phase": "consensus",
            "content": "【阶段三：共识达成】仲裁主席正在综合各方意见..."
        }, message_callback)
        
        # 主席综合意见
        context = {"agent_results": session_data["agent_results"]}
        final_report = await self.moderator.audit(
            script,
            conversation_history,
            kb_id,
            context
        )
        
        session_data["final_report"] = final_report
        session_data["messages"].append(final_report)
        
        # 发送最终报告
        await self._send_message(session_data, {
            "type": "final_report",
            **final_report
        }, message_callback)
        
        await self._send_message(session_data, {
            "type": "session_complete",
            "content": "审核会议结束，感谢各位专家的参与！"
        }, message_callback)
    
    def _extract_modification_suggestions(self, session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据智能体结果生成结构化修改建议"""
        suggestions: List[Dict[str, Any]] = []
        agent_results = session_data.get("agent_results", {})
        session_id = session_data.get("session_id", "session")
        counter = 1
        seen_descriptions = set()
        
        for agent_id, result in agent_results.items():
            agent_name = result.get("agent_name", agent_id)
            details = result.get("details", {}) or {}
            issues = result.get("issues", []) or []
            evidence_list = result.get("evidence", []) or []
            
            if agent_id == "requirement_analyst":
                for req in details.get("missing_requirements", []) or []:
                    description = f"未覆盖用户需求：{req}"
                    if description in seen_descriptions:
                        continue
                    suggestions.append({
                        "suggestion_id": f"{session_id}-SUG-{counter}",
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "issue_type": "missing_requirement",
                        "severity": "high",
                        "description": description,
                        "suggested_action": f"在脚本中新增或强化关于“{req}”的内容，确保满足该需求。",
                        "evidence": [req]
                    })
                    seen_descriptions.add(description)
                    counter += 1
            
            if agent_id == "knowledge_validator":
                for fact in details.get("inconsistent_facts", []) or []:
                    trimmed = fact[:80] + ("..." if len(fact) > 80 else "")
                    description = f"知识点与知识库不一致：{trimmed}"
                    if description in seen_descriptions:
                        continue
                    suggestions.append({
                        "suggestion_id": f"{session_id}-SUG-{counter}",
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "issue_type": "knowledge_inconsistency",
                        "severity": "high",
                        "description": description,
                        "suggested_action": "修正该知识点的描述，确保与知识库事实一致。",
                        "evidence": [fact]
                    })
                    seen_descriptions.add(description)
                    counter += 1
            
            for issue in issues:
                if issue in seen_descriptions:
                    continue
                suggestions.append({
                    "suggestion_id": f"{session_id}-SUG-{counter}",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "issue_type": "general_issue",
                    "severity": "medium",
                    "description": issue,
                    "suggested_action": "根据该审核问题调整对应脚本段落。",
                    "evidence": evidence_list
                })
                seen_descriptions.add(issue)
                counter += 1
        
        return suggestions

    async def _send_message(
        self,
        session_data: Dict[str, Any],
        message: Dict[str, Any],
        callback: Optional[Callable],
        delay: float = 0.5  # 默认每条消息间隔0.5秒
    ):
        """发送消息（通过WebSocket或其他方式）"""
        import time
        start_time = time.time()
        
        if callback:
            print(f"[_send_message] 准备发送消息: {message.get('type')}, delay={delay}秒")
            await callback(message)
            print(f"[_send_message] 消息已发送: {message.get('type')}, 开始等待{delay}秒...")
            # 【关键】发送后等待，让前端有时间渲染
            await asyncio.sleep(delay)
            print(f"[_send_message] 等待完成: {message.get('type')}, 实际耗时={(time.time() - start_time):.2f}秒")
        
        # 同时保存到会话记录
        if "messages" in session_data:
            session_data["messages"].append(message)
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取审核会话数据"""
        return self.audit_sessions.get(session_id)
    
    def get_final_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取最终审核报告"""
        session = self.audit_sessions.get(session_id)
        if session:
            return {
                "session_id": session_id,
                "script_id": session["script_id"],
                "start_time": session["start_time"],
                "end_time": session["end_time"],
                "status": session["status"],
                "messages": session["messages"],
                "final_report": session["final_report"]
            }
        return None
    
    def get_modification_suggestions(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取指定会话的修改建议"""
        session = self.get_session(session_id)
        if not session:
            return None
        if session.get("modification_suggestions") is None:
            session["modification_suggestions"] = self._extract_modification_suggestions(session)
        return session.get("modification_suggestions")


# 全局实例
multi_agent_audit_service = MultiAgentAuditService()
