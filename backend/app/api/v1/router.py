from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.chunks import router as chunks_router
from app.api.v1.documents import router as documents_router
from app.api.v1.retrieval import router as retrieval_router

api_router = APIRouter()

# 所有 v1 接口统一在这里汇总，后续新增 chat/sql/dashboard 也继续按这个入口挂载。
api_router.include_router(documents_router)
api_router.include_router(chunks_router)
api_router.include_router(retrieval_router)
api_router.include_router(chat_router)
