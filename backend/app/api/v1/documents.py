from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_database
from app.schemas.chunk import ChunkItem
from app.schemas.document import (
    DocumentCreateRequest,
    DocumentIngestResponse,
    DocumentItem,
    DocumentRebuildRequest,
    DocumentUploadResponse,
    SplitterOptionItem,
)
from app.services.chunk_service import ChunkService
from app.services.document_service import DocumentService
from app.utils.storage import save_upload_file

router = APIRouter(prefix='/documents', tags=['documents'])


@router.post('/ingest-text', response_model=DocumentIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_text_document(request: DocumentCreateRequest, db: Session = Depends(get_database)) -> DocumentIngestResponse:
    """通过纯文本快速创建文档并完成切分入库。"""

    service = DocumentService(db)
    try:
        document = service.ingest_text(
            filename=request.filename,
            content=request.content,
            knowledge_base=request.knowledge_base,
            preferred_splitter=request.preferred_splitter,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentIngestResponse(document=DocumentItem.model_validate(document))


@router.post('/upload', response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(description='上传的文档文件，支持 txt/md/pdf/doc/docx；PDF/Word 会在必要时自动尝试 OCR 解析'),
    knowledge_base: str = Form(default='default'),
    preferred_splitter: str | None = Form(default=None),
    db: Session = Depends(get_database),
) -> DocumentUploadResponse:
    """上传文件并完成解析、切分与向量入库。"""

    stored_path, file_size = await save_upload_file(file)
    service = DocumentService(db)
    try:
        document = service.ingest_file(
            file_path=stored_path,
            original_filename=file.filename or stored_path.name,
            knowledge_base=knowledge_base,
            file_size=file_size,
            preferred_splitter=preferred_splitter,
        )
    except ValueError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentUploadResponse(document=DocumentItem.model_validate(document))


@router.get('', response_model=list[DocumentItem])
def list_documents(db: Session = Depends(get_database)) -> list[DocumentItem]:
    """返回文档列表。"""

    service = DocumentService(db)
    documents = service.list_documents()
    return [DocumentItem.model_validate(document) for document in documents]


@router.get('/splitters/options', response_model=list[SplitterOptionItem])
def list_splitter_options(db: Session = Depends(get_database)) -> list[SplitterOptionItem]:
    """返回当前支持的切分策略列表。"""

    service = DocumentService(db)
    return [SplitterOptionItem.model_validate(item) for item in service.list_splitter_options()]


@router.get('/{document_id}', response_model=DocumentItem)
def get_document(document_id: str, db: Session = Depends(get_database)) -> DocumentItem:
    """返回单个文档详情。"""

    service = DocumentService(db)
    document = service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')
    return DocumentItem.model_validate(document)


@router.delete('/{document_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_database)) -> None:
    """物理删除整个文档，级联删除 Chunk 和向量。"""

    service = DocumentService(db)
    if not service.delete_document(document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')


@router.get('/{document_id}/chunks', response_model=list[ChunkItem])
def list_document_chunks(document_id: str, db: Session = Depends(get_database)) -> list[ChunkItem]:
    """返回指定文档的全部 chunk，方便前端直接展示切分结果。"""

    document_service = DocumentService(db)
    if document_service.get_document(document_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    chunk_service = ChunkService(db)
    chunks = chunk_service.list_chunks(document_id=document_id, limit=1000)
    return [ChunkItem.model_validate(chunk) for chunk in chunks]


@router.post('/{document_id}/rebuild-index', response_model=DocumentIngestResponse)
def rebuild_document_index(
    document_id: str,
    request: DocumentRebuildRequest,
    db: Session = Depends(get_database),
) -> DocumentIngestResponse:
    """按指定或自动策略重新切分文档并重建向量索引。"""

    service = DocumentService(db)
    document = service.rebuild_index(document_id, preferred_splitter=request.preferred_splitter)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')
    return DocumentIngestResponse(
        document=DocumentItem.model_validate(document),
        message='Document chunks and vector index rebuilt successfully',
    )
