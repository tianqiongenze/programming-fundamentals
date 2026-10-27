# -*- coding: utf-8 -*-
"""质量日报：派生指标 + 等宽报表渲染（纯函数）。"""


def derive(k):
    """派生：合格率、达成率。"""
    produced = float(k["produced"])
    planned = float(k["planned"])
    good = float(k["good"])
    return {
        "line": str(k["line"]),
        "planned": int(planned),
        "produced": int(produced),
        "good": int(good),
        "oee": float(k["oee"]),
        "good_rate": round(good / produced, 4) if produced else 0.0,
        "plan_rate": round(produced / planned, 4) if planned else 0.0,
    }


def render_table(rows):
    header = ("产线", "计划", "产出", "合格", "合格率", "达成率", "OEE%")
    body = [(r["line"], str(r["planned"]), str(r["produced"]), str(r["good"]),
             "%.2f%%" % (r["good_rate"] * 100), "%.2f%%" % (r["plan_rate"] * 100),
             "%.1f%%" % r["oee"]) for r in rows]
    return [header] + body


def to_markdown(rows, title):
    out = ["# %s" % title, "", "口径: 合格率=合格/产出；达成率=产出/计划；OEE 取自系统", ""]
    hdr = render_table(rows)[0]
    out.append("| " + " | ".join(hdr) + " |")
    out.append("|" + "---|" * len(hdr))
    for r in render_table(rows)[1:]:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)
