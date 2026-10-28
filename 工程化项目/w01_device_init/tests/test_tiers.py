# -*- coding: utf-8 -*-
"""工单 W01 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

判据与 tiers.verdict / cli --tier 同源，数字门槛外置在 rules.yaml tiers:：
D ≥6 变量、≥3 类型（AST）+ 规范率≥70%；C 冒号列对齐实测 + 换算独立公式复核；
B ≥8 变量、4 类型、换算≥2 处 + 规范率≥90%；A 达 B 且 stdin 注入真走
input() 路径：越界/非数字当场拒收、温度范围提示可见。
反向断言只削弱实测值、不动门槛——档位是算出来的，不是常量。
"""
import copy
import os

import pytest

from device_init import config as C
from device_init import pipeline, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "rules.yaml")
OUT = os.path.join(ROOT, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整流水线，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    """verdict 返回 → {档字母: 判定}（实测与手工削弱走同一口径）。"""
    return {t["key"]: t for t in v["tiers"]}


def _down(built, weaken):
    """复用本次实测值、只削弱指定能力项重算档位——证明承诺档位会跟着掉。"""
    _, r = built
    m = copy.deepcopy(r["tiers"]["measured"])
    m.update(weaken)
    return tiers.verdict(tiers.gates(C.load_config(CFG)), m)


def test_measured_counts_come_from_ast_and_stdin(built):
    _, r = built
    m = r["tiers"]["measured"]
    assert m["ast_vars"] >= 6 and m["ast_types"] >= 3
    assert m["conv_funcs"] >= 2 and m["conv_failed"] == 0
    assert m["colon_lines"] >= 5 and m["colon_same"] == 1
    assert m["input_probe_ok"] and m["input_hint_ok"]


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
    assert "验收档位判定（实测）" in text
    assert "实测达成档位: 优(A)" in text
    assert "人工答辩项" in text
    gen = open(os.path.join(OUT, "report.txt"), encoding="utf-8").read()
    assert "实测达成档位: %s" % r["tiers"]["claimed"] in gen


@pytest.mark.parametrize("weaken,expect_claim", [
    ({"ast_vars": 5}, "未达 D 档"),                    # 变量实测不足 6：全档掉光
    ({"conv_failed": 2}, "及格(D)"),                  # 换算复核错 2 处：C 起不过
    ({"style_rate": 85.0}, "良好(C)"),                # 规范率不到 90：B/A 不过
    ({"input_probe_ok": False}, "优秀(B)"),           # input() 路径断：只掉 A
])
def test_claim_drops_when_capability_weakened(built, weaken, expect_claim):
    assert _down(built, weaken)["claimed"] == expect_claim
