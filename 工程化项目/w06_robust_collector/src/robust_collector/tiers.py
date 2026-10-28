# -*- coding: utf-8 -*-
"""工单 W06 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W06工单-健壮的工业数据采集程序.md》验收标准：
  及格(D)：处理≥2 种异常 + 基本日志；规范率≥75%
  良好(C)：INFO/WARNING/ERROR 三级日志分明；统计输出正确
  优秀(B)：≥3 种异常 + 完整 finally；日志可定位到行；规范率≥90%
  优(A)：达 B 且脏数据自动写入 bad_records.csv 备查
输入全部来自 pipeline 的实测值（日志文件反读、CSV 行数、异常计数），
verdict 只做比较，不产生新数据——与 stylecheck 同口径，可复核。
"""

TIERS = [
    ("及格(D)", "处理≥2 种异常 + 基本日志（run.log 非空）", 75.0),
    ("良好(C)", "INFO/WARNING/ERROR 三级日志分明；统计输出正确", 80.0),
    ("优秀(B)", "≥3 种异常 + 完整 finally；日志可定位到行", 90.0),
    ("优(A)", "达 B 且脏数据自动写入 bad_records.csv 备查", 90.0),
]
KEYS = ("D", "C", "B", "A")


def verdict(rate, n_exc_types, ran_finally, levels, row_refs,
            n_bad, stats_ok, bad_csv_rows, log_lines):
    """按实测值给四档判定；每档 = 功能门 + 规范率门，缺一即不达标。

    levels: run.log 里按级别统计的条数 dict（INFO/WARNING/ERROR）；
    row_refs: 日志中"第N行"可定位记录条数；bad_csv_rows: 备查 CSV 实测行数。
    """
    lv = {k: int(levels.get(k, 0)) for k in ("INFO", "WARNING", "ERROR")}
    located = n_bad >= 1 and row_refs >= n_bad
    reaches_b = n_exc_types >= 3 and ran_finally and located
    functional = {
        "D": n_exc_types >= 2 and log_lines >= 1,
        "C": all(v >= 1 for v in lv.values()) and stats_ok,
        "B": reaches_b,
        "A": reaches_b and bad_csv_rows == n_bad,
    }
    out = []
    for (name, need, gate), key in zip(TIERS, KEYS):
        ok = bool(functional[key]) and rate >= gate
        out.append({"tier": name, "gate": gate, "need": need,
                    "functional": bool(functional[key]),
                    "style_ok": rate >= gate, "pass": ok})
    claimed = next((t["tier"] for t in reversed(out) if t["pass"]),
                   "未达 D 档")
    return {"tiers": out, "claimed": claimed,
            "measured": {"n_exc_types": n_exc_types,
                         "ran_finally": bool(ran_finally), "levels": lv,
                         "row_refs": row_refs, "log_lines": log_lines,
                         "n_bad": n_bad, "bad_csv_rows": bad_csv_rows}}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    lines = ["实测达成档位: %s ｜ 实测捕获异常 %d 种 ｜ 日志 %d 行（INFO %d/"
             "WARNING %d/ERROR %d）｜ 定位到行 %d 处 ｜ bad_records.csv %d 行"
             % (v["claimed"], m["n_exc_types"], m["log_lines"],
                m["levels"]["INFO"], m["levels"]["WARNING"],
                m["levels"]["ERROR"], m["row_refs"], m["bad_csv_rows"])]
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    return lines
