import os
import uuid
import shutil
from typing import List, Dict, Any
from fastapi import UploadFile
from app.core.config import UPLOAD_DIR

class FileService:
    @staticmethod
    async def save_upload(file: UploadFile) -> str:
        file_id = str(uuid.uuid4())
        save_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
        return save_path, file_id

    @staticmethod
    def get_file_list() -> List[Dict[str, Any]]:
        files = []
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                if "_" in filename:
                    parts = filename.split("_", 1)
                    file_id = parts[0]
                    original_name = parts[1]
                    file_path = os.path.join(UPLOAD_DIR, filename)
                    stats = os.stat(file_path)
                    files.append({
                        "file_id": file_id,
                        "filename": original_name,
                        "size": stats.st_size,
                        "upload_time": stats.st_mtime
                    })
        files.sort(key=lambda x: x["upload_time"], reverse=True)
        return files

    @staticmethod
    def delete_file(file_id: str) -> bool:
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                if filename.startswith(f"{file_id}_"):
                    os.remove(os.path.join(UPLOAD_DIR, filename))
                    return True
        return False

file_service = FileService()
