# -*- coding: utf-8 -*-
"""报告生成模块（工单 Z 必备项④）：report.txt + PDF 图文 + 词云 PNG。

为什么要三条产物：文本报告是过程证据，PDF 是交付物（答辩要交的），
词云是"图文"里的那张图——缺任何一条，工单 checklist 就有一项打不了勾。
中文字体按候选链找（课程包 fonts/ZH_Font.ttf > 环境变量 > reportlab 内置
CID 字体 STSong-Light）；装了 wordcloud/PIL 才画词云，缺就如实记 MISS，
绝不写一个"看起来像"的空文件糊弄验收。
"""
import logging
import os

from . import io_utils, report as R

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
COURSE = os.path.normpath(os.path.join(PROJ, "..", ".."))
_FONT_NAMES = ("ZH_Font.ttf", "NotoSansSC-Regular.otf", "simhei.ttf")


def font_candidates():
    """中文字体候选：环境变量 > 课程包 fonts/ > 项目内 fonts/。"""
    out = [os.environ.get("AI_COURSE_FONT")]
    for base in (os.path.join(COURSE, "fonts"), os.path.join(PROJ, "fonts")):
        for name in _FONT_NAMES:
            out.append(os.path.join(base, name))
    return [os.path.normpath(p) for p in out if p]


def find_font():
    for p in font_candidates():
        if os.path.exists(p):
            return p
    return None


class Reporter:
    """交付物生成器：每个方法返回 (路径, 说明)，失败返回 (None, 原因)。"""

    def __init__(self, out_dir, log=None):
        self.out_dir = out_dir
        self.log = log or logging.getLogger("capstone.reporter")
        io_utils.ensure_dir(out_dir)
        self.produced = []

    def text(self, sections, name="report.txt"):
        path = os.path.join(self.out_dir, name)
        R.save(sections, path)
        self.produced.append((name, path, "文本报告"))
        self.log.info("文本报告已落盘：%s", path)
        return path, "reportlab 之外的兜底产物，始终生成"

    def wordcloud(self, words, name="keyword_cloud.png"):
        """词云（工单"可视化"项）：缺库/缺字体就不假装成功。"""
        path = os.path.join(self.out_dir, name)
        try:
            from wordcloud import WordCloud
            from PIL import Image                     # noqa: F401 校验依赖
        except ImportError as exc:
            self.log.warning("词云 MISS：%s", exc)
            return None, "未安装 wordcloud/Pillow，词云项记为缺失"
        if not words:
            return None, "无关键词可画（故障文本为空）"
        font = find_font()
        wc = WordCloud(width=800, height=400, background_color="white",
                       font_path=font, max_words=40, random_state=7)
        freq = {}
        for w, c in words:
            freq[str(w)] = int(c)
        wc.generate_from_frequencies(freq)
        wc.to_image().save(path)
        self.produced.append((name, path, "关键词词云"))
        self.log.info("词云已生成：%s（字体=%s）", path, font or "内置默认")
        return path, "wordcloud + Pillow 真实渲染"

    def pdf(self, sections, title, image=None, name="deliverable.pdf"):
        """PDF 图文报告：reportlab 真实排版，中文靠字体候选链。"""
        path = os.path.join(self.out_dir, name)
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, \
                ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate,
                                            Spacer)
        except ImportError as exc:
            self.log.warning("PDF MISS：%s", exc)
            return None, "未安装 reportlab，PDF 交付项记为缺失"
        font = find_font()
        font_name = "Helvetica"
        if font:
            pdfmetrics.registerFont(TTFont("ZH", font))
            font_name = "ZH"
        else:
            try:                                # reportlab 自带中文 CID 字体
                from reportlab.pdfbase.cidfonts import UnicodeCIDFont
                pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
                font_name = "STSong-Light"
            except Exception as exc:             # noqa: BLE001 环境差异兜底
                self.log.warning("中文 CID 字体不可用：%s", exc)
        if font_name == "Helvetica":
            self.log.warning("未找到中文字体，PDF 中文可能显示为方块")
        styles = getSampleStyleSheet()
        body = ParagraphStyle("zh", parent=styles["Normal"],
                              fontName=font_name, fontSize=9.5,
                              leading=14)
        head = ParagraphStyle("zhh", parent=styles["Heading2"],
                              fontName=font_name, fontSize=13, leading=18)
        story = [Paragraph(title, head), Spacer(1, 4 * mm)]
        for sec, lines in sections:
            story.append(Paragraph(sec, head))
            for ln in lines:
                story.append(Paragraph(str(ln), body))
            story.append(Spacer(1, 3 * mm))
        if image and os.path.exists(image):
            story.append(Paragraph("附图：关键词词云", head))
            w = 160 * mm
            story.append(Image(image, width=w, height=w * 0.5))
        SimpleDocTemplate(path, pagesize=A4,
                          leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=18 * mm, bottomMargin=18 * mm).build(story)
        self.produced.append((name, path, "PDF 图文交付"))
        self.log.info("PDF 已生成：%s（字体=%s，附图=%s）", path, font_name,
                      "有" if image and os.path.exists(image) else "无")
        return path, "reportlab + %s 真实排版" % font_name

    def checklist(self, items):
        """把交付物清单渲染成报告段（工单 checklist 逐项打勾，含缺失项）。"""
        lines = []
        for label, path, note in items:
            ok = bool(path) and os.path.exists(path)
            size = os.path.getsize(path) if ok else 0
            lines.append("%s %s ｜ %s ｜ %s"
                         % ("[✓]" if ok else "[✗]", label,
                            os.path.basename(path) if path else "-",
                            "%s（%d 字节）" % (note, size) if ok else note))
        return lines
