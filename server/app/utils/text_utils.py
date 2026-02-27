import re
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import CHINESE_STOPWORDS, SEARCH_CONFIG

def get_text_splitter(has_articles: bool = False) -> RecursiveCharacterTextSplitter:
    """根据是否是结构化文档返回分块器"""
    if has_articles:
        return RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=200,
            separators=[
                "\n\n\n", "\n\n", "。\n", "\n", "。", "；", "，", " ", ""
            ]
        )
    else:
        return RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""]
        )

def extract_keywords(query: str) -> List[str]:
    """从查询中提取关键词（滑动窗口算法，更稳健）"""
    keywords = []
    try:
        # 预处理：去掉标点符号和空格
        clean_query = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', query)
        
        min_len = SEARCH_CONFIG.get("keyword_min_length", 2)
        max_len = SEARCH_CONFIG.get("keyword_max_length", 4)
        max_kw = SEARCH_CONFIG.get("max_keywords", 8)
        
        # 滑动窗口提取
        raw_words = []
        n = len(clean_query)
        for length in range(min_len, max_len + 1):
            for i in range(n - length + 1):
                word = clean_query[i:i+length]
                # 支持中文、英文单词、数字
                if re.match(r'^[\u4e00-\u9fa5]+$|^[a-zA-Z0-9]+$', word):
                    if word.lower() not in CHINESE_STOPWORDS:
                        raw_words.append(word)
        
        # 去重并根据长度排序（优先匹配长词）
        unique_words = list(set(raw_words))
        unique_words.sort(key=len, reverse=True)
        
        # 挑选最有代表性的关键词
        # 避免选出包含关系的重复词（如有了“无人机”就不再要“无人”）
        selected = []
        for word in unique_words:
            if not any(word in s for s in selected):
                selected.append(word)
            if len(selected) >= max_kw:
                break
        
        keywords = selected
        if not keywords and len(clean_query) >= min_len:
            keywords = [clean_query[:max_len]]
            
    except Exception as e:
        print(f"  ⚠️ 关键词提取失败: {e}")
        keywords = [query]
    return keywords
