# -*- coding: utf-8 -*-
"""工单 W01 D/C/B/A 功能门的实测产出：AST 计数 + 独立公式复核 + stdin 注入真走 input()。

档位数字门槛外置在 config/rules.yaml 的 tiers: 段；本模块只产实测值，
判定在 tiers.verdict——口径与 stylecheck 相同：报告里的数字都是跑出来的。
  ast_vars/ast_types   —— AST 数 Device 台账带类型标注的字段及种类；
  conv_funcs/conv_bad  —— AST 找 *_to_* 换算函数，并逐个用独立手算公式复核；
  colon_lines/same_col —— 台账卡实渲染，等宽显示宽度实测冒号列是否同列；
  input_probe_*        —— 换 sys.stdin 喂样本，越界/非数字必须当场拒收，
                          范围提示必须出现在提问行（A 档可机器判定的部分）。
"""
import ast
import contextlib
import io
import sys
import unicodedata

from . import core

LEDGER_TYPES = ("bool", "float", "int", "str")
# 兜底 stdin 样本（唯一出处是 rules.yaml tiers.input_feed）；
# 999（越界）与 abc（非数字）必须被拒收。按字面 \n 切分——yaml_lite 不解析转义。
INPUT_FEED = "DEV-PROBE\\n探针泵\\n999\\nabc\\n75\\n450\\n380\\n2024\\ny"


def _scan(path):
    """AST 解析 → (带 str/int/float/bool 标注的字段清单, 顶层函数名清单)。"""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    typed = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and getattr(node.annotation, "id", "") in LEDGER_TYPES):
            typed.append((node.target.id, node.annotation.id))
    funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    return typed, funcs


def _conv_checks():
    """换算正确性：core 函数 vs 独立手算公式（不复用 core），逐个样本比差。"""
    samples = (37.0, 100.0, 56.5)
    checks = [(core.c_to_f, lambda c: c * 9.0 / 5.0 + 32.0),
              (core.kpa_to_mpa, lambda k: k / 1000.0),
              (core.mpa_to_psi, lambda p: p * 14.5038)]
    bad = 0
    for fn, expect in checks:
        bad += sum(1 for s in samples if abs(fn(s) - expect(s)) > 1e-9)
    return len(checks), bad


def _display_width(text):
    """等宽字体显示宽度（CJK 记 2 列）——"对齐"要看眼见的列，不是字符数。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in text)


def _colon_columns(lines):
    """台账卡实渲染后，取每条含 ' : ' 行的冒号显示列（同列才算对齐）。"""
    cols = []
    for ln in lines:
        if " : " in ln:
            cols.append(_display_width(ln[:ln.index(" : ")]))
    return cols


def _feed_text(cfg):
    """rules.yaml 的 input_feed → 真换行样本串。

    PyYAML 会把 "\n" 解析成真换行、yaml_lite 保留字面反斜杠——两种都归一。
    """
    feed = str(cfg.get("input_feed") or INPUT_FEED)
    return "\n".join(p for chunk in feed.split("\\n") for p in chunk.split("\n"))


def _input_probe(cfg):
    """A 档实测路径：临时替换 sys.stdin 真走内置 input()，拒收/提示/出卡全实测。"""
    old_in, out = sys.stdin, io.StringIO()
    sys.stdin = io.StringIO(_feed_text(cfg))
    try:
        with contextlib.redirect_stdout(out):
            card = core.interactive_card(cfg, reader=input)
    except (EOFError, ValueError) as exc:
        return False, False, "input() 录入路径异常中断: %r" % (exc,)
    finally:
        sys.stdin = old_in
    text = out.getvalue() + "\n".join(card)
    want_code = _feed_text(cfg).split("\n")[0]   # 录入编号取自样本第一行
    hint = "温度℃（%.0f~%.0f）" % (core.TEMP_MIN, core.TEMP_MAX) in text
    rejected = ("[校验未通过]" in text and "超出车间允许区间" in text
                and "不是数字" in text)
    accepted = want_code in text and "设 备 台 账 卡" in text
    detail = "越界/非数字当场拒收=%s ｜ 范围提示进提问行=%s ｜ 合法录入出卡=%s" % (
        rejected, hint, accepted)
    return rejected and hint and accepted, hint, detail


def collect(cfg, devs):
    """汇总 W01 四档功能门的实测值（只测量、不判定）。"""
    typed, funcs = _scan(core.__file__)
    kinds = sorted({t for _, t in typed})
    conv_checked, conv_bad = _conv_checks()
    cols = _colon_columns(core.card(devs[0], cfg))
    ok, hint, detail = _input_probe(cfg)
    return {"ast_vars": len(typed), "ast_types": len(kinds), "types": kinds,
            "conv_funcs": sum(1 for n in funcs if "_to_" in n),
            "conv_names": sorted(n for n in funcs if "_to_" in n),
            "conv_checked": conv_checked, "conv_failed": conv_bad,
            "colon_lines": len(cols), "colon_same": len(set(cols)),
            # ≥5 条键值行同列才叫"格式清晰对齐"——只有 1~2 行的"对齐"无意义
            "align_ok": len(cols) >= 5 and len(set(cols)) == 1,
            "input_probe_ok": ok, "input_hint_ok": hint,
            "input_detail": detail}
