# -*- coding: utf-8 -*-
"""工单 W11 四档验收判定（纯函数，档位是算出来的、不是自称的）。

判据逐字对齐《W11工单-工业互联网数据采集系统.md》验收标准表：
  D 及格：Modbus 读取成功 + MQTT 发布成功（实跑非模拟）；规范率≥80%
  C 良好：5 轮采集完整；JSON 结构规范（id/ts/metrics）
  B 优秀：断线重连；异常日志清晰；规范率≥90%
  A 优：达 B 且订阅回环验证（订阅自己主题打印回执，载荷逐字节核对）
输入全部来自 pipeline 实测（真实协议栈连接/发布计数、run.log 反读、
断线重连尝试次数、回环回执条数），verdict 只做比较，不产生新数据。
"""

TIERS = [
    ("及格(D)", "Modbus 读取成功 + MQTT 发布成功（真实 TCP 协议栈）", 80.0),
    ("良好(C)", "5 轮采集完整；JSON 结构规范（id/ts/metrics）", 85.0),
    ("优秀(B)", "断线重连实测（尝试≥2 次且重连成功）；异常日志清晰", 90.0),
    ("优(A)", "达 B 且订阅回环收到回执（载荷逐字节一致并打印）", 90.0),
]

KEYS = ("D", "C", "B", "A")
#: 工单里机器测不了、必须答辩/现场核对的项——如实列出，不代答也不隐瞒
manual = [
    "采集/上报运行日志截图归档提交（工单提交物）",
    "寄存器地址与工程值换算口径和现场 PLC 核对（答辩）",
]


def gates_from(value):
    """rules.yaml 的 tiers: 段 → {档位字母: 门槛}；非法项过滤，不谎报门槛。"""
    out = {}
    if isinstance(value, dict):
        for key in KEYS:
            try:
                out[key] = float(value[key])
            except (KeyError, TypeError, ValueError):
                continue
    return out


def verdict(rate, rows_ok, sent_all, modbus_real, mqtt_real,
            rounds_done, rounds_need, json_ok,
            reconnect_attempts, log_error_count, loopback_ok, gates=None,
            loopback_receipts=0):
    """输入全是本次运行实测值；返回 {tiers, claimed, measured}。

    gates: 外置门槛（config.py tier_gates 读出）；缺项回落 TIERS 内置默认。
    """
    rate = float(rate)
    g = {k: t[2] for k, t in zip(KEYS, TIERS)}
    g.update(gates or {})
    measured = {
        "rate": round(rate, 1),
        "rows_ok": bool(rows_ok),
        "sent_all": bool(sent_all),
        "modbus_real": bool(modbus_real),
        "mqtt_real": bool(mqtt_real),
        "rounds_done": int(rounds_done),
        "rounds_need": int(rounds_need),
        "json_ok": bool(json_ok),
        "reconnect_attempts": int(reconnect_attempts),
        "log_error_count": int(log_error_count),
        "loopback_ok": bool(loopback_ok),
        "loopback_receipts": int(loopback_receipts),
    }
    funcs = {
        "D": bool(rows_ok and sent_all and modbus_real and mqtt_real),
        "C": bool(1 <= rounds_need <= rounds_done and json_ok),
        "B": bool(reconnect_attempts >= 2 and log_error_count >= 1),
    }
    funcs["A"] = bool(funcs["B"] and loopback_ok)
    rows = []
    claimed = "未达 D 档"
    for (name, need, _default_gate), key in zip(TIERS, KEYS):
        gate = g[key]
        ok = bool(funcs[key] and rate >= gate)
        rows.append({"tier": name, "gate": gate, "need": need,
                     "functional": funcs[key], "style_ok": rate >= gate,
                     "pass": ok})
        if ok:
            claimed = name
    return {"tiers": rows, "claimed": claimed, "measured": measured}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    lines = ["实测达成档位: %s ｜ 采集 %d/%d 轮｜JSON %s ｜ Modbus %s ｜ "
             "MQTT %s ｜ 重连尝试 %d 次｜ERROR 日志 %d 条｜回环回执 %d 条"
             % (v["claimed"], m["rounds_done"], m["rounds_need"],
                "规范" if m["json_ok"] else "MISS",
                "实跑成功" if m["modbus_real"] else "未达标(无服务端)",
                "实跑成功" if m["mqtt_real"] else "未达标(无broker)",
                m["reconnect_attempts"], m["log_error_count"],
                m["loopback_receipts"])]
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("  （人工答辩项，机器不代判）%s" % "；".join(manual))
    return lines
