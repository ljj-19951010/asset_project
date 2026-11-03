#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026/8/31 All rights reserved.
"""
Project Name: mdpi_asset,
File Name: enums.py,
IDE: PyCharm,
Day: 2026 - 08 - 31,
Author: Jinjing.Liu
Title:
Description:
    1.
    2.
"""
import enum


class AdminUsersGender(str, enum.Enum):
    MALE = 'male'
    FEMALE = 'female'
    OTHER = 'other'


class ComputersStatus(str, enum.Enum):
    SCRAPPED = 'scrapped'
    NORMAL = 'normal'
    WAITING_REPAIR = 'waiting_repair'
    REPAIRING = 'repairing'


class MonitorsStatus(str, enum.Enum):
    SCRAPPED = 'scrapped'
    NORMAL = 'normal'

