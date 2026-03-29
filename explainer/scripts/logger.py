#!/usr/bin/env python3
"""
Explainer Logger - 统一日志模块

使用方式：
    from logger import get_logger
    logger = get_logger(__name__)

    logger.info("开始处理...")
    logger.warning("文件不存在，跳过")
    logger.error("生成失败: %s", error)
    logger.debug("当前状态: %s", state)

日志级别：
    - console: INFO（简洁）
    - file:    DEBUG（详细，含行号）

日志文件：
    项目目录下 logs/<name>.log（需传入 log_dir）
    或 ~/.explainer/logs/<name>.log（全局日志）
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def get_logger(
    name: str,
    log_dir: Optional[Path] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    获取命名 logger，同时输出到 console 和文件

    Args:
        name: logger 名称（通常用 __name__）
        log_dir: 日志文件目录（None 则不写文件）
        level: 日志级别（默认 INFO）

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler：INFO 及以上，简洁格式
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(console_handler)

    # File handler：DEBUG 及以上，详细格式（含文件名和行号）
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / f"{name.replace('.', '_')}.log",
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
            )
        )
        logger.addHandler(file_handler)

    # 防止日志向 root logger 传播（避免重复输出）
    logger.propagate = False

    return logger
