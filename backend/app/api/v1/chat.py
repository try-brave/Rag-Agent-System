from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatHistoryItem,
    ChatRequest,
    ChatResponse,
    SessionClearResponse,
    SessionSummaryItem,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix='/chat', tags=['chat'])
"""
"""

@router.post('', response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """同步问答接口。"""

    service = ChatService()
    try:
        return service.invoke(
            session_id=request.session_id,
            message=request.message,
            top_k=request.top_k,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/stream')
def stream_chat(request: ChatRequest) -> StreamingResponse:
    """SSE 流式问答接口。"""

    service = ChatService()
    return StreamingResponse(
        service.stream(
            session_id=request.session_id,
            message=request.message,
            top_k=request.top_k,
        ),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@router.get('/sessions', response_model=list[SessionSummaryItem])
def list_chat_sessions(
    limit: int = Query(default=50, ge=1, le=200, description='返回最近会话数量'),
) -> list[SessionSummaryItem]:
    """返回最近会话列表。"""

    service = ChatService()
    return service.list_sessions(limit=limit)


@router.get('/sessions/{session_id}/history', response_model=list[ChatHistoryItem])
def get_chat_session_history(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200, description='返回历史消息数量'),
) -> list[ChatHistoryItem]:
    """返回指定会话的问答历史。"""

    service = ChatService()
    return service.get_session_history(session_id, limit=limit)


@router.delete('/sessions/{session_id}', response_model=SessionClearResponse)
def clear_chat_session(session_id: str) -> SessionClearResponse:
    """清空指定会话的日志和短期记忆。"""

    service = ChatService()
    return service.clear_session(session_id)
