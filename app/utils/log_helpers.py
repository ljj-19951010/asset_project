#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
操作日志辅助工具
"""
from typing import Any, Dict, List, Optional


# 字段英文名 → 中文
FIELD_LABELS: Dict[str, str] = {
    'asset_number': '资产编号',
    'brand': '品牌',
    'model': '型号',
    'sn_code': 'SN码',
    'status': '状态',
    'chinese_name': '员工姓名',
    'english_name': '员工英文名',
    'department_name': '科室',
    'purchase_date': '购买时间',
    'warranty_time': '保修时间',
    'price': '价格',
    'replace_time': '更换时间',
    'scrapped_date': '报废时间',
    'remark': '备注',
    'join_date': '入职时间',
    'leave_date': '离职时间',
    'username': '用户名',
    'email': '邮箱',
    'is_superadmin': '超级管理员',
    'password': '密码',
    'avatar': '头像',
}

# 状态英文 → 中文
STATUS_LABELS = {
    'normal': '正常',
    'waiting_repair': '待维修',
    'repairing': '维修中',
    'scrapped': '已报废',
}


def normalize_value(v: Any) -> Optional[str]:
    """归一化值，用于比较（消除枚举/日期格式/数字精度差异）"""
    if v is None or v == '':
        return None
    if hasattr(v, 'value'):
        return str(v.value).strip()
    if hasattr(v, 'strftime'):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            return f'{float(v):.2f}'
        except (TypeError, ValueError):
            return str(v)
    return str(v).strip()


def format_value(v: Any) -> str:
    """格式化值，用于显示"""
    if v is None or v == '':
        return '空'
    if hasattr(v, 'value'):
        v = v.value
    if hasattr(v, 'strftime'):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    s = str(v)
    return STATUS_LABELS.get(s, s)


def build_change_list(old_values: Dict[str, Any], new_values: Dict[str, Any]) -> List[str]:
    """对比新旧值，生成 ['品牌：DELL → Lenovo', ...]"""
    changes = []
    for k, new_v in new_values.items():
        if k.startswith('_') or k not in old_values:
            continue
        old_v = old_values[k]
        if normalize_value(old_v) == normalize_value(new_v):
            continue
        label = FIELD_LABELS.get(k, k)
        changes.append(f'{label}：{format_value(old_v)} → {format_value(new_v)}')
    return changes