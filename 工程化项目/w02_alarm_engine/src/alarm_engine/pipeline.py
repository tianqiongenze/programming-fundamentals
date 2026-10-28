# -*- coding: utf-8 -*-
"""读数序列 → 告警事件流 → 去重 → 边界用例表 → 3 台设备循环 → 四档实测判定。

档位判定（tiers.verdict）吃的全部是实测值：measure.collect 的 AST 计数、
边界五组独立公式复核、三级定向探针、sweep 实跑台数，加 stylecheck 的
实测规范率——报告里的"达成档位"是算出来的，不是承诺出来的。
"""
import os

from . import core, io_utils, measure, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
# 工单任务3 点名的五组温度边界值；rules.yaml 未配置时用这份（可被 --set 覆盖）
TEMP_BOUNDARY = [79.9, 80.0, 94.9, 95.0, 100.0]
PRESS_BOUNDARY = [0.54, 0.55, 0.64, 0.65, 0.80]


def build(cfg, out_dir):
    """跑完整告警流水线，返回 (sections, result)；result 含实测值与档位判定。"""
    if cfg.warn >= cfg.danger:
        raise ValueError("阈值配置非法：warn(%.1f) 必须小于 danger(%.1f)"
                         % (cfg.warn, cfg.danger))
    pw = float(cfg.get("press_warn", 0.55))
    pd = float(cfg.get("press_danger", 0.65))
    plimit = float(cfg.get("press_limit", 0.8))
    win = float(cfg.get("dedup_seconds", 10))
    readings = cfg.seq("readings")
    events = [{"ts": float(r["ts"]), "temp": float(r["temp"]),
               "press": float(r["press"]),
               "level": core.judge(float(r["temp"]), float(r["press"]),
                                   cfg.warn, cfg.danger, pw, pd)} for r in readings]
    out = core.dedup(events, win)
    fired = [e for e in out if not e["suppressed"]]
    lines = ["%s ｜ts=%6.1f temp=%5.1f press=%.2f%s"
             % (core.alarm(e["level"], "读数告警"), e["ts"], e["temp"], e["press"],
                "" if not e["suppressed"] else "  （已去重抑制）") for e in out]
    stat = {}
    for e in fired:
        stat[e["level"]] = stat.get(e["level"], 0) + 1

    # ── C 档：边界五组全覆盖（温度 5 组 + 压力 5 组）──
    tb = [float(x) for x in (cfg.seq("boundary_temps") or TEMP_BOUNDARY)]
    pb = [float(x) for x in (cfg.seq("boundary_press") or PRESS_BOUNDARY)]
    brows = core.boundary_table(tb, pb, cfg)
    boundary_lines = ["  %-6s %-6.2f → %-9s %s"
                      % (r["kind"], r["value"], r["level"].upper(), r["text"])
                      for r in brows]

    # ── B 档：嵌套三级 + A 档：循环 3 台设备 ──
    devices = cfg.seq("devices")
    swept = core.sweep(devices, cfg)
    sweep_lines = ["  %s" % s["text"] for s in swept]
    sweep_stat = {}
    for s in swept:
        sweep_stat[s["level"]] = sweep_stat.get(s["level"], 0) + 1

    m = measure.collect(cfg)
    result = {"n_readings": len(out), "fired": len(fired),
              "suppressed": len(out) - len(fired), "by_level": stat,
              "events": out,
              "boundary_cases": len(brows),
              "boundary_temps": tb, "boundary_press": pb,
              "nested_levels": sorted({s["level"] for s in swept}),
              "n_devices_swept": len(swept), "sweep_by_level": sweep_stat,
              "sweep": swept,
              "alarm_signature": "alarm(level, msg)",
              "measured": m}
    covered = "/".join(sorted({s["level"] for s in swept})) or "-"
    advice = ["紧急级告警必须立即停机并回填工单；去重抑制 %d 条属预期行为（防刷屏）"
              % (len(out) - len(fired)),
              "嵌套三级实测覆盖级别: %s" % covered,
              "A 档循环测试设备 %d 台；边界用例 %d 组（温度 %d + 压力 %d）"
              % (len(swept), len(brows), len(tb), len(pb))]
    scope = ("读数 %d 条｜温度预警 %.0f℃ / 停机 %.0f℃｜压力预警 %.2f / 停机 %.2f"
             % (len(out), cfg.warn, cfg.danger, pw, pd))
    scope += " / 硬上限 %.2fMPa｜去重窗口 %.0fs" % (plimit, win)
    sections = [
        ("输入口径", [scope]),
        ("告警流水（alarm(level,msg) 输出）", lines),
        ("边界用例表（工单任务3 五组全覆盖）", boundary_lines),
        ("多条件嵌套三级 + 3 台设备循环（B/A 档）", sweep_lines),
        ("告警分布", ["%s: %d 次（已去重）" % (k, v) for k, v in sorted(stat.items())]
         or ["无告警"])]
    style = stylecheck.augment(sections, result, ROOT,
                               float(cfg.get("style_min", 90.0)))
    m["style_rate"] = style["rate"]
    v = tiers.verdict(tiers.gates(cfg), m)
    result["tiers"] = v
    sections.append(("验收档位判定（实测）", tiers.render_lines(v)))
    sections.append(("结论与建议", advice + [
        "实测达成档位: %s（功能门实测见上，人工答辩项 %d 条）"
        % (v["claimed"], len(v["manual"]))]))
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir):
    """兼容旧入口：返回报告段（cli / tests 用）。"""
    sections, _ = build(cfg, out_dir)
    return sections
