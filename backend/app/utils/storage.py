from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

CHUNK_SIZE = 1024 * 1024


def ensure_upload_dir() -> Path:
    """确保本地上传目录存在。

    当前阶段文件先落本地，后续如果切到 OSS、S3 或 MinIO，
    只需要替换这一层的实现，不影响 service 和 API 层。
    """

    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def sanitize_filename(filename: str) -> str:
    """生成安全文件名，避免路径穿越和特殊字符问题。"""

    base_name = Path(filename).name.strip()
    if not base_name:
        return 'unnamed.txt'

    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', base_name)
    return safe_name or 'unnamed.txt'


def build_storage_path(filename: str) -> Path:
    """为上传文件生成唯一存储路径。"""

    upload_dir = ensure_upload_dir()
    safe_filename = sanitize_filename(filename)
    suffix = Path(safe_filename).suffix
    stored_name = f'{uuid.uuid4().hex}{suffix}'
    return upload_dir / stored_name


async def save_upload_file(upload_file: UploadFile) -> tuple[Path, int]:
    """把上传文件以分块方式保存到本地磁盘。"""

    if not upload_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No filename provided')

    settings = get_settings()
    target_path = build_storage_path(upload_file.filename)

    file_size = 0
    with target_path.open('wb') as output_file:
        while True:
            chunk = await upload_file.read(CHUNK_SIZE)
            if not chunk:
                break

            file_size += len(chunk)
            if file_size > settings.max_upload_size_mb * 1024 * 1024:
                output_file.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f'File too large, max size is {settings.max_upload_size_mb} MB',
                )
            output_file.write(chunk)

    await upload_file.close()
    return target_path, file_size
