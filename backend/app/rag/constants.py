from __future__ import annotations

# 这里先采用最基础、最稳妥的一组默认切分参数。
# 后续接入前端调试台时，可以把这些参数暴露成可配置项。
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50

# 优先按“结构更强”的分隔符切分，这样能尽量保留语义完整性。
DEFAULT_SEPARATORS = [
    '\n\n',
    '\n',
    '。',
    '！',
    '？',
    '；',
    '，',
    ' ',
]
