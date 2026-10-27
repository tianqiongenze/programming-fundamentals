# -*- coding: utf-8 -*-
"""读数序列 → 告警事件流 → 去重 → 统计报告。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    if cfg.warn >= cfg.danger:
        raise ValueError("阈值配置非法：warn(%.1f) 必须小于 danger(%.1f)"
                         % (cfg.warn, cfg.danger))
    pw, pd = float(cfg.raw.get("press_warn", 0.55)), float(cfg.raw.get("press_danger", 0.65))
    win = float(cfg.raw.get("dedup_seconds", 10))
    events = []
    for r in cfg.items:
        events.append({"ts": float(r["ts"]), "temp": float(r["temp"]),
                       "press": float(r["press"]),
                       "level": core.judge(float(r["temp"]), float(r["press"]),
                                           cfg.warn, cfg.danger, pw, pd)})
    out = core.dedup(events, win)
    fired = [e for e in out if not e["suppressed"]]
    lines = ["ts=%6.1f  temp=%5.1f  press=%.2f → %-9s %s"
             % (e["ts"], e["temp"], e["press"], e["level"].upper(),
                "（已去重抑制）" if e["suppressed"] else "") for e in out]
    stat = {}
    for e in fired:
        stat[e["level"]] = stat.get(e["level"], 0) + 1
    result = {"n_readings": len(out), "fired": len(fired),
              "suppressed": len(out) - len(fired), "by_level": stat, "events": out}
    sections = [("输入口径", ["读数 %d 条｜温度预警 %.0f℃ / 停机 %.0f℃｜去重窗口 %.0fs"
                % (len(out), cfg.warn, cfg.danger, win)]),
                ("告警流水", lines),
                ("告警分布", ["%s: %d 次（已去重）" % (k, v) for k, v in sorted(stat.items())] or ["无告警"]),
                ("结论与建议", ["紧急级告警必须立即停机并回填工单；"
                           "去重抑制 %d 条属预期行为（防刷屏）"
                           % (len(out) - len(fired))])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
