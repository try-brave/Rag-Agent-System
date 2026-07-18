from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document


class Chunk(Base, TimestampMixin):
    """切分块表。

    这是实现“切分可视化”和“答案溯源”的关键表：
    - `content` 保存切分后的文本；
    - `metadata_json` 保存页码、标题层级、切分策略等附加信息；
    - `vector_id` 记录向量库中的对应主键，方便反查与重建索引。
    """

    __tablename__ = 'chunk'

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment='Chunk 主键，使用 UUID 便于后续跨表引用',
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey('document.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='所属文档 ID',
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, comment='在同一文档中的顺序编号')
    content: Mapped[str] = mapped_column(Text, nullable=False, comment='切分后的正文内容')
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment='扩展元数据，例如标题、来源页、切分策略、标签等',
    )
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment='预估 token 数量')
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='来源页码，适用于 PDF 等分页文档')
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='在原文中的起始偏移量')
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='在原文中的结束偏移量')
    vector_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment='Milvus 中对应向量记录 ID')
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment='是否参与检索，禁用后可用于人工排除脏数据',
    )

    document: Mapped['Document'] = relationship('Document', back_populates='chunks')
