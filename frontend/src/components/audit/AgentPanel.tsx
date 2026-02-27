/**
 * 智能体面板组件
 * 显示单个智能体的审核状态和进度
 */
import { useState, useEffect } from 'react';
import { FaPause, FaSpinner, FaCheckCircle, FaTimesCircle } from 'react-icons/fa';
import './AgentPanel.css';

interface AgentPanelProps {
  agentId: string;
  agentName: string;
  emoji: string;
  status: 'waiting' | 'auditing' | 'completed' | 'error';
  score?: number;
  content?: string;
}

export default function AgentPanel({
  agentName,
  emoji,
  status,
  score,
  content
}: AgentPanelProps) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (status === 'auditing') {
      // 模拟进度条动画
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) return prev;
          return prev + Math.random() * 15;
        });
      }, 500);
      return () => clearInterval(interval);
    } else if (status === 'completed') {
      setProgress(100);
    }
  }, [status]);

  const getStatusIcon = () => {
    switch (status) {
      case 'waiting':
        return <FaPause className="status-icon" />;
      case 'auditing':
        return <FaSpinner className="status-icon spinning" />;
      case 'completed':
        return <FaCheckCircle className="status-icon success" />;
      case 'error':
        return <FaTimesCircle className="status-icon error" />;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'waiting':
        return '等待中...';
      case 'auditing':
        return '审核中...';
      case 'completed':
        return `完成 (${score}/100)`;
      case 'error':
        return '审核失败';
    }
  };

  const getScoreColor = () => {
    if (!score) return '';
    if (score >= 85) return '#52c41a';
    if (score >= 70) return '#1890ff';
    if (score >= 60) return '#faad14';
    return '#f5222d';
  };

  return (
    <div className="agent-panel">
      <div className="agent-header">
        <span className="agent-emoji">{emoji}</span>
        <span className="agent-name">{agentName}</span>
        <span className="agent-status-icon">{getStatusIcon()}</span>
      </div>

      <div className="agent-status">
        {getStatusText()}
      </div>

      {status === 'auditing' && (
        <div className="agent-progress">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          <span className="progress-text">{Math.round(progress)}%</span>
        </div>
      )}

      {status === 'completed' && score !== undefined && (
        <div className="agent-score" style={{ color: getScoreColor() }}>
          <div className="score-circle">
            <span className="score-value">{score}</span>
          </div>
        </div>
      )}

      {content && (
        <div className="agent-content">
          {content}
        </div>
      )}
    </div>
  );
}
