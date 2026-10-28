# -*- coding: utf-8 -*-
"""core 层测试：判级函数、循环封装、while 退出条件（正常/边界/异常三档）。"""
import random

import pytest

from patrol_loop import core


# ── 正常 ──
def test_series_deterministic():
    a = core.series(70.0, 2.5, 5, random.Random(0))
    b = core.series(70.0, 2.5, 5, random.Random(0))
    assert a == b
    assert all(60.0 < t < 95.0 for t in a)


def test_check_device_levels():
    """工单任务3：check_device(d) 判级——单参数（dict）即可，阈值随设备走。"""
    assert core.check_device({"temp": 79.9, "press": 0.4}) == "normal"
    assert core.check_device({"temp": 81.0, "press": 0.4}) == "warn"
    assert core.check_device({"temp": 96.0, "press": 0.4}) == "danger"
    assert core.check_device({"temp": 96.0, "press": 0.80}) == "emergency"


def test_alarm_output_signature():
    assert core.alarm("warn", "80.0℃") == "[警告] 80.0℃"
    assert core.alarm("emergency", "x").startswith("[紧急]")
    assert core.alarm("nope", "x").startswith("[未知]")


def test_patrol_covers_all_devices_and_cycles():
    devs = [{"code": "D1", "base_temp": 70.0, "drift": 2.0, "press": 0.4},
            {"code": "D2", "base_temp": 66.0, "drift": 2.4, "press": 0.7}]
    stat = core.patrol(devs, 10, seed=2)
    assert set(stat) == {"D1", "D2"}
    assert all(len(s["temps"]) == 10 for s in stat.values())
    assert all(len(s["levels"]) == 10 for s in stat.values())


def test_patrol_is_reproducible():
    devs = [{"code": "D1", "base_temp": 70.0, "drift": 2.0}]
    a = core.patrol(devs, 10, seed=5)["D1"]["temps"]
    b = core.patrol(devs, 10, seed=5)["D1"]["temps"]
    assert a == b


def test_summarize_totals():
    devs = [{"code": "D1", "base_temp": 78.0, "drift": 2.5, "press": 0.4}]
    stat = core.patrol(devs, 10, seed=1)
    rows = core.summarize(stat)
    assert rows[0]["alarms"] == rows[0]["warn"] + rows[0]["danger"]


# ── 边界 ──
def test_priority_sorts_by_alarm_count():
    stat = {"A": {"alarms": 1}, "B": {"alarms": 3}, "C": {"alarms": 0}}
    assert [d for d, _ in core.priority(stat)] == ["B", "A", "C"]


def test_count_alarms_counts_each_level():
    c = core.count_alarms(["normal", "warn", "danger", "emergency", "warn"])
    assert (c["warn"], c["danger"], c["emergency"]) == (2, 1, 1)


# ── while 版本：退出条件（工单任务5 / 良好 C "无死循环风险"）──
def test_while_exit_by_danger():
    devs = [{"code": "D1", "base_temp": 96.0, "drift": 0.0, "danger": 95.0}]
    stat = core.patrol_while(devs, 10, seed=0)
    assert stat["D1"]["cycles"] == 1
    assert "触停机线" in stat["D1"]["exit_reason"]


def test_while_exit_by_cycle_count():
    devs = [{"code": "D1", "base_temp": 40.0, "drift": 0.0, "danger": 95.0}]
    stat = core.patrol_while(devs, 10, seed=0)
    assert stat["D1"]["cycles"] == 10
    assert "跑满 10 个周期" in stat["D1"]["exit_reason"]


def test_while_hard_limit_never_exceeded():
    """即使把周期数写成天文数字，兜底上限也必须把循环掐住（防死循环）。"""
    devs = [{"code": "D1", "base_temp": 40.0, "drift": 0.0, "danger": 999.0}]
    stat = core.patrol_while(devs, 10 ** 6, seed=0, hard_limit=50)
    assert stat["D1"]["cycles"] <= 50
    assert "硬上限" in stat["D1"]["exit_reason"]


# ── 异常 ──
def test_check_device_tolerates_missing_keys():
    assert core.check_device({}) == "normal"          # 缺字段按 0 处理 → 正常


def test_check_device_rejects_non_numeric_temp():
    with pytest.raises(ValueError):
        core.check_device({"temp": "abc"})            # 脏数据当场抛，不静默吞
