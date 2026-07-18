from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求体。"""

    session_id: str = Field(description='会话 ID，用于多轮记忆的 thread_id')
    message: str = Field(description='用户问题')
    top_k: int = Field(default=5, ge=1, le=8, description='知识库检索结果数量上限')


class SourceChunkItem(BaseModel):
    """答案溯源条目。"""

    ref_id: int
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


class ChatResponse(BaseModel):
    """同步聊天响应。"""

    session_id: str
    answer: str
    route: str = 'agent_rag'
    latency_ms: int
    source_chunks: list[SourceChunkItem] = Field(default_factory=list)
    created_at: datetime


class ChatHistoryItem(BaseModel):
    """单轮会话历史记录。"""

    id: str
    session_id: str | None = None
    user_question: str
    answer: str | None = None
    route: str
    latency_ms: int | None = None
    source_chunks: list[SourceChunkItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SessionSummaryItem(BaseModel):
    """会话摘要列表项。"""

    session_id: str
    latest_question: str
    latest_answer: str | None = None
    message_count: int
    updated_at: datetime


class SessionClearResponse(BaseModel):
    """清空会话后的响应。"""

    session_id: str
    deleted_query_log_count: int
    cleared_memory: bool
