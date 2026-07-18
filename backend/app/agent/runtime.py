from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Generator

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievalTrace:
    """记录一次 Agent 调用过程中产生的检索溯源信息。"""

    top_k: int = 5
    source_chunks: list[dict] = field(default_factory=list)


_current_retrieval_trace: ContextVar[RetrievalTrace | None] = ContextVar(
    'current_retrieval_trace',
    default=None,
)


@contextmanager
def bind_retrieval_trace(trace: RetrievalTrace) -> Generator[RetrievalTrace, None, None]:
    """把当前请求的检索溯源容器绑定到上下文。

    之所以使用 `contextvars` 而不是全局变量，是为了保证：
    - 多请求并发时互不串数据；
    - Agent 工具函数无需感知 FastAPI 请求对象；
    - 以后切到异步工具或更多工具时仍然能复用同一机制。
    """

    token: Token[RetrievalTrace | None] = _current_retrieval_trace.set(trace)
    try:
        yield trace
    finally:
        try:
            _current_retrieval_trace.reset(token)
        except ValueError:
            # StreamingResponse may resume/close the generator in a different context.
            # In that case, best-effort clear the current trace instead of failing the whole request.
            logger.warning('Retrieval trace token reset crossed context boundary; falling back to clear current trace')
            _current_retrieval_trace.set(None)


def get_current_retrieval_trace() -> RetrievalTrace | None:
    """返回当前上下文中绑定的检索溯源容器。"""

    return _current_retrieval_trace.get()
