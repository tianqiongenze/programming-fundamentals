# -*- coding: utf-8 -*-
"""工单 W04《工业设备类设计》验收标准逐档断言（D/C/B/A）。

档位门槛唯一来源是 cli.TIERS（与工单表格同序），功能条逐档写死：
  D 1 类 + ≥2 属性 + ≥2 方法 + ≥2 实例（且必须显式 __init__）
  C 方法含状态校验（已启动再 start 被拦）
  B ≥3 属性 + ≥3 方法 + 3 实例 + __str__ + get_status + 规范率≥90%
  A 达 B 且方法间协作（stop 后自动记录日志字符串）
"""
import inspect
import os

import pytest

from device_model import cli
from device_model import config as C
from device_model import core, pipeline, stylecheck

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "output", "report.txt")
ATTRS = ("code", "kind", "temp", "status")


@pytest.fixture(scope="module")
def cfg():
    return C.load_config(os.path.join(ROOT, "config", "rules.yaml"))


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    return pipeline.run(C.load_config(os.path.join(ROOT, "config", "rules.yaml")),
                        out_dir=str(tmp_path_factory.mktemp("out")))


def _public_methods(d):
    return [m for m in dir(d) if not m.startswith("_") and callable(getattr(d, m))]


# ── 四档共同的规范率门槛（工单每档都写"规范率≥N%"）──
@pytest.mark.parametrize("tier,need,gate", cli.TIERS)
def test_style_rate_meets_each_tier(tier, need, gate):
    stats = stylecheck.scan_project(ROOT)
    assert stats["rate"] >= gate, \
        "%s 要求规范率≥%s%%，实测 %.1f%%（引擎 %s）" % (
            tier, gate, stats["rate"], stats["engine"])


def test_style_checker_is_real_not_stub():
    stats = stylecheck.scan_project(ROOT)
    assert stats["files"] >= 8 and stats["lines"] >= 200
    assert stats["engine_kind"] in ("pycodestyle", "builtin")


# ── 及格(D)：1 类 + 2 属性 + 2 方法 + 2 实例 + 显式 __init__ ──
def test_d_tier_class_with_explicit_init_and_2_instances(cfg):
    assert inspect.isclass(core.Device)
    assert "__init__" in vars(core.Device), "工单任务2 要求显式 __init__ 构造方法"
    init = vars(core.Device)["__init__"]
    assert not getattr(init, "__isdataclass__", False)
    assert list(inspect.signature(init).parameters)[:2] == ["self", "code"]
    src = inspect.getsource(core.Device.__init__)
    for name in ATTRS:
        assert ("self.%s =" % name) in src or ("self.%s=" % name) in src, \
            "__init__ 应直接给实例属性 %s 赋值（工单 B02：出生即建档）" % name
    devs = core.build_devices(cfg.items, cfg)
    assert len(devs) >= 2
    assert len(_public_methods(devs[0])) >= 2


# ── 良好(C)：方法含状态校验（已启动再 start 给出提示/拦截）──
def test_c_tier_state_guard_on_double_start():
    d = core.Device("DEV-C", "空压机")
    d.start()
    with pytest.raises(core.AlreadyRunningError):
        d.start()
    with pytest.raises(core.NotRunningError):
        core.Device("DEV-C2", "冷却泵").stop()


def test_c_tier_guard_records_rejection_in_log():
    """C 档校验与 A 档协作的交接点：被拦下的调用也留痕，不静默吞掉。"""
    d = core.Device("DEV-C3", "变频器")
    d.start()
    before = len(d.logs)
    with pytest.raises(core.AlreadyRunningError):
        d.start()
    assert len(d.logs) == before + 1 and "重复启动" in d.logs[-1]


# ── 优秀(B)：≥3 属性 + ≥3 方法 + 3 实例 + __str__ + get_status ──
def test_b_tier_3_attrs_3_methods_3_instances(cfg):
    devs = core.build_devices(cfg.items, cfg)
    assert len(devs) >= 3, "B 档需 3 个实例，配置只给了 %d" % len(devs)
    own = [a for a in ATTRS if a in vars(devs[0])]
    assert len(own) >= 3, "B 档需 ≥3 属性，实得 %s" % own
    assert len(devs[0].__dict__) >= 3
    assert len(_public_methods(devs[0])) >= 3


def test_b_tier_dunder_str_and_get_status():
    assert "__str__" in vars(core.Device), "工单任务4 要求在类内重写 __str__"
    assert "get_status" in vars(core.Device), "工单任务1 点名的方法"
    d = core.Device("DEV-B", "空压机A", temp=96.0)
    text = str(d)
    assert isinstance(text, str) and "DEV-B" in text and "96.0" in text
    assert "0x" not in text, "__str__ 生效后不应再看到内存地址"
    st = d.get_status()
    assert "DANGER" in st and "96.0" in st and d.status in st


def test_b_tier_instances_are_isolated(cfg):
    """工单 B01 误区：改 d1 不影响 d2——各实例各一份属性。"""
    devs = core.build_devices(cfg.items, cfg)
    base = [d.temp for d in devs]
    devs[0].set_temp(base[0] + 7.5)
    after = [d.temp for d in devs]
    assert after[1:] == base[1:] and abs(after[0] - base[0] - 7.5) < 1e-9
    assert devs[0].plant_code == devs[1].plant_code, "类属性才是全厂共享的那一份"


def test_b_tier_temp_range_validation():
    with pytest.raises(core.OutOfRangeError):
        core.Device("DEV-X", "空压机").set_temp(999.0)
    with pytest.raises(ValueError):
        core.Device("DEV-X", "空压机").set_temp(-999.0)


# ── 优(A)：达 B 且方法间有协作（stop 后自动记录日志字符串）──
def test_a_tier_stop_appends_log_string():
    d = core.Device("DEV-A", "空压机", temp=77.0)
    d.start()
    n = len(d.logs)
    line = d.stop()
    assert len(d.logs) == n + 1, "stop 必须自动追加日志（A 档方法间协作）"
    assert isinstance(line, str) and "停机" in line and "77.0" in line
    assert d.logs[-1] == line


def test_a_tier_pipeline_exports_collaboration_logs(ran):
    table = dict(ran)
    key = [t for t in table if t.startswith("方法间协作日志")][0]
    body = "\n".join(str(x) for x in table[key])
    assert "停机（此刻温度" in body, "A 档证据：停机日志字符串要出现在报告里"
    assert body.count("建档出厂") >= 3, "3 台实例各自都要有出厂日志"


# ── 集成：报告四段齐全 + 无规则失效 ──
def test_pipeline_report_sections_and_no_rule_leak(ran, cfg):
    titles = [t for t, _ in ran]
    for need in ("输入口径", "状态校验流水", "巡检台账", "结论与建议"):
        assert any(need in t for t in titles), "缺少报告分节: %s" % need
    fail = dict(ran)["规则失效项（应为空）"]
    assert list(fail) == ["无——三条业务规则全部拦住"]
    assert len(cfg.items) >= 3


# ── 交付证据：已提交的 output/report.txt 必须含真实规范率（防伪造）──
def test_committed_report_contains_measured_style_rate():
    assert os.path.exists(REPORT), "先跑 python run.py 生成 output/report.txt"
    text = open(REPORT, encoding="utf-8").read()
    assert "编码规范率（PEP 8 实测）" in text
    stats = stylecheck.scan_project(ROOT)
    assert ("规范率实测: %.1f%%" % stats["rate"]) in text
