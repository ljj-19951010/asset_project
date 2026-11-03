#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""员工管理"""
from datetime import datetime, date

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import select, func, or_, case, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, Employees, Computers, Monitors, Departments
from app.core.schemas import Page, EmployeeWithAssetsOut, AssetBrief, ChangeUserRequest, RegisterRequest, \
    CheckoutRequest
from app.logs.operation_logs import create_operation_logs
from app.utils.get_department import get_or_create_department

router = APIRouter()

STATUS_CN = {
    'normal': '正常', 'waiting_repair': '待维修',
    'repairing': '维修中', 'scrapped': '已报废',
}


async def _find_employee(db, chinese_name: str, english_name: str = None):
    """查找员工：中文名去空格精确匹配，英文名忽略大小写+去空格匹配"""
    chinese_name = (chinese_name or '').strip()
    english_name = (english_name or '').strip() if english_name else None
    if not chinese_name:
        return None

    stmt = select(Employees).where(
        func.trim(Employees.chinese_name) == chinese_name,
        Employees.deleted_at.is_(None)
    )

    if english_name:
        stmt = stmt.where(
            func.lower(func.trim(func.coalesce(Employees.english_name, ''))) == english_name.lower()
        )

    return (await db.execute(stmt)).scalars().first()


# ============================================================
#  1. 精确查询资产信息
# ============================================================
@router.get('/asset-info', summary='精确查询资产信息')
async def asset_info(
        asset_number: str = Query(...),
        asset_type: str = Query(...),
        db: AsyncSession = Depends(get_db),
        _current_user: AdminUsers = Depends(get_current_user)
):
    if asset_type == 'computer':
        asset = (await db.execute(
            select(Computers).where(Computers.asset_number == asset_number, Computers.deleted_at.is_(None))
        )).scalar_one_or_none()
    elif asset_type == 'monitor':
        asset = (await db.execute(
            select(Monitors).where(Monitors.asset_number == asset_number, Monitors.deleted_at.is_(None))
        )).scalar_one_or_none()
    else:
        raise HTTPException(400, 'asset_type 必须是 computer 或 monitor')

    if not asset:
        return {'found': False}

    has_employee = bool(asset.employee_id)
    employee_name = None
    if has_employee:
        emp = await db.get(Employees, asset.employee_id)
        employee_name = emp.chinese_name if emp else None

    return {
        'found': True,
        'asset_number': asset.asset_number,
        'brand': asset.brand or '',
        'model': asset.model or '',
        'sn_code': asset.sn_code or '',
        'status': asset.status.value if asset.status else 'normal',
        'has_employee': has_employee,
        'employee_name': employee_name,
    }


# ============================================================
#  2. 模糊搜索资产（用于下拉提示，带出历史备注）
# ============================================================
@router.get('/search-asset', summary='模糊搜索资产（同类型）')
async def search_asset(
        q: str = Query(..., min_length=1),
        asset_type: str = Query(...),
        limit: int = Query(10, ge=1, le=30),
        db: AsyncSession = Depends(get_db),
        _current_user: AdminUsers = Depends(get_current_user)
):
    kw = f'%{q.strip()}%'
    if asset_type == 'computer':
        stmt = select(Computers).where(
            Computers.deleted_at.is_(None),
            or_(Computers.asset_number.ilike(kw), Computers.sn_code.ilike(kw))
        ).limit(limit)
    elif asset_type == 'monitor':
        stmt = select(Monitors).where(
            Monitors.deleted_at.is_(None),
            or_(Monitors.asset_number.ilike(kw), Monitors.sn_code.ilike(kw))
        ).limit(limit)
    else:
        raise HTTPException(400, 'asset_type 必须是 computer 或 monitor')

    rows = (await db.execute(stmt)).scalars().all()

    results = []
    for asset in rows:
        emp = None
        if asset.employee_id:
            emp = await db.get(Employees, asset.employee_id)
        results.append({
            'asset_number': asset.asset_number,
            'brand': asset.brand or '',
            'model': asset.model or '',
            'sn_code': asset.sn_code or '',
            'status': asset.status.value if asset.status else 'normal',
            'has_employee': bool(asset.employee_id),
            'employee_name': emp.chinese_name if emp else None,
            'remark': asset.remark or '',
        })
    return results


