from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreateRequest(BaseModel):
    """通过纯文本快速入库的请求体。"""

    filename: str = Field(description='文档文件名，仅用于展示与类型推断')
    content: str = Field(description='文档正文内容')
    knowledge_base: str = Field(default='default', description='目标知识库名称')
    preferred_splitter: str | None = Field(default=None, description='可选的切分策略：structured / semi_structured / unstructured')


class DocumentItem(BaseModel):
    """文档列表项。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base: str
    filename: str
    file_type: str
    source_path: str | None
    file_size: int | None
    status: str
    chunk_count: int
    summary: str | None
    created_at: datetime
    updated_at: datetime


class DocumentIngestResponse(BaseModel):
    """文档入库响应。"""

    document: DocumentItem
    message: str = Field(default='Document ingested successfully')


class DocumentUploadResponse(BaseModel):
    """文件上传并入库响应，batch-upload 时单个失败会返回 error 而非抛异常。"""

    document: DocumentItem | None = Field(default=None, description='成功入库的文档信息')
    message: str = Field(default='Document uploaded and ingested successfully')
    error: str | None = Field(default=None, description='此文件处理失败时的错误信息')


class DocumentRebuildRequest(BaseModel):
    """文档重建索引请求体。"""

    preferred_splitter: str | None = Field(default=None, description='强制指定切分策略，不传则自动判断')


class SplitterOptionItem(BaseModel):
    """切分策略选项。"""

    name: str
    description: str
