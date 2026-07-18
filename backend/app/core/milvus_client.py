from __future__ import annotations

from functools import lru_cache

from langchain_milvus import Milvus
from pymilvus import MilvusClient

from app.config import get_settings
from app.core.embeddings import get_embeddings


def _build_connection_args() -> dict[str, str]:
    """统一构造 Milvus 连接参数。

    这样做的好处是：
    - 原生 `MilvusClient` 和 LangChain `Milvus` 向量库共用同一份配置；
    - 后续如果增加认证参数，只需要改一个地方。
    """

    settings = get_settings()
    return {'uri': settings.resolved_milvus_uri}


@lru_cache(maxsize=1)
def get_milvus_client() -> MilvusClient:
    """返回 Milvus 原生客户端单例。

    原生客户端更适合做 collection 管理、索引检查和底层运维操作；
    LangChain 的 `Milvus` 封装则更适合做 RAG 检索。
    两者会在后续阶段同时用到，因此这里都提前准备好。
    """

    return MilvusClient(**_build_connection_args())


def get_vector_store(collection_name: str | None = None) -> Milvus:
    """创建 LangChain Milvus 向量库实例。

    这里不做缓存，是因为后续可能按知识库动态切换 collection。
    每次根据传入的 `collection_name` 构造实例，行为更直观。
    """

    settings = get_settings()
    return Milvus(
        embedding_function=get_embeddings(),
        collection_name=collection_name or settings.milvus_collection,
        connection_args=_build_connection_args(),
        index_params={'index_type': 'AUTOINDEX', 'metric_type': 'COSINE'},
        auto_id=True,
    )
