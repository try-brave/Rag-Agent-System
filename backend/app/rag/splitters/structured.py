from __future__ import annotations

import re

from app.rag.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.rag.splitters.unstructured import SplitChunk, split_unstructured_text
from app.utils.text import clean_text

STRUCTURED_LINE_PATTERNS = (
    r'^\s*[\w.-]+\s*[:：]\s*.+$',
    r'^\s*[-*]\s+.+$',
    r'^\s*\d+[.)、]\s+.+$',
    r'^\s*(create|alter|drop|select|insert|update|delete)\b.+$',
)


def _is_structured_line(line: str) -> bool:
    """判断单行是否更像结构化/配置型内容。"""

    normalized_line = line.strip()
    if not normalized_line:
        return False
    return any(re.match(pattern, normalized_line, flags=re.IGNORECASE) for pattern in STRUCTURED_LINE_PATTERNS)


def split_structured_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[SplitChunk]:
    """面向结构化文本的切分策略。

    适用场景：
    - 参数说明
    - 字段定义
    - SQL / DDL
    - 配置项列表

    目标是尽量让一个 chunk 保留完整的“条目块”语义。
    """

    cleaned_text = clean_text(text)
    if not cleaned_text:
        return []

    lines = cleaned_text.splitlines()
    grouped_blocks: list[str] = []
    current_block: list[str] = []

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            if current_block:
                grouped_blocks.append('\n'.join(current_block))
                current_block = []
            continue

        if _is_structured_line(stripped_line):
            if current_block:
                grouped_blocks.append('\n'.join(current_block))
            current_block = [stripped_line]
            continue

        current_block.append(stripped_line)

    if current_block:
        grouped_blocks.append('\n'.join(current_block))

    if not grouped_blocks:
        return split_unstructured_text(
            cleaned_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    chunks: list[SplitChunk] = []
    offset_cursor = 0
    for block in grouped_blocks:
        normalized_block = clean_text(block)
        if not normalized_block:
            continue

        if len(normalized_block) > chunk_size:
            block_chunks = split_unstructured_text(
                normalized_block,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            for block_chunk in block_chunks:
                chunks.append(
                    SplitChunk(
                        chunk_index=len(chunks),
                        content=block_chunk.content,
                        start_offset=offset_cursor + block_chunk.start_offset,
                        end_offset=offset_cursor + block_chunk.end_offset,
                    )
                )
            offset_cursor += len(normalized_block) + 2
            continue

        chunks.append(
            SplitChunk(
                chunk_index=len(chunks),
                content=normalized_block,
                start_offset=offset_cursor,
                end_offset=offset_cursor + len(normalized_block),
            )
        )
        offset_cursor += len(normalized_block) + 2

    return chunks
