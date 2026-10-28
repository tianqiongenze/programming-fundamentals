# -*- coding: utf-8 -*-
"""工单 W02《工业实时告警系统Ⅰ：条件判断》验收标准逐档断言（D/C/B/A）。

数字门槛唯一来源：config/rules.yaml 的 tiers: 段（经 tiers.gates 读出）。
"""
import inspect
import os

import pytest

from alarm_engine import cli
from alarm_engine import config as C
from alarm_engine import core, pipeline, stylecheck, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "output", "report.txt")
EXPECTED_TEMPS = [79.9, 80.0, 94.9, 95.0, 100.0]


@pytest.fixture(scope="module")
def cfg():
    return C.load_config(os.path.join(ROOT, "config", "rules.yaml"))


@pytest.fixture(scope="module")
def run_out(cfg, tmp_path_factory):
    return pipeline.run(cfg, out_dir=str(tmp_path_factory.mktemp("out")))


# ── 各档规范率门槛（数字外置在 rules.yaml tiers:；工单未设的档不编造）──
@pytest.mark.parametrize("key", ["D", "C", "B", "A"])
def test_style_rate_meets_each_tier(cfg, key):
    gate = tiers.gates(cfg)[key]["rate_min"]
    if gate is None:
        return                  # 工单该档只写功能项——没有数字门槛就不判数字
    stats = stylecheck.scan_project(ROOT)
    assert stats["rate"] >= gate, "%s 需规范率≥%s%%，实测 %.1f%%" % (
        key, gate, stats["rate"])


def test_tiers_surface_wired_to_rules_yaml(cfg):
    """cli --tier 与 report 段必须同源：tiers.py 判据 + rules.yaml 数字。"""
    assert cli.TIERS == tiers.TIERS
    assert tiers.gates(cfg)["D"]["rate_min"] == 70.0
    assert tiers.gates(cfg)["B"]["rate_min"] == 85.0


def test_style_checker_is_real_not_stub():
    stats = stylecheck.scan_project(ROOT)
    assert stats["files"] >= 8 and stats["lines"] >= 200


# ── 及格(D)：≥2 个 if 判断 + 1 个告警函数 alarm(level, msg) ──
def test_d_tier_two_if_and_alarm_function(cfg):
    assert callable(core.alarm)
    params = list(inspect.signature(core.alarm).parameters)
    assert params == ["level", "msg"], "工单点名签名 alarm(level, msg)，实得 %s" % params
    src = inspect.getsource(core.temp_level) + inspect.getsource(core.press_level)
    assert src.count("if ") >= 2, "D 档需 ≥2 个 if 条件判断"
    # 阈值口径与工单一致：温度 80/95、压力 0.8
    assert (cfg.warn, cfg.danger) == (80.0, 95.0)
    assert float(cfg.get("press_limit")) == 0.8
    assert core.alarm("danger", "试验").startswith("[停机]")


# ── 良好(C)：边界五组测试全对 ──
@pytest.mark.parametrize("t,lv", [(79.9, "normal"), (80.0, "warn"), (94.9, "warn"),
                                  (95.0, "danger"), (100.0, "danger")])
def test_c_tier_five_boundary_groups(cfg, t, lv):
    assert core.temp_level(t, cfg.warn, cfg.danger) == lv


def test_c_tier_boundary_table_covers_all_five(cfg):
    rows = core.boundary_table(EXPECTED_TEMPS, [0.55, 0.8], cfg)
    temps = [r["value"] for r in rows if r["kind"] == "temp"]
    assert temps == EXPECTED_TEMPS, "五组温度边界必须逐一实测"
    assert all(r["text"] for r in rows)


def test_c_tier_pressure_boundary_including_08(cfg):
    """压力 0.8MPa 这条工单点名的阈值必须真的出现在用例表里。"""
    rows = core.boundary_table([50.0], [0.54, 0.55, 0.64, 0.65, 0.80], cfg)
    vals = [r["value"] for r in rows if r["kind"] == "press"]
    assert 0.80 in vals
    by = {r["value"]: r["level"] for r in rows if r["kind"] == "press"}
    assert by[0.54] == "normal" and by[0.55] == "warn" and by[0.80] == "danger"


# ── 优秀(B)：多条件嵌套（提示/警告/停机三级）──
def test_b_tier_nested_three_levels(cfg):
    pw, pd, pl = 0.55, 0.65, 0.8
    assert core.nested_level(50.0, 0.60, 80.0, 95.0, pw, pd, pl) == "notice"
    assert core.nested_level(85.0, 0.40, 80.0, 95.0, pw, pd, pl) == "warning"
    assert core.nested_level(96.0, 0.40, 80.0, 95.0, pw, pd, pl) == "stop"
    assert core.nested_level(96.0, 0.70, 80.0, 95.0, pw, pd, pl) == "emergency"
    src = inspect.getsource(core.nested_level)
    body = [ln for ln in src.splitlines() if ln.strip().startswith("if ")]
    deep = [ln for ln in src.splitlines() if ln.startswith("        if ")]
    assert len(body) >= 4 and len(deep) >= 2, "B 档需真实嵌套（外层粗筛+内层细筛）"


# ── 优(A)：达 B 且循环测试 3 台设备 ──
def test_a_tier_loop_three_devices(cfg):
    swept = core.sweep(cfg.seq("devices"), cfg)
    assert len(swept) >= 3, "A 档需循环测试 ≥3 台设备，实得 %d" % len(swept)
    assert {s["code"] for s in swept} == {"PUMP-01", "PUMP-02", "VFD-03"}
    assert all(s["text"].startswith("[") for s in swept)   # 全部经 alarm() 输出


def test_task4_both_over_limit_upgrades_to_emergency(cfg):
    assert core.judge(96.0, 0.70, 80.0, 95.0, 0.55, 0.65) == "emergency"
    assert core.judge(96.0, 0.50, 80.0, 95.0, 0.55, 0.65) == "danger"


# ── 交付证据 ──
def test_committed_report_contains_tier_evidence(run_out):
    assert os.path.exists(REPORT)
    text = open(REPORT, encoding="utf-8").read()
    for key in ("告警流水（alarm(level,msg) 输出）", "边界用例表", "多条件嵌套三级",
                "编码规范率（PEP 8 实测）", "验收档位判定（实测）"):
        assert key in text, key
    assert "实测达成档位" in text
    stats = stylecheck.scan_project(ROOT)
    assert ("规范率实测: %.1f%%" % stats["rate"]) in text
