from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QueryLog(Base, TimestampMixin):
    """查询日志表。

    这张表暂时先保留最基础的埋点字段，后续可以直接扩展到：
    - dashboard 看板统计；
    - 检索质量分析；
    - 对话链路排错与审计。
    """

    __tablename__ = 'query_log'

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment='查询日志主键',
    )
    session_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment='会话 ID，用于串联多轮对话',
    )
    user_question: Mapped[str] = mapped_column(Text, nullable=False, comment='用户原始问题')
    answer: Mapped[str | None] = mapped_column(Text, nullable=True, comment='系统最终回答')
    route: Mapped[str] = mapped_column(
        String(50),
        default='rag',
        nullable=False,
        comment='命中的处理链路，例如 rag/sql/web',
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='本次处理耗时，单位毫秒')
    source_chunks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment='回答引用到的 chunk 摘要，用于看板与审计',
    )
