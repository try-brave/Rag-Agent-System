from __future__ import annotations

from dataclasses import dataclass

from app.rag.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, DEFAULT_SEPARATORS
from app.utils.text import clean_text


@dataclass(slots=True)
class SplitChunk:
    """切分结果结构。

    使用 dataclass 的好处是：
    - 字段含义清晰；
    - 后续无论是落库、向量化还是前端回显，都可以复用同一份数据结构。
    """

    chunk_index: int
    content: str
    start_offset: int
    end_offset: int


def _find_split_position(text: str, chunk_size: int, separators: list[str]) -> int:
    """在目标长度附近寻找最合适的截断点。

    逻辑优先级：
    1. 先尝试在 chunk_size 范围内从后往前找高优先级分隔符；
    2. 如果找不到，就直接在固定长度处截断，保证算法稳定。
    """

    if len(text) <= chunk_size:
        return len(text)

    candidate_text = text[:chunk_size]
    for separator in separators:
        split_index = candidate_text.rfind(separator)
        if split_index > 0:
            return split_index + len(separator)
    return chunk_size


def split_unstructured_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> list[SplitChunk]:
    """按最基础的非结构化文本策略切分内容。

    该实现故意保持简单可靠：
    - 足够适合第一版 RAG；
    - 不依赖额外复杂库；
    - 能保留 overlap 以降低跨 chunk 语义断裂问题。
    """

    cleaned_text = clean_text(text)
    if not cleaned_text:
        return []

    active_separators = separators or DEFAULT_SEPARATORS
    chunks: list[SplitChunk] = []

    start_offset = 0
    chunk_index = 0
    while start_offset < len(cleaned_text):
        remaining_text = cleaned_text[start_offset:]
        split_length = _find_split_position(remaining_text, chunk_size, active_separators)
        end_offset = min(len(cleaned_text), start_offset + split_length)
        chunk_content = cleaned_text[start_offset:end_offset].strip()

        if chunk_content:
            chunks.append(
                SplitChunk(
                    chunk_index=chunk_index,
                    content=chunk_content,
                    start_offset=start_offset,
                    end_offset=end_offset,
                )
            )
            chunk_index += 1

        if end_offset >= len(cleaned_text):
            break

        # overlap 用于保留上一块尾部上下文，方便后续检索和回答衔接。
        start_offset = max(0, end_offset - chunk_overlap)

    return chunks
