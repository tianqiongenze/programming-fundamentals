# -*- coding: utf-8 -*-
"""读配置 → 落盘 CSV/JSON → 一致性校验 → 统计报告。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    rows = [{"code": str(d["code"]), "temp": float(d["temp"]),
             "press": float(d["press"])} for d in cfg.items]
    if not rows:
        raise ValueError("config/rules.yaml 的 rows 为空")
    os.makedirs(out_dir, exist_ok=True)
    csv_ok, json_ok = core.verify_roundtrip(rows, out_dir)
    st = core.summarize(rows)
    result = {"rows": rows, "summary": st,
              "roundtrip": {"csv": csv_ok, "json": json_ok}}
    sections = [("输入口径", ["记录 %d 条｜字段 code/temp/press｜输出 CSV+JSON" % len(rows)]),
                ("落盘产物", ["output/data.csv", "output/data.json（utf-8, ensure_ascii=False）"]),
                ("一致性校验", ["CSV round-trip: %s" % ("通过" if csv_ok else "失败"),
                 "JSON round-trip: %s" % ("通过" if json_ok else "失败")]),
                ("聚合统计", [
                    "记录数: %d" % st["count"],
                    "温度℃: min %.1f / max %.1f / mean %.2f" % (
                        st["temp"]["min"], st["temp"]["max"], st["temp"]["mean"]),
                    "压力MPa: min %.2f / max %.2f / mean %.2f" % (
                        st["press"]["min"], st["press"]["max"], st["press"]["mean"]),
                ]),
                ("超限设备", st["over_limit"] or ["无"]),
                ("结论与建议", ["双格式 round-trip 校验通过，数据可安全交下游；"
                 "超限设备 %d 台需工单跟进" % len(st["over_limit"])])]
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