# ============================================================
#  3. 新员工入职登记（支持修改备注）
# ============================================================
@router.post('/register', summary='新员工入职登记')
async def register_employee(
        request: Request,
        payload: RegisterRequest,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    chinese_name = (payload.chinese_name or '').strip()
    if not chinese_name:
        raise HTTPException(400, '员工中文名不能为空')

    employee = await _find_employee(db, chinese_name, payload.english_name)
    dept = None
    if payload.department_name:
        dept = await get_or_create_department(db, payload.department_name.strip())

    if not employee:
        employee = Employees(
            chinese_name=chinese_name,
            english_name=(payload.english_name or '').strip(),
            department_id=dept.id if dept else None,
            hire_date=payload.hire_date.date() if payload.hire_date else date.today(),
        )
        db.add(employee)
        await db.flush()
    else:
        if employee.leave_date:
            employee.leave_date = None
        if dept:
            employee.department_id = dept.id
        if payload.hire_date and not employee.hire_date:
            employee.hire_date = payload.hire_date.date()

    today = datetime.now().strftime('%Y年%m月%d日')
    today_dt = datetime.now()

    # 绑定电脑
    c_bound = None
    if payload.computer_asset_number and payload.computer_asset_number.strip():
        c_asset = payload.computer_asset_number.strip()
        c = (await db.execute(
            select(Computers).where(Computers.asset_number == c_asset, Computers.deleted_at.is_(None))
        )).scalar_one_or_none()
        if not c:
            raise HTTPException(404, f'电脑 {c_asset} 不存在')

        if c.employee_id and c.employee_id != employee.id:
            old_emp = await db.get(Employees, c.employee_id)
            old_name = old_emp.chinese_name if old_emp else '未知'
            if not payload.force:
                raise HTTPException(409, f'电脑 {c_asset} 已被 {old_name} 使用')
            c.remark = f'原{old_name}'

        c.employee_id = employee.id
        c.leave_date = None

        if payload.computer_remark is not None and payload.computer_remark.strip():
            c.remark = payload.computer_remark.strip()

        if c.status and c.status.value != 'normal':
            c.status = 'normal'
            c.scrapped_date = None
        c_bound = c.asset_number

    # 绑定显示器
    m_bound = None
    if payload.monitor_asset_number and payload.monitor_asset_number.strip():
        m_asset = payload.monitor_asset_number.strip()
        m = (await db.execute(
            select(Monitors).where(Monitors.asset_number == m_asset, Monitors.deleted_at.is_(None))
        )).scalar_one_or_none()
        if not m:
            raise HTTPException(404, f'显示器 {m_asset} 不存在')

        if m.employee_id and m.employee_id != employee.id:
            old_emp = await db.get(Employees, m.employee_id)
            old_name = old_emp.chinese_name if old_emp else '未知'
            if not payload.force:
                raise HTTPException(409, f'显示器 {m_asset} 已被 {old_name} 使用')
            m.remark = f'原{old_name}'

        m.employee_id = employee.id
        m.leave_date = None

        if payload.monitor_remark is not None and payload.monitor_remark.strip():
            m.remark = payload.monitor_remark.strip()

        if m.status and m.status.value != 'normal':
            m.status = 'normal'
            m.scrapped_date = None
        m_bound = m.asset_number

    await db.commit()

    bound_info = []
    if c_bound:
        bound_info.append(f'电脑 {c_bound}')
    if m_bound:
        bound_info.append(f'显示器 {m_bound}')
    detail = '、'.join(bound_info) if bound_info else '无设备'

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='employee_register', target_table='employees', target_id=employee.id,
        details={'message': f'用户 {current_user.username} 登记员工 {chinese_name} 入职，分配设备：{detail}' + (
            '（强制覆盖）' if payload.force else '')}
    )

    return {
        'message': '登记成功',
        'employee_id': employee.id,
        'chinese_name': chinese_name,
        'computer_asset_number': c_bound,
        'monitor_asset_number': m_bound,
    }


