from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.rag.bm25_index import get_bm25_index
from app.rag.ingest import ingest_file_document, ingest_text_document, rebuild_document_chunks
from app.rag.splitters import SPLITTER_REGISTRY

logger = logging.getLogger(__name__)


class DocumentService:
    """文档相关业务编排。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _validate_splitter_name(preferred_splitter: str | None) -> None:
        """校验用户显式指定的切分策略是否合法。"""

        if preferred_splitter is not None and preferred_splitter not in SPLITTER_REGISTRY:
            available_names = ', '.join(SPLITTER_REGISTRY)
            raise ValueError(f'Unsupported splitter: {preferred_splitter}. Available: {available_names}')

    def ingest_text(
        self,
        *,
        filename: str,
        content: str,
        knowledge_base: str = 'default',
        preferred_splitter: str | None = None,
    ) -> Document:
        """写入文档、切分 chunk，并同步建立向量索引。"""

        self._validate_splitter_name(preferred_splitter)
        logger.info(
            '[DOC] ingest_text: filename=%s knowledge_base=%s preferred_splitter=%s content_chars=%s',
            filename,
            knowledge_base,
            preferred_splitter or 'auto',
            len(content),
        )
        document = ingest_text_document(
            self.db,
            filename=filename,
            content=content,
            knowledge_base=knowledge_base,
            preferred_splitter=preferred_splitter,
        )
        self.db.commit()
        self.db.refresh(document)
        get_bm25_index().mark_dirty(f'document_ingested:{document.id}')
        logger.info(
            '[DOC] ingest_text done: document_id=%s filename=%s status=%s chunk_count=%s summary=%s',
            document.id,
            document.filename,
            document.status,
            document.chunk_count,
            document.summary,
        )
        return document

    def ingest_file(
        self,
        *,
        file_path: str | Path,
        original_filename: str,
        knowledge_base: str = 'default',
        file_size: int | None = None,
        preferred_splitter: str | None = None,
    ) -> Document:
        """从已保存的本地文件创建文档并完成入库。"""

        self._validate_splitter_name(preferred_splitter)
        logger.info(
            '[DOC] ingest_file: original_filename=%s file_path=%s knowledge_base=%s file_size=%s preferred_splitter=%s',
            original_filename,
            file_path,
            knowledge_base,
            file_size,
            preferred_splitter or 'auto',
        )
        document = ingest_file_document(
            self.db,
            file_path=file_path,
            original_filename=original_filename,
            knowledge_base=knowledge_base,
            file_size=file_size,
            preferred_splitter=preferred_splitter,
        )
        self.db.commit()
        self.db.refresh(document)
        get_bm25_index().mark_dirty(f'document_ingested:{document.id}')
        logger.info(
            '[DOC] ingest_file done: document_id=%s filename=%s status=%s chunk_count=%s summary=%s',
            document.id,
            document.filename,
            document.status,
            document.chunk_count,
            document.summary,
        )
        return document

    def list_documents(self) -> list[Document]:
        """按更新时间倒序返回文档列表。"""

        statement = select(Document).order_by(Document.updated_at.desc())
        return self.db.execute(statement).scalars().all()

    def get_document(self, document_id: str) -> Document | None:
        """按主键查询单个文档。"""

        statement = select(Document).where(Document.id == document_id)
        return self.db.execute(statement).scalar_one_or_none()

    def rebuild_index(self, document_id: str, *, preferred_splitter: str | None = None) -> Document | None:
        """删除旧 chunk 与旧向量后，按当前策略重新切分并重建索引。"""

        self._validate_splitter_name(preferred_splitter)
        logger.info(
            '[DOC] rebuild_index: document_id=%s preferred_splitter=%s',
            document_id,
            preferred_splitter or 'auto',
        )
        document = self.get_document(document_id)
        if document is None:
            return None

        rebuilt_document = rebuild_document_chunks(
            self.db,
            document=document,
            preferred_splitter=preferred_splitter,
        )
        self.db.commit()
        self.db.refresh(rebuilt_document)
        get_bm25_index().mark_dirty(f'document_rebuilt:{rebuilt_document.id}')
        logger.info(
            '[DOC] rebuild_index done: document_id=%s filename=%s status=%s chunk_count=%s summary=%s',
            rebuilt_document.id,
            rebuilt_document.filename,
            rebuilt_document.status,
            rebuilt_document.chunk_count,
            rebuilt_document.summary,
        )
        return rebuilt_document

    def list_splitter_options(self) -> list[dict[str, str]]:
        """返回当前系统支持的切分策略列表。"""

        descriptions = {
            'structured': '适合字段说明、配置项、DDL、参数列表等强结构化内容',
            'semi_structured': '适合 Markdown、Docx 标题段落块、业务方案说明等半结构化内容',
            'unstructured': '适合普通自然段文本，按长度与分隔符做基础切分',
        }
        return [
            {'name': name, 'description': descriptions.get(name, '')}
            for name in SPLITTER_REGISTRY
        ]

    def delete_document(self, document_id: str) -> bool:
        """物理删除整个文档，级联删除所有相关的 Chunk 及其向量，并删除物理源文件。"""

        document = self.get_document(document_id)
        if document is None:
            return False

        # 1. 查出所有关联的 chunks
        chunks = self.db.execute(select(Chunk).where(Chunk.document_id == document.id)).scalars().all()

        # 2. 从 Milvus 删除 chunks 对应的向量，并从数据库删除 chunk 记录
        if chunks:
            from app.rag.ingest import _delete_chunk_vectors
            _delete_chunk_vectors(chunks)
            self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))

        # 3. 删除物理磁盘上的源文件
        if document.source_path:
            source_file = Path(document.source_path)
            if source_file.exists():
                try:
                    source_file.unlink()
                except Exception as exc:
                    logger.warning('Failed to delete physical file %s: %s', document.source_path, exc)

        # 4. 删除文档记录
        self.db.delete(document)
        self.db.commit()
        get_bm25_index().mark_dirty(f'document_deleted:{document_id}')
        logger.info('[DOC] delete_document done: document_id=%s', document_id)
        return True
