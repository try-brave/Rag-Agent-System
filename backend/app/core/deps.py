from __future__ import annotations

from collections.abc import Generator

from redis import Redis
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.postgres import get_db
from app.core.redis_client import get_redis_client


def get_app_settings() -> Settings:
    """FastAPI 依赖：返回已校验过的全局配置。"""

    return get_settings()


def get_redis() -> Redis:
    """FastAPI 依赖：返回 Redis 单例客户端。"""

    return get_redis_client()


def get_database() -> Generator[Session, None, None]:
    """FastAPI 依赖：把数据库 Session 注入到接口层。"""

    yield from get_db()
