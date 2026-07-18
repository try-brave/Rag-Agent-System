from __future__ import annotations

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.language_models import BaseChatModel

from app.config import get_settings


def get_llm(*, streaming: bool = False, temperature: float = 0.1) -> BaseChatModel:
    """返回项目统一使用的聊天模型实例。

    说明：
    - 在本项目当前依赖组合下，Tongyi 的稳定调用入口仍可通过 `ChatTongyi` 使用；
    - 后续接入 Agent 时，业务层不应该直接依赖具体实现类，因此这里返回
      `BaseChatModel` 抽象类型，便于后续平滑替换实现。
    """

    settings = get_settings()
    return ChatTongyi(
        model_name=settings.model,
        dashscope_api_key=settings.dashscope_api_key,
        streaming=streaming,
        temperature=temperature,
    )
