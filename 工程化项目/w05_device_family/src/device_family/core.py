# -*- coding: utf-8 -*-
"""设备家族：抽象基类 + 子类扩展 + 工厂方法（多态统一调度）。"""
from abc import ABC, abstractmethod


class Device(ABC):
    """设备抽象基类：定义统一接口 dispatch()。"""

    def __init__(self, code, temp):
        self.code = code
        self.temp = temp

    @abstractmethod
    def dispatch(self, warn, danger):
        """统一调度接口——子类必须实现。"""


class PumpDevice(Device):
    """泵：额外支持变频设定。"""

    def __init__(self, code, temp, freq_hz=50.0):
        super().__init__(code, temp)
        self.freq_hz = float(freq_hz)

    def set_freq(self, hz):
        """设定变频（超范围抛错，防止损坏电机）。"""
        if not (25.0 <= hz <= 60.0):
            raise ValueError("频率 %.1fHz 超出安全区间 25~60Hz" % hz)
        self.freq_hz = float(hz)
        return "%s 频率设定 %.1fHz" % (self.code, self.freq_hz)

    def dispatch(self, warn, danger):
        lv = "DANGER" if self.temp >= danger else ("WARN" if self.temp >= warn else "NORMAL")
        return "%s 泵 %.1fHz 巡检[%s]" % (self.code, self.freq_hz, lv)


class FanDevice(Device):
    """风机：额外支持延时停机（避免水锤）。"""

    def __init__(self, code, temp, delay_s=3):
        super().__init__(code, temp)
        self.delay_s = int(delay_s)

    def delay_stop(self):
        return "%s 风机将延时 %ds 停机（防喘振）" % (self.code, self.delay_s)

    def dispatch(self, warn, danger):
        lv = "DANGER" if self.temp >= danger else ("WARN" if self.temp >= warn else "NORMAL")
        return "%s 风机 延时%ds 巡检[%s]" % (self.code, self.delay_s, lv)


def from_dict(d):
    """工厂：依 type 字段分派到具体子类。"""
    t = str(d.get("type", "")).lower()
    if t == "pump":
        return PumpDevice(str(d["code"]), float(d["temp"]), d.get("freq_hz", 50))
    if t == "fan":
        return FanDevice(str(d["code"]), float(d["temp"]), d.get("delay_s", 3))
    raise ValueError("未知设备类型: %s" % t)
