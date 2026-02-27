from langchain_community.vectorstores import Chroma
from app.services.ai_service import embeddings
import warnings
warnings.filterwarnings('ignore')

print("测试default知识库...")
vs = Chroma(persist_directory='chroma_db', embedding_function=embeddings)
docs = vs.similarity_search('飞行安全', k=3)
print(f'查询"飞行安全"结果数: {len(docs)}')

if docs:
    for i, doc in enumerate(docs):
        print(f'\n文档{i+1}:')
        print(doc.page_content[:200])
else:
    print("知识库为空！")
