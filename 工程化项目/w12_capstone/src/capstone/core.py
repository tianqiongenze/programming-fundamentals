# -*- coding: utf-8 -*-
"""综合项目核心：解析 / 清洗 / 分级 / 词频（四类纯函数，可独立单测）。"""
import re


def parse_row(line):
    """'注塑机,61.2,0.50' -> dict；字段不足/非数值返回 None。"""
    a = [x.strip() for x in str(line).split(",")]
    if len(a) != 3:
        return None
    try:
        return {"name": a[0], "temp": float(a[1]), "press": float(a[2])}
    except ValueError:
        return None


def clean(row, warn, danger):
    """清洗校验：返回 (ok, reason)。范围: temp 0~200 / press 0~5。"""
    if row is None:
        return False, "解析失败"
    if row["temp"] < 0 or row["press"] < 0:
        return False, "负值"
    if not (0.0 <= row["temp"] <= 200.0):
        return False, "温度越界"
    if not (0.0 <= row["press"] <= 5.0):
        return False, "压力越界"
    return True, ""


def level(row, warn, danger):
    if row["temp"] >= danger or row["press"] >= 0.65:
        return "danger"
    if row["temp"] >= warn or row["press"] >= 0.55:
        return "warn"
    return "normal"


def keywords(faults, k=5, stop=None):
    stop = stop or {"设备", "系统", "发生", "进行", "状态"}
    toks = []
    for f in faults:
        for seg in re.findall(r"[\u4e00-\u9fff]+", str(f)):
            if len(seg) >= 2:
                toks += [seg[i:i + 2] for i in range(len(seg) - 1)] + [seg]
    toks = [t for t in toks if t not in stop]
    from collections import Counter
    return Counter(toks).most_common(k)


#: 三维度清洗口径（复用 W08）：报告与隔离区都按这三类归因
DIMENSIONS = ("完整性", "有效性", "范围")
TEMP_RANGE = (0.0, 200.0)
PRESS_RANGE = (0.0, 5.0)


def as_row(rec):
    """任意来源的一条记录 → 统一行结构；返回 (row, 维度, 原因)。

    row 为 None 表示这条记录进隔离区。三类失败各有归属，答辩时
    "坏数据怎么处理"才答得出具体维度，而不是只说一句"做了清洗"。
    """
    if isinstance(rec, dict):
        row = dict(rec)
    else:
        row = parse_row(rec)
        if row is None:
            txt = str(rec)
            miss = (not txt.strip()) or any(
                not x.strip() for x in txt.split(","))
            dim = "完整性" if miss else "有效性"
            return None, dim, ("字段缺失或空值" if miss
                               else "字段数/类型不合法")
    for key in ("name", "temp", "press"):
        if row.get(key) in (None, ""):
            return None, "完整性", "缺字段 %s" % key
    try:
        row["temp"] = float(row["temp"])
        row["press"] = float(row["press"])
    except (TypeError, ValueError):
        return None, "有效性", "temp/press 非数值"
    if not row["name"]:
        return None, "完整性", "设备名为空"
    return row, "", ""


def check_range(row):
    """物理量程校验（范围维度）：负值/越界返回原因。"""
    if row["temp"] < 0 or row["press"] < 0:
        return False, "负值"
    if not (TEMP_RANGE[0] <= row["temp"] <= TEMP_RANGE[1]):
        return False, "温度越界"
    if not (PRESS_RANGE[0] <= row["press"] <= PRESS_RANGE[1]):
        return False, "压力越界"
    return True, ""


def triage(records, warn, danger):
    """三维度清洗 → (有效行, 隔离区, 各维度计数)。隔离不等于丢证据。"""
    good, quarantine, dim_count = [], [], {d: 0 for d in DIMENSIONS}
    for i, rec in enumerate(records, 1):
        row, dim, reason = as_row(rec)
        if row is None:
            dim_count[dim] += 1
            quarantine.append({"line": i, "raw": rec,
                               "dimension": dim, "reason": reason})
            continue
        ok, why = check_range(row)
        if not ok:
            dim_count["范围"] += 1
            quarantine.append({"line": i, "raw": rec,
                               "dimension": "范围", "reason": why})
            continue
        row["level"] = level(row, warn, danger)
        good.append(row)
    return good, quarantine, dim_count
