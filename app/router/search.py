from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, Computers, Monitors, Employees, Departments
from app.core.schemas import build_computer_out, build_monitors_out

router = APIRouter()


@router.get('/', summary='全局搜索')
async def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current_user: AdminUsers = Depends(get_current_user)
):
    kw = f'%{q.strip()}%'
    q_stripped = q.strip()

    # 电脑
    c_stmt = (
        select(Computers)
        .outerjoin(Employees, Computers.employee_id == Employees.id)
        .outerjoin(Departments, Employees.department_id == Departments.id)
        .where(
            Computers.deleted_at.is_(None),
            or_(
                Computers.asset_number.ilike(kw),
                Computers.sn_code.ilike(kw),
                Computers.brand.ilike(kw),
                Computers.model.ilike(kw),
                Computers.remark.ilike(kw),
                Employees.chinese_name.ilike(kw),
                Employees.english_name.ilike(kw),
                Departments.name.ilike(kw)
            )
        )
        .options(selectinload(Computers.employee).selectinload(Employees.department))
        # 排序：资产编号以关键词开头的排最前，其次包含的，最后是其他匹配
        .order_by(
            case(
                (Computers.asset_number.ilike(f'{q_stripped}%'), 1),
                (Computers.asset_number.ilike(kw), 2),
                else_=3
            ),
            Computers.id.desc()
        )
        .limit(limit)
    )
    computers = (await db.execute(c_stmt)).scalars().unique().all()

    # 显示器
    m_stmt = (
        select(Monitors)
        .outerjoin(Employees, Monitors.employee_id == Employees.id)
        .outerjoin(Departments, Employees.department_id == Departments.id)
        .where(
            Monitors.deleted_at.is_(None),
            or_(
                Monitors.asset_number.ilike(kw),
                Monitors.sn_code.ilike(kw),
                Monitors.brand.ilike(kw),
                Monitors.model.ilike(kw),
                Monitors.remark.ilike(kw),
                Employees.chinese_name.ilike(kw),
                Employees.english_name.ilike(kw),
                Departments.name.ilike(kw)
            )
        )
        .options(selectinload(Monitors.employee).selectinload(Employees.department))
        .order_by(
            case(
                (Monitors.asset_number.ilike(f'{q_stripped}%'), 1),
                (Monitors.asset_number.ilike(kw), 2),
                else_=3
            ),
            Monitors.id.desc()
        )
        .limit(limit)
    )
    monitors = (await db.execute(m_stmt)).scalars().unique().all()

    return {
        'computers': [build_computer_out(c) for c in computers],
        'monitors': [build_monitors_out(m) for m in monitors],
    }