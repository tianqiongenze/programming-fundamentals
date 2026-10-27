# -*- coding: utf-8 -*-
"""W04 工业设备类设计 —— 类与对象(图纸与产品)"""


class Device:
    """工业设备基类: 属性=铭牌参数, 方法=操作行为"""

    def __init__(self, dev_id, name, temp=25.0):
        """TODO-1 实例属性: id/name/temp/status(初始'停止')"""
        # === 你的代码 ===
        pass

    def start(self):
        """TODO-2 启动: 已启动则提示"请勿重复启动", 否则改状态并输出"""
        # === 你的代码 ===
        pass

    def stop(self):
        """TODO-3 停止(同上逻辑)"""
        pass

    def get_status(self):
        """返回 'id 名称: 状态 温度℃' 的字符串"""
        # === 你的代码 ===
        return ""


if __name__ == "__main__":
    # TODO-4: 创建≥2个对象并演示: 属性访问 / start / stop / get_status
    # d1 = Device("DEV-01", "空压机A")
    # print(d1.get_status()); d1.start(); ...
    # TODO-5(优秀): 实现 __str__ 使 print(d1) 输出可读信息
    pass
