#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: authen.py,
IDE: PyCharm,
Day: 2026 - 08 - 31,
Author: Jinjing.Liu
Title:
Description:
    1.
    2.
"""

from datetime import timedelta, datetime, timezone
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.config import settings
from app.core.database import get_db
from app.core.models import AdminUsers
from app.logs.loggers import logger


# 哈西密码的模型
pwd_context = CryptContext(schemes=['argon2'], deprecated="auto")

credential = HTTPBearer()


# 验证密码
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# 创建哈希密码
def generate_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


# 创建token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# 验证token
def validate_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        token = jwt.decode(token, settings.SECRET_KEY, algorithms=settings.ALGORITHM)
        if 'sub' not in token:
            print('令牌缺少重要标识')
            return None
        return token
    except JWTError as jwt_error:
        print(jwt_error)
        logger.error(f'日志:验证token失败:{jwt_error}')


# 获取当前用户
async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(credential),
        db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    payload = validate_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='无效的凭据')
    user_username = payload.get('sub')
    if not user_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='凭据关键字段有误!')
    result = await db.execute(select(AdminUsers).where(AdminUsers.username == user_username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='用户不存在'
        )

    return user
