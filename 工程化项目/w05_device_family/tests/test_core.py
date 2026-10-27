# -*- coding: utf-8 -*-
import pytest

from device_family import core


def test_factory_builds_subclasses():
    p = core.from_dict({"type": "pump", "code": "P1", "temp": 50.0, "freq_hz": 40})
    f = core.from_dict({"type": "fan", "code": "F1", "temp": 40.0, "delay_s": 5})
    assert isinstance(p, core.PumpDevice) and isinstance(f, core.FanDevice)


def test_unknown_type_rejected():
    with pytest.raises(ValueError):
        core.from_dict({"type": "tank", "code": "T1", "temp": 1.0})


def test_polymorphic_dispatch_same_call():
    p = core.PumpDevice("P1", 96.0)
    f = core.FanDevice("F1", 30.0)
    assert "DANGER" in p.dispatch(80, 95) and "NORMAL" in f.dispatch(80, 95)


def test_set_freq_within_range():
    assert "35.0Hz" in core.PumpDevice("P1", 1.0).set_freq(35.0)


@pytest.mark.parametrize("hz", [10.0, 70.0, 0.0])
def test_set_freq_out_of_range_rejected(hz):
    with pytest.raises(ValueError):
        core.PumpDevice("P1", 1.0).set_freq(hz)


def test_fan_delay_stop():
    assert "延时 4s" in core.FanDevice("F1", 1.0, 4).delay_stop()


def test_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        core.Device("X", 1.0)
