# -*- coding: utf-8 -*-
"""工单 W08 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W08工单-工业数据文件处理系统.md》验收标准：
  及格(D)：读写≥2 种格式 + 基本验证；规范率≥75%
  良好(C)：三维验证齐全（缺失/类型/范围）；bad.csv 可追溯
  优秀(B)：清洗报告清晰；输出规范列名；规范率≥90%
  优(A)：达 B 且命令行参数选择输入文件（含 GBK 编码演示）
输入全部来自 pipeline 实测（round-trip 结果、维度计数、bad.csv 行数、
data.csv 表头、GBK 输入自检），verdict 只做比较。
"""

TIERS = [
    ("及格(D)", "CSV+JSON 双格式读写且 round-trip 通过 + 基本验证", 75.0),
    ("良好(C)", "缺失/类型/范围三维验证齐全；bad.csv 可追溯", 80.0),
    ("优秀(B)", "清洗报告清晰（维度计数入报告）；输出规范列名", 90.0),
    ("优(A)", "达 B 且 --input/--encoding 输入文件通道实测走通（GBK 演示）", 90.0),
]
KEYS = ("D", "C", "B", "A")
EXPECTED_HEADER = "code,temp,press"
#: 工单里机器测不了、必须答辩/现场核对的项——如实列出，不代答也不隐瞒
manual = [
    "清洗报告文字是否通顺可读（答辩抽查）",
    "输入数据来源与现场文件口径是否一致（答辩核对）",
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


def verdict(rate, csv_ok, json_ok, n_checked, dims, bad_csv_rows, n_bad,
            header_ok, report_ok, input_demo_ok, gates=None):
    """dims: {缺失/类型/范围: 实测计数}；header_ok: data.csv 列名与规范一致。

    gates: 外置门槛（config.py tier_gates 读出）；缺项回落 TIERS 内置默认。
    """
    g = {k: t[2] for k, t in zip(KEYS, TIERS)}
    g.update(gates or {})
    dims_hit = all(int(dims.get(k, 0)) >= 1 for k in ("缺失", "类型", "范围"))
    b_func = bool(header_ok) and bool(report_ok)
    functional = {
        "D": n_checked >= 1 and bool(csv_ok) and bool(json_ok),
        "C": dims_hit and n_bad >= 1 and bad_csv_rows == n_bad,
        "B": b_func and n_checked >= 1,
        "A": b_func and bool(input_demo_ok),
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
            "measured": {"n_checked": n_checked, "dims": dict(dims),
                         "n_bad": n_bad, "bad_csv_rows": bad_csv_rows,
                         "header_ok": bool(header_ok),
                         "input_demo_ok": bool(input_demo_ok)}}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    d = m["dims"]
    lines = ["实测达成档位: %s ｜ 验证 %d 行（缺失 %d/类型 %d/范围 %d）｜ "
             "bad.csv %d 行｜规范列名 %s｜输入文件通道 %s"
             % (v["claimed"], m["n_checked"], d.get("缺失", 0),
                d.get("类型", 0), d.get("范围", 0), m["bad_csv_rows"],
                "实测通过" if m["header_ok"] else "缺",
                "实测走通(GBK)" if m["input_demo_ok"] else "缺")]
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("  （人工答辩项，机器不代判）%s" % "；".join(manual))
    return lines
