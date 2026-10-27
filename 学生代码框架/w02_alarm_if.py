# -*- coding: utf-8 -*-
"""W02 工业实时告警系统Ⅰ —— 条件判断
边界测试五组: 79.9 / 80 / 94.9 / 95 / 100
"""

# 告警阈值(勿改)
TEMP_WARN, TEMP_DANGER = 80.0, 95.0
PRESS_WARN = 0.8


def alarm(level, msg):
    """TODO-1 告警函数: 按级别输出
    level 1=提示 2=警告 3=停机, 格式: [级别] HH:MM:SS msg"""
    # === 你的代码 ===
    pass


def check(temp, press):
    """TODO-2 判断逻辑(本工单核心):
    temp≥95 或 press≥PRESS_WARN*1.2 → 3级停机
    temp≥80 或 press≥PRESS_WARN    → 2级警告
    其他 → 1级提示"运行正常"
    注意判断顺序: 先判危险再判警告!"""
    # === 你的代码 ===
    pass


if __name__ == "__main__":
    # TODO-3: 用五组边界值循环调用check, 打印对照表
    for t in [79.9, 80, 94.9, 95, 100]:
        check(t, 0.5)
    # TODO-4(优秀): 温度与压力同时超限 → 升级"紧急"
