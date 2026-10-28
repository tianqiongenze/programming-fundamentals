# -*- coding: utf-8 -*-
"""工单 W10 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

档位判据与 tiers.verdict / cli --tier 同源（工单验收标准表）：
D 图像标注+PDF 生成（≥80%）；C PDF 含图+表+结论三要素（≥85%）；
B 排版专业：中文字体+统一边距（≥90%）；A 达B且多页（封面+概览+明细）。
标注图/PDF 全部读回磁盘实测——Pillow 没画、reportlab 没嵌图都会当场红。
"""
import os

import pytest

from daily_report import config as C
from daily_report import pipeline, tiers

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(HERE, "config", "rules.yaml")
OUT = os.path.join(HERE, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整日报，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    return {t["tier"][-2]: t for t in v["tiers"]}


def test_D_annotated_image_and_pdf_on_disk(built):
    _, r = built
    img = r["image"]
    assert img["path"] and os.path.exists(img["path"])
    assert img["size"] == [400, 300], "工单要求 400×300 统一尺寸（读回实测）"
    assert img["bytes"] > 1000 and img["boxes"] >= 2, "红框标注必须真的画了"
    assert r["pdf"]["path"] and os.path.getsize(r["pdf"]["path"]) > 2000


def test_C_pdf_three_elements_image_table_conclusion(built):
    """C 档三要素：图确实内嵌（PDF 字节里有 /Image），表与结论进正文。"""
    _, r = built
    assert r["pdf"]["has_image"], "PDF 未内嵌标注图（字节探测失败）"
    assert r["pdf"]["has_table"]
    assert r["pdf"]["conclusion"], "story 正文未扫描到结论文本（PDF 缺要素）"
    text = open(os.path.join(OUT, "report.txt"), encoding="utf-8").read()
    assert "结论" in text and "合格率" in text


def test_B_professional_layout_font_and_margins(built):
    _, r = built
    assert r["pdf"]["font_ok"], "中文字体未注册（工单要求④）"
    assert r["pdf"]["layout_ok"], "页边距/排版参数未显式设定"
    assert len(r["pdf"]["font_sizes"]) >= 3, "工单 B 档：字号层级≥3 级实测"
    assert all(0 < v <= 60 for v in r["pdf"]["margins_mm"].values()), (
        "页边距必须从 doc 对象回读实测")


def test_A_multipage_cover_overview_detail(built):
    """A 档：pypdf 读回页数≥3（封面+首页概览+次页明细）——多页是实测的。"""
    _, r = built
    assert r["pdf"]["pages"] >= 2
    assert tiers_of(r["tiers"])["A"]["functional"]


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
    """档位是算出来的：PDF 只有 1 页（没有次页明细），A 档必须判不达标。"""
    v = tiers.verdict(rate=99.0, img_bytes=8000, img_size=[400, 300],
                      pdf_bytes=50000, has_image=True, has_table=True,
                      has_conclusion=True, font_ok=True, layout_ok=True,
                      pages=1, font_levels=3,
                      margins_mm={"leftMargin": 20.0, "rightMargin": 20.0,
                                  "topMargin": 20.0, "bottomMargin": 20.0},
                      aligns=["封面标题居中"])
    assert tiers_of(v)["A"]["pass"] is False


def test_B_fails_when_font_levels_below_three(built):
    """反向证明：字号只有 2 级（层级被删），B/A 档必须判不达标。"""
    v = tiers.verdict(rate=99.0, img_bytes=8000, img_size=[400, 300],
                      pdf_bytes=50000, has_image=True, has_table=True,
                      has_conclusion=True, font_ok=True, layout_ok=True,
                      pages=3, font_levels=2,
                      margins_mm={"leftMargin": 20.0, "rightMargin": 20.0,
                                  "topMargin": 20.0, "bottomMargin": 20.0},
                      aligns=["封面标题居中"])
    got = tiers_of(v)
    assert got["C"]["pass"] and not got["B"]["pass"]


def test_C_fails_when_conclusion_missing(built):
    """反向证明：正文里没扫到结论文本（三要素缺一），C 档必须判不达标。"""
    v = tiers.verdict(rate=99.0, img_bytes=8000, img_size=[400, 300],
                      pdf_bytes=50000, has_image=True, has_table=True,
                      has_conclusion=False, font_ok=True, layout_ok=True,
                      pages=3, font_levels=3,
                      margins_mm={"leftMargin": 20.0, "rightMargin": 20.0,
                                  "topMargin": 20.0, "bottomMargin": 20.0},
                      aligns=["封面标题居中"])
    got = tiers_of(v)
    assert got["D"]["pass"] and not got["C"]["pass"] and not got["B"]["pass"]


def test_tier_claim_drops_when_capability_removed(built):
    """反向证明：标注图没生成（0 字节），D 档就该塌方，但 B 档要素不受牵连。"""
    _, r = built
    m = r["tiers"]["measured"]
    down = tiers.verdict(rate=r["style_rate"],
                         img_bytes=0, img_size=m["img_size"],
                         pdf_bytes=m["pdf_bytes"], has_image=m["has_image"],
                         has_table=True, has_conclusion=True,
                         font_ok=m["font_ok"], layout_ok=m["layout_ok"],
                         pages=m["pages"], font_levels=m["font_levels"],
                         margins_mm=m["margins_mm"], aligns=m["aligns"])
    got = tiers_of(down)
    assert not got["D"]["pass"] and got["B"]["pass"]


def test_gates_are_externalized_in_rules_yaml(built):
    """门槛数字外置在 rules.yaml 的 tiers 段，config.py 读出并生效。"""
    cfg = C.load_config(CFG)
    gates = cfg.tier_gates()
    assert gates.get("D") == 80.0 and gates.get("B") == 90.0
    _, r = built
    m = r["tiers"]["measured"]
    v = tiers.verdict(rate=82.0, img_bytes=m["img_bytes"],
                      img_size=m["img_size"], pdf_bytes=m["pdf_bytes"],
                      has_image=m["has_image"], has_table=m["has_table"],
                      has_conclusion=m["has_conclusion"],
                      font_ok=m["font_ok"], layout_ok=m["layout_ok"],
                      pages=m["pages"], font_levels=m["font_levels"],
                      margins_mm=m["margins_mm"], aligns=m["aligns"],
                      gates=tiers.gates_from(gates))
    got = tiers_of(v)
    assert got["D"]["pass"] and not got["C"]["pass"], (
        "82% 应达 D(≥80) 而不达 C(≥85)——门槛必须来自 rules.yaml")


def test_report_contains_manual_items(built):
    """人工答辩项（排版观感等主观项）如实写进报告，机器不代判。"""
    sections, _ = built
    text = "\n".join("\n".join(x) for _t, x in sections)
    assert "人工答辩项" in text and tiers.manual
