# -*- coding: utf-8 -*-
"""工单 W04 四档验收判定（纯函数，档位是算出来的、不是自称的）。

门槛逐条取自《W04工单-工业设备类设计.md》验收标准：
  及格(D)：1 类 + 2 属性 + 2 方法 + 2 实例；规范率≥75%
  良好(C)：方法含状态校验（已启动再 start 给出提示）
  优秀(B)：≥3 属性 + ≥3 方法 + 3 实例；规范率≥90%
  优(A)：达 B 且方法间有协作（stop 后自动记录日志字符串）
输入全部来自 pipeline 的实测值：类结构用 ast 真实统计 core.py（与
stylecheck 同口径、可复核），实例数/拦截提示/停机日志来自真实调用——
verdict 只做比较，不产生新数据。档位按工单语义递进：B 建立在 D/C 之上，
A 档工单明写"达 B"。数字门槛外置在 config/rules.yaml 的 `tiers:` 段。
"""

TIERS = [
    ("及格(D)", "1 类 + 2 属性 + 2 方法 + 2 实例；规范率≥75%", 75.0),
    ("良好(C)", "方法含状态校验（已启动再 start 给出提示）", 80.0),
    ("优秀(B)", "≥3 属性 + ≥3 方法 + 3 实例；规范率≥90%", 90.0),
    ("优(A)", "达 B 且方法间有协作（stop 后自动记录日志字符串）", 90.0),
]
KEYS = ("D", "C", "B", "A")
# 机器判不了、必须教师现场确认的条目（报告明列，答辩时逐条勾）
MANUAL = [
    "预习单口述：一台变频器有哪些属性和方法",
    "课中抽查：温度告警三级阈值判断（口述/白板）",
    "提交物核对：对象调用输出截图与 report.txt 实测行一致",
]

GATES = {
    "D_style_min": 75.0, "C_style_min": 80.0,
    "B_style_min": 90.0, "A_style_min": 90.0,
    "D_min_classes": 1, "D_min_attrs": 2,
    "D_min_methods": 2, "D_min_instances": 2,
    "B_min_attrs": 3, "B_min_methods": 3, "B_min_instances": 3,
}
_STYLE_KEY = {"D": "D_style_min", "C": "C_style_min",
              "B": "B_style_min", "A": "A_style_min"}


def gates_from(cfg):
    """rules.yaml `tiers:` 段读出数字门槛（config.py 负责合并与回落）。"""
    return cfg.tier_gates(GATES)


def verdict(gates, rate, n_classes, n_attrs, n_methods, n_instances,
            guard_ok, guard_msg, stop_log_ok, stop_log_lines):
    """按实测值给四档判定；每档 = 功能门 + 规范率门，缺一即不达标。

    guard_msg: 真实连调两次 start() 捕获到的拦截提示文本（工单"给出提示"）；
    stop_log_ok/stop_log_lines: 真实 stop() 后日志实测增行与全厂停机类行数。
    """
    fd = (n_classes >= int(gates["D_min_classes"])
          and n_attrs >= int(gates["D_min_attrs"])
          and n_methods >= int(gates["D_min_methods"])
          and n_instances >= int(gates["D_min_instances"]))
    fc = fd and bool(guard_ok) and bool(str(guard_msg).strip())
    fb = fc and (n_attrs >= int(gates["B_min_attrs"])
                 and n_methods >= int(gates["B_min_methods"])
                 and n_instances >= int(gates["B_min_instances"]))
    fa = fb and bool(stop_log_ok) and stop_log_lines >= 1
    functional = {"D": fd, "C": fc, "B": fb, "A": fa}
    out = []
    for (name, need, _), key in zip(TIERS, KEYS):
        gate = float(gates[_STYLE_KEY[key]])
        ok = bool(functional[key]) and rate >= gate
        out.append({"tier": name, "gate": gate, "need": need,
                    "functional": bool(functional[key]),
                    "style_ok": rate >= gate, "pass": ok})
    claimed = next((t["tier"] for t in reversed(out) if t["pass"]),
                   "未达 D 档")
    return {"tiers": out, "claimed": claimed,
            "measured": {"n_classes": n_classes, "n_attrs": n_attrs,
                         "n_methods": n_methods,
                         "n_instances": n_instances,
                         "guard_ok": bool(guard_ok),
                         "guard_msg": str(guard_msg),
                         "stop_log_ok": bool(stop_log_ok),
                         "stop_log_lines": int(stop_log_lines),
                         "manual": list(MANUAL)}}


def render_lines(v):
    """把判定渲染成报告行（实测 + 档位判定，进 output/report.txt）。"""
    m = v["measured"]
    lines = ["实测达成档位: %s ｜ AST 实测: 业务类 %d 个 / 实例属性 %d 个 / "
             "公开方法 %d 个 ｜ 运行时实例 %d 台 ｜ stop 协作日志 %d 行"
             % (v["claimed"], m["n_classes"], m["n_attrs"], m["n_methods"],
                m["n_instances"], m["stop_log_lines"])]
    lines.append("重复 start 拦截提示（真实调用两次实测捕获）: %s"
                 % (m["guard_msg"] or "无——未捕获到任何提示"))
    for t in v["tiers"]:
        lines.append("  %-8s 规范率门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"],
                        "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("人工答辩项 %d 条（教师答辩时确认）:" % len(m["manual"]))
    lines.extend("  · " + x for x in m["manual"])
    return lines
