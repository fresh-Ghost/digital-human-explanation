/**
 * 多智能体审核主组件 - 聊天室风格
 */
import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { FaUsers, FaRocket, FaTools, FaComments, FaScroll, FaSpinner, FaChartBar, FaCheckCircle, FaTimesCircle, FaExclamationTriangle, FaSync, FaCheck, FaReply, FaTimes, FaLightbulb } from 'react-icons/fa';
import './MultiAgentAudit.css';

interface Message {
  type: string;
  agent_id?: string;
  agent_name?: string;
  emoji?: string;
  content?: string;
  score?: number;
  phase?: string;
  timestamp?: string;
  // 新增：详细信息
  details?: {
    matched_requirements?: string[];  // 已覆盖的需求
    missing_requirements?: string[];  // 未覆盖的需求
    total_requirements?: number;
    coverage_rate?: number;
    verified_facts?: string[];  // 已验证的知识点
    inconsistent_facts?: string[];  // 不一致的知识点
    total_facts?: number;
    accuracy_rate?: number;
  };
  evidence?: string[];  // 证据列表
  issues?: string[];  // 问题列表
}

interface ModificationSuggestion {
  suggestion_id: string;
  agent_id: string;
  agent_name: string;
  issue_type: string;
  severity: string;
  description: string;
  suggested_action: string;
  evidence: string[];
}

interface ScriptChange {
  node_id: number;
  change_type: string;
  old_text?: string;
  new_text?: string;
  reason?: string;
}

interface ApplyModificationResult {
  script_id: string;
  version: number;
  summary: string;
  changes: ScriptChange[];
  new_script: {
    id: string;
    meta: {
      title: string;
      target_audience: string;
      estimated_duration: number;
    };
    timeline: Array<{
      seq_id: number;
      voice_text: string;
      [key: string]: any;
    }>;
  };
}

interface Props {
  scriptId: string;
  conversationHistory: any[];
  knowledgeBaseId: string;
  onComplete?: (report: any) => void;
}

export default function MultiAgentAudit({
  scriptId,
  conversationHistory,
  knowledgeBaseId,
  onComplete
}: Props) {
  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [suggestions, setSuggestions] = useState<ModificationSuggestion[]>([]);
  const [selectedSuggestionIds, setSelectedSuggestionIds] = useState<string[]>([]);
  const [isSuggestionModalOpen, setIsSuggestionModalOpen] = useState(false);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<ApplyModificationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [isConfirmingVersion, setIsConfirmingVersion] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // 启动审核
  const startAudit = async () => {
    try {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsRunning(true);
      setMessages([]);
      setSuggestions([]);
      setSelectedSuggestionIds([]);
      setApplyResult(null);
      setErrorMessage('');
      console.log('[前端] 开始启动审核...');
      
      const response = await axios.post(`/api/v1/audit/multi-agent/${scriptId}`, {
        conversation_history: conversationHistory,
        knowledge_base_id: knowledgeBaseId
      });
      
      const sid = response.data.session_id;
      setSessionId(sid);
      console.log('[前端] 会话已创建:', sid);
      
      // 连接WebSocket
      connectWebSocket(sid);
    } catch (error) {
      console.error('[前端] 启动审核失败:', error);
      alert('启动审核失败，请重试');
      setIsRunning(false);
    }
  };

  // 连接WebSocket
  const connectWebSocket = (sid: string) => {
    console.log('[前端] 正在连接WebSocket...');
    const ws = new WebSocket(`ws://localhost:8000/api/v1/audit/ws/multi-agent/${sid}`);
    
    ws.onopen = () => {
      console.log('[前端] WebSocket已连接');
    };
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('[前端] 收到消息:', message.type, message);
      handleMessage(message);
    };
    
    ws.onerror = (error) => {
      console.error('[前端] WebSocket错误:', error);
    };
    
    ws.onclose = () => {
      console.log('[前端] WebSocket已断开');
      setIsRunning(false);
    };
    
    wsRef.current = ws;
  };

  // 处理消息
  const handleMessage = (message: Message) => {
    setMessages(prev => {
      console.log('[前端] 添加消息到列表, 当前消息数:', prev.length + 1);
      return [...prev, message];
    });
    
    if (message.type === 'session_complete') {
      setIsRunning(false);
    }
    
    if (message.type === 'final_report' && onComplete) {
      onComplete(message);
    }
  };

  const fetchSuggestions = async (sid: string) => {
    setIsLoadingSuggestions(true);
    setErrorMessage('');
    try {
      const resp = await axios.get(`/api/v1/audit/multi-agent/${sid}/suggestions`);
      const list: ModificationSuggestion[] = resp.data?.suggestions || [];
      setSuggestions(list);
      setSelectedSuggestionIds(list.map(item => item.suggestion_id));
    } catch (error) {
      console.error('[前端] 获取修改建议失败', error);
      setErrorMessage('获取修改建议失败，请稍后重试');
    } finally {
      setIsLoadingSuggestions(false);
    }
  };

  const openSuggestionModal = async () => {
    if (!sessionId) return;
    setIsSuggestionModalOpen(true);
    if (suggestions.length === 0) {
      await fetchSuggestions(sessionId);
    }
  };

  const closeSuggestionModal = () => {
    setIsSuggestionModalOpen(false);
  };

  const toggleSuggestion = (id: string) => {
    setSelectedSuggestionIds(prev => {
      if (prev.includes(id)) {
        return prev.filter(item => item !== id);
      }
      return [...prev, id];
    });
  };

  const handleApplyModifications = async () => {
    if (!sessionId) {
      setErrorMessage('尚未完成审核，无法应用修改');
      return;
    }
    if (suggestions.length > 0 && selectedSuggestionIds.length === 0) {
      setErrorMessage('请选择至少一条需要修复的问题');
      return;
    }
    setIsApplying(true);
    setErrorMessage('');
    try {
      const payload: any = {};
      if (selectedSuggestionIds.length > 0) {
        payload.selected_suggestions = selectedSuggestionIds;
      } else {
        payload.regenerate_all = true;
      }
      const resp = await axios.post(`/api/v1/audit/multi-agent/${sessionId}/apply-modifications`, payload);
      setApplyResult(resp.data);
      setIsSuggestionModalOpen(false);
    } catch (error) {
      console.error('[前端] 应用修改失败', error);
      setErrorMessage('应用修改失败，请稍后重试');
    } finally {
      setIsApplying(false);
    }
  };

  const handleConfirmVersion = async (useNewVersion: boolean) => {
    if (!applyResult) return;
    setIsConfirmingVersion(true);
    try {
      if (useNewVersion) {
        // 通知父组件使用新脚本（如需持久化可调用后端接口）
        alert(`已确认使用新版本 v${applyResult.version}，脚本已更新！`);
        if (onComplete) {
          onComplete({ type: 'version_confirmed', script: applyResult.new_script });
        }
      } else {
        alert('已保留原版本脚本。');
      }
      setApplyResult(null);
    } catch (error) {
      console.error('[前端] 确认版本失败', error);
      alert('操作失败，请重试');
    } finally {
      setIsConfirmingVersion(false);
    }
  };

  // 自动滚动到底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 组件卸载时关闭WebSocket
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const isSessionCompleted = messages.some(msg => msg.type === 'session_complete');

  return (
    <div className="chat-room">
      {/* 头部 */}
      <div className="chat-header">
        <h2><FaUsers className="header-icon" /> 多智能体审核会议室</h2>
        {!isRunning && messages.length === 0 && (
          <button className="start-btn" onClick={startAudit}>
            <FaRocket /> 开始会议
          </button>
        )}
        {isRunning && (
          <span className="status-badge running">🟢 会议进行中</span>
        )}
      </div>

      {isSessionCompleted && (
        <div className="audit-actions">
          <button className="primary" onClick={openSuggestionModal}>
            <FaTools /> 查看并应用修改建议
          </button>
          <button className="secondary" onClick={startAudit} disabled={isRunning}>
            <FaSync /> 重新发起审核
          </button>
        </div>
      )}

      {/* 消息区域 */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p><FaComments /> 点击"开始会议"，启动多智能体审核讨论</p>
            <p className="hint">智能体将逐个发言，实时讨论脚本质量</p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.type}`}>
            {/* 系统消息（脚本预览） */}
            {msg.type === 'script_preview' && (
              <div className="system-message">
                <strong><FaScroll /> 待审核脚本</strong>
                <pre>{msg.content}</pre>
              </div>
            )}
            
            {/* 主席发言 */}
            {msg.type === 'moderator_speak' && (
              <div className="moderator-bubble">
                <div className="bubble-header">
                  <span className="avatar">{msg.emoji}</span>
                  <span className="name">{msg.agent_name}</span>
                </div>
                <div className="bubble-content">{msg.content}</div>
              </div>
            )}
            
            {/* 智能体正在输入 */}
            {msg.type === 'agent_typing' && (
              <div className="typing-indicator">
                <span className="avatar">{msg.emoji}</span>
                <span className="text">{msg.content}</span>
                <span className="dots">...</span>
              </div>
            )}
            
            {/* 智能体审核进度 */}
            {msg.type === 'agent_progress' && (
              <div className="progress-indicator">
                <span className="avatar">{msg.emoji}</span>
                <span className="text">{msg.content}</span>
                <span className="spinner"><FaSpinner className="spinning" /></span>
              </div>
            )}
            
            {/* 智能体发言 */}
            {msg.type === 'agent_speak' && (
              <div className="agent-bubble">
                <div className="bubble-header">
                  <span className="avatar">{msg.emoji}</span>
                  <span className="name">{msg.agent_name}</span>
                  <span className="score">评分: {msg.score}/100</span>
                </div>
                <div className="bubble-content">
                  <pre>{msg.content}</pre>
                              
                  {/* 详细信息展开 */}
                  {msg.details && (
                    <details className="audit-details" open>
                      <summary><FaChartBar /> 查看详细匹配明细</summary>
                                  
                      {/* 需求分析师的明细 */}
                      {msg.agent_id === 'requirement_analyst' && msg.details.matched_requirements && (
                        <div className="requirements-details">
                          <h4><FaCheckCircle className="icon-success" /> 已覆盖的需求 ({msg.details.matched_requirements.length}/{msg.details.total_requirements})</h4>
                          <ul className="matched-list">
                            {msg.details.matched_requirements.map((req, i) => (
                              <li key={i}><FaCheckCircle className="icon-success" /> {req}</li>
                            ))}
                          </ul>
                                      
                          {msg.details.missing_requirements && msg.details.missing_requirements.length > 0 && (
                            <>
                              <h4><FaTimesCircle className="icon-error" /> 未覆盖的需求 ({msg.details.missing_requirements.length}/{msg.details.total_requirements})</h4>
                              <ul className="missing-list">
                                {msg.details.missing_requirements.map((req, i) => (
                                  <li key={i}><FaTimesCircle className="icon-error" /> {req}</li>
                                ))}
                              </ul>
                            </>
                          )}
                        </div>
                      )}
                                  
                      {/* 知识审查官的明细 */}
                      {msg.agent_id === 'knowledge_validator' && msg.details.verified_facts && (
                        <div className="knowledge-details">
                          <h4><FaCheckCircle className="icon-success" /> 已验证的知识点 ({msg.details.verified_facts.length}/{msg.details.total_facts})</h4>
                          <ul className="verified-list">
                            {msg.details.verified_facts.map((fact, i) => (
                              <li key={i}><FaCheckCircle className="icon-success" /> {fact.length > 80 ? fact.substring(0, 80) + '...' : fact}</li>
                            ))}
                          </ul>
                                      
                          {msg.details.inconsistent_facts && msg.details.inconsistent_facts.length > 0 && (
                            <>
                              <h4><FaExclamationTriangle className="icon-warning" /> 不一致的知识点 ({msg.details.inconsistent_facts.length}/{msg.details.total_facts})</h4>
                              <ul className="inconsistent-list">
                                {msg.details.inconsistent_facts.map((fact, i) => (
                                  <li key={i}><FaExclamationTriangle className="icon-warning" /> {fact.length > 80 ? fact.substring(0, 80) + '...' : fact}</li>
                                ))}
                              </ul>
                            </>
                          )}
                        </div>
                      )}
                    </details>
                  )}
                </div>
              </div>
            )}
            
            {/* 辩论消息 */}
            {msg.type === 'agent_debate' && (
              <div className="debate-bubble">
                <div className="bubble-header">
                  <span className="avatar">{msg.emoji}</span>
                  <span className="name">{msg.agent_name}</span>
                  <span className="badge"><FaComments className="badge-icon" /> 辩论</span>
                </div>
                <div className="bubble-content">
                  <pre>{msg.content}</pre>
                </div>
              </div>
            )}
            
            {/* 最终报告 */}
            {msg.type === 'final_report' && (
              <div className="final-report">
                <div className="report-header">
                  <span className="avatar">{msg.emoji}</span>
                  <span className="name">{msg.agent_name}</span>
                  <span className="badge"><FaCheckCircle className="badge-icon" /> 最终报告</span>
                </div>
                <div className="report-content">
                  <pre>{msg.content}</pre>
                </div>
              </div>
            )}
            
            {/* 会议结束 */}
            {msg.type === 'session_complete' && (
              <div className="session-end">
                <FaCheckCircle className="icon-success" /> {msg.content || '会议结束'}
              </div>
            )}
          </div>
        ))}
        
        <div ref={chatEndRef} />
      </div>


      
      {applyResult && (
        <div className="apply-result-panel">
          <div className="panel-header">
            <h3><FaCheck className="icon-success" /> 新脚本版本 v{applyResult.version}</h3>
            <span>{applyResult.summary}</span>
          </div>
          <div className="result-content">
            {applyResult.changes.length === 0 ? (
              <p className="no-changes">本次脚本内容未发生可见变动。</p>
            ) : (
              <ul className="change-list">
                {applyResult.changes.map(change => (
                  <li key={change.node_id} className={`change-item change-${change.change_type}`}>
                    <div className="change-title">
                      <span>节点 {change.node_id}</span>
                      <span className="badge">{change.change_type}</span>
                    </div>
                    <div className="change-body">
                      {change.old_text && (
                        <div>
                          <h5>旧内容</h5>
                          <pre>{change.old_text}</pre>
                        </div>
                      )}
                      {change.new_text && (
                        <div>
                          <h5>新内容</h5>
                          <pre>{change.new_text}</pre>
                        </div>
                      )}
                    </div>
                    {change.reason && <p className="change-reason"><FaCheck className="icon-info" /> 原因：{change.reason}</p>}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="version-actions">
            <button
              className="use-new"
              onClick={() => handleConfirmVersion(true)}
              disabled={isConfirmingVersion}
            >
              <FaCheck /> 使用新版本
            </button>
            <button
              className="keep-old"
              onClick={() => handleConfirmVersion(false)}
              disabled={isConfirmingVersion}
            >
              <FaReply /> 保留原版本
            </button>
          </div>
        </div>
      )}

      {/* 底部状态栏 */}
      <div className="chat-footer">
        <span className="message-count">
          {messages.length} 条消息
        </span>
        {isRunning && (
          <span className="status">审核进行中，请耐心等待...</span>
        )}
      </div>
      
      {isSuggestionModalOpen && (
        <div className="suggestion-modal-overlay">
          <div className="suggestion-modal">
            <div className="modal-header">
              <h3><FaTools /> 审核修改建议</h3>
              <button className="close-btn" onClick={closeSuggestionModal}><FaTimes /></button>
            </div>
            {errorMessage && <p className="error-tip">{errorMessage}</p>}
            <div className="modal-body">
              {isLoadingSuggestions ? (
                <div className="loading-state">正在分析审核结果，请稍候...</div>
              ) : (
                <div className="suggestion-list">
                  {suggestions.length === 0 ? (
                    <div className="suggestion-empty">暂无明确问题，可直接生成改进版脚本。</div>
                  ) : (
                    suggestions.map(item => (
                      <label
                        key={item.suggestion_id}
                        className={`suggestion-item severity-${item.severity}`}
                      >
                        <div className="item-header">
                          <input
                            type="checkbox"
                            checked={selectedSuggestionIds.includes(item.suggestion_id)}
                            onChange={() => toggleSuggestion(item.suggestion_id)}
                          />
                          <div>
                            <span className="agent">{item.agent_name}</span>
                            <span className="severity">{item.severity}</span>
                          </div>
                        </div>
                        <p className="description">{item.description}</p>
                        <p className="action"><FaLightbulb className="icon-info" /> 建议：{item.suggested_action}</p>
                        {item.evidence && item.evidence.length > 0 && (
                          <details>
                            <summary><FaScroll /> 查看依据</summary>
                            <ul>
                              {item.evidence.map((ev, idx) => (
                                <li key={idx}>{ev}</li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </label>
                    ))
                  )}
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button
                className="primary"
                onClick={handleApplyModifications}
                disabled={isApplying || (!isLoadingSuggestions && suggestions.length > 0 && selectedSuggestionIds.length === 0)}
              >
                {isApplying ? '应用中...' : '应用修改'}
              </button>
              <button className="secondary" onClick={closeSuggestionModal} disabled={isApplying}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
