# -*- coding: utf-8 -*-
"""批量报文 → 可扩展解析 → 格式统计。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    pkts = [str(x) for x in cfg.items]
    ok, bad, fmt_stat = [], [], {}
    for i, p in enumerate(pkts, 1):
        d = core.parse(p)
        if d is None:
            bad.append({"line": i, "raw": p, "reason": "未知格式/解析失败"})
            continue
        ok.append(d)
        fmt_stat[d["format"]] = fmt_stat.get(d["format"], 0) + 1
    result = {"total": len(pkts), "parsed": len(ok), "bad": len(bad),
              "by_format": fmt_stat, "rows": ok, "quarantine": bad}
    lines = ["%s  格式:%-5s 温度 %5.1f℃ 压力 %.2fMPa"
             % (d["id"], d["format"], d["temp"], d["press"]) for d in ok]
    sections = [("输入口径", ["原始报文 %d 条｜支持格式: json / kv / csv" % len(pkts)]),
                ("解析成功", lines or ["无"]),
                ("格式分布", ["%s: %d 条（%.0f%%）" % (k, v, v * 100 // max(len(ok), 1))
                          for k, v in sorted(fmt_stat.items())] or ["-"]),
                ("隔离区", ["第%d行 %r" % (b["line"], b["raw"]) for b in bad] or ["无坏报文"]),
                ("结论与建议", ["新增格式 = 写解析函数 + 注册 PARSERS；调用方零改动"])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections
