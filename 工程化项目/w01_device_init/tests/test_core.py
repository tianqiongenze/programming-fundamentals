# -*- coding: utf-8 -*-
"""core 层测试：正常 / 边界 / 异常三档。"""
import pytest

from device_init import core
from device_init.config import Settings


@pytest.fixture
def cfg():
    return Settings(warn=80.0, danger=95.0)


def make_dev(**kw):
    base = dict(code="DEV-1", name="注塑机", temp=56.5, press_kpa=450.0, rpm=1480)
    base.update(kw)
    return core.Device(**base)


# ── 正常 ──
def test_c_to_f_normal():
    assert core.c_to_f(100.0) == 212.0
    assert abs(core.c_to_f(37.0) - 98.6) < 1e-6


def test_kpa_to_mpa_normal():
    assert core.kpa_to_mpa(450.0) == 0.45
    assert abs(core.mpa_to_psi(1.0) - 14.5038) < 1e-6


def test_card_is_fstring_and_contains_all_fields(cfg):
    """工单任务2：台账卡必须是 f-string 渲染（非 % 拼接），字段齐全且对齐。"""
    t = "\n".join(core.card(make_dev(), cfg))
    for k in ("DEV-1", "注塑机", "56.5", "133.7", "0.450 MPa", "6.53 psi",
              "1480", "380", "NORMAL", "设 备 台 账 卡"):
        assert k in t, k
    src = open(core.__file__, encoding="utf-8").read()
    assert 'f"温度' in src and "f\"设备编号" in src     # 源码层面确实是 f-string


def test_ledger_has_8_vars_4_types():
    """工单 B 档：≥8 变量、4 种类型。"""
    table = core.var_table(make_dev())
    kinds = {t for _, _, t in table}
    assert len(table) >= 8
    assert len(kinds) >= 4
    assert {"str", "int", "float", "bool"} <= kinds


def test_two_or_more_conversions(cfg):
    """工单 B 档：换算 ≥2 处——℉ / MPa / psi 三个换算值同卡可见。"""
    t = "\n".join(core.card(make_dev(temp=78.5, press_kpa=450.0), cfg))
    assert "173.3" in t and "0.450 MPa" in t and "6.53 psi" in t


# ── 边界 ──
@pytest.mark.parametrize("t,lv", [
    (79.9, "normal"), (80.0, "warn"), (94.9, "warn"),
    (95.0, "danger"), (100.0, "danger")])
def test_level_of_boundaries(cfg, t, lv):
    assert core.level_of(t, cfg.warn, cfg.danger) == lv


def test_device_is_immutable():
    d = make_dev()
    with pytest.raises(Exception):
        d.temp = 99.0


def test_parse_temp_range_hint():
    """工单 A 档：温度范围提示——越界与非法都要给出可读原因。"""
    assert core.parse_temp("56.5")[0] == 56.5
    ok, msg = core.parse_temp("999")
    assert ok is None and "超出车间允许区间" in msg
    ok, msg = core.parse_temp("abc")
    assert ok is None and "不是数字" in msg


def test_interactive_card_with_injected_reader(cfg):
    """工单 A 档：input() 录入并校验——用假 reader 复现同一分支。"""
    answers = iter(["DEV-9", "试制泵", "81.5", "500", "380", "2024", "y"])
    lines = core.interactive_card(cfg, reader=lambda prompt: next(answers))
    joined = "\n".join(lines)
    assert "DEV-9" in joined and "试制泵" in joined and "WARN" in joined
    assert "交互录入" in joined


# ── 异常 ──
def test_card_rejects_negative_pressure():
    with pytest.raises(Exception):
        make_dev(press_kpa=-1.0)


def test_rejects_bad_voltage_and_year():
    with pytest.raises(ValueError):
        make_dev(voltage=0)
    with pytest.raises(ValueError):
        make_dev(install_year=1899)
