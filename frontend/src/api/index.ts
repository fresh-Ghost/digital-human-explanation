import axios from 'axios';
import type { CuratorRequest, CuratorResponse, Script, AuditRequest, AuditReport } from '../types';

const API_BASE = '/api/v1';

export const api = {
  // 健康检查
  health: () => axios.get('/health'),

  // 策展对话
  curatorChat: (data: CuratorRequest) =>
    axios.post<CuratorResponse>(`${API_BASE}/curator/chat`, data),

  // 语音策展对话
  curatorVoiceChat: (audioBlob: Blob, audience: string, duration: number, voiceId: string, history?: {role: string, content: string}[], kbId?: string) => {
    const formData = new FormData();
    // 根据 Blob 的实际类型决定扩展名
    const extension = audioBlob.type.split('/')[1]?.split(';')[0] || 'wav';
    formData.append('file', audioBlob, `curator_voice.${extension}`);
    formData.append('audience', audience);
    formData.append('duration_minutes', duration.toString());
    formData.append('voice_id', voiceId);
    if (history) {
      formData.append('history', JSON.stringify(history));
    }
    if (kbId) {
      formData.append('knowledge_base_id', kbId);
    }
    return axios.post<CuratorResponse>(`${API_BASE}/curator/voice-chat`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // 生成脚本（使用 POST 方法）
  generateScript: (data: { 
    audience: string; 
    durationMinutes: number; 
    requirement?: string;
    voiceId?: string;
    knowledgeBaseId?: string;
  }) =>
    axios.post<Script>(`${API_BASE}/script/generate`, {
      audience: data.audience,
      duration_minutes: data.durationMinutes,
      requirement: data.requirement || '',
      voice_id: data.voiceId || 'zh-CN-YunxiNeural',
      knowledge_base_id: data.knowledgeBaseId || 'default',
    }),

  // 获取 TTS 音频 URL
  getTTSUrl: (text: string, voice: string = 'zh-CN-YunxiNeural') =>
    `${API_BASE}/tts/generate?text=${encodeURIComponent(text)}&voice=${voice}`,

  // 上传文件
  uploadFile: (file: File, kbId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    const url = kbId 
      ? `${API_BASE}/upload?kb_id=${kbId}` 
      : `${API_BASE}/upload`;
    return axios.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // RAG 语义搜索
  ragSearch: (query: string, topK: number = 3) =>
    axios.get(`${API_BASE}/rag/search`, { params: { query, top_k: topK } }),

  // 获取已上传文件列表
  getFilesList: () =>
    axios.get(`${API_BASE}/files/list`),

  // 获取知识库信息
  getKnowledgeBaseInfo: () =>
    axios.get(`${API_BASE}/knowledge-base/info`),

  // 删除文件
  deleteFile: (fileId: string) =>
    axios.delete(`${API_BASE}/files/${fileId}`),

  // 从知识库中删除文档
  deleteDocumentFromKB: (filename: string) =>
    axios.delete(`${API_BASE}/knowledge-base/documents/${encodeURIComponent(filename)}`),

  // 清空知识库
  clearKnowledgeBase: () =>
    axios.delete(`${API_BASE}/knowledge-base/clear`),
  
  // ==== 多知识库管理 ====
  
  // 获取知识库列表
  getKnowledgeBasesList: () =>
    axios.get(`${API_BASE}/knowledge-bases/list`),
  
  // 创建知识库
  createKnowledgeBase: (name: string) =>
    axios.post(`${API_BASE}/knowledge-bases/create`, null, { params: { name } }),
  
  // 切换知识库
  switchKnowledgeBase: (kbId: string) =>
    axios.post(`${API_BASE}/knowledge-bases/switch/${kbId}`),
  
  // 删除知识库
  deleteKnowledgeBase: (kbId: string) =>
    axios.delete(`${API_BASE}/knowledge-bases/${kbId}`),
  
  // 重命名知识库
  renameKnowledgeBase: (kbId: string, newName: string) =>
    axios.put(`${API_BASE}/knowledge-bases/${kbId}/rename`, null, { params: { new_name: newName } }),
  
  // 获取语音列表
  getVoicesList: () =>
    axios.get(`${API_BASE}/voices/list`),
  
  // ==== 审核智能体 ====
  
  // 触发脚本审核
  auditScript: (scriptId: string, data: AuditRequest) =>
    axios.post<AuditReport>(`${API_BASE}/audit/script/${scriptId}`, data),
  
  // 获取审核报告
  getAuditReport: (scriptId: string) =>
    axios.get<AuditReport>(`${API_BASE}/audit/report/${scriptId}`),
};
