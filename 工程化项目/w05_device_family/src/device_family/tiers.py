# -*- coding: utf-8 -*-
"""工单 W05 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W05工单-工业设备继承体系.md》验收标准：
  及格(D)：1 基类 + 2 子类 + 继承覆盖；规范率≥75%
  良好(C)：多态调用演示清晰；docstring 齐全
  优秀(B)：≥3 子类；规范率≥90%；覆盖方法内用 super() 协作
  优(A)：达 B 且体现"is-a"设计判断（说明为什么不用继承实现某设备）
输入全部来自 pipeline 的实测值：家族结构/覆盖/super()/docstring 用 ast
真实统计 core.py（与 stylecheck 同口径），多态输出来自真实遍历子类实例
调用同名方法，A 档文档段落按字数与"组合"提及数实测——verdict 只做比较。
数字门槛外置在 config/rules.yaml 的 `tiers:` 段。
"""

TIERS = [
    ("及格(D)", "1 基类 + 2 子类 + 继承覆盖；规范率≥75%", 75.0),
    ("良好(C)", "多态调用演示清晰；docstring 齐全", 80.0),
    ("优秀(B)", "≥3 子类；规范率≥90%；覆盖方法内用 super() 协作", 90.0),
    ("优(A)", "达 B 且体现「is-a」设计判断（说明为什么不用继承实现某设备）", 90.0),
]
KEYS = ("D", "C", "B", "A")
# 机器判不了、必须教师现场确认的条目（报告明列，答辩时逐条勾）
MANUAL = [
    "多态调用演示讲解是否清晰（『清晰』属口头答辩项，实测只判各自输出确有差异）",
    "提交物核对：继承体系类图照片",
    "课中抽查：能用循环处理 10 台设备数据（口述/白板）",
    "A 档答辩：口头说明为什么工位不用继承实现",
]

GATES = {
    "D_style_min": 75.0, "C_style_min": 80.0,
    "B_style_min": 90.0, "A_style_min": 90.0,
    "D_min_base": 1, "D_min_subs": 2, "D_min_overrides": 1,
    "C_min_doc_rate": 100.0, "C_min_poly_kinds": 2, "C_min_poly_calls": 2,
    "B_min_subs": 3, "B_min_super": 3, "B_max_super_gaps": 0,
    "A_min_doc_chars": 600, "A_min_doc_mentions": 3,
}
_STYLE_KEY = {"D": "D_style_min", "C": "C_style_min",
              "B": "B_style_min", "A": "A_style_min"}


def gates_from(cfg):
    """rules.yaml `tiers:` 段读出数字门槛（config.py 负责合并与回落）。"""
    return cfg.tier_gates(GATES)


def verdict(gates, rate, n_base, n_subs, n_overrides, doc_filled, doc_total,
            poly_kinds, poly_calls, poly_distinct, n_super, super_gaps,
            isa_present, isa_chars, isa_mentions, comp_ok):
    """按实测值给四档判定；每档 = 功能门 + 规范率门，缺一即不达标。

    档位按工单语义递进：C 建立在 D 之上，B 工单虽未明写但"≥3 子类"以继承
    成立为前提，A 明写"达 B"。doc_rate = docstring 实测覆盖率（齐全=100%）；
    isa_chars/isa_mentions = is-a 判断正文的实测字数与"组合"提及数。
    """
    doc_rate = 100.0 * doc_filled / doc_total if doc_total else 0.0
    fd = (n_base >= int(gates["D_min_base"])
          and n_subs >= int(gates["D_min_subs"])
          and n_overrides >= int(gates["D_min_overrides"]))
    fc = (fd
          and poly_kinds >= int(gates["C_min_poly_kinds"])
          and poly_calls >= int(gates["C_min_poly_calls"])
          and poly_distinct == poly_calls
          and doc_rate >= float(gates["C_min_doc_rate"]))
    fb = (fc
          and n_subs >= int(gates["B_min_subs"])
          and n_super >= int(gates["B_min_super"])
          and super_gaps <= int(gates["B_max_super_gaps"]))
    fa = (fb and bool(isa_present) and bool(comp_ok)
          and isa_chars >= int(gates["A_min_doc_chars"])
          and isa_mentions >= int(gates["A_min_doc_mentions"]))
    functional = {"D": fd, "C": fc, "B": fb, "A": fa}
    out = []
    for (name, need, _), key in zip(TIERS, KEYS):
        gate = float(gates[_STYLE_KEY[key]])
        ok = bool(functional[key]) and rate >= gate
        out.append({"tier": name, "gate": gate, "need": need,
                    "functional": bool(functional[key]),
                    "style_ok": rate >= gate, "pass": ok})
    claimed = next((t["tier"] for t in reversed(out) if t["pass"]),
                   "未达 D 档")
    return {"tiers": out, "claimed": claimed,
            "measured": {"n_base": n_base, "n_subs": n_subs,
                         "n_overrides": n_overrides, "n_super": n_super,
                         "super_gaps": super_gaps,
                         "doc": "%d/%d=%.0f%%" % (doc_filled, doc_total,
                                                  doc_rate),
                         "poly_kinds": poly_kinds, "poly_calls": poly_calls,
                         "poly_distinct": poly_distinct,
                         "isa_present": bool(isa_present),
                         "isa_chars": isa_chars,
                         "isa_mentions": isa_mentions,
                         "comp_ok": bool(comp_ok),
                         "manual": list(MANUAL)}}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    lines = ["实测达成档位: %s ｜ AST 实测: 基类 %d 个 / 子类 %d 个 / 覆盖 %d 处"
             " ｜ super() 协作 %d 处（缺口 %d）｜ docstring %s"
             % (v["claimed"], m["n_base"], m["n_subs"], m["n_overrides"],
                m["n_super"], m["super_gaps"], m["doc"])]
    lines.append("多态实测: 一个循环喊 start() %d 次，自有实现的子类 %d 个，"
                 "输出互不相同 %d 条 ｜ is-a 判断正文 %d 字（『组合』提及 %d 处，"
                 "达标线见 rules.yaml tiers:）"
                 % (m["poly_calls"], m["poly_kinds"], m["poly_distinct"],
                    m["isa_chars"], m["isa_mentions"]))
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("人工答辩项 %d 条（教师答辩时确认）:" % len(m["manual"]))
    lines.extend("  · " + x for x in m["manual"])
    return lines
