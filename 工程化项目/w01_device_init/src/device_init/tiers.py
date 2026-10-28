# -*- coding: utf-8 -*-
"""工单 W01 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W01工单-设备参数初始化系统.md》验收标准表：
  及格(D)：≥6个变量、≥3种数据类型；规范率≥70%
  良好(C)：输出格式清晰对齐；换算正确
  优秀(B)：≥8变量、4种类型；换算≥2处；规范率≥90%
  优(A)：达B且使用input()录入并校验（温度范围提示）
数字门槛外置在 config/rules.yaml 的 tiers: 段（缺失回落 DEFAULT_GATES，
数值与工单逐字一致——唯一出处是 rules.yaml，回落只是兜底不是第二口径）；
功能输入全部来自 measure.collect 的实测值（AST 计数、独立公式复核、
stdin 注入真走 input()），verdict 只做比较——与 stylecheck 同口径，可复核。
"""

TIERS = [
    ("及格(D)", "≥6 个变量、≥3 种数据类型"),
    ("良好(C)",
     "输出格式清晰对齐（实测口径：≥5 条键值行冒号同列）；"
     "换算正确（实测口径：独立公式逐条复核 0 失败）"),
    ("优秀(B)", "≥8 变量、4 种类型；换算≥2 处"),
    ("优(A)", "达 B 且使用 input() 录入并校验（温度范围提示）"),
]
KEYS = ("D", "C", "B", "A")
# 工单里无法机器判定的条目：W01 验收表四档均可实测 → 0 条
MANUAL = []
DEFAULT_GATES = {
    "D": {"rate_min": 70.0, "min_vars": 6, "min_types": 3},
    "C": {"rate_min": None},
    "B": {"rate_min": 90.0, "min_vars": 8, "min_types": 4,
          "min_conversions": 2},
    "A": {"rate_min": 90.0},
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


def _own(key, g, m):
    """本档自己的功能门（工单原句对应项），叠加关系由 _functional 负责。"""
    if key == "D":
        return (m["ast_vars"] >= g["min_vars"] and
                m["ast_types"] >= g["min_types"])
    if key == "C":
        return m["align_ok"] and m["conv_failed"] == 0 and m["conv_checked"] > 0
    if key == "B":
        return (m["ast_vars"] >= g["min_vars"] and
                m["ast_types"] >= g["min_types"] and
                m["conv_funcs"] >= g["min_conversions"])
    return m["input_probe_ok"] and m["input_hint_ok"]


def _functional(key, g, m):
    """工单档位逐级叠加：上一档功能项不过，本档必不过（削能力必掉档）。"""
    upto = KEYS[:KEYS.index(key) + 1]
    return all(_own(k, g[k], m) for k in upto)


def _rate_or_none(v):
    """rate_min 归一化：数字保留；缺失/空值（yaml_lite 的空帧）视为"工单未设"。"""
    return float(v) if isinstance(v, (int, float)) else None


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
    head = ("实测达成档位: %s ｜ AST 台账变量 %d 个/%d 种类型(%s)"
            " ｜ 换算函数 %d 个、独立公式复核错 %d 处"
            " ｜ 冒号列 %d 行同列 %d ｜ input() 实测: %s"
            % (v["claimed"], m["ast_vars"], m["ast_types"],
               ",".join(m["types"]), m["conv_funcs"], m["conv_failed"],
               m["colon_lines"], m["colon_same"], m["input_detail"]))
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
