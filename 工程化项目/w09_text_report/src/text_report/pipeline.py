# -*- coding: utf-8 -*-
"""故障单 → 分词（jieba 优先/二元词兜底）→ 词频 Top-N/Top20 → 图文产物 → 档位判定。

工单 W09 的验收证据全部实测：分词通道如实报告，词云/柱状图/分组词云
以磁盘字节数验收（缺库记 0 字节如实判缺），停用词过滤前后对照，
洞察句必须带实测数字。档位由 tiers.verdict 用这些实测值计算。
"""
import os

from . import core, io_utils, report, stylecheck, tiers, visuals

ROOT = stylecheck.project_root(os.path.abspath(__file__))


def _split_tokens(texts):
    """分词通道：jieba 精确模式优先；缺 jieba 回落二元词，通道名如实返回。"""
    tok_lists, channel = [], "jieba-精确模式"
    for t in texts:
        toks = core.jieba_tokens(t)
        if toks is None:
            tok_lists.append(core.tokenize(t))
            channel = "二元词兜底(未装 jieba)"
        else:
            tok_lists.append(toks)
    return tok_lists, channel


def _group_faults(texts, rules):
    """按 group_rules（关键词→系统名）给故障单分组；未命中归"其他"。"""
    groups = {}
    for t in texts:
        tag = "其他"
        for kw, name in (rules or {}).items():
            if str(kw) in t:
                tag = str(name)
                break
        groups.setdefault(tag, []).append(t)
    return groups


def build(cfg, out_dir):
    """跑完整文本分析流水线，返回 (sections, result)；result 供 pytest 断言。"""
    faults = [str(x) for x in cfg.items]
    if not faults:
        raise ValueError("config/rules.yaml 的 faults 为空")
    io_utils.ensure_dir(out_dir)
    tok_lists, channel = _split_tokens(faults)
    all_toks = [t for lst in tok_lists for t in lst]
    filtered = [core.clean_tokens(lst) for lst in tok_lists]
    flat = [t for lst in filtered for t in lst]
    top = core.topn(flat, k=int(cfg.topk))
    removed_stop = [t for t in all_toks if t in core.STOP]
    stop_ok = all(w not in core.STOP for w, _ in top)
    tags20 = core.keyword_tags(faults, k=20)
    top20 = [(w, int(round(float(s) * 100))) for w, s in tags20] if tags20 \
        else core.topn(flat, k=20)
    total = sum(c for _, c in core.count(flat).items())
    font = visuals.find_font()
    cloud_path, cloud_note, cloud_bytes = visuals.wordcloud_png(
        top20 or top, out_dir)
    chart_path, chart_note, chart_bytes = visuals.top10_chart(
        top, out_dir)
    group_rules = cfg.raw.get("group_rules") or {}
    groups = _group_faults(faults, group_rules)
    group_rows, group_clouds, group_cloud_names = [], [], []
    for name, texts in sorted(groups.items()):
        g_toks = [t for lst in _split_tokens(texts)[0]
                  for t in core.clean_tokens(lst)]
        g_top = core.topn(g_toks, k=int(cfg.topk))
        g_name = "group_cloud_%s.png" % name
        g_path, _note, g_bytes = visuals.wordcloud_png(g_top, out_dir,
                                                       name=g_name)
        group_clouds.append(g_bytes)
        if g_path:
            group_cloud_names.append(g_name)
        group_rows.append("%s: 故障 %d 条｜Top 词 %s｜词云 %s" % (
            name, len(texts),
            ", ".join("%s×%d" % (w, c) for w, c in g_top[:3]) or "-",
            "%d 字节" % g_bytes if g_path else "MISS"))
    insight = ("故障规律洞察: 共 %d 条故障单、有效词 %d 个，Top1「%s」出现 %d 次"
               "（%.1f%%），巡检与备件按此优先级排布。" % (
                   len(faults), total, top[0][0] if top else "-",
                   top[0][1] if top else 0,
                   (top[0][1] * 100.0 / max(total, 1)) if top else 0.0))
    insight_ok = any(ch.isdigit() for ch in insight) and bool(top)
    cloud_line = ("词云 wordcloud.png: %s，%d 字节｜%s" % (
        os.path.basename(cloud_path), cloud_bytes, cloud_note)
        if cloud_path else "词云 wordcloud.png: MISS（%s）" % cloud_note)
    chart_line = ("词频图 top10.png: %d 字节｜%s" % (
        chart_bytes, chart_note) if chart_path
        else "词频图 top10.png: MISS（%s）" % chart_note)
    font_line = "中文字体: %s" % (
        os.path.basename(font) if font else "未找到（词云可能方块）")
    style = stylecheck.scan_project(ROOT)
    result = {"n_faults": len(faults), "channel": channel,
              "total_tokens": total,
              "top": [{"word": w, "count": c} for w, c in top],
              "top20": [{"word": w, "count": c} for w, c in top20],
              "stopwords_removed": len(removed_stop), "stop_ok": stop_ok,
              "font_used": font or "内置默认",
              "artifacts": {
                  "wordcloud.png": {"path": cloud_path, "bytes": cloud_bytes},
                  "top10.png": {"path": chart_path, "bytes": chart_bytes},
                  "group_clouds": {"paths": group_cloud_names,
                                   "bytes_per_cloud": group_clouds}},
              "groups": {k: len(v) for k, v in groups.items()},
              "insight": insight,
              "style_rate": style["rate"],
              "style_violations": style["violations"],
              "style_engine": style["engine"]}
    result["tiers"] = tiers.verdict(
        rate=style["rate"], n_tokens=total, cloud_bytes=cloud_bytes,
        stop_ok=stop_ok, chart_bytes=chart_bytes, font_ok=bool(font),
        top20_count=len(top20), insight_ok=insight_ok,
        group_cloud_bytes=group_clouds, stop_hits=len(removed_stop),
        gates=tiers.gates_from(cfg.tier_gates()))
    lines = ["%-10s %3d 次  (%.1f%%)" % (w, c, c * 100 / max(total, 1))
             for w, c in top]
    sections = [
        ("输入口径", [
            "故障单 %d 条｜Top-%d｜分词通道: %s（零依赖兜底可用）"
            % (len(faults), cfg.topk, channel)]),
        ("高频故障词", lines or ["无有效词"]),
        ("Top20 关键词（extract_tags 实测）",
         ["%s（权重×100=%d）" % (w, c) for w, c in top20[:20]] or ["-"]),
        ("停用词过滤（实测）", [
            "过滤掉的停用词 %d 个；Top 词中停用词残留: %s" % (
                len(removed_stop), "0（处理得当）" if stop_ok else "有，需检查")]),
        ("图文产物（磁盘实测）", [cloud_line, chart_line, font_line]),
        ("分组对比词云（A 档实测）", group_rows),
        ("故障规律洞察（≤150 字）", [insight]),
        ("编码规范率（PEP 8 实测）",
         stylecheck.format_section(style, 90.0)),
        ("验收档位判定（实测）", tiers.render_lines(result["tiers"])),
        ("结论与建议", [
            "按高频故障词锁定备件与巡检重点；Top1「%s」需优先排查"
            % (top[0][0] if top else "-")]),
    ]
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir):
    """兼容旧入口：返回报告段（cli 用）。"""
    sections, _ = build(cfg, out_dir)
    return sections
