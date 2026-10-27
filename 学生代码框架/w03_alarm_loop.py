# -*- coding: utf-8 -*-
"""W03 工业实时告警系统Ⅱ —— 循环与函数(完整版)
模拟3台设备×10周期连续监测, 汇总告警统计。
"""
import random

random.seed(42)   # 固定随机种子: 结果可复现

# TODO-1: 用列表+字典组织3台设备 (提示: 每台含id/name/base_temp)
# devices = [...]

# 告警统计(字典: 设备id -> 各级别次数)
stats = {}


def check_device(dev, temp):
    """TODO-2 判断级别: ≥95→3 / ≥80→2 / 其他→0(正常)
    返回级别数字(0-3)"""
    # === 你的代码 ===
    return 0


def alarm(dev, level, temp):
    """TODO-3 输出告警并累计到stats (格式自定, 要含设备id与温度)"""
    # === 你的代码 ===
    pass


if __name__ == "__main__":
    # TODO-4: 双层循环 3设备×10周期
    # 每周期温度 = base_temp + random.uniform(-8, 15) (制造偶发超限)
    # 调用check_device→alarm
    # TODO-5: 循环结束输出《告警统计报告》: 每设备各级别次数
    pass
