import os
from typing import List

# 基础目录配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
KB_BASE_DIR = os.path.join(BASE_DIR, "knowledge_bases")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
TTS_CACHE_DIR = os.path.join(BASE_DIR, "tts_cache")

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(KB_BASE_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

# 智谱 AI 配置
ZHIPUAI_API_KEY = "d9b8b8298ff1470ba69ed094bdba16c5.NdjZFDpNJkOGb3lN"

# 可用的语音列表
AVAILABLE_VOICES = [
    {"id": "zh-CN-YunxiNeural", "name": "云希(男声-沉稳)", "gender": "male"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬(男声-专业)", "gender": "male"},
    {"id": "zh-CN-YunjianNeural", "name": "云健(男声-活力)", "gender": "male"},
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓(女声-亲切)", "gender": "female"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊(女声-温柔)", "gender": "female"},
    {"id": "zh-CN-XiaohanNeural", "name": "晓涵(女声-知性)", "gender": "female"},
]

# 中文停用词配置
CHINESE_STOPWORDS = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', 
    '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', 
    '没有', '看', '好', '自己', '这', '那', '可以', '哪些', 
    '什么', '怎么', '为什么', '吗', '呢', '啊', '请', '能', 
    '一些', '我们', '他们', '已经', '如果', '这个', '那个'
}

# 搜索配置
SEARCH_CONFIG = {
    "keyword_min_length": 2,
    "keyword_max_length": 4,
    "max_keywords": 5,
    "keyword_boost_score": 0.08,
    "multi_keyword_bonus": 0.05,
    "similarity_threshold": 0.25,
    "search_multiplier": 5,
    "max_search_results": 100
}
