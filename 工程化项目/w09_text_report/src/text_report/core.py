# -*- coding: utf-8 -*-
"""中文故障文本：二元词分词、停用词过滤、词频统计（纯函数，零依赖）。"""
import re

STOP = {"设备", "系统", "发生", "进行", "状态"}


def tokenize(text):
    """中文二元词兜底分词：连续中文段 -> [w[i:i+2]]，并保留整段原词。"""
    toks = []
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(seg) < 2:
            continue
        toks += [seg[i:i + 2] for i in range(len(seg) - 1)]
        toks.append(seg)
    return toks


def clean_tokens(toks, stop=None):
    stop = stop or STOP
    return [t for t in toks if t not in stop and len(t) >= 2]


def count(toks):
    from collections import Counter
    return Counter(toks)


def topn(toks, k=10, stop=None):
    """Top-N：按频次降序；同频次按词出现顺序稳定排序。"""
    c = count(clean_tokens(toks, stop))
    return c.most_common(k)
