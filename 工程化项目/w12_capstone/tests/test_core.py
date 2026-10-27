# -*- coding: utf-8 -*-
import pytest

from capstone import core


def test_parse_row_good():
    assert core.parse_row("注塑机,61.2,0.50") == {"name": "注塑机", "temp": 61.2, "press": 0.5}


@pytest.mark.parametrize("bad", ["err,0.46", "a,1", "a,1,2,3"])
def test_parse_row_bad_returns_none(bad):
    assert core.parse_row(bad) is None


@pytest.mark.parametrize("row,reason", [
    ({"name": "x", "temp": -1.0, "press": 0.4}, "负值"),
    ({"name": "x", "temp": 250.0, "press": 0.4}, "温度越界"),
    ({"name": "x", "temp": 50.0, "press": 9.0}, "压力越界"),
])
def test_clean_rejects(row, reason):
    assert core.clean(row, 80.0, 95.0) == (False, reason)


def test_clean_accepts():
    assert core.clean({"name": "x", "temp": 50.0, "press": 0.4}, 80.0, 95.0) == (True, "")


def test_level_tiers():
    assert core.level({"temp": 50, "press": 0.3}, 80, 95) == "normal"
    assert core.level({"temp": 82, "press": 0.3}, 80, 95) == "warn"
    assert core.level({"temp": 96, "press": 0.3}, 80, 95) == "danger"


def test_level_press_also_counts():
    assert core.level({"temp": 50, "press": 0.66}, 80, 95) == "danger"


def test_keywords_top1():
    kw = core.keywords(["注塑机液压油温升高报警", "注塑机液压泵泄漏"], k=3)
    assert kw and kw[0][1] >= kw[-1][1]


def test_keywords_stopword_filtered():
    kw = core.keywords(["设备系统发生异常"], k=5)
    words = [w for w, _ in kw]
    assert "设备" not in words and "系统" not in words


def test_keywords_empty_input():
    assert core.keywords([], k=5) == []
