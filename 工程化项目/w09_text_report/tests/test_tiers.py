# -*- coding: utf-8 -*-
"""工单 W09 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

档位判据与 tiers.verdict / cli --tier 同源（工单验收标准表）：
D 分词正确+词云 PNG（≥80%）；C 停用词处理+Top10 词频图（≥85%）；
B 中文字体词云+Top20 关键词+洞察有数据（≥90%）；A 达B且分组对比词云。
所有 PNG 以磁盘字节数实测——缺库/缺字体只能如实判缺，写不进真图就红。
"""
import os

import pytest

from text_report import config as C
from text_report import core, pipeline, tiers

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(HERE, "config", "rules.yaml")
OUT = os.path.join(HERE, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整分析，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    return {t["tier"][-2]: t for t in v["tiers"]}


def test_D_tokenizer_output_and_wordcloud_png(built):
    _, r = built
    assert r["channel"] in ("jieba-精确模式", "二元词兜底(未装 jieba)")
    assert r["total_tokens"] > 0, "分词必须有产出（工单 D：分词正确）"
    png = os.path.join(OUT, "wordcloud.png")
    assert os.path.exists(png), "词云 PNG 必须真实落盘"
    assert os.path.getsize(png) > 1000, "词云字节数过小=不是真实渲染"


def test_C_stopwords_and_top10_chart(built):
    """C 档：Top 词里零停用词；matplotlib 词频图落盘且非空壳。"""
    _, r = built
    assert r["stop_ok"], "Top 词中残留停用词——过滤没生效"
    assert r["tiers"]["measured"]["stop_hits"] >= 1, (
        "停用词必须真实命中过（过滤前计数>0），否则'处理得当'无从谈起")
    assert all(w not in core.STOP for w in [t["word"] for t in r["top"]])
    chart = os.path.join(OUT, "top10.png")
    assert os.path.exists(chart) and os.path.getsize(chart) > 1000


def test_B_font_top20_and_data_backed_insight(built):
    """B 档：词云走中文字体（课程包 ZH_Font 候选链）、Top20 有货、洞察含实测数字。"""
    _, r = built
    assert r["font_used"] != "内置默认", "工单避坑：禁止默认字体出方块"
    assert len(r["top20"]) >= 10
    assert any(ch.isdigit() for ch in r["insight"]) and len(r["insight"]) <= 150


def test_A_group_clouds_compare(built):
    """A 档：按系统分组（传动 vs 电气）各出词云，磁盘实测≥2 张。"""
    _, r = built
    names = r["artifacts"]["group_clouds"]["paths"]
    sizes = [os.path.getsize(os.path.join(OUT, n)) for n in names]
    assert len([s for s in sizes if s > 1000]) >= 2, (
        "分组对比词云不足 2 张: %s" % names)
    assert {"传动系统", "电气系统"} <= set(r["groups"])


def test_B_measured_style_rate_is_at_least_90(built):
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
    """档位是算出来的：词云没渲染出来（0 字节），D 档必须判不达标。"""
    v = tiers.verdict(rate=99.0, n_tokens=30, cloud_bytes=0, stop_ok=True,
                      chart_bytes=20000, font_ok=True, top20_count=20,
                      insight_ok=True, group_cloud_bytes=[5000, 5000],
                      stop_hits=2)
    assert tiers_of(v)["D"]["pass"] is False


def test_C_fails_when_stopwords_never_hit(built):
    """反向证明：原文里从未出现停用词（命中 0 处），"处理得当"无从谈起。"""
    v = tiers.verdict(rate=99.0, n_tokens=30, cloud_bytes=5000, stop_ok=True,
                      chart_bytes=20000, font_ok=True, top20_count=20,
                      insight_ok=True, group_cloud_bytes=[5000, 5000],
                      stop_hits=0)
    assert tiers_of(v)["C"]["pass"] is False


def test_tier_claim_drops_when_capability_removed(built):
    """反向证明：分组词云拿掉（0 张），A 档就该掉到 B。"""
    _, r = built
    m = r["tiers"]["measured"]
    down = tiers.verdict(rate=r["style_rate"], n_tokens=m["n_tokens"],
                         cloud_bytes=m["cloud_bytes"], stop_ok=m["stop_ok"],
                         chart_bytes=m["chart_bytes"], font_ok=m["font_ok"],
                         top20_count=m["top20_count"],
                         insight_ok=m["insight_ok"], group_cloud_bytes=[],
                         stop_hits=m["stop_hits"])
    got = tiers_of(down)
    assert not got["A"]["pass"] and got["B"]["pass"] and got["D"]["pass"]


def test_gates_are_externalized_in_rules_yaml(built):
    """门槛数字外置在 rules.yaml 的 tiers 段，config.py 读出并生效。"""
    cfg = C.load_config(CFG)
    gates = cfg.tier_gates()
    assert gates.get("D") == 80.0 and gates.get("B") == 90.0
    _, r = built
    m = r["tiers"]["measured"]
    v = tiers.verdict(rate=82.0, n_tokens=m["n_tokens"],
                      cloud_bytes=m["cloud_bytes"], stop_ok=m["stop_ok"],
                      chart_bytes=m["chart_bytes"], font_ok=m["font_ok"],
                      top20_count=m["top20_count"],
                      insight_ok=m["insight_ok"],
                      group_cloud_bytes=[5000, 5000],
                      stop_hits=m["stop_hits"],
                      gates=tiers.gates_from(gates))
    got = tiers_of(v)
    assert got["D"]["pass"] and not got["C"]["pass"], (
        "82% 应达 D(≥80) 而不达 C(≥85)——门槛必须来自 rules.yaml")


def test_report_contains_manual_items(built):
    """人工答辩项（词云美观度等主观项）如实写进报告，机器不代判。"""
    sections, _ = built
    text = "\n".join("\n".join(x) for _t, x in sections)
    assert "人工答辩项" in text and tiers.manual
