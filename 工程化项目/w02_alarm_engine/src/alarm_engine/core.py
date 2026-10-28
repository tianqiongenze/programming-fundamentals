# -*- coding: utf-8 -*-
"""告警引擎：单点分级、组合判定、嵌套三级、边界用例表、多设备循环（纯函数）。

工单 W02 对照：
  任务1「≥2 个 if 条件判断（温度 80/95℃、压力 0.8MPa）」→ temp_level / press_level
  任务2「设计 ≥1 个告警函数 def alarm(level, msg)」  → alarm()（签名逐字一致）
  任务3「边界测试 79.9/80/94.9/95/100 五组全覆盖」→ boundary_table()
  任务4「温度与压力同时超限 → 升级紧急」              → judge() 的 emergency 分支
  优秀(B)「多条件嵌套：提示/警告/停机三级」            → nested_level()
  优(A)  「循环测试 3 台设备」                        → sweep()
"""

LEVEL_TEXT = {
    "normal": ("正常", "无需处理"),
    "notice": ("提示", "记入观察本，班后复核"),
    "warn": ("警告", "喊人加密监测"),
    "warning": ("警告", "喊人加密监测"),
    "danger": ("停机", "通知班长自动断电"),
    "stop": ("停机", "通知班长自动断电"),
    "emergency": ("紧急", "立即停机并上报值长"),
}


def alarm(level, msg):
    """工单指定签名：按级别加前缀并给出响应动作（未知级别也不崩）。"""
    name, action = LEVEL_TEXT.get(str(level).lower(), ("未知级别", "先核对级别字典"))
    return "[%s] %s ｜响应: %s" % (name, msg, action)


def temp_level(temp, warn, danger):
    """温度分级：>=danger 停机 / >=warn 预警 / 正常（两道 if，工单任务1）。"""
    if temp >= danger:
        return "danger"
    if temp >= warn:
        return "warn"
    return "normal"


def press_level(press, warn, danger):
    """压力分级：同上，阈值独立（工单任务1 的压力 0.8MPa 由 limit 参数表达）。"""
    if press >= danger:
        return "danger"
    if press >= warn:
        return "warn"
    return "normal"


def judge(temp, press, temp_w, temp_d, press_w, press_d):
    """组合判定：温度与压力同时越预警线 → emergency（工单任务4 的逻辑组合）。"""
    tl, pl = temp_level(temp, temp_w, temp_d), press_level(press, press_w, press_d)
    both_warn = (tl != "normal") and (pl != "normal")
    if both_warn:
        return "emergency"
    return max(tl, pl, key=lambda x: ["normal", "warn", "danger"].index(x))


def nested_level(temp, press, temp_w, temp_d, press_w, press_d, press_limit):
    """B 档：多条件嵌套给出「提示/警告/停机」三级（if 里套 if，先粗筛再细筛）。

    外层按温度粗筛（停机线先判——顺序即优先级，写反了危险分支永远到不了），
    内层用压力细筛：压力到 0.8MPa 硬上限（≥press_d，含在内）即升级为紧急。
    """
    if temp >= temp_d:                          # 粗筛①：温度已破停机线
        if press >= press_d or press >= press_limit:
            return "emergency"                  # 工单任务4：温压同时超限 → 紧急
        return "stop"
    if temp >= temp_w:                          # 粗筛②：温度在预警带
        if press >= press_limit:
            return "emergency"
        if press >= press_d:
            return "stop"
        return "warning"
    if press >= press_limit:                    # 粗筛③：温度正常，压力独立越限
        return "stop"
    if press >= press_d:
        return "warning"
    if press >= press_w:
        return "notice"
    return "normal"


def boundary_table(temp_values, press_values, cfg):
    """边界用例表：温度五组 × 压力五组，逐行给出分级与告警文本（C 档）。"""
    rows = []
    for t in temp_values:
        rows.append({"kind": "temp", "value": float(t),
                     "level": temp_level(float(t), cfg.warn, cfg.danger),
                     "text": alarm(temp_level(float(t), cfg.warn, cfg.danger),
                                   "温度 %.1f℃ 边界实测" % float(t))})
    for p in press_values:
        lv = press_level(float(p), float(cfg.get("press_warn", 0.55)),
                         float(cfg.get("press_danger", 0.65)))
        rows.append({"kind": "press", "value": float(p), "level": lv,
                     "text": alarm(lv, "压力 %.2fMPa 边界实测" % float(p))})
    return rows


def sweep(devices, cfg):
    """A 档：循环测试 ≥3 台设备——每台都跑嵌套分级 + 告警函数。"""
    out = []
    for d in devices:
        temp, press = float(d["temp"]), float(d["press"])
        lv = nested_level(temp, press, cfg.warn, cfg.danger,
                          float(cfg.get("press_warn", 0.55)),
                          float(cfg.get("press_danger", 0.65)),
                          float(cfg.get("press_limit", 0.8)))
        out.append({"code": str(d["code"]), "temp": temp, "press": press,
                    "level": lv,
                    "text": alarm(lv, "%s 温度 %.1f℃ / 压力 %.2fMPa"
                                  % (d["code"], temp, press))})
    return out


def dedup(events, window):
    """同等级告警在 window 秒内只保留首条（时间窗去重，防刷屏）。"""
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
