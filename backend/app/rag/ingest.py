from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import delete, select

from app.core.milvus_client import get_vector_store
from app.models.chunk import Chunk
from app.models.document import Document
from app.rag.loader import LoadedDocument, build_loaded_document_from_text, load_document
from app.rag.splitters import SPLITTER_REGISTRY, SplitChunk
from app.utils.text import clean_text, estimate_token_count

logger = logging.getLogger(__name__)


def _infer_file_type(filename: str) -> str:
    """根据文件名推断文件类型。

    第一版先用扩展名判断即可，后续如果接入真实上传解析器，
    可以在这里升级成更细粒度的 MIME 识别。
    """

    suffix = Path(filename).suffix.lower().lstrip('.')
    return suffix or 'txt'


def _build_chunk_metadata(
    *,
    document: Document,
    knowledge_base: str,
    parser_name: str,
    section_metadata: dict[str, object],
    chunk_index: int,
    filename: str,
    splitter_name: str,
) -> dict[str, object]:
    """统一生成 chunk 元数据。

    把所有来源信息集中在这里构造，后续不管是：
    - 前端溯源展示；
    - Agent 引用来源；
    - 结果审计与检索调试
    都可以复用同一套字段约定。
    """

    return {
        'chunk_id': None,
        'document_id': document.id,
        'knowledge_base': knowledge_base,
        'filename': filename,
        'file_type': document.file_type,
        'parser_name': parser_name,
        'chunk_index': chunk_index,
        'splitter_name': splitter_name,
        'source_path': document.source_path,
        **section_metadata,
    }


def _infer_splitter_name(
    *,
    file_type: str,
    section_metadata: dict[str, object],
    preferred_splitter: str | None = None,
) -> str:
    """为 section 选择最合适的切分策略。"""

    if preferred_splitter and preferred_splitter in SPLITTER_REGISTRY:
        return preferred_splitter

    section_type = str(section_metadata.get('section_type') or '').lower()
    if section_type in {'pdf_page', 'markdown_heading', 'docx_heading_block'}:
        return 'semi_structured'
    if file_type in {'sql', 'ddl'}:
        return 'structured'
    if section_type in {'table_schema', 'field_definition', 'config_block'}:
        return 'structured'
    return 'unstructured'


def _split_section(
    *,
    text: str,
    file_type: str,
    section_metadata: dict[str, object],
    preferred_splitter: str | None = None,
) -> tuple[str, list[SplitChunk]]:
    """切分单个 section，并返回实际使用的切分策略名称。"""

    splitter_name = _infer_splitter_name(
        file_type=file_type,
        section_metadata=section_metadata,
        preferred_splitter=preferred_splitter,
    )
    splitter = SPLITTER_REGISTRY[splitter_name]
    return splitter_name, splitter(text)


def _delete_chunk_vectors(chunks: list[Chunk]) -> None:
    """从 Milvus 中删除旧向量记录。"""

    vector_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]
    if not vector_ids:
        return

    vector_store = get_vector_store()
    try:
        vector_store.delete(ids=vector_ids)
    except Exception:  # noqa: BLE001
        # 向量删除失败不阻断重建流程，后续仍可通过再次重建或运维修复。
        pass


