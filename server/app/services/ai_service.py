from typing import List
from app.core.config import ZHIPUAI_API_KEY

# 延迟初始化，避免导入时出错
_zhipu_client = None
_llm = None
_embeddings = None

class ZhipuEmbeddings:
    """智谱 AI Embedding-3 封装类"""
    def __init__(self, api_key: str):
        from zhipuai import ZhipuAI
        self.client = ZhipuAI(api_key=api_key)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            response = self.client.embeddings.create(
                model="embedding-3",
                input=text
            )
            embeddings.append(response.data[0].embedding)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            model="embedding-3",
            input=text
        )
        return response.data[0].embedding

def get_zhipu_client():
    """获取智谱 AI 客户端（延迟初始化）"""
    global _zhipu_client
    if _zhipu_client is None:
        from zhipuai import ZhipuAI
        _zhipu_client = ZhipuAI(api_key=ZHIPUAI_API_KEY, timeout=30.0)
    return _zhipu_client

def get_llm():
    """获取 LLM（延迟初始化）"""
    global _llm
    if _llm is None:
        from langchain_community.chat_models import ChatZhipuAI
        _llm = ChatZhipuAI(model="glm-4-plus", api_key=ZHIPUAI_API_KEY, temperature=0.7)
    return _llm

def get_embeddings():
    """获取 Embeddings（延迟初始化）"""
    global _embeddings
    if _embeddings is None:
        _embeddings = ZhipuEmbeddings(api_key=ZHIPUAI_API_KEY)
    return _embeddings

# 兼容旧代码的导出
zhipu_client = get_zhipu_client()
llm = get_llm()
embeddings = get_embeddings()
