# -*- coding: utf-8 -*-
"""核心纯函数：单位换算、告警分级、台账卡渲染（零 IO，可单测）。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    """设备值对象（不可变）——代码零硬编码，字段来自 config/rules.yaml。"""
    code: str
    name: str
    temp: float
    press_kpa: float
    rpm: int
    status: str = "running"

    def __post_init__(self):
        if self.temp < -273.15:
            raise ValueError("温度低于绝对零度")
        if self.press_kpa < 0:
            raise ValueError("压力不能为负（%.2f kPa）" % self.press_kpa)
        if self.rpm < 0:
            raise ValueError("转速不能为负")


def c_to_f(c):
    """摄氏度 → 华氏度。"""
    return c * 9.0 / 5.0 + 32.0


def kpa_to_mpa(kpa):
    """千帕 → 兆帕。"""
    return kpa / 1000.0


def level_of(temp, warn, danger):
    """告警分级：>=danger 停机 / >=warn 预警 / 其余正常（边界值取高等级）。"""
    if temp >= danger:
        return "danger"
    if temp >= warn:
        return "warn"
    return "normal"


def card(dev, cfg):
    """渲染设备台账卡（等宽对齐、单位齐全）。"""
    f = c_to_f(dev.temp)
    mpa = kpa_to_mpa(dev.press_kpa)
    lv = level_of(dev.temp, cfg.warn, cfg.danger)
    return [
        "====== 设备台账卡 ======",
        "编号: %s" % dev.code,
        "名称: %-12s 状态: %s" % (dev.name, "运行" if dev.status == "running" else "停止"),
        "温度: %7.1f℃ (%6.1f℉)  压力: %.2fMPa  转速: %drpm" % (dev.temp, f, mpa, dev.rpm),
        "告警级别: %s" % lv.upper(),
    ]
