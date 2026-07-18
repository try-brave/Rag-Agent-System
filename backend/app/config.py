from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
"""
"""
# `backend/.env` 是当前项目运行时配置的唯一入口。
# 这里统一计算绝对路径，避免从不同工作目录启动时读不到配置文件。
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / '.env'


class Settings(BaseSettings):
    """项目全局配置。

    设计目标：
    1. 所有外部依赖配置统一在这里定义，避免散落在各个模块中。
    2. 启动阶段即完成校验，缺少关键配置时尽快失败，而不是运行到半路才报错。
    3. 保持字段名和 `.env` 中的环境变量一一对应，便于排查问题。
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # ------------------------------
    # 应用本身的运行配置
    # ------------------------------
    app_name: str = 'RAG Agent System'
    app_version: str = '0.1.0'
    app_env: str = 'development'
    debug: bool = False
    api_v1_prefix: str = '/api/v1'
    allowed_origins: list[str] = Field(default_factory=lambda: ['http://localhost:5173'])
    storage_root: str = Field(default='storage', alias='STORAGE_ROOT')
    upload_dir_name: str = Field(default='uploads', alias='UPLOAD_DIR_NAME')
    max_upload_size_mb: int = Field(default=20, alias='MAX_UPLOAD_SIZE_MB')

    # ------------------------------
    # LLM / Embedding 配置
    # ------------------------------
    dashscope_api_key: str = Field(alias='DASHSCOPE_API_KEY')
    model: str = Field(default='qwen-plus', alias='MODEL')
    embedding_model: str = Field(default='text-embedding-v1', alias='EMBEDDING_MODEL')

    # ------------------------------
    # 向量库 Milvus 配置
    # ------------------------------
    milvus_uri: str | None = Field(default=None, alias='MILVUS_URI')
    milvus_host: str = Field(default='127.0.0.1', alias='MILVUS_HOST')
    milvus_port: int = Field(default=19530, alias='MILVUS_PORT')
    milvus_collection: str = Field(alias='MILVUS_COLLECTION')
    milvus_dimension: int = Field(default=1536, alias='MILVUS_DIMENSION')

    # ------------------------------
    # 关系库 / 缓存 / 联网检索 配置
    # ------------------------------
    postgres_dsn: str = Field(alias='POSTGRES_DSN')
    redis_url: str = Field(alias='REDIS_URL')
    bocha_api_key: str | None = Field(default=None, alias='BOCHA_API_KEY')

    # ------------------------------
    # OCR 文档解析配置
    # ------------------------------
    ocr_enabled: bool = Field(default=False, alias='OCR_ENABLED')
    ocr_access_token: str | None = Field(default=None, alias='OCR_ACCESS_TOKEN')
    ocr_client_id: str | None = Field(default=None, alias='OCR_CLIENT_ID')
    ocr_client_secret: str | None = Field(default=None, alias='OCR_CLIENT_SECRET')
    ocr_token_url: str = Field(
        default='https://aip.baidubce.com/oauth/2.0/token',
        alias='OCR_TOKEN_URL',
    )
    ocr_task_url: str = Field(
        default='https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task',
        alias='OCR_TASK_URL',
    )
    ocr_query_url: str = Field(
        default='https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task/query',
        alias='OCR_QUERY_URL',
    )
    ocr_poll_interval_sec: int = Field(default=3, alias='OCR_POLL_INTERVAL_SEC')
    ocr_poll_max_attempts: int = Field(default=20, alias='OCR_POLL_MAX_ATTEMPTS')
    ocr_pdf_min_page_chars: int = Field(default=40, alias='OCR_PDF_MIN_PAGE_CHARS')
    ocr_pdf_empty_page_ratio: float = Field(default=0.5, alias='OCR_PDF_EMPTY_PAGE_RATIO')
    ocr_pdf_low_text_avg_chars: int = Field(default=120, alias='OCR_PDF_LOW_TEXT_AVG_CHARS')
    ocr_docx_min_chars: int = Field(default=120, alias='OCR_DOCX_MIN_CHARS')
    ocr_table_like_line_threshold: int = Field(default=3, alias='OCR_TABLE_LIKE_LINE_THRESHOLD')

    @field_validator('allowed_origins', mode='before')
    @classmethod
    def normalize_allowed_origins(cls, value: Any) -> list[str]:
        """兼容多种 CORS 输入格式。

        常见场景：
        - `.env` 中写成 JSON 数组：`["http://localhost:5173"]`
        - `.env` 中写成逗号分隔字符串：`http://a.com,http://b.com`
        - 代码默认值直接给 Python 列表
        """

        if value is None:
            return ['http://localhost:5173']

        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return []

            if raw_value.startswith('['):
                parsed_value = json.loads(raw_value)
                if not isinstance(parsed_value, list):
                    raise ValueError('allowed_origins JSON must be a list')
                return [str(item).strip() for item in parsed_value if str(item).strip()]

            return [item.strip() for item in raw_value.split(',') if item.strip()]

        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]

        raise TypeError('allowed_origins must be a list or comma-separated string')

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_milvus_uri(self) -> str:
        """统一返回 Milvus 连接地址。

        优先使用显式配置的 `MILVUS_URI`，否则回退为 `host + port` 组合，
        这样其它模块只依赖一个标准化后的字段即可。
        """

        if self.milvus_uri:
            return self.milvus_uri
        return f'http://{self.milvus_host}:{self.milvus_port}'

    @computed_field  # type: ignore[prop-decorator]
    @property
    def upload_dir(self) -> str:
        """返回上传文件目录的绝对路径。"""

        return str(BASE_DIR / self.storage_root / self.upload_dir_name)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回配置单例。

    BaseSettings 每次实例化都会重新读取环境变量。这里做缓存，是为了保证：
    - 整个进程内读取配置的行为一致；
    - 避免在高频依赖注入场景下重复解析 `.env`。
    """

    return Settings()
