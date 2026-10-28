# -*- coding: utf-8 -*-
"""健壮采集：解析、校验、隔离（纯函数，无 IO）。"""


class ParseError(ValueError):
    """行格式非法。"""


def parse_line(line):
    """把 "56.2,0.45" 解析为 (temp, press)；非法抛 ParseError。"""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 2:
        raise ParseError("字段数不为2: %r" % line)
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        raise ParseError("非数值: %r" % line)


def parse_row(line):
    """字段级解析：让原生异常如实上抛（采集主循环的异常路径实练）。

    与 parse_line 的分工：parse_line 把错误打包成 ParseError（对外语义统一），
    parse_row 保留原始类型——非数值→ValueError、字段缺失→IndexError——
    pipeline 按类型分诊捕获，"实际捕获到几种异常"因此可实测、可复盘。
    """
    parts = [p.strip() for p in line.split(",")]
    temp = float(parts[0])
    press = float(parts[1])
    return temp, press


def validate(temp, press):
    """三重校验：空值/负值/越界。返回 (ok, reason)。"""
    if temp is None or press is None:
        return False, "空值"
    if temp < 0 or press < 0:
        return False, "负值"
    if not (0.0 <= temp <= 200.0):
        return False, "温度越界"
    if not (0.0 <= press <= 5.0):
        return False, "压力越界"
    return True, ""


def quarantine_line(idx, raw, reason):
    """坏数据隔离区条目（行号+原文+原因）。"""
    return {"line": idx, "raw": raw, "reason": reason}
