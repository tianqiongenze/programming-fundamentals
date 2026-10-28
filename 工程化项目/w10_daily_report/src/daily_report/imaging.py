# -*- coding: utf-8 -*-
"""设备图标注（Pillow）与图文 PDF（reportlab）——工单 W10 的"图像+报告"实测项。

与 w09 visuals 同一原则：缺库/缺字体如实返回 MISS 与原因，不写假产物；
PDF 页数、图片内嵌、字体注册全部在落盘后用磁盘字节/pypdf 实测。
"""
import os

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
#: 课程包根（工程化项目/w10_daily_report → 02-程序设计基础）
COURSE = os.path.normpath(os.path.join(PROJ, "..", ".."))
_FONT_NAMES = ("ZH_Font.ttf", "NotoSansSC-Regular.otf", "simhei.ttf")
IMG_W, IMG_H = 400, 300


def find_font():
    """中文字体候选：环境变量 > 课程包 fonts/ > 项目内 fonts/。"""
    out = [os.environ.get("AI_COURSE_FONT")]
    for base in (os.path.join(COURSE, "fonts"), os.path.join(PROJ, "fonts")):
        for name in _FONT_NAMES:
            out.append(os.path.join(base, name))
    return next((os.path.normpath(p) for p in out
                 if p and os.path.exists(p)), None)


def annotate(defects, out_dir, name="marked_defect.png", width=None,
             height=None):
    """生成标注图（默认 400×300）并按给定坐标画红框+文字标注（工单要求①②）。

    defects: [{"name","x","y","w","h"}...]，坐标与尺寸由 config 给定。
    返回 (路径|None, 说明, 实测 dict: 字节数/尺寸/标注数)。
    """
    img_w = int(width or IMG_W)
    img_h = int(height or IMG_H)
    path = os.path.join(out_dir, name)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        return None, "未安装 Pillow: %s" % exc, {}
    img = Image.new("RGB", (img_w, img_h), (235, 236, 230))
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 8, img_w - 8, img_h - 8], outline=(90, 90, 110))
    font = find_font()
    try:
        label_font = (ImageFont.truetype(font, 14) if font
                      else ImageFont.load_default())
    except OSError:
        label_font = ImageFont.load_default()
    n = 0
    for d in defects or []:
        x, y = int(d["x"]), int(d["y"])
        w, h = int(d["w"]), int(d["h"])
        draw.rectangle([x, y, x + w, y + h], outline=(220, 30, 30), width=3)
        draw.text((x + 2, max(y - 16, 0)), str(d.get("name", "缺陷%d" % (n + 1))),
                  fill=(220, 30, 30), font=label_font)
        n += 1
    img.save(path)
    from PIL import Image as _I
    with _I.open(path) as back:
        size = back.size
    return path, "Pillow 真实标注（红框 %d 处，字体 %s）" % (
        n, os.path.basename(font) if font else "默认"), {
        "bytes": os.path.getsize(path), "size": list(size), "boxes": n}


def build_pdf(rows, table, title, conclusion, image_path, out_dir,
              name="report.pdf", margin_mm=18):
    """多页 PDF：自绘封面 + 首页概览（结论+标注图+表）+ 次页明细表。

    返回 (路径|None, 说明, 实测 dict)。实测口径：页数用 pypdf（缺失回落
    字节探测）读回；图内嵌用 /Image 字节探测；边距/字号/对齐从构建完成的
    doc 与样式对象回读；"有结论"必须在 story 正文里真的扫描到结论文本——
    排版要素删掉后档位判定会跟着掉，不靠程序自称。
    """
    path = os.path.join(out_dir, name)
    try:
        from reportlab.lib import pagesizes
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (Image, PageBreak, Paragraph,
                                        SimpleDocTemplate, Spacer, Table,
                                        TableStyle)
    except ImportError as exc:
        return None, "未安装 reportlab: %s" % exc, {}
    font = find_font()
    font_name, font_ok = "Helvetica", False
    if font:
        pdfmetrics.registerFont(TTFont("ZH", font))
        font_name, font_ok = "ZH", True
    else:
        try:
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            font_name, font_ok = "STSong-Light", True
        except Exception:
            font_ok = False
    styles = getSampleStyleSheet()
    body = ParagraphStyle("zh", parent=styles["Normal"], fontName=font_name,
                          fontSize=9.5, leading=14)
    head = ParagraphStyle("zhh", parent=styles["Heading1"],
                          fontName=font_name, fontSize=16, leading=22)
    # 封面大标题（第三级字号——B 档"字号层级≥3 级"实测来源之一）
    cover = ParagraphStyle("zhc", parent=head, fontSize=24, leading=30,
                           alignment=1)
    margin = margin_mm * mm
    story = []
    story.append(Spacer(1, 90))
    story.append(Paragraph(title, cover))
    story.append(Paragraph("两江智造集团 · 工业质量部（自动签发）", body))
    story.append(PageBreak())
    story.append(Paragraph("首页概览", head))
    for line in conclusion:
        story.append(Paragraph(line, body))
    story.append(Spacer(1, 6))
    has_image = False
    if image_path and os.path.exists(image_path):
        w = 120 * mm
        story.append(Image(image_path, width=w, height=w * 0.75))
        story.append(Paragraph("附图：设备缺陷标注图（红框为缺陷区域）", body))
        has_image = True
    story.append(Spacer(1, 8))
    tbl = Table(table)
    # 表内中文必须用已注册字体，否则 PDF 里是方块（工单避坑：字体链路一致）
    tbl.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font_name),
                             ("FONTSIZE", (0, 0), (-1, -1), body.fontSize)]))
    tbl.hAlign = "CENTER"
    story.append(tbl)
    story.append(PageBreak())
    story.append(Paragraph("次页明细（产线 × %d）" % len(rows), head))
    detail = [tuple(str(c) for c in r) for r in table]
    story.append(Table(detail, repeatRows=1))
    doc = SimpleDocTemplate(path, pagesize=pagesizes.A4, leftMargin=margin,
                            rightMargin=margin, topMargin=margin,
                            bottomMargin=margin)
    # 三要素"结论"实测：build 前确认结论文本真的在 story 正文流里
    conclusion_in = any(str(getattr(p, "text", "")).startswith("最低合格率")
                        for p in story)
    doc.build(story)
    pages, size = 0, os.path.getsize(path)
    try:
        from pypdf import PdfReader
        pages = len(PdfReader(path).pages)
    except ImportError:
        with open(path, "rb") as f:
            raw = f.read()
        pages = raw.count(b"/Type /Page") - raw.count(b"/Type /Pages")
    with open(path, "rb") as f:
        embedded = f.read().count(b"/Image") > 0
    margins_mm = {k: round(getattr(doc, k) / mm, 2) for k in (
        "leftMargin", "rightMargin", "topMargin", "bottomMargin")}
    layout_ok = bool(margins_mm) and all(0 < v <= 60 for v in
                                         margins_mm.values())
    aligns = [k for k, ok in (("封面标题居中", cover.alignment == 1),
                              ("表格居中", tbl.hAlign == "CENTER")) if ok]
    return path, "reportlab 多页排版（字体 %s，%s）" % (
        font_name, "中文已注册" if font_ok else "缺中文字体"), {
        "bytes": size, "pages": pages, "has_image": embedded and has_image,
        "has_table": True, "conclusion": conclusion_in,
        "font_ok": font_ok, "layout_ok": layout_ok,
        "font_sizes": sorted({cover.fontSize, head.fontSize,
                              body.fontSize}),
        "margins_mm": margins_mm, "aligns": aligns, "font": font_name}
