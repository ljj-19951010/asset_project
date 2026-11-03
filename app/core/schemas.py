#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: schemas.py,
IDE: PyCharm,
Day: 2026 - 08 - 31,
Author: Jinjing.Liu
Title:模型
Description:2026.09.16更新
    1.pydantic模型
    2.电脑和显示器更新用户字段，给前端显示用户状态
"""
from datetime import datetime
from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict

from app.core.models import Computers, Monitors

T = TypeVar('T')


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class TokenData(BaseModel):
    username: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserRegister(BaseModel):
    username: str
    password: str
    chinese_name: str
    english_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_superadmin: Optional[bool] = True
    gender: Optional[str] = '未知'
    age: Optional[int] = None
    join_date: Optional[datetime] = datetime.now()
    avatar: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    chinese_name: str
    english_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_superadmin: Optional[bool] = True
    gender: Optional[str] = None
    age: Optional[int] = None
    join_date: Optional[datetime] = None
    avatar: Optional[str] = None
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    chinese_name:Optional[str] = None
    english_name:Optional[str] = None
    gender:Optional[str] = None
    age:Optional[int] = None
    join_date:Optional[datetime] = None
    avatar:Optional[str] = None
    is_superadmin: Optional[bool] = True


class ComputersOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_number: str
    brand: str
    model: str
    sn_code: str
    status: str
    purchase_date: Optional[datetime] = None
    warranty_time: Optional[datetime] = None
    price: Optional[float | int] = None
    replace_time: Optional[datetime] = None
    scrapped_date: Optional[datetime] = None
    remark: Optional[str] = None

    # 员工相关字段（直接声明）
    chinese_name: Optional[str] = None
    english_name: Optional[str] = None
    department_name: Optional[str] = None
    join_date: Optional[datetime] = None  # 对应 hire_date
    leave_date: Optional[datetime] = None


class ComputersCreate(BaseModel):
    asset_number: str
    brand: str
    model: str
    sn_code: str
    status: str
    employee_id: Optional[int] = None
    purchase_date: Optional[datetime] = None        # 购买时间
    warranty_time: Optional[datetime] = None        # 保修时间
    price: Optional[float | int] = None
    replace_time: Optional[datetime] = None         # 更换时间
    scrapped_date: Optional[datetime] = None        # 报废时间
    remark: Optional[str] = None                  # 备注


class ComputersUpdate(BaseModel):
    asset_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    sn_code: Optional[str] = None
    status: Optional[str] = None
    employee_id: Optional[int] = None
    purchase_date: Optional[datetime] = None
    warranty_time: Optional[datetime] = None
    price: Optional[float | int] = None
    replace_time: Optional[datetime] = None
    scrapped_date: Optional[datetime] = None
    remark: Optional[str] = None

    # 【新增】前端传递的员工相关字段
    chinese_name: Optional[str] = None
    english_name: Optional[str] = None
    department_name: Optional[str] = None
    join_date: Optional[datetime] = None  # 对应 hire_date
    leave_date: Optional[datetime] = None


class MonitorsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_number: str
    brand: str
    model: str
    sn_code: str
    status: str
    purchase_date: Optional[datetime] = None
    price: Optional[float | int] = None
    replace_time: Optional[datetime] = None
    scrapped_date: Optional[datetime] = None
    remark: Optional[str] = None
    # 员工相关字段
    chinese_name:Optional[str] = None
    english_name:Optional[str] = None
    department_name: Optional[str] = None
    join_date: Optional[datetime] = None
    leave_date: Optional[datetime] = None


class MonitorsCreate(BaseModel):
    asset_number: str
    brand: str
    model: str
    sn_code: str
    status: str
    purchase_date: Optional[datetime] = None
    price: Optional[float | int] = None
    replace_time: Optional[datetime] = None
    scrapped_date: Optional[datetime] = None
    remark: Optional[str] = None
    employee_id: Optional[int] = None


class MonitorsUpdate(BaseModel):
    asset_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    sn_code: Optional[str] = None
    status: Optional[str] = None
    purchase_date: Optional[datetime] = None
    price: Optional[float | int] = None
    replace_time: Optional[datetime] = None
    scrapped_date: Optional[datetime] = None
    remark: Optional[str] = None
    employee_id: Optional[int] = None

    # 【新增】前端传递的员工相关字段
    chinese_name: Optional[str] = None
    english_name: Optional[str] = None
    department_name: Optional[str] = None
    join_date: Optional[datetime] = None  # 对应 hire_date
    leave_date: Optional[datetime] = None


class EmployeesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chinese_name: str
    english_name: str
    department_id: int
    hire_date: Optional[datetime] = None
    leave_date: Optional[datetime] = None

    # 科室相关信息
    department_name: Optional[str] = None
    # 资产相关信息
    computers_asset_number: str
    computers_sn: str
    computers_remark: str
    monitors_asset_number: str
    monitors_sn: str
    monitors_remark: str


class EmployeesCreate(BaseModel):
    chinese_name: str
    english_name: str
    department_id: Optional[int] = None
    hire_date: Optional[datetime] = None
    leave_date: Optional[datetime] = None
    # 资产相关信息
    computers_asset_number: str
    computers_sn: Optional[str] = None
    computers_remark: Optional[str] = None
    monitors_asset_number: str
    monitors_sn: Optional[str] = None
    monitors_remark: Optional[str] = None


class EmployeesUpdate(BaseModel):
    chinese_name: Optional[str] = None
    english_name: Optional[str] = None
    department_id: Optional[int] = None
    hire_date: Optional[datetime] = None
    leave_date: Optional[datetime] = None
    # 资产相关
    computers_asset_number: Optional[str] = None
    computers_sn: Optional[str] = None
    computers_remark: Optional[str] = None
    monitors_asset_number: Optional[str] = None
    monitors_sn: Optional[str] = None
    monitors_remark: Optional[str] = None



# 工具函数
def build_computer_out(comp: Computers) -> ComputersOut:
    """将 Computers ORM 对象转换为 ComputersOut"""
    return ComputersOut(
        asset_number=comp.asset_number,
        brand=comp.brand,
        model=comp.model,
        sn_code=comp.sn_code,
        status=comp.status.value if comp.status else None,
        purchase_date=comp.purchase_date,
        warranty_time=comp.warranty_time,
        price=comp.price,
        replace_time=comp.replace_time,
        scrapped_date=comp.scrapped_date,
        remark=comp.remark,
        chinese_name=comp.employee.chinese_name if comp.employee else None,
        english_name=comp.employee.english_name if comp.employee else None,
        department_name=comp.employee.department.name if comp.employee and comp.employee.department else None,
        join_date=comp.employee.hire_date if comp.employee else None,
        leave_date = comp.employee.leave_date if comp.employee else None,  # ← 加这行
    )


def build_monitors_out(mon: Monitors) -> MonitorsOut:
    """
    将orm对象转换成 人类可以读懂的数据
    :param mon:
    :return:
    """
    return MonitorsOut(
        asset_number=mon.asset_number,
        brand=mon.brand,
        model=mon.model,
        sn_code=mon.sn_code,
        status=mon.status.value if mon.status else None,
        purchase_date=mon.purchase_date,
        price=mon.price,
        replace_time=mon.replace_time,
        scrapped_date=mon.scrapped_date,
        remark=mon.remark,
        chinese_name=mon.employee.chinese_name if mon.employee else None,
        english_name=mon.employee.english_name if mon.employee else None,
        department_name=mon.employee.department.name if mon.employee and mon.employee.department else None,
        join_date=mon.employee.hire_date if mon.employee else None,
        leave_date=mon.employee.leave_date if mon.employee else None,  # ← 加这行
    )


# ============================================================
#  员工管理相关 Schema（新增）
# ============================================================

class AssetBrief(BaseModel):
    """员工名下的单个资产简要信息"""
    asset_number: str
    brand: Optional[str] = None
    model: Optional[str] = None
    sn_code: Optional[str] = None
    remark: Optional[str] = None
    replace_time: Optional[datetime] = None


class EmployeeWithAssetsOut(BaseModel):
    """员工 + 名下资产（用于员工资产管理界面）"""
    id: int
    chinese_name: str
    english_name: Optional[str] = None
    department_name: Optional[str] = None
    hire_date: Optional[datetime] = None
    leave_date: Optional[datetime] = None
    computers: List[AssetBrief] = []
    monitors: List[AssetBrief] = []


class AssetSearchOut(BaseModel):
    """资产搜索结果（用于员工登记界面）"""
    asset_type: str                      # 'computer' 或 'monitor'
    asset_number: str
    brand: Optional[str] = None
    model: Optional[str] = None
    sn_code: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    # 当前使用人信息（如果已绑定员工）
    employee_id: Optional[int] = None
    employee_chinese_name: Optional[str] = None
    employee_english_name: Optional[str] = None
    department_name: Optional[str] = None
    hire_date: Optional[datetime] = None
    leave_date: Optional[datetime] = None


class CheckinRequest(BaseModel):
    """入职：给资产绑定员工"""
    asset_type: str                      # 'computer' 或 'monitor'
    asset_number: str
    chinese_name: str
    english_name: Optional[str] = None
    department_name: Optional[str] = None
    hire_date: Optional[datetime] = None
    force: Optional[bool] = False


class CheckoutRequest(BaseModel):
    """离职：员工离职 + 资产解绑 + 备注追加"""
    asset_type: str
    asset_number: str


class ChangeUserRequest(BaseModel):
    """更换使用人"""
    asset_type: str
    asset_number: str
    chinese_name: str
    english_name: Optional[str] = None
    department_name: Optional[str] = None
    force: Optional[bool] = False


class RegisterRequest(BaseModel):
    chinese_name: str
    english_name: Optional[str] = None
    department_name: Optional[str] = None
    hire_date: Optional[datetime] = None
    computer_asset_number: Optional[str] = None
    monitor_asset_number: Optional[str] = None
    # 【新增】接收前端传来的备注
    computer_remark: Optional[str] = None
    monitor_remark: Optional[str] = None
    force: Optional[bool] = False


class CheckoutRequest(BaseModel):
    asset_type: str
    asset_number: str
