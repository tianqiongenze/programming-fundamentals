# -*- coding: utf-8 -*-
"""工单 W03《工业实时告警系统Ⅱ：循环与函数》验收标准逐档断言（D/C/B/A）。

数字门槛唯一来源：config/rules.yaml 的 tiers: 段（经 tiers.gates 读出）。
"""
import inspect
import os

import pytest

from patrol_loop import cli
from patrol_loop import config as C
from patrol_loop import core, pipeline, stylecheck, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "output", "report.txt")
A_DOC = os.path.join(ROOT, "docs", "09-函数化收益对比-W02到W03.md")


@pytest.fixture(scope="module")
def cfg():
    return C.load_config(os.path.join(ROOT, "config", "rules.yaml"))


@pytest.fixture(scope="module")
def sections(cfg, tmp_path_factory):
    return dict(pipeline.run(cfg, out_dir=str(tmp_path_factory.mktemp("out"))))


@pytest.fixture(scope="module")
def stat(cfg):
    return core.patrol(cfg.seq("devices"), int(cfg.num("n_cycles", 10)),
                       seed=int(cfg.seed))


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


# ── 及格(D)：循环跑通 + 2 个函数 ──
def test_d_tier_two_named_functions(cfg):
    assert list(inspect.signature(core.check_device).parameters)[:1] == ["d"]
    assert list(inspect.signature(core.alarm).parameters) == ["level", "msg"]
    stat = core.patrol(cfg.seq("devices"), 10, seed=int(cfg.seed))
    assert len(stat) >= 3, "工单任务1：≥3 台设备（列表+字典）"
    assert all(len(s["temps"]) == 10 for s in stat.values())


def test_d_tier_devices_are_list_of_dicts(cfg):
    """工单任务1 要求"列表+字典"组织——pipeline 不再自己合成设备名。"""
    devs = cfg.seq("devices")
    assert isinstance(devs, list) and all(isinstance(d, dict) for d in devs)
    assert {"code", "base_temp", "drift", "press"} <= set(devs[0])


# ── 良好(C)：统计报告正确；无死循环风险 ──
def test_c_tier_statistics_match_recount(cfg, stat):
    for code, s in stat.items():
        recount = s["warn"] + s["danger"] + s["emergency"]
        assert s["alarms"] == recount, code
        assert sum(1 for lv in s["levels"] if lv != "normal") == recount


def test_c_tier_report_numbers_are_real(sections, stat):
    text = "\n".join(sections["总计"])
    total = sum(s["alarms"] for s in stat.values())
    assert ("告警合计 %d 次" % total) in text


def test_c_tier_no_infinite_loop(cfg):
    n = int(cfg.num("n_cycles", 10))
    wstat = core.patrol_while(cfg.seq("devices"), n, seed=int(cfg.seed))
    assert all(s["cycles"] <= n for s in wstat.values())
    assert all(s["exit_reason"] for s in wstat.values()), "每次 while 都要留退出原因"


# ── 优秀(B)：函数职责清晰（每个函数 ≤15 行）；注释清晰 ──
@pytest.mark.parametrize("fn", ["check_device", "alarm", "jitter", "count_alarms",
                                "patrol", "patrol_while", "summarize"])
def test_b_tier_function_within_15_lines(fn):
    f = getattr(core, fn)
    body = inspect.getsource(f).splitlines()
    code_lines = [ln for ln in body[1:] if ln.strip()
                  and not ln.strip().startswith("#")]
    assert len(code_lines) <= 15, "%s 函数体 %d 行 > 15" % (fn, len(code_lines))


@pytest.mark.parametrize("fn", ["check_device", "alarm", "patrol", "patrol_while",
                                "count_alarms", "summarize", "priority", "jitter"])
def test_b_tier_every_function_documented(fn):
    assert getattr(core, fn).__doc__, "%s 缺 docstring" % fn


def test_b_tier_n_cycles_is_10(cfg):
    assert int(cfg.num("n_cycles", 0)) == 10, "工单要求 10 个周期"


# ── 优(A)：达 B 且重构 W02 代码对比说明"函数化收益" ──
def test_a_tier_reflection_doc_exists_and_substantive():
    assert os.path.exists(A_DOC), "A 档需提交函数化收益对比文档"
    text = open(A_DOC, encoding="utf-8").read()
    assert len(text) > 600, "对比文档不能是空壳"
    for kw in ("W02", "check_device", "alarm", "重复", "收益"):
        assert kw in text, "文档应覆盖关键词: %s" % kw


def test_a_tier_doc_referenced_in_report(sections):
    joined = "\n".join(sections["排班建议"])
    assert "docs/09" in joined
