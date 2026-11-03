#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/9/16 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: stats.py,
IDE: PyCharm,
Day: 2026 - 09 - 16,
Author: Jinjing.Liu
Title:月度购买趋势统计
Description:月度购买趋势统计（今年 + 去年同期对比）
    1.
    2.
"""
from datetime import datetime

from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, Computers, Monitors

router = APIRouter()


async def _count_by_month(db, model, year):
    """统计某张表某年 1-12 月每月的数量，返回 {1: n, ..., 12: n}"""
    stmt = (
        select(
            extract('month', model.purchase_date).label('month'),
            func.count().label('count')
        )
        .where(
            extract('year', model.purchase_date) == year,
            model.deleted_at.is_(None)
        )
        .group_by(extract('month', model.purchase_date))
    )
    rows = (await db.execute(stmt)).all()
    counts = {i: 0 for i in range(1, 13)}
    for m, c in rows:
        counts[int(m)] = c
    return counts


@router.get('/monthly-purchase', summary='按月统计购买数量（今年+去年同期）')
async def monthly_purchase(
    year: int = Query(None, description='年份，默认今年'),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user)
):
    if not year:
        year = datetime.now().year
    last_year = year - 1

    # 今年
    c_this = await _count_by_month(db, Computers, year)
    m_this = await _count_by_month(db, Monitors, year)
    # 去年
    c_last = await _count_by_month(db, Computers, last_year)
    m_last = await _count_by_month(db, Monitors, last_year)

    return {
        'year': year,
        'last_year': last_year,
        'months': list(range(1, 13)),
        'computers': [c_this[i] for i in range(1, 13)],
        'monitors': [m_this[i] for i in range(1, 13)],
        'last_computers': [c_last[i] for i in range(1, 13)],
        'last_monitors': [m_last[i] for i in range(1, 13)],
        'total_computers': sum(c_this.values()),
        'total_monitors': sum(m_this.values()),
        'total_last_computers': sum(c_last.values()),
        'total_last_monitors': sum(m_last.values()),
    }