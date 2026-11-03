#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""报废资产合并查询"""
from datetime import datetime

from fastapi import APIRouter, Query, Depends, Request, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, Computers, Monitors, Employees, Departments
from app.core.enums import ComputersStatus, MonitorsStatus
from app.logs.operation_logs import create_operation_logs


router = APIRouter()


@router.get('/', summary='报废资产合并分页')
async def scrapped_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str = Query(None, description='搜索：资产编号/SN码/品牌/型号/使用人'),
    db: AsyncSession = Depends(get_db),
    _current_user: AdminUsers = Depends(get_current_user)
):
    keyword = (q or '').strip()
    kw = f'%{keyword}%' if keyword else None

    # -------- 电脑报废 --------
    c_stmt = (
        select(Computers)
        .outerjoin(Employees, Computers.employee_id == Employees.id)
        .where(Computers.status == ComputersStatus.SCRAPPED)
        .options(selectinload(Computers.employee).selectinload(Employees.department))
    )
    if kw:
        c_stmt = c_stmt.where(or_(
            Computers.asset_number.ilike(kw),
            Computers.sn_code.ilike(kw),
            Computers.brand.ilike(kw),
            Computers.model.ilike(kw),
            Employees.chinese_name.ilike(kw),
        ))
    c_rows = (await db.execute(c_stmt)).scalars().unique().all()

    # -------- 显示器报废 --------
    m_stmt = (
        select(Monitors)
        .outerjoin(Employees, Monitors.employee_id == Employees.id)
        .where(Monitors.status == MonitorsStatus.SCRAPPED)
        .options(selectinload(Monitors.employee).selectinload(Employees.department))
    )
    if kw:
        m_stmt = m_stmt.where(or_(
            Monitors.asset_number.ilike(kw),
            Monitors.sn_code.ilike(kw),
            Monitors.brand.ilike(kw),
            Monitors.model.ilike(kw),
            Employees.chinese_name.ilike(kw),
        ))
    m_rows = (await db.execute(m_stmt)).scalars().unique().all()

    # -------- 合并 --------
    items = []
    for c in c_rows:
        items.append({
            'asset_type': 'computer',
            'asset_number': c.asset_number,
            'brand': c.brand,
            'model': c.model,
            'sn_code': c.sn_code,
            'chinese_name': c.employee.chinese_name if c.employee else None,
            'department_name': c.employee.department.name if c.employee and c.employee.department else None,
            'scrapped_date': c.scrapped_date.isoformat() if c.scrapped_date else None,
            'remark': c.remark,
        })
    for m in m_rows:
        items.append({
            'asset_type': 'monitor',
            'asset_number': m.asset_number,
            'brand': m.brand,
            'model': m.model,
            'sn_code': m.sn_code,
            'chinese_name': m.employee.chinese_name if m.employee else None,
            'department_name': m.employee.department.name if m.employee and m.employee.department else None,
            'scrapped_date': m.scrapped_date.isoformat() if m.scrapped_date else None,
            'remark': m.remark,
        })

    # 按报废时间倒序
    items.sort(key=lambda x: x['scrapped_date'] or '', reverse=True)

    total = len(items)
    offset = (page - 1) * size
    return {
        'total': total,
        'items': items[offset:offset + size],
        'page': page,
        'size': size,
    }



@router.post('/restore', summary='恢复报废资产为正常使用')
async def restore_scrapped(
    request: Request,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user)
):
    asset_type = payload.get('asset_type')
    asset_number = payload.get('asset_number')
    if asset_type not in ('computer', 'monitor') or not asset_number:
        raise HTTPException(400, '参数错误')

    if asset_type == 'computer':
        asset = (await db.execute(
            select(Computers).where(Computers.asset_number == asset_number)
        )).scalar_one_or_none()
    else:
        asset = (await db.execute(
            select(Monitors).where(Monitors.asset_number == asset_number)
        )).scalar_one_or_none()

    if not asset:
        raise HTTPException(404, '未找到该资产')

    # 恢复
    asset.status = 'normal'
    asset.scrapped_date = None
    asset.deleted_at = None

    today_str = datetime.now().strftime('%Y年%m月%d日')
    old_remark = asset.remark or ''
    asset.remark = f'{today_str} 恢复为正常使用' + (f'（原备注：{old_remark}）' if old_remark else '')

    await db.commit()

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='restore_asset', target_table=asset_type + 's', target_id=asset.id,
        details={'message': f'用户 {current_user.username} 将 {asset_type} {asset_number} 从报废恢复为正常使用'}
    )

    return {'message': '恢复成功', 'asset_number': asset_number}