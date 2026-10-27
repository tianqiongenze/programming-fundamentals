# -*- coding: utf-8 -*-
"""多层循环巡检：温度轨迹生成与告警统计（纯函数）。"""
import random


def series(base, drift, n, rng=None):
    """生成 n 个周期的温度轨迹：基线 + 确定性漂移 + 固定种子噪声。"""
    r = rng or random.Random(0)
    return [round(base + drift * i + r.uniform(-0.8, 0.8), 1) for i in range(n)]


def count_alarms(temps, warn, danger):
    """分级计数：返回 (warn_count, danger_count)。"""
    w = sum(1 for t in temps if warn <= t < danger)
    d = sum(1 for t in temps if t >= danger)
    return w, d


def priority(stat):
    """巡检优先级：按告警总数降序（稳定排序）。"""
    return sorted(stat.items(), key=lambda kv: -(kv[1]["warn"] + kv[1]["danger"]))


def patrol(devices, n_cycles, base, drift, warn, danger, seed=0):
    """双层循环：外层设备 × 内周期，返回统计 dict。"""
    r = random.Random(seed)
    stat = {}
    for dev in devices:
        temps = series(base, drift, n_cycles, r)
        w, d = count_alarms(temps, warn, danger)
        stat[dev] = {"temps": temps, "warn": w, "danger": d}
    return stat
