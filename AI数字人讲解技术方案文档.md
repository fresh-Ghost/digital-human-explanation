```markdown
# 技术架构方案 (TDD) - 灵境·AI 自适应数字讲解系统
**Lingjing AI Smart Narrator (Lite Edition) - Technical Design Document**

| 属性 | 内容 |
| :--- | :--- |
| **项目名称** | Lingjing-Lite |
| **版本号** | v2.5.0 |
| **日期** | 2025-01-13 |
| **核心技术栈** | React 18, FastAPI, LangChain, ChromaDB, 智谱 AI (GLM-4-Flash/ASR/TTS) |

---

## 1. 系统架构概述 (System Architecture)

本系统采用 **B/S (Browser/Server)** 架构，通过 WebSocket 实现低延迟的语音交互流。

### 1.1 架构图 (Mermaid)

```mermaid
graph TD
    subgraph "Client Side (Browser)"
        UI[React UI Component]
        Player[Player State Machine]
        AudioCtx[Web Audio Context]
        WS_Client[WebSocket Client]
    end

    subgraph "Server Side (Python/FastAPI)"
        WS_Server[WebSocket Endpoint]
        Router[Request Router]
        
        subgraph "AI Core"
            VAD[Voice Activity Detection]
            ASR[ASR Service (FunASR/Aliyun)]
            LLM[LangChain Agent (Qwen/DeepSeek)]
            TTS[TTS Service (EdgeTTS/CosyVoice)]
            RAG[RAG Engine]
        end
        
        subgraph "Data Persistence"
            Chroma[(ChromaDB - Vectors)]
            SQLite[(SQLite - Metadata)]
            FileSys[File Storage]
        end
    end

    UI --> Player
    Player --> AudioCtx
    AudioCtx <--> WS_Client
    WS_Client <--> WS_Server
    WS_Server --> Router
    Router --> VAD
    Router --> ASR
    Router --> LLM
    LLM <--> RAG
    RAG <--> Chroma
    LLM --> TTS

