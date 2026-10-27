# -*- coding: utf-8 -*-
import random

from patrol_loop import core


def test_series_deterministic():
    a = core.series(70.0, 2.5, 5, random.Random(0))
    b = core.series(70.0, 2.5, 5, random.Random(0))
    assert a == b
    assert all(69.0 < t < 91.0 for t in a)


def test_series_monotonic_drift():
    temps = core.series(70.0, 2.0, 4, random.Random(1))
    assert temps[3] > temps[0]


def test_count_alarms_tiers():
    w, d = core.count_alarms([60.0, 80.0, 95.0, 96.0], 80.0, 95.0)
    assert (w, d) == (1, 2)


def test_count_alarms_none():
    assert core.count_alarms([10.0, 20.0], 80.0, 95.0) == (0, 0)


def test_priority_sorts_by_alarm_count():
    stat = {"A": {"warn": 1, "danger": 0}, "B": {"warn": 0, "danger": 3},
            "C": {"warn": 0, "danger": 0}}
    assert [d for d, _ in core.priority(stat)] == ["B", "A", "C"]


def test_patrol_covers_all_devices():
    stat = core.patrol(["D1", "D2"], 6, 70.0, 3.0, 80.0, 95.0, seed=2)
    assert set(stat) == {"D1", "D2"}
    assert all(len(s["temps"]) == 6 for s in stat.values())
