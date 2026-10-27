# -*- coding: utf-8 -*-
"""core 层测试：正常 / 边界 / 异常三档。"""
import pytest

from device_init import core
from device_init.config import Settings


@pytest.fixture
def cfg():
    return Settings(warn=80.0, danger=95.0)


# ── 正常 ──
def test_c_to_f_normal():
    assert core.c_to_f(100.0) == 212.0
    assert abs(core.c_to_f(37.0) - 98.6) < 1e-6


def test_kpa_to_mpa_normal():
    assert core.kpa_to_mpa(450.0) == 0.45


def test_card_contains_all_fields(cfg):
    d = core.Device("DEV-1", "注塑机", 56.5, 450.0, 1480)
    t = "\n".join(core.card(d, cfg))
    for k in ("DEV-1", "注塑机", "56.5", "0.45MPa", "NORMAL"):
        assert k in t


# ── 边界 ──
@pytest.mark.parametrize("t,lv", [(79.9, "normal"), (80.0, "warn"), (94.9, "warn"), (95.0, "danger")])
def test_level_of_boundaries(cfg, t, lv):
    assert core.level_of(t, cfg.warn, cfg.danger) == lv


def test_device_is_immutable():
    d = core.Device("DEV-1", "x", 1.0, 1.0, 1)
    with pytest.raises(Exception):
        d.temp = 99.0


# ── 异常 ──
def test_card_rejects_negative_pressure():
    with pytest.raises(Exception):
        core.Device("DEV-1", "x", 1.0, -1.0, 1)
