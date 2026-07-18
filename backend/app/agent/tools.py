from __future__ import annotations

import logging

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from langchain.tools import tool

from app.agent.runtime import get_current_retrieval_trace
from app.core.postgres import get_session_factory
from app.rag.retriever import retrieve_chunks

logger = logging.getLogger(__name__)


class SearchKnowledgeBaseInput(BaseModel):
    """知识库检索工具输入。"""

    query: str = Field(description='需要检索的用户问题或关键词')
    top_k: int = Field(default=5, ge=1, le=8, description='返回最相关的片段数量')


def _truncate_content(content: str, max_length: int = 400) -> str:
    """把工具返回内容裁剪到适合模型阅读的长度。"""

    normalized = ' '.join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length].rstrip() + '...'


@tool(args_schema=SearchKnowledgeBaseInput)
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """检索知识库中与问题最相关的内容片段，并返回可引用的来源编号。

    使用场景：
    - 用户询问项目文档、系统规范、配置说明、知识库内容；
    - 需要基于已入库的 chunk 回答问题；
    - 需要给最终答案附带可追溯来源。
    """

    session_factory = get_session_factory()
    with session_factory() as db:
        db: Session
        trace = get_current_retrieval_trace()
        effective_top_k = min(top_k, trace.top_k) if trace is not None else top_k
        logger.info(
            '[TOOL][KB] called: query=%r requested_top_k=%s effective_top_k=%s trace_bound=%s',
            query,
            top_k,
            effective_top_k,
            trace is not None,
        )
        hits = retrieve_chunks(db, query=query, top_k=effective_top_k)

    if not hits:
        logger.info('[TOOL][KB] no hits: query=%r effective_top_k=%s', query, effective_top_k)
        if trace is not None:
            trace.source_chunks = []
        return '未检索到相关知识库内容。'

    normalized_hits: list[dict] = []
    lines: list[str] = []
    for index, hit in enumerate(hits, start=1):
        normalized_hit = {
            **hit,
            'ref_id': index,
            'content': _truncate_content(hit['content']),
        }
        normalized_hits.append(normalized_hit)
        lines.append(
            '\n'.join(
                [
                    f'[{index}] filename={hit.get("filename") or "unknown"}',
                    f'chunk_id={hit.get("chunk_id") or "unknown"}',
                    f'chunk_index={hit.get("chunk_index")}',
                    f'page_number={hit.get("page_number")}',
                    f'retrieval_source={hit.get("retrieval_source")}',
                    f'score={hit.get("score")}',
                    f'vector_score={hit.get("vector_score")}',
                    f'bm25_score={hit.get("bm25_score")}',
                    f'fused_score={hit.get("fused_score")}',
                    f'content={normalized_hit["content"]}',
                ]
            )
        )

    if trace is not None:
        trace.source_chunks = normalized_hits
    logger.info(
        '[TOOL][KB] returning hits: query=%r hit_count=%s preview=%s',
        query,
        len(normalized_hits),
        [
            {
                'ref_id': item.get('ref_id'),
                'chunk_id': item.get('chunk_id'),
                'filename': item.get('filename'),
                'retrieval_source': item.get('retrieval_source'),
                'score': item.get('score'),
                'vector_score': item.get('vector_score'),
                'bm25_score': item.get('bm25_score'),
                'fused_score': item.get('fused_score'),
                'content_preview': item.get('content', '')[:120],
            }
            for item in normalized_hits[:3]
        ],
    )

    return '\n\n'.join(lines)


def get_agent_tools() -> list:
    """返回 Agent 可用工具列表。"""

    return [search_knowledge_base]
