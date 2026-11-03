#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: loggers.py,
IDE: PyCharm,
Day: 2026 - 08 - 31,
Author: Jinjing.Liu
Title:
Description:
    1.
    2.
"""
import sys

from pathlib import Path
from loguru import logger

from app.core.config import settings

# 日志目录（自动创建）
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 移除默认的 handler（避免重复输出）
logger.remove()

# ---------- 配置控制台输出（带颜色，便于开发） ----------
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if settings.ENV == "development" else "INFO",
    colorize=True,
)

# ---------- 配置按日期滚动的文件输出 ----------
# 普通日志（全部级别）
logger.add(
    LOG_DIR / "app_{time:YYYY-MM-DD}.log",
    rotation="00:00",          # 每天午夜轮转
    retention="30 days",       # 保留最近30天
    compression="zip",         # 压缩旧日志
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",              # 文件只记录 INFO 及以上级别
)

# 错误日志（单独分离，便于排查）
logger.add(
    LOG_DIR / "error_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="90 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",             # 只记录 ERROR 及以上
    filter=lambda record: record["level"].name in ("ERROR", "CRITICAL"),
)

# 提供全局日志对象
def get_logger(name: str = None):
    """
    获取 logger 实例，可传入模块名，方便追踪
    若未传入，则返回根 logger
    """
    if name:
        return logger.bind(name=name)
    return logger

# 为方便使用，直接导出 logger
__all__ = ["logger", "get_logger"]