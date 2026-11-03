#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
电脑管理
"""
from datetime import datetime

from fastapi import APIRouter, Query, Depends, Request, HTTPException
from sqlalchemy import select, func, or_, and_, asc, desc, Integer, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.schemas import Page, ComputersOut, ComputersCreate, ComputersUpdate, build_computer_out
from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, Computers, Employees
from app.core.enums import ComputersStatus
from app.logs.operation_logs import create_operation_logs
from app.utils.get_date import serialize_datetime
from app.utils.get_employee import mark_employee_leave, get_or_create_employee
from app.utils.log_helpers import build_change_list, format_value

router = APIRouter()


@router.get('/', response_model=Page[ComputersOut])
async def show_computers(
        request: Request,
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        sort_by: str = Query(None),
        sort_order: str = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    total_stmt = select(func.count()).select_from(Computers).where(
        Computers.status == ComputersStatus.NORMAL,
        Computers.deleted_at.is_(None),
        Computers.scrapped_date.is_(None)
    )
    total = (await db.execute(total_stmt)).scalar()

    offset = (page - 1) * size

    stmt = (
        select(Computers)
        .outerjoin(Employees, Computers.employee_id == Employees.id)
        .where(
            Computers.status == ComputersStatus.NORMAL,
            Computers.deleted_at.is_(None),
            Computers.scrapped_date.is_(None)
        )
        .options(selectinload(Computers.employee).selectinload(Employees.department))
    )

    # 【修复】正确的 cast 写法
    order_clauses = []
    num_expr = cast(func.substring_index(Computers.asset_number, '-', -1), Integer)

    if sort_by == 'asset_number':
        order_clauses.append(asc(num_expr) if sort_order == 'asc' else desc(num_expr))
        order_clauses.append(asc(Computers.asset_number) if sort_order == 'asc' else desc(Computers.asset_number))
    elif sort_by == 'join_date':
        order_clauses.append(asc(Employees.hire_date) if sort_order == 'asc' else desc(Employees.hire_date))
    elif sort_by == 'leave_date':
        order_clauses.append(asc(Employees.leave_date) if sort_order == 'asc' else desc(Employees.leave_date))
    elif sort_by == 'usage_time':
        order_clauses.append(asc(Computers.purchase_date) if sort_order == 'asc' else desc(Computers.purchase_date))

    if not order_clauses:
        order_clauses = [asc(num_expr), asc(Computers.asset_number)]
    else:
        order_clauses.append(asc(Computers.id))

    stmt = stmt.offset(offset).limit(size).order_by(*order_clauses)

    result = await db.execute(stmt)
    computers = result.scalars().all()
    computers_out = [build_computer_out(comp) for comp in computers]
    return Page(total=total, items=computers_out)


@router.get('/scrapped', response_model=Page[ComputersOut], summary='查看所有已报废电脑的信息')
async def scrapped_computers(
        request: Request,
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    offset = (page - 1) * size
    total_stmt = select(func.count()).select_from(Computers).where(Computers.status == ComputersStatus.SCRAPPED)
    total = (await db.execute(total_stmt)).scalar()
    stmt = select(Computers).where(Computers.status == ComputersStatus.SCRAPPED).offset(offset).limit(size).order_by(
        Computers.id.desc())
    computers = (await db.execute(stmt)).scalars().all()
    return Page(total=total, items=computers)


@router.get('/repairing', response_model=Page[ComputersOut], summary='查询所有维修的电脑')
async def repairing_computers(
        request: Request,
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    offset = (page - 1) * size
    total_stmt = select(func.count()).select_from(Computers).where(
        or_(Computers.status == ComputersStatus.WAITING_REPAIR, Computers.status == ComputersStatus.REPAIRING))
    total = (await db.execute(total_stmt)).scalar()
    stmt = (select(Computers).where(
        or_(Computers.status == ComputersStatus.REPAIRING, Computers.status == ComputersStatus.WAITING_REPAIR))
            .offset(offset).limit(size).order_by(Computers.id.desc()))
    computers = (await db.execute(stmt)).scalars().all()
    return Page(total=total, items=computers)


@router.post('/create', response_model=ComputersOut, summary='添加电脑')
async def create_computer(
        request: Request,
        computer_in: ComputersCreate,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if not computer_in.asset_number or not computer_in.asset_number.strip():
        raise HTTPException(400, '资产编号不能为空')
    if not computer_in.brand or not computer_in.brand.strip():
        raise HTTPException(400, '品牌不能为空')
    if not computer_in.model or not computer_in.model.strip():
        raise HTTPException(400, '型号不能为空')
    if not computer_in.sn_code or not computer_in.sn_code.strip():
        raise HTTPException(400, 'SN码不能为空')
    if not computer_in.status:
        raise HTTPException(400, '状态不能为空')

    existing = (await db.execute(
        select(Computers).where(Computers.asset_number == computer_in.asset_number))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, '资产编号已存在!')
    sn_exist = (
        await db.execute(select(Computers).where(Computers.sn_code == computer_in.sn_code))).scalar_one_or_none()
    if sn_exist:
        raise HTTPException(400, 'sn码已存在!')

    new_computer = Computers(**computer_in.model_dump())
    db.add(new_computer)
    await db.flush()

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='create_computer', target_table='computers', target_id=new_computer.id,
        details={
            'message': f'用户 {current_user.username} 创建了电脑 {new_computer.asset_number}（品牌：{new_computer.brand}，型号：{new_computer.model}）'}
    )
    await db.commit()

    flush_computer = (await db.execute(select(Computers).options(selectinload(Computers.employee)).where(
        Computers.sn_code == computer_in.sn_code))).scalar_one_or_none()
    return flush_computer


@router.put('/{asset_number}', response_model=ComputersOut, summary='更新电脑')
async def update_computer(
        asset_number: str,
        request: Request,
        computer_in: ComputersUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    computer = (await db.execute(select(Computers).where(Computers.asset_number == asset_number))).scalar_one_or_none()
    if not computer:
        raise HTTPException(404, '资产编号不存在!')

    old_employee_id = computer.employee_id
    computer_items = computer_in.model_dump(exclude_unset=True)

    # 记录旧值
    old_values = {}
    for k in computer_items.keys():
        if hasattr(computer, k):
            old_values[k] = getattr(computer, k)

    # 处理员工字段
    has_employee_fields = any(
        k in computer_items for k in ('chinese_name', 'english_name', 'department_name', 'join_date', 'leave_date'))

    old_emp_name = None
    new_emp_name = None
    if has_employee_fields:
        chinese_name = computer_items.pop('chinese_name', None)
        english_name = computer_items.pop('english_name', None)
        department_name = computer_items.pop('department_name', None)
        join_date = computer_items.pop('join_date', None)
        leave_date = computer_items.pop('leave_date', None)

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
                        await mark_employee_leave(db, employee_id=old_employee_id, exclude_computer_id=computer.id)
                computer.employee_id = None
                new_emp_name = None
            else:
                employee = await get_or_create_employee(
                    db=db, chinese_name=chinese_name_clean,
                    english_name=english_name.strip() if english_name else None,
                    department_name=department_name.strip() if department_name else None,
                    hire_date=join_date_value, leave_date=leave_date_value
                )
                computer.employee_id = employee.id if employee else None
                new_emp_name = chinese_name_clean
        old_values['_new_emp_name'] = new_emp_name

    # 唯一性校验
    if 'asset_number' in computer_items and computer_items['asset_number'] != asset_number:
        exist = (await db.execute(select(Computers).where(Computers.asset_number == computer_items['asset_number'],
                                                          Computers.id != computer.id))).scalar_one_or_none()
        if exist:
            raise HTTPException(400, f'资产编号已被其他记录使用')
    if 'sn_code' in computer_items:
        exist = (await db.execute(select(Computers).where(Computers.sn_code == computer_items['sn_code'],
                                                          Computers.id != computer.id))).scalar_one_or_none()
        if exist:
            raise HTTPException(400, f'SN码已被其他记录使用')

    # 应用字段
    for k, v in computer_items.items():
        if hasattr(computer, k):
            setattr(computer, k, v)

    # 生成变化列表
    change_list = build_change_list(old_values, computer_items)
    if has_employee_fields and old_values.get('_old_emp_name') != old_values.get('_new_emp_name'):
        change_list.insert(0,
                           f'员工姓名：{format_value(old_values.get("_old_emp_name"))} → {format_value(old_values.get("_new_emp_name"))}')

    await db.commit()
    await db.refresh(computer)

    # 写入日志
    if change_list:
        log_msg = f'用户 {current_user.username} 更新了资产编号为{asset_number}的信息:{"；".join(change_list)}'
    else:
        log_msg = f'用户 {current_user.username} 更新了资产编号 {asset_number}（无字段变化）'

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='update_computer', target_table='Computers', target_id=computer.id,
        details={'message': log_msg, 'data': serialize_datetime(computer_items)}
    )

    stmt_return = (select(Computers).where(Computers.asset_number == computer.asset_number)
                   .options(selectinload(Computers.employee).selectinload(Employees.department)))
    computer = (await db.execute(stmt_return)).scalar_one_or_none()
    return computer


@router.delete('/{asset_number}', response_model=dict, summary='删除电脑')
async def delete_computer(
        asset_number: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    computer = (await db.execute(select(Computers).where(Computers.asset_number == asset_number))).scalar_one_or_none()
    if not computer or computer.deleted_at:
        raise HTTPException(404, '电脑不存在或已被删除')

    old_brand = computer.brand
    old_model = computer.model

    computer.deleted_at = datetime.now()
    computer.status = ComputersStatus.SCRAPPED
    await db.commit()

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='delete_computer', target_table='computers', target_id=computer.id,
        details={
            'message': f'用户 {current_user.username} 删除了电脑 {asset_number}（品牌：{old_brand}，型号：{old_model}）'}
    )
    return {'message': '删除成功'}


@router.get('/find-page/{asset_number}', summary='查找电脑在第几页')
async def find_computer_page(
        asset_number: str,
        size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _current_user: AdminUsers = Depends(get_current_user)
):
    target = (await db.execute(select(Computers).where(Computers.asset_number == asset_number))).scalar_one_or_none()
    if not target or target.deleted_at:
        return {'page': None, 'asset_number': asset_number}

    count_stmt = select(func.count()).select_from(Computers).where(
        Computers.status == ComputersStatus.NORMAL,
        Computers.deleted_at.is_(None),
        Computers.scrapped_date.is_(None),
        or_(
            Computers.purchase_date > target.purchase_date,
            and_(Computers.purchase_date == target.purchase_date, Computers.id > target.id)
        )
    )
    before_count = (await db.execute(count_stmt)).scalar() or 0
    page = (before_count // size) + 1
    return {'page': page, 'asset_number': asset_number}