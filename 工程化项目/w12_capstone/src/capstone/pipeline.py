# -*- coding: utf-8 -*-
"""五段流水线：解析 → 清洗 → [分级 | 词频] → 落盘 → 交付清单。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    raw = [str(x) for x in cfg.items]
    faults = cfg.raw.get("faults") or []
    if isinstance(faults, str):
        faults = [faults]
    # ① 解析 + ② 清洗（隔离）
    good, quarantine = [], []
    for i, line in enumerate(raw, 1):
        row = core.parse_row(line)
        ok, reason = core.clean(row, cfg.warn, cfg.danger)
        (good.append(row) if ok else quarantine.append(
            {"line": i, "raw": line, "reason": reason}))
    if not good:
        raise ValueError("清洗后无有效数据——请检查 config/rules.yaml")
    # ③ 分级 + 词频（互不依赖）
    for r in good:
        r["level"] = core.level(r, cfg.warn, cfg.danger)
    kw = core.keywords(faults, k=int(cfg.topk))
    # ④ 落盘
    os.makedirs(out_dir, exist_ok=True)
    io_utils.write_csv_rows(os.path.join(out_dir, "clean_data.csv"),
                            good, ["name", "temp", "press", "level"])
    io_utils.write_json(os.path.join(out_dir, "result.json"),
                        {"rows": good, "quarantine": quarantine,
                         "keywords": kw,
                         "levels": {lv: sum(1 for r in good if r["level"] == lv)
                                    for lv in ("normal", "warn", "danger")}})
    io_utils.write_json(os.path.join(out_dir, "quarantine.json"), quarantine)
    # ⑤ 交付清单 + 报告
    lv_stat = {}
    for r in good:
        lv_stat[r["level"]] = lv_stat.get(r["level"], 0) + 1
    sections = [("输入口径", ["原始行 %d 条｜预警 %.0f℃ / 停机 %.0f℃｜温度 0~200℃｜压力 0~5MPa"
                % (len(raw), cfg.warn, cfg.danger)]),
                ("流水线产物", ["① clean_data.csv（清洗后数据集）",
                           "② quarantine.json（隔离区 %d 条）" % len(quarantine),
                           "③ result.json（含分级与词频）", "④ report.txt（本报告）"]),
                ("告警分级", ["%s: %d 条" % (k, v) for k, v in sorted(lv_stat.items())]),
                ("高频故障词", ["%s ×%d" % (w, c) for w, c in kw] or ["无故障文本"]),
                ("结论与建议", ["有效数据 %d 条、隔离 %d 条；词频 Top1「%s」需优先排查"
                 % (len(good), len(quarantine), kw[0][0] if kw else "-")])]
    report.save(sections, os.path.join(out_dir, "report.txt"))
    return sections
