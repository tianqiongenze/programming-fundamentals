# -*- coding: utf-8 -*-
"""设备对象：数据与行为一体 + 状态机 + 业务规则校验。"""
from dataclasses import dataclass, field


class DeviceError(Exception):
    """设备操作错误基类。"""


class AlreadyRunningError(DeviceError):
    """设备已在运行，禁止重复启动。"""


class NotRunningError(DeviceError):
    """设备未运行，禁止执行仅运行态可做的操作。"""


@dataclass
class Device:
    """设备聚合根：私有状态 + 只读属性 + 行为方法。"""
    code: str
    kind: str
    temp: float = 0.0
    _running: bool = field(default=False, repr=False)

    @property
    def running(self):
        """只读运行状态——禁止外部直接改写。"""
        return self._running

    def start(self):
        """启动：运行态重复启动属误操作，抛 AlreadyRunningError。"""
        if self._running:
            raise AlreadyRunningError("%s 已在运行，请勿重复启动" % self.code)
        self._running = True
        return "%s %s 启动成功" % (self.code, self.kind)

    def stop(self):
        """停机：未运行却停机，抛 NotRunningError。"""
        if not self._running:
            raise NotRunningError("%s 未运行，无需停机" % self.code)
        self._running = False
        return "%s %s 已停止" % (self.code, self.kind)

    def patrol(self, warn, danger):
        """巡检：状态 + 温度 + 告警级。"""
        lv = "DANGER" if self.temp >= danger else ("WARN" if self.temp >= warn else "NORMAL")
        return "%s %-8s %-6s %.1f℃ [%s]" % (
            self.code, self.kind, "运行" if self._running else "停止", self.temp, lv)
