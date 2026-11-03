#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""贪吃蛇 - 关卡、蛇币、皮肤、积分消耗、速度倍率"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, SnakeScores

router = APIRouter()

INITIAL_CREDITS = 50
INITIAL_POINTS = 100
POINT_COST_PER_GAME = 10
MIN_LEVEL_FOR_SHOP = 5

SKIN_CATALOG = {
    'solid_red':       {'cost': 100,   'name': '赤焰'},
    'solid_green':     {'cost': 100,   'name': '翠竹'},
    'solid_blue':      {'cost': 100,   'name': '深蓝'},
    'solid_gray':      {'cost': 100,   'name': '岩石'},
    'solid_black':     {'cost': 100,   'name': '墨玉'},
    'dual_rg':         {'cost': 200,   'name': '红绿'},
    'dual_rw':         {'cost': 200,   'name': '红白'},
    'dual_bw':         {'cost': 200,   'name': '蓝白'},
    'dual_grw':        {'cost': 200,   'name': '灰白'},
    'dual_bkw':        {'cost': 200,   'name': '黑白'},
    'dual_pw':         {'cost': 200,   'name': '粉白'},
    'rainbow':         {'cost': 500,   'name': '幻彩流光'},
    'gradient_purple': {'cost': 500,   'name': '紫气东来'},
    'gradient_sunset': {'cost': 500,   'name': '落日余晖'},
    'pattern_leopard': {'cost': 1000,  'name': '豹纹'},
    'pattern_star':    {'cost': 1000,  'name': '星空'},
    'pattern_flower':  {'cost': 1000,  'name': '花语'},
    'limited_rattlesnake': {'cost': 30000, 'name': '响尾蛇·限定'},
}

LEVEL_CONFIG = {
    1:  {'foods': 10,  'bonus': 50,   'speed': 1},
    2:  {'foods': 25,  'bonus': 100,  'speed': 2},
    3:  {'foods': 40,  'bonus': 150,  'speed': 3},
    4:  {'foods': 60,  'bonus': 200,  'speed': 4},
    5:  {'foods': 80,  'bonus': 300,  'speed': 5},
    6:  {'foods': 100, 'bonus': 400,  'speed': 6},
    7:  {'foods': 130, 'bonus': 500,  'speed': 7},
    8:  {'foods': 160, 'bonus': 600,  'speed': 8},
    9:  {'foods': 200, 'bonus': 800,  'speed': 9},
    10: {'foods': 250, 'bonus': 1000, 'speed': 10},
}


class LevelResultRequest(BaseModel):
    level: int
    level_score: int
    completed: bool
    speed_multiplier: float = 1.0


class ExchangeRequest(BaseModel):
    points: int


class SkinRequest(BaseModel):
    skin_id: str


def _parse_unlocked(raw: Optional[str]) -> list:
    return [s for s in (raw or '').split(',') if s]


def _point_rate(speed_multiplier: float) -> float:
    """速度倍率 → 积分倍率
    - 慢速 (1.5) → 积分 ×0.7
    - 标准 (1.0) → 积分 ×1.0
    - 快速 (0.75) → 积分 ×1.4
    """
    if speed_multiplier >= 1.4:
        return 0.7
    if speed_multiplier <= 0.8:
        return 1.4
    return 1.0


async def _get_or_create_row(db, user_id: int) -> SnakeScores:
    row = (await db.execute(
        select(SnakeScores).where(SnakeScores.user_id == user_id)
    )).scalar_one_or_none()
    if not row:
        row = SnakeScores(
            user_id=user_id, high_score=0,
            current_points=INITIAL_POINTS, credits=INITIAL_CREDITS,
            unlocked_skins='', equipped_skin='default', max_level=1,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get('/snake/state', summary='获取游戏状态')
async def get_state(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user),
):
    row = await _get_or_create_row(db, current_user.id)

    lb_stmt = (
        select(SnakeScores, AdminUsers)
        .join(AdminUsers, SnakeScores.user_id == AdminUsers.id)
        .order_by(desc(SnakeScores.high_score))
        .limit(20)
    )
    lb_rows = (await db.execute(lb_stmt)).all()
    leaderboard = [
        {
            'rank': i + 1,
            'user_id': u.id,
            'username': u.username,
            'chinese_name': u.chinese_name,
            'high_score': s.high_score,
            'equipped_skin': s.equipped_skin or 'default',
            'is_me': u.id == current_user.id,
        }
        for i, (s, u) in enumerate(lb_rows)
    ]

    return {
        'high_score': row.high_score,
        'current_points': row.current_points,
        'credits': row.credits,
        'unlocked_skins': _parse_unlocked(row.unlocked_skins),
        'equipped_skin': row.equipped_skin or 'default',
        'max_level': row.max_level,
        'shop_unlocked': row.max_level > MIN_LEVEL_FOR_SHOP,
        'leaderboard': leaderboard,
        'level_config': LEVEL_CONFIG,
        'initial_points': INITIAL_POINTS,
        'initial_credits': INITIAL_CREDITS,
        'cost_per_game': POINT_COST_PER_GAME,
    }