def ingest_loaded_document(
    db: Session,
    *,
    loaded_document: LoadedDocument,
    knowledge_base: str = 'default',
    source_path: str | None = None,
    file_size: int | None = None,
    preferred_splitter: str | None = None,
    existing_document: Document | None = None,
) -> Document:
    """把统一的加载结果写入数据库并同步建立向量索引。"""

    logger.info(
        '[INGEST] started: file=%s file_type=%s parser=%s sections=%s preferred_splitter=%s knowledge_base=%s source_path=%s',
        loaded_document.filename,
        loaded_document.file_type,
        loaded_document.parser_name,
        len(loaded_document.sections),
        preferred_splitter,
        knowledge_base,
        source_path or '',
    )
    if existing_document is None:
        document = Document(
            knowledge_base=knowledge_base,
            filename=loaded_document.filename,
            file_type=_infer_file_type(loaded_document.filename),
            source_path=source_path,
            file_size=file_size,
            status='uploaded',
            summary=f'parser={loaded_document.parser_name}',
        )
        db.add(document)
        db.flush()
    else:
        document = existing_document
        document.knowledge_base = knowledge_base
        document.filename = loaded_document.filename
        document.file_type = _infer_file_type(loaded_document.filename)
        document.source_path = source_path
        document.file_size = file_size
        document.status = 'uploaded'
        document.summary = f'parser={loaded_document.parser_name}'
        db.flush()

    chunk_models: list[Chunk] = []
    global_chunk_index = 0
    section_splitter_summary: list[dict[str, object]] = []
    for section_position, section in enumerate(loaded_document.sections, start=1):
        splitter_name, split_chunks = _split_section(
            text=section.text,
            file_type=document.file_type,
            section_metadata=section.metadata,
            preferred_splitter=preferred_splitter,
        )
        section_splitter_summary.append(
            {
                'section_no': section_position,
                'section_type': section.metadata.get('section_type'),
                'section_title': section.metadata.get('section_title'),
                'page_number': section.metadata.get('page_number'),
                'splitter': splitter_name,
                'chunk_count': len(split_chunks),
                'ocr_used': section.metadata.get('ocr_used', False),
            }
        )
        logger.info(
            '[SPLITTER] selected: file=%s section_no=%s section_type=%s section_title=%r page_number=%s splitter=%s chunk_count=%s ocr_used=%s',
            loaded_document.filename,
            section_position,
            section.metadata.get('section_type'),
            section.metadata.get('section_title'),
            section.metadata.get('page_number'),
            splitter_name,
            len(split_chunks),
            section.metadata.get('ocr_used', False),
        )
        for split_chunk in split_chunks:
            metadata = _build_chunk_metadata(
                document=document,
                knowledge_base=knowledge_base,
                parser_name=loaded_document.parser_name,
                section_metadata=section.metadata,
                chunk_index=global_chunk_index,
                filename=loaded_document.filename,
                splitter_name=splitter_name,
            )
            chunk_model = Chunk(
                document_id=document.id,
                chunk_index=global_chunk_index,
                content=split_chunk.content,
                metadata_json=metadata,
                token_count=estimate_token_count(split_chunk.content),
                page_number=int(section.metadata['page_number']) if section.metadata.get('page_number') is not None else None,
                start_offset=split_chunk.start_offset,
                end_offset=split_chunk.end_offset,
            )
            chunk_models.append(chunk_model)
            global_chunk_index += 1

    db.add_all(chunk_models)
    db.flush()

    if chunk_models:
        vector_store = get_vector_store()
        texts = [chunk.content for chunk in chunk_models]
        metadatas: list[dict] = []
        for chunk in chunk_models:
            metadata = dict(chunk.metadata_json)
            metadata['chunk_id'] = chunk.id
            metadatas.append(metadata)

        vector_ids = vector_store.add_texts(texts=texts, metadatas=metadatas)
        for chunk, vector_id in zip(chunk_models, vector_ids, strict=False):
            chunk.vector_id = str(vector_id)
            chunk.metadata_json = {
                **chunk.metadata_json,
                'chunk_id': chunk.id,
                'vector_id': chunk.vector_id,
            }

    document.chunk_count = len(chunk_models)
    document.status = 'indexed' if chunk_models else 'parsed'
    document.summary = f'parser={loaded_document.parser_name}; splitter={preferred_splitter or "auto"}'
    logger.info(
        '[INGEST] completed: document_id=%s file=%s parser=%s chunk_count=%s status=%s split_summary=%s',
        document.id,
        loaded_document.filename,
        loaded_document.parser_name,
        len(chunk_models),
        document.status,
        section_splitter_summary,
    )
    return document


def ingest_text_document(
    db: Session,
    *,
    filename: str,
    content: str,
    knowledge_base: str = 'default',
    preferred_splitter: str | None = None,
) -> Document:
    """把一段文本完整走完“文档 -> chunk -> 向量索引”的基础链路。"""

    cleaned_content = clean_text(content)
    if not cleaned_content:
        raise ValueError('Document content cannot be empty')

    loaded_document = build_loaded_document_from_text(filename, cleaned_content)
    return ingest_loaded_document(
        db,
        loaded_document=loaded_document,
        knowledge_base=knowledge_base,
        file_size=len(cleaned_content.encode('utf-8')),
        preferred_splitter=preferred_splitter,
    )


def ingest_file_document(
    db: Session,
    *,
    file_path: str | Path,
    original_filename: str,
    knowledge_base: str = 'default',
    file_size: int | None = None,
    preferred_splitter: str | None = None,
) -> Document:
    """从本地文件路径加载文档并完成入库。"""

    loaded_document = load_document(file_path)
    loaded_document.filename = original_filename
    return ingest_loaded_document(
        db,
        loaded_document=loaded_document,
        knowledge_base=knowledge_base,
        source_path=str(file_path),
        file_size=file_size,
        preferred_splitter=preferred_splitter,
    )


def rebuild_document_chunks(
    db: Session,
    *,
    document: Document,
    preferred_splitter: str | None = None,
) -> Document:
    """重建文档的 chunk 与向量索引。"""

    existing_chunks = db.execute(select(Chunk).where(Chunk.document_id == document.id)).scalars().all()
    _delete_chunk_vectors(existing_chunks)
    db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    db.flush()

    if document.source_path:
        loaded_document = load_document(document.source_path)
        loaded_document.filename = document.filename
        document_file_size = document.file_size
    else:
        full_text = '\n\n'.join(chunk.content for chunk in sorted(existing_chunks, key=lambda item: item.chunk_index))
        loaded_document = build_loaded_document_from_text(document.filename, full_text)
        document_file_size = len(full_text.encode('utf-8'))

    rebuilt_document = ingest_loaded_document(
        db,
        loaded_document=loaded_document,
        knowledge_base=document.knowledge_base,
        source_path=document.source_path,
        file_size=document_file_size,
        preferred_splitter=preferred_splitter,
        existing_document=document,
    )
    return rebuilt_document