```

---

## 2. 技术栈详细选型 (Tech Stack)

### 2.1 前端 (Frontend)

* **构建工具:** Vite + TypeScript
* **核心框架:** React 18
* **状态管理:** **Zustand** (用于管理复杂的播放器状态机)
* **UI 组件:** 自定义 CSS + React Icons
* **音频处理:** 
  * `Web Audio API`: 录音采样率转换 (48kHz -> 16kHz) 与播放。
  * **原生 WAV 编码器** (`wavEncoder.ts`): 纯 JS 实现 PCM 转标准 WAV。
* **通信:** `Axios` 进行 HTTP 请求，支持 FormData 上传音频文件。



### 2.2 后端 (Backend)

* **Web 框架:** **FastAPI** (Python 3.10+) - 原生支持 Async/Await，处理高并发性能极佳。
* **AI 编排:** **LangChain** - 管理 Prompt Templates、RAG 检索链和 Agent 逻辑。
* **向量数据库:** **ChromaDB** - 轻量级、本地文件存储，无需复杂运维。
* **大语言模型:** **智谱 GLM-4-Flash** - 用于对话生成、RAG 问答和脚本生成。
* **语音服务:** 
  * **ASR**: 智谱 `glm-asr-2512` 或 `whisper-1` (支持多级回退)。
  * **TTS**: 智谱语音合成 API，支持多种音色选择。
* **文档解析:** PyPDF2 / pdfplumber 支持 PDF 提取，支持 TXT/Markdown 直接导入。



---

## 3. 核心模块设计 (Core Modules)

### 3.1 模块 A：知识库管理 (KMS)

**功能:** 将非结构化文档转化为向量索引。

**处理流程:**

1. **Ingestion:** 接收 PDF/TXT/Markdown 文档上传。
2. **Splitting:** 使用 `RecursiveCharacterTextSplitter` 按语义分块 (chunk_size=500, overlap=50)。
3. **Embedding:** 使用智谱 `embedding-3` 模型生成向量。
4. **Storage:** 存入 ChromaDB，Collection 命名为 `lingjing_knowledge_zhipu`。
5. **多知识库支持:** 每个知识库独立存储，命名格式为 `kb_{timestamp}_{name}`。

**已实现功能:**
- 多知识库 CRUD（创建、列表、切换、删除）
- 文档管理（上传、删除、清空）
- 知识来源可见（显示文档来源和 Chunk 数量）
- Windows 文件占用问题优化（自动重试、强制 GC、权限修复）

### 3.2 模块 B：策展 Agent (The Curator)

**功能:** 基于 LangChain 的对话系统，生成讲解脚本。

**System Prompt 核心逻辑:**

```python
system_prompt = f"""
你是灵境公司的专业策展人。你的任务是通过对话收集用户的演示需求（受众、时长、重点）。

基本配置：受众为「{audience}」，讲解时长约 {duration} 分钟。

【核心：你的背景知识库 (KMS)】
你拥有来自知识库「{kb_id}」的权威资料。以下是与用户当前输入最相关的片段：
{context}

行为准则：
1. **严格基于知识库**：你的回答必须体现出你已经“读过”上述背景资料。
2. **禁止虚假追问**：不要问知识库中已经明确给出答案的问题。
3. **上下文感知的追问**：请检查对话历史，严禁重复之前已经问过的问题。
4. **策略总结**：当你认为已经掌握了足够的信息时，请主动总结出一份策展策略摘要。
"""
```

**已实现功能:**
- 多轮对话与历史记忆（前端维护 `messages` 数组并透传给后端）
- 文字与语音双模式对话（ASR + TTS 集成）
- RAG 增强对话（实时检索当前激活知识库）
- 上下文感知 Prompt 优化（避免机械重复追问）
- 对话汇总与脚本生成触发

### 3.3 模块 C：脚本生成引擎 (Script Generator)

**功能:** 基于用户需求和知识库生成 JSON 脚本。

**处理流程:**

1. **需求提取:** 使用大模型从对话历史中提取核心需求，过滤客套话噪音。
2. **RAG 检索:** 基于提取后的需求检索知识库（k=10），获取相关背景资料。
3. **关键词提取:** 从检索结果中提取关键词，用于生成针对性内容。
4. **脚本生成:** 调用 GLM-4-Flash，根据 Prompt 生成符合 JSON Schema 的脚本。
5. **时长计算:** 根据文本长度估算每页 TTS 时长。

**已实现优化:**
- 需求提取环节，减少 RAG 检索噪音
- 脚本生成 Prompt 强化主题聚焦
- 时长匹配度优化（动态计算节点数）

### 3.4 模块 D：语音交互层 (Voice Interaction Layer)

**ASR 流程:**

1. **前端录音:** 使用 `MediaRecorder` + `AudioContext` 实时采样。
2. **WAV 编码:** 调用 `wavEncoder.ts` 将 PCM 数据转为标准 16kHz/16bit 单声道 WAV。
3. **上传识别:** 通过 FormData 上传至后端 `/curator/voice-chat`。
4. **后端 ASR:** 调用智谱 `glm-asr-2512` 或 `whisper-1` 进行语音识别。
5. **多级回退:** 如果主模型失败，自动切换备用模型。

**TTS 流程:**

1. **文本清洗:** 移除 Markdown 符号（`*`, `#`, `-`, `>`）避免朗读干扰。
2. **语音合成:** 调用智谱 TTS API 生成音频文件。
3. **文件存储:** 保存至服务端 `static/audio/` 目录。
4. **URL 返回:** 返回音频文件 URL 给前端播放。
5. **播放控制:** 前端支持手动停止播放。

**功能:** 前端播放器的核心控制逻辑。

| 状态 (State) | 描述 | 触发变迁条件 | 实现状态 |
| --- | --- | --- | --- |
| **IDLE** | 空闲/等待开始 | 用户点击"Start" -> `PLAYING` | ✅ 已实现 |
| **PLAYING** | 播放 TTS 和脚本内容 | 用户点击暂停 -> `PAUSED` | ✅ 已实现 |
| **PAUSED** | 暂停播放 | 用户点击继续 -> `PLAYING` | ✅ 已实现 |
| **NARRATING** | 播放 TTS 和 PPT | VAD 检测到说话 -> `LISTENING` | 📋 待实现 |
| **LISTENING** | 暂停播放，采集录音 | VAD 检测到静音 -> `THINKING` | 📋 待实现 |
| **THINKING** | 等待 AI 生成回答 | 收到 TTS 音频流 -> `ANSWERING` | 📋 待实现 |
| **ANSWERING** | 播放回答音频 | 回答播放完毕 -> `RESUMING` | 📋 待实现 |
| **RESUMING** | 恢复讲解上下文 | 自动/用户确认 -> `NARRATING` | 📋 待实现 |

### 3.5 模块 E：脚本审核智能体 (The Auditor)

**功能:** 自动审核生成的脚本质量，确保内容准确性和需求匹配度。

**设计哲学:**
- 审核智能体与策展 Agent 地位平等，均使用相同的知识库和大模型。
- 采用"三角互验"机制：用户需求 ↔ 生成脚本 ↔ 知识库真实内容。
- 输出结构化审核报告，而非简单的“通过/不通过”。

**审核流程:**

1. **触发机制:**
   - 在脚本生成成功后自动触发，无需人工介入。
   - 接收输入：对话历史、生成脚本 JSON、知识库 ID。

