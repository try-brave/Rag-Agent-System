from __future__ import annotations

from sqlalchemy.orm import Session

from app.rag.retriever import retrieve_chunks


class RetrievalService:
    """检索调试相关业务编排。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def search(self, *, query: str, top_k: int = 5) -> list[dict]:
        """返回最基础的检索结果列表。"""

        return retrieve_chunks(self.db, query=query, top_k=top_k)
