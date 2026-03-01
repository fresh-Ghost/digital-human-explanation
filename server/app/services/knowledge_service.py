import os
import gc
import time
import shutil
from typing import Optional, List
from langchain_community.vectorstores import Chroma
from app.core.config import CHROMA_DIR, KB_BASE_DIR
from app.services.ai_service import embeddings

class KnowledgeService:
    def __init__(self):
        self._vectorstore: Optional[Chroma] = None
        self.current_kb_id: str = "default"
        self.current_kb_name: str = "默认知识库"
        # 延迟初始化，不在构造函数中创建

    @property
    def vectorstore(self) -> Optional[Chroma]:
        """延迟初始化向量库"""
        if self._vectorstore is None:
            self.init_vectorstore()
        return self._vectorstore

    def init_vectorstore(self):
        """初始化向量库"""
        try:
            kb_path = self.get_kb_path(self.current_kb_id)
            if not kb_path:
                kb_path = CHROMA_DIR
            
            # 确保目录存在
            os.makedirs(kb_path, exist_ok=True)
                
            self._vectorstore = Chroma(
                collection_name="lingjing_knowledge_zhipu",
                embedding_function=embeddings,
                persist_directory=kb_path
            )
            print(f"向量库初始化成功: {self.current_kb_id} -> {kb_path}")
        except Exception as e:
            print(f"警告：向量库初始化失败: {e}")
            import traceback
            traceback.print_exc()
            self._vectorstore = None

    def load_vectorstore(self, kb_id: str) -> Optional[Chroma]:
        """按需加载向量库"""
        kb_path = self.get_kb_path(kb_id)
        if not kb_path:
            return None
        try:
            return Chroma(
                collection_name="lingjing_knowledge_zhipu",
                embedding_function=embeddings,
                persist_directory=kb_path
            )
        except Exception as e:
            print(f"加载向量库 {kb_id} 失败: {e}")
            return None

    def close_vectorstore(self, vs: Chroma):
        """显式释放一个向量库的连接资源"""
        if vs is not None:
            try:
                if hasattr(vs, '_client') and vs._client:
                    client = vs._client
                    if hasattr(client, 'close'):
                        try:
                            client.close()
                        except:
                            pass
                    vs._client = None
                if hasattr(vs, '_collection') and vs._collection:
                    vs._collection = None
            except Exception as e:
                print(f"释放向量库资源异常: {e}")
        
        # 释放后建议由调用方 del vs 并调用 gc.collect()

    def get_kb_path(self, kb_id: str) -> Optional[str]:
        if kb_id == "default":
            return CHROMA_DIR
        if os.path.exists(KB_BASE_DIR):
            # 优先尝试完全匹配 (kb_{id}_*)
            for dirname in os.listdir(KB_BASE_DIR):
                if dirname.startswith(f"kb_{kb_id}_"):
                    return os.path.join(KB_BASE_DIR, dirname)
            # 兼容旧逻辑：如果 kb_id 只是时间戳部分
            for dirname in os.listdir(KB_BASE_DIR):
                parts = dirname.split("_")
                if len(parts) >= 3 and parts[1] == kb_id:
                    return os.path.join(KB_BASE_DIR, dirname)
        return None

    def close_connection(self):
        """关闭当前连接并尝试释放资源 - Windows 优化版"""
        if self.vectorstore is not None:
            try:
                # 尝试持久化
                try:
                    self.vectorstore.persist()
                except:
                    pass
                
                # 获取客户端并关闭 - 这是释放文件锁定的关键
                if hasattr(self.vectorstore, '_client') and self.vectorstore._client:
                    client = self.vectorstore._client
                    # 关闭集合
                    if hasattr(client, '_collection') and client._collection:
                        try:
                            client._collection = None
                        except:
                            pass
                    # 关闭客户端连接
                    if hasattr(client, 'close'):
                        try:
                            client.close()
                        except:
                            pass
                    self.vectorstore._client = None
                
                # 清理集合引用
                if hasattr(self.vectorstore, '_collection'):
                    self.vectorstore._collection = None
                
                self.vectorstore = None
                print("[KnowledgeService] 知识库连接已释放")
            except Exception as e:
                print(f"[KnowledgeService] 释放资源异常: {e}")
        
        # 强制垃圾回收，多次调用确保资源释放
        for _ in range(3):
            gc.collect()
            time.sleep(0.1)

# 全局单例
knowledge_service = KnowledgeService()
