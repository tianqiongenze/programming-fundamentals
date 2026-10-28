# -*- coding: utf-8 -*-
"""工单 W05 四档验收断言——每档都钉在"实测值"上，功能删掉就必须红。

档位判据与 tiers.verdict / cli --tier 同源（工单验收标准表）：
D 1基类+2子类+继承覆盖（AST 统计，≥75%）；C 多态真实输出互异+docstring
AST 覆盖率 100%（≥80%）；B ≥3子类+覆盖方法内 super() 协作（≥90%）；
A 达 B 且 is-a 判断正文实测达标（字数/"组合"提及数）+组合代码证据。
断言只看本次运行 AST 真实统计与真实调用输出，自称会当场红。
"""
import os

import pytest

from device_family import config as C
from device_family import pipeline, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "rules.yaml")
OUT = os.path.join(ROOT, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整继承体系流程，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    """tiers.verdict 的返回 → {档位字母: 判定}（实测与手工构造同一口径）。"""
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


def test_D_family_measured_by_ast(built):
    """D 档：基类/子类/覆盖处数来自 AST 真实统计，不是注释里自称。"""
    _, r = built
    fam = r["ast_family"]
    assert fam["n_base"] >= 1
    assert fam["n_subs"] >= 2 and set(fam["sub_names"]) >= {"PLCDevice",
                                                            "VFDDevice"}
    assert fam["n_overrides"] >= 1, "工单 D 档『继承覆盖』必须 AST 数得出"


def test_C_polymorphic_outputs_are_real_and_distinct(built):
    """C 档：真实遍历不同子类实例调同名 start()，实测输出逐条互不相同。"""
    _, r = built
    poly = r["poly"]
    assert poly["calls"] >= 2
    assert poly["distinct"] == poly["calls"], (
        "多态输出必须各不相同（%d 调用/%d 互异）——各子类跑各自实现"
        % (poly["calls"], poly["distinct"]))
    started = "\n".join(r["started"])
    assert "上电自检" in started and "爬升" in started, \
        "报告要写进 PLC/变频器各自的实测输出原文"


def test_C_docstring_census_full_coverage(built):
    """C 档『docstring 齐全』：AST 覆盖率必须 100%，缺一行就红。"""
    _, r = built
    fam = r["ast_family"]
    assert fam["doc_filled"] == fam["doc_total"], (
        "docstring 缺口: %d/%d" % (fam["doc_filled"], fam["doc_total"]))
    assert fam["doc_total"] >= 30, "清点规模异常（应覆盖家族全部类与方法）"


def test_B_super_calls_found_in_overrides(built):
    """B 档：覆盖父类具体实现的方法里 AST 真实找到 super() 调用，缺口为 0。"""
    _, r = built
    fam = r["ast_family"]
    assert fam["n_subs"] >= 3
    assert fam["n_super"] >= 3 and fam["gaps"] == 0, fam["gap_rows"]
    assert r["style_rate"] >= 90.0, (
        "B/A 档门槛≥90%%，实测 %.1f%%（引擎 %s）"
        % (r["style_rate"], r["style_engine"]))


def test_A_is_a_doc_measured_and_composition_real(built):
    """A 档：is-a 判断正文真实存在且字数/条目数达标；组合证据来自 issubclass。"""
    _, r = built
    isa = r["is_a_doc_stats"]
    gates = tiers.gates_from(C.load_config(CFG))
    assert isa["present"] and os.path.exists(isa["path"])
    assert isa["chars"] >= int(gates["A_min_doc_chars"])
    assert isa["mentions"] >= int(gates["A_min_doc_mentions"])
    assert r["composition_used"], "WorkStation 必须以组合（非 Device 子类）落地"


def test_all_four_tiers_pass_and_claim_is_highest(built):
    _, r = built
    got = tiers_of(r["tiers"])
    for key in ("D", "C", "B", "A"):
        assert got[key]["pass"], "%s 档实测未达标: %s" % (key, got[key])
    assert r["tiers"]["claimed"] == "优(A)"


def _down(built, **patch):
    """反向证明：只改一个实测值走 verdict，承诺档位必须如实下降。"""
    _, r = built
    fam, isa = r["ast_family"], r["is_a_doc_stats"]
    args = {"gates": tiers.GATES, "rate": 100.0,
            "n_base": fam["n_base"], "n_subs": fam["n_subs"],
            "n_overrides": fam["n_overrides"],
            "doc_filled": fam["doc_filled"], "doc_total": fam["doc_total"],
            "poly_kinds": fam["poly_kinds"],
            "poly_calls": r["poly"]["calls"],
            "poly_distinct": r["poly"]["distinct"],
            "n_super": fam["n_super"], "super_gaps": fam["gaps"],
            "isa_present": isa["present"], "isa_chars": isa["chars"],
            "isa_mentions": isa["mentions"], "comp_ok": True}
    args.update(patch)
    return tiers.verdict(**args)


def test_claim_drops_when_subclass_removed(built):
    """反向 1：抽掉一个子类（只剩 2 个），B/A 档必须落空，承诺掉到 C。"""
    down = _down(built, n_subs=2, n_super=2)
    got = tiers_of(down)
    assert got["D"]["pass"] and got["C"]["pass"]
    assert not got["B"]["pass"] and not got["A"]["pass"]
    assert down["claimed"] == "良好(C)"


def test_claim_drops_when_super_call_removed(built):
    """反向 2：覆盖方法里删掉一处 super()（出现缺口），B/A 必须落空。"""
    down = _down(built, super_gaps=1)
    got = tiers_of(down)
    assert not got["B"]["pass"] and not got["A"]["pass"]
    assert got["C"]["pass"] and down["claimed"] == "良好(C)"


def test_claim_drops_when_is_a_doc_missing(built):
    """反向 3：is-a 判断正文没写（文档不存在），A 档必须掉到 B。"""
    down = _down(built, isa_present=False, isa_chars=0, isa_mentions=0)
    got = tiers_of(down)
    assert not got["A"]["pass"] and got["B"]["pass"]
    assert down["claimed"] == "优秀(B)"


def test_claim_drops_when_docstring_gap_appears(built):
    """反向 4：docstring 缺 3 处（覆盖率 <100%），C/B/A 连锁落空只剩 D。"""
    _, r = built
    total = r["ast_family"]["doc_total"]
    down = _down(built, doc_filled=total - 3, doc_total=total)
    got = tiers_of(down)
    assert not got["C"]["pass"] and not got["B"]["pass"]
    assert got["D"]["pass"] and down["claimed"] == "及格(D)"
