# -*- coding: utf-8 -*-
"""core 单元测试：工厂分派、继承覆盖、super() 协作、越界校验、组合调度。"""
import inspect

import pytest

from device_family import core


def test_factory_builds_three_subclasses():
    plc = core.from_dict({"type": "plc", "code": "P1", "temp": 50.0, "scan_ms": 60})
    vfd = core.from_dict({"type": "vfd", "code": "V1", "temp": 50.0, "freq_hz": 40})
    sen = core.from_dict({"type": "sensor", "code": "S1", "temp": 50.0,
                          "range_lo": 0, "range_hi": 100})
    assert isinstance(plc, core.PLCDevice)
    assert isinstance(vfd, core.VFDDevice)
    assert isinstance(sen, core.SensorDevice)
    assert plc.scan_ms == 60.0 and vfd.freq_hz == 40.0 and sen.range_hi == 100.0


def test_unknown_type_rejected_with_hint():
    with pytest.raises(ValueError) as e:
        core.from_dict({"type": "tank", "code": "T1", "temp": 1.0})
    assert "已注册" in str(e.value)


def test_extra_config_keys_ignored_not_crashing():
    """配置多写字段（工厂只挑签名认识的），不该炸——改配置不改代码的容错面。"""
    d = core.from_dict({"type": "plc", "code": "P9", "temp": 40.0,
                        "kind": "主控 PLC", "note": "冗余字段"})
    assert d.code == "P9"


def test_abstract_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        core.Device("X", 1.0)


def test_subclass_inherits_parent_state_machine():
    plc = core.PLCDevice("P1", 50.0)
    assert plc.status == core.STATUS_STOP and not plc.running
    plc.start()
    assert plc.running
    with pytest.raises(core.AlreadyRunningError):
        plc.start()
    with pytest.raises(core.NotRunningError):
        core.VFDDevice("V9", 30.0).stop()


def test_overridden_start_calls_super_first():
    """B 档核心口径：子类 start() 里必须借父类实现，而不是另起炉灶。"""
    src = inspect.getsource(core.PLCDevice.start)
    assert "super().start()" in src
    line = core.PLCDevice("P1", 50.0).start()
    assert "启动" in line and "扫描周期" in line           # 父类动作 + 子类动作都在


def test_overridden_stop_calls_super():
    vfd = core.VFDDevice("V1", 40.0, freq_hz=45.0)
    vfd.start()
    assert "频率回零" in vfd.stop()
    assert vfd.status == core.STATUS_STOP


def test_super_init_not_skipped():
    """工单避坑第一条：漏 super().__init__ → 父类属性全空。这里反向锁死。"""
    plc = core.PLCDevice("P1", 55.5, scan_ms=80)
    for field in ("code", "temp", "warn", "danger", "status", "logs"):
        assert hasattr(plc, field), "父类字段 %s 未初始化" % field
    assert plc.temp == 55.5 and plc.family == "PLC 控制器"


def test_scan_cycle_three_steps_in_order():
    plc = core.PLCDevice("P1", 40.0, scan_ms=100)
    line = plc.scan_cycle()
    assert "输入采样" in line and "程序执行" in line and "输出刷新" in line
    assert "第1个扫描周期" in line
    assert "第2个扫描周期" in plc.scan_cycle()


@pytest.mark.parametrize("ms", [0.0, 5000.0, -1.0])
def test_scan_cycle_out_of_range_rejected(ms):
    with pytest.raises(core.UnsafeSettingError):
        core.PLCDevice("P1", 40.0, scan_ms=ms).start()


@pytest.mark.parametrize("hz", [10.0, 70.0, 0.0, 60.5])
def test_set_freq_out_of_range_rejected(hz):
    with pytest.raises(ValueError):
        core.VFDDevice("V1", 40.0).set_freq(hz)


def test_set_freq_within_range_ok():
    vfd = core.VFDDevice("V1", 40.0)
    assert "35.0Hz" in vfd.set_freq(35.0) and vfd.freq_hz == 35.0


def test_sensor_read_once_scales_adc():
    sen = core.SensorDevice("S1", 25.0, range_lo=0.0, range_hi=150.0)
    sen.read_once(4095)
    assert abs(sen.temp - 150.0) < 1e-6
    sen.read_once(0)
    assert sen.temp == 0.0


def test_sensor_read_once_rejects_bad_counts():
    with pytest.raises(core.UnsafeSettingError):
        core.SensorDevice("S1", 25.0).read_once(5000)


def test_sensor_calibrate_moves_zero():
    sen = core.SensorDevice("S1", 25.0, range_lo=0.0, range_hi=150.0)
    sen.calibrate(-1.5)
    assert sen.range_lo == -1.5 and "零点标定" in sen.logs[-1]


def test_temp_range_guard_inherited():
    with pytest.raises(core.UnsafeSettingError):
        core.PLCDevice("P1", 0.0).set_temp(9999.0)


def test_patrol_and_str_are_inherited_and_polymorphic():
    rows = [core.PLCDevice("P1", 96.0, scan_ms=80).patrol(),
            core.VFDDevice("V1", 20.0).patrol()]
    assert "DANGER" in rows[0] and "NORMAL" in rows[1]
    assert "扫描周期" in rows[0] and "设定频率" in rows[1]
    assert "0x" not in str(core.SensorDevice("S1", 30.0))


def test_lineage_and_subclasses():
    subs = {c.__name__ for c in core.subclasses()}
    assert {"PLCDevice", "VFDDevice", "SensorDevice"} <= subs
    assert core.lineage(core.PLCDevice("P1", 1.0)).startswith("PLCDevice → Device")


def test_station_composes_not_inherits():
    """A 档：工位是组合，不是继承——但它能用同一句循环调度所有类型。"""
    assert not issubclass(core.WorkStation, core.Device)
    fleet = [core.PLCDevice("P1", 40.0), core.VFDDevice("V1", 40.0),
             core.SensorDevice("S1", 40.0)]
    st = core.WorkStation("ST-01", fleet)
    assert len(st.start_all()) == 3
    assert all(d.running for d in fleet)
    assert len(st.stop_all()) == 3 and len(st.ledger()) == 3


def test_station_rejects_non_device_member():
    st = core.WorkStation("ST-01")
    with pytest.raises(TypeError):
        st.add(object())
