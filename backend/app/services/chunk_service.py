from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.milvus_client import get_vector_store
from app.models.chunk import Chunk
from app.rag.bm25_index import get_bm25_index
from app.utils.text import clean_text, estimate_token_count


class ChunkService:
    """Chunk 相关业务编排。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_chunks(self, *, document_id: str | None = None, limit: int = 100) -> list[Chunk]:
        """按文档筛选并返回 chunk 列表。"""

        statement = select(Chunk).order_by(Chunk.updated_at.desc()).limit(limit)
        if document_id:
            statement = statement.where(Chunk.document_id == document_id)
        return self.db.execute(statement).scalars().all()

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        """按主键查询单个 chunk。"""

        statement = select(Chunk).where(Chunk.id == chunk_id)
        return self.db.execute(statement).scalar_one_or_none()

    def update_chunk(
        self,
        chunk_id: str,
        *,
        content: str | None = None,
        enabled: bool | None = None,
        metadata_json: dict | None = None,
    ) -> Chunk | None:
        """更新单个 chunk，并在必要时同步重建向量。"""

        chunk = self.get_chunk(chunk_id)
        if chunk is None:
            return None

        metadata_changed = False
        if metadata_json:
            chunk.metadata_json = {
                **chunk.metadata_json,
                **metadata_json,
            }
            metadata_changed = True

        if enabled is not None:
            chunk.enabled = enabled

        if content is not None:
            normalized_content = clean_text(content)
            if not normalized_content:
                raise ValueError('Chunk content cannot be empty')

            if normalized_content != chunk.content:
                vector_store = get_vector_store()
                if chunk.vector_id:
                    try:
                        vector_store.delete(ids=[chunk.vector_id])
                    except Exception:  # noqa: BLE001
                        # 向量删除失败不阻止文本更新，后续可通过重建索引重新清理。
                        pass

                chunk.content = normalized_content
                chunk.token_count = estimate_token_count(normalized_content)

                updated_metadata = {
                    **chunk.metadata_json,
                    'chunk_id': chunk.id,
                    'chunk_index': chunk.chunk_index,
                    'document_id': chunk.document_id,
                    'start_offset': chunk.start_offset,
                    'end_offset': chunk.end_offset,
                    'manual_edited': True,
                }
                vector_ids = vector_store.add_texts(
                    texts=[chunk.content],
                    metadatas=[updated_metadata],
                )
                chunk.vector_id = str(vector_ids[0])
                chunk.metadata_json = {
                    **updated_metadata,
                    'vector_id': chunk.vector_id,
                }
            elif metadata_changed:
                chunk.metadata_json = {
                    **chunk.metadata_json,
                    'manual_edited': True,
                }

        self.db.commit()
        self.db.refresh(chunk)
        get_bm25_index().mark_dirty(f'chunk_updated:{chunk.id}')
        return chunk

    def delete_chunk(self, chunk_id: str) -> bool:
        """物理删除单个 chunk，包括从 Milvus 和数据库中删除。"""

        chunk = self.get_chunk(chunk_id)
        if chunk is None:
            return False

        if chunk.vector_id:
            vector_store = get_vector_store()
            try:
                vector_store.delete(ids=[chunk.vector_id])
            except Exception:  # noqa: BLE001
                # 即使向量删除失败，也继续删除数据库记录，防止产生脏数据死锁。
                pass

        self.db.delete(chunk)
        self.db.commit()
        get_bm25_index().mark_dirty(f'chunk_deleted:{chunk.id}')
        return True
