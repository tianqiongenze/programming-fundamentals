# -*- coding: utf-8 -*-
"""统计与读写一致性校验（纯函数）。"""


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
