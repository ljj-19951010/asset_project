#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/9/2 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: assets.py,
Title:上传下载数据
"""
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Query, Depends, UploadFile, File, HTTPException
from openpyxl import Workbook
from openpyxl.reader.excel import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.database import get_db
from app.core.authen import get_current_user
from app.core.models import AdminUsers, Employees, Departments, Monitors
from app.core.models import Computers
from app.logs.operation_logs import create_operation_logs
from app.logs.loggers import logger
from app.utils.get_date import parse_date, parse_datetime
from app.utils.get_employee import get_or_create_employee
from app.core.enums import ComputersStatus, MonitorsStatus

router = APIRouter()


@router.get("/export", summary='导出')
async def export_assets(
        request: Request,
        asset_type: Optional[str] = Query(None, description='computer / monitor / scrapped / normal，不传则全部导出'),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    wb = Workbook()
    wb.remove(wb.active)
    header_font = Font(bold=True, color='FFFFFF')
    header_Fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')

    def create_sheet(title, columns):
        ws = wb.create_sheet(title)
        ws.append(columns)
        for col_idx, _ in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_Fill
            cell.alignment = header_alignment
        return ws

    # ============================================================
    #  准备查询条件
    # ============================================================
    if asset_type == 'scrapped':
        c_filter = [Computers.status == ComputersStatus.SCRAPPED]
        m_filter = [Monitors.status == MonitorsStatus.SCRAPPED]
    elif asset_type == 'normal':
        c_filter = [Computers.status == ComputersStatus.NORMAL, Computers.deleted_at.is_(None), Computers.scrapped_date.is_(None)]
        m_filter = [Monitors.status == MonitorsStatus.NORMAL, Monitors.deleted_at.is_(None), Monitors.scrapped_date.is_(None)]
    else:
        c_filter = []
        m_filter = []

    # ============================================================
    #  电脑表
    # ============================================================
    if asset_type in (None, 'computer', 'scrapped', 'normal'):
        computer_columns = [
            'remark','asset_number','brand','model','sn_code','chinese_name',
            'english_name','department','hire_date','leave_date','replace_time',
            'status','purchase_date','warranty_time','price','scrapped_date'
        ]
        sheet_title = 'computer_scrapped' if asset_type == 'scrapped' else 'computer'
        ws_computer = create_sheet(sheet_title, computer_columns)
        stmt = (
            select(Computers, Employees, Departments)
            .outerjoin(Employees, Computers.employee_id == Employees.id)
            .outerjoin(Departments, Employees.department_id == Departments.id)
        )
        if c_filter:
            stmt = stmt.where(*c_filter)
        result = await db.execute(stmt)
        rows = result.all()
        for row_idx, (computer, emp, dept) in enumerate(rows, start=2):
            ws_computer.cell(row=row_idx, column=1, value=computer.remark or '')
            ws_computer.cell(row=row_idx, column=2, value=computer.asset_number)
            ws_computer.cell(row=row_idx, column=3, value=computer.brand)
            ws_computer.cell(row=row_idx, column=4, value=computer.model)
            ws_computer.cell(row=row_idx, column=5, value=computer.sn_code)
            ws_computer.cell(row=row_idx, column=6, value=emp.chinese_name if emp else "")
            ws_computer.cell(row=row_idx, column=7, value=emp.english_name if emp else "")
            ws_computer.cell(row=row_idx, column=8, value=dept.name if dept else "")
            ws_computer.cell(row=row_idx, column=9, value=emp.hire_date.isoformat() if emp and emp.hire_date else "")
            ws_computer.cell(row=row_idx, column=10, value=emp.leave_date.isoformat() if emp and emp.leave_date else "")
            ws_computer.cell(row=row_idx, column=11, value=computer.replace_time if computer.replace_time else "")
            ws_computer.cell(row=row_idx, column=12, value=computer.status.value if computer.status else '')
            ws_computer.cell(row=row_idx, column=13, value=computer.purchase_date.isoformat() if computer.purchase_date else '')
            ws_computer.cell(row=row_idx, column=14, value=computer.warranty_time.isoformat() if computer.warranty_time else '')
            ws_computer.cell(row=row_idx, column=15, value=float(computer.price) if computer.price else '')
            ws_computer.cell(row=row_idx, column=16, value=computer.scrapped_date.isoformat() if computer.scrapped_date else '')
        for col in ws_computer.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
            ws_computer.column_dimensions[col_letter].width = max_len + 2

    # ============================================================
    #  显示器表
    # ============================================================
    if asset_type in (None, 'monitor', 'scrapped', 'normal'):
        monitor_columns = [
            'remark','asset_number','brand','model','sn_code',
            'chinese_name', 'english_name','department', 'status',
            'hire_date', 'leave_date', 'replace_time', 'purchase_date',
            'scrapped_date', 'price'
        ]
        sheet_title = 'monitor_scrapped' if asset_type == 'scrapped' else 'monitor'
        ws_monitor = create_sheet(sheet_title, monitor_columns)
        stmt = (
            select(Monitors, Employees, Departments)
            .outerjoin(Employees, Monitors.employee_id == Employees.id)
            .outerjoin(Departments, Employees.department_id == Departments.id)
        )
        if m_filter:
            stmt = stmt.where(*m_filter)
        result = await db.execute(stmt)
        rows = result.all()
        for row_idx, (monitor, emp, dept) in enumerate(rows, start=2):
            ws_monitor.cell(row=row_idx, column=1, value=monitor.remark or '')
            ws_monitor.cell(row=row_idx, column=2, value=monitor.asset_number)
            ws_monitor.cell(row=row_idx, column=3, value=monitor.brand)
            ws_monitor.cell(row=row_idx, column=4, value=monitor.model)
            ws_monitor.cell(row=row_idx, column=5, value=monitor.sn_code)
            ws_monitor.cell(row=row_idx, column=6, value=emp.chinese_name if emp else "")
            ws_monitor.cell(row=row_idx, column=7, value=emp.english_name if emp else "")
            ws_monitor.cell(row=row_idx, column=8, value=dept.name if dept else "")
            ws_monitor.cell(row=row_idx, column=9, value=monitor.status.value if monitor.status else '')
            ws_monitor.cell(row=row_idx, column=10, value=emp.hire_date.isoformat() if emp and emp.hire_date else "")
            ws_monitor.cell(row=row_idx, column=11, value=emp.leave_date.isoformat() if emp and emp.leave_date else "")
            ws_monitor.cell(row=row_idx, column=12, value=monitor.replace_time if monitor.replace_time else "")
            ws_monitor.cell(row=row_idx, column=13, value=monitor.purchase_date.isoformat() if monitor.purchase_date else '')
            ws_monitor.cell(row=row_idx, column=14, value=monitor.scrapped_date.isoformat() if monitor.scrapped_date else '')
            ws_monitor.cell(row=row_idx, column=15, value=float(monitor.price) if monitor.price else '')
        for col in ws_monitor.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
            ws_monitor.column_dimensions[col_letter].width = max_len + 2

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # 日志描述
    type_desc_map = {
        None: '所有资产',
        'computer': '电脑数据',
        'monitor': '显示器数据',
        'scrapped': '报废资产数据',
        'normal': '正常资产数据',
    }
    type_desc = type_desc_map.get(asset_type, asset_type)

    await create_operation_logs(
        db=db,
        request=request,
        user_id=current_user.id,
        action='export_assets',
        target_table='assets',
        target_id=0,
        details={'message': f'用户 {current_user.username} 导出了{type_desc}'},
    )
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": f"attachment; filename=assets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"}
    )


@router.post('/import', summary='导入')
async def import_assets(
        request: Request,
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, '仅支持导入.xlsx或.xls格式文件!')
    try:
        contents = await file.read()
        wb = load_workbook(io.BytesIO(contents))
    except Exception as e:
        logger.warning('日志:导入数据失败，文件无法解析!')
        raise HTTPException(400, f'文件解析失败:{e}')

    total_rows = 0
    success_count = 0
    error_rows = []
    inserted_asset_numbers = set()
    duplicate_asset_numbers = []

    def get_column_index(ws, header_name):
        for idx, cell in enumerate(ws[1], 1):
            if cell.value and cell.value.strip() == header_name:
                return idx
        return None

    status_map = {
        "normal": "normal", "正常": "normal", "正常使用": "normal",
        "scrapped": "scrapped", "已报废": "scrapped", "报废": "scrapped",
        "waiting_repair": "waiting_repair", "等待维修": "waiting_repair",
        "repairing": "repairing", "维修中": "repairing",
        "nromal": "normal"
    }

    # ---------- 电脑 ----------
    if 'computer' in wb.sheetnames:
        ws = wb['computer']
        headers = [cell.value for cell in ws[1]]
        required = ['asset_number', 'brand', 'model', 'sn_code', 'chinese_name', 'status']
        missing = [col for col in required if col not in headers]
        if missing:
            raise HTTPException(400, f'电脑表缺少必须列:{",".join(missing)}')

        col_remark = get_column_index(ws, 'remark')
        col_asset_number = get_column_index(ws, 'asset_number')
        col_brand = get_column_index(ws, 'brand')
        col_model = get_column_index(ws, 'model')
        col_sn_code = get_column_index(ws, 'sn_code')
        col_emp_name = get_column_index(ws, 'chinese_name')
        col_replace_time = get_column_index(ws, 'replace_time')
        col_status = get_column_index(ws, 'status')
        col_purchase_date = get_column_index(ws, 'purchase_date')
        col_warranty_time = get_column_index(ws, 'warranty_time')
        col_price = get_column_index(ws, 'price')
        col_scrapped_date = get_column_index(ws, 'scrapped_date')
        col_emp_english_name = get_column_index(ws, 'english_name')
        col_dept = get_column_index(ws, 'department')
        col_hire_date = get_column_index(ws, 'hire_date')
        col_leave_date = get_column_index(ws, 'leave_date')

        for row_idx in range(2, ws.max_row + 1):
            total_rows += 1
            try:
                asset_number = ws.cell(row=row_idx, column=col_asset_number).value
                if not asset_number:
                    error_rows.append(f'第{row_idx}行: 资产编号为空')
                    continue
                asset_number_str = str(asset_number).strip()
                if asset_number_str in inserted_asset_numbers:
                    duplicate_asset_numbers.append(
                        f'第{row_idx}行: 资产编号 {asset_number_str} 在本次导入中重复，已覆盖')
                inserted_asset_numbers.add(asset_number_str)

                stmt = select(Computers).where(Computers.asset_number == asset_number)
                computer = (await db.execute(stmt)).scalar_one_or_none()
                if computer:
                    computer.deleted_at = None
                else:
                    computer = Computers(asset_number=asset_number)

                computer.brand = ws.cell(row=row_idx, column=col_brand).value or ''
                computer.model = ws.cell(row=row_idx, column=col_model).value or ''
                computer.sn_code = ws.cell(row=row_idx, column=col_sn_code).value or ''

                status_str = ws.cell(row=row_idx, column=col_status).value
                scrapped_date_val = ws.cell(row=row_idx, column=col_scrapped_date).value

                if scrapped_date_val:
                    computer.scrapped_date = parse_date(scrapped_date_val)
                    computer.status = 'scrapped'
                else:
                    computer.scrapped_date = None
                    if status_str:
                        normalized = status_map.get(str(status_str).strip().lower())
                        if normalized:
                            computer.status = normalized
                        else:
                            error_rows.append(f'第{row_idx}行 (资产编号: {asset_number}): 状态值 "{status_str}" 无效，使用默认 normal')
                            computer.status = 'normal'
                    else:
                        computer.status = 'normal'

                if col_warranty_time:
                    computer.warranty_time = parse_date(ws.cell(row=row_idx, column=col_warranty_time).value)
                if col_purchase_date:
                    computer.purchase_date = parse_date(ws.cell(row=row_idx, column=col_purchase_date).value)
                if col_replace_time:
                    computer.replace_time = parse_datetime(ws.cell(row=row_idx, column=col_replace_time).value)
                if col_price:
                    price_val = ws.cell(row=row_idx, column=col_price).value
                    computer.price = float(price_val) if price_val else None
                if col_remark:
                    computer.remark = ws.cell(row=row_idx, column=col_remark).value or ''

                chinese_name = ws.cell(row=row_idx, column=col_emp_name).value
                if chinese_name:
                    chinese_name = str(chinese_name).strip()
                    english_name = ws.cell(row=row_idx, column=col_emp_english_name).value
                    english_name = str(english_name).strip() if english_name else None
                    dept_name = ws.cell(row=row_idx, column=col_dept).value
                    dept_name = str(dept_name).strip() if dept_name else None
                    hire_date = parse_date(ws.cell(row=row_idx, column=col_hire_date).value)
                    leave_date = parse_date(ws.cell(row=row_idx, column=col_leave_date).value)

                    employee = await get_or_create_employee(
                        db=db,
                        chinese_name=chinese_name,
                        english_name=english_name,
                        department_name=dept_name,
                        hire_date=hire_date,
                        leave_date=leave_date
                    )
                    computer.employee_id = employee.id if employee else None
                else:
                    computer.employee_id = None

                db.add(computer)
                success_count += 1
            except Exception as e:
                error_rows.append(f'第{row_idx}行 (资产编号: {asset_number if "asset_number" in locals() else "未知"}): {str(e)}')

    # ---------- 显示器 ----------
    if 'monitor' in wb.sheetnames:
        ws = wb['monitor']
        headers = [cell.value for cell in ws[1]]
        required = ['asset_number', 'brand', 'model', 'sn_code', 'status', 'chinese_name']
        missing = [col for col in required if col not in headers]
        if missing:
            raise HTTPException(400, f'显示器表缺少必须列:{",".join(missing)}')

        col_remark = get_column_index(ws, 'remark')
        col_asset_number = get_column_index(ws, 'asset_number')
        col_brand = get_column_index(ws, 'brand')
        col_model = get_column_index(ws, 'model')
        col_sn_code = get_column_index(ws, 'sn_code')
        col_status = get_column_index(ws, 'status')
        col_emp_name = get_column_index(ws, 'chinese_name')
        col_english_name = get_column_index(ws, 'english_name')
        col_dept = get_column_index(ws, 'department')
        col_hire_date = get_column_index(ws, 'hire_date')
        col_leave_date = get_column_index(ws, 'leave_date')
        col_replace_time = get_column_index(ws, 'replace_time')
        col_purchase_date = get_column_index(ws, 'purchase_date')
        col_price = get_column_index(ws, 'price')
        col_scrapped_date = get_column_index(ws, 'scrapped_date')

        for row_idx in range(2, ws.max_row + 1):
            total_rows += 1
            try:
                asset_number = ws.cell(row=row_idx, column=col_asset_number).value
                if not asset_number:
                    error_rows.append(f'第{row_idx}行: 资产编号为空')
                    continue
                asset_number_str = str(asset_number).strip()
                if asset_number_str in inserted_asset_numbers:
                    duplicate_asset_numbers.append(
                        f'第{row_idx}行: 资产编号 {asset_number_str} 在本次导入中重复，已覆盖')
                inserted_asset_numbers.add(asset_number_str)

                stmt = select(Monitors).where(Monitors.asset_number == asset_number)
                monitor = (await db.execute(stmt)).scalar_one_or_none()
                if monitor:
                    monitor.deleted_at = None
                else:
                    monitor = Monitors(asset_number=asset_number)

                monitor.brand = ws.cell(row=row_idx, column=col_brand).value or ''
                monitor.model = ws.cell(row=row_idx, column=col_model).value or ''
                monitor.sn_code = ws.cell(row=row_idx, column=col_sn_code).value or ''

                status_str = ws.cell(row=row_idx, column=col_status).value
                scrapped_date_val = ws.cell(row=row_idx, column=col_scrapped_date).value

                if scrapped_date_val:
                    monitor.scrapped_date = parse_date(scrapped_date_val)
                    monitor.status = 'scrapped'
                else:
                    monitor.scrapped_date = None
                    if status_str:
                        normalized = status_map.get(str(status_str).strip().lower())
                        if normalized:
                            monitor.status = normalized
                        else:
                            error_rows.append(f'第{row_idx}行 (资产编号: {asset_number}): 状态值 "{status_str}" 无效，使用默认 normal')
                            monitor.status = 'normal'
                    else:
                        monitor.status = 'normal'

                if col_purchase_date:
                    monitor.purchase_date = parse_date(ws.cell(row=row_idx, column=col_purchase_date).value)
                if col_replace_time:
                    monitor.replace_time = parse_datetime(ws.cell(row=row_idx, column=col_replace_time).value)
                if col_price:
                    price_val = ws.cell(row=row_idx, column=col_price).value
                    monitor.price = float(price_val) if price_val else None
                if col_remark:
                    monitor.remark = ws.cell(row=row_idx, column=col_remark).value or ''

                chinese_name = ws.cell(row=row_idx, column=col_emp_name).value
                if chinese_name:
                    chinese_name = str(chinese_name).strip()
                    english_name = ws.cell(row=row_idx, column=col_english_name).value
                    english_name = str(english_name).strip() if english_name else None
                    dept_name = ws.cell(row=row_idx, column=col_dept).value
                    dept_name = str(dept_name).strip() if dept_name else None
                    hire_date = parse_date(ws.cell(row=row_idx, column=col_hire_date).value)
                    leave_date = parse_date(ws.cell(row=row_idx, column=col_leave_date).value)

                    employee = await get_or_create_employee(
                        db=db,
                        chinese_name=chinese_name,
                        english_name=english_name,
                        department_name=dept_name,
                        hire_date=hire_date,
                        leave_date=leave_date
                    )
                    monitor.employee_id = employee.id if employee else None
                else:
                    monitor.employee_id = None

                db.add(monitor)
                success_count += 1
            except Exception as e:
                error_rows.append(f'第{row_idx}行 (资产编号: {asset_number if "asset_number" in locals() else "未知"}): {str(e)}')

    await db.commit()

    # 记录日志（详细版）
    await create_operation_logs(
        db=db,
        request=request,
        user_id=current_user.id,
        action='import_assets',
        target_table='assets',
        target_id=0,
        details={
            'message': f'导入了 {success_count} 条数据（共 {total_rows} 行，错误 {len(error_rows)} 行）',
            'total_rows': total_rows,
            'success_count': success_count,
            'error_count': len(error_rows)
        }
    )
    logger.info(f'日志:用户{current_user.username}导入资产成功{success_count}条，失败{len(error_rows)}条')
    return {
        'total_rows': total_rows,
        'success_count': success_count,
        'unique_count': len(inserted_asset_numbers),
        'duplicate_count': len(duplicate_asset_numbers),
        'duplicate_details': duplicate_asset_numbers[:30],
        'error_rows': error_rows[:50],
        'error_count': len(error_rows)
    }


@router.get('/template', summary='下载导入模板')
async def download_template(
        request: Request,
        asset_type: Optional[str] = Query(None, description='computer或monitor，默认都生成'),
        db: AsyncSession = Depends(get_db),
        current_user: AdminUsers = Depends(get_current_user)
):
    wb = Workbook()
    wb.remove(wb.active)
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')

    def create_template_sheet(title, columns, sample_data):
        ws = wb.create_sheet(title)
        ws.append(columns)
        for col_idx, _ in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        if sample_data:
            ws.append(sample_data)
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
            ws.column_dimensions[col_letter].width = max_len + 2
        return ws

    if asset_type is None or asset_type == 'computer':
        computer_columns = [
            'remark', 'asset_number', 'brand', 'model', 'sn_code', 'chinese_name',
            'english_name', 'department', 'hire_date', 'leave_date', 'replace_time',
            'status', 'purchase_date', 'warranty_time', 'price', 'scrapped_date'
        ]
        computer_sample = [
            '示例备注', '资产编号', '品牌', '型号', 'SN码', '中文名',
            '英文名', '科室', '入职时间', '离职时间(可空)', '更换电脑时间(可空)',
            '状态:normal(正常),scrapped(已报废),repairing(正在维修)', '电脑购买时间', '保修时间', '单价', '报废时间(可空)'
        ]
        create_template_sheet('computer', computer_columns, computer_sample)

    if asset_type is None or asset_type == 'monitor':
        monitor_columns = [
            'remark', 'asset_number', 'brand', 'model', 'sn_code',
            'chinese_name', 'english_name', 'department', 'status',
            'hire_date', 'leave_date', 'replace_time', 'purchase_date',
            'scrapped_date', 'price'
        ]
        monitor_sample = [
            '示例备注', '资产编号', '品牌', '型号', 'SN码', '中文名',
            '英文名', '科室', '状态:normal(正常),scrapped(报废),repairing(正在维修)', '入职时间', '离职时间',
            '更换显示器时间', '显示器购买时间', '报废时间(可空)', '单价'
        ]
        create_template_sheet('monitor', monitor_columns, monitor_sample)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # 记录日志
    type_desc = '所有' if not asset_type else asset_type
    await create_operation_logs(
        db=db,
        request=request,
        user_id=current_user.id,
        action='download_template',
        target_table='assets',
        target_id=0,
        details={'message': f'下载了{type_desc}导入模板'}
    )
    logger.info(f'日志:用户{current_user.username}下载了模板')
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": f"attachment; filename=assets_template_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )