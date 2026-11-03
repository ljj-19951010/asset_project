#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: operation_logs.py,
IDE: PyCharm,
Day: 2026 - 08 - 31,
Author: Jinjing.Liu
Title:
Description:
    1.
    2.
"""
from fastapi import Request

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import AdminOperationLogs


async def create_operation_logs(
        db: AsyncSession,
        request: Request,
        user_id: int,
        action: str,
        target_table: str,
        target_id: int,
        details: dict
):
    log = AdminOperationLogs(
        user_id=user_id,
        action=action,
        target_table=target_table,
        target_id=target_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        details=details
    )
    db.add(log)
    await db.commit()
