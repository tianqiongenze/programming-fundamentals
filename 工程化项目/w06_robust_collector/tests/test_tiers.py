# -*- coding: utf-8 -*-
"""工单 W06 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

档位判据与 tiers.verdict / cli --tier 同源（工单验收标准表）：
D 处理≥2种异常+基本日志（规范率≥75%）；C 三级日志分明+统计正确（≥80%）；
B ≥3种异常+完整finally+日志定位到行（≥90%）；A 达B且 bad_records.csv 备查。
断言只看本次运行真实产生的文件与计数，print 冒充日志会当场红。
"""
import os

import pytest

from robust_collector import config as C
from robust_collector import io_utils, pipeline, tiers

CFG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "config", "rules.yaml")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整采集，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    """tiers.verdict 的返回 → {档位字母: 判定}（实测结果与手工构造走同一口径）。"""
    return {t["tier"][-2]: t for t in v["tiers"]}


def test_D_catches_at_least_two_real_exception_types(built):
    _, r = built
    assert len(r["caught_exceptions"]) >= 2, (
        "工单 D 档要求实测捕获≥2 种异常，本次: %s" % r["caught_exceptions"])
    assert "FileNotFoundError" in r["caught_exceptions"], "现场文件缺失路径必须真实触发"


def test_D_run_log_is_a_real_logging_file(built):
    _, r = built
    log_path = r["log"]["path"]
    assert log_path.endswith("run.log") and os.path.exists(log_path)
    assert os.path.getsize(log_path) > 0, "logging 必须真落盘，不是 print"


def test_C_three_log_levels_all_present(built):
    """三级日志分明：INFO/WARNING/ERROR 在 run.log 里各自≥1 条（文件反读实测）。"""
    _, r = built
    lv = r["log"]["levels"]
    for level in ("INFO", "WARNING", "ERROR"):
        assert lv.get(level, 0) >= 1, "%s 级日志缺失（run.log 实测）" % level


def test_C_statistics_are_self_consistent(built):
    _, r = built
    assert r["stats_ok"] and r["ok"] + r["bad"] == r["total"]
    assert r["bad"] >= 1, "配置里的脏样本必须真的被隔离"


def test_B_finally_actually_ran_and_log_locates_rows(built):
    """B 档：完整 finally 实测标记 + 每条隔离行都能在日志里定位到'第N行'。"""
    _, r = built
    assert r["ran_finally"], "starter 回读的 finally 收尾必须真实执行"
    assert r["log"]["row_refs"] >= r["bad"], "每条坏数据都要有可定位行号"
    assert len(r["caught_exceptions"]) >= 3


def test_A_bad_records_csv_matches_quarantine(built):
    """A 档：脏数据自动写入 bad_records.csv，行数与隔离区实测一一对应。"""
    _, r = built
    path = r["bad_records_csv"]
    assert os.path.exists(path)
    rows = io_utils.read_csv_rows(path)
    assert len(rows) == r["bad"]
    assert all(set(x) >= {"line", "raw", "reason"} for x in rows)


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
    """档位是算出来的：只捕获到 1 种异常，D 档必须判不达标。"""
    v = tiers.verdict(rate=99.0, n_exc_types=1, ran_finally=True,
                      levels={"INFO": 5, "WARNING": 3, "ERROR": 1},
                      row_refs=3, n_bad=3, stats_ok=True,
                      bad_csv_rows=3, log_lines=9)
    assert tiers_of(v)["D"]["pass"] is False


def test_tier_claim_drops_when_capability_removed(built):
    """反向证明：bad_records.csv 没落盘（0 行），A 档就该掉到 B。"""
    _, r = built
    m = r["tiers"]["measured"]
    down = tiers.verdict(rate=r["style_rate"],
                         n_exc_types=m["n_exc_types"],
                         ran_finally=m["ran_finally"], levels=m["levels"],
                         row_refs=m["row_refs"], n_bad=m["n_bad"],
                         stats_ok=True, bad_csv_rows=0,
                         log_lines=m["log_lines"])
    got = tiers_of(down)
    assert not got["A"]["pass"] and got["B"]["pass"] and got["D"]["pass"]
