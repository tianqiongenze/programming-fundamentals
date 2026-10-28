# -*- coding: utf-8 -*-
"""工单 W01《设备参数初始化系统》验收标准逐档断言（D/C/B/A）。

档位数字门槛的唯一来源是 config/rules.yaml 的 tiers: 段（经 tiers.gates 读出，
与工单表格同序同值），测试不另抄一份数字，避免"工单改了测试没改"的脱节；
功能条则逐档写死，跑不过就是没达标。
"""
import os

import pytest

from device_init import cli
from device_init import config as C
from device_init import core, pipeline, stylecheck, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "output", "report.txt")


@pytest.fixture(scope="module")
def cfg():
    return C.load_config(os.path.join(ROOT, "config", "rules.yaml"))


@pytest.fixture(scope="module")
def run_out(tmp_path_factory):
    return pipeline.run(C.load_config(os.path.join(ROOT, "config", "rules.yaml")),
                        out_dir=str(tmp_path_factory.mktemp("out")))


# ── 四档各自的规范率门槛（数字外置在 rules.yaml tiers:；工单未设的档不编造）──
@pytest.mark.parametrize("key", ["D", "C", "B", "A"])
def test_style_rate_meets_each_tier(cfg, key):
    gate = tiers.gates(cfg)[key]["rate_min"]
    if gate is None:
        return                  # 工单该档只写功能项——没有数字门槛就不判数字
    stats = stylecheck.scan_project(ROOT)
    assert stats["rate"] >= gate, \
        "%s 要求规范率≥%s%%，实测 %.1f%%（引擎 %s）" % (
            key, gate, stats["rate"], stats["engine"])


def test_tiers_surface_wired_to_rules_yaml(cfg):
    """cli --tier 与 report 段必须同源：tiers.py 判据 + rules.yaml 数字。"""
    assert cli.TIERS == tiers.TIERS
    assert tiers.gates(cfg)["D"]["rate_min"] == 70.0
    assert tiers.gates(cfg)["B"]["rate_min"] == 90.0


def test_style_checker_is_real_not_stub():
    """体检必须真的数到文件与行，且能定位到 file:line（防"假合规"）。"""
    stats = stylecheck.scan_project(ROOT)
    assert stats["files"] >= 8 and stats["lines"] >= 200
    assert stats["engine_kind"] in ("pycodestyle", "builtin")


# ── 及格(D)：≥6 个变量、≥3 种数据类型 ──
def test_d_tier_at_least_6_vars_3_types(cfg):
    devs = pipeline.load_devices(cfg)
    table = core.var_table(devs[0])
    assert len(devs) >= 1
    assert len(table) >= 6 and len({t for _, _, t in table}) >= 3


# ── 良好(C)：输出格式清晰对齐；换算正确 ──
def test_c_tier_aligned_and_correct_conversion(cfg):
    devs = pipeline.load_devices(cfg)
    lines = core.card(devs[0], cfg)
    assert all(len(ln) <= 100 for ln in lines)
    assert any("  =  " in ln for ln in lines)               # 右对齐换算列
    assert abs(core.c_to_f(devs[0].temp) - (devs[0].temp * 9 / 5 + 32)) < 1e-9
    assert abs(core.kpa_to_mpa(devs[0].press_kpa) - devs[0].press_kpa / 1000) < 1e-12


# ── 优秀(B)：≥8 变量、4 种类型；换算 ≥2 处 ──
def test_b_tier_8_vars_4_types_and_2_conversions(cfg):
    devs = pipeline.load_devices(cfg)
    table = core.var_table(devs[0])
    kinds = {t for _, _, t in table}
    assert len(table) >= 8, "B 档需 ≥8 变量，实得 %d" % len(table)
    assert len(kinds) >= 4, "B 档需 4 种类型，实得 %s" % sorted(kinds)
    body = "\n".join(core.card(devs[0], cfg))
    hits = sum(1 for kw in ("℉", "MPa", "psi") if kw in body)
    assert hits >= 2, "B 档需换算≥2 处"


# ── 优(A)：达 B 且使用 input() 录入并校验（温度范围提示）──
def test_a_tier_input_with_range_check(cfg):
    answers = iter(["DEV-A1", "答辩样机", "999", "abc", "86", "520", "380", "2025", "y"])
    lines = core.interactive_card(cfg, reader=lambda p: next(answers))
    joined = "\n".join(lines)
    assert "校验未通过" not in joined          # 校验在 core 内打印，此处看最终台账
    assert "DEV-A1" in joined and "WARN" in joined


def test_a_tier_pipeline_interactive_section(tmp_path):
    cfg = C.load_config(os.path.join(ROOT, "config", "rules.yaml"))
    cfg.raw["interactive"] = True
    answers = iter(["DEV-A2", "录入泵", "70", "400", "380", "2024", "y"])
    cfg.raw["reader"] = lambda prompt: next(answers)
    sections = pipeline.run(cfg, out_dir=str(tmp_path))
    titles = [t for t, _ in sections]
    assert "交互录入（A 档 input 变体）" in titles
    text = "\n".join(dict(sections)["交互录入（A 档 input 变体）"])
    assert "DEV-A2" in text


# ── 交付证据：已提交的 output/report.txt 必须含真实规范率（防伪造）──
def test_committed_report_contains_measured_style_rate():
    assert os.path.exists(REPORT), "先跑 python run.py 生成 output/report.txt"
    text = open(REPORT, encoding="utf-8").read()
    assert "编码规范率（PEP 8 实测）" in text
    assert "验收档位判定（实测）" in text
    assert "实测达成档位" in text
    stats = stylecheck.scan_project(ROOT)
    assert ("规范率实测: %.1f%%" % stats["rate"]) in text
