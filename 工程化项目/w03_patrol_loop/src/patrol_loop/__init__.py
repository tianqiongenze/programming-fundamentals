# -*- coding: utf-8 -*-
"""多设备巡检循环模拟 —— 工程化实现包。

分层：config（配置）/ core（纯逻辑）/ io_utils（IO）/ report（报告）/
pipeline（编排）/ measure（工单门槛实测）/ tiers（工单四档判定，纯函数）。
"""
__version__ = "1.1.0"
__all__ = ["config", "core", "io_utils", "report", "pipeline",
           "measure", "stylecheck", "tiers"]
