# -*- coding: utf-8 -*-
"""六段流水线：采集 → 三维度清洗 → [分级 | 词频] → 交付物 → 清单 → 档位判定。

对应工单 Z 的七项必备模块，每一项都在报告里留**可复核的实测证据**：
采集通道与条数（Collector）、三维度隔离计数（core.triage）、分级统计、
词云/PDF 产物字节数、规范率实测值（stylecheck）。缺一项就如实打叉，
不把"没生成"写成"已完成"。
"""
import logging
import os

from . import collector, core, io_utils, report, reporter, stylecheck

TIERS = [("及格(D)", 80.0, "功能基本完整 + 主流程可演示（≥50 条数据）"),
         ("良好(C)", 85.0, "功能完整 + 讲清设计思路（Collector/Reporter 两类）"),
         ("优秀(B)", 90.0, "技术细节深入 + 合理创新点（复用 W02/06/08/10）"),
         ("优(A)", 95.0, "架构图清晰 + 明显工业应用价值")]


def setup_logging(out_dir, echo=False):
    """日志落盘 output/run.log（工单"异常与日志"项的硬证据）。"""
    io_utils.ensure_dir(out_dir)
    path = os.path.join(out_dir, "run.log")
    logger = logging.getLogger("capstone")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.FileHandler(path, encoding="utf-8"))
    if echo:
        logger.addHandler(logging.StreamHandler())
    return path, logger


def build(cfg, out_dir, echo=False):
    """跑完整流水线，返回 (sections, result)；result 供 pytest 断言。"""
    log_path, logger = setup_logging(out_dir, echo=echo)
    style_min = float(cfg.get("style_min", 80.0))
    faults = cfg.raw.get("faults") or []
    if isinstance(faults, str):
        faults = [faults]
    # ① 采集（工单要求 ≥50 条；CSV 优先，缺文件走种子补齐）
    coll = collector.Collector(min_rows=int(cfg.get("min_rows", 50)),
                               seed=int(cfg.get("seed", 7)),
                               csv_name=str(cfg.get("csv_name",
                                                    collector.DEFAULT_CSV)),
                               log=logging.getLogger("capstone.collector"))
    rows, cmeta = coll.collect(source=cfg.raw.get("csv_path") or None)
    # ② 三维度清洗（采集行 + 配置里的脏行样本一起过，脏行才有归因可看）
    records = list(rows) + [str(x) for x in cfg.items]
    good, quarantine, dims = core.triage(records, cfg.warn, cfg.danger)
    if not good:
        raise ValueError("清洗后无有效数据——请检查 config/rules.yaml")
    # ③ 分级 + 词频（互不依赖）
    kw = core.keywords(faults, k=int(cfg.topk))
    lv_stat = {lv: sum(1 for r in good if r["level"] == lv)
               for lv in ("normal", "warn", "danger")}
    # ④ 产物落盘
    io_utils.ensure_dir(out_dir)
    io_utils.write_csv_rows(os.path.join(out_dir, "clean_data.csv"), good,
                            ["name", "temp", "press", "level"])
    # ⑤ 交付物（文本 + 词云 + PDF 图文）
    rep = reporter.Reporter(out_dir, log=logging.getLogger(
        "capstone.reporter"))
    stats = stylecheck.scan_project(stylecheck.project_root(
        os.path.abspath(__file__)))
    body = _sections(cfg, cmeta, good, quarantine, dims, lv_stat, kw, stats,
                     style_min, log_path, rep)
    txt_path, txt_note = rep.text(body)
    cloud_path, cloud_note = rep.wordcloud(kw)
    pdf_path, pdf_note = rep.pdf(body, title="工业互联网完整数据处理系统 · "
                                 "终验报告（W12 综合项目）", image=cloud_path)
    deliverables = [("文本报告 report.txt", txt_path, txt_note),
                    ("词云 keyword_cloud.png", cloud_path, cloud_note),
                    ("PDF 图文交付 deliverable.pdf", pdf_path, pdf_note),
                    ("清洗数据 clean_data.csv", os.path.join(
                        out_dir, "clean_data.csv"), "复用 W08 口径"),
                    ("运行日志 run.log", log_path, "复用 W06 logging")]
    result = {"collect": cmeta, "records": len(records), "valid": len(good),
              "quarantine": len(quarantine), "dimensions": dims,
              "levels": lv_stat, "keywords": kw,
              "style_rate": stats["rate"], "style_violations":
              stats["violations"], "style_engine": stats["engine"],
              "tiers": tier_verdict(stats["rate"], len(good), cmeta["rows"],
                                    coll.min_rows, bool(cloud_path),
                                    bool(pdf_path), dims),
              "checklist": rep.checklist(deliverables),
              "artifacts": {(os.path.basename(p) if p else n):
                            bool(p and os.path.exists(p))
                            for n, p, _ in deliverables}}
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    io_utils.write_json(os.path.join(out_dir, "quarantine.json"), quarantine)
    # 交付物清单只有跑完才知道有没有——补一段再重写文本报告
    body.append(("工单必备模块 checklist（实测）", result["checklist"]))
    body.append(("验收档位判定（答辩评分）",
                 _tier_lines(result["tiers"], stats)))
    report.save(body, txt_path)
    return body, result


