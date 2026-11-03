#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: config.py,
IDE: PyCharm,
Day: 2026 - 08 - 31,
Author: Jinjing.Liu
Title: 配置文件
Description:
    1.
    2.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    DEBUG: bool = False
    ALGORITHM: str
    POOL_SIZE: int
    MAX_OVERFLOW: int
    POOL_TIMEOUT: int
    POOL_RECYCLE: int
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080        # 会话保留七天
    ENV: str = 'development'

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()