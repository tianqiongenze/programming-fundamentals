# -*- coding: utf-8 -*-
"""加载设备 → 演示状态机转移 → 输出巡检台账。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    devs = [core.Device(code=str(d["code"]), kind=str(d["kind"]),
                        temp=float(d.get("temp", 0.0))) for d in cfg.items]
    if not devs:
        raise ValueError("config/rules.yaml 的 devices 为空")
    ops, errs = [], []
    for d in devs:
        ops.append(d.start())
    ops.append(devs[0].start()) if False else None     # 占位：真正演示见下方显式用例
    # 显式演示两条业务规则
    try:
        devs[0].start()
        errs.append("未拦住重复启动（规则失效！）")
    except core.AlreadyRunningError as e:
        ops.append("已拦截重复启动: %s" % e)
    try:
        devs[1].stop()
        devs[1].stop()
        errs.append("未拦住重复停机（规则失效！）")
    except core.NotRunningError as e:
        ops.append("已拦截重复停机: %s" % e)
    devs[0].temp = 96.0
    lines = [d.patrol(cfg.warn, cfg.danger) for d in devs]
    result = {"n_devices": len(devs), "ops": ops, "errors": errs,
              "flags": [d.running for d in devs]}
    sections = [("输入口径", ["设备 %d 台｜预警 %.0f℃ / 停机 %.0f℃"
                % (len(devs), cfg.warn, cfg.danger)]),
                ("操作流水", ops),
                ("规则校验", ["拦截面: %s" % (len(errs) == 0 and "全部通过" or "失败")] + errs),
                ("巡检台账", lines)]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
