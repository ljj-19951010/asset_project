#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/9/2 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: get_employee.py,
IDE: PyCharm,
Day: 2026 - 09 - 02,
Author: Jinjing.Liu
Title:优化员工导入数据
Description: 2026.09.16更新
    1.主要是导入数据时，识别员工 允许有重名！且一个人可以有多台电脑
    2.如果导入的数据中员工不存在则自动创建
    3.更新：识别员工离职状态。 用于更新数据时，前端显示员工未离职
"""
from datetime import date
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.get_department import get_or_create_department


from app.core.models import Employees, Computers, Monitors
from app.core.enums import ComputersStatus, MonitorsStatus
from app.logs.loggers import logger


async def get_or_create_employee(
        db: AsyncSession,
        chinese_name: str,
        english_name: str = None,
        department_name: str = None,
        hire_date: date = None,
        leave_date: date = None,
) -> Optional[Employees]:
    if not chinese_name:
        return None

    chinese_name = str(chinese_name).strip()
    english_name = str(english_name).strip() if english_name else None
    department_name = str(department_name).strip() if department_name else None

    # ============================================================
    # 查找：中文名去空格精确匹配 + 英文名忽略大小写
    # ============================================================
    stmt = select(Employees).where(
        func.trim(Employees.chinese_name) == chinese_name,
        Employees.deleted_at.is_(None)
    )
    if english_name:
        stmt = stmt.where(
            func.lower(func.trim(func.coalesce(Employees.english_name, ''))) == english_name.lower()
        )
    emp = (await db.execute(stmt)).scalars().first()

    # 如果按中文名+英文名找不到，再尝试只按中文名找
    if not emp and english_name:
        stmt2 = select(Employees).where(
            func.trim(Employees.chinese_name) == chinese_name,
            Employees.deleted_at.is_(None)
        )
        emp = (await db.execute(stmt2)).scalars().first()
        if emp and emp.english_name and emp.english_name.strip().lower() != english_name.lower():
            emp = None

    dept = None
    if department_name:
        dept = await get_or_create_department(db, department_name)

    if emp:
        if dept:
            emp.department_id = dept.id
        if english_name:
            emp.english_name = english_name
        if hire_date:
            emp.hire_date = hire_date
        if leave_date:
            emp.leave_date = leave_date
    else:
        emp = Employees(
            chinese_name=chinese_name,
            english_name=english_name or '',
            department_id=dept.id if dept else None,
            hire_date=hire_date,
            leave_date=leave_date
        )
        db.add(emp)
        await db.flush()
    return emp


async def _update_employee_info(
        db: AsyncSession,
        emp: Employees,
        department_name: str = None,
        hire_date: date = None,
        leave_date: date = None,
):
    """更新员工信息（部门、入职/离职时间）"""
    if department_name:
        from app.utils.get_department import get_or_create_department
        dept = await get_or_create_department(db, department_name)
        if dept:
            emp.department_id = dept.id
    if hire_date:
        emp.hire_date = hire_date
    if leave_date:
        emp.leave_date = leave_date


async def _create_new_employee(
        db: AsyncSession,
        chinese_name: str,
        english_name: str = None,
        department_name: str = None,
        hire_date: date = None,
        leave_date: date = None,
) -> Employees:
    """创建新员工"""
    dept = None
    if department_name:
        dept = await get_or_create_department(db, department_name)

    emp = Employees(
        chinese_name=chinese_name,
        english_name=english_name or '',
        department_id=dept.id if dept else None,
        hire_date=hire_date,
        leave_date=leave_date
    )
    db.add(emp)
    await db.flush()
    return emp


# 检查员工是否还有资产
async def mark_employee_leave(
        db: AsyncSession,
        employee_id: int,
        exclude_computer_id: int = None,
        exclude_monitor_id: int = None
) -> bool:
    """
    检查员工是否还有使用中的电脑或显示器，都没有则标记离职
    :param db:
    :param employee_id:
    :param exclude_computer_id:
    :param exclude_monitor_id:
    :return:
    """
    if not employee_id:
        return False
    # 1. 检查是否还有使用中的电脑
    computer_query = select(func.count()).select_from(Computers).where(
        Computers.employee_id == employee_id,
        Computers.deleted_at.is_(None),
        Computers.scrapped_date.is_(None),
        Computers.status != ComputersStatus.SCRAPPED
    )
    if exclude_computer_id:
        computer_query = computer_query.where(Computers.id != exclude_computer_id)
    computer_count = (await db.execute(computer_query)).scalar() or 0

    # 2. 检查是否还有使用中的显示器
    monitor_query = select(func.count()).select_from(Monitors).where(
        Monitors.employee_id == employee_id,
        Monitors.deleted_at.is_(None),
        Monitors.scrapped_date.is_(None),
        Monitors.status != MonitorsStatus.SCRAPPED
    )
    if exclude_monitor_id:
        monitor_query = monitor_query.where(Monitors.id != exclude_monitor_id)
    monitor_count = (await db.execute(monitor_query)).scalar() or 0

    # 3. 两者都为 0 → 标记离职
    if computer_count == 0 and monitor_count == 0:
        employee = await db.get(Employees, employee_id)
        if employee and not employee.leave_date:
            employee.leave_date = date.today()
            logger.info(f'日志:员工 {employee.chinese_name} 已无任何资产，自动标记离职')
            return True
    return False