# -*- coding: utf-8 -*-
import pytest

from device_model import core


def test_start_from_stopped():
    d = core.Device("DEV-1", "空压机")
    assert "启动成功" in d.start() and d.running


def test_double_start_rejected():
    d = core.Device("DEV-1", "空压机")
    d.start()
    with pytest.raises(core.AlreadyRunningError):
        d.start()


def test_stop_when_stopped_rejected():
    d = core.Device("DEV-1", "空压机")
    with pytest.raises(core.NotRunningError):
        d.stop()


def test_start_after_stop_ok():
    d = core.Device("DEV-1", "空压机")
    d.start()
    d.stop()
    assert d.start() and d.running


def test_running_is_read_only():
    d = core.Device("DEV-1", "x")
    with pytest.raises(AttributeError):
        d.running = True


def test_patrol_levels():
    assert "DANGER" in core.Device("DEV-2", "x", temp=96.0).patrol(80, 95)
    assert "NORMAL" in core.Device("DEV-3", "x", temp=50.0).patrol(80, 95)


def test_empty_device_list_raises():
    from device_model.config import Settings
    from device_model import pipeline
    with pytest.raises(ValueError):
        pipeline.run(Settings(items=[]), "/tmp/never")
