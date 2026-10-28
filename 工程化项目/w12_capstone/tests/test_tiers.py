# -*- coding: utf-8 -*-
"""工单 Z 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

为什么不只测函数：工单是按档位验收的（D 采集≥50 条 / C 两类+图文交付 /
B 三维度清洗 / A 规范率≥95%）。测试与档位同构，学生删了功能还能全绿，
就是测试写错了。
"""
import os

import pytest

from capstone import collector, core, io_utils, pipeline, reporter
from capstone import config as C

CFG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "config", "rules.yaml")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整流水线，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(result):
    return {t["tier"][-2]: t for t in result["tiers"]["tiers"]}


def test_D_collects_at_least_50_real_rows(built):
    _, r = built
    assert r["collect"]["rows"] >= 50, "工单 D 档要求采集模块≥50 条读数"
    assert r["valid"] > 0


def test_D_channel_is_reported_not_assumed(built):
    _, r = built
    assert r["collect"]["channel"] in ("csv", "modbus", "seed")
    assert r["collect"]["detail"], "必须写明这批数从哪个文件/种子来"


def test_D_gate_fails_below_min_rows():
    """档位是算出来的：只采到 49 条，D 档必须判不达标。"""
    dims = {"完整性": 0, "有效性": 0, "范围": 0}
    v = pipeline.tier_verdict(rate=99.0, n_valid=49, n_raw=49,
                              min_rows=50, has_cloud=True, has_pdf=True,
                              dims=dims)
    assert {t["tier"][-2]: t for t in v["tiers"]}["D"]["pass"] is False


def test_C_has_collector_and_reporter_classes():
    """工单 OOP 项：≥2 个类，且真被流水线用上（不是摆样子）。"""
    assert isinstance(collector.Collector, type)
    assert isinstance(reporter.Reporter, type)
    c = collector.Collector(min_rows=5, seed=3)
    rows, meta = c.collect()
    assert len(rows) >= 5 and meta["rows"] == len(rows)


def test_C_pdf_and_wordcloud_actually_written(built):
    _, r = built
    assert r["artifacts"]["deliverable.pdf"], "PDF 图文交付必须存在"
    assert r["artifacts"]["keyword_cloud.png"], "词云必须真实渲染出来"
    assert os.path.getsize(os.path.join(OUT, "deliverable.pdf")) > 1000
    assert os.path.getsize(os.path.join(OUT, "keyword_cloud.png")) > 1000


def test_B_three_dimension_cleaning_counts(built):
    """三维度（完整性/有效性/范围）各自有计数，配置里的脏样本必须被归因。"""
    _, r = built
    dims = r["dimensions"]
    assert set(dims) == set(core.DIMENSIONS)
    assert sum(dims.values()) >= 3, "配置里 4 条脏样本，至少 3 条要被归类"
    assert dims["范围"] >= 2 and dims["完整性"] >= 1 and dims["有效性"] >= 1


def test_B_quarantine_keeps_evidence_per_row(built):
    """隔离区不是"扔了就算清洗"——每条坏数据都要留下行号、原文和归因。"""
    _, r = built
    assert r["quarantine"] > 0
    rows = io_utils.read_json(os.path.join(OUT, "quarantine.json"))
    assert all(set(x) >= {"line", "raw", "dimension", "reason"} for x in rows)
    assert all(x["dimension"] in core.DIMENSIONS for x in rows)


def test_A_measured_style_rate_is_at_least_95(built):
    _, r = built
    assert r["style_rate"] >= 95.0, (
        "A 档门槛≥95%%，实测 %.1f%%（引擎 %s）"
        % (r["style_rate"], r["style_engine"]))


def test_run_log_written_for_troubleshooting(built):
    _, _r = built
    assert os.path.getsize(os.path.join(OUT, "run.log")) > 0


def test_all_four_tiers_pass_and_claim_is_highest(built):
    _, r = built
    got = tiers_of(r)
    for key in ("D", "C", "B", "A"):
        assert got[key]["pass"], "%s 档实测未达标: %s" % (key, got[key])
    assert r["tiers"]["claimed"] == "优(A)"


def test_tier_claim_drops_when_capability_removed(built):
    """反向证明：把 PDF 拿掉，C 档就该掉级——说明档位真由产物决定。"""
    _, r = built
    down = pipeline.tier_verdict(rate=99.0, n_valid=58, n_raw=62,
                                 min_rows=50, has_cloud=False,
                                 has_pdf=False, dims=r["dimensions"])
    got = {t["tier"][-2]: t for t in down["tiers"]}
    assert not got["C"]["pass"] and got["D"]["pass"]
