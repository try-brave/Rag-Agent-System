from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.agent.memory import initialize_checkpointer, shutdown_checkpointer
from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.core.milvus_client import get_milvus_client
from app.core.postgres import get_engine
from app.core.redis_client import get_redis_client
from app.middleware import register_middlewares
from app.models import Base
from app.rag.bm25_index import get_bm25_index
from app.schemas.common import HealthResponse, ServiceHealthItem
from app.utils.logger import configure_logging
from app.utils.storage import ensure_upload_dir

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


def _build_health_response() -> HealthResponse:
    """汇总基础依赖健康状态。

    这里拆成独立函数而不是把逻辑全部堆在路由里，是为了后续：
    - CLI 自检；
    - 启动探活；
    - 看板埋点
    都能复用同一套检测逻辑。
    """

    postgres_ok = False
    redis_ok = False
    milvus_ok = False

    postgres_error = None
    redis_error = None
    milvus_error = None

    try:
        with get_engine().connect() as conn:
            conn.execute(text('SELECT 1'))
        postgres_ok = True
    except Exception as exc:  # noqa: BLE001
        postgres_error = str(exc)

    try:
        redis_ok = bool(get_redis_client().ping())
    except Exception as exc:  # noqa: BLE001
        redis_error = str(exc)

    try:
        client = get_milvus_client()
        client.list_collections()
        milvus_ok = True
    except Exception as exc:  # noqa: BLE001
        milvus_error = str(exc)

    return HealthResponse(
        ok=postgres_ok and redis_ok and milvus_ok,
        services={
            'postgres': ServiceHealthItem(ok=postgres_ok, error=postgres_error),
            'redis': ServiceHealthItem(ok=redis_ok, error=redis_error),
            'milvus': ServiceHealthItem(ok=milvus_ok, error=milvus_error),
        },
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期钩子。

    当前仅做轻量预热和日志输出，不在启动阶段强制探测远端依赖，
    这样即使某个外部服务暂时不可用，接口服务本身依旧可以先启动起来。
    """

    _warm_up_singletons(settings)
    logger.info('Application started: %s (%s)', settings.app_name, settings.app_env)
    yield
    shutdown_checkpointer()
    logger.info('Application stopped: %s', settings.app_name)


def _warm_up_singletons(app_settings: Settings) -> None:
    """预热关键单例。

    这里的预热是“构建对象”而不是“强依赖连通性校验”。
    真正的连通性检查交给 `/health`，从而降低启动阶段的耦合。
    """

    _ = app_settings
    engine = get_engine()
    # 第一版先用 `create_all` 确保最基础表结构存在，方便本地快速启动验证。
    # 后续接入 Alembic 后，迁移脚本仍然是正式环境的首选方案。
    Base.metadata.create_all(bind=engine)
    ensure_upload_dir()
    get_redis_client()
    get_milvus_client()
    get_bm25_index()
    initialize_checkpointer()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    openapi_url=f'{settings.api_v1_prefix}/openapi.json',
    docs_url=f'{settings.api_v1_prefix}/docs',
    redoc_url=f'{settings.api_v1_prefix}/redoc',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
register_middlewares(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get('/health', response_model=HealthResponse, tags=['system'])
def health_check() -> HealthResponse:
    """返回 PostgreSQL、Redis、Milvus 的健康状态。"""

    return _build_health_response()
