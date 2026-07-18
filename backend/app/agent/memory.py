from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except Exception:  # noqa: BLE001
    PostgresSaver = None  # type: ignore[assignment]

_checkpointer: Any | None = None
_checkpointer_context_manager: Any | None = None
"""
"""

def _normalize_checkpointer_dsn(dsn: str) -> str:
    """把 SQLAlchemy 风格的 DSN 转回 checkpointer 可直接使用的形式。"""

    if dsn.startswith('postgresql+psycopg://'):
        return 'postgresql://' + dsn[len('postgresql+psycopg://'):]
    return dsn


def initialize_checkpointer() -> Any:
    """初始化 Agent 短期记忆存储。

    设计策略：
    - 优先使用 PostgreSQL checkpointer，满足多轮对话持久化；
    - 如果运行环境缺少依赖或初始化失败，则自动降级到内存版，
      确保本地开发和最小演示链路始终可用。
    """

    global _checkpointer, _checkpointer_context_manager

    if _checkpointer is not None:
        return _checkpointer

    settings = get_settings()
    if PostgresSaver is not None:
        try:
            _checkpointer_context_manager = PostgresSaver.from_conn_string(
                _normalize_checkpointer_dsn(settings.postgres_dsn)
            )
            # def _normalize_checkpointer_dsn(dsn: str) -> str:
            #     """把 SQLAlchemy 风格的 DSN 转回 checkpointer 可直接使用的形式。"""
            #
            #     if dsn.startswith('postgresql+psycopg://'):
            #         return 'postgresql://' + dsn[len('postgresql+psycopg://'):]
            #     return dsn
            _checkpointer = _checkpointer_context_manager.__enter__()
            _checkpointer.setup()
            logger.info('Using PostgreSQL checkpointer for agent memory')
            return _checkpointer
        except Exception as exc:  # noqa: BLE001
            logger.warning('Failed to initialize PostgreSQL checkpointer: %s', exc)
            if _checkpointer_context_manager is not None:
                try:
                    _checkpointer_context_manager.__exit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass
                _checkpointer_context_manager = None

    _checkpointer = InMemorySaver()
    logger.info('Using in-memory checkpointer for agent memory')
    return _checkpointer


def get_checkpointer() -> Any:
    """返回已初始化的 checkpointer。"""

    return initialize_checkpointer()


def clear_thread_memory(thread_id: str) -> bool:
    """清空指定会话线程的短期记忆。

    返回值表示是否成功执行了删除操作。这里做宽松兼容：
    - PostgreSQL checkpointer 提供 `delete_thread`；
    - 内存版若未来接口变动，也只会返回 `False`，不会影响主流程。
    """

    checkpointer = get_checkpointer()
    delete_thread = getattr(checkpointer, 'delete_thread', None)
    if delete_thread is None:
        logger.warning('Current checkpointer does not support delete_thread')
        return False

    delete_thread(thread_id)
    return True


def shutdown_checkpointer() -> None:
    """释放 checkpointer 持有的外部资源。"""

    global _checkpointer, _checkpointer_context_manager

    if _checkpointer_context_manager is not None:
        try:
            _checkpointer_context_manager.__exit__(None, None, None)
        except Exception as exc:  # noqa: BLE001
            logger.warning('Failed to close checkpointer cleanly: %s', exc)

    _checkpointer = None
    _checkpointer_context_manager = None
