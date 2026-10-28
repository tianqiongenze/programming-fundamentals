# -*- coding: utf-8 -*-
"""兼容层：W10 交付物实测实现唯一存放在 imaging.py（避免双实现口径漂移）。

本模块只做转发，不再新增逻辑——改标注/PDF 请只改 imaging.py。
"""
from .imaging import (  # noqa: F401  转发即本模块职责，不做二次实现
    COURSE, IMG_H, IMG_W, annotate, build_pdf, find_font)

MIN_ARTIFACT_BYTES = 1000