# ============================================================
#  4. 员工离职
# ============================================================
@router.post('/checkout', summary='员工离职')
async def checkout(
        request: Request,
        payload: CheckoutRequest,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if payload.asset_type == 'computer':
        asset = (await db.execute(
            select(Computers).where(Computers.asset_number == payload.asset_number))).scalar_one_or_none()
    elif payload.asset_type == 'monitor':
        asset = (await db.execute(
            select(Monitors).where(Monitors.asset_number == payload.asset_number))).scalar_one_or_none()
    else:
        raise HTTPException(400, 'asset_type 必须是 computer 或 monitor')

    if not asset:
        raise HTTPException(404, '未找到该资产')
    if not asset.employee_id:
        raise HTTPException(400, '该资产当前没有绑定员工')

    employee = await db.get(Employees, asset.employee_id)
    if not employee:
        raise HTTPException(404, '未找到员工信息')

    today_dt = datetime.now()
    today_str = today_dt.strftime('%Y年%m月%d日')

    employee.leave_date = today_dt.date()

    c_rows = (await db.execute(
        select(Computers).where(
            Computers.employee_id == employee.id,
            Computers.deleted_at.is_(None)
        )
    )).scalars().all()

    for c in c_rows:
        c.employee_id = None
        c.leave_date = today_dt.date()
        c.replace_time = today_dt
        c.remark = f'{today_str} {employee.chinese_name} 离职'

    m_rows = (await db.execute(
        select(Monitors).where(
            Monitors.employee_id == employee.id,
            Monitors.deleted_at.is_(None)
        )
    )).scalars().all()

    for m in m_rows:
        m.employee_id = None
        m.leave_date = today_dt.date()
        m.replace_time = today_dt
        m.remark = f'{today_str} {employee.chinese_name} 离职'

    await db.commit()

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='employee_checkout', target_table='employees', target_id=employee.id,
        details={'message': f'用户 {current_user.username} 将员工 {employee.chinese_name} 标记离职，'
                            f'并自动回收电脑 {len(c_rows)} 台、显示器 {len(m_rows)} 台'}
    )

    return {
        'message': '离职登记成功，资产已全部回收',
        'employee_name': employee.chinese_name,
        'released_computers': len(c_rows),
        'released_monitors': len(m_rows)
    }


# ============================================================
#  5. 员工列表 (增加了排序支持)
# ============================================================
@router.get('/', response_model=Page[EmployeeWithAssetsOut], summary='员工列表')
async def list_employees(
        q: str = Query(None),
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        sort_by: str = Query(None),
        sort_order: str = Query(None),
        db: AsyncSession = Depends(get_db),
        _current_user: AdminUsers = Depends(get_current_user)
):
    keyword = (q or '').strip()

    # 【修复】移除 case，使用最基础的 is_(None) 来排序状态
    order_clauses = []
    if sort_by == 'hire_date':
        order_clauses.append(asc(Employees.hire_date) if sort_order == 'asc' else desc(Employees.hire_date))
    elif sort_by == 'leave_date':
        order_clauses.append(asc(Employees.leave_date) if sort_order == 'asc' else desc(Employees.leave_date))
    elif sort_by == 'status':
        # leave_date 为 None(在职) 时返回 True(1)，有离职时间返回 False(0)
        # desc(True) 会让 True(在职) 在前，对应 asc
        # asc(False) 会让 False(离职) 在前，对应 desc
        col = Employees.leave_date.is_(None)
        order_clauses.append(desc(col) if sort_order == 'asc' else asc(col))

    if not order_clauses:
        order_clauses = [desc(Employees.hire_date), desc(Employees.id)]
    else:
        order_clauses.append(desc(Employees.id))

    if keyword:
        kw = f'%{keyword}%'
        emp_stmt = select(Employees.id).where(
            Employees.deleted_at.is_(None),
            or_(Employees.chinese_name.ilike(kw), Employees.english_name.ilike(kw))
        )
        emp_ids = set((await db.execute(emp_stmt)).scalars().all())

        c_stmt = select(Computers.employee_id).where(
            Computers.deleted_at.is_(None), Computers.employee_id.isnot(None),
            or_(Computers.asset_number.ilike(kw), Computers.sn_code.ilike(kw))
        )
        m_stmt = select(Monitors.employee_id).where(
            Monitors.deleted_at.is_(None), Monitors.employee_id.isnot(None),
            or_(Monitors.asset_number.ilike(kw), Monitors.sn_code.ilike(kw))
        )
        emp_ids.update((await db.execute(c_stmt)).scalars().all())
        emp_ids.update((await db.execute(m_stmt)).scalars().all())
        emp_ids.discard(None)

        if not emp_ids:
            return Page(total=0, items=[])

        total = len(emp_ids)
        emp_list_stmt = (
            select(Employees).where(Employees.id.in_(emp_ids))
            .order_by(*order_clauses)
            .offset((page - 1) * size).limit(size)
        )
        employees = (await db.execute(emp_list_stmt)).scalars().all()
    else:
        total = (await db.execute(
            select(func.count()).select_from(Employees).where(Employees.deleted_at.is_(None))
        )).scalar() or 0
        stmt = (
            select(Employees).where(Employees.deleted_at.is_(None))
            .order_by(*order_clauses)
            .offset((page - 1) * size).limit(size)
        )
        employees = (await db.execute(stmt)).scalars().all()

    results = []
    for emp in employees:
        dept_name = None
        if emp.department_id:
            dept = await db.get(Departments, emp.department_id)
            dept_name = dept.name if dept else None

        c_rows = (await db.execute(
            select(Computers).where(Computers.employee_id == emp.id, Computers.deleted_at.is_(None))
        )).scalars().all()
        m_rows = (await db.execute(
            select(Monitors).where(Monitors.employee_id == emp.id, Monitors.deleted_at.is_(None))
        )).scalars().all()

        results.append(EmployeeWithAssetsOut(
            id=emp.id,
            chinese_name=emp.chinese_name,
            english_name=emp.english_name,
            department_name=dept_name,
            hire_date=emp.hire_date,
            leave_date=emp.leave_date,
            computers=[AssetBrief(asset_number=c.asset_number, brand=c.brand, model=c.model, sn_code=c.sn_code,
                                  replace_time=c.replace_time, remark=c.remark) for c in c_rows],
            monitors=[AssetBrief(asset_number=m.asset_number, brand=m.brand, model=m.model, sn_code=m.sn_code,
                                 replace_time=m.replace_time, remark=m.remark) for m in m_rows],
        ))

    return Page(total=total, items=results)


