# -*- coding: utf-8 -*-
"""工单 W08 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

档位判据与 tiers.verdict / cli --tier 同源（工单验收标准表）：
D 读写≥2种格式+基本验证（≥75%）；C 三维验证齐全+bad.csv 可追溯（≥80%）；
B 清洗报告清晰+规范列名（≥90%）；A 达B且 --input 选择输入文件（GBK 演示）。
断言只看本次运行真实落盘的文件与计数，少一个维度都会当场红。
"""
import os

import pytest

from data_fileio import config as C
from data_fileio import core, io_utils, pipeline, tiers

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(HERE, "config", "rules.yaml")
OUT = os.path.join(HERE, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整文件处理，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    return {t["tier"][-2]: t for t in v["tiers"]}


def test_D_two_formats_roundtrip_measured(built):
    _, r = built
    rt = r["roundtrip"]
    assert rt["csv"] and rt["json"], "CSV/JSON 双格式 round-trip 实测必须通过"
    assert os.path.getsize(os.path.join(OUT, "data.csv")) > 0
    assert os.path.getsize(os.path.join(OUT, "data.json")) > 0
    assert r["checked"] >= 1, "基本验证必须真的逐行跑过"


def test_C_three_dimensions_all_hit_and_bad_csv_traceable(built):
    """C 档：缺失/类型/范围三维度每条至少命中 1 次（配置脏样本保证），
    bad.csv 行数与隔离区实测一一对应、每行可追溯到原文。"""
    _, r = built
    dims = r["dimensions"]
    assert set(dims) == set(core.DIMENSIONS)
    for d in core.DIMENSIONS:
        assert dims[d] >= 1, "%s 维度实测 0 条——验证缺失或被删了" % d
    rows = io_utils.read_csv_rows(r["bad_csv"])
    assert len(rows) == len(r["quarantine"]) >= 1
    assert all(set(x) >= {"line", "raw", "dimension", "reason"} for x in rows)
    assert all(x["dimension"] in core.DIMENSIONS for x in rows)


def test_B_clean_report_and_canonical_header(built):
    """B 档：data.csv 表头逐字等于规范列名；清洗报告段含三维度计数。"""
    sections, r = built
    assert r["header_ok"]
    with open(os.path.join(OUT, "data.csv"), encoding="utf-8") as f:
        assert f.readline().strip() == tiers.EXPECTED_HEADER
    text = "\n".join(title + "\n" + "\n".join(x) for title, x in sections)
    assert "清洗报告（三维度实测）" in text and "缺失" in text


def test_A_cli_input_channel_with_gbk_file(built, tmp_path):
    """A 档：命令行 --input/--encoding 真选文件——这里用 GBK 样例实跑 CLI。"""
    src = tmp_path / "现场数据.csv"
    src.write_bytes(
        "code,temp,press\n产线-甲,50.0,0.40\n产线-乙,err,0.40\n".encode("gbk"))
    out_dir = str(tmp_path / "cli_out")
    rc = pipeline_cli_main(["--quiet", "--outdir", out_dir,
                            "--input", str(src), "--encoding", "gbk"])
    assert rc == 0
    result = io_utils.read_json(os.path.join(out_dir, "result.json"))
    assert result["source"].startswith(str(src))
    assert result["checked"] == 2 and len(result["rows"]) == 1, (
        "GBK 文件应读入 2 行、清洗后剩 1 行（err 行被类型维度隔离）")


def pipeline_cli_main(argv):
    from data_fileio import cli
    return cli.main(argv)


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


def test_gate_fails_below_minimum(built):
    """档位是算出来的：范围维度 0 条（三维不齐），C 档必须判不达标。"""
    v = tiers.verdict(rate=99.0, csv_ok=True, json_ok=True, n_checked=7,
                      dims={"缺失": 1, "类型": 1, "范围": 0},
                      bad_csv_rows=2, n_bad=2, header_ok=True,
                      report_ok=True, input_demo_ok=True)
    assert tiers_of(v)["C"]["pass"] is False


def test_tier_claim_drops_when_capability_removed(built):
    """反向证明：输入文件通道没走通，A 档就该掉到 B。"""
    _, r = built
    m = r["tiers"]["measured"]
    down = tiers.verdict(rate=r["style_rate"], csv_ok=True, json_ok=True,
                         n_checked=m["n_checked"], dims=m["dims"],
                         bad_csv_rows=m["bad_csv_rows"], n_bad=m["n_bad"],
                         header_ok=m["header_ok"], report_ok=True,
                         input_demo_ok=False)
    got = tiers_of(down)
    assert not got["A"]["pass"] and got["B"]["pass"] and got["D"]["pass"]


def test_gates_are_externalized_in_rules_yaml():
    """门槛数字外置在 rules.yaml 的 tiers 段，config.py 读出并生效。"""
    cfg = C.load_config(CFG)
    gates = cfg.tier_gates()
    assert gates.get("D") == 75.0 and gates.get("B") == 90.0
    v = tiers.verdict(rate=78.0, csv_ok=True, json_ok=True, n_checked=7,
                      dims={"缺失": 1, "类型": 1, "范围": 1},
                      bad_csv_rows=3, n_bad=3, header_ok=True,
                      report_ok=True, input_demo_ok=True,
                      gates=tiers.gates_from(gates))
    got = tiers_of(v)
    assert got["D"]["pass"] and not got["C"]["pass"], (
        "78% 应达 D(≥75) 而不达 C(≥80)——门槛必须来自 rules.yaml")


def test_report_contains_manual_items(built):
    """人工答辩项如实写进报告，机器不代判。"""
    sections, _ = built
    text = "\n".join("\n".join(x) for _t, x in sections)
    assert "人工答辩项" in text and tiers.manual
