from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.chunk import Chunk


class Document(Base, TimestampMixin):
    """文档主表。

    这张表保存“文档级”元信息，不保存切分后的明细内容。
    这样可以把文档管理、切分管理、检索调试三个模块拆开处理。
    """

    __tablename__ = 'document'

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment='文档主键，使用 UUID 便于分布式场景扩展',
    )
    knowledge_base: Mapped[str] = mapped_column(
        String(100),
        default='default',
        nullable=False,
        comment='所属知识库名称，后续可支持多知识库隔离',
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, comment='原始文件名')
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, comment='文件类型，例如 pdf/docx/md/txt')
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True, comment='文件在服务器上的存储路径')
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment='文件大小，单位字节')
    status: Mapped[str] = mapped_column(
        String(32),
        default='uploaded',
        nullable=False,
        comment='文档当前状态，例如 uploaded/parsed/indexed/failed',
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment='当前文档已生成的 chunk 数量，便于管理页快速展示',
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment='可选的文档摘要或说明')

    # 删除文档时级联删除其所有 chunk，避免产生孤儿数据。
    chunks: Mapped[list['Chunk']] = relationship(
        'Chunk',
        back_populates='document',
        cascade='all, delete-orphan',
    )
