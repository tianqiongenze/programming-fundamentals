# -*- coding: utf-8 -*-
"""批量报文 → 可扩展解析 → 容错归因 → 批量转换文件落盘 → 统计 + 档位判定。

工单 W07 的验收证据全部来自实测：本次运行真实解析出的格式集合、
正则 kv 通道条数、隔离区归因、成功行键集合是否实测一致（"字典结构
统一"）、output/samples/ 下多个样本文件的批量转换（逐文件读盘 →
转换 → output/converted/ 产物回读），再交给 tiers.verdict 计算
D/C/B/A——报告里的档位是算出来的。
"""
import os

from . import core, io_utils, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
DEFAULT_BATCH_FILES = ("shift_a.txt", "shift_b.txt", "shift_c.txt")


def _split_batches(pkts, names):
    """报文按轮转分进 N 个班次样本——确定性生成，不依赖随机数。"""
    buckets = {n: [] for n in names}
    for i, p in enumerate(pkts):
        buckets[names[i % len(names)]].append(p)
    return buckets


def batch_convert(cfg, pkts, out_dir):
    """A 档实测：样本文件落 output/samples/ → 真实逐行读盘转换 → 产物落盘。

    转换统计（n_ok/n_fail/格式分布）来自读盘解析与产物回读双向核对，
    不是内存里自称——产物没落盘、行数对不上，A 档当场判不达标。
    """
    names = [str(n) for n in cfg.seq("batch_files", list(DEFAULT_BATCH_FILES))
             if str(n).strip()] or list(DEFAULT_BATCH_FILES)
    samples_dir = io_utils.ensure_dir(os.path.join(out_dir, "samples"))
    converted_dir = io_utils.ensure_dir(
        os.path.join(out_dir, "converted"))
    buckets = _split_batches(pkts, names)
    for name in names:
        io_utils.write_text(os.path.join(samples_dir, name),
                            "\n".join(buckets[name]) + "\n")
    per_file, fmt_stat = [], {}
    n_ok = n_fail = n_lines = rows_back = 0
    for name in names:
        path = os.path.join(samples_dir, name)
        with open(path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        rows, bad = [], 0
        for ln in lines:
            d = core.parse(ln)
            if d is None:
                bad += 1
                continue
            rows.append(d)
            fmt_stat[d["format"]] = fmt_stat.get(d["format"], 0) + 1
        out_path = os.path.join(converted_dir,
                                os.path.splitext(name)[0] + ".json")
        io_utils.write_json(out_path, rows)
        back = len(io_utils.read_json(out_path))
        per_file.append({"file": name, "lines": len(lines), "ok": len(rows),
                         "fail": bad, "out": out_path, "out_rows": back})
        n_lines += len(lines)
        n_ok += len(rows)
        n_fail += bad
        rows_back += back
    batch = {"files": len(names), "lines": n_lines, "n_ok": n_ok,
             "n_fail": n_fail, "rows": rows_back, "by_format": fmt_stat,
             "per_file": per_file, "samples_dir": samples_dir,
             "converted_dir": converted_dir}
    return batch


def build(cfg, out_dir):
    """跑完整解析流水线，返回 (sections, result)；result 供 pytest 断言。"""
    pkts = [str(x) for x in cfg.items]
    ok, bad, fmt_stat = [], [], {}
    for i, p in enumerate(pkts, 1):
        d = core.parse(p)
        if d is None:
            bad.append({"line": i, "raw": p,
                        "reason": core.failure_reason(p)})
            continue
        ok.append(d)
        fmt_stat[d["format"]] = fmt_stat.get(d["format"], 0) + 1
    # B 档容错实测：乱序键值报文与缺字段报文各探一次真实解析路径
    reordered = core.parse("t=95.5;p=0.66;id=PROBE-乱序")
    out_of_order_ok = reordered is not None and reordered["id"] == "PROBE-乱序"
    missing_field = core.parse("id=PROBE-缺字段;t=60.0")
    missing_field_ok = missing_field is None
    # A 档批量转换：多个样本文件逐文件读盘转换，计数与产物双向核对
    batch = batch_convert(cfg, pkts, out_dir)
    io_utils.ensure_dir(out_dir)
    conv_path = os.path.join(out_dir, "converted.json")
    io_utils.write_json(conv_path, ok)
    conv_rows = len(io_utils.read_json(conv_path))
    conv_bytes = os.path.getsize(conv_path)
    uniform = len({tuple(sorted(r.keys())) for r in ok}) <= 1
    stats_ok = len(ok) + len(bad) == len(pkts)
    style = stylecheck.scan_project(ROOT)
    result = {"total": len(pkts), "parsed": len(ok), "bad": len(bad),
              "by_format": fmt_stat, "rows": ok, "quarantine": bad,
              "stats_ok": stats_ok, "uniform_structure": uniform,
              "fault_tolerance": {"out_of_order_ok": out_of_order_ok,
                                  "missing_field_ok": missing_field_ok},
              "batch": {k: v for k, v in batch.items() if k != "per_file"},
              "artifacts": {"converted.json": {"path": conv_path,
                                               "rows": conv_rows,
                                               "bytes": conv_bytes}},
              "style_rate": style["rate"],
              "style_violations": style["violations"],
              "style_engine": style["engine"]}
    result["tiers"] = tiers.verdict(
        gates=tiers.gates_from(cfg), rate=style["rate"],
        formats=fmt_stat.keys(), n_regex_kv=fmt_stat.get("kv", 0),
        uniform=uniform, n_bad=len(bad), stats_ok=stats_ok,
        out_of_order_ok=out_of_order_ok, missing_field_ok=missing_field_ok,
        batch=batch)
    lines = ["%s  格式:%-5s 温度 %5.1f℃ 压力 %.2fMPa"
             % (d["id"], d["format"], d["temp"], d["press"]) for d in ok]
    batch_rows = ["  %s: 读入 %d 行 → 成功 %d / 失败 %d → 产物回读 %d 行"
                  % (p["file"], p["lines"], p["ok"], p["fail"], p["out_rows"])
                  for p in batch["per_file"]]
    batch_rows.append("  合计: 样本 %d 个文件 / %d 行 → OK %d / FAIL %d，"
                      "产物行数回读核对 %s"
                      % (batch["files"], batch["lines"], batch["n_ok"],
                         batch["n_fail"],
                         "一致" if batch["rows"] == batch["n_ok"] else "不一致！"))
    batch_rows.append("  格式统计（批量通道实测）: %s" % (
        ", ".join("%s %d 条" % (k, v)
                  for k, v in sorted(batch["by_format"].items())) or "-"))
    sections = [("输入口径",
                 ["原始报文 %d 条｜支持格式: json / kv / csv" % len(pkts)]),
                ("解析成功", lines or ["无"]),
                ("格式分布（转换统计·实测）",
                 ["%s: %d 条（%.0f%%）" % (k, v, v * 100 // max(len(ok), 1))
                  for k, v in sorted(fmt_stat.items())] or ["-"]),
                ("隔离区（容错归因）",
                 ["第%d行 %r 原因: %s" % (b["line"], b["raw"], b["reason"])
                  for b in bad] or ["无坏报文"]),
                ("容错实测（B 档证据）", [
                    "乱序键值报文实测解析: %s（id=%s）" % (
                        "通过" if out_of_order_ok else "失败",
                        reordered["id"] if reordered else "-"),
                    "缺字段报文实测处置: %s" % (
                        "隔离不崩溃" if missing_field_ok else "异常")]),
                ("字典结构统一实测（C 档证据）", [
                    "成功行键集合去重后 %d 种（1 种=结构统一）" % len(
                        {tuple(sorted(r.keys())) for r in ok})]),
                ("批量转换文件（A 档证据）", batch_rows),
                ("批量转换汇总产物", [
                    "converted.json: %d 行 / %d 字节" % (conv_rows, conv_bytes)]),
                ("编码规范率（PEP 8 实测）", stylecheck.format_section(
                    style, float(cfg.get("style_min", 90.0)))),
                ("验收档位判定（实测）", tiers.render_lines(result["tiers"])),
                ("结论与建议", ["新增格式 = 写解析函数 + 注册 PARSERS；调用方零改动"])]
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir):
    """兼容旧入口：返回报告段（cli 用）。"""
    sections, _ = build(cfg, out_dir)
    return sections
