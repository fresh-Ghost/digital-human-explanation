from typing import List
from zhipuai import ZhipuAI
from langchain_community.chat_models import ChatZhipuAI
from app.core.config import ZHIPUAI_API_KEY

class ZhipuEmbeddings:
    """智谱 AI Embedding-3 封装类"""
    def __init__(self, api_key: str):
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

# 初始化智谱 AI 客户端（设置超时避免长时间等待）
zhipu_client = ZhipuAI(
    api_key=ZHIPUAI_API_KEY,
    timeout=30.0  # 30秒超时
)

# 初始化 LLM
llm = ChatZhipuAI(
    model="glm-4-plus",
    api_key=ZHIPUAI_API_KEY,
    temperature=0.7,
)

# 初始化 Embeddings
embeddings = ZhipuEmbeddings(api_key=ZHIPUAI_API_KEY)
