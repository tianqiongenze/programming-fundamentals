# -*- coding: utf-8 -*-
from text_report import core


def test_tokenize_bigram():
    assert core.tokenize("液压油温") == ["液压", "压油", "油温", "液压油温"]


def test_tokenize_mixed_text_keeps_chinese_only():
    assert core.tokenize("轴承ABB报警") == ["轴承", "轴承", "报警", "报警"]


def test_clean_removes_stopwords():
    assert core.clean_tokens(["液压", "设备", "油温"]) == ["液压", "油温"]


def test_topn_sorted_by_count():
    toks = ["液压", "液压", "液压", "轴承", "轴承", "油温"]
    top = core.topn(toks, k=3)
    assert top[0] == ("液压", 3) and top[1] == ("轴承", 2)


def test_topn_k_limited():
    toks = ["液压", "液压", "轴承", "轴承", "冷却", "cool"]
    assert len(core.topn(toks, k=2)) == 2


def test_empty_text_returns_empty():
    assert core.tokenize("") == []


def test_single_char_text_returns_empty():
    assert core.tokenize("泵") == []
