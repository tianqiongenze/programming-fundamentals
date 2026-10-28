# -*- coding: utf-8 -*-
"""工单 W02 D/C/B/A 功能门的实测产出：AST 计数 + 边界五组独立复核 + 循环实测。

数字门槛外置在 config/rules.yaml 的 tiers: 段；本模块只产实测值：
  ast_ifs_d   —— AST 数 temp_level/press_level 里的 if 节点（工单任务1 两道分级）；
  alarm_fns   —— AST 找签名恰为 alarm(level, msg) 的告警函数；
  boundary_*  —— 工单点名五组温度边界值实跑，期望等级按工单语义独立复算核对；
  nest_depth  —— AST 数 nested_level 里 if 套 if 的最大层数（elif 同列不算嵌套）；
  levels_hit  —— 提示/警告/停机三级各喂一组定向样本，判级与告警文案都要实测命中；
  devices_*   —— 实跑 sweep() 的循环覆盖设备台数。
"""
import ast

from . import core

# 三级文案的定向探针：(期望级别, alarm() 文案前缀, 温度, 压力)
NEST_PROBES = (("notice", "[提示]", 50.0, 0.60),
               ("warning", "[警告]", 85.0, 0.40),
               ("stop", "[停机]", 96.0, 0.40))


def _defs(path):
    """AST → {顶层函数名: FunctionDef 节点}。"""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _count_ifs(defs, names):
    """数给定函数集合里的 if 节点总数（工单 D 档"≥2 个 if 条件判断"）。"""
    total = 0
    for name in names:
        node = defs.get(name)
        if node is not None:
            total += sum(1 for n in ast.walk(node) if isinstance(n, ast.If))
    return total


def _alarm_fns(defs):
    """工单点名的告警函数：名字 alarm 且签名恰为 (level, msg) 才计数。"""
    node = defs.get("alarm")
    if node is None:
        return 0
    return 1 if [a.arg for a in node.args.args] == ["level", "msg"] else 0


def _nest_depth(node):
    """函数内 if 的最大嵌套层数：col_offset 严格更大才算嵌套（elif 同列）。"""
    ifs = [n for n in ast.walk(node) if isinstance(n, ast.If)]

    def depth(outer):
        inner = [n for n in ifs if n is not outer
                 and n.col_offset > outer.col_offset
                 and outer.lineno <= n.lineno <= outer.end_lineno]
        return 1 + max((depth(i) for i in inner), default=0)

    return max((depth(i) for i in ifs), default=0)


def _expected_level(t, warn, danger):
    """按工单语义独立复算（≥停机线→danger / ≥预警线→warn / 其余 normal）。

    故意不用 core.temp_level——用自己写的期望值核对被测函数，
    实现改坏了会当场对不上，这才是"测试全对"。
    """
    if t >= danger:
        return "danger"
    if t >= warn:
        return "warn"
    return "normal"


def collect(cfg):
    """汇总 W02 四档功能门的实测值（只测量、不判定）。"""
    defs = _defs(core.__file__)
    pw = float(cfg.get("press_warn", 0.55))
    pd = float(cfg.get("press_danger", 0.65))
    pl = float(cfg.get("press_limit", 0.8))
    temps = [float(x) for x in (cfg.seq("boundary_temps") or [])]
    hit = 0
    for lv, text, t, p in NEST_PROBES:
        if (core.nested_level(t, p, cfg.warn, cfg.danger, pw, pd, pl) == lv
                and core.alarm(lv, "探针").startswith(text)):
            hit += 1
    swept = core.sweep(cfg.seq("devices"), cfg)
    nest = defs.get("nested_level")
    # 五组边界逐个实跑，与独立复算的期望等级比对（C 档"全对"的实测口径）
    n_pass = sum(
        1 for t in temps
        if core.temp_level(t, cfg.warn, cfg.danger)
        == _expected_level(t, cfg.warn, cfg.danger))
    return {"ast_ifs_d": _count_ifs(defs, ("temp_level", "press_level")),
            "alarm_fns": _alarm_fns(defs),
            "boundary_total": len(temps),
            "boundary_pass": n_pass,
            "nest_depth": _nest_depth(nest) if nest is not None else 0,
            "levels_hit": hit,
            "devices_swept": len(swept),
            "sweep_has_for": defs.get("sweep") is not None and any(
                isinstance(n, ast.For) for n in ast.walk(defs["sweep"])),
            "alarm_via": bool(swept) and all(
                s["text"].startswith("[") for s in swept)}