2. **需求匹配度检查:**
   ```python
   # 使用大模型提取用户需求清单
   extract_prompt = f"""
   从以下对话中提取用户明确提出的所有要求：
   {conversation_history}
   
   请返回 JSON 格式：
   {{
     "audience": "目标受众",
     "duration": "时长要求",
     "focus_topics": ["重点主题1", "重点主题2"],
     "special_requirements": ["特殊要求1"]
   }}
   """
   
   # 逐项比对脚本是否满足
   for topic in focus_topics:
       if not any(topic in page["content"] for page in script):
           issues.append(f"未覆盖重点主题：{topic}")
   ```

3. **知识一致性验证:**
   ```python
   # 提取脚本中的关键事实性陈述
   fact_extract_prompt = f"""
   从以下脚本中提取所有事实性陈述（数据、参数、技术指标）：
   {script_content}
   
   返回格式：["陈述1", "陈述2"]
   """
   
   # 逐条在知识库中验证
   for fact in facts:
       kb_docs = vectorstore.similarity_search(fact, k=3)
       if not verify_fact_consistency(fact, kb_docs):
           issues.append(f"与知识库不一致：{fact}")
   ```

4. **时长合理性评估:**
   ```python
   total_duration = sum([page["duration_ms"] for page in script["timeline"]])
   expected_duration = user_duration * 60 * 1000  # 转毫秒
   
   deviation = abs(total_duration - expected_duration) / expected_duration
   if deviation > 0.1:  # 超过 10% 容差
       issues.append(f"时长偏离：实际 {total_duration/1000/60:.1f} 分钟 vs 要求 {user_duration} 分钟")
   ```

5. **生成审核报告:**
   ```python
   audit_report = {
       "script_id": script_id,
       "audit_time": datetime.now().isoformat(),
       "overall_score": calculate_score(issues),  # 0-100 分
       "requirement_coverage": {
           "matched": matched_requirements,
           "missing": missing_requirements
       },
       "knowledge_consistency": {
           "verified_facts": len(facts) - len(inconsistent_facts),
           "inconsistent_facts": inconsistent_facts
       },
       "duration_check": {
           "expected_minutes": user_duration,
           "actual_minutes": total_duration / 60000,
           "deviation_percent": deviation * 100
       },
       "issues": issues,
       "suggestions": generate_suggestions(issues)
   }
   ```

6. **一键修复（选项）:**
   - 如果评分 < 80，提供“重新生成”按钮。
   - 将审核问题列表注入 Prompt，指导大模型修正。

**技术实现细节:**

- **防止循环误判:** 审核智能体和生成智能体使用相同模型，但通过 **temperature=0.1** 降低审核随机性，提高一致性。
- **事实验证准确度:** 采用 **语义相似度阈值 (>0.85)** 而非简单字符串匹配。
- **性能优化:** 审核过程异步执行，不阻塞脚本生成结果返回。

---

## 4. 数据结构规范 (Data Schemas)

### 4.1 讲解脚本 (Script JSON)

这是后端生成、前端执行的"剧本"。

```typescript
// Script Interface
interface PresentationScript {
  id: string;
  meta: {
    title: string;
    target_audience: string;
    estimated_duration: number;
  };
  timeline: ScriptNode[];
}

interface ScriptNode {
  seq_id: number;
  type: 'image' | 'video';
  url: string; // 媒体文件路径
  voice_text: string; // TTS 朗读文本
  voice_id?: string; // 指定音色
  duration_ms: number; // 预估时长
  
  // 视觉高亮指令
  hotspots?: {
    time_offset: number; // 语音播放多少毫秒后触发
    x: number; // 百分比坐标
    y: number;
    width: number;
    height: number;
    style: 'blink' | 'border' | 'pulse';
  }[];
  
  // RAG 上下文标签 (用于提升问答准确率)
  rag_tags: string[]; 
}

```

### 4.2 WebSocket 通信协议

Endpoint: `ws://{host}/ws/runtime/session/{id}`

**Client -> Server (上行):**

```json
// 1. 发送音频数据 (Binary)
<PCM_DATA_16K_16BIT_MONO>

// 2. VAD 状态事件
{ "type": "vad_event", "status": "start" } // 开始说话
{ "type": "vad_event", "status": "end" }   // 说话结束

```

**Server -> Client (下行):**

```json
// 1. 控制指令
{ "type": "control", "command": "pause" } 
{ "type": "control", "command": "resume", "seek_time": 12000 }

// 2. 字幕/状态
{ "type": "subtitle", "text": "正在查询相关参数..." }

// 3. 回答音频 (Base64 或 Binary)
{ "type": "audio_stream", "chunk": "<Base64_Encoded_MP3>" }

```

---

## 5. 接口定义 (API Endpoints)

### 5.1 REST API (Management)

