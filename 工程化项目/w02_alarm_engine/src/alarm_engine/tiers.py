# -*- coding: utf-8 -*-
"""工单 W02 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W02工单-工业实时告警系统Ⅰ.md》验收标准表：
  及格(D)：≥2个if判断+1个告警函数；规范率≥70%
  良好(C)：边界五组测试全对
  优秀(B)：多条件嵌套（提示/警告/停机三级）；规范率≥85%
  优(A)：达B且循环测试3台设备（为W3铺垫）
数字门槛外置在 config/rules.yaml 的 tiers: 段；功能输入全部来自
measure.collect 的实测值（AST 计数、边界五组独立公式复核、三级定向探针、
sweep 实跑台数），verdict 只做比较——与 stylecheck 同口径，可复核。
"""

TIERS = [
    ("及格(D)", "≥2 个 if 判断 + 1 个告警函数 alarm(level, msg)"),
    ("良好(C)", "边界五组测试全对（79.9/80/94.9/95/100 逐组核对）"),
    ("优秀(B)", "多条件嵌套（提示/警告/停机三级）"),
    ("优(A)", "达 B 且循环测试 3 台设备（为 W3 铺垫）"),
]
KEYS = ("D", "C", "B", "A")
# 工单 W02 验收表四档均可机器实测 → 无无法判定条目
MANUAL = []
DEFAULT_GATES = {
    "D": {"rate_min": 70.0, "min_ifs": 2, "min_alarm_fns": 1},
    "C": {"rate_min": None, "boundary_groups": 5},
    "B": {"rate_min": 85.0, "min_nest_depth": 2, "min_levels": 3},
    "A": {"rate_min": 85.0, "min_devices": 3},
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
        return (m["ast_ifs_d"] >= g["min_ifs"] and
                m["alarm_fns"] >= g["min_alarm_fns"])
    if key == "C":
        # "全对"= 组数恰为工单的五组，且逐组核对通过数 = 总数
        return (m["boundary_total"] == g["boundary_groups"] and
                m["boundary_pass"] == m["boundary_total"])
    if key == "B":
        return (m["nest_depth"] >= g["min_nest_depth"] and
                m["levels_hit"] >= g["min_levels"])
    return (m["devices_swept"] >= g["min_devices"] and
            m["sweep_has_for"] and m["alarm_via"])


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
    head = ("实测达成档位: %s ｜ AST if %d 处 + alarm(level,msg) %d 个"
            " ｜ 边界五组实测 %d/%d 全对 ｜ 嵌套深度 %d 层"
            " ｜ 提示/警告/停机实测 %d/3 ｜ 循环实测设备 %d 台"
            % (v["claimed"], m["ast_ifs_d"], m["alarm_fns"],
               m["boundary_pass"], m["boundary_total"], m["nest_depth"],
               m["levels_hit"], m["devices_swept"]))
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
