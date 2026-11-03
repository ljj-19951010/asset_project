#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: user.py,
Title:后台管理
"""
import secrets
import string
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.database import get_db
from app.core.models import AdminUsers
from app.core.schemas import UserOut, Token, UserLogin, UserRegister, UserUpdate, Page
from app.logs.loggers import logger
from app.logs.operation_logs import create_operation_logs
from app.core.authen import verify_password, get_current_user, create_access_token, generate_password
from app.utils.get_users import check_username, check_password


router = APIRouter()
AVATAR_DIR = Path('static/avatars')
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/me", response_model=UserOut, summary='查看个人信息')
async def show_me(
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    result = await db.execute(select(AdminUsers).where(AdminUsers.id == current_user.id))
    user = result.scalar_one_or_none()
    return user


@router.post('/login', response_model=Token, summary='登录')
async def login(
        user_login: UserLogin,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(AdminUsers).where(AdminUsers.username == user_login.username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户名不存在')

    if not user_login.password:
        raise HTTPException(400, '密码不能为空!')

    if not verify_password(user_login.password, user.password_hash):
        raise HTTPException(400, '密码错误')

    if user.deleted_at:
        raise HTTPException(400, '用户已被删除!')

    token_data = {'sub': user.username}
    access_token = create_access_token(token_data)

    try:
        await create_operation_logs(
            db=db,
            user_id=user.id,
            action='login',
            request=request,
            target_table='AdminUsers',
            target_id=user.id,
            details={
                'message': f'用户 {user.username} 登录成功'
            }
        )
    except Exception as e:
        logger.error(f'日志添加失败:{e}')
    logger.info(f'日志:用户{user_login.username}登录成功！')
    return Token(access_token=access_token)


@router.post('/register', response_model=UserOut, summary='注册')
async def register(
        request: Request,
        user_register: UserRegister,
        db: AsyncSession = Depends(get_db)
):
    ok, msg = check_username(user_register.username)
    if not ok:
        raise HTTPException(400, msg)

    ok, msg = check_password(user_register.password)
    if not ok:
        raise HTTPException(400, msg)

    result = await db.execute(select(AdminUsers).where(AdminUsers.username == user_register.username))
    user = result.scalar_one_or_none()
    if user:
        logger.warning('日志：用户名已存在!')
        raise HTTPException(400, '用户名已存在!')

    if not user_register.username or not user_register.password:
        raise HTTPException(400, '用户名或密码不能为空')

    user_data = user_register.model_dump(exclude={'password'}, exclude_unset=True)
    hash_pwd = generate_password(user_register.password)
    new_user = AdminUsers(**user_data, password_hash=hash_pwd)
    new_user.join_date = datetime.now()

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    try:
        await create_operation_logs(
            db=db,
            request=request,
            user_id=new_user.id,
            action='register',
            target_table='AdminUsers',
            target_id=new_user.id,
            details={
                'message': f'新用户注册：{new_user.username}（{new_user.chinese_name}）'
            }
        )
    except Exception as e:
        logger.error(f'日志添加失败:{e}')
    logger.info(f'日志: 注册成功! 用户名:{new_user.username}')
    return new_user


@router.put('/update_me', response_model=UserOut, summary='更新当前用户的信息')
async def update_me(
        user_update: UserUpdate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    result = await db.execute(select(AdminUsers).where(AdminUsers.username == current_user.username))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning(f'日志:当前用户{current_user.username}与你要更新的用户信息不符!无法更新')
        raise HTTPException(400, '当前用户与你要更新的用户信息不符!')

    user_id = user.id
    update_data = user_update.model_dump(exclude_unset=True)
    if 'password' in update_data:
        if verify_password(update_data['password'], current_user.password_hash):
            raise HTTPException(400, '新密码不能与当前密码相同!')
        current_user.password_hash = generate_password(update_data['password'])

    for key, value in update_data.items():
        if hasattr(current_user, key):
            setattr(current_user, key, value)
    await db.commit()

    fresh_user = await db.get(AdminUsers, user_id)

    try:
        def convert_dates(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        # 详细日志
        change_list = []
        for k, v in update_data.items():
            if k == 'password':
                change_list.append('密码已修改')
            else:
                change_list.append(f'{k}: {v}')

        log_msg = f'用户 {current_user.username} 更新个人信息：{"；".join(change_list)}'
        log_details = {
            'message': log_msg,
            'data': {k: convert_dates(v) for k, v in update_data.items()}
        }
        await create_operation_logs(
            db=db,
            request=request,
            user_id=current_user.id,
            action='update',
            target_table='AdminUsers',
            target_id=current_user.id,
            details=log_details
        )
    except Exception as e:
        logger.error(f'日志:当前用户更新失败,{e}')
        await db.rollback()

    logger.info(f'日志:{current_user.username}更新信息成功!')
    return fresh_user


@router.get('/', response_model=Page[UserOut], summary='查看所有用户')
async def show_users(
        page:int = Query(1, ge=1),
        size:int = Query(10, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if current_user.is_superadmin == False:
        total_stmt = select(func.count()).select_from(AdminUsers).where(AdminUsers.deleted_at == None)
        total = (await db.execute(total_stmt)).scalar()
        offset = (page-1) * size
        result = await db.execute(select(AdminUsers).where(AdminUsers.deleted_at == None).offset(offset).limit(size).order_by(AdminUsers.join_date))
        users = result.scalars().all()
        return Page(total=total, items=users)
    else:
        total_stmt = select(func.count()).select_from(AdminUsers)
        total = (await db.execute(total_stmt)).scalar()
        offset = (page - 1) * size
        result = await db.execute(
            select(AdminUsers).offset(offset).limit(size).order_by(AdminUsers.join_date))
        users = result.scalars().all()
        return Page(total=total, items=users)


@router.delete('/user_id', summary='删除用户')
async def del_user(
        user_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if current_user.is_superadmin == False:
        raise HTTPException(400, '权限不足，无法删除')
    if current_user.id == user_id:
        raise HTTPException(400, '当前用户已登录，不能删除!')

    result = await db.execute(select(AdminUsers).where(AdminUsers.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.deleted_at:
        raise HTTPException(404, '用户不存在或已被删除')

    # 保存旧信息
    old_username = user.username
    old_chinese_name = user.chinese_name

    user.deleted_at = datetime.now()
    if user.is_superadmin:
        user.is_superadmin = False

    await db.commit()
    await db.refresh(user)
    try:
        await create_operation_logs(
            db=db,
            request=request,
            user_id=current_user.id,
            action='delete',
            target_table='AdminUsers',
            target_id=user_id,
            details={
                'message': f'删除了用户 {old_username}（{old_chinese_name}）'
            }
        )
    except Exception as e:
        logger.error(f'日志:删除失败! {e}')
        await db.rollback()
    logger.info(f'日志:超级管理员用户{current_user.username}删除了{user.username}!')
    return None


@router.put('/avatar', summary='上传头像')
async def upload_avatar(
        request: Request,
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if not file.content_type.startswith('image/'):
        logger.warning(f'日志:{current_user.username}上传头像失败，格式错误!')
        raise HTTPException(400, '仅支持图片格式类型!')
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        logger.warning(f'日志:{current_user.username}上传头像失败，超过了5MB!')
        raise HTTPException(400, '图片大小不能超过5MB')
    ext = file.filename.split('.')[-1]
    filename = f'user_{current_user.id}_{int(datetime.now().timestamp())}.{ext}'
    file_path = AVATAR_DIR / filename

    with open(file_path, 'wb') as f:
        f.write(contents)
    if current_user.avatar:
        old_path = Path(current_user.avatar.lstrip('/'))
        if old_path.exists() and old_path.parents == AVATAR_DIR:
            old_path.unlink(missing_ok=True)
    avatar_url = f'/static/avatars/{filename}'
    current_user.avatar = avatar_url
    await db.commit()
    await db.refresh(current_user)

    await create_operation_logs(
        db=db,
        request=request,
        user_id=current_user.id,
        action='update avatar',
        target_table='AdminUsers',
        target_id=current_user.id,
        details={'message': f'用户 {current_user.username} 更新了头像'}
    )
    logger.info(f'日志:{current_user.username}更新了头像!')
    return {'avatar': avatar_url}


@router.delete('/avatar', summary='清除头像')
async def clear_avatar(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user)
):
    if current_user.avatar:
        old_path = Path(current_user.avatar.lstrip('/'))
        if old_path.exists() and old_path.parent == AVATAR_DIR:
            old_path.unlink(missing_ok=True)
        current_user.avatar = None
        await db.commit()
        await db.refresh(current_user)
        await create_operation_logs(
            db=db,
            request=request,
            user_id=current_user.id,
            action='clear_avatar',
            target_table='AdminUsers',
            target_id=current_user.id,
            details={'message': f'用户 {current_user.username} 清除了头像'}
        )
        logger.info(f'用户 {current_user.username} 清除了头像')
    return {'avatar': None}


@router.put('/reset_password/{user_id}', summary='重置用户密码')
async def reset_password(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user)
):
    if not current_user.is_superadmin:
        raise HTTPException(403, "权限不足")
    user = await db.get(AdminUsers, user_id)
    if not user or user.deleted_at:
        raise HTTPException(404, "用户不存在或已删除")
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    new_password = ''.join(secrets.choice(chars) for _ in range(8))
    user.password_hash = generate_password(new_password)
    await db.commit()
    await create_operation_logs(
        db=db,
        request=request,
        user_id=current_user.id,
        action='reset_password',
        target_table='AdminUsers',
        target_id=user.id,
        details={'message': f'重置了用户 {user.username} 的密码'}
    )
    return {"new_password": new_password}


@router.put('/toggle_admin/{user_id}', summary='切换超级管理员')
async def toggle_admin(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user)
):
    if not current_user.is_superadmin:
        raise HTTPException(403, "权限不足")
    if user_id == current_user.id:
        raise HTTPException(400, "不能修改自己的权限")
    user = await db.get(AdminUsers, user_id)
    if not user or user.deleted_at:
        raise HTTPException(404, "用户不存在或已删除")
    user.is_superadmin = not user.is_superadmin
    await db.commit()

    action_word = "设为" if user.is_superadmin else "取消"
    await create_operation_logs(
        db=db,
        request=request,
        user_id=current_user.id,
        action='toggle_admin',
        target_table='AdminUsers',
        target_id=user.id,
        details={'message': f'{action_word}用户 {user.username} 的超级管理员权限'}
    )
    return {"is_superadmin": user.is_superadmin}