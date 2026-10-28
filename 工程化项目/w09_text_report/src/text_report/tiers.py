# -*- coding: utf-8 -*-
"""工单 W09 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W09工单-工业故障分析报告生成系统.md》验收标准：
  及格(D)：分词正确 + 词云 PNG 生成；规范率≥80%
  良好(C)：停用词处理得当；词频 Top10 柱状图正确
  优秀(B)：词云中文渲染（字体实测）；洞察有数据支撑（Top20 关键词）；规范率≥90%
  优(A)：达 B 且按系统分组对比词云（传动 vs 电气）
PNG 一律用磁盘字节数实测；缺库/缺字体时如实判缺，不降门槛。
"""

TIERS = [
    ("及格(D)", "分词产出>0 + 词云 PNG 真实落盘（>1000 字节）", 80.0),
    ("良好(C)", "停用词过滤生效 + Top10 词频柱状图落盘", 85.0),
    ("优秀(B)", "词云中文字体实测 + Top20 关键词 + 洞察含实测数字", 90.0),
    ("优(A)", "达 B 且按系统分组对比词云≥2 张（如传动 vs 电气）", 90.0),
]
KEYS = ("D", "C", "B", "A")
MIN_PNG_BYTES = 1000
#: 工单里机器测不了、必须答辩/现场核对的项——如实列出，不代答也不隐瞒
manual = [
    "词云是否美观（蒙版/配色）——工单 B 档主观项，答辩打分",
    "洞察结论是否与现场故障规律相符（答辩核对）",
]


def gates_from(value):
    """rules.yaml 的 tiers: 段 → {档位字母: 门槛}；非法项过滤，不谎报门槛。"""
    out = {}
    if isinstance(value, dict):
        for key in KEYS:
            try:
                out[key] = float(value[key])
            except (KeyError, TypeError, ValueError):
                continue
    return out


def verdict(rate, n_tokens, cloud_bytes, stop_ok, chart_bytes, font_ok,
            top20_count, insight_ok, group_cloud_bytes, gates=None,
            stop_hits=0):
    """cloud_bytes/chart_bytes/group_cloud_bytes: 磁盘实测字节数。

    stop_hits: 停用词在原始分词结果中的实测命中条数（工单 C"处理得当"
    的可测部分——先要真的出现过，过滤才有意义）。
    gates: 外置门槛（config.py tier_gates 读出）；缺项回落 TIERS 内置默认。
    """
    g = {k: t[2] for k, t in zip(KEYS, TIERS)}
    g.update(gates or {})
    g_clouds = sum(1 for b in group_cloud_bytes if b > MIN_PNG_BYTES)
    b_func = bool(font_ok) and top20_count >= 10 and bool(insight_ok)
    functional = {
        "D": n_tokens > 0 and cloud_bytes > MIN_PNG_BYTES,
        "C": bool(stop_ok) and stop_hits >= 1 and chart_bytes > MIN_PNG_BYTES,
        "B": b_func,
        "A": b_func and g_clouds >= 2,
    }
    out = []
    for (name, need, _default_gate), key in zip(TIERS, KEYS):
        gate = g[key]
        ok = bool(functional[key]) and rate >= gate
        out.append({"tier": name, "gate": gate, "need": need,
                    "functional": bool(functional[key]),
                    "style_ok": rate >= gate, "pass": ok})
    claimed = next((t["tier"] for t in reversed(out) if t["pass"]),
                   "未达 D 档")
    return {"tiers": out, "claimed": claimed,
            "measured": {"n_tokens": n_tokens, "cloud_bytes": cloud_bytes,
                         "chart_bytes": chart_bytes, "stop_ok": bool(stop_ok),
                         "stop_hits": int(stop_hits),
                         "font_ok": bool(font_ok),
                         "top20_count": top20_count,
                         "insight_ok": bool(insight_ok),
                         "group_clouds": g_clouds}}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    lines = ["实测达成档位: %s ｜ 分词 %d 个｜词云 %d 字节｜柱状图 %d 字节｜"
             "停用词命中 %d 处｜Top20 关键词 %d 个｜分组词云 %d 张"
             % (v["claimed"], m["n_tokens"], m["cloud_bytes"],
                m["chart_bytes"], m["stop_hits"], m["top20_count"],
                m["group_clouds"])]
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("  （人工答辩项，机器不代判）%s" % "；".join(manual))
    return lines
