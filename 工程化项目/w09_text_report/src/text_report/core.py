# -*- coding: utf-8 -*-
"""中文故障文本：jieba 精确分词（可降级）、二元词兜底、停用词、词频统计。"""
import re

STOP = {"设备", "系统", "发生", "进行", "状态"}


def jieba_tokens(text):
    """jieba 精确模式分词（工单 W09 任务要求②）；未安装返回 None（走兜底）。"""
    try:
        import jieba
    except ImportError:
        return None
    return [t.strip() for t in jieba.cut(text, cut_all=False) if t.strip()]


def keyword_tags(texts, k=20):
    """jieba.analyse.extract_tags Top-K 关键词（工单任务要求③）。

    未安装 jieba 时返回 None——调用方回落二元词统计，通道如实写进报告。
    带权重与否跨版本参数名不同（withWeight/with_weights），逐级降级调用。
    """
    try:
        from jieba import analyse
    except ImportError:
        return None
    text = "".join(texts)
    try:
        return list(analyse.extract_tags(text, topK=int(k),
                                         withWeight=True))
    except TypeError:
        return [(w, 1.0) for w in analyse.extract_tags(text, topK=int(k))]


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
