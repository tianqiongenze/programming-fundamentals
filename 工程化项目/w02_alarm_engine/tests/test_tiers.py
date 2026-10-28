# -*- coding: utf-8 -*-
"""工单 W02 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

判据与 tiers.verdict / cli --tier 同源，数字门槛外置在 rules.yaml tiers:：
D ≥2 个 if（AST）+ alarm(level,msg)（AST）+ 规范率≥70%；C 边界五组逐组
独立公式复核全对；B if 嵌套≥2 层且提示/警告/停机三级实测命中 + 规范率≥85%；
A 达 B 且 sweep 循环实测≥3 台设备。
反向断言只削弱实测值、不动门槛——档位是算出来的，不是常量。
"""
import copy
import os

import pytest

from alarm_engine import config as C
from alarm_engine import pipeline, tiers

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
    assert m["ast_ifs_d"] >= 2 and m["alarm_fns"] == 1
    assert m["boundary_total"] == 5 and m["boundary_pass"] == 5
    assert m["nest_depth"] >= 2 and m["levels_hit"] == 3
    assert m["devices_swept"] >= 3 and m["sweep_has_for"] and m["alarm_via"]


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


@pytest.mark.parametrize("weaken,expect_claim", [
    ({"alarm_fns": 0}, "未达 D 档"),                  # 告警函数没了：D 即不过
    ({"boundary_pass": 3}, "及格(D)"),                # 边界五组只对 3：C 起不过
    ({"nest_depth": 1, "levels_hit": 2}, "良好(C)"),  # 没嵌套缺一级：B/A 不过
    ({"style_rate": 80.0}, "良好(C)"),                # 规范率不到 85：B/A 不过
    ({"devices_swept": 2, "alarm_via": False}, "优秀(B)"),   # 只循环 2 台：掉 A
])
def test_claim_drops_when_capability_weakened(built, weaken, expect_claim):
    assert _down(built, weaken)["claimed"] == expect_claim