# ============================================================
#  6. 资产列表（设备使用人管理用）
# ============================================================
@router.get('/asset-list', summary='资产列表（含当前使用人）')
async def asset_list(
        q: str = Query(None),
        asset_type: str = Query('all'),
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _current_user: AdminUsers = Depends(get_current_user)
):
    keyword = (q or '').strip()
    kw = f'%{keyword}%' if keyword else None
    all_items = []

    if asset_type in ('all', 'computer'):
        c_stmt = (
            select(Computers)
            .outerjoin(Employees, Computers.employee_id == Employees.id)
            .outerjoin(Departments, Employees.department_id == Departments.id)
            .where(Computers.deleted_at.is_(None))
            .options(selectinload(Computers.employee).selectinload(Employees.department))
        )
        if kw:
            c_stmt = c_stmt.where(or_(
                Computers.asset_number.ilike(kw), Computers.sn_code.ilike(kw),
                Computers.brand.ilike(kw), Computers.model.ilike(kw),
                Employees.chinese_name.ilike(kw), Employees.english_name.ilike(kw),
            ))
        c_rows = (await db.execute(c_stmt)).scalars().unique().all()
        for c in c_rows:
            emp = c.employee
            all_items.append({
                'asset_type': 'computer',
                'asset_number': c.asset_number,
                'brand': c.brand, 'model': c.model, 'sn_code': c.sn_code,
                'status': c.status.value if c.status else 'normal',
                'employee_id': emp.id if emp else None,
                'chinese_name': emp.chinese_name if emp else None,
                'english_name': emp.english_name if emp else None,
                'department_name': emp.department.name if emp and emp.department else None,
                'leave_date': emp.leave_date.isoformat() if emp and emp.leave_date else None,
                'replace_time': c.replace_time.isoformat() if c.replace_time else None,
                'remark': c.remark,
            })

    if asset_type in ('all', 'monitor'):
        m_stmt = (
            select(Monitors)
            .outerjoin(Employees, Monitors.employee_id == Employees.id)
            .outerjoin(Departments, Employees.department_id == Departments.id)
            .where(Monitors.deleted_at.is_(None))
            .options(selectinload(Monitors.employee).selectinload(Employees.department))
        )
        if kw:
            m_stmt = m_stmt.where(or_(
                Monitors.asset_number.ilike(kw), Monitors.sn_code.ilike(kw),
                Monitors.brand.ilike(kw), Monitors.model.ilike(kw),
                Employees.chinese_name.ilike(kw), Employees.english_name.ilike(kw),
            ))
        m_rows = (await db.execute(m_stmt)).scalars().unique().all()
        for m in m_rows:
            emp = m.employee
            all_items.append({
                'asset_type': 'monitor',
                'asset_number': m.asset_number,
                'brand': m.brand, 'model': m.model, 'sn_code': m.sn_code,
                'status': m.status.value if m.status else 'normal',
                'employee_id': emp.id if emp else None,
                'chinese_name': emp.chinese_name if emp else None,
                'english_name': emp.english_name if emp else None,
                'department_name': emp.department.name if emp and emp.department else None,
                'leave_date': emp.leave_date.isoformat() if emp and emp.leave_date else None,
                'replace_time': m.replace_time.isoformat() if m.replace_time else None,
                'remark': m.remark,
            })

    all_items.sort(key=lambda x: x['asset_number'])
    total = len(all_items)
    offset = (page - 1) * size
    return {'total': total, 'items': all_items[offset:offset + size], 'page': page, 'size': size}


