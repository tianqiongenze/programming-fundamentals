# -*- coding: utf-8 -*-
"""工单 W07 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W07工单-工业数据格式转换工具.md》验收标准：
  及格(D)：处理≥2 种格式 + 使用正则；规范率≥75%
  良好(C)：三种格式全通；字典结构统一
  优秀(B)：≥3 种格式 + 容错（缺字段/乱序报文）；规范率≥90%
  优(A)：达 B 且批量转换文件并输出转换统计
输入全部来自 pipeline 的实测值：本次运行真实解析出的格式集合、正则
kv 通道条数、成功行键集合是否一致（"字典结构统一"按实测判定）、容错
样本实测、output/samples/ 多个样本文件的批量转换计数（产物回读行数），
verdict 只做比较。数字门槛外置在 config/rules.yaml 的 `tiers:` 段。
"""

TIERS = [
    ("及格(D)", "处理≥2 种格式 + 使用正则（kv 通道实测走通）；规范率≥75%",
     75.0),
    ("良好(C)", "三种格式全通；字典结构统一（实测键集合一致）", 80.0),
    ("优秀(B)", "≥3 种格式 + 容错（缺字段/乱序报文实测通过）；规范率≥90%",
     90.0),
    ("优(A)", "达 B 且批量转换多个样本文件并输出转换统计（实测计数）", 90.0),
]
KEYS = ("D", "C", "B", "A")
REQUIRED_FORMATS = ("json", "kv", "csv")
# 机器判不了、必须教师现场确认的条目（报告明列，答辩时逐条勾）
MANUAL = [
    "课堂决策矩阵（列表/字典/集合选型）工单填写照片核对",
    "课中抽查：能 import random 生成测试数据（口述/白板）",
    "提交物核对：转换输出样例与 report.txt 实测行一致",
]

GATES = {
    "D_style_min": 75.0, "C_style_min": 80.0,
    "B_style_min": 90.0, "A_style_min": 90.0,
    "D_min_formats": 2, "D_min_regex_kv": 1,
    "B_min_formats": 3, "B_min_bad": 1,
    "A_min_batch_files": 3,
}
_STYLE_KEY = {"D": "D_style_min", "C": "C_style_min",
              "B": "B_style_min", "A": "A_style_min"}


def gates_from(cfg):
    """rules.yaml `tiers:` 段读出数字门槛（config.py 负责合并与回落）。"""
    return cfg.tier_gates(GATES)


def verdict(gates, rate, formats, n_regex_kv, uniform, n_bad, stats_ok,
            out_of_order_ok, missing_field_ok, batch):
    """按实测值给四档判定；每档 = 功能门 + 规范率门，缺一即不达标。

    formats: 本次实测解析成功的格式集合；uniform: 成功行键集合实测一致；
    batch: 批量转换实测 dict（files/lines/n_ok/n_fail/rows——rows 为产物
    文件回读行数，与 n_ok 对不上就说明统计是虚报）。档位按工单语义递进，
    A 档工单明写"达 B"。
    """
    got = set(formats)
    has_all = all(f in got for f in REQUIRED_FORMATS)
    tolerant = (stats_ok and out_of_order_ok and missing_field_ok
                and n_bad >= int(gates["B_min_bad"]))
    fd = (len(got) >= int(gates["D_min_formats"])
          and n_regex_kv >= int(gates["D_min_regex_kv"]))
    fc = fd and has_all and bool(uniform)
    fb = fc and len(got) >= int(gates["B_min_formats"]) and tolerant
    fa = (fb and batch["files"] >= int(gates["A_min_batch_files"])
          and batch["rows"] == batch["n_ok"] >= 1)
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
            "measured": {"formats": sorted(got), "n_regex_kv": n_regex_kv,
                         "uniform": bool(uniform), "n_bad": n_bad,
                         "out_of_order_ok": bool(out_of_order_ok),
                         "missing_field_ok": bool(missing_field_ok),
                         "batch": dict(batch),
                         "manual": list(MANUAL)}}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    b = m["batch"]
    lines = ["实测达成档位: %s ｜ 解析成功格式 %s（正则 kv 通道 %d 条）｜ "
             "字典结构统一: %s ｜ 隔离 %d 条"
             % (v["claimed"], "/".join(m["formats"]) or "无",
                m["n_regex_kv"], "是" if m["uniform"] else "否", m["n_bad"])]
    lines.append("批量转换实测: 样本 %d 个文件 / %d 行 → 成功 %d 失败 %d，"
                 "产物回读 %d 行（统计与产物逐行核对）"
                 % (b["files"], b["lines"], b["n_ok"], b["n_fail"],
                    b["rows"]))
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("人工答辩项 %d 条（教师答辩时确认）:" % len(m["manual"]))
    lines.extend("  · " + x for x in m["manual"])
    return lines
