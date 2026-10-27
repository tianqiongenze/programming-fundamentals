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
