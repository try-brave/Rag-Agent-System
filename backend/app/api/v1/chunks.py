from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_database
from app.schemas.chunk import ChunkItem, ChunkUpdateRequest
from app.services.chunk_service import ChunkService

router = APIRouter(prefix='/chunks', tags=['chunks'])


@router.get('', response_model=list[ChunkItem])
def list_chunks(
    document_id: str | None = Query(default=None, description='按文档 ID 过滤'),
    limit: int = Query(default=100, ge=1, le=500, description='返回结果数量上限'),
    db: Session = Depends(get_database),
) -> list[ChunkItem]:
    """返回 chunk 列表，便于前端直接做 chunk 管理页。"""

    service = ChunkService(db)
    chunks = service.list_chunks(document_id=document_id, limit=limit)
    return [ChunkItem.model_validate(chunk) for chunk in chunks]


@router.get('/{chunk_id}', response_model=ChunkItem)
def get_chunk(chunk_id: str, db: Session = Depends(get_database)) -> ChunkItem:
    """返回单个 chunk 详情。"""

    service = ChunkService(db)
    chunk = service.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chunk not found')
    return ChunkItem.model_validate(chunk)


@router.delete('/{chunk_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_chunk(chunk_id: str, db: Session = Depends(get_database)) -> None:
    """物理删除单个 chunk。"""

    service = ChunkService(db)
    if not service.delete_chunk(chunk_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chunk not found')


@router.patch('/{chunk_id}', response_model=ChunkItem)
def update_chunk(
    chunk_id: str,
    request: ChunkUpdateRequest,
    db: Session = Depends(get_database),
) -> ChunkItem:
    """更新 chunk 内容、启用状态或附加元数据。"""

    service = ChunkService(db)
    try:
        chunk = service.update_chunk(
            chunk_id,
            content=request.content,
            enabled=request.enabled,
            metadata_json=request.metadata_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if chunk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chunk not found')
    return ChunkItem.model_validate(chunk)
