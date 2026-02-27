import os
import shutil
import time
import gc
import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from app.models.schemas import KnowledgeBaseInfo, KnowledgeBaseListResponse
from app.core.config import KB_BASE_DIR, CHROMA_DIR
from app.services.knowledge_service import knowledge_service

router = APIRouter()

@router.get("/list", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases():
    """获取所有知识库列表"""
    kb_list = []
    
    # 1. 默认知识库
    default_kb = {
        "id": "default",
        "name": "默认知识库",
        "collection_name": "lingjing_knowledge_zhipu",
        "total_documents": 0,
        "uploaded_files": [],
        "is_active": knowledge_service.current_kb_id == "default"
    }
    
    # 只为激活的知识库获取文档数，避免创建多余连接导致文件被占用
    if default_kb["is_active"] and knowledge_service.vectorstore is not None:
        try:
            default_kb["total_documents"] = knowledge_service.vectorstore._collection.count()
        except:
            pass
    else:
        default_kb["total_documents"] = "未加载"
        
    kb_list.append(default_kb)
    
    # 2. 用户创建的知识库
    if os.path.exists(KB_BASE_DIR):
        for dirname in os.listdir(KB_BASE_DIR):
            if dirname.startswith("kb_") and os.path.isdir(os.path.join(KB_BASE_DIR, dirname)):
                # 兼容多种格式: kb_{id}_{name} 或 kb_{date}_{time}_{name}
                parts = dirname.split("_")
                if len(parts) >= 3:
                    # 将中间部分作为 ID，最后一部分作为名称
                    kb_name = parts[-1]
                    kb_id = "_".join(parts[1:-1])
                    
                    kb_info = {
                        "id": kb_id,
                        "name": kb_name,
                        "collection_name": f"kb_{kb_id}",
                        "total_documents": 0,
                        "uploaded_files": [],
                        "is_active": knowledge_service.current_kb_id == kb_id,
                        "created_at": os.path.getctime(os.path.join(KB_BASE_DIR, dirname))
                    }
                    
                    if kb_info["is_active"] and knowledge_service.vectorstore is not None:
                        try:
                            kb_info["total_documents"] = knowledge_service.vectorstore._collection.count()
                        except:
                            pass
                    else:
                        kb_info["total_documents"] = "未加载"
                        
                    kb_list.append(kb_info)
    
    return {"knowledge_bases": kb_list}

@router.post("/create")
async def create_knowledge_base(name: str):
    # 使用 UUID 确保全局唯一性
    kb_id = str(uuid.uuid4())[:8]  # 取前8位，足够唯一且简短
    kb_dir = os.path.join(KB_BASE_DIR, f"kb_{kb_id}_{name}")
    os.makedirs(kb_dir, exist_ok=True)
    return {"success": True, "kb_id": kb_id, "name": name}

@router.post("/switch/{kb_id}")
async def switch_knowledge_base(kb_id: str):
    path = knowledge_service.get_kb_path(kb_id)
    if not path:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    knowledge_service.close_connection()
    knowledge_service.current_kb_id = kb_id
    
    # 从路径中提取名称
    if kb_id == "default":
        knowledge_service.current_kb_name = "默认知识库"
    else:
        dirname = os.path.basename(path)
        parts = dirname.split("_")
        if len(parts) >= 3:
            knowledge_service.current_kb_name = parts[-1]
    
    knowledge_service.init_vectorstore()
    
    # 获取切换后的知识库文档数
    total_docs = 0
    if knowledge_service.vectorstore is not None:
        try:
            # 尝试获取文档数，Chroma 可能需要一点时间初始化集合
            import time
            time.sleep(0.1)  # 短暂延迟确保集合准备就绪
            total_docs = knowledge_service.vectorstore._collection.count()
            print(f"[切换知识库] {kb_id} 文档数: {total_docs}")
        except Exception as e:
            print(f"[切换知识库] 获取文档数失败: {e}")
            pass
    else:
        print(f"[切换知识库] vectorstore 为 None")
    
    return {"success": True, "kb_id": kb_id, "name": knowledge_service.current_kb_name, "total_documents": total_docs}

@router.get("/info", response_model=KnowledgeBaseInfo)
async def get_knowledge_base_info():
    """获取当前激活知识库的详细信息"""
    path = knowledge_service.get_kb_path(knowledge_service.current_kb_id)
    
    info = {
        "id": knowledge_service.current_kb_id,
        "name": knowledge_service.current_kb_name,
        "collection_name": "lingjing_knowledge_zhipu",
        "total_documents": 0,
        "uploaded_files": [],
        "is_active": True
    }
    
    if knowledge_service.vectorstore is not None:
        try:
            collection = knowledge_service.vectorstore._collection
            info["total_documents"] = collection.count()
            
            # 统计文件信息
            all_metadata = collection.get(include=['metadatas'])
            file_stats = {}
            if all_metadata and 'metadatas' in all_metadata:
                for meta in all_metadata['metadatas']:
                    if meta and 'source' in meta:
                        source = meta['source']
                        file_stats[source] = file_stats.get(source, 0) + 1
            
            for filename, count in file_stats.items():
                info["uploaded_files"].append({
                    "filename": filename,
                    "chunk_count": count
                })
        except Exception as e:
            print(f"获取知识库信息失败: {e}")
            
    return info

@router.delete("/clear")
async def clear_knowledge_base():
    """清空当前知识库的所有文档。"""
    if knowledge_service.vectorstore is None:
        return {"success": False, "message": "知识库未初始化"}
    
    try:
        collection = knowledge_service.vectorstore._collection
        all_docs = collection.get()
        if not all_docs or not all_docs.get('ids'):
            return {"success": True, "message": "知识库已经为空"}
        
        doc_count = len(all_docs['ids'])
        collection.delete(ids=all_docs['ids'])
        return {"success": True, "message": f"知识库已清空，删除了 {doc_count} 个文档分块"}
    except Exception as e:
        return {"success": False, "message": f"清空失败: {str(e)}"}

@router.put("/{kb_id}/rename")
async def rename_knowledge_base(kb_id: str, new_name: str):
    """重命名知识库 - Windows 优化版"""
    if kb_id == "default":
        raise HTTPException(status_code=400, detail="默认知识库不能重命名")
        
    old_path = knowledge_service.get_kb_path(kb_id)
    if not old_path:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 检查新名称是否已存在
    new_dirname = f"kb_{kb_id}_{new_name}"
    new_path = os.path.join(KB_BASE_DIR, new_dirname)
    if os.path.exists(new_path):
        return {"success": False, "message": f"名为「{new_name}」的知识库已存在"}
    
    # 关键：无论是否当前知识库，都先切换到默认库，确保释放所有句柄
    is_target_current = (knowledge_service.current_kb_id == kb_id)
    
    # 关闭当前连接
    knowledge_service.close_connection()
    
    # 切换到默认库，避免保持对目标目录的任何引用
    knowledge_service.current_kb_id = "default"
    knowledge_service.current_kb_name = "默认知识库"
    knowledge_service.init_vectorstore()
    
    # 强制垃圾回收，多次调用确保所有句柄释放（Windows 需要更长时间）
    for _ in range(10):
        gc.collect()
        time.sleep(0.3)
        
    # 尝试重命名，包含重试逻辑（针对 Windows 文件占用）
    last_error = None
    for i in range(20):  # 增加重试次数
        try:
            # 使用 shutil.move 替代 os.rename，更健壮
            shutil.move(old_path, new_path)
            
            # 如果重命名的是之前激活的知识库，切换回去
            if is_target_current:
                knowledge_service.close_connection()
                knowledge_service.current_kb_id = kb_id
                knowledge_service.current_kb_name = new_name
                knowledge_service.init_vectorstore()
                
            return {"success": True, "new_name": new_name}
        except Exception as e:
            last_error = e
            # 释放句柄并重试
            gc.collect()
            time.sleep(0.5 + i * 0.1)  # 递增等待时间
    
    # 所有重试失败
    return {"success": False, "message": f"重命名失败（文件可能被占用）: {str(last_error)}"}

@router.delete("/documents/{filename}")
async def delete_document_from_kb(filename: str):
    """从当前向量库中删除特定文件的所有分块。"""
    if knowledge_service.vectorstore is None:
        return {"success": False, "message": "知识库未初始化"}
    
    try:
        collection = knowledge_service.vectorstore._collection
        all_docs = collection.get(include=['metadatas'])
        
        chunk_ids = []
        if all_metadata := all_docs.get('metadatas'):
            for i, meta in enumerate(all_metadata):
                if meta and meta.get('source') == filename:
                    chunk_ids.append(all_docs['ids'][i])
        
        if not chunk_ids:
            return {"success": False, "message": f"在知识库中未找到文件「{filename}」"}
        
        collection.delete(ids=chunk_ids)
        return {"success": True, "message": f"已从知识库中删除文档「{filename}」"}
    except Exception as e:
        return {"success": False, "message": f"删除失败: {str(e)}"}

@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    """删除知识库 - Windows 优化版"""
    if kb_id == "default":
        raise HTTPException(status_code=400, detail="默认知识库不能删除")
    
    path = knowledge_service.get_kb_path(kb_id)
    if not path:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 关键：无论是否当前知识库，都先切换到默认库，确保释放所有句柄
    # 关闭当前连接
    knowledge_service.close_connection()
    
    # 切换到默认库，避免保持对目标目录的任何引用
    knowledge_service.current_kb_id = "default"
    knowledge_service.current_kb_name = "默认知识库"
    knowledge_service.init_vectorstore()
    
    # 强制垃圾回收，多次调用确保所有句柄释放（Windows 需要更长时间）
    for _ in range(10):
        gc.collect()
        time.sleep(0.3)
    
    # 增强删除逻辑
    last_error = "未知错误"
    for i in range(20):  # 增加重试次数
        try:
            if os.path.exists(path):
                # 先尝试逐个删除内部文件
                for root, dirs, files in os.walk(path, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        try:
                            os.chmod(file_path, 0o777)
                            os.remove(file_path)
                        except Exception as e:
                            last_error = str(e)
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        try:
                            os.rmdir(dir_path)
                        except Exception as e:
                            last_error = str(e)
                # 最后删除根目录
                shutil.rmtree(path, ignore_errors=True)
            
            # 检查是否真的删除了
            if not os.path.exists(path):
                return {"success": True}
        except Exception as e:
            last_error = str(e)
            print(f"删除重试 {i+1} 失败: {e}")
        
        # 释放句柄并重试
        gc.collect()
        time.sleep(0.5 + i * 0.1)
    
    # 所有重试失败
    return {"success": False, "message": f"删除失败，文件可能被占用: {last_error}"}


