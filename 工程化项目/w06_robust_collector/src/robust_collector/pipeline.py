# -*- coding: utf-8 -*-
"""逐行采集 → 校验 → 隔离 → 统计报告。"""
import logging
import os

from . import core, io_utils, report

log = logging.getLogger(__name__)


def run(cfg, out_dir):
    lines = [str(x) for x in cfg.items]
    ok_rows, bad = [], []
    for i, raw in enumerate(lines, 1):
        try:
            temp, press = core.parse_line(raw)
            good, reason = core.validate(temp, press)
            if not good:
                bad.append(core.quarantine_line(i, raw, reason))
                continue
            ok_rows.append({"line": i, "temp": temp, "press": press})
        except core.ParseError as e:
            bad.append(core.quarantine_line(i, raw, str(e)))
    total = len(lines)
    result = {"total": total, "ok": len(ok_rows), "bad": len(bad),
              "success_rate": round(len(ok_rows) / max(total, 1), 4),
              "quarantine": bad, "rows": ok_rows}
    reasons = {}
    for b in bad:
        reasons[b["reason"]] = reasons.get(b["reason"], 0) + 1
    sections = [("输入口径", ["原始行 %d 条｜温度 0~200℃｜压力 0~5.0MPa" % total]),
                ("采集成功", ["成功 %d 条（%.1f%%）" % (len(ok_rows),
                 len(ok_rows) / max(total, 1) * 100)]),
                ("隔离区", ["第%2d行 %-14r 原因: %s" % (b["line"], b["raw"], b["reason"])
                 for b in bad] or ["无坏数据"]),
                ("失败原因分布", ["%s: %d 条" % (k, v) for k, v in sorted(reasons.items())] or ["-"]),
                ("结论与建议", ["坏数据不进结果集；隔离区需人工复核后决定重采或补录"])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
