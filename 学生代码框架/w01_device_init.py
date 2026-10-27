# -*- coding: utf-8 -*-
"""W01 设备参数初始化系统 —— 你的第一个程序!
运行: python W01_device_init.py
"""
import sys

# ============ TODO-1 定义设备参数变量 (≥6个, ≥3种数据类型) ============
device_id = "DEV-2026-001"        # str 字符串: 设备编号
device_name = "智能注塑机"        # str: 设备名称
# === 你的代码: 补充 status(bool) temp(float) press(float) rpm(int) ... ===


def c_to_f(celsius):
    """TODO-2 摄氏度→华氏度: F = C × 9/5 + 32"""
    # === 你的代码 ===
    return 0


def print_card():
    """TODO-3 用f-string输出'设备台账卡'(对齐美观)"""
    # === 你的代码 ===
    print("====== 设备台账卡 ======")


def check_env():
    print("环境OK" if sys.version_info >= (3, 12) else "需要Python3.12+")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check_env()
    else:
        print_card()
        # TODO-4: 调用c_to_f并输出换算结果 (优秀: 再加kPa→MPa)
