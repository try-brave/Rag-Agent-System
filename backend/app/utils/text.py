from __future__ import annotations

import math
import re


def clean_text(text: str) -> str:
    """对原始文本做最基础的清洗。

    目标不是“过度处理”，而是保证后续切分更稳定：
    - 统一换行符；
    - 去掉首尾空白；
    - 压缩过多的空行；
    - 保留正常段落结构，便于后续溯源展示。
    """

    normalized_text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    normalized_text = re.sub(r'\n{3,}', '\n\n', normalized_text)
    normalized_text = re.sub(r'[ \t]{2,}', ' ', normalized_text)
    return normalized_text


def estimate_token_count(text: str) -> int:
    """粗略估算 token 数量。

    这里不引入额外 tokenizer 依赖，先使用一个足够稳定的近似值。
    对中文和英文混排场景，这个数字不追求完全准确，主要用于：
    - chunk 管理页展示；
    - 后续检索和切分调试。
    """

    cleaned_text = clean_text(text)
    if not cleaned_text:
        return 0
    return max(1, math.ceil(len(cleaned_text) / 4))
