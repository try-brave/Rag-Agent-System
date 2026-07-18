from __future__ import annotations

from functools import lru_cache

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings

from app.config import get_settings


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    """返回 Embedding 模型单例。

    Embedding 实例通常会在如下场景频繁复用：
    - 文档入库时批量向量化；
    - 查询时把用户问题编码成向量；
    - 可能的重建索引任务。

    因此这里使用单例缓存，避免重复初始化客户端。
    """

    settings = get_settings()
    return DashScopeEmbeddings(
        model=settings.embedding_model,
        dashscope_api_key=settings.dashscope_api_key,
    )
