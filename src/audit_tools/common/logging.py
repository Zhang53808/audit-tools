"""审计工具包统一日志模块。

用法:
    from audit_tools.common.logging import get_logger, setup_logging
    logger = get_logger(__name__)
    logger.info("读取到 %d 条记录", len(df))
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    verbose: bool = False,
) -> logging.Logger:
    """配置根日志器。

    Args:
        level: 默认级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径 (None 则不输出到文件)
        verbose: True 时将控制台级别降到 DEBUG

    Returns:
        Root logger
    """
    root = logging.getLogger("audit_tools")
    root.setLevel(logging.DEBUG)  # root 设最低，由 handler 控制级别

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_level = logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)
    console_handler.setLevel(console_level)
    console_fmt = logging.Formatter(
        "%(message)s" if console_level >= logging.WARNING else "%(name)s: %(message)s"
    )
    console_handler.setFormatter(console_fmt)
    root.addHandler(console_handler)

    # 文件 handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """获取具名日志器（自动继承 audit_tools 配置）。"""
    return logging.getLogger(f"audit_tools.{name}")


# 默认配置（无文件输出，INFO 级别）
_root_logger = logging.getLogger("audit_tools")
_root_logger.addHandler(logging.NullHandler())
