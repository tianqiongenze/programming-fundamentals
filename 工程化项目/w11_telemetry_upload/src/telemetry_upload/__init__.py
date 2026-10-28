# -*- coding: utf-8 -*-
"""虚拟设备采数与云端上报 —— 工程化实现包。

分层：config（配置）/ core（纯逻辑）/ live（真实通道）/ services（本地真实
服务面：mini broker 子进程 + pymodbus 从站）/ io_utils（IO）/ report（报告）/
tiers（档位判定）/ stylecheck（规范体检）/ pipeline（编排）。
"""
__version__ = "1.0.0"
__all__ = ["config", "core", "io_utils", "live", "report", "services",
           "stylecheck", "tiers", "pipeline"]
