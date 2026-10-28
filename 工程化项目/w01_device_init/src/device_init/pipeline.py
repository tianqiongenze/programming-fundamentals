# -*- coding: utf-8 -*-
"""流水线：加载设备清单 → 换算评估 → 渲染 f-string 台账卡 → 规范体检 →
四档实测判定 → 落盘。

档位判定（tiers.verdict）吃的全部是实测值：measure.collect 的 AST 计数、
独立公式复核、冒号列对齐、stdin 注入真走 input() 的结果，加 stylecheck
的实测规范率——报告里的"达成档位"是算出来的，不是承诺出来的。
"""
import os

from . import core, io_utils, measure, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
# 台账可选字段：rules.yaml 没写就取这里的默认值（改配置不改代码）
OPTIONAL = (("voltage", float), ("power_kw", float), ("install_year", int),
            ("running", bool))


def load_devices(cfg):
    """配置 dict → Device 列表；缺字段用默认，脏值当场报错点名设备。"""
    devs = []
    for d in cfg.items:
        kwargs = {"code": str(d["code"]), "name": str(d["name"]),
                  "temp": float(d["temp"]), "press_kpa": float(d["press_kpa"]),
                  "rpm": int(d["rpm"]), "status": str(d.get("status", "running"))}
        for key, cast in OPTIONAL:
            if key in d:
                kwargs[key] = cast(d[key])
        devs.append(core.Device(**kwargs))
    return devs


def build(cfg, out_dir):
    """跑完整流水线，返回 (sections, result)；result 含实测值与档位判定供断言。"""
    devs = load_devices(cfg)
    if not devs:
        raise ValueError("config/rules.yaml 中 devices 为空——请至少配置 1 台设备")
    lines, lv_stat = [], {}
    for d in devs:
        lines.extend(core.card(d, cfg))
        lines.append("")
        key = core.level_of(d.temp, cfg.warn, cfg.danger)
        lv_stat[key] = lv_stat.get(key, 0) + 1
    # 台账字段类型清点（工单 B 档：≥8 变量、4 种类型的运行时旁证）
    table = core.var_table(devs[0])
    kinds = sorted({t for _, _, t in table})
    lines.append("台账变量清点（第 1 台设备）:")
    lines.extend("  %-14s %-14s 类型: %s" % (k, repr(v), t) for k, v, t in table)
    lines.append("  → 变量 %d 个 / 数据类型 %d 种（%s）"
                 % (len(table), len(kinds), ", ".join(kinds)))
    m = measure.collect(cfg, devs)
    result = {"n_devices": len(devs), "levels": lv_stat,
              "n_vars": len(table), "n_types": len(kinds), "types": kinds,
              "conversions": m["conv_names"], "measured": m,
              "devices": [{"code": d.code, "temp_c": d.temp,
                           "temp_f": round(core.c_to_f(d.temp), 2),
                           "press_mpa": round(core.kpa_to_mpa(d.press_kpa), 4),
                           "level": core.level_of(d.temp, cfg.warn, cfg.danger)}
                          for d in devs]}
    sections = [("输入口径", ["设备 %d 台｜预警线 %.1f℃｜停机线 %.1f℃｜单位 %s"
                % (len(devs), cfg.warn, cfg.danger, cfg.unit)]),
                ("设备台账卡（f-string 渲染）", lines),
                ("告警分布", ["%s: %d 台" % (k, v)
                 for k, v in sorted(lv_stat.items())])]
    # A 档展示段：input() 录入并校验（reader 可注入，默认走真实 input()）。
    # stdin 枯竭（如管道里跑 --tier --set interactive=true）只降级提示不崩——
    # A 档的机器实测证据来自 measure._input_probe，本段只是课堂演示变体。
    if cfg.flag("interactive", False):
        reader = cfg.get("reader") or input
        try:
            ilines = core.interactive_card(cfg, reader=reader)
        except EOFError:
            ilines = ["stdin 已枯竭——交互演示需终端输入；"
                      "A 档 input() 实测路径见「验收档位判定（实测）」段"]
        sections.append(("交互录入（A 档 input 变体）", ilines))
    style = stylecheck.augment(sections, result, ROOT,
                               float(cfg.get("style_min", 90.0)))
    m["style_rate"] = style["rate"]
    v = tiers.verdict(tiers.gates(cfg), m)
    result["tiers"] = v
    sections.append(("验收档位判定（实测）", tiers.render_lines(v)))
    sections.append(("结论与建议", [
        "共 %d 台设备；danger 级需当班处置并回填工单；台账 %d 变量/%d 类型，"
        "换算 %d 处；实测达成档位: %s"
        % (len(devs), len(table), len(kinds), m["conv_funcs"], v["claimed"])]))
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir):
    """兼容旧入口：返回报告段（cli / tests 用）。"""
    sections, _ = build(cfg, out_dir)
    return sections
