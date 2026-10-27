# -*- coding: utf-8 -*-
"""异构设备 → 工厂构建 → 统一 dispatch 调度。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    fleet = [core.from_dict(d) for d in cfg.items]
    if not fleet:
        raise ValueError("config/rules.yaml 的 fleet 为空")
    lines, extra = [], []
    for d in fleet:
        lines.append(d.dispatch(cfg.warn, cfg.danger))       # 多态：同一行代码
        if isinstance(d, core.PumpDevice):
            extra.append(d.set_freq(35.0))
        if isinstance(d, core.FanDevice):
            extra.append(d.delay_stop())
    result = {"n_devices": len(fleet), "dispatched": lines,
              "extras": extra,
              "types": sorted({type(d).__name__ for d in fleet})}
    sections = [("输入口径", ["异构设备 %d 台｜类型: %s" %
                (len(fleet), ", ".join(sorted({type(d).__name__ for d in fleet})))]),
                ("统一调度结果", lines),
                ("子类专属能力", extra),
                ("结论与建议", ["新增设备类型只需加子类并注册工厂，调度层零改动（开闭原则）"])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
