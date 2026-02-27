import React, { useState } from 'react';
import { FaChartBar, FaCheckCircle, FaSearch, FaClock, FaExclamationTriangle, FaLightbulb, FaCaretDown, FaCaretRight } from 'react-icons/fa';
import type { AuditReport } from '../types';
import './AuditReport.css';

interface AuditReportProps {
  report: AuditReport | null;
  onClose: () => void;
}

export const AuditReportComponent: React.FC<AuditReportProps> = ({ report, onClose }) => {
  const [showMatchedRequirements, setShowMatchedRequirements] = useState(false);
  const [showVerifiedFacts, setShowVerifiedFacts] = useState(false);
  
  if (!report) return null;

  const getScoreColor = (score: number) => {
    if (score >= 90) return '#4ade80'; // 绿色
    if (score >= 70) return '#fbbf24'; // 黄色
    return '#f87171'; // 红色
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN');
  };

  return (
    <div className="audit-report-overlay">
      <div className="audit-report-container">
        <div className="audit-report-header">
          <h2><FaChartBar className="header-icon" /> 脚本审核报告</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="audit-report-content">
          {/* 总体评分 */}
          <div className="audit-score-section">
            <div className="score-circle" style={{ borderColor: getScoreColor(report.overall_score) }}>
              <span className="score-number" style={{ color: getScoreColor(report.overall_score) }}>
                {report.overall_score}
              </span>
              <span className="score-label">分</span>
            </div>
            <div className="score-info">
              <p className="audit-time">审核时间：{formatTime(report.audit_time)}</p>
              <p className="script-id">脚本 ID：{report.script_id.substring(0, 8)}...</p>
            </div>
          </div>

          {/* 需求覆盖度 */}
          <div className="audit-section">
            <h3><FaCheckCircle className="section-icon success" /> 需求覆盖度</h3>
            <div className="coverage-stats">
              <span className="stat-item matched">
                已满足：{report.requirement_coverage.matched.length} 项
              </span>
              <span className="stat-item missing">
                缺失：{report.requirement_coverage.missing.length} 项
              </span>
            </div>
            
            {/* 已满足的需求（折叠显示） */}
            {report.requirement_coverage.matched.length > 0 && (
              <div className="matched-section">
                <button 
                  className="toggle-btn"
                  onClick={() => setShowMatchedRequirements(!showMatchedRequirements)}
                >
                  {showMatchedRequirements ? <FaCaretDown /> : <FaCaretRight />} 查看已满足的需求 ({report.requirement_coverage.matched.length}项)
                </button>
                {showMatchedRequirements && (
                  <ul className="matched-list">
                    {report.requirement_coverage.matched.map((item, idx) => (
                      <li key={idx} className="matched-item">✓ {item}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            
            {/* 缺失的需求 */}
            {report.requirement_coverage.missing.length > 0 && (
              <div className="missing-list">
                <p className="section-subtitle">缺失需求：</p>
                <ul>
                  {report.requirement_coverage.missing.map((item, idx) => (
                    <li key={idx}>✗ {item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* 知识一致性 */}
          <div className="audit-section">
            <h3><FaSearch className="section-icon" /> 知识一致性</h3>
            <div className="consistency-stats">
              <span className="stat-item verified">
                验证通过：{report.knowledge_consistency.verified_facts} 条
              </span>
              <span className="stat-item inconsistent">
                不一致：{report.knowledge_consistency.inconsistent_facts.length} 条
              </span>
            </div>
            
            {/* 验证通过的事实（折叠显示） */}
            {report.knowledge_consistency.verified_facts_list && report.knowledge_consistency.verified_facts_list.length > 0 && (
              <div className="verified-section">
                <button 
                  className="toggle-btn"
                  onClick={() => setShowVerifiedFacts(!showVerifiedFacts)}
                >
                  {showVerifiedFacts ? <FaCaretDown /> : <FaCaretRight />} 查看验证通过的事实 ({report.knowledge_consistency.verified_facts_list.length}条)
                </button>
                {showVerifiedFacts && (
                  <ul className="verified-list">
                    {report.knowledge_consistency.verified_facts_list.map((fact, idx) => (
                      <li key={idx} className="verified-item">✓ {fact}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            
            {/* 不一致的事实 */}
            {report.knowledge_consistency.inconsistent_facts.length > 0 && (
              <div className="inconsistent-list">
                <p className="section-subtitle">与知识库不一致的内容：</p>
                <ul>
                  {report.knowledge_consistency.inconsistent_facts.map((fact, idx) => (
                    <li key={idx}>✗ {fact}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* 时长检查 */}
          <div className="audit-section">
            <h3><FaClock className="section-icon" /> 时长检查</h3>
            <div className="duration-comparison">
              <div className="duration-item">
                <span className="label">要求时长：</span>
                <span className="value">{report.duration_check.expected_minutes.toFixed(1)} 分钟</span>
              </div>
              <div className="duration-item">
                <span className="label">实际时长：</span>
                <span className="value">{report.duration_check.actual_minutes.toFixed(1)} 分钟</span>
              </div>
              <div className="duration-item">
                <span className="label">偏差：</span>
                <span className={`value ${report.duration_check.deviation_percent > 10 ? 'warning' : 'ok'}`}>
                  {report.duration_check.deviation_percent.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* 问题列表 */}
          {report.issues.length > 0 && (
            <div className="audit-section issues-section">
              <h3><FaExclamationTriangle className="section-icon warning" /> 发现的问题</h3>
              <ul className="issues-list">
                {report.issues.map((issue, idx) => (
                  <li key={idx} className="issue-item">{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 改进建议 */}
          {report.suggestions.length > 0 && (
            <div className="audit-section suggestions-section">
              <h3><FaLightbulb className="section-icon info" /> 改进建议</h3>
              <ul className="suggestions-list">
                {report.suggestions.map((suggestion, idx) => (
                  <li key={idx} className="suggestion-item">{suggestion}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="audit-report-footer">
          <button className="action-btn close" onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  );
};
