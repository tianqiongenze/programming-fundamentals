# -*- coding: utf-8 -*-
import pytest

from alarm_engine import core


@pytest.mark.parametrize("t,lv", [(78.0, "normal"), (80.0, "warn"), (95.0, "danger")])
def test_temp_level(t, lv):
    assert core.temp_level(t, 80.0, 95.0) == lv


def test_single_param_warn():
    assert core.judge(80.0, 0.50, 80.0, 95.0, 0.55, 0.65) == "warn"


def test_double_over_limit_becomes_emergency():
    assert core.judge(95.0, 0.66, 80.0, 95.0, 0.55, 0.65) == "emergency"


def test_only_one_over_limit_stays_danger():
    assert core.judge(95.0, 0.50, 80.0, 95.0, 0.55, 0.65) == "danger"


def test_dedup_suppresses_within_window():
    ev = [{"ts": 0, "level": "warn"}, {"ts": 5, "level": "warn"},
          {"ts": 15, "level": "warn"}]
    out = core.dedup(ev, 10)
    assert [e["suppressed"] for e in out] == [False, True, False]


def test_dedup_different_levels_not_merged():
    ev = [{"ts": 0, "level": "warn"}, {"ts": 1, "level": "danger"}]
    out = core.dedup(ev, 10)
    assert not any(e["suppressed"] for e in out)


def test_empty_input_returns_empty():
    assert core.dedup([], 10) == []


def test_pipeline_rejects_inverted_threshold():
    from alarm_engine.config import Settings
    from alarm_engine import pipeline
    cfg = Settings(warn=95.0, danger=80.0, items=[])
    with pytest.raises(ValueError):
        pipeline.run(cfg, "/tmp/never-created")
