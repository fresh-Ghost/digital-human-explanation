export interface ScriptNode {
  seq_id: number;
  type: string;
  url: string;
  voice_text: string;
  voice_id?: string;
  duration_ms: number;
  hotspots?: any[];
  rag_tags: string[];
}

export interface ScriptMeta {
  title: string;
  target_audience: string;
  estimated_duration: number;
}

export interface Script {
  id: string;
  meta: ScriptMeta;
  timeline: ScriptNode[];
}

export interface CuratorRequest {
  message: string;
  audience: string;
  duration_minutes: number;
  focus: string;
  history?: { role: string; content: string }[];
  knowledge_base_id?: string;
}

export interface CuratorResponse {
  reply: string;
  audio_url?: string;
}

export interface Voice {
  id: string;
  name: string;
  gender: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  collection_name?: string;
  total_documents?: number | string;
  uploaded_files?: any[];
  is_active: boolean;
  created_at?: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  audio_url?: string;
  timestamp: number;
}

export type PlayerState = 'idle' | 'playing' | 'paused' | 'loading' | 'error';

export interface PlayerStateData {
  state: PlayerState;
  currentPageIndex: number;
  script: Script | null;
  audioElement: HTMLAudioElement | null;
  isPlaying: boolean;
  progress: number;
}

// 审核相关类型
export interface RequirementCoverage {
  matched: string[];
  missing: string[];
}

export interface KnowledgeConsistency {
  verified_facts: number;
  verified_facts_list: string[];  // 验证通过的事实列表
  inconsistent_facts: string[];
}

export interface DurationCheck {
  expected_minutes: number;
  actual_minutes: number;
  deviation_percent: number;
}

export interface AuditReport {
  script_id: string;
  audit_time: string;
  overall_score: number;
  requirement_coverage: RequirementCoverage;
  knowledge_consistency: KnowledgeConsistency;
  duration_check: DurationCheck;
  issues: string[];
  suggestions: string[];
}

export interface AuditRequest {
  script_id: string;
  conversation_history: { role: string; content: string }[];
  knowledge_base_id: string;
}
