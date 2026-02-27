from typing import List, Dict, Any
from app.core.config import SEARCH_CONFIG
from app.services.knowledge_service import knowledge_service
from app.utils.text_utils import extract_keywords

class RAGService:
    @staticmethod
    async def search(query: str, top_k: int = 10) -> Dict[str, Any]:
        if knowledge_service.vectorstore is None:
            return {"results": [], "message": "知识库为空，请先上传文档"}
        
        try:
            keywords = extract_keywords(query)
            
            search_multiplier = SEARCH_CONFIG["search_multiplier"]
            max_results = SEARCH_CONFIG["max_search_results"]
            search_k = min(top_k * search_multiplier, max_results)
            
            docs_with_scores = knowledge_service.vectorstore.similarity_search_with_score(query, k=search_k)
            
            results = []
            boost_score = SEARCH_CONFIG["keyword_boost_score"]
            multi_bonus = SEARCH_CONFIG["multi_keyword_bonus"]
            threshold = SEARCH_CONFIG["similarity_threshold"]
            
            for doc, distance in docs_with_scores:
                # 智谱 Embedding-3 建议使用余弦相似度。
                # Chroma 默认 L2 距离，对于归一化向量，cosine_sim = 1 - L2_dist_sq / 2
                # 如果 distance 是 squared L2，则 similarity = 1 - distance / 2
                similarity = max(0, 1 - distance / 2)
                
                # 如果相似度过低，即便有关键词加成也不应排到前面
                if similarity < 0.2:
                    continue

                keyword_boost = 0
                matched_keywords = []
                for keyword in keywords:
                    if keyword in doc.page_content:
                        # 降低单次匹配权重，增加多样性权重
                        keyword_boost += boost_score * 0.5
                        matched_keywords.append(keyword)
                
                # 匹配到的不同关键词越多，加成越高
                if len(matched_keywords) >= 2:
                    # 奖励关键词的多样性匹配
                    keyword_boost += multi_bonus * len(matched_keywords)
                
                # 如果查询词本身较短且完全匹配，给予极高奖励（针对 PRD, DJI 等专有名词）
                if any(kw.lower() == query.lower() for kw in matched_keywords):
                    keyword_boost += 0.1
                
                # 最终分数：语义占据 60%，关键词占据 40% (增加关键词权重)
                final_score = (similarity * 0.6) + (min(0.4, keyword_boost) * 1.0)
                
                if final_score >= threshold:
                    results.append({
                        "content": doc.page_content,
                        "source": doc.metadata.get("source", "unknown"),
                        "score": final_score,
                        "semantic_score": similarity,
                        "keyword_boost": keyword_boost,
                        "distance": distance,
                        "article": doc.metadata.get("article", None),
                    })
            
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]
            
            return {
                "results": results,
                "total": len(results),
                "query": query,
                "kb_name": knowledge_service.current_kb_name,
                "kb_id": knowledge_service.current_kb_id
            }
        except Exception as e:
            print(f"❌ RAG 搜索失败: {e}")
            return {"results": [], "error": str(e)}
    
    def retrieve(self, query: str, kb_id: str = None, k: int = 5) -> List[Any]:
        """
        检索知识库相关文档（同步版本，用于 WebSocket）
        """
        try:
            # 如果指定了 kb_id，临时加载该知识库
            if kb_id and kb_id != knowledge_service.current_kb_id:
                vectorstore = knowledge_service.load_vectorstore(kb_id)
            else:
                vectorstore = knowledge_service.vectorstore
            
            if not vectorstore:
                print(f"[检索] 知识库不可用: {kb_id}")
                return []
            
            docs = vectorstore.similarity_search(query, k=k)
            print(f"[检索] 找到 {len(docs)} 个相关文档")
            return docs
        except Exception as e:
            print(f"[检索] 失败: {e}")
            return []

rag_service = RAGService()
