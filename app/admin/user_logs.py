#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/9/20 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: user_logs.py,
IDE: PyCharm,
Day: 2026 - 09 - 20,
Author: Jinjing.Liu
Title:用户操作日志查询接口
Description:
    1.
    2.
"""
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import select, func, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.models import AdminOperationLogs
from app.core.authen import get_current_user
from app.core.database import get_db
from app.core.models import AdminUsers


router = APIRouter()

# 定义中文操作标签
ACTION_LABELS = {
    'login': '登录',
    'logout': '登出',
    'register': '注册',
    'update': '更新信息',
    'delete': '删除用户',
    'create_computer': '添加电脑',
    'update_computer': '更新电脑',
    'delete_computer': '删除电脑',
    'show_computers': '查询电脑列表',
    'show_scrapped_computers': '查询报废电脑',
    'show_repairing_computers': '查询维修电脑',
    'create_monitors': '添加显示器',
    'update_monitors': '更新显示器',
    'delete_monitors': '删除显示器',
    'show_monitors': '查询显示器列表',
    'show_monitors_scrapped': '查询报废显示器',
    'import_assets': '导入数据',
    'export_assets': '导出数据',
    'download_template': '下载模板',
    'reset_password': '重置密码',
    'toggle_admin': '切换管理员权限',
    'clear_avatar': '清除头像',
    'update avatar': '更新头像',
}


def build_description(log: AdminOperationLogs) -> str:
    """
    根据日志生成人类可读的语言
    优先detail的内容，然后根据操作等信息拼接
    :param log:
    :return:
    """
    if log.details and isinstance(log.details, dict):
        msg = log.details.get('message')
        if msg:
            return str(msg)
    label = ACTION_LABELS.get(log.action, log.action or '未知操作')
    if log.target_table:
        target = log.target_table
        table_names = {
            'AdminUsers': '用户',
            'Computers': '电脑',
            'computers': '电脑',
            'Monitors': '显示器',
            'monitors': '显示器',
            'Employees': '员工',
            'assets': '资产',
        }
        target = table_names.get(target, target)
        if log.target_id:
            return f'{label}({target}#{log.target_id})'
        return f'{label}({target})'
    return label


@router.get('', summary='查询操作日志')
async def show_logs(
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1,),
        username: str = Query(None, description='按用户名筛选'),
        action: str = Query(None, description='按操作类型筛选'),
        db: AsyncSession = Depends(get_db),
        _current_user: AdminUsers = Depends(get_current_user)
):
    conditions = []
    if username:
        conditions.append(AdminUsers.username.ilike(f'%{username}%'))
    if action:
        conditions.append(AdminOperationLogs.action == action)

    # 总数
    total_stmt = select(func.count()).select_from(AdminOperationLogs).outerjoin(AdminUsers, AdminOperationLogs.user_id == AdminUsers.id).where(*conditions)
    total = (await db.execute(total_stmt)).scalar() or 0
    # 数据
    offset = (page - 1) * size
    stmt = select(AdminOperationLogs, AdminUsers).outerjoin(AdminUsers, AdminOperationLogs.user_id == AdminUsers.id).where(*conditions).order_by(desc(AdminOperationLogs.created_at), desc(AdminOperationLogs.id)).offset(offset).limit(size)
    rows = (await db.execute(stmt)).all()

    items = []
    for log, user in rows:
        target_str = ''
        if log.target_table:
            table_names = {
                'AdminUsers': '用户',
                'Computers': '电脑',
                'computers': '电脑',
                'Monitors': '显示器',
                'monitors': '显示器',
                'Employees': '员工',
                'assets': '资产',
            }
            target_str = table_names.get(log.target_table, log.target_table)
            if log.target_id:
                target_str += f' #{log.target_id}'
        items.append({
            'id': log.id,
            'username': user.username,
            'chinese_name': user.chinese_name,
            'action': log.action,
            'action_label': ACTION_LABELS.get(log.action, log.action or '未知'),
            'description': build_description(log),
            'target_table': log.target_table,
            'target_id': log.target_id,
            'target_str': target_str or '-',
            'ip_address': log.ip_address or '***.***.***.***',
            'details': log.details,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M') if log.created_at else '-',
        })
    return {'total': total, 'items': items}


@router.delete('/', summary='清空日志')
async def clear_logs(
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if not current_user.is_superadmin:
        raise HTTPException(403, '权限不足!')
    await db.execute(delete(AdminOperationLogs))
    await db.commit()
    return {'message': '已清空所有操作日志'}

