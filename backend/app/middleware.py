from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response


def register_middlewares(app: FastAPI) -> None:
    """集中注册项目中间件。

    当前阶段先保留一个最基础、但非常实用的耗时统计中间件。
    后续如果增加请求日志、限流、链路追踪，也统一放在这里管理。
    """

    @app.middleware('http')
    async def request_timing_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 使用高精度计时器统计整个请求处理链路的耗时。
        started_at = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started_at) * 1000

        # 把耗时放到响应头，方便前端、调试工具和日志平台快速观察性能。
        response.headers['X-Process-Time-MS'] = f'{duration_ms:.2f}'
        return response
