# -*- coding: utf-8 -*-
# [教学脚手架] 下列导入/变量供 TODO 完成后使用，故标注 noqa 而非删除
"""W10 工业图像处理与报告生成 —— Pillow标注 + reportlab PDF"""
import os

from PIL import Image, ImageDraw  # noqa: F401
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image as RLImage, Paragraph, SimpleDocTemplate,  # noqa: F401
                                Spacer, Table, TableStyle)
from reportlab.lib.styles import getSampleStyleSheet

import os as _os
FONT = next((f"fonts/{n}" for n in ("ZH_Font.ttf", "SimHei.ttf")
            if _os.path.exists(f"fonts/{n}")), "SimHei.ttf")
pdfmetrics.registerFont(TTFont("ZH", FONT))          # 中文字体注册(勿删)
pdfmetrics.registerFont(TTFont("SimHei", FONT))

# 缺陷信息: (x, y, w, h, 说明)
DEFECTS = [(120, 80, 90, 40, "划痕 9.0mm"), (220, 150, 45, 45, "凹坑 4.5mm²")]


def make_marked_image(src, dst):
    """TODO-1: 打开src→缩放到400×300→红框+文字标注DEFECTS→存dst
    提示: draw.rectangle([x,y,x+w,y+h], outline=(255,0,0), width=3)
          draw.text((x, y-14), 说明, fill=(255,0,0))"""
    # === 你的代码 ===
    return dst


def build_pdf(img_path):
    """TODO-2: 生成PDF日报(标题+结论段+标注图+统计表)"""
    doc = SimpleDocTemplate("质量日报.pdf", pagesize=A4,  # noqa: F841
                            leftMargin=20 * mm, rightMargin=20 * mm)
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "SimHei"
    # 提示: Paragraph的样式也要 setAttribute fontName='SimHei'
    # TODO-2a 标题: 《设备质量日报》+日期
    # TODO-2b 结论段落(2-3句)
    # TODO-2c RLImage(img_path, width=120*mm, height=90*mm)
    # TODO-2d Table: 缺陷/尺寸/判定 三列×2行, TableStyle含GRID
    # doc.build([...])


if __name__ == "__main__":
    img = make_marked_image("sample_device.png", "marked.png") \
        if os.path.exists("sample_device.png") else None
    build_pdf(img or "marked.png")
    print("已生成 质量日报.pdf")
