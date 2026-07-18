from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generator

from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import delete, desc, func, select

from app.agent.memory import clear_thread_memory
from app.agent.graph import get_rag_agent
from app.agent.runtime import RetrievalTrace, bind_retrieval_trace
from app.core.postgres import get_session_factory
from app.models.query_log import QueryLog
from app.rag.retriever import retrieve_chunks
from app.schemas.chat import (
    ChatHistoryItem,
    ChatResponse,
    SessionClearResponse,
    SessionSummaryItem,
    SourceChunkItem,
)
from app.utils.sse import format_sse_event

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatRunResult:
    """一次对话调用的标准化结果。"""

    session_id: str
    answer: str
    latency_ms: int
    source_chunks: list[dict]
    route: str = 'agent_rag'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ChatService:
    """对话服务。

    这里把 Agent 调用、SSE 适配、日志记录统一放在 service 层，
    避免 API 层直接处理 LangChain / LangGraph 的细节。
    """

    def __init__(self) -> None:
        self.agent = get_rag_agent()
        self.session_factory = get_session_factory()

    def _build_agent_input(self, message: str, prefetched_chunks: list[dict] | None = None) -> dict:
        """把用户文本包装成 Agent 标准输入格式。"""

        messages: list[dict[str, str]] = []
        if prefetched_chunks:
            messages.append(
                {
                    'role': 'system',
                    'content': (
                        '以下是系统在回答前已从知识库中检索到的高相关片段，请优先基于这些内容回答。'
                        '如果这些片段与问题直接相关，请优先引用它们，并使用 `[1]`、`[2]` 这样的编号标记来源。\n\n'
                        f'{self._format_prefetched_context(prefetched_chunks)}'
                    ),
                }
            )
        messages.append({'role': 'user', 'content': message})
        return {'messages': messages}

    def _build_agent_config(self, session_id: str) -> dict:
        """构建 Agent 运行配置。

        根据 LangChain / LangGraph 1.x 的推荐方式，使用 `thread_id`
        作为多轮记忆的主键，把同一会话的上下文串起来。
        """

        return {'configurable': {'thread_id': session_id}}

    def _extract_final_answer(self, result: dict) -> str:
        """从 Agent 返回状态中提取最后一条 AI 回复。"""

        messages = result.get('messages', [])
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                content = message.text if hasattr(message, 'text') else str(message.content)
                if content.strip():
                    return content.strip()
        return ''

    def _format_prefetched_context(self, prefetched_chunks: list[dict]) -> str:
        """把预检索到的片段压缩成适合模型消费的上下文。"""

        lines: list[str] = []
        for index, item in enumerate(prefetched_chunks[:5], start=1):
            lines.append(
                '\n'.join(
                    [
                        f'[{index}] filename={item.get("filename") or "unknown"}',
                        f'chunk_id={item.get("chunk_id") or "unknown"}',
                        f'chunk_index={item.get("chunk_index")}',
                        f'page_number={item.get("page_number")}',
                        f'retrieval_source={item.get("retrieval_source")}',
                        f'score={item.get("score")}',
                        f'content={str(item.get("content") or "")[:500]}',
                    ]
                )
            )
        return '\n\n'.join(lines)

    def _source_preview(self, source_chunks: list[dict]) -> list[dict]:
        return [
            {
                'ref_id': item.get('ref_id'),
                'chunk_id': item.get('chunk_id'),
                'filename': item.get('filename'),
                'retrieval_source': item.get('retrieval_source'),
                'score': item.get('score'),
                'vector_score': item.get('vector_score'),
                'bm25_score': item.get('bm25_score'),
                'fused_score': item.get('fused_score'),
            }
            for item in source_chunks[:3]
        ]

    def _normalize_source_chunks(self, source_chunks: list[dict]) -> list[dict]:
        """规范化来源字段，保证响应体和日志结构稳定。"""

        normalized_items: list[dict] = []
        for index, source_chunk in enumerate(source_chunks or [], start=1):
            normalized_items.append(
                {
                    'ref_id': int(source_chunk.get('ref_id', index)),
                    'chunk_id': source_chunk.get('chunk_id'),
                    'document_id': source_chunk.get('document_id'),
                    'filename': source_chunk.get('filename'),
                    'file_type': source_chunk.get('file_type'),
                    'chunk_index': source_chunk.get('chunk_index'),
                    'content': source_chunk.get('content', ''),
                    'score': float(source_chunk.get('score', 0.0)),
                    'vector_score': float(source_chunk['vector_score']) if source_chunk.get('vector_score') is not None else None,
                    'bm25_score': float(source_chunk['bm25_score']) if source_chunk.get('bm25_score') is not None else None,
                    'fused_score': float(source_chunk['fused_score']) if source_chunk.get('fused_score') is not None else None,
                    'retrieval_source': source_chunk.get('retrieval_source'),
                    'retrieval_sources': list(source_chunk.get('retrieval_sources') or []),
                    'rank_vector': source_chunk.get('rank_vector'),
                    'rank_bm25': source_chunk.get('rank_bm25'),
                    'rank_fused': source_chunk.get('rank_fused'),
                    'splitter_name': source_chunk.get('splitter_name'),
                    'parser_name': source_chunk.get('parser_name'),
                    'section_type': source_chunk.get('section_type'),
                    'section_title': source_chunk.get('section_title'),
                    'page_number': source_chunk.get('page_number'),
                    'source_path': source_chunk.get('source_path'),
                    'start_offset': source_chunk.get('start_offset'),
                    'end_offset': source_chunk.get('end_offset'),
                }
            )
        return normalized_items

    def _prefetch_source_chunks(self, *, message: str, top_k: int) -> list[dict]:
        """在进入 Agent 前先做一次确定性的知识库检索。"""

        with self.session_factory() as db:
            prefetched_hits = retrieve_chunks(db, query=message, top_k=top_k)
        normalized_hits = self._normalize_source_chunks(prefetched_hits)
        logger.info(
            '[CHAT] prefetch retrieval: query=%r top_k=%s hit_count=%s preview=%s',
            message,
            top_k,
            len(normalized_hits),
            self._source_preview(normalized_hits),
        )
        return normalized_hits

    def _persist_query_log(self, *, session_id: str, question: str, result: ChatRunResult) -> None:
        """把一次问答结果落到查询日志表。"""

        with self.session_factory() as db:
            query_log = QueryLog(
                session_id=session_id,
                user_question=question,
                answer=result.answer,
                route=result.route,
                latency_ms=result.latency_ms,
                source_chunks=result.source_chunks,
            )
            db.add(query_log)
            db.commit()

    def _serialize_history_item(self, query_log: QueryLog) -> ChatHistoryItem:
        """把数据库查询日志转成接口层响应对象。"""

        source_chunks = self._normalize_source_chunks(query_log.source_chunks)
        return ChatHistoryItem(
            id=query_log.id,
            session_id=query_log.session_id,
            user_question=query_log.user_question,
            answer=query_log.answer,
            route=query_log.route,
            latency_ms=query_log.latency_ms,
            source_chunks=[SourceChunkItem.model_validate(item) for item in source_chunks],
            created_at=query_log.created_at,
            updated_at=query_log.updated_at,
        )

    @contextmanager
    def _chat_run(self, *, top_k: int) -> Generator[RetrievalTrace, None, None]:
        """为一次问答绑定独立的检索溯源容器。"""

        trace = RetrievalTrace(top_k=top_k)
        with bind_retrieval_trace(trace):
            yield trace

    def invoke(self, *, session_id: str, message: str, top_k: int = 5) -> ChatResponse:
        """执行一次同步问答。"""

        started_at = time.perf_counter()
        logger.info(
            '[CHAT] invoke started: session=%s top_k=%s message_length=%s message_preview=%r',
            session_id,
            top_k,
            len(message),
            message[:120],
        )
        try:
            with self._chat_run(top_k=top_k) as trace:
                prefetched_chunks = self._prefetch_source_chunks(message=message, top_k=top_k)
                if prefetched_chunks:
                    trace.source_chunks = prefetched_chunks
                result = self.agent.invoke(
                    self._build_agent_input(message, prefetched_chunks),
                    config=self._build_agent_config(session_id),
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception('Chat invoke failed for session=%s', session_id)
            raise RuntimeError(f'Agent 对话执行失败: {exc}') from exc

        answer = self._extract_final_answer(result)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        source_chunks = self._normalize_source_chunks(trace.source_chunks)
        chat_result = ChatRunResult(
            session_id=session_id,
            answer=answer,
            latency_ms=latency_ms,
            source_chunks=source_chunks,
        )
        self._persist_query_log(session_id=session_id, question=message, result=chat_result)
        logger.info(
            '[CHAT] invoke finished: session=%s latency_ms=%s answer_length=%s source_chunk_count=%s source_preview=%s',
            session_id,
            latency_ms,
            len(answer),
            len(source_chunks),
            self._source_preview(source_chunks),
        )

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            latency_ms=latency_ms,
            source_chunks=[SourceChunkItem.model_validate(item) for item in source_chunks],
            created_at=chat_result.created_at,
        )

    def stream(self, *, session_id: str, message: str, top_k: int = 5) -> Generator[str, None, None]:
        """以 SSE 方式流式返回问答结果。"""

        started_at = time.perf_counter()
        answer_fragments: list[str] = []
        trace = RetrievalTrace(top_k=top_k)

        logger.info(
            '[CHAT] stream started: session=%s top_k=%s message_length=%s message_preview=%r',
            session_id,
            top_k,
            len(message),
            message[:120],
        )
        yield format_sse_event('status', {'phase': 'started', 'session_id': session_id})
        try:
            prefetched_chunks = self._prefetch_source_chunks(message=message, top_k=top_k)
            if prefetched_chunks:
                trace.source_chunks = prefetched_chunks
                yield format_sse_event(
                    'sources',
                    {
                        'items': prefetched_chunks,
                    },
                )
                yield format_sse_event(
                    'status',
                    {
                        'phase': 'retrieved',
                        'session_id': session_id,
                        'source_chunk_count': len(prefetched_chunks),
                    },
                )
            with bind_retrieval_trace(trace):
                logger.info(
                    '[CHAT] stream calling agent: session=%s thread_id=%s prefetched_hits=%s',
                    session_id,
                    self._build_agent_config(session_id).get('configurable', {}).get('thread_id'),
                    len(prefetched_chunks),
                )
                for stream_mode, chunk in self.agent.stream(
                    self._build_agent_input(message, prefetched_chunks),
                    config=self._build_agent_config(session_id),
                    stream_mode=['updates', 'messages'],
                ):
                    if stream_mode == 'messages':
                        token, metadata = chunk
                        if metadata.get('langgraph_node') != 'model':
                            continue
                        content_blocks = getattr(token, 'content_blocks', []) or []
                        for block in content_blocks:
                            if block.get('type') != 'text':
                                continue

                            text_delta = block.get('text', '')
                            if not text_delta:
                                continue

                            answer_fragments.append(text_delta)
                            yield format_sse_event('token', {'text': text_delta})
                        continue

                    if stream_mode != 'updates':
                        continue

                    update_chunk = chunk
                    for step_name, step_data in update_chunk.items():
                        messages = step_data.get('messages', [])
                        if not messages:
                            continue

                        latest_message = messages[-1]
                        if isinstance(latest_message, AIMessage):
                            tool_calls = latest_message.tool_calls or []
                            for tool_call in tool_calls:
                                yield format_sse_event(
                                    'tool_call',
                                    {
                                        'step': step_name,
                                        'tool_name': tool_call.get('name'),
                                        'tool_call_id': tool_call.get('id'),
                                        'args': tool_call.get('args'),
                                    },
                                )
                        elif isinstance(latest_message, ToolMessage):
                            tool_status = getattr(latest_message, 'status', 'success') or 'success'
                            yield format_sse_event(
                                'tool_error' if tool_status == 'error' else 'tool_result',
                                {
                                    'step': step_name,
                                    'tool_call_id': latest_message.tool_call_id,
                                    'status': tool_status,
                                    'content': str(latest_message.content),
                                },
                            )
        except Exception as exc:  # noqa: BLE001
            logger.exception('Chat stream failed for session=%s', session_id)
            yield format_sse_event(
                'error',
                {
                    'session_id': session_id,
                    'message': f'Agent 流式对话执行失败: {exc}',
                },
            )
            yield format_sse_event('done', {'session_id': session_id, 'ok': False})
            return

        answer = ''.join(answer_fragments).strip()
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        source_chunks = self._normalize_source_chunks(trace.source_chunks)
        logger.info(
            '[CHAT] stream finished: session=%s latency_ms=%s answer_length=%s source_chunk_count=%s source_preview=%s',
            session_id,
            latency_ms,
            len(answer),
            len(source_chunks),
            self._source_preview(source_chunks),
        )
        chat_result = ChatRunResult(
            session_id=session_id,
            answer=answer,
            latency_ms=latency_ms,
            source_chunks=source_chunks,
        )
        self._persist_query_log(session_id=session_id, question=message, result=chat_result)

        yield format_sse_event(
            'sources',
            {
                'items': source_chunks,
            },
        )
        yield format_sse_event(
            'done',
            {
                'session_id': session_id,
                'answer': answer,
                'route': chat_result.route,
                'latency_ms': latency_ms,
                'created_at': chat_result.created_at.isoformat(),
            },
        )

    def clear_session(self, session_id: str) -> SessionClearResponse:
        """清空会话日志，并尝试清空 Agent 短期记忆。"""

        with self.session_factory() as db:
            statement = delete(QueryLog).where(QueryLog.session_id == session_id)
            result = db.execute(statement)
            db.commit()

        cleared_memory = False
        try:
            cleared_memory = clear_thread_memory(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning('Failed to clear thread memory for session=%s: %s', session_id, exc)

        return SessionClearResponse(
            session_id=session_id,
            deleted_query_log_count=int(result.rowcount or 0),
            cleared_memory=cleared_memory,
        )

    def get_session_history(self, session_id: str, *, limit: int = 50) -> list[ChatHistoryItem]:
        """按会话 ID 返回最近的问答历史。"""

        with self.session_factory() as db:
            statement = (
                select(QueryLog)
                .where(QueryLog.session_id == session_id)
                .order_by(QueryLog.created_at.asc())
                .limit(limit)
            )
            query_logs = db.execute(statement).scalars().all()
        return [self._serialize_history_item(query_log) for query_log in query_logs]

    def list_sessions(self, *, limit: int = 50) -> list[SessionSummaryItem]:
        """返回会话摘要列表，便于前端展示最近会话。"""

        with self.session_factory() as db:
            latest_created_at_subquery = (
                select(
                    QueryLog.session_id.label('session_id'),
                    func.max(QueryLog.created_at).label('latest_created_at'),
                    func.count(QueryLog.id).label('message_count'),
                )
                .where(QueryLog.session_id.is_not(None))
                .group_by(QueryLog.session_id)
                .subquery()
            )

            statement = (
                select(QueryLog, latest_created_at_subquery.c.message_count)
                .join(
                    latest_created_at_subquery,
                    (QueryLog.session_id == latest_created_at_subquery.c.session_id)
                    & (QueryLog.created_at == latest_created_at_subquery.c.latest_created_at),
                )
                .order_by(desc(QueryLog.created_at))
                .limit(limit)
            )
            rows = db.execute(statement).all()

        return [
            SessionSummaryItem(
                session_id=query_log.session_id or '',
                latest_question=query_log.user_question,
                latest_answer=query_log.answer,
                message_count=int(message_count or 0),
                updated_at=query_log.updated_at,
            )
            for query_log, message_count in rows
            if query_log.session_id
        ]
