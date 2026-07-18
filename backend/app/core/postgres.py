from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _normalize_sqlalchemy_dsn(dsn: str) -> str:
    """把通用 PostgreSQL DSN 转成 SQLAlchemy 推荐方言。

    用户通常会在 `.env` 中写 `postgresql://...`。
    但当前项目依赖的是 `psycopg` v3，SQLAlchemy 更推荐显式写成
    `postgresql+psycopg://...`，这样驱动选择更清晰。
    """

    if dsn.startswith('postgresql://'):
        return 'postgresql+psycopg://' + dsn[len('postgresql://'):]
    return dsn


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """创建 SQLAlchemy Engine 单例。

    `pool_pre_ping=True` 可以在连接池返回连接前先做一次轻量探测，
    避免长时间闲置后拿到失效连接。
    """

    settings = get_settings()
    return create_engine(
        _normalize_sqlalchemy_dsn(settings.postgres_dsn),
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """返回 Session 工厂单例。

    - `autoflush=False`：显式提交前不自动刷盘，减少隐式 SQL。
    - `expire_on_commit=False`：提交后对象仍可继续访问，便于 service 层返回数据。
    """

    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI 数据库依赖。

    每次请求拿到一个独立 Session，请求结束后统一关闭，
    这是最稳定且容易理解的后端事务管理方式。
    """

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
