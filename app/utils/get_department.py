#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/9/3 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: get_department.py,
IDE: PyCharm,
Day: 2026 - 09 - 03,
Author: Jinjing.Liu
Title:
Description:
    1.
    2.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models import Departments


async def get_or_create_department(
        db: AsyncSession,
        department_name: str
) -> Optional[Departments]:
    """根据部门名称获取或创建部门"""
    if not department_name:
        return None

    # 查询是否已存在
    stmt = select(Departments).where(
        Departments.name == department_name,
        Departments.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    dept = result.scalar_one_or_none()

    if not dept:
        dept = Departments(name=department_name)
        db.add(dept)
        await db.flush()  # 获取ID

    return dept
