from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.milvus_client import get_vector_store
from app.models.chunk import Chunk
from app.rag.bm25_index import get_bm25_index

logger = logging.getLogger(__name__)

_RRF_K = 60
_CANDIDATE_MULTIPLIER = 4
_MIN_CANDIDATE_K = 10


def _preview_hits(hits: list[dict], score_field: str = 'score') -> list[dict]:
    return [
        {
            'chunk_id': item.get('chunk_id'),
            'filename': item.get('filename'),
            'score': round(float(item.get(score_field) or 0.0), 4),
            'retrieval_source': item.get('retrieval_source'),
            'content_preview': str(item.get('content') or '')[:120],
        }
        for item in hits[:3]
    ]


def _candidate_k(top_k: int) -> int:
    return max(top_k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATE_K)


def _rrf_score(rank: int) -> float:
    return 1.0 / (_RRF_K + rank)


def _vector_retrieve_chunks(*, query: str, candidate_k: int) -> list[dict]:
    try:
        vector_store = get_vector_store()
        docs_with_score = vector_store.similarity_search_with_score(query, k=candidate_k)
        logger.info(
            '[VECTOR] retrieval completed: query=%r candidate_k=%s raw_hit_count=%s',
            query,
            candidate_k,
            len(docs_with_score),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('[VECTOR] retrieval failed: query=%r candidate_k=%s error=%s', query, candidate_k, exc)
        return []

    hits: list[dict] = []
    for rank, (document, score) in enumerate(docs_with_score, start=1):
        metadata = document.metadata or {}
        numeric_score = float(score)
        hits.append(
            {
                'chunk_id': metadata.get('chunk_id'),
                'document_id': metadata.get('document_id'),
                'filename': metadata.get('filename'),
                'file_type': metadata.get('file_type'),
                'chunk_index': metadata.get('chunk_index'),
                'content': document.page_content,
                'score': numeric_score,
                'vector_score': numeric_score,
                'splitter_name': metadata.get('splitter_name'),
                'parser_name': metadata.get('parser_name'),
                'section_type': metadata.get('section_type'),
                'section_title': metadata.get('section_title'),
                'page_number': metadata.get('page_number'),
                'source_path': metadata.get('source_path'),
                'start_offset': metadata.get('start_offset'),
                'end_offset': metadata.get('end_offset'),
                'retrieval_source': 'vector',
                'retrieval_sources': ['vector'],
                'rank_vector': rank,
            }
        )

    logger.info(
        '[VECTOR] retrieval preview: query=%r hit_count=%s preview=%s',
        query,
        len(hits),
        _preview_hits(hits, score_field='vector_score'),
    )
    return hits


def _bm25_retrieve_chunks(*, query: str, candidate_k: int) -> list[dict]:
    try:
        hits = get_bm25_index().search(query, top_k=candidate_k, candidate_k=candidate_k)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[BM25] retrieval failed: query=%r candidate_k=%s error=%s', query, candidate_k, exc)
        return []

    logger.info(
        '[BM25] retrieval preview: query=%r hit_count=%s preview=%s',
        query,
        len(hits),
        _preview_hits(hits, score_field='bm25_score'),
    )
    return hits


def _fuse_hits(*, query: str, vector_hits: list[dict], bm25_hits: list[dict], top_k: int) -> list[dict]:
    merged_by_chunk_id: dict[str, dict] = {}

    for source_name, hits in (('vector', vector_hits), ('bm25', bm25_hits)):
        for rank, hit in enumerate(hits, start=1):
            chunk_id = str(hit.get('chunk_id') or f'{source_name}:{rank}')
            fused_hit = merged_by_chunk_id.setdefault(
                chunk_id,
                {
                    **hit,
                    'score': float(hit.get('score') or 0.0),
                    'vector_score': hit.get('vector_score'),
                    'bm25_score': hit.get('bm25_score'),
                    'fused_score': 0.0,
                    'retrieval_sources': [],
                    'rank_vector': None,
                    'rank_bm25': None,
                    'rank_fused': None,
                },
            )

            if source_name not in fused_hit['retrieval_sources']:
                fused_hit['retrieval_sources'].append(source_name)

            fused_hit['fused_score'] += _rrf_score(rank)
            if source_name == 'vector':
                fused_hit['vector_score'] = hit.get('vector_score')
                fused_hit['rank_vector'] = rank
            else:
                fused_hit['bm25_score'] = hit.get('bm25_score')
                fused_hit['rank_bm25'] = rank

            for field_name, value in hit.items():
                if field_name in {'retrieval_sources', 'retrieval_source'}:
                    continue
                if fused_hit.get(field_name) in (None, '', []) and value not in (None, '', []):
                    fused_hit[field_name] = value

    ranked_hits = sorted(
        merged_by_chunk_id.values(),
        key=lambda item: (
            float(item.get('fused_score') or 0.0),
            float(item.get('bm25_score') or 0.0),
            float(item.get('vector_score') or 0.0),
        ),
        reverse=True,
    )

    for rank, hit in enumerate(ranked_hits, start=1):
        hit['rank_fused'] = rank
        if len(hit['retrieval_sources']) > 1:
            hit['retrieval_source'] = 'hybrid'
            hit['score'] = float(hit.get('fused_score') or 0.0)
        elif hit['retrieval_sources'] == ['bm25']:
            hit['retrieval_source'] = 'bm25'
            hit['score'] = float(hit.get('bm25_score') or 0.0)
        else:
            hit['retrieval_source'] = 'vector'
            hit['score'] = float(hit.get('vector_score') or 0.0)

    fused_hits = ranked_hits[:top_k]
    logger.info(
        '[HYBRID] fusion completed: query=%r vector_hits=%s bm25_hits=%s final_hits=%s preview=%s',
        query,
        len(vector_hits),
        len(bm25_hits),
        len(fused_hits),
        [
            {
                'chunk_id': item.get('chunk_id'),
                'filename': item.get('filename'),
                'retrieval_source': item.get('retrieval_source'),
                'vector_score': round(float(item.get('vector_score') or 0.0), 4),
                'bm25_score': round(float(item.get('bm25_score') or 0.0), 4),
                'fused_score': round(float(item.get('fused_score') or 0.0), 4),
                'content_preview': str(item.get('content') or '')[:120],
            }
            for item in fused_hits[:3]
        ],
    )
    return fused_hits


def _postgres_fallback(db: Session, *, query: str, top_k: int) -> list[dict]:
    statement = (
        select(Chunk)
        .where(Chunk.enabled.is_(True), Chunk.content.ilike(f'%{query}%'))
        .order_by(Chunk.updated_at.desc())
        .limit(top_k)
    )
    chunks = db.execute(statement).scalars().all()
    fallback_hits = [
        {
            'chunk_id': chunk.id,
            'document_id': chunk.document_id,
            'filename': chunk.metadata_json.get('filename'),
            'file_type': chunk.metadata_json.get('file_type'),
            'chunk_index': chunk.chunk_index,
            'content': chunk.content,
            'score': 1.0,
            'splitter_name': chunk.metadata_json.get('splitter_name'),
            'parser_name': chunk.metadata_json.get('parser_name'),
            'section_type': chunk.metadata_json.get('section_type'),
            'section_title': chunk.metadata_json.get('section_title'),
            'page_number': chunk.page_number or chunk.metadata_json.get('page_number'),
            'source_path': chunk.metadata_json.get('source_path'),
            'start_offset': chunk.start_offset,
            'end_offset': chunk.end_offset,
            'retrieval_source': 'postgres_fallback',
            'retrieval_sources': ['postgres_fallback'],
        }
        for chunk in chunks
    ]
    logger.info(
        '[POSTGRES] fallback retrieval: query=%r hit_count=%s preview=%s',
        query,
        len(fallback_hits),
        _preview_hits(fallback_hits),
    )
    return fallback_hits


def retrieve_chunks(db: Session, *, query: str, top_k: int = 5) -> list[dict]:
    """执行混合检索（向量 + BM25 并行 -> RRF 融合）。如果两路都失败或无结果，降级到 Postgres。"""

    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    candidate_k = _candidate_k(top_k)
    logger.info(
        '[RETRIEVER] hybrid retrieval started: query=%r top_k=%s candidate_k=%s',
        cleaned_query,
        top_k,
        candidate_k,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_vector = executor.submit(_vector_retrieve_chunks, query=cleaned_query, candidate_k=candidate_k)
        future_bm25 = executor.submit(_bm25_retrieve_chunks, query=cleaned_query, candidate_k=candidate_k)

        try:
            vector_hits = future_vector.result()
        except Exception as exc:  # noqa: BLE001
            logger.warning('[VECTOR] retrieval failed: %s', exc)
            vector_hits = []

        try:
            bm25_hits = future_bm25.result()
        except Exception as exc:  # noqa: BLE001
            logger.warning('[BM25] retrieval failed: %s', exc)
            bm25_hits = []

    fused_hits = _fuse_hits(query=cleaned_query, vector_hits=vector_hits, bm25_hits=bm25_hits, top_k=top_k)

    if fused_hits:
        return fused_hits

    logger.info(
        '[RETRIEVER] hybrid retrieval returned no hits; falling back to PostgreSQL ilike: query=%r top_k=%s',
        cleaned_query,
        top_k,
    )
    return _postgres_fallback(db, query=cleaned_query, top_k=top_k)
