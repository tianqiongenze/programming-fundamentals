# -*- coding: utf-8 -*-
"""多设备×多周期巡检：函数封装（check_device / alarm）与统计（纯逻辑 + random）。

工单 W03 对照：
  任务1「列表+字典组织 ≥3 台设备参数」 → rules.yaml 的 devices（list of dict）
  任务2「for 遍历设备 × for 模拟 10 个周期，温度随机波动 random.uniform」→ patrol()
  任务3「封装 ≥2 个函数：check_device(d) 判级 + alarm(level, msg) 输出」→ 同名函数
  任务4「统计报告：各设备告警次数汇总」→ summarize()
  任务5「防死循环：while 版本必须写退出条件（选做）」→ patrol_while()
  良好(C)「无死循环风险」→ while 版三重退出条件，报告实测真实轮数
  优秀(B)「每个函数 ≤15 行、职责单一」→ measure.py 用 AST 实测函数体行数
"""
import random

LEVEL_NAME = {"normal": "正常", "warn": "警告", "danger": "停机",
              "emergency": "紧急"}
DEFAULT_WARN, DEFAULT_DANGER = 80.0, 95.0
DEFAULT_PRESS_DANGER = 0.65


def alarm(level, msg):
    """输出层：级别 → 带前缀的一行文本（W02 的 alarm(level,msg) 沿用，职责单一）。"""
    return "[%s] %s" % (LEVEL_NAME.get(level, "未知"), msg)


def check_device(d, warn=None, danger=None):
    """判级层：一台设备（dict）→ 级别字符串。不做输出、不改数据（职责单一）。

    阈值优先级：显式入参 > 设备自带 d["warn"]/d["danger"] > 模块默认。
    这样"同类同阈值、异类各自一套"都能在 rules.yaml 里配出来（W02 B04）。
    """
    temp = float(d.get("temp", 0.0))
    press = float(d.get("press", 0.0))
    w = float(d.get("warn", DEFAULT_WARN if warn is None else warn))
    dg = float(d.get("danger", DEFAULT_DANGER if danger is None else danger))
    hard = float(d.get("press_danger", DEFAULT_PRESS_DANGER))
    if temp >= dg:
        return "emergency" if press >= hard else "danger"
    if temp >= w:
        return "danger" if press >= hard else "warn"
    return "normal"


def jitter(rng, base, drift, cycle):
    """单个周期的温度样本：基线 + 线性漂移 + random.uniform 波动（工单任务2）。"""
    return round(base + drift * cycle + rng.uniform(-0.8, 0.8), 1)


def count_alarms(levels):
    """告警计数：级别序列 → 各级次数 dict（工单任务4 统计报告的原子）。"""
    stat = {k: 0 for k in ("normal", "warn", "danger", "emergency")}
    for lv in levels:
        stat[lv] = stat.get(lv, 0) + 1
    return stat


def _stat_one(dev, bundle, cycles, mode):
    """把一台设备的判级序列折算成统计条目（for 版与 while 版共用）。"""
    c = count_alarms(bundle["levels"])
    alarms = c["warn"] + c["danger"] + c["emergency"]
    return {"code": dev["code"], "temps": bundle["temps"],
            "levels": bundle["levels"], "cycles": cycles,
            "mode": mode, "warn": c["warn"], "danger": c["danger"],
            "emergency": c["emergency"], "alarms": alarms,
            "peak": max(bundle["temps"]),
            "exit_reason": bundle.get("exit", "")}


def patrol(devices, n_cycles, seed=0):
    """双层 for：外层设备 × 内层 n_cycles 个周期；每样本走 check_device()。"""
    rng = random.Random(seed)
    stat = {}
    for dev in devices:                          # 外层：设备（列表 + 字典）
        base = float(dev.get("base_temp", 70.0))
        drift = float(dev.get("drift", 2.5))
        press = float(dev.get("press", 0.4))
        temps, levels = [], []
        for cycle in range(n_cycles):             # 内层：10 个监测周期
            sample = jitter(rng, base, drift, cycle)
            temps.append(sample)
            levels.append(check_device(dict(dev, temp=sample, press=press)))
        stat[dev["code"]] = _stat_one(dev, {"temps": temps, "levels": levels},
                                      n_cycles, "for")
    return stat


def _exit_reason(sample, cycle, n_cycles, dg):
    """while 退出判定（B 档实测要求每个函数≤15 行，判定逻辑独立成原子函数）。"""
    if sample >= dg:
        return "触停机线 %.0f℃ 提前退出" % dg
    if cycle >= n_cycles:
        return "跑满 %d 个周期正常退出" % n_cycles
    return ""


def while_one(dev, n_cycles, rng, hard_limit=1000):
    """while 单台巡检：三重退出（触停机线/跑满周期/hard_limit 兜底）杜绝死循环。

    返回 (温度序列, 判级序列, 实跑轮数, 退出原因)，轮数与原因进报告做有界实测。
    """
    base, drift = float(dev.get("base_temp", 70.0)), float(dev.get("drift", 2.5))
    press, dg = float(dev.get("press", 0.4)), float(dev.get("danger", DEFAULT_DANGER))
    temps, levels, cycle, reason = [], [], 0, ""
    while cycle < hard_limit:
        sample = jitter(rng, base, drift, cycle)
        temps.append(sample)
        levels.append(check_device(dict(dev, temp=sample, press=press)))
        cycle += 1
        reason = _exit_reason(sample, cycle, n_cycles, dg)
        if reason:
            break
    return temps, levels, cycle, reason or "触发硬上限 %d 轮兜底退出" % hard_limit


def patrol_while(devices, n_cycles, seed=0, hard_limit=1000):
    """选做：while 版本（工单任务5）——骨架换成 while，判级与统计原样复用。"""
    rng = random.Random(seed)
    stat = {}
    for dev in devices:
        temps, levels, cycle, reason = while_one(dev, n_cycles, rng, hard_limit)
        stat[dev["code"]] = _stat_one(dev, {"temps": temps, "levels": levels,
                                            "exit": reason}, cycle, "while")
    return stat


def summarize(stat):
    """各设备告警次数汇总（工单任务4）。"""
    return [{"code": code, "alarms": s["alarms"], "warn": s["warn"],
             "danger": s["danger"], "emergency": s["emergency"],
             "peak": s["peak"]} for code, s in stat.items()]


def priority(stat):
    """巡检优先级：按告警总数降序（稳定排序）。"""
    return sorted(stat.items(), key=lambda kv: -kv[1]["alarms"])


def series(base, drift, n, rng=None):
    """兼容 W03 之前的旧接口：单台设备 n 周期轨迹。"""
    r = rng or random.Random(0)
    return [jitter(r, base, drift, i) for i in range(n)]
