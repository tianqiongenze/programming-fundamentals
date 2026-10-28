# -*- coding: utf-8 -*-
"""设备×周期双层循环巡检 → check_device 判级 → alarm 输出 → 统计报告 + while 版
→ 四档实测判定 → 落盘。

档位判定（tiers.verdict）吃的全部是实测值：measure.collect 的 AST 函数清点、
循环实跑样本数、统计逐台复算、while 有界实测、W02→W03 对照数字，加
stylecheck 实测规范率——报告里的"达成档位"是算出来的，不是承诺出来的。
"""
import os

from . import core, io_utils, measure, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
# A 档交付物：同仓函数化收益对比文档（路径写在 config/rules.yaml，可被 --set 覆盖）
DEFAULT_A_TIER_DOC = "docs/09-函数化收益对比-W02到W03.md"


def build(cfg, out_dir):
    """跑完整巡检流水线，返回 (sections, result)；result 含实测值与档位判定。"""
    devices = cfg.seq("devices")                 # 工单任务1：列表 + 字典
    if len(devices) < 3:
        raise ValueError("工单 W03 任务1 要求 ≥3 台设备，当前 %d 台" % len(devices))
    doc = str(cfg.get("a_tier_doc", DEFAULT_A_TIER_DOC))
    n_cycles = int(cfg.num("n_cycles", 10))
    stat = core.patrol(devices, n_cycles, seed=int(cfg.seed))
    wstat = core.patrol_while(devices, n_cycles, seed=int(cfg.seed))
    order = core.priority(stat)

    lines = []
    for dev, s in order:
        lines.append("%s  告警 %2d 次（警告 %d / 停机 %d / 紧急 %d）  峰值 %.1f℃  轨迹: %s"
                     % (dev, s["alarms"], s["warn"], s["danger"], s["emergency"],
                        s["peak"], " ".join("%.0f" % t for t in s["temps"])))
        for cycle, lv in enumerate(s["levels"][:4], 1):
            lines.append("    └ %s" % core.alarm(
                lv, "%s 第%d周期 温度 %.1f℃" % (dev, cycle, s["temps"][cycle - 1])))
    while_lines = ["  %-9s while 实跑 %2d 轮（约定 %d 轮）｜退出原因: %s"
                   % (dev, s["cycles"], n_cycles, s["exit_reason"])
                   for dev, s in wstat.items()]
    total = {k: sum(s[k] for s in stat.values())
             for k in ("warn", "danger", "emergency", "alarms")}
    m = measure.collect(cfg, ROOT, stat, wstat, n_cycles)
    result = {"n_devices": len(devices), "n_cycles": n_cycles,
              "seed": int(cfg.seed),
              "order": [d for d, _ in order],
              "functions": ["check_device(d)", "alarm(level, msg)", "patrol()",
                            "patrol_while()", "count_alarms()", "summarize()"],
              "totals": total,
              "measured": m,
              "stat": {d: {k: s[k] for k in ("warn", "danger", "emergency",
                                             "alarms", "cycles")}
                       for d, s in stat.items()},
              "while_exits": {d: s["exit_reason"] for d, s in wstat.items()},
              "a_tier_doc": doc}
    head = ["设备 %d 台 × 周期 %d（工单要求 10 周期）" % (len(devices), n_cycles),
            "预警 %.0f℃ / 停机 %.0f℃｜种子 %d（结果可复现）" % (cfg.warn, cfg.danger, cfg.seed)]
    summary = ["警告 %d 次｜停机 %d 次｜紧急 %d 次｜告警合计 %d 次"
               % (total["warn"], total["danger"], total["emergency"], total["alarms"])]
    roster = ["优先巡检 %s（告警最集中）" % (order[0][0] if order else "-"),
              "函数化后的 W03 与 W02 的取舍对比见 %s" % doc]
    verdict = ["双层循环 + 两个具名函数（check_device / alarm）跑通 %d 台 × %d 周期"
               % (len(devices), n_cycles),
               "while 版三重退出条件，实测无死循环"]
    sections = [
        ("输入口径", head),
        ("巡检优先级与告警汇总（工单任务4）", lines),
        ("while 版本与退出条件（工单任务5 选做）", while_lines),
        ("总计", summary),
        ("排班建议", roster)]
    style = stylecheck.augment(sections, result, ROOT,
                               float(cfg.get("style_min", 85.0)))
    m["style_rate"] = style["rate"]
    v = tiers.verdict(tiers.gates(cfg), m)
    result["tiers"] = v
    sections.append(("验收档位判定（实测）", tiers.render_lines(v)))
    sections.append(("结论与建议", verdict + [
        "实测达成档位: %s；人工答辩项 %d 条（教师答辩时确认）"
        % (v["claimed"], len(v["manual"]))]))
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir):
    """兼容旧入口：返回报告段（cli / tests 用）。"""
    sections, _ = build(cfg, out_dir)
    return sections
