# -*- coding: utf-8 -*-
"""W05 工业设备继承体系 —— 继承与多态
基类Device沿用W04, 新增PLC/变频器子类。
"""


class Device:
    """通用设备基类"""

    def __init__(self, dev_id, name):
        self.dev_id = dev_id
        self.name = name
        self.status = "停止"

    def start(self):
        self.status = "运行"
        print(f"{self.name} 已启动")

    def stop(self):
        self.status = "停止"
        print(f"{self.name} 已停止")

    def report(self):
        return f"{self.dev_id} {self.name}: {self.status}"


# TODO-1 PLC子类: 新增属性scan_ms(扫描周期), 覆盖start()输出含扫描周期信息
class PLC(Device):
    """TODO: __init__用super()调用父类, 再加scan_ms"""

    # === 你的代码 ===
    pass


# TODO-2 变频器子类: 新增方法set_freq(f)(限制0-50Hz, 超范围提示)
class VFD(Device):
    pass


# TODO-3 传感器子类(优秀): 新增calibrate()校准方法


if __name__ == "__main__":
    devices = [PLC("DEV-01", "西门子S7-1200"), VFD("DEV-02", "ABB变频器"),
               Device("DEV-03", "温度变送器")]
    # TODO-4 多态演示: 循环调用start()与report(), 观察不同子类行为
    # for d in devices: d.start(); print(d.report())
    # TODO-5: docstring齐全(每个类+方法一行)
