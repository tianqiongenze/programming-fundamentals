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
