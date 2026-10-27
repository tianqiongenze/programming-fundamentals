# -*- coding: utf-8 -*-
"""设备×周期双层循环巡检 → 双维统计 → 排班建议。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    n_dev = int(cfg.raw.get("n_devices", 3))
    n_cyc = int(cfg.raw.get("n_cycles", 12))
    base = float(cfg.raw.get("base_temp", 70.0))
    drift = float(cfg.raw.get("drift", 2.5))
    devices = ["DEV-%02d" % (i + 1) for i in range(n_dev)]
    stat = core.patrol(devices, n_cyc, base, drift, cfg.warn, cfg.danger, cfg.seed)
    order = core.priority(stat)
    lines = []
    for dev, s in order:
        lines.append("%s  告警 %2d 次（warn %d / danger %d）  轨迹: %s"
                     % (dev, s["warn"] + s["danger"], s["warn"], s["danger"],
                        " ".join("%.0f" % t for t in s["temps"])))
    result = {"n_devices": n_dev, "n_cycles": n_cyc,
              "order": [d for d, _ in order],
              "stat": {d: {"warn": s["warn"], "danger": s["danger"]}
                       for d, s in stat.items()}}
    sections = [("输入口径", ["设备 %d 台 × 周期 %d｜基线 %.0f℃｜漂移 %.1f℃/周期｜"
                "预警 %.0f℃ / 停机 %.0f℃｜种子 %d"
                          % (n_dev, n_cyc, base, drift, cfg.warn, cfg.danger, cfg.seed)]),
                ("巡检优先级", lines),
                ("排班建议", ["优先巡检 %s（告警最集中）" % (order[0][0] if order else "-")]),
                ("结论与建议", ["按告警频次倾斜巡检力量；danger 级当班处置并回填工单"])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
