# -*- coding: utf-8 -*-
"""KPI → 派生指标 → 等宽报表 → 缺陷标注图（Pillow）→ 多页图文 PDF → 档位判定。

工单 W10 的验收证据全部实测：标注图尺寸/字节从落盘文件读回，PDF 页数用
pypdf 解析、图内嵌用字节探测；reportlab/Pillow 缺失时如实记 MISS，
不生成假产物。档位由 tiers.verdict 用这些实测值计算。
"""
import os

from . import core, imaging, io_utils, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))


def build(cfg, out_dir):
    """跑完整日报流水线，返回 (sections, result)；result 供 pytest 断言。"""
    rows_raw = list(cfg.items)
    if not rows_raw:
        raise ValueError("config/rules.yaml 的 kpi 为空")
    rows = [core.derive(r) for r in rows_raw]
    io_utils.ensure_dir(out_dir)
    # 1) 等宽文本报表（始终生成）
    tbl = core.render_table(rows)
    txt_lines = io_utils.fmt_table(tbl[1:], tbl[0]).splitlines()
    min_line = min(rows, key=lambda r: r["good_rate"])
    conclusion = [
        "最低合格率 %.2f%%（%s）需当日复盘。" % (
            min_line["good_rate"] * 100, min_line["line"]),
        "口径: 合格率=合格/产出；达成率=产出/计划。",
    ]
    # 2) 缺陷标注图（工单要求①②：尺寸与坐标由 config 给定，红框实测计数）
    defects = cfg.raw.get("defects") or []
    ann = cfg.get("annotate") if isinstance(cfg.get("annotate"), dict) else {}
    img_path, img_note, img_m = imaging.annotate(
        defects, out_dir, width=ann.get("width", 400),
        height=ann.get("height", 300))
    # 3) Markdown 兜底 + 多页图文 PDF（工单要求③④）
    title = "两江智造集团 · 生产质量日报"
    md_path = os.path.join(out_dir, "report.md")
    io_utils.write_text(md_path, core.to_markdown(rows, title))
    layout = cfg.get("layout") if isinstance(cfg.get("layout"), dict) else {}
    margin_mm = float(layout.get("margin_mm", 18))
    pdf_path, pdf_note, pdf_m = imaging.build_pdf(
        rows, tbl, title, conclusion, img_path, out_dir,
        margin_mm=margin_mm)
    # 4) 实测汇总 → 档位判定
    style = stylecheck.scan_project(ROOT)
    result = {"rows": rows, "pdf_ok": bool(pdf_path),
              "files": ["report.txt", "report.md",
                        "report.pdf" if pdf_path else "report.md（PDF 降级）"],
              "image": {"path": img_path, "note": img_note, **img_m},
              "pdf": {"path": pdf_path, "note": pdf_note, **pdf_m},
              "style_rate": style["rate"],
              "style_violations": style["violations"],
              "style_engine": style["engine"],
              "conclusion_lines": conclusion}
    img_bytes = img_m.get("bytes", 0)
    pdf_bytes = pdf_m.get("bytes", 0)
    result["tiers"] = tiers.verdict(
        rate=style["rate"], img_bytes=img_bytes,
        img_size=img_m.get("size", [0, 0]), pdf_bytes=pdf_bytes,
        has_image=pdf_m.get("has_image", False),
        has_table=pdf_m.get("has_table", False),
        # 三要素之一"结论"：imaging 在 story 正文里真实扫描到过结论文本
        has_conclusion=pdf_m.get("conclusion", False),
        font_ok=pdf_m.get("font_ok", False),
        layout_ok=pdf_m.get("layout_ok", False),
        pages=pdf_m.get("pages", 0),
        font_levels=len(pdf_m.get("font_sizes") or []),
        margins_mm=pdf_m.get("margins_mm"),
        aligns=pdf_m.get("aligns"),
        gates=tiers.gates_from(cfg.tier_gates()))
    img_line = ("标注图 marked_defect.png: %d 字节，尺寸 %s｜%s" % (
        img_bytes, "×".join(str(x) for x in img_m.get("size", [])), img_note)
        if img_path else "标注图 marked_defect.png: MISS（%s）" % img_note)
    pdf_line = ("PDF report.pdf: %d 字节 / %d 页｜%s" % (
        pdf_bytes, pdf_m.get("pages", 0), pdf_note) if pdf_path
        else "PDF report.pdf: MISS（%s）" % pdf_note)
    input_line = ("产线 %d 条｜合格率=合格/产出｜达成率=产出/计划｜"
                  "缺陷标注 %d 处（坐标由 config 给定）"
                  % (len(rows), len(defects)))
    layout_line = ("三要素回读: 图%s/表%s/结论%s｜字号 %s｜边距(mm) %s｜对齐 %s"
                   % ("✓" if pdf_m.get("has_image") else "MISS",
                      "✓" if pdf_m.get("has_table") else "MISS",
                      "✓" if pdf_m.get("conclusion") else "MISS",
                      pdf_m.get("font_sizes", []),
                      pdf_m.get("margins_mm", {}),
                      "、".join(pdf_m.get("aligns") or []) or "MISS"))
    sections = [
        ("输入口径", [input_line]),
        ("日报主表", txt_lines),
        ("图文产物（磁盘实测）", [img_line, pdf_line, layout_line]),
        ("编码规范率（PEP 8 实测）",
         stylecheck.format_section(style, 90.0)),
        ("验收档位判定（实测）", tiers.render_lines(result["tiers"])),
        ("结论与建议", conclusion + [
            "坏数据不进结果集；报告三要素（图/表/结论）以 PDF 实测为准"]),
    ]
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir):
    """兼容旧入口：返回报告段（cli 用）。"""
    sections, _ = build(cfg, out_dir)
    return sections
