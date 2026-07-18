from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkItem(BaseModel):
    """Chunk 列表项与详情项。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_index: int
    content: str
    metadata_json: dict[str, Any]
    token_count: int
    page_number: int | None
    start_offset: int | None
    end_offset: int | None
    vector_id: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ChunkUpdateRequest(BaseModel):
    """Chunk 编辑请求体。"""

    content: str | None = Field(default=None, description='更新后的 chunk 文本')
    enabled: bool | None = Field(default=None, description='是否参与检索')
    metadata_json: dict[str, Any] | None = Field(default=None, description='需要合并到元数据中的附加字段')