def run(cfg, out_dir, echo=False):
    """兼容旧入口：返回报告段（cli 用）。"""
    sections, _ = build(cfg, out_dir, echo=echo)
    return sections


def tier_verdict(rate, n_valid, n_raw, min_rows, has_cloud, has_pdf, dims):
    """按工单四档给判定，每条都要有实测依据（不是"我觉得行"）。"""
    n_dims = sum(1 for v in dims.values() if v)
    functional = {"D": n_valid > 0 and n_raw >= min_rows,
                  "C": has_cloud and has_pdf,
                  "B": n_dims >= 2,
                  "A": rate >= 95.0}
    out = []
    for name, gate, need in TIERS:
        key = name[-2]
        ok = bool(functional[key]) and rate >= gate
        out.append({"tier": name, "gate": gate, "need": need,
                    "functional": bool(functional[key]),
                    "style_ok": rate >= gate, "pass": ok})
    return {"tiers": out, "min_rows": min_rows, "n_raw": n_raw,
            "claimed": next((t["tier"] for t in reversed(out) if t["pass"]),
                            "未达 D 档")}


def _tier_lines(tiers, stats):
    lines = ["实测档位: %s｜规范率实测 %.1f%%（引擎 %s）——档位由 tier_verdict "
             "按本次实测值算出，代码里没有自称的承诺档位"
             % (tiers["claimed"], stats["rate"], stats["engine"])]
    for t in tiers["tiers"]:
        lines.append("  %-8s 门槛≥%.0f%% [%s] ｜ 功能%s ｜ %s"
                     % (t["tier"], t["gate"], "达标" if t["pass"] else "未达标",
                        "OK" if t["functional"] else "缺", t["need"]))
    lines.append("  功能门实测口径: D=有效行数≥min_rows 且原始行数达标；"
                 "C=云端通道与 PDF 交付物真实产出；B=清洗维度实测≥2 项；"
                 "A=规范率≥95%")
    lines.append("  人工答辩项 3 条（机器判不了，不计入上方档位，教师答辩时确认）: "
                 "C·讲清设计思路（Collector/Reporter 两类）；"
                 "B·技术细节深入＋有合理创新点；A·架构图清晰＋有明显工业应用价值")
    return lines


def _sections(cfg, cmeta, good, quarantine, dims, lv_stat, kw, stats,
              style_min, log_path, rep):
    """组装报告段（不含 checklist——它在交付物生成后追加）。"""
    from . import stylecheck as S
    return [
        ("输入口径", [
            "采集通道: %s｜%s" % (cmeta["channel"], cmeta["detail"]),
            "原始读数 %d 条（丢弃坏行 %d 条）｜预警 %.0f℃ / 停机 %.0f℃"
            % (cmeta["rows"], cmeta["dropped"], cfg.warn, cfg.danger),
            "量程: 温度 0~200℃｜压力 0~5MPa｜清洗后有效 %d 条" % len(good)]),
        ("三维度清洗（复用 W08）",
         ["%s: %d 条" % (d, dims[d]) for d in core.DIMENSIONS] +
         ["隔离区样例（最多 5 条，全量见 quarantine.json）:"] +
         ["  第%d条 [%s] %s ｜ 原文 %s"
          % (q["line"], q["dimension"], q["reason"], q["raw"])
          for q in quarantine[:5]]),
        ("告警分级（复用 W02 阈值规则）",
         ["%s: %d 条" % (k, v) for k, v in sorted(lv_stat.items())]),
        ("高频故障词 + 词云",
         ["%s ×%d" % (w, c) for w, c in kw] or ["无故障文本"]),
        ("编码规范率（PEP 8 实测）",
         S.format_section(stats, style_min)),
        ("日志与异常处理（复用 W06）",
         ["日志文件: %s" % os.path.relpath(log_path, rep.out_dir + "/.."),
          "全流程 try/except 兜底：CSV 缺失→种子补齐；reportlab/wordcloud "
          "缺失→如实记 MISS，不生成假产物"]),
        ("结论与建议",
         ["有效数据 %d 条、隔离 %d 条；词频 Top1「%s」需优先排查"
          % (len(good), len(quarantine), kw[0][0] if kw else "-"),
          "档位以实测规范率与交付物存在性为准，未达项按 checklist 补齐后重跑"])]