#### 知识库管理
* `POST /api/v1/knowledge`: 创建新知识库。
* `GET /api/v1/knowledge`: 获取知识库列表。
* `POST /api/v1/knowledge/{kb_id}/activate`: 切换激活知识库。
* `DELETE /api/v1/knowledge/{kb_id}`: 删除整个知识库。
* `GET /api/v1/knowledge/{kb_id}/documents`: 查看知识库文档列表。
* `DELETE /api/v1/knowledge/clear`: 清空当前知识库。

#### 文件管理
* `POST /api/v1/upload`: 上传文件 (PDF/TXT/Markdown) 到指定知识库。
* `GET /api/v1/files`: 获取已上传文件列表。
* `DELETE /api/v1/files/{file_id}`: 删除单个文档。

#### 策展对话
* `POST /api/v1/curator/chat`: 发送文字消息，获取 Agent 回复。
* `POST /api/v1/curator/voice-chat`: 上传语音文件，获取语音回复。

#### 脚本管理
* `POST /api/v1/script/generate`: 触发脚本生成，返回 JSON。
* `GET /api/v1/script/{script_id}`: 获取指定脚本。

#### 审核系统（新增）
* `POST /api/v1/audit/script/{script_id}`: 触发脚本审核。
* `GET /api/v1/audit/report/{script_id}`: 获取审核报告。
* `POST /api/v1/audit/fix/{script_id}`: 一键修复脚本问题。

### 5.2 WebSocket (Runtime)

* `WS /ws/runtime/{session_id}`: 处理实时语音流和控制信令（待实现）。

---

## 6. 项目目录结构 (Directory Structure)

```text
lingjing-lite/
├── frontend/                # React Frontend
│   ├── src/
│   │   ├── components/       # UI Components
│   │   │   ├── CuratorPanel.tsx    # 策展对话面板（文字+语音）
│   │   │   ├── KnowledgeManager.tsx # 知识库管理组件
│   │   │   ├── Player.tsx          # 脚本播放器
│   │   │   ├── ScriptDisplay.tsx   # 脚本展示
│   │   │   └── AuditReport.tsx     # 审核报告展示（待实现）
│   │   ├── stores/           # Zustand Stores
│   │   │   └── usePlayerStore.ts   # 播放器状态管理
│   │   ├── api/              # API 服务
│   │   │   └── index.ts            # Axios 封装
│   │   ├── utils/            # 工具函数
│   │   │   └── wavEncoder.ts       # 原生 WAV 编码器
│   │   └── types/            # TypeScript 类型定义
│   │       └── index.ts
│   ├── public/               # 静态资源
│   └── package.json
│
├── server/                 # FastAPI Backend
│   ├── app/
│   │   ├── api/              # REST Routers
│   │   │   └── v1/
│   │   │       ├── files.py         # 文件上传
│   │   │       ├── knowledge.py     # 知识库 CRUD
│   │   │       ├── curator.py       # 策展对话（文字+语音）
│   │   │       ├── script.py        # 脚本生成
│   │   │       └── audit.py         # 审核智能体（待实现）
│   │   ├── core/             # 核心配置
│   │   │   └── config.py        # 环境配置
│   │   ├── services/         # 业务逻辑
│   │   │   ├── ai_service.py    # 智谱 AI 封装
│   │   │   ├── knowledge_service.py # 知识库管理
│   │   │   ├── voice_service.py # ASR + TTS
│   │   │   └── audit_service.py # 审核逻辑（待实现）
│   │   ├── models/           # Pydantic Schemas
│   │   │   └── schemas.py
│   │   └── utils/            # 工具函数
│   │       ├── pdf_parser.py    # PDF 解析
│   │       └── text_processor.py # 文本处理
│   ├── data/               # ChromaDB 存储
│   │   ├── chroma_db/          # 默认知识库
│   │   └── knowledge_bases/    # 用户创建的知识库
│   ├── uploads/            # 上传文件缓存
│   ├── static/             # 静态文件
│   │   └── audio/              # TTS 生成的音频
│   ├── main.py             # FastAPI 入口
│   └── requirements.txt    # Python 依赖
│
└── docs/                   # 文档
    ├── AI数字人讲解PRD.md
    └── AI数字人讲解技术方案文档.md
```
```

---

## 7. 关键实现提示 (Development Tips)

1. **VAD 实现:**
* 在前端使用 `hargrave` 或简单的 `Web Audio API` 能量检测。
* 设置 `Silence Threshold` (静音阈值)，防止背景噪音误触发打断。


2. **WebSocket 音频流:**
* 前端录音通常是 44.1kHz/48kHz，发送前必须 Downsample 到 16kHz，以匹配 ASR 模型要求，减少带宽。


3. **TTS 缓存:**
* 对于生成的固定脚本，建议在服务端生成 MP3 文件缓存。
* 对于 RAG 问答生成的临时回复，使用流式传输 (Streaming)。



```

```