# -*- coding: utf-8 -*-
"""流水线：加载设备清单 → 换算评估 → 渲染台账卡 → 落盘报告。"""
import os

from . import core, io_utils, report


def load_devices(cfg):
    return [core.Device(code=str(d["code"]), name=str(d["name"]), temp=float(d["temp"]),
                        press_kpa=float(d["press_kpa"]), rpm=int(d["rpm"]),
                        status=str(d.get("status", "running")))
            for d in cfg.items]


def run(cfg, out_dir):
    devs = load_devices(cfg)
    if not devs:
        raise ValueError("config/rules.yaml 中 devices 为空——请至少配置 1 台设备")
    lines, lv_stat = [], {}
    for d in devs:
        lines.extend(core.card(d, cfg))
        lines.append("")
        lv_stat[core.level_of(d.temp, cfg.warn, cfg.danger)] = \
            lv_stat.get(core.level_of(d.temp, cfg.warn, cfg.danger), 0) + 1
    result = {"n_devices": len(devs), "levels": lv_stat,
              "devices": [{"code": d.code, "temp_c": d.temp,
                           "temp_f": round(core.c_to_f(d.temp), 2),
                           "level": core.level_of(d.temp, cfg.warn, cfg.danger)} for d in devs]}
    sections = [("输入口径", ["设备 %d 台｜预警线 %.1f℃｜停机线 %.1f℃｜单位 %s"
                % (len(devs), cfg.warn, cfg.danger, cfg.unit)]),
                ("设备台账卡", lines),
                ("告警分布", ["%s: %d 台" % (k, v) for k, v in sorted(lv_stat.items())]),
                ("结论与建议", ["共 %d 台设备；danger 级需当班处置并回填工单"
                 % len(devs)])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
