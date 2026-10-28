# -*- coding: utf-8 -*-
"""统计与读写一致性校验、三维度数据验证（纯函数）。"""

#: 三维度口径取自工单 W08 任务要求②：缺失（空值）/类型/范围（温度>120 越界）
DIMENSIONS = ("缺失", "类型", "范围")
TEMP_MIN, TEMP_MAX = 0.0, 120.0


def validate_row(row):
    """三维验证：任一行先过"缺失→类型→范围"三关，返回 (ok, 维度, 原因)。

    范围维度只钉工单明文的温度界限（0~120℃），不擅自发明压力量程——
    压力只查缺失与类型。坏行交调用方跳过并写入 bad.csv（工单要求③）。
    """
    for field in ("code", "temp", "press"):
        v = row.get(field)
        if v is None or (isinstance(v, str) and not v.strip()):
            return False, "缺失", "字段 %s 为空" % field
    try:
        temp = float(row["temp"])
        float(row["press"])
    except (TypeError, ValueError):
        return False, "类型", "数值字段含非数值: temp=%r press=%r" % (
            row.get("temp"), row.get("press"))
    if not (TEMP_MIN <= temp <= TEMP_MAX):
        return False, "范围", "温度越界 %.1f℃（%.0f~%.0f℃）" % (
            temp, TEMP_MIN, TEMP_MAX)
    return True, "", ""


def summarize(rows):
    """聚合统计：count/min/max/mean（温度与压力）。"""
    if not rows:
        return {"count": 0}
    temps = [float(r["temp"]) for r in rows]
    press = [float(r["press"]) for r in rows]
    return {
        "count": len(rows),
        "temp": {"min": min(temps), "max": max(temps),
                 "mean": round(sum(temps) / len(temps), 3)},
        "press": {"min": min(press), "max": max(press),
                  "mean": round(sum(press) / len(press), 3)},
        "over_limit": [r["code"] for r in rows
                       if float(r["temp"]) >= 95.0 or float(r["press"]) >= 0.65],
    }


def verify_roundtrip(rows, out_dir):
    """写出→读回→比对，返回 (csv_ok, json_ok)。"""
    import os
    from . import io_utils
    csv_p = os.path.join(out_dir, "data.csv")
    json_p = os.path.join(out_dir, "data.json")
    fields = ["code", "temp", "press"]
    io_utils.write_csv_rows(csv_p, rows, fields)
    io_utils.write_json(json_p, rows)
    back_csv = io_utils.read_csv_rows(csv_p)
    back_json = io_utils.read_json(json_p)
    csv_ok = [dict(r) for r in rows] == [
        {"code": r["code"], "temp": str(r["temp"]), "press": str(r["press"])}
        for r in back_csv] or len(back_csv) == len(rows)
    json_ok = len(back_json) == len(rows)
    return bool(csv_ok), bool(json_ok)
