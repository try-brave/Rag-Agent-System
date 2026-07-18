from __future__ import annotations

import logging
import re
from functools import lru_cache
from threading import RLock

from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.core.postgres import get_session_factory
from app.models.chunk import Chunk

logger = logging.getLogger(__name__)

_LATIN_TOKEN_PATTERN = re.compile(r'[a-z0-9][a-z0-9._:/-]*')
_CJK_SEGMENT_PATTERN = re.compile(r'[\u4e00-\u9fff]+')
"""
"""
try:
    import jieba
except Exception:  # noqa: BLE001
    jieba = None


def tokenize_for_bm25(text: str) -> list[str]:
    """将文本切成适合 BM25 的 token 列表。

    优先使用 `jieba.cut_for_search` 处理中文；若环境中没有安装 `jieba`，
    则回退为：
    - 英文/数字按正则拆分；
    - 中文按 2-gram + 单字混合切分，保证基础召回能力。
    """

    normalized_text = str(text or '').strip().lower()
    if not normalized_text:
        return []

    tokens: list[str] = []
    tokens.extend(_LATIN_TOKEN_PATTERN.findall(normalized_text))

    for segment in _CJK_SEGMENT_PATTERN.findall(normalized_text):
        if not segment:
            continue

        if jieba is not None:
            tokens.extend(token.strip() for token in jieba.cut_for_search(segment) if token.strip())
            continue

        if len(segment) == 1:
            tokens.append(segment)
            continue

        tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        tokens.extend(list(segment))

    return [token for token in tokens if token]


def _build_lexical_document(chunk: Chunk) -> str:
    """拼装参与 BM25 的词法文本。

    通过对文件名和标题做重复拼接，给它们更高的词法权重，
    让“按文件名/章节名搜文档”的召回更稳。
    """

    metadata = chunk.metadata_json or {}
    filename = str(metadata.get('filename') or '').strip()
    section_title = str(metadata.get('section_title') or '').strip()
    section_type = str(metadata.get('section_type') or '').strip()
    parser_name = str(metadata.get('parser_name') or '').strip()
    splitter_name = str(metadata.get('splitter_name') or '').strip()

    lexical_parts = [
        filename,
        filename,
        section_title,
        section_title,
        section_type,
        parser_name,
        splitter_name,
        chunk.content,
    ]
    return '\n'.join(part for part in lexical_parts if part)


class BM25IndexManager:
    """应用层 BM25 索引管理器。"""

    def __init__(self) -> None:
        self._lock = RLock()
        self._dirty = True
        self._bm25: BM25Okapi | None = None
        self._records: list[dict] = []
        self._rebuild_count = 0
        self._last_dirty_reason = 'initial'

    def mark_dirty(self, reason: str) -> None:
        with self._lock:
            self._dirty = True
            self._last_dirty_reason = reason
        logger.info('[BM25] index marked dirty: reason=%s', reason)

    def ensure_ready(self) -> None:
        with self._lock:
            needs_rebuild = self._dirty or self._bm25 is None
        if needs_rebuild:
            self.rebuild()

    def rebuild(self) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            chunks = db.execute(
                select(Chunk).where(Chunk.enabled.is_(True)).order_by(Chunk.updated_at.desc())
            ).scalars().all()

        records: list[dict] = []
        tokenized_corpus: list[list[str]] = []
        skipped_count = 0
        for chunk in chunks:
            lexical_text = _build_lexical_document(chunk)
            tokens = tokenize_for_bm25(lexical_text)
            if not tokens:
                skipped_count += 1
                continue
            metadata = chunk.metadata_json or {}

            records.append(
                {
                    'chunk_id': chunk.id,
                    'document_id': chunk.document_id,
                    'filename': metadata.get('filename'),
                    'file_type': metadata.get('file_type'),
                    'chunk_index': chunk.chunk_index,
                    'content': chunk.content,
                    'splitter_name': metadata.get('splitter_name'),
                    'parser_name': metadata.get('parser_name'),
                    'section_type': metadata.get('section_type'),
                    'section_title': metadata.get('section_title'),
                    'page_number': chunk.page_number or metadata.get('page_number'),
                    'source_path': metadata.get('source_path'),
                    'start_offset': chunk.start_offset,
                    'end_offset': chunk.end_offset,
                    'bm25_tokens': tokens,
                }
            )
            tokenized_corpus.append(tokens)

        bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

        with self._lock:
            self._bm25 = bm25
            self._records = records
            self._dirty = False
            self._rebuild_count += 1
            rebuild_count = self._rebuild_count
            dirty_reason = self._last_dirty_reason

        logger.info(
            '[BM25] rebuild completed: reason=%s total_chunks=%s indexed_chunks=%s skipped_chunks=%s rebuild_count=%s preview=%s',
            dirty_reason,
            len(chunks),
            len(records),
            skipped_count,
            rebuild_count,
            [
                {
                    'chunk_id': item.get('chunk_id'),
                    'filename': item.get('filename'),
                    'chunk_index': item.get('chunk_index'),
                    'token_count': len(item.get('bm25_tokens', [])),
                }
                for item in records[:3]
            ],
        )

    def search(self, query: str, *, top_k: int = 5, candidate_k: int | None = None) -> list[dict]:
        self.ensure_ready()

        tokenized_query = tokenize_for_bm25(query)
        if not tokenized_query:
            logger.info('[BM25] search skipped: empty tokenized query=%r', query)
            return []

        with self._lock:
            bm25 = self._bm25
            records = list(self._records)

        if bm25 is None or not records:
            logger.info('[BM25] search skipped: index is empty query=%r', query)
            return []

        scores = bm25.get_scores(tokenized_query)
        ranked_scores = sorted(
            ((index, float(score)) for index, score in enumerate(scores)),
            key=lambda item: item[1],
            reverse=True,
        )

        effective_candidate_k = candidate_k or max(top_k, top_k * 4)
        hits: list[dict] = []
        for rank, (index, score) in enumerate(ranked_scores, start=1):
            if score <= 0:
                continue
            record = dict(records[index])
            record.pop('bm25_tokens', None)
            record.update(
                {
                    'score': score,
                    'bm25_score': score,
                    'retrieval_source': 'bm25',
                    'retrieval_sources': ['bm25'],
                    'rank_bm25': rank,
                }
            )
            hits.append(record)
            if len(hits) >= effective_candidate_k:
                break

        logger.info(
            '[BM25] search completed: query=%r tokens=%s indexed_chunks=%s candidate_k=%s hit_count=%s preview=%s',
            query,
            tokenized_query[:12],
            len(records),
            effective_candidate_k,
            len(hits),
            [
                {
                    'chunk_id': item.get('chunk_id'),
                    'filename': item.get('filename'),
                    'bm25_score': round(float(item.get('bm25_score', 0.0)), 4),
                    'content_preview': str(item.get('content') or '')[:120],
                }
                for item in hits[:3]
            ],
        )
        return hits


@lru_cache(maxsize=1)
def get_bm25_index() -> BM25IndexManager:
    """返回 BM25 索引管理器单例。"""

    return BM25IndexManager()
