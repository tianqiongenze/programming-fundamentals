# -*- coding: utf-8 -*-
"""告警引擎：单点分级、组合判定、超限升级、时间窗去重（纯函数）。"""


def temp_level(temp, warn, danger):
    """温度分级：>=danger 停机 / >=warn 预警 / 正常。"""
    if temp >= danger:
        return "danger"
    if temp >= warn:
        return "warn"
    return "normal"


def press_level(press, warn, danger):
    if press >= danger:
        return "danger"
    if press >= warn:
        return "warn"
    return "normal"


def judge(temp, press, temp_w, temp_d, press_w, press_d):
    """组合判定：温度或压力任一达 danger → danger；双 warn 以下；同时超限 → emergency。"""
    tl, pl = temp_level(temp, temp_w, temp_d), press_level(press, press_w, press_d)
    both_warn = (tl != "normal") and (pl != "normal")
    if both_warn:
        return "emergency"
    return max(tl, pl, key=lambda x: ["normal", "warn", "danger"].index(x))


def dedup(events, window):
    """同等级告警在 window 秒内只保留首条（时间窗去重）。"""
    kept, last_ts = [], {}
    for e in events:
        key = e["level"]
        if key in last_ts and (e["ts"] - last_ts[key]) < window:
            e = dict(e, suppressed=True)
        else:
            last_ts[key] = e["ts"]
            e = dict(e, suppressed=False)
        kept.append(e)
    return kept