# ============================================================
#  7. 更换使用人
# ============================================================
@router.put('/change-user', summary='更换使用人')
async def change_user(
        request: Request,
        payload: ChangeUserRequest,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    chinese_name = (payload.chinese_name or '').strip()
    if not chinese_name:
        raise HTTPException(400, '新员工中文名不能为空')

    if payload.asset_type == 'computer':
        asset = (await db.execute(
            select(Computers).where(Computers.asset_number == payload.asset_number))).scalar_one_or_none()
    elif payload.asset_type == 'monitor':
        asset = (await db.execute(
            select(Monitors).where(Monitors.asset_number == payload.asset_number))).scalar_one_or_none()
    else:
        raise HTTPException(400, 'asset_type 必须是 computer 或 monitor')
    if not asset:
        raise HTTPException(404, '未找到该资产')

    asset_status = asset.status.value if asset.status else 'normal'
    status_changed_from = None
    if asset_status != 'normal':
        if not payload.force:
            raise HTTPException(409, f'该资产当前状态为「{STATUS_CN.get(asset_status, asset_status)}」，是否继续？')
        status_changed_from = asset_status

    old_emp = await db.get(Employees, asset.employee_id) if asset.employee_id else None

    new_emp = await _find_employee(db, chinese_name, payload.english_name)
    dept = None
    if payload.department_name:
        dept = await get_or_create_department(db, payload.department_name.strip())

    if not new_emp:
        new_emp = Employees(
            chinese_name=chinese_name,
            english_name=(payload.english_name or '').strip(),
            department_id=dept.id if dept else None,
            hire_date=date.today(),
        )
        db.add(new_emp)
        await db.flush()
    else:
        if new_emp.leave_date:
            new_emp.leave_date = None
        if dept:
            new_emp.department_id = dept.id

    asset.employee_id = new_emp.id
    asset.leave_date = None
    asset.replace_time = datetime.now()
    if old_emp:
        asset.remark = f'原{old_emp.chinese_name}'
    if status_changed_from:
        asset.status = 'normal'
        asset.scrapped_date = None

    await db.commit()

    old_name = old_emp.chinese_name if old_emp else '空'
    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='employee_change_user', target_table=payload.asset_type + 's', target_id=asset.id,
        details={
            'message': f'用户 {current_user.username} 将 {asset.asset_number} 的使用人从 {old_name} 更换为 {chinese_name}'}
    )
    return {'message': '更换成功', 'old_employee': old_name, 'new_employee': chinese_name}


# ============================================================
#  8. 更新员工
# ============================================================
@router.put('/{employee_id}', summary='更新员工信息')
async def update_employee(
        employee_id: int,
        request: Request,
        payload: dict,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    emp = await db.get(Employees, employee_id)
    if not emp:
        raise HTTPException(404, '员工不存在')

    if 'chinese_name' in payload and payload['chinese_name']:
        emp.chinese_name = payload['chinese_name'].strip()
    if 'english_name' in payload:
        emp.english_name = (payload['english_name'] or '').strip()
    if 'department_name' in payload and payload['department_name']:
        dept = await get_or_create_department(db, payload['department_name'].strip())
        emp.department_id = dept.id
    if 'hire_date' in payload:
        emp.hire_date = datetime.fromisoformat(payload['hire_date'].replace('Z', '')).date() if payload[
            'hire_date'] else None
    if 'leave_date' in payload:
        emp.leave_date = datetime.fromisoformat(payload['leave_date'].replace('Z', '')).date() if payload[
            'leave_date'] else None

    await db.commit()
    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='employee_update', target_table='employees', target_id=emp.id,
        details={'message': f'用户 {current_user.username} 更新了员工 {emp.chinese_name} 的信息'}
    )
    return {'message': '更新成功'}


