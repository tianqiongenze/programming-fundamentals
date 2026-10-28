# -*- coding: utf-8 -*-
"""工单 W03 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

判据与 tiers.verdict / cli --tier 同源，数字门槛外置在 rules.yaml tiers:：
D 循环实跑≥30 样本 + 2 具名函数（AST）+ 规范率≥70%；C 统计逐台复算全对
且 while 实跑轮数≤约定上限；B 每个函数体≤15 行（AST 量）+ docstring 全
覆盖 + 规范率≥85%；A 达 B 且 W02→W03 对照数字实测成功、对比文档真实存在。
反向断言只削弱实测值、不动门槛——档位是算出来的，不是常量。
"""
import copy
import os

import pytest

from patrol_loop import config as C
from patrol_loop import pipeline, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "rules.yaml")
OUT = os.path.join(ROOT, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整流水线，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    return {t["key"]: t for t in v["tiers"]}


def _down(built, weaken):
    """复用本次实测值、只削弱指定能力项重算档位——证明承诺档位会跟着掉。"""
    _, r = built
    m = copy.deepcopy(r["tiers"]["measured"])
    m.update(weaken)
    return tiers.verdict(tiers.gates(C.load_config(CFG)), m)


def test_measured_counts_are_ast_and_run_real(built):
    _, r = built
    m = r["tiers"]["measured"]
    assert m["named_funcs"] == 2 and m["for_loops_patrol"] >= 2
    assert m["samples"] >= 30 and m["stats_ok"]
    assert m["bounded_ok"] and m["while_max_cycles"] <= m["while_cap"]
    assert m["doc_defs"] == m["n_funcs"] and m["max_body"] <= 15
    assert m["w02"]["ok"] and m["has_doc"]


def test_all_four_tiers_pass_and_claim_is_highest(built):
    _, r = built
    got = tiers_of(r["tiers"])
    for key in ("D", "C", "B", "A"):
        assert got[key]["pass"], "%s 档实测未达标: %s" % (key, got[key])
    assert r["tiers"]["claimed"] == "优(A)"


def test_tier_section_written_into_run_report(built):
    """run.py 落盘的 output/report.txt 必须含实测四档判定与人工答辩项计数。"""
    _, r = built
    text = open(os.path.join(ROOT, "output", "report.txt"),
                encoding="utf-8").read()
    assert "验收档位判定（实测）" in text and "人工答辩项" in text
    assert "实测达成档位: %s" % r["tiers"]["claimed"] in text


def test_w02_comparison_numbers_are_real(built):
    """A 档"函数化收益"的对照数字是两边源码各扫一遍 AST 得来的。"""
    _, r = built
    cmp2 = r["tiers"]["measured"]["w02"]
    assert cmp2["fns_w02"] > cmp2["fns_w03"], "判级函数应被收敛得更少"
    assert cmp2["ge_w02"] > cmp2["ge_w03"], "≥ 判级比较点应显著减少"


@pytest.mark.parametrize("weaken,expect_claim", [
    ({"named_funcs": 1}, "未达 D 档"),               # 少一个具名函数：D 即不过
    ({"samples": 20}, "未达 D 档"),                  # 循环实跑样本不足 30
    ({"stats_ok": False}, "及格(D)"),                # 统计复算对不上：C 起不过
    ({"bounded_ok": False}, "及格(D)"),              # while 越出上限：C 起不过
    ({"body_lines": {"patrol": 21}}, "良好(C)"),     # 冒出一个 21 行函数：B/A 不过
    ({"doc_defs": 5}, "良好(C)"),                    # docstring 覆盖不全：B/A 不过
    ({"w02": {"ok": False, "detail": "MISS", "ge_w02": "-", "ge_w03": "-",
              "fns_w02": "-", "lines_w02": "-"}, "has_doc": True}, "优秀(B)"),
])
def test_claim_drops_when_capability_weakened(built, weaken, expect_claim):
    assert _down(built, weaken)["claimed"] == expect_claim
