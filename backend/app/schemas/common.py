from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceHealthItem(BaseModel):
    """单个基础服务的健康状态。"""

    ok: bool = Field(description='服务是否可用')
    error: str | None = Field(default=None, description='服务异常时的错误信息')


class HealthResponse(BaseModel):
    """系统健康检查响应体。"""

    ok: bool = Field(description='系统整体是否健康')
    services: dict[str, ServiceHealthItem] = Field(
        default_factory=dict,
        description='各个依赖服务的健康状态明细',
    )
