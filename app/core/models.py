from datetime import datetime, date
from typing import Optional

import decimal


from sqlalchemy import DECIMAL, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, JSON, String, Text, text, \
    Column, ForeignKey
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import AdminUsersGender, ComputersStatus, MonitorsStatus


class AdminUsers(Base):
    __tablename__ = 'admin_users'
    __table_args__ = (
        Index('idx_deleted_at', 'deleted_at'),
        Index('idx_username', 'username'),
        Index('username', 'username', unique=True)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(200, 'utf8mb4_unicode_ci'), nullable=False, comment='登录用户名')
    password_hash: Mapped[str] = mapped_column(String(255, 'utf8mb4_unicode_ci'), nullable=False, comment='密码哈希（建议bcrypt）')
    chinese_name: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='中文名')
    english_name: Mapped[str] = mapped_column(String(100, 'utf8mb4_unicode_ci'), nullable=False, comment='英文名')
    email: Mapped[str] = mapped_column(String(150, 'utf8mb4_unicode_ci'), comment='邮箱')
    is_superadmin: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("'0'"), comment='是否为超级管理员')
    gender: Mapped[Optional[AdminUsersGender]] = mapped_column(Enum(AdminUsersGender, values_callable=lambda cls: [member.value for member in cls]), comment='性别')
    age: Mapped[Optional[int]] = mapped_column(Integer, comment='年龄')
    join_date: Mapped[Optional[date]] = mapped_column(Date, comment='管理员入职时间（非必须）')
    avatar: Mapped[Optional[str]] = mapped_column(String(255, 'utf8mb4_unicode_ci'), comment='当前头像路径/URL')
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment='软删除时间')

    admin_operation_logs: Mapped[list['AdminOperationLogs']] = relationship('AdminOperationLogs', back_populates='admin_user')


class Departments(Base):
    __tablename__ = 'departments'
    __table_args__ = (
        Index('idx_deleted_at', 'deleted_at'),
        Index('name', 'name', unique=True)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100, 'utf8mb4_unicode_ci'), nullable=False, comment='科室名称')
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment='软删除时间')

    employees: Mapped[list['Employees']] = relationship('Employees', back_populates='department')


class AdminOperationLogs(Base):
    __tablename__ = 'admin_operation_logs'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['admin_users.id'], ondelete='RESTRICT', name='admin_operation_logs_ibfk_1'),
        Index('idx_action', 'action'),
        Index('idx_admin', 'user_id'),
        Index('idx_created', 'created_at')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='操作人ID')
    action: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='操作类型（如 login, update_asset, assign_asset, update_avatar 等）')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='操作时间')
    target_table: Mapped[Optional[str]] = mapped_column(String(50, 'utf8mb4_unicode_ci'), comment='操作的目标表名（如 computers, employees, admin_users）')
    target_id: Mapped[Optional[int]] = mapped_column(Integer, comment='操作的目标记录ID')
    ip_address: Mapped[Optional[str]] = mapped_column(String(45, 'utf8mb4_unicode_ci'), comment='操作者IP')
    user_agent: Mapped[Optional[str]] = mapped_column(Text(collation='utf8mb4_unicode_ci'), comment='浏览器/客户端信息')
    details: Mapped[Optional[dict]] = mapped_column(JSON, comment='操作详情（JSON格式，例如 {"old_employee_id": 5, "new_employee_id": 12}）')

    admin_user: Mapped['AdminUsers'] = relationship('AdminUsers', back_populates='admin_operation_logs')


class Employees(Base):
    __tablename__ = 'employees'
    __table_args__ = (
        ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL', name='employees_ibfk_1'),
        Index('idx_deleted_at', 'deleted_at'),
        Index('idx_dept', 'department_id')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chinese_name: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='中文名')
    english_name: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='英文名')
    department_id: Mapped[Optional[int]] = mapped_column(Integer, comment='所属科室ID')
    hire_date: Mapped[Optional[date]] = mapped_column(Date, comment='入职日期')
    leave_date: Mapped[Optional[date]] = mapped_column(Date, comment='离职日期')
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment='软删除时间')

    department: Mapped[Optional['Departments']] = relationship('Departments', back_populates='employees')
    computers: Mapped[list['Computers']] = relationship('Computers', back_populates='employee')
    monitors: Mapped[list['Monitors']] = relationship('Monitors', back_populates='employee')


class Computers(Base):
    __tablename__ = 'computers'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL', name='computers_ibfk_1'),
        Index('asset_number', 'asset_number', unique=True),
        Index('idx_deleted_at', 'deleted_at'),
        Index('idx_employee', 'employee_id'),
        Index('idx_sn', 'sn_code'),
        Index('idx_status', 'status'),
        Index('sn_code', 'sn_code', unique=True)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_number: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='资产编号')
    brand: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='品牌')
    model: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='型号')
    sn_code: Mapped[str] = mapped_column(String(100, 'utf8mb4_unicode_ci'), nullable=False, comment='SN码')
    status: Mapped[ComputersStatus] = mapped_column(Enum(ComputersStatus, values_callable=lambda cls: [member.value for member in cls]), nullable=False, server_default=text("'normal'"), comment='状态')
    warranty_time: Mapped[Optional[date]] = mapped_column(Date, comment='保修截止时间')
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, comment='购买日期')
    price: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(12, 2), comment='价格（元）')
    remark: Mapped[Optional[str]] = mapped_column(Text(collation='utf8mb4_unicode_ci'), comment='备注')
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, comment='当前使用员工ID')
    replace_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment='更换电脑时间')
    scrapped_date: Mapped[Optional[date]] = mapped_column(Date, comment='报废时间')
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment='软删除时间')

    employee: Mapped[Optional['Employees']] = relationship('Employees', back_populates='computers')


class Monitors(Base):
    __tablename__ = 'monitors'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL', name='monitors_ibfk_1'),
        Index('asset_number', 'asset_number', unique=True),
        Index('idx_deleted_at', 'deleted_at'),
        Index('idx_employee', 'employee_id'),
        Index('idx_sn', 'sn_code'),
        Index('idx_status', 'status'),
        Index('sn_code', 'sn_code', unique=True)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_number: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='资产编号')
    brand: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='品牌')
    model: Mapped[str] = mapped_column(String(50, 'utf8mb4_unicode_ci'), nullable=False, comment='型号')
    sn_code: Mapped[str] = mapped_column(String(100, 'utf8mb4_unicode_ci'), nullable=False, comment='SN码')
    status: Mapped[MonitorsStatus] = mapped_column(Enum(MonitorsStatus, values_callable=lambda cls: [member.value for member in cls]), nullable=False, server_default=text("'normal'"), comment='状态')
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, comment='购买日期')
    price: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(12, 2), comment='价格（元）')
    remark: Mapped[Optional[str]] = mapped_column(Text(collation='utf8mb4_unicode_ci'), comment='备注')
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, comment='当前使用员工ID')
    replace_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment='更换显示器时间')
    scrapped_date: Mapped[Optional[date]] = mapped_column(Date, comment='报废时间')
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment='软删除时间')

    employee: Mapped[Optional['Employees']] = relationship('Employees', back_populates='monitors')


# 新增贪吃蛇
class SnakeScores(Base):
    __tablename__ = 'snake_scores'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('admin_users.id'), unique=True, nullable=False)
    high_score = Column(Integer, default=0, nullable=False)
    current_points = Column(Integer, default=100, nullable=False)
    credits = Column(Integer, default=50, nullable=False)
    unlocked_skins = Column(String(1000), default='')  # ← 改这里
    equipped_skin = Column(String(64), default='default')
    max_level = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
