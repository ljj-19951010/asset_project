#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/9/2 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: get_date.py,
IDE: PyCharm,
Day: 2026 - 09 - 02,
Author: Jinjing.Liu
Title:
Description:
    1.解析日期小工具
    2.
"""
from datetime import datetime, date, timedelta
from typing import Union, Optional


def parse_date(value: Union[str, int, float, datetime, None]) -> Optional[date]:
    """
    解析 Excel 中的日期，支持：
    - datetime 对象
    - Excel 数字序列号（如 45340）
    - 字符串：'YYYY-MM-DD'、'YYYY/MM/DD'、'YYYY.MM.DD' 及其带时间形式
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):  # 已经是 date 对象
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime(1899, 12, 30) + timedelta(days=int(value)).date()
        except:
            return None
    if isinstance(value, str):
        value = value.strip()
        # 支持多种日期格式，包括点分隔
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
                    '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y.%m.%d %H:%M',
                    '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None

def parse_datetime(value: Union[str, int, float, datetime, None]) -> Optional[datetime]:
    """解析日期时间（支持 Excel 数字序列号、点分隔日期等）"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime(1899, 12, 30) + timedelta(days=float(value))
        except:
            return None
    if isinstance(value, str):
        value = value.strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S',
                    '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y.%m.%d %H:%M'):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


# 添加日志时 识别错时间类型的格式
def serialize_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    return obj