from __future__ import annotations

import re

from app.rag.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.rag.splitters.unstructured import SplitChunk, split_unstructured_text
from app.utils.text import clean_text


def split_semi_structured_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[SplitChunk]:
    """面向半结构化文本的切分策略。

    适用场景：
    - Markdown/Docx 的标题段落块
    - 业务说明文档
    - 方案文档、流程说明

    这类文本通常介于强结构化字段说明和纯自然段之间，
    优先按段落块聚合，再做必要拆分。
    """

    cleaned_text = clean_text(text)
    if not cleaned_text:
        return []

    # 第一步：保护 HTML 块，把 <table>...</table> 和 <img>...</div> 作为独立单元保护起来
    # 增加 Fast Path 快速检查，提升普通无 HTML 文档的性能
    protected_blocks = []
    text_with_placeholders = cleaned_text
    
    text_lower = cleaned_text.lower()
    has_html = '<table' in text_lower or '<img' in text_lower
    
    if has_html:
        # 保护 table
        table_pattern = re.compile(r'(<table.*?>.*?</table>)', re.IGNORECASE | re.DOTALL)
        def table_repl(match):
            block = match.group(1)
            # 增加安全兜底：如果 HTML 块异常大（比如缺失闭合标签导致吞了后续几万字），放弃保护，防止 OOM
            if len(block) > 8000:
                return block
            protected_blocks.append(block)
            return f"\n\n__PROTECTED_HTML_BLOCK_{len(protected_blocks)-1}__\n\n"
        
        text_with_placeholders = table_pattern.sub(table_repl, text_with_placeholders)
        
        # 保护 img div (类似 <div...><img...></div>)
        img_div_pattern = re.compile(r'(<div.*?>.*?<img.*?>.*?</div>)', re.IGNORECASE | re.DOTALL)
        def img_repl(match):
            block = match.group(1)
            if len(block) > 8000:
                return block
            protected_blocks.append(block)
            return f"\n\n__PROTECTED_HTML_BLOCK_{len(protected_blocks)-1}__\n\n"
        
        text_with_placeholders = img_div_pattern.sub(img_repl, text_with_placeholders)

    # 第二步：按段落（空行）切分
    paragraphs = [paragraph.strip() for paragraph in text_with_placeholders.split('\n\n') if paragraph.strip()]
    
    # 恢复保护块
    restored_paragraphs = []
    for p in paragraphs:
        restored_p = p
        for i, block in enumerate(protected_blocks):
            placeholder = f"__PROTECTED_HTML_BLOCK_{i}__"
            if placeholder in restored_p:
                restored_p = restored_p.replace(placeholder, block)
        restored_paragraphs.append(restored_p)

    if not restored_paragraphs:
        return []

    chunks: list[SplitChunk] = []
    current_text = ''
    current_start = 0
    offset_cursor = 0

    for paragraph in restored_paragraphs:
        candidate_text = paragraph if not current_text else f'{current_text}\n\n{paragraph}'
        if current_text and len(candidate_text) > chunk_size:
            chunks.append(
                SplitChunk(
                    chunk_index=len(chunks),
                    content=current_text,
                    start_offset=current_start,
                    end_offset=current_start + len(current_text),
                )
            )
            current_start = max(0, offset_cursor - min(chunk_overlap, len(paragraph)))
            current_text = paragraph
        else:
            if not current_text:
                current_start = offset_cursor
            current_text = candidate_text

        offset_cursor += len(paragraph) + 2

    if current_text:
        if len(current_text) > chunk_size:
            # 检查这个超长段落是否是因为包含受保护的 HTML 块
            has_protected = any(block in current_text for block in protected_blocks)
            if has_protected:
                # 包含受保护块的超长段落，绝不硬切，直接作为完整 chunk 保留结构
                chunks.append(
                    SplitChunk(
                        chunk_index=len(chunks),
                        content=current_text,
                        start_offset=current_start,
                        end_offset=current_start + len(current_text),
                    )
                )
            else:
                overflow_chunks = split_unstructured_text(
                    current_text,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                for overflow_chunk in overflow_chunks:
                    chunks.append(
                        SplitChunk(
                            chunk_index=len(chunks),
                            content=overflow_chunk.content,
                            start_offset=current_start + overflow_chunk.start_offset,
                            end_offset=current_start + overflow_chunk.end_offset,
                        )
                    )
        else:
            chunks.append(
                SplitChunk(
                    chunk_index=len(chunks),
                    content=current_text,
                    start_offset=current_start,
                    end_offset=current_start + len(current_text),
                )
            )

    return chunks
