# -*- coding: utf-8 -*-
"""质量日报生成 —— 工程化实现包。

分层：config（配置）/ core（纯逻辑）/ io_utils（IO）/ report（报告）/
pipeline（编排）/ imaging（标注图与 PDF）/ tiers（工单四档判定，纯函数）。
"""
__version__ = "1.0.0"
__all__ = ["config", "core", "io_utils", "report", "pipeline", "imaging",
           "tiers"]
