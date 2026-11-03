#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
显示器管理
"""
from datetime import datetime

from fastapi import APIRouter, Query, Request, Depends, HTTPException
from sqlalchemy import select, func, or_, and_, asc, desc, Integer, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.schemas import Page, MonitorsOut, build_monitors_out, MonitorsCreate, MonitorsUpdate
from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, Monitors, Employees
from app.core.enums import MonitorsStatus
from app.logs.operation_logs import create_operation_logs
from app.utils.get_date import serialize_datetime
from app.utils.get_employee import mark_employee_leave, get_or_create_employee
from app.utils.log_helpers import build_change_list, format_value

router = APIRouter()


@router.get('/', response_model=Page[MonitorsOut], summary='查询所有显示器')
async def show_monitors(
        request: Request,
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        sort_by: str = Query(None),
        sort_order: str = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    offset = (page - 1) * size
    total_stmt = select(func.count()).select_from(Monitors).where(
        Monitors.status == MonitorsStatus.NORMAL,
        Monitors.deleted_at.is_(None),
        Monitors.scrapped_date.is_(None)
    )
    total = (await db.execute(total_stmt)).scalar()

    stmt = (
        select(Monitors)
        .outerjoin(Employees, Monitors.employee_id == Employees.id)
        .where(
            Monitors.status == MonitorsStatus.NORMAL,
            Monitors.deleted_at.is_(None),
            Monitors.scrapped_date.is_(None)
        )
        .options(selectinload(Monitors.employee).selectinload(Employees.department))
    )

    # 【修复】正确的 cast 写法
    order_clauses = []
    num_expr = cast(func.substring_index(Monitors.asset_number, '-', -1), Integer)

    if sort_by == 'asset_number':
        order_clauses.append(asc(num_expr) if sort_order == 'asc' else desc(num_expr))
        order_clauses.append(asc(Monitors.asset_number) if sort_order == 'asc' else desc(Monitors.asset_number))
    elif sort_by == 'join_date':
        order_clauses.append(asc(Employees.hire_date) if sort_order == 'asc' else desc(Employees.hire_date))
    elif sort_by == 'leave_date':
        order_clauses.append(asc(Employees.leave_date) if sort_order == 'asc' else desc(Employees.leave_date))
    elif sort_by == 'usage_time':
        order_clauses.append(asc(Monitors.purchase_date) if sort_order == 'asc' else desc(Monitors.purchase_date))

    if not order_clauses:
        order_clauses = [asc(num_expr), asc(Monitors.asset_number)]
    else:
        order_clauses.append(asc(Monitors.id))

    stmt = stmt.offset(offset).limit(size).order_by(*order_clauses)

    monitors = (await db.execute(stmt)).scalars().all()
    monitors_out = [build_monitors_out(mon) for mon in monitors]
    return Page(total=total, items=monitors_out)


@router.get('/scrapped', response_model=Page[MonitorsOut], summary='查询已报废显示器')
async def show_monitors_scrapped(
        request: Request,
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    offset = (page - 1) * size
    total = (await db.execute(
        select(func.count()).select_from(Monitors).where(Monitors.status == MonitorsStatus.SCRAPPED))).scalar()
    stmt = select(Monitors).where(Monitors.status == MonitorsStatus.SCRAPPED).offset(offset).limit(size).order_by(
        Monitors.id.desc())
    monitors = (await db.execute(stmt)).scalars().all()
    return Page(total=total, items=monitors)


@router.post('/create', response_model=MonitorsOut, summary='添加显示器')
async def create_monitors(
        request: Request,
        monitors_in: MonitorsCreate,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if not monitors_in.asset_number or not monitors_in.asset_number.strip():
        raise HTTPException(400, '资产编号不能为空')
    if not monitors_in.brand or not monitors_in.brand.strip():
        raise HTTPException(400, '品牌不能为空')
    if not monitors_in.model or not monitors_in.model.strip():
        raise HTTPException(400, '型号不能为空')
    if not monitors_in.sn_code or not monitors_in.sn_code.strip():
        raise HTTPException(400, 'SN码不能为空')
    if not monitors_in.status:
        raise HTTPException(400, '状态不能为空')

    if (
    await db.execute(select(Monitors).where(Monitors.asset_number == monitors_in.asset_number))).scalar_one_or_none():
        raise HTTPException(400, '资产编号已存在!')
    if (await db.execute(select(Monitors).where(Monitors.sn_code == monitors_in.sn_code))).scalar_one_or_none():
        raise HTTPException(400, 'SN码已存在!')

    new_monitor = Monitors(**monitors_in.model_dump(exclude_unset=True))
    db.add(new_monitor)
    await db.flush()

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='create_monitors', target_id=new_monitor.id, target_table='monitors',
        details={
            'message': f'用户 {current_user.username} 创建了显示器 {new_monitor.asset_number}（品牌：{new_monitor.brand}，型号：{new_monitor.model}）'}
    )
    await db.commit()

    flush_monitor = (await db.execute(select(Monitors).where(Monitors.asset_number == monitors_in.asset_number).options(
        selectinload(Monitors.employee)))).scalar_one_or_none()
    return flush_monitor


@router.put('/{asset_number}', response_model=MonitorsOut, summary='更新显示器')
async def update_monitors(
        request: Request,
        asset_number: str,
        monitors_in: MonitorsUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    monitor = (await db.execute(select(Monitors).where(Monitors.asset_number == asset_number))).scalar_one_or_none()
    if not monitor:
        raise HTTPException(404, '资产编号不存在!')

    old_employee_id = monitor.employee_id
    update_data = monitors_in.model_dump(exclude_unset=True)

    # 记录旧值
    old_values = {}
    for k in update_data.keys():
        if hasattr(monitor, k):
            old_values[k] = getattr(monitor, k)

    # 处理员工字段
    has_employee_fields = any(
        k in update_data for k in ('chinese_name', 'english_name', 'department_name', 'join_date', 'leave_date'))

    old_emp_name = None
    new_emp_name = None
    if has_employee_fields:
        chinese_name = update_data.pop('chinese_name', None)
        english_name = update_data.pop('english_name', None)
        department_name = update_data.pop('department_name', None)
        join_date = update_data.pop('join_date', None)
        leave_date = update_data.pop('leave_date', None)

        if old_employee_id:
            old_emp = await db.get(Employees, old_employee_id)
            old_emp_name = old_emp.chinese_name if old_emp else None
        old_values['_old_emp_name'] = old_emp_name

        def to_date(v):
            if not v: return None
            if hasattr(v, 'date') and callable(v.date): return v.date()
            return v

        join_date_value = to_date(join_date)
        leave_date_value = to_date(leave_date)

        if chinese_name is not None:
            chinese_name_clean = str(chinese_name).strip() if chinese_name else ''
            if not chinese_name_clean:
                if old_employee_id and old_emp:
                    if leave_date_value:
                        old_emp.leave_date = leave_date_value
                    else:
                        await mark_employee_leave(db, employee_id=old_employee_id, exclude_monitor_id=monitor.id)
                monitor.employee_id = None
                new_emp_name = None
            else:
                employee = await get_or_create_employee(
                    db=db, chinese_name=chinese_name_clean,
                    english_name=english_name.strip() if english_name else None,
                    department_name=department_name.strip() if department_name else None,
                    hire_date=join_date_value, leave_date=leave_date_value
                )
                monitor.employee_id = employee.id if employee else None
                new_emp_name = chinese_name_clean
        old_values['_new_emp_name'] = new_emp_name

    # 唯一性校验
    if 'asset_number' in update_data and update_data['asset_number'] != asset_number:
        exist = (await db.execute(select(Monitors).where(Monitors.asset_number == update_data['asset_number'],
                                                         Monitors.id != monitor.id))).scalar_one_or_none()
        if exist:
            raise HTTPException(400, '资产编号已存在')
    if 'sn_code' in update_data:
        exist = (await db.execute(select(Monitors).where(Monitors.sn_code == update_data['sn_code'],
                                                         Monitors.id != monitor.id))).scalar_one_or_none()
        if exist:
            raise HTTPException(400, 'SN码已存在')

    # 应用字段
    for k, v in update_data.items():
        if hasattr(monitor, k):
            setattr(monitor, k, v)

    # 生成变化列表
    change_list = build_change_list(old_values, update_data)
    if has_employee_fields and old_values.get('_old_emp_name') != old_values.get('_new_emp_name'):
        change_list.insert(0,
                           f'员工姓名：{format_value(old_values.get("_old_emp_name"))} → {format_value(old_values.get("_new_emp_name"))}')

    await db.commit()
    await db.refresh(monitor)

    # 写入日志
    if change_list:
        log_msg = f'用户 {current_user.username}更新了资产编号{asset_number}的信息:{"；".join(change_list)}'
    else:
        log_msg = f'用户 {current_user.username}更新了资产编号{asset_number}（无字段变化）'

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='update_monitors', target_id=monitor.id, target_table='monitors',
        details={'message': log_msg, 'data': serialize_datetime(monitors_in.model_dump())}
    )

    stmt_return = (select(Monitors).where(Monitors.asset_number == monitor.asset_number)
                   .options(selectinload(Monitors.employee).selectinload(Employees.department)))
    monitor = (await db.execute(stmt_return)).scalar_one_or_none()
    return monitor


@router.delete('/{asset_number}', response_model=dict, summary='删除显示器')
async def delete_monitors(
        request: Request,
        asset_number: str,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    monitor = (await db.execute(select(Monitors).where(Monitors.asset_number == asset_number))).scalar_one_or_none()
    if not monitor or monitor.deleted_at:
        raise HTTPException(404, '资产编号不存在或已被删除!')

    old_brand = monitor.brand
    old_model = monitor.model

    monitor.deleted_at = datetime.now()
    monitor.status = MonitorsStatus.SCRAPPED
    await db.commit()

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='delete_monitors', target_id=monitor.id, target_table='monitors',
        details={
            'message': f'用户 {current_user.username} 删除了显示器 {asset_number}（品牌：{old_brand}，型号：{old_model}）'}
    )
    return {'message': '删除成功!'}


@router.get('/find-page/{asset_number}', summary='查找显示器在第几页')
async def find_monitor_page(
        asset_number: str,
        size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _current_user: AdminUsers = Depends(get_current_user)
):
    target = (await db.execute(select(Monitors).where(Monitors.asset_number == asset_number))).scalar_one_or_none()
    if not target or target.deleted_at:
        return {'page': None, 'asset_number': asset_number}

    count_stmt = select(func.count()).select_from(Monitors).where(
        Monitors.status == MonitorsStatus.NORMAL,
        Monitors.deleted_at.is_(None),
        Monitors.scrapped_date.is_(None),
        or_(
            Monitors.purchase_date > target.purchase_date,
            and_(Monitors.purchase_date == target.purchase_date, Monitors.id > target.id)
        )
    )
    before_count = (await db.execute(count_stmt)).scalar() or 0
    page = (before_count // size) + 1
    return {'page': page, 'asset_number': asset_number}