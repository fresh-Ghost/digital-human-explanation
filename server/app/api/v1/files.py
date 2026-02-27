import os
import re
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from langchain_core.documents import Document
from app.models.schemas import UploadResponse, FileListResponse
from app.services.file_service import file_service
from app.services.knowledge_service import knowledge_service
from app.services.ai_service import embeddings
from app.utils.pdf_utils import parse_pdf
from app.utils.text_utils import get_text_splitter

router = APIRouter()

@router.get("/list", response_model=FileListResponse)
async def list_files():
    files = file_service.get_file_list()
    return {"files": files, "total_count": len(files)}

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...), kb_id: str = "default"):
    """上传文件并进行向量化"""
    save_path, file_id = await file_service.save_upload(file)
    
    # 读取内容
    with open(save_path, "rb") as f:
        content = f.read()
    
    text_content = None
    if file.filename.endswith((".txt", ".md")):
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                # 尝试常见的中文编码
                text_content = content.decode("gbk")
            except UnicodeDecodeError:
                # 尝试 UTF-16 (Windows PowerShell 默认)
                text_content = content.decode("utf-16")
    elif file.filename.endswith(".pdf"):
        text_content = parse_pdf(content)
    
    if text_content:
        # 确定目标知识库路径
        target_kb_path = knowledge_service.get_kb_path(kb_id)
        if not target_kb_path:
            raise HTTPException(status_code=404, detail="知识库不存在")
        
        # 智能分块
        has_articles = bool(re.search(r'第[\d一二三四五六七八九十百千万]+条', text_content))
        text_splitter = get_text_splitter(has_articles)
        chunks = text_splitter.split_text(text_content)
        
        documents = []
        for idx, chunk in enumerate(chunks):
            metadata = {
                "source": file.filename,
                "file_id": file_id,
                "chunk_index": idx,
                "total_chunks": len(chunks)
            }
            # 提取条款和章节
            article_match = re.search(r'第([\d一二三四五六七八九十百千万]+)条', chunk)
            if article_match: metadata["article"] = article_match.group(1)
            
            chapter_match = re.search(r'第([\d一二三四五六七八九十百千万]+)章', chunk)
            if chapter_match: metadata["chapter"] = chapter_match.group(1)
            
            documents.append(Document(page_content=chunk, metadata=metadata))
        
        # 添加到向量库
        if kb_id == knowledge_service.current_kb_id and knowledge_service.vectorstore is not None:
            knowledge_service.vectorstore.add_documents(documents)
        else:
            # 这里的逻辑在main.py中是临时加载，保持一致
            from langchain_community.vectorstores import Chroma
            temp_vs = Chroma(
                collection_name="lingjing_knowledge_zhipu",
                embedding_function=embeddings,
                persist_directory=target_kb_path
            )
            temp_vs.add_documents(documents)
            
    return {"file_id": file_id, "filename": file.filename}

@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """从物理存储中删除文件。"""
    success = file_service.delete_file(file_id)
    if success:
        return {"success": True}
    else:
        return {"success": False, "message": "文件不存在或删除失败"}

