from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalSearchRequest(BaseModel):
    """检索调试请求体。"""

    query: str = Field(description='用户检索问题')
    top_k: int = Field(default=5, ge=1, le=20, description='返回结果数量')


class RetrievalHitItem(BaseModel):
    """单条检索命中结果。"""

    chunk_id: str | None = None
    document_id: str | None = None
    filename: str | None = None
    file_type: str | None = None
    chunk_index: int | None = None
    content: str
    score: float
    vector_score: float | None = None
    bm25_score: float | None = None
    fused_score: float | None = None
    retrieval_source: str | None = None
    retrieval_sources: list[str] = Field(default_factory=list)
    rank_vector: int | None = None
    rank_bm25: int | None = None
    rank_fused: int | None = None
    splitter_name: str | None = None
    parser_name: str | None = None
    section_type: str | None = None
    section_title: str | None = None
    page_number: int | None = None
    source_path: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None


class RetrievalSearchResponse(BaseModel):
    """检索调试响应体。"""

    items: list[RetrievalHitItem] = Field(default_factory=list)
