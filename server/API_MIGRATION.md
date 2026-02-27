# API 迁移记录 - 从 Ollama 到智谱清言

## 变更日期
2026-01-12

## 变更概述
将项目中所有使用大模型的地方从本地 Ollama (qwen2.5:3b) 迁移到智谱清言云端 API。

## 具体变更

### 1. LLM 模型
- **之前**: Ollama + qwen2.5:3b (本地部署)
- **现在**: 智谱清言 GLM-4-Flash (云端 API)

### 2. Embedding 向量化
- **之前**: HuggingFace BAAI/bge-small-zh-v1.5 (本地模型)
- **现在**: 智谱清言 Embedding-3 (云端 API)

### 3. API Key
```
d9b8b8298ff1470ba69ed094bdba16c5.NdjZFDpNJkOGb3lN
```

### 4. 代码变更位置

#### server/main.py
- 导入模块从 `langchain_community.llms.Ollama` 改为 `langchain_community.chat_models.ChatZhipuAI`
- 移除 `HuggingFaceEmbeddings`，添加自定义 `ZhipuEmbeddings` 类
- 初始化 LLM 使用 `ChatZhipuAI(model="glm-4-flash")`
- LLM 响应处理改为提取 `response.content`

#### server/requirements.txt
添加新依赖：
- zhipuai
- langchain
- langchain-community
- langchain-core
- edge-tts
- pypdf
- chromadb
- sniffio (zhipuai 依赖)

## 优势

### 性能提升
- GLM-4-Flash 响应速度更快
- 无需本地运行模型，节省计算资源
- Embedding-3 向量质量更高

### 稳定性
- 云端服务高可用
- 无需担心本地 Ollama 服务状态
- API 调用更可靠

### 成本
- 按需付费，无需购买 GPU
- GLM-4-Flash 性价比高

## 注意事项

1. **网络依赖**: 需要稳定的网络连接
2. **API 限额**: 注意智谱 API 的调用限额
3. **成本控制**: 合理控制 API 调用次数
4. **错误处理**: 已添加完善的异常捕获和回退机制

## 测试建议

1. 上传测试文档，验证 Embedding 向量化
2. 测试脚本生成功能，验证 LLM 调用
3. 测试策展对话功能
4. 检查 RAG 检索效果

## 回退方案

如需回退到 Ollama，恢复以下代码：

```python
from langchain_community.llms import Ollama
from langchain_community.embeddings import HuggingFaceEmbeddings

llm = Ollama(model="qwen2.5:3b", base_url="http://localhost:11434")
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)
```
