# -*- coding: utf-8 -*-
"""工单 W03 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W03工单-工业实时告警系统Ⅱ.md》验收标准表：
  及格(D)：循环跑通+2函数；规范率≥70%
  良好(C)：统计报告正确；无死循环风险
  优秀(B)：函数职责清晰（每个函数≤15行）；规范率≥85%；注释清晰
  优(A)：达B且重构W02代码对比说明"函数化收益"
数字门槛外置在 config/rules.yaml 的 tiers: 段；功能输入全部来自
measure.collect 的实测值（AST 函数清点、循环实跑样本数、统计复算、
while 有界实测、W02→W03 对照数字），verdict 只做比较——可复核。
"注释清晰"的可测部分 = 每个函数都有 docstring；口头解释归人工答辩项。
"""

TIERS = [
    ("及格(D)", "循环跑通（设备×周期双层 for 实跑）+ 2 函数 check_device/alarm"),
    ("良好(C)", "统计报告正确（逐台复算核对）；无死循环风险（有界实测）"),
    ("优秀(B)", "函数职责清晰（每个函数≤15 行，AST 实测）；注释清晰（docstring 全覆盖）"),
    ("优(A)", "达 B 且重构 W02 代码对比说明「函数化收益」（对照数字实测）"),
]
KEYS = ("D", "C", "B", "A")
# 工单里无法机器判定的条目：A 档"说明收益"的解释性陈述要现场答辩
MANUAL = ["「函数化收益」的取舍口头解释（对照数字已实测：判级比较点/函数数/行数）"]
DEFAULT_GATES = {
    "D": {"rate_min": 70.0, "min_functions": 2, "min_samples": 30},
    "C": {"rate_min": None},
    "B": {"rate_min": 85.0, "max_fn_lines": 15, "min_doc_ratio": 1.0},
    "A": {"rate_min": 85.0},
}


def gates(cfg):
    """rules.yaml 的 tiers: 段 → {档字母: 门槛 dict}；缺档用 DEFAULT_GATES 补。"""
    raw = cfg.get("tiers") or {}
    out = {}
    for key in KEYS:
        g = dict(DEFAULT_GATES[key])
        if isinstance(raw.get(key), dict):
            g.update(raw[key])
        out[key] = g
    return out


def _rate_or_none(v):
    """rate_min 归一化：数字保留；缺失/空值（yaml_lite 的空帧）视为"工单未设"。"""
    return float(v) if isinstance(v, (int, float)) else None


def _own(key, g, m):
    """本档自己的功能门（工单原句对应项），叠加关系由 _functional 负责。"""
    if key == "D":
        return (m["named_funcs"] >= g["min_functions"] and
                m["for_loops_patrol"] >= 2 and
                m["samples"] >= g["min_samples"])
    if key == "C":
        return m["stats_ok"] and m["bounded_ok"]
    if key == "B":
        over = sum(1 for n in m["body_lines"].values()
                   if n > g["max_fn_lines"])
        need = g["min_doc_ratio"] * m["n_funcs"]
        return over == 0 and m["doc_defs"] >= need
    return m["w02"]["ok"] and m["has_doc"]


def _functional(key, g, m):
    """工单档位逐级叠加：上一档功能项不过，本档必不过（削能力必掉档）。"""
    upto = KEYS[:KEYS.index(key) + 1]
    return all(_own(k, g[k], m) for k in upto)


def verdict(g, m):
    """按实测值给四档判定：每档 = 功能门 + 规范率门（工单未设率门槛记 None）。"""
    rate = float(m.get("style_rate", 0.0))
    out = []
    for (name, need), key in zip(TIERS, KEYS):
        gate = _rate_or_none(g[key].get("rate_min"))
        style_ok = gate is None or rate >= float(gate)
        fun = bool(_functional(key, g, m))
        out.append({"tier": name, "key": key, "need": need,
                    "rate_min": gate, "functional": fun,
                    "style_ok": style_ok, "pass": fun and style_ok})
    claimed = next((t["tier"] for t in reversed(out) if t["pass"]),
                   "未达 D 档")
    return {"tiers": out, "claimed": claimed, "measured": m, "gates": g,
            "manual": list(MANUAL)}


def _gate_str(t):
    if t["rate_min"] is None:
        return "规范率门槛: 工单未设"
    return "规范率门槛≥%.0f%%" % float(t["rate_min"])


def render_lines(v):
    """把判定渲染成报告行（实测达成档位 + 四行档位 + 人工答辩项）。"""
    m = v["measured"]
    head = ("实测达成档位: %s ｜ AST 函数 %d 个（最长体 %d 行）｜ "
            "docstring 覆盖 %d/%d ｜ 循环实测 %d 台×%d 周期 = %d 样本 ｜ "
            "while 最长 %d 轮（约定上限 %d）｜ W02→W03 对照: %s ｜ "
            "对比文档 %s（%d 字符）"
            % (v["claimed"], m["n_funcs"], m["max_body"],
               m["doc_defs"], m["n_funcs"], m["devices"], m["n_cycles"],
               m["samples"], m["while_max_cycles"], m["while_cap"],
               m["w02"]["detail"], m["doc_rel"], m["doc_chars"]))
    lines = [head]
    for t in v["tiers"]:
        lines.append("  %-8s %s [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], _gate_str(t),
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    if v["manual"]:
        lines.append("人工答辩项 %d 条，教师答辩时确认: %s"
                     % (len(v["manual"]), "；".join(v["manual"])))
    else:
        lines.append("人工答辩项 0 条：四档门槛均由代码实测判定")
    return lines
