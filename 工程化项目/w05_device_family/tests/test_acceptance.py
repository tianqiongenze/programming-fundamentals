# -*- coding: utf-8 -*-
"""工单 W05《工业设备继承体系》验收标准逐档断言（D/C/B/A）。

档位门槛唯一来源是 cli.TIERS（与工单表格同序），功能条逐档写死：
  D 1 基类 + 2 子类 + 继承覆盖
  C 多态 start() 调用演示清晰 + docstring 齐全
  B ≥3 子类；规范率≥90%；覆盖方法内用 super() 协作
  A 达 B 且体现 is-a 设计判断（说明为什么不用继承实现某设备）
"""
import inspect
import os

import pytest

from device_family import cli
from device_family import config as C
from device_family import core, pipeline, stylecheck

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "output", "report.txt")
EXPECTED_SUBCLASSES = {"PLCDevice", "VFDDevice", "SensorDevice"}


@pytest.fixture(scope="module")
def cfg():
    return C.load_config(os.path.join(ROOT, "config", "rules.yaml"))


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    return pipeline.run(C.load_config(os.path.join(ROOT, "config", "rules.yaml")),
                        out_dir=str(tmp_path_factory.mktemp("out")))


# ── 四档共同的规范率门槛 ──
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


# ── 及格(D)：1 基类 + 2 子类 + 继承覆盖 ──
def test_d_tier_one_base_two_subclasses_with_override():
    subs = core.subclasses()
    assert len(subs) >= 2, "D 档需 ≥2 个子类，实得 %d" % len(subs)
    assert core.Device in {core.PLCDevice.__mro__[1], core.VFDDevice.__mro__[1]}
    overridden = EXPECTED_SUBCLASSES and {
        m for m in ("start", "stop", "profile")
        if any(m in vars(c) for c in subs)}
    assert {"start", "profile"} <= overridden, "子类必须真的覆盖父类同名方法"
    assert {"type", "code", "temp"} <= set(C.load_config(
        os.path.join(ROOT, "config", "rules.yaml")).items[0].keys())


# ── 良好(C)：多态调用演示清晰 + docstring 齐全 ──
def test_c_tier_polymorphic_start_loop(ran):
    table = dict(ran)
    key = [k for k in table if k.startswith("多态启动流水")][0]
    started = table[key]
    assert len(started) >= 3, "多态演示需 ≥3 台设备跑同一个循环，实得 %d" % len(started)
    families = {core.VFDDevice.family, core.PLCDevice.family}
    assert any(f in " ".join(started) for f in families)
    src = inspect.getsource(pipeline.build)
    assert "d.start() for d in fleet" in src, "多态演示应是一行不含类型分支的推导式"
    assert "isinstance" not in src.split("started = ")[1].split("extras = ")[0]


def test_c_tier_docstrings_complete():
    rows, rate = pipeline._docstring_census()
    assert rate == 100.0, "任务4 要求每个类与方法都有一行 docstring，实测 %.1f%%：%s" % (
        rate, [r for r in rows if "**缺**" in r])
    for cls in [core.Device, core.PLCDevice, core.VFDDevice, core.SensorDevice,
                core.WorkStation]:
        assert inspect.getdoc(cls)
        for name, fn in vars(cls).items():
            if not name.startswith("_") and callable(fn):
                assert inspect.getdoc(fn), "%s.%s 缺 docstring" % (cls.__name__, name)


def test_c_tier_named_subclass_methods():
    """任务2 点名的方法：PLC.scan_cycle()、变频 set_freq()（本项目方法名 VFDDevice）。"""
    assert callable(getattr(core.PLCDevice, "scan_cycle", None))
    assert callable(getattr(core.VFDDevice, "set_freq", None))


# ── 优秀(B)：≥3 子类 + super() 协作 + 规范率≥90% ──
def test_b_tier_at_least_three_subclasses():
    subs = {c.__name__ for c in core.subclasses()}
    assert EXPECTED_SUBCLASSES <= subs, "B 档需 ≥3 子类，实得 %s" % sorted(subs)
    assert "PLCDevice" in subs, "工单点名 PLC 子类"


@pytest.mark.parametrize("cls_name,method", [
    ("PLCDevice", "start"), ("VFDDevice", "start"), ("VFDDevice", "stop")])
def test_b_tier_super_collaboration_in_overrides(cls_name, method):
    cls = getattr(core, cls_name)
    assert method in vars(cls), "%s 未覆盖 %s()" % (cls_name, method)
    assert "super()." in inspect.getsource(vars(cls)[method]), \
        "%s.%s 覆盖里必须用 super() 与父类协作（B 档原文）" % (cls_name, method)


def test_b_tier_super_evidence_in_report(ran):
    rows, hits = pipeline._super_usage()
    assert hits >= 2, "至少要实测到 2 处 super() 协作"
    body = "\n".join(str(x) for _, xs in ran for x in xs)
    assert "覆盖父类实现 → super() 协作: 有" in body
    assert "**无**" not in body


def test_b_tier_subclasses_behave_differently(ran):
    """覆盖要真的"行为不同"：同一句 start()，三类设备输出各不相同。"""
    fleet = [core.from_dict(d) for d in C.load_config(
        os.path.join(ROOT, "config", "rules.yaml")).items]
    lines = [d.start() for d in fleet]
    kinds = {type(d).__name__ for d in fleet}
    assert len(kinds) >= 3
    for k in ("PLCDevice", "VFDDevice"):
        assert any(k.replace("Device", "").lower() in str(d).lower() or k in repr(d)
                   for d in fleet)
    assert len(set(lines)) == len(lines)


# ── 优(A)：is-a 设计判断（说明为什么不用继承实现某设备）──
def test_a_tier_composition_instead_of_inheritance():
    """A 档：代码里真有一个"明知不该继承、所以改用组合"的类。"""
    assert not issubclass(core.WorkStation, core.Device)
    assert not hasattr(core.WorkStation, "temp")
    st = core.WorkStation("ST-A", [core.PLCDevice("P1", 40.0), core.VFDDevice("V1", 40.0)])
    assert len(st.start_all()) == 2 and len(st.ledger()) == 2
    assert "isinstance" not in inspect.getsource(core.WorkStation)


def test_a_tier_is_a_doc_exists_and_substantive():
    doc = os.path.join(ROOT, "docs", "09-is-a设计判断.md")
    assert os.path.exists(doc), "A 档需提交 is-a 设计判断说明"
    text = open(doc, encoding="utf-8").read()
    assert len(text) > 800, "A 档文档太短（%d 字），说不清选型" % len(text)
    for kw in ("is-a", "组合", "继承", "WorkStation", "has-a"):
        assert kw in text, "A 档文档缺关键论证词: %s" % kw


def test_a_tier_doc_referenced_in_report(ran):
    body = "\n".join(str(x) for _, xs in ran for x in xs)
    assert "docs/09-is-a设计判断.md" in body


# ── 集成 ──
def test_pipeline_sections_cover_all_tiers(ran):
    titles = " ".join(t for t, _ in ran)
    for need in ("输入口径", "多态启动流水", "super() 协作证据", "is-a 判断", "结论与建议"):
        assert need in titles, "缺少报告分节: %s" % need


def test_committed_report_contains_measured_style_rate():
    assert os.path.exists(REPORT), "先跑 python run.py 生成 output/report.txt"
    text = open(REPORT, encoding="utf-8").read()
    stats = stylecheck.scan_project(ROOT)
    assert ("规范率实测: %.1f%%" % stats["rate"]) in text
    assert "issubclass(WorkStation, Device) = False" in text