@router.post('/snake/start-game', summary='开始游戏（扣除积分）')
async def start_game(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user),
):
    row = await _get_or_create_row(db, current_user.id)
    if (row.current_points or 0) < POINT_COST_PER_GAME:
        raise HTTPException(400, '积分不足，请重置游戏或兑换后再试')
    row.current_points -= POINT_COST_PER_GAME
    await db.commit()
    await db.refresh(row)
    return {
        'current_points': row.current_points,
        'cost': POINT_COST_PER_GAME,
    }


@router.post('/snake/submit-level', summary='提交关卡成绩（含速度倍率）')
async def submit_level(
    payload: LevelResultRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user),
):
    if payload.level not in LEVEL_CONFIG:
        raise HTTPException(400, '无效关卡')
    if payload.level_score < 0 or payload.level_score > 1000000:
        raise HTTPException(400, '分数不合法')

    row = await _get_or_create_row(db, current_user.id)
    cfg = LEVEL_CONFIG[payload.level]

    rate = _point_rate(payload.speed_multiplier)
    raw_gain = payload.level_score
    if payload.completed:
        raw_gain += cfg['bonus']

    total_gain = round(raw_gain * rate)

    if payload.completed:
        if payload.level >= row.max_level and payload.level < 10:
            row.max_level = payload.level + 1
        elif payload.level == 10 and (row.max_level or 1) < 10:
            row.max_level = 10

    row.current_points = (row.current_points or 0) + total_gain

    if payload.level_score > (row.high_score or 0):
        row.high_score = payload.level_score

    await db.commit()
    await db.refresh(row)

    return {
        'gain': total_gain,
        'raw_gain': raw_gain,
        'point_rate': rate,
        'current_points': row.current_points,
        'credits': row.credits,
        'max_level': row.max_level,
        'high_score': row.high_score,
    }


@router.post('/snake/exchange', summary='积分兑换蛇币（四舍五入）')
async def exchange_points(
    payload: ExchangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user),
):
    if payload.points <= 0:
        raise HTTPException(400, '兑换积分必须大于 0')

    row = await _get_or_create_row(db, current_user.id)
    if payload.points > (row.current_points or 0):
        raise HTTPException(400, f'积分不足，当前 {row.current_points}')

    gained = round(payload.points / 10)

    row.current_points -= payload.points
    row.credits = (row.credits or 0) + gained

    await db.commit()
    await db.refresh(row)
    return {
        'gained_credits': gained,
        'current_points': row.current_points,
        'credits': row.credits,
    }


@router.post('/snake/buy-skin', summary='购买皮肤')
async def buy_skin(
    payload: SkinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user),
):
    skin_id = payload.skin_id
    if skin_id not in SKIN_CATALOG:
        raise HTTPException(400, '皮肤不存在')

    row = await _get_or_create_row(db, current_user.id)
    if (row.max_level or 1) <= MIN_LEVEL_FOR_SHOP:
        raise HTTPException(400, f'需通关 {MIN_LEVEL_FOR_SHOP} 关以上才能解锁皮肤兑换')

    unlocked = _parse_unlocked(row.unlocked_skins)
    if skin_id in unlocked:
        raise HTTPException(400, '已拥有该皮肤')

    cost = SKIN_CATALOG[skin_id]['cost']
    if (row.credits or 0) < cost:
        raise HTTPException(400, f'蛇币不足，需要 {cost}，当前 {row.credits}')

    row.credits -= cost
    unlocked.append(skin_id)
    row.unlocked_skins = ','.join(unlocked)

    await db.commit()
    return {'unlocked_skins': unlocked, 'credits': row.credits}


@router.post('/snake/equip-skin', summary='装备皮肤')
async def equip_skin(
    payload: SkinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user),
):
    skin_id = payload.skin_id
    if skin_id != 'default' and skin_id not in SKIN_CATALOG:
        raise HTTPException(400, '皮肤不存在')

    row = await _get_or_create_row(db, current_user.id)
    if skin_id != 'default':
        if skin_id not in _parse_unlocked(row.unlocked_skins):
            raise HTTPException(400, '尚未解锁该皮肤')

    row.equipped_skin = skin_id
    await db.commit()
    return {'equipped_skin': skin_id}


@router.post('/snake/reset', summary='重置游戏')
async def reset_game(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUsers = Depends(get_current_user),
):
    row = await _get_or_create_row(db, current_user.id)
    row.high_score = 0
    row.current_points = INITIAL_POINTS
    row.credits = INITIAL_CREDITS
    row.unlocked_skins = ''
    row.equipped_skin = 'default'
    row.max_level = 1
    await db.commit()
    return {
        'current_points': row.current_points,
        'credits': row.credits,
        'high_score': row.high_score,
        'max_level': row.max_level,
        'unlocked_skins': [],
        'equipped_skin': 'default',
    }