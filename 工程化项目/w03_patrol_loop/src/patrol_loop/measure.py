# -*- coding: utf-8 -*-
"""工单 W03 D/C/B/A 功能门的实测产出：AST 函数清点 + 循环实跑 + W02 对照。

数字门槛外置在 config/rules.yaml 的 tiers: 段；本模块只产实测值：
  named_funcs     —— AST 核对工单点名的两个具名函数 check_device(d)/alarm(level,msg)；
  for_loops_patrol—— AST 数 patrol() 里的 for 层数（外层设备 × 内层周期）；
  samples         —— 实跑巡检收到的温度样本数（≥3 台 × 10 周期 = 30）；
  stats_ok        —— 统计报告逐台复算核对（告警数 = 各级之和 = 判级序列重数）；
  while_*         —— while 版实跑轮数对照约定上限（有界循环实测，不是声称）；
  body_lines      —— AST（lineno/end_lineno）量 core 每个函数体的有效行数；
  w02_compare     —— 读兄弟项目 W02 core 的 AST 实测：判级 ≥ 比较点数、
                     判级函数个数、core 有效行——"函数化收益"的数字部分。
"""
import ast
import os

from . import core


def _parse(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    return ast.parse(src, filename=path), src.splitlines(), src


def _body_lines(lines, node):
    """函数体有效行数（去空行与整行注释；docstring 计入——与验收测试同口径）。"""
    return sum(1 for ln in lines[node.lineno:node.end_lineno]
               if ln.strip() and not ln.lstrip().startswith("#"))


def _top_funcs(tree):
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


def _ge_and_level_funcs(path):
    """一台 core 的实测画像：≥ 比较出现点数 / 判级函数数 / 有效行数。"""
    tree, lines, _src = _parse(path)
    ge = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Compare)
             and any(isinstance(op, ast.GtE) for op in n.ops))
    level_fns = [n.name for n in _top_funcs(tree)
                 if "level" in n.name or "check" in n.name]
    return {"ge": ge, "level_fns": len(level_fns),
            "lines": sum(1 for ln in lines if ln.strip())}


def compare_w02(cfg, root):
    """W02→W03 函数化收益的实测数字（跨项目对照，路径外置；找不到就 MISS）。"""
    sec = cfg.get("tiers") or {}
    a_sec = sec.get("A") if isinstance(sec, dict) else None
    rel = str((a_sec or {}).get("w02_core") or
              "../w02_alarm_engine/src/alarm_engine/core.py")
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return {"ok": False, "detail": "MISS：未找到 W02 源码（%s）" % rel,
                "ge_w02": "-", "ge_w03": "-", "fns_w02": "-", "lines_w02": "-"}
    a = _ge_and_level_funcs(path)
    b = _ge_and_level_funcs(core.__file__)
    return {"ok": True, "detail": "判级 ≥ 比较点 %d→%d 处 ｜ 判级函数 %d→%d 个"
            "（check_device）｜ core 有效行 %d→%d"
            % (a["ge"], b["ge"], a["level_fns"], b["level_fns"],
               a["lines"], b["lines"]),
            "ge_w02": a["ge"], "ge_w03": b["ge"],
            "fns_w02": a["level_fns"], "fns_w03": b["level_fns"],
            "lines_w02": a["lines"], "lines_w03": b["lines"]}


def collect(cfg, root, stat, wstat, n_cycles):
    """汇总 W03 四档功能门的实测值（只测量、不判定）。"""
    tree, lines, _src = _parse(core.__file__)
    defs = _top_funcs(tree)
    bodies = {n.name: _body_lines(lines, n) for n in defs}
    doc_defs = sum(1 for n in defs if ast.get_docstring(n))
    named = sum(1 for n in defs
                if (n.name == "check_device"
                    and [a.arg for a in n.args.args][:1] == ["d"])
                or (n.name == "alarm"
                    and [a.arg for a in n.args.args] == ["level", "msg"]))
    patrol = next((n for n in defs if n.name == "patrol"), None)
    fors = sum(1 for n in ast.walk(patrol) if isinstance(n, ast.For)) if patrol else 0
    samples = sum(len(s["temps"]) for s in stat.values())
    stats_ok = bool(stat) and all(
        s["alarms"] == s["warn"] + s["danger"] + s["emergency"]
        and s["alarms"] == sum(1 for lv in s["levels"] if lv != "normal")
        for s in stat.values())
    while_max = max((s["cycles"] for s in wstat.values()), default=0)
    # "无死循环风险"实测口径：每台实跑轮数 ≤ 约定上限，且退出原因逐台留痕
    bounded_ok = bool(wstat) and all(
        0 < s["cycles"] <= n_cycles and s["exit_reason"]
        for s in wstat.values())
    doc = str(cfg.get("a_tier_doc") or "")
    doc_path = os.path.join(root, doc)
    doc_text = open(doc_path, encoding="utf-8").read() if doc else ""
    cmp2 = compare_w02(cfg, root)
    return {"n_funcs": len(defs), "doc_defs": doc_defs,
            "body_lines": bodies, "max_body": max(bodies.values() or [0]),
            "named_funcs": named, "for_loops_patrol": fors,
            "devices": len(stat), "n_cycles": n_cycles, "samples": samples,
            "stats_ok": stats_ok, "while_max_cycles": while_max,
            "while_cap": n_cycles, "bounded_ok": bounded_ok,
            "has_doc": bool(doc_text.strip()),
            "doc_chars": len(doc_text.strip()), "doc_rel": doc,
            "w02": cmp2}
