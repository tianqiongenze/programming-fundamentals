# -*- coding: utf-8 -*-
import pytest

from daily_report import core


@pytest.fixture
def kpi():
    return {"line": "一号产线", "planned": 960, "produced": 912, "good": 896, "oee": 86.6}


def test_derive_good_rate(kpi):
    assert core.derive(kpi)["good_rate"] == 0.9825


def test_derive_plan_rate(kpi):
    assert core.derive(kpi)["plan_rate"] == 0.95


def test_derive_zero_produced_no_crash():
    r = core.derive({"line": "X", "planned": 10, "produced": 0, "good": 0, "oee": 0})
    assert r["good_rate"] == 0.0


def test_render_table_shape():
    rows = [core.derive({"line": "A", "planned": 10, "produced": 9, "good": 8, "oee": 50.0})]
    tbl = core.render_table(rows)
    assert len(tbl) == 2 and len(tbl[0]) == 7


def test_render_table_percent_format():
    rows = [core.derive({"line": "A", "planned": 100, "produced": 50, "good": 25, "oee": 10.0})]
    tbl = core.render_table(rows)
    flat = " ".join(str(c) for r in tbl[1:] for c in r)
    assert "50.00%" in flat   # 25/50 = 50.00%


def test_markdown_has_header():
    rows = [core.derive({"line": "A", "planned": 10, "produced": 9, "good": 8, "oee": 50.0})]
    md = core.to_markdown(rows, "日报")
    assert md.startswith("# 日报") and "| 产线 |" in md
