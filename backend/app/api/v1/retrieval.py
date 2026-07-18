from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_database
from app.schemas.retrieval import RetrievalHitItem, RetrievalSearchRequest, RetrievalSearchResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix='/retrieval', tags=['retrieval'])


@router.post('/search', response_model=RetrievalSearchResponse)
def search_chunks(
    request: RetrievalSearchRequest,
    db: Session = Depends(get_database),
) -> RetrievalSearchResponse:
    """返回最基础的检索命中列表，用于前端检索调试台。"""

    service = RetrievalService(db)
    results = service.search(query=request.query, top_k=request.top_k)
    return RetrievalSearchResponse(items=[RetrievalHitItem.model_validate(item) for item in results])
