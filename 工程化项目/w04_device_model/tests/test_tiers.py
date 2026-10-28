# -*- coding: utf-8 -*-
"""工单 W04 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

档位判据与 tiers.verdict / cli --tier 同源（工单验收标准表）：
D 1类+2属性+2方法+2实例（AST 统计，≥75%）；C 已启动再 start 实测有提示（≥80%）；
B ≥3属性+≥3方法+3实例（≥90%）；A 达 B 且 stop 后实测新增日志字符串。
断言只看本次运行真实产生的 AST 统计、拦截提示与日志行，自称会当场红。
"""
import os

import pytest

from device_model import config as C
from device_model import pipeline, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "rules.yaml")
OUT = os.path.join(ROOT, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整建模流程，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    """tiers.verdict 的返回 → {档位字母: 判定}（实测与手工构造同一口径）。"""
    return {t["tier"][-2]: t for t in v["tiers"]}


def test_artifacts_exist_and_are_real(built):
    """产物真实性：report.txt / result.json 都落盘且字节 > 1000，报告含四档判定。"""
    _, r = built
    report = os.path.join(OUT, "report.txt")
    assert os.path.exists(report) and os.path.getsize(report) > 1000
    assert os.path.getsize(os.path.join(OUT, "result.json")) > 1000
    text = open(report, encoding="utf-8").read()
    assert "验收档位判定（实测）" in text and "实测达成档位" in text
    assert "人工答辩项" in text, "人工判定项必须在报告里明列"
    assert r["tiers"]["claimed"] in text


def test_D_structure_measured_by_ast_not_claimed(built):
    """D 档：类/属性/方法数来自 AST 真实统计，实例数来自真实构造。"""
    _, r = built
    m = r["tiers"]["measured"]
    assert m["n_classes"] >= 1
    assert m["n_attrs"] >= 2 and m["n_methods"] >= 2
    assert m["n_instances"] == r["n_devices"] >= 2
    assert "logs" in r["ast_structure"]["attrs"], \
        "A 档协作载体 logs 必须真的写在 __init__ 里（AST 证据）"


def test_C_double_start_prompt_is_captured_text(built):
    """C 档：真实连调两次 start，报告里的提示文本是捕获到的异常消息。"""
    _, r = built
    m = r["tiers"]["measured"]
    assert m["guard_ok"] and "已在运行" in m["guard_msg"], (
        "工单 C 档『已启动再start给出提示』：实测捕获=%r" % m["guard_msg"])


def test_B_instances_and_style_gate(built):
    """B 档：≥3 属性/≥3 方法/3 实例 + 规范率≥90%，全部实测。"""
    _, r = built
    m = r["tiers"]["measured"]
    assert m["n_attrs"] >= 3 and m["n_methods"] >= 3 and m["n_instances"] >= 3
    assert r["style_rate"] >= 90.0, (
        "B/A 档门槛≥90%%，实测 %.1f%%（引擎 %s）"
        % (r["style_rate"], r["style_engine"]))


def test_A_stop_actually_appends_log_string(built):
    """A 档：stop() 实测新增一行含『停机』的字符串日志（不是文档里自称）。"""
    _, r = built
    m = r["tiers"]["measured"]
    assert m["stop_log_ok"] and m["stop_log_lines"] >= 1
    assert "停机（此刻温度" in str(r["logs_per_device"]), \
        "协作日志里必须能回读到停机行原文"


def test_all_four_tiers_pass_and_claim_is_highest(built):
    _, r = built
    got = tiers_of(r["tiers"])
    for key in ("D", "C", "B", "A"):
        assert got[key]["pass"], "%s 档实测未达标: %s" % (key, got[key])
    assert r["tiers"]["claimed"] == "优(A)"


def _down(built, **patch):
    """反向证明：只改一个实测值走 verdict，档位必须如实下降。"""
    _, r = built
    m = r["tiers"]["measured"]
    args = {"gates": tiers.GATES, "rate": 100.0,
            "n_classes": m["n_classes"], "n_attrs": m["n_attrs"],
            "n_methods": m["n_methods"], "n_instances": m["n_instances"],
            "guard_ok": m["guard_ok"], "guard_msg": m["guard_msg"],
            "stop_log_ok": m["stop_log_ok"],
            "stop_log_lines": m["stop_log_lines"]}
    args.update(patch)
    return tiers.verdict(**args)


def test_claim_drops_when_instances_shrink(built):
    """反向 1：实例只剩 2 台（B 档要 3），承诺档位必须从 A 掉到 C。"""
    down = _down(built, n_instances=2)
    got = tiers_of(down)
    assert got["D"]["pass"] and got["C"]["pass"]
    assert not got["B"]["pass"] and not got["A"]["pass"]
    assert down["claimed"] == "良好(C)"


def test_claim_drops_when_state_guard_removed(built):
    """反向 2：去掉状态校验（重复 start 不再提示），C/B/A 全部落空。"""
    down = _down(built, guard_ok=False, guard_msg="")
    got = tiers_of(down)
    assert not got["C"]["pass"] and not got["B"]["pass"] and not got["A"]["pass"]
    assert down["claimed"] == "及格(D)"


def test_claim_drops_when_stop_log_removed(built):
    """反向 3：stop 不再写日志（协作断链），A 档必须掉到 B。"""
    down = _down(built, stop_log_ok=False, stop_log_lines=0)
    got = tiers_of(down)
    assert not got["A"]["pass"] and got["B"]["pass"]
    assert down["claimed"] == "优秀(B)"


def test_gate_fails_below_style_minimum(built):
    """反向 4：规范率 70% < D 档 75%，功能全对也判『未达 D 档』。"""
    down = _down(built, rate=70.0)
    assert tiers_of(down)["D"]["pass"] is False
    assert down["claimed"] == "未达 D 档"
