#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: database.py,
IDE: PyCharm,
Day: 2026 - 08 - 31,
Author: Jinjing.Liu
Title:数据库连接、会话创建
Description:
    1.
    2.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# 模型基类
class Base(DeclarativeBase):
    pass


# 创建会话引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_timeout=settings.POOL_TIMEOUT,
    pool_recycle=settings.POOL_RECYCLE,
    connect_args={
        'charset': 'utf8',
        'use_unicode': True,
    }
)
# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)


# 创建临时会话
async def get_db() -> AsyncGenerator[AsyncSession, None]:
   async with AsyncSessionLocal() as session:
       try:
           yield session
       except Exception:
           await session.rollback()
           raise
       finally:
           await session.close()