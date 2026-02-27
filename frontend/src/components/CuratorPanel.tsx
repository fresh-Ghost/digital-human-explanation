import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { api } from '../api';
import { usePlayerStore } from '../store/playerStore';
import { Voice, KnowledgeBase, ChatMessage, AuditReport } from '../types';
import { FaMicrophone, FaStop, FaMagic, FaCommentDots, FaTrash, FaClipboardCheck, FaChevronDown, FaUsers, FaClock, FaVolumeUp, FaDatabase } from 'react-icons/fa';
import { encodeWAV } from '../utils/wavEncoder';
import { AuditReportComponent } from './AuditReport';
import MultiAgentAudit from './audit/MultiAgentAudit';
import './CuratorPanel.css';

// 自定义下拉选择组件
interface CustomSelectProps {
  label: string;
  icon: React.ReactNode;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}

function CustomSelect({ label, icon, value, onChange, options }: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const selected = options.find(opt => opt.value === value);
    setSelectedLabel(selected?.label || '');
  }, [value, options]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (optValue: string, optLabel: string) => {
    onChange(optValue);
    setSelectedLabel(optLabel);
    setIsOpen(false);
  };

  return (
    <div className="form-group custom-select-group" ref={containerRef}>
      <label>{icon && <span className="field-icon">{icon}</span>} {label}</label>
      <div 
        className={`custom-select-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="custom-select-value">{selectedLabel}</span>
        <FaChevronDown className={`custom-select-arrow ${isOpen ? 'open' : ''}`} />
      </div>
      {isOpen && (
        <div className="custom-select-dropdown">
          {options.map((opt) => (
            <div
              key={opt.value}
              className={`custom-select-option ${opt.value === value ? 'selected' : ''}`}
              onClick={() => handleSelect(opt.value, opt.label)}
            >
              {opt.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CuratorPanel() {
  const [audience, setAudience] = useState('技术经理');
  const [duration, setDuration] = useState(5);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [voiceId, setVoiceId] = useState('zh-CN-YunxiNeural');
  const [voices, setVoices] = useState<Voice[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  
  const [auditReport, setAuditReport] = useState<AuditReport | null>(null);
  const [isAuditing, setIsAuditing] = useState(false);
  const [currentScriptId, setCurrentScriptId] = useState<string | null>(null);
  const [showMultiAgentAudit, setShowMultiAgentAudit] = useState(false);
  
  const [isRecording, setIsRecording] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const samplesRef = useRef<Float32Array[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const setScript = usePlayerStore((state) => state.setScript);

  // 添加消息并滚动到底部
  const addMessage = (newMessage: ChatMessage | ChatMessage[]) => {
    setMessages(prev => {
      const messages = Array.isArray(newMessage) ? [...prev, ...newMessage] : [...prev, newMessage];
      // 使用 setTimeout 确保 DOM 更新后再滚动
      setTimeout(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 0);
      return messages;
    });
  };

  useEffect(() => {
    console.log('[CuratorPanel] currentScriptId changed:', currentScriptId);
  }, [currentScriptId]);

  useEffect(() => {
    loadVoices();
    loadKnowledgeBases();
    initializeGreeting();
  }, []);

  const initializeGreeting = () => {
    if (messages.length === 0) {
      const greetingMsg: ChatMessage = {
        role: 'assistant',
        content: '您好！我是您的策展助手。请告诉我，您这次讲解的目标受众是谁？想要重点介绍哪些方面？',
        timestamp: Date.now()
      };
      setMessages([greetingMsg]);
    }
  };

  const loadVoices = async () => {
    try {
      const response = await api.getVoicesList();
      setVoices(response.data.voices || []);
    } catch (error) {
      console.error('加载语音列表失败:', error);
    }
  };

  const loadKnowledgeBases = async () => {
    try {
      const response = await api.getKnowledgeBasesList();
      setKnowledgeBases(response.data.knowledge_bases || []);
    } catch (error) {
      console.error('加载知识库列表失败:', error);
    }
  };

  const handleSwitchKnowledgeBase = async (kbId: string) => {
    try {
      const response = await api.switchKnowledgeBase(kbId);
      const { total_documents } = response.data;
      
      // 更新本地知识库列表，将新激活的知识库文档数更新
      setKnowledgeBases(prev => prev.map(kb => ({
        ...kb,
        is_active: kb.id === kbId,
        total_documents: kb.id === kbId ? (total_documents || 0) : kb.total_documents
      })));
    } catch (error) {
      console.error('切换知识库失败:', error);
      alert('切换知识库失败，请重试');
    }
  };

  const handleChat = async () => {
    if (!message.trim()) return;
    
    const userMsg: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: Date.now()
    };
    
    addMessage(userMsg);
    setMessage('');
    setLoading(true);
    
    const activeKb = knowledgeBases.find(kb => kb.is_active);
    const currentKbId = activeKb?.id || 'default';

    try {
      const response = await api.curatorChat({
        message: userMsg.content,
        audience,
        duration_minutes: duration,
        focus: 'business',
        history: messages.map(m => ({ role: m.role, content: m.content })),
        knowledge_base_id: currentKbId
      });
      
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: response.data.reply,
        audio_url: response.data.audio_url,
        timestamp: Date.now()
      };
      
      addMessage(assistantMsg);
      
      if (response.data.audio_url) {
        playResponseAudio(response.data.audio_url);
      }
    } catch (error) {
      console.error('策展对话失败:', error);
      const errorMsg: ChatMessage = {
        role: 'assistant',
        content: '抱歉，对话发生错误，请重试。',
        timestamp: Date.now()
      };
      addMessage(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const playResponseAudio = (url: string) => {
    const fullUrl = url.startsWith('http') ? url : `http://localhost:8000${url}`;
    
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.src = fullUrl;
    } else {
      const audio = new Audio(fullUrl);
      audioPlayerRef.current = audio;
    }

    audioPlayerRef.current.onplay = () => setIsPlayingAudio(true);
    audioPlayerRef.current.onended = () => setIsPlayingAudio(false);
    audioPlayerRef.current.onpause = () => setIsPlayingAudio(false);
    
    audioPlayerRef.current.play().catch(e => {
      console.error('播放音频失败:', e);
      setIsPlayingAudio(false);
    });
  };

  const stopPlayback = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      setIsPlayingAudio(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      samplesRef.current = [];

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        samplesRef.current.push(new Float32Array(inputData));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      setIsRecording(true);
    } catch (error) {
      console.error('无法访问麦克风:', error);
      alert('请允许访问麦克风以使用语音功能');
    }
  };

  const stopRecording = () => {
    if (processorRef.current && isRecording) {
      processorRef.current.disconnect();
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }

      const totalLength = samplesRef.current.reduce((acc, curr) => acc + curr.length, 0);
      const mergedSamples = new Float32Array(totalLength);
      let offset = 0;
      for (const samples of samplesRef.current) {
        mergedSamples.set(samples, offset);
        offset += samples.length;
      }

      const audioBlob = encodeWAV(mergedSamples, 16000);
      handleVoiceChat(audioBlob);
      setIsRecording(false);
    }
  };

  const handleVoiceChat = async (audioBlob: Blob) => {
    const activeKb = knowledgeBases.find(kb => kb.is_active);
    const currentKbId = activeKb?.id || 'default';

    setLoading(true);
    try {
      const response = await api.curatorVoiceChat(
        audioBlob, 
        audience, 
        duration, 
        voiceId,
        messages.map(m => ({ role: m.role, content: m.content })),
        currentKbId
      );
      
      const replyParts = response.data.reply.split('\n');
      const userPart = replyParts[0].match(/\[你听起来在说：(.+?)\]/);
      const userText = userPart ? userPart[1] : '语音输入';
      const assistantText = userPart ? replyParts.slice(1).join('\n') : response.data.reply;

      const userMsg: ChatMessage = {
        role: 'user',
        content: userText,
        timestamp: Date.now()
      };
      
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: assistantText,
        audio_url: response.data.audio_url,
        timestamp: Date.now()
      };
      
      addMessage([userMsg, assistantMsg]);
      
      if (response.data.audio_url) {
        playResponseAudio(response.data.audio_url);
      }
    } catch (error) {
      console.error('语音对话失败:', error);
      const errorMsg: ChatMessage = {
        role: 'assistant',
        content: '语音识别或对话失败，请重试。',
        timestamp: Date.now()
      };
      addMessage(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = () => {
    if (window.confirm('确定要清空对话历史吗？')) {
      setMessages([]);
    }
  };

  const handleGenerateScript = async () => {
    if (messages.length === 0) {
      alert('请先通过对话描述您的需求。');
      return;
    }

    setLoading(true);
    try {
      const historyText = messages
        .map(m => `${m.role === 'user' ? '用户' : '策划师'}: ${m.content}`)
        .join('\n');

      const activeKb = knowledgeBases.find(kb => kb.is_active);
      const currentKbId = activeKb?.id || 'default';
      
      const response = await api.generateScript({
        audience,
        durationMinutes: duration,
        requirement: historyText,
        voiceId: voiceId,
        knowledgeBaseId: currentKbId,
      });
      setScript(response.data);
      
      setCurrentScriptId(response.data.id);
      
      const successMsg: ChatMessage = {
        role: 'assistant',
        content: `脚本生成完毕！内容已加载至右侧播放器（共 ${response.data.timeline.length} 个讲解节点）。点击下方"审核脚本"按钮可查看质量报告。`,
        timestamp: Date.now()
      };
      addMessage(successMsg);
    } catch (error) {
      console.error('生成脚本失败:', error);
      alert('生成脚本失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleAuditScript = async () => {
    if (!currentScriptId) {
      alert('请先生成脚本！');
      return;
    }

    setIsAuditing(true);
    try {
      const activeKb = knowledgeBases.find(kb => kb.is_active);
      const currentKbId = activeKb?.id || 'default';

      const response = await api.auditScript(currentScriptId, {
        script_id: currentScriptId,
        conversation_history: messages.map(m => ({ role: m.role, content: m.content })),
        knowledge_base_id: currentKbId,
      });

      setAuditReport(response.data);
      
      const auditMsg: ChatMessage = {
        role: 'assistant',
        content: `审核完成！总分：${response.data.overall_score}/100。${response.data.overall_score >= 80 ? '脚本质量良好！' : '建议查看详细报告并进行优化。'}`,
        timestamp: Date.now()
      };
      addMessage(auditMsg);
    } catch (error) {
      console.error('审核失败:', error);
      alert('审核失败，请重试');
    } finally {
      setIsAuditing(false);
    }
  };

  return (
    <div className="curator-panel">
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner">
            <div className="spinner-ring"></div>
            <p>处理中...</p>
          </div>
        </div>
      )}
      
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="icon icon-curator" /> 策展配置
        </h2>
      </div>
      
      <div className="form-grid">
        <CustomSelect
          label="目标受众"
          icon={<FaUsers />}
          value={audience}
          onChange={setAudience}
          options={[
            { value: '技术经理', label: '技术经理' },
            { value: '产品经理', label: '产品经理' },
            { value: '投资人', label: '投资人' },
            { value: '普通客户', label: '普通客户' }
          ]}
        />

        <div className="form-group">
          <label><FaClock className="field-icon" /> 讲解时长（分钟）</label>
          <input
            type="number"
            min="1"
            max="30"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
          />
        </div>

        <CustomSelect
          label="语音选择"
          icon={<FaVolumeUp />}
          value={voiceId}
          onChange={setVoiceId}
          options={voices.length > 0 ? voices.map(v => ({ value: v.id, label: v.name })) : [{ value: 'zh-CN-YunxiNeural', label: '云希(男声-沉稳)' }]}
        />

        <CustomSelect
          label="知识库选择"
          icon={<FaDatabase />}
          value={knowledgeBases.find(kb => kb.is_active)?.id || 'default'}
          onChange={handleSwitchKnowledgeBase}
          options={knowledgeBases.map(kb => ({
            value: kb.id,
            label: `${kb.name} (${typeof kb.total_documents === 'number' ? kb.total_documents : kb.total_documents === '未加载' ? '未加载' : 0} 个分块)`
          }))}
        />
      </div>
      
      <div className="kb-hint">
        <span className="kb-tip-icon">i</span>
        <span className="kb-tip-text">切换知识库后，生成的脚本将使用该知识库的内容</span>
      </div>

      <div className="form-group chat-section">
        <label>策展需求对话</label>
        <div className="chat-history">
          {messages.length === 0 ? (
            <div className="chat-empty">
              <p>请通过语音或文字描述您的讲解需求，我会为您提供策展建议。</p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`chat-bubble ${msg.role}`}>
                <div className="bubble-content">{msg.content}</div>
                {msg.audio_url && (
                  <button className="play-mini-btn" onClick={() => playResponseAudio(msg.audio_url!)}>
                    <FaMicrophone size={12} />
                  </button>
                )}
              </div>
            ))
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      <div className="chat-input-area">
        <textarea
          placeholder="描述您的讲解需求，或按住下方麦克风..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleChat();
            }
          }}
          rows={2}
        />
        <button className="clear-btn" onClick={handleClearHistory} title="清空对话">
          <FaTrash size={14} />
        </button>
      </div>

      <div className="button-group">
        <button 
          onClick={handleChat} 
          disabled={loading || !message.trim()}
          className="chat-btn"
        >
          <FaCommentDots size={14} /> {loading ? '对话中...' : '发送'}
        </button>

        <button 
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onTouchStart={startRecording}
          onTouchEnd={stopRecording}
          disabled={loading}
          className={`voice-btn ${isRecording ? 'recording' : ''}`}
          title="按住说话"
        >
          {isRecording ? <FaStop size={14} /> : <FaMicrophone size={14} />}
          {isRecording ? ' 正在聆听...' : ' 按住说话'}
        </button>

        {isPlayingAudio && (
          <button onClick={stopPlayback} className="stop-btn" title="停止播放语音">
            <FaStop size={14} /> 停止播放
          </button>
        )}

        <button 
          onClick={handleGenerateScript} 
          disabled={loading || messages.length === 0}
          className="generate-btn highlight"
        >
          <FaMagic size={14} /> {loading ? '生成中...' : '确认需求并生成脚本'}
        </button>

        {currentScriptId ? (
          <div className="audit-buttons-group">
            <button 
              onClick={handleAuditScript} 
              disabled={isAuditing}
              className="audit-btn"
              title="单智能体审核（快速）"
            >
              <FaClipboardCheck size={14} /> {isAuditing ? '审核中...' : '单智能体审核'}
            </button>
            <button 
              onClick={() => setShowMultiAgentAudit(true)} 
              className="multi-agent-audit-btn"
              title="多智能体审核（详细）"
            >
              <span className="icon icon-runtime" /> 多智能体审核
            </button>
          </div>
        ) : (
          <div className="audit-hint">
            <span className="info-icon">i</span> 生成脚本后可使用审核功能
          </div>
        )}
      </div>

      <audio ref={audioPlayerRef} style={{ display: 'none' }} />
      
      {auditReport && createPortal(
        <AuditReportComponent 
          report={auditReport} 
          onClose={() => setAuditReport(null)} 
        />,
        document.body
      )}
      
      {showMultiAgentAudit && currentScriptId && createPortal(
        <div className="multi-agent-audit-overlay" onClick={(e) => {
          if (e.target === e.currentTarget) {
            setShowMultiAgentAudit(false);
          }
        }}>
          <div className="multi-agent-audit-modal">
            <div className="modal-header">
              <h2><span className="icon icon-runtime" /> 多智能体审核</h2>
              <button 
                className="close-btn" 
                onClick={() => setShowMultiAgentAudit(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-content">
              <MultiAgentAudit
                scriptId={currentScriptId}
                conversationHistory={messages.map(m => ({ role: m.role, content: m.content }))}
                knowledgeBaseId={knowledgeBases.find(kb => kb.is_active)?.id || 'default'}
                onComplete={(report) => {
                  console.log('审核完成:', report);
                  if (report.type === 'version_confirmed' && report.script) {
                    console.log('[前端] 用户选择使用新版本脚本:', report.script);
                    setScript(report.script);
                    setCurrentScriptId(report.script.id);
                    const confirmMsg: ChatMessage = {
                      role: 'assistant',
                      content: `已应用新版本脚本（v${report.script._version || 'N/A'}），播放器内容已更新！`,
                      timestamp: Date.now()
                    };
                    addMessage(confirmMsg);
                  } else {
                    const auditMsg: ChatMessage = {
                      role: 'assistant',
                      content: `多智能体审核完成！综合评分：${report.score}/100。${report.score >= 85 ? '脚本质量优秀！' : report.score >= 70 ? '脚本质量良好。' : '建议根据专家意见优化。'}`,
                      timestamp: Date.now()
                    };
                    addMessage(auditMsg);
                  }
                }}
              />
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
