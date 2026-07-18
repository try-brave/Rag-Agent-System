from __future__ import annotations

import logging
import sys


class ColorFormatter(logging.Formatter):
    """为终端日志增加颜色和更醒目的级别展示。"""

    RESET = '\033[0m'
    BOLD = '\033[1m'
    LEVEL_COLORS = {
        logging.DEBUG: '\033[36m',
        logging.INFO: '\033[32m',
        logging.WARNING: '\033[33m',
        logging.ERROR: '\033[31m',
        logging.CRITICAL: '\033[35m',
    }

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        if sys.stderr.isatty():
            color = self.LEVEL_COLORS.get(record.levelno, '')
            if color:
                record.levelname = f'{self.BOLD}{color}{original_levelname}{self.RESET}'
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


def configure_logging() -> None:
    """配置项目统一日志格式。

    这里保持实现尽量简单：
    - 只做一次全局配置；
    - 不在业务模块里重复配置 handler；
    - 日志格式优先突出时间、级别、模块名，方便本地排查问题。
    """

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))

    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
