# -*- coding: utf-8 -*-
"""工单 W10 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W10工单-工业图像处理与报告生成.md》验收标准：
  及格(D)：图像标注完成 + PDF 可生成；规范率≥80%
  良好(C)：PDF 含图 + 表 + 结论三要素
  优秀(B)：排版专业（页边距/对齐/字号层级）；规范率≥90%
  优(A)：达 B 且多页报告（首页概览 + 次页明细）或自绘封面
输入全部来自 imaging 的实测：字节数、PDF 页数解析、结论正文扫描、
doc/style 对象回读的边距与字号集合；verdict 只做比较，不产生新数据。
"""

TIERS = [
    ("及格(D)", "标注图 400×300 落盘（>1000 字节）+ PDF 可生成", 80.0),
    ("良好(C)", "PDF 三要素实测：嵌图 + 表格 + 结论文本", 85.0),
    ("优秀(B)", "排版实测：中文字体 + ≥3 级字号 + 回读页边距 + 对齐生效", 90.0),
    ("优(A)", "达 B 且多页报告（实测页数≥2：封面+概览+明细）", 90.0),
]
KEYS = ("D", "C", "B", "A")
MIN_ARTIFACT_BYTES = 1000
IMG_SIZE_EXPECT = [400, 300]
#: 工单里机器测不了、必须答辩/现场核对的项——如实列出，不代答也不隐瞒
manual = [
    "排版视觉专业度（观感/留白/配色）——答辩打分",
    "标注框与真实缺陷位置的对应关系（现场核对）",
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


def verdict(rate, img_bytes, img_size, pdf_bytes, has_image, has_table,
            has_conclusion, font_ok, layout_ok, pages, gates=None,
            font_levels=0, margins_mm=None, aligns=None):
    """font_levels: 样式对象回读到的不同字号个数；margins_mm: 实测四边毫米。

    gates: 外置门槛（config.py tier_gates 读出）；缺项回落 TIERS 内置默认。
    """
    g = {k: t[2] for k, t in zip(KEYS, TIERS)}
    g.update(gates or {})
    pdf_real = pdf_bytes > MIN_ARTIFACT_BYTES
    c_func = bool(pdf_real and has_image and has_table and has_conclusion)
    b_func = (c_func and bool(font_ok) and bool(layout_ok)
              and int(font_levels) >= 3 and bool(margins_mm)
              and all(0 < float(m) <= 60 for m in margins_mm.values())
              and len(aligns or []) >= 1)
    functional = {
        "D": (img_bytes > MIN_ARTIFACT_BYTES
              and list(img_size) == IMG_SIZE_EXPECT and pdf_real),
        "C": c_func,
        "B": b_func,
        "A": b_func and pages >= 2,
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
            "measured": {"img_bytes": int(img_bytes),
                         "img_size": list(img_size),
                         "pdf_bytes": int(pdf_bytes),
                         "has_image": bool(has_image),
                         "has_table": bool(has_table),
                         "has_conclusion": bool(has_conclusion),
                         "font_ok": bool(font_ok),
                         "layout_ok": bool(layout_ok),
                         "font_levels": int(font_levels),
                         "margins_mm": dict(margins_mm or {}),
                         "aligns": list(aligns or []), "pages": int(pages)}}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    lines = ["实测达成档位: %s ｜ 标注图 %d 字节（%s）｜ PDF %d 字节 / %d 页｜"
             "三要素: 图%s/表%s/结论%s｜字号 %d 级｜边距 %s｜对齐 %s"
             % (v["claimed"], m["img_bytes"],
                "×".join(str(x) for x in m["img_size"]),
                m["pdf_bytes"], m["pages"],
                "✓" if m["has_image"] else "MISS",
                "✓" if m["has_table"] else "MISS",
                "✓" if m["has_conclusion"] else "MISS",
                m["font_levels"],
                "/".join("%.1f" % x for x in m["margins_mm"].values())
                or "MISS",
                "、".join(m["aligns"]) or "MISS")]
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("  （人工答辩项，机器不代判）%s" % "；".join(manual))
    return lines
