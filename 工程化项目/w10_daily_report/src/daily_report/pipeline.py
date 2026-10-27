# -*- coding: utf-8 -*-
"""KPI → 派生指标 → 等宽报表 → PDF（reportlab 缺失时降级 Markdown）。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    rows_raw = list(cfg.items)
    if not rows_raw:
        raise ValueError("config/rules.yaml 的 kpi 为空")
    rows = [core.derive(r) for r in rows_raw]
    os.makedirs(out_dir, exist_ok=True)
    # 1) 等宽文本报表（始终生成）
    tbl = core.render_table(rows)
    txt_lines = io_utils.fmt_table(tbl[1:], tbl[0]).splitlines()
    sections = [("输入口径", ["产线 %d 条｜合格率=合格/产出｜达成率=产出/计划" % len(rows)]),
                ("日报主表", txt_lines),
                ("结论与建议",
                 ["最低合格率 %.2f%%（%s）需当日复盘" % (
                     min(r["good_rate"] for r in rows) * 100,
                     min(rows, key=lambda r: r["good_rate"])["line"])])]
    report.save(sections, os.path.join(out_dir, "report.txt"))
    # 2) Markdown / PDF（特性探测降级）
    title = "两江智造集团 · 生产质量日报"
    md_path = os.path.join(out_dir, "report.md")
    io_utils.write_text(md_path, core.to_markdown(rows, title))
    pdf_ok, pdf_note = False, "reportlab 未安装，已降级为 report.md"
    try:
        from reportlab.lib import pagesizes
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
        from reportlab.lib.styles import getSampleStyleSheet
        pdf_path = os.path.join(out_dir, "report.pdf")
        doc = SimpleDocTemplate(pdf_path, pagesize=pagesizes.A4)
        styles = getSampleStyleSheet()
        story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
        story.append(Paragraph("口径: 合格率=合格/产出；达成率=产出/计划", styles["Normal"]))
        story.append(Spacer(1, 8))
        story.append(Table(tbl))
        doc.build(story)
        pdf_ok = os.path.exists(pdf_path)
        pdf_note = "已生成 report.pdf（A4）"
    except ImportError:
        pass
    result = {"rows": rows, "pdf": pdf_ok,
              "files": ["report.txt", "report.md", "report.pdf" if pdf_ok else "report.md"]}
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    sections.append(("产物清单", ["report.txt（等宽报表）", "report.md（可读版）", pdf_note]))
    return sections
