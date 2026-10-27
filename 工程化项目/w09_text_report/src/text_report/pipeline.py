# -*- coding: utf-8 -*-
"""批量故障单 → 二元词分词 → 词频 Top-N → 报告。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    faults = [str(x) for x in cfg.items]
    if not faults:
        raise ValueError("config/rules.yaml 的 faults 为空")
    all_toks = []
    for f in faults:
        all_toks.extend(core.clean_tokens(core.tokenize(f)))
    top = core.topn(all_toks, k=int(cfg.topk))
    total = sum(c for _, c in core.count(all_toks).items())
    lines = ["%-10s %3d 次  (%.1f%%)" % (w, c, c * 100 / max(total, 1)) for w, c in top]
    result = {"n_faults": len(faults), "total_tokens": total,
              "top": [{"word": w, "count": c} for w, c in top]}
    sections = [("输入口径", ["故障单 %d 条｜Top-%d｜分词: 中文二元词（零依赖兜底）" % (len(faults), cfg.topk)]),
                ("高频故障词", lines or ["无有效词"]),
                ("结论与建议", ["按高频故障词锁定备件与巡检重点；"
                 "Top1「%s」需优先排查" % (top[0][0] if top else "-")])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
