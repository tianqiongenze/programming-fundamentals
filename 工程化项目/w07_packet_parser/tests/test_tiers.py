# -*- coding: utf-8 -*-
"""工单 W07 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

档位判据与 tiers.verdict / cli --tier 同源（工单验收标准表）：
D 处理≥2种格式+使用正则（≥75%）；C 三格式全通+字典结构统一（≥80%）；
B ≥3种格式+缺字段/乱序容错（≥90%）；A 达B且批量转换多个样本文件+
输出转换统计（产物回读行数与实测计数一致）。
断言只看本次运行真实产生的解析结果与落盘文件，虚报格式覆盖会当场红。
"""
import inspect
import os

import pytest

from packet_parser import config as C
from packet_parser import core, io_utils, pipeline, tiers

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(HERE, "config", "rules.yaml")
OUT = os.path.join(HERE, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整解析，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    return {t["tier"][-2]: t for t in v["tiers"]}


def test_artifacts_exist_and_are_real(built):
    """产物真实性：report.txt / result.json 落盘且字节 > 1000，报告含四档判定。"""
    _, r = built
    report = os.path.join(OUT, "report.txt")
    assert os.path.exists(report) and os.path.getsize(report) > 1000
    assert os.path.getsize(os.path.join(OUT, "result.json")) > 1000
    text = open(report, encoding="utf-8").read()
    assert "验收档位判定（实测）" in text and "实测达成档位" in text
    assert "人工答辩项" in text, "人工判定项必须在报告里明列"


def test_D_two_formats_and_regex_actually_used(built):
    _, r = built
    assert len(r["by_format"]) >= 2, "工单 D 档要求实测解析≥2 种格式"
    assert r["tiers"]["measured"]["n_regex_kv"] >= 1, (
        "kv 通道必须真的走通（正则提取键值的实测证据）")
    src = inspect.getsource(core)
    assert "re.compile" in src and "finditer" in src, "键值提取必须真是正则实现"


def test_C_all_three_formats_and_uniform_dict(built):
    """C 档：json/kv/csv 三种格式全通，且成功行字典键集合实测一致。"""
    _, r = built
    assert {"json", "kv", "csv"} <= set(r["by_format"])
    assert r["uniform_structure"]
    keys = {tuple(sorted(d.keys())) for d in r["rows"]}
    assert len(keys) == 1, "实测键集合不止一种 → 字典结构不统一"


def test_B_tolerance_measured_not_claimed(built):
    """B 档：缺字段报文隔离不崩、乱序键值报文实测解析通过、统计自洽。"""
    _, r = built
    ft = r["fault_tolerance"]
    assert ft["out_of_order_ok"] and ft["missing_field_ok"]
    assert r["stats_ok"] and r["bad"] >= 1
    assert all(b["reason"] for b in r["quarantine"]), "隔离区必须有归因"


def test_A_batch_files_converted_with_stats(built):
    """A 档：output/samples/ 多个样本文件真实读盘转换，产物行数与计数一致。"""
    _, r = built
    b = r["batch"]
    gates = tiers.gates_from(C.load_config(CFG))
    assert b["files"] >= int(gates["A_min_batch_files"]), "工单 A 档要批量多个文件"
    assert b["rows"] == b["n_ok"] >= 1, "统计必须与产物回读行数一致"
    assert b["n_fail"] >= 1, "样本里必须真的含被隔离的坏行（容错实测）"
    for name in ("shift_a", "shift_b", "shift_c"):
        out = os.path.join(OUT, "converted", name + ".json")
        assert os.path.exists(out), "逐文件产物必须落盘: %s" % out
        assert len(io_utils.read_json(out)) > 0
    conv = r["artifacts"]["converted.json"]
    assert os.path.exists(conv["path"]) and conv["bytes"] > 100
    assert len(io_utils.read_json(conv["path"])) == r["parsed"] == conv["rows"]


def test_A_measured_style_rate_is_at_least_90(built):
    _, r = built
    assert r["style_rate"] >= 90.0, (
        "B/A 档门槛≥90%%，实测 %.1f%%（引擎 %s）"
        % (r["style_rate"], r["style_engine"]))


def test_all_four_tiers_pass_and_claim_is_highest(built):
    _, r = built
    got = tiers_of(r["tiers"])
    for key in ("D", "C", "B", "A"):
        assert got[key]["pass"], "%s 档实测未达标: %s" % (key, got[key])
    assert r["tiers"]["claimed"] == "优(A)"


def _down(built, **patch):
    """反向证明：只改一个实测值走 verdict，承诺档位必须如实下降。"""
    _, r = built
    m = r["tiers"]["measured"]
    args = {"gates": tiers.GATES, "rate": 100.0, "formats": m["formats"],
            "n_regex_kv": m["n_regex_kv"], "uniform": m["uniform"],
            "n_bad": m["n_bad"], "stats_ok": True,
            "out_of_order_ok": m["out_of_order_ok"],
            "missing_field_ok": m["missing_field_ok"],
            "batch": dict(m["batch"])}
    args.update(patch)
    return tiers.verdict(**args)


def test_gate_fails_below_minimum(built):
    """档位是算出来的：只解析出 1 种格式，D 档必须判不达标。"""
    v = tiers.verdict(gates=tiers.GATES, rate=99.0, formats=["json"],
                      n_regex_kv=0, uniform=True, n_bad=1, stats_ok=True,
                      out_of_order_ok=True, missing_field_ok=True,
                      batch={"files": 3, "lines": 9, "n_ok": 8, "n_fail": 1,
                             "rows": 8})
    assert tiers_of(v)["D"]["pass"] is False


def test_claim_drops_when_tolerance_removed(built):
    """反向 1：删掉容错样本（乱序报文不再能解析），B/A 档必须落空只剩 C。"""
    down = _down(built, out_of_order_ok=False)
    got = tiers_of(down)
    assert got["D"]["pass"] and got["C"]["pass"]
    assert not got["B"]["pass"] and not got["A"]["pass"]
    assert down["claimed"] == "良好(C)"


def test_claim_drops_when_batch_files_missing(built):
    """反向 2：批量转换文件没落盘（产物回读 0 行），A 档就该掉到 B。"""
    _, r = built
    b = dict(r["tiers"]["measured"]["batch"], rows=0)
    down = _down(built, batch=b)
    got = tiers_of(down)
    assert not got["A"]["pass"] and got["B"]["pass"]
    assert down["claimed"] == "优秀(B)"


def test_claim_drops_when_sample_count_shrinks(built):
    """反向 3：样本文件只剩 2 个（工单要批量多个），A 档必须落空。"""
    _, r = built
    b = dict(r["tiers"]["measured"]["batch"], files=2)
    down = _down(built, batch=b)
    assert tiers_of(down)["A"]["pass"] is False
    assert down["claimed"] == "优秀(B)"


def test_claim_drops_when_dict_structure_splits(built):
    """反向 4：成功行键集合不一致（结构不统一），C 以上全部落空。"""
    down = _down(built, uniform=False)
    got = tiers_of(down)
    assert not got["C"]["pass"] and not got["B"]["pass"]
    assert got["D"]["pass"] and down["claimed"] == "及格(D)"
