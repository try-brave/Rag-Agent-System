from __future__ import annotations

import json
from typing import Any


def format_sse_event(event: str, data: Any) -> str:
    """把 Python 对象格式化成标准 SSE 文本块。"""

    payload = json.dumps(data, ensure_ascii=False)
    return f'event: {event}\ndata: {payload}\n\n'