# ============================================================
#  9. 删除员工
# ============================================================
@router.delete('/{employee_id}', summary='删除员工')
async def delete_employee(
        employee_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    emp = await db.get(Employees, employee_id)
    if not emp:
        raise HTTPException(404, '员工不存在')

    emp_name = emp.chinese_name
    c_rows = (await db.execute(select(Computers).where(Computers.employee_id == employee_id))).scalars().all()
    m_rows = (await db.execute(select(Monitors).where(Monitors.employee_id == employee_id))).scalars().all()

    today_dt = datetime.now()
    today_str = today_dt.strftime('%Y年%m月%d日')
    for c in c_rows:
        c.employee_id = None
        c.leave_date = today_dt.date()
        c.replace_time = today_dt
        c.remark = f'{today_str} {emp_name} 被删除'
    for m in m_rows:
        m.employee_id = None
        m.leave_date = today_dt.date()
        m.replace_time = today_dt
        m.remark = f'{today_str} {emp_name} 被删除'

    await db.delete(emp)
    await db.commit()
    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='employee_delete', target_table='employees', target_id=employee_id,
        details={
            'message': f'用户 {current_user.username} 删除了员工 {emp_name}（解绑 {len(c_rows)} 台电脑、{len(m_rows)} 台显示器）'}
    )
    return {'message': '删除成功'}


# ============================================================
#  10. 批量删除员工
# ============================================================
@router.post('/batch-delete', summary='批量删除员工')
async def batch_delete_employees(
        request: Request,
        payload: dict,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    employee_ids = payload.get('employee_ids', [])
    if not employee_ids or not isinstance(employee_ids, list):
        raise HTTPException(400, '请选择要删除的员工')

    emps = (await db.execute(select(Employees).where(Employees.id.in_(employee_ids)))).scalars().all()
    if not emps:
        raise HTTPException(404, '未找到要删除的员工')

    today_dt = datetime.now()
    today_str = today_dt.strftime('%Y年%m月%d日')
    total_c = 0
    total_m = 0

    for emp in emps:
        c_rows = (await db.execute(select(Computers).where(Computers.employee_id == emp.id))).scalars().all()
        for c in c_rows:
            c.employee_id = None
            c.leave_date = today_dt.date()
            c.replace_time = today_dt
            c.remark = f'{today_str} {emp.chinese_name} 被删除'
        total_c += len(c_rows)

        m_rows = (await db.execute(select(Monitors).where(Monitors.employee_id == emp.id))).scalars().all()
        for m in m_rows:
            m.employee_id = None
            m.leave_date = today_dt.date()
            m.replace_time = today_dt
            m.remark = f'{today_str} {emp.chinese_name} 被删除'
        total_m += len(m_rows)

        await db.delete(emp)

    await db.commit()
    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='employee_batch_delete', target_table='employees', target_id=0,
        details={
            'message': f'用户 {current_user.username} 批量删除了 {len(emps)} 名员工，解绑电脑 {total_c} 台、显示器 {total_m} 台'}
    )
    return {'message': f'成功删除 {len(emps)} 名员工', 'deleted_count': len(emps)}


@router.post('/clear-user', summary='清空资产当前使用人（不离职）')
async def clear_user(
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
        asset = (await db.execute(select(Computers).where(Computers.asset_number == asset_number))).scalar_one_or_none()
    elif asset_type == 'monitor':
        asset = (await db.execute(select(Monitors).where(Monitors.asset_number == asset_number))).scalar_one_or_none()
    else:
        raise HTTPException(400, 'asset_type 必须是 computer 或 monitor')

    if not asset:
        raise HTTPException(404, '未找到该资产')
    if not asset.employee_id:
        raise HTTPException(400, '该资产当前没有绑定员工')

    old_emp = await db.get(Employees, asset.employee_id)
    old_name = old_emp.chinese_name if old_emp else '未知'

    asset.employee_id = None
    asset.remark = f'原{old_name}'
    asset.replace_time = datetime.now()

    await db.commit()

    await create_operation_logs(
        db=db, request=request, user_id=current_user.id,
        action='employee_clear_user', target_table=asset_type + 's', target_id=asset.id,
        details={'message': f'用户 {current_user.username} 清空了 {asset_type} {asset_number} 的使用人（原{old_name}）'}
    )

    return {'message': '已清空使用人', 'old_employee': old_name}