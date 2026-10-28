# -*- coding: utf-8 -*-
"""逐行采集 → 异常分诊 → 三级日志 → 校验 → 隔离 → 统计报告。

工单 W06 的三条硬要求在报告里都留**实测证据**（不是 print 冒充日志）：
  ① logging 真落盘：INFO 记正常行 / WARNING 记脏数据跳过 / ERROR 记异常，
    写 output/run.log（--quiet 只落盘，非 quiet 同步回显控制台）；
  ② 异常全程捕获：现场文件缺失 FileNotFoundError、非数值 ValueError、
    字段缺失 IndexError——捕获到几种按本次运行实测计数；
  ③ try/except/finally 完整：starter 文件回读用显式 finally 收尾并实测标记。
档位判定（tiers.verdict）吃的全部是上面这些实测值。
"""
import logging
import os
import re

from . import core, io_utils, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
LOG_FORMAT = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
log = logging.getLogger("robust_collector")


def setup_logging(out_dir, echo=False):
    """logging 真落盘 run.log（utf-8 防中文乱码）；echo 时同步进控制台。"""
    io_utils.ensure_dir(out_dir)
    path = os.path.join(out_dir, "run.log")
    logger = logging.getLogger("robust_collector")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(LOG_FORMAT)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if echo:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return path, logger


def _read_input_lines(cfg, out_dir):
    """现场 data_file 优先；缺失记 ERROR，并用配置行生成 starter 文件回读。

    回读走显式 try/except/finally：finally 里关文件并记 INFO——
    工单 B06"无论成败必做收尾"的实测点。
    """
    caught = set()
    ran_finally = False
    primary = str(cfg.get("data_file", ""))
    text = None
    if primary:
        try:
            with open(primary, encoding="utf-8") as f:
                text = f.read()
            log.info("现场数据文件已读取: %s", primary)
        except FileNotFoundError as exc:
            caught.add("FileNotFoundError")
            text = None
            log.error("现场数据文件缺失，改用 starter 数据: %s", exc)
    starter = os.path.join(out_dir, "raw_data.txt")
    if text is None:
        io_utils.write_text(starter, "\n".join(
            [str(x) for x in cfg.items]) + "\n")
        f = open(starter, encoding="utf-8")
        try:
            text = f.read()
        except OSError as exc:
            caught.add("OSError")
            log.error("starter 文件回读失败: %s", exc)
            raise
        finally:
            f.close()
            ran_finally = True
            log.info("starter 文件已回读并在 finally 中关闭: %s", starter)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines, caught, starter, ran_finally


def measure_log(log_path):
    """从 run.log 反读实测：级别分布、"第N行"定位数、总行数——报告只认文件。"""
    with open(log_path, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    levels = {}
    for ln in lines:
        for lvl in ("INFO", "WARNING", "ERROR"):
            if " %s " % lvl in ln:
                levels[lvl] = levels.get(lvl, 0) + 1
    row_refs = len(re.findall(r"第\d+行", text))
    return levels, row_refs, len(lines)


def build(cfg, out_dir, echo=False):
    """跑完整采集流水线，返回 (sections, result)；result 供 pytest 断言。"""
    log_path, logger = setup_logging(out_dir, echo=echo)
    logger.info("采集开始：配置 %d 行", len(cfg.items))
    lines, caught, starter, ran_finally = _read_input_lines(cfg, out_dir)
    ok_rows, bad = [], []
    for i, raw in enumerate(lines, 1):
        try:
            temp, press = core.parse_row(raw)
        except ValueError as exc:
            caught.add("ValueError")
            bad.append(core.quarantine_line(i, raw, "非数值: %s" % exc))
            logger.warning("第%d行 脏数据跳过: %r —— %s", i, raw, exc)
            continue
        except IndexError as exc:
            caught.add("IndexError")
            bad.append(core.quarantine_line(i, raw, "缺字段: %s" % exc))
            logger.warning("第%d行 缺字段跳过: %r —— %s", i, raw, exc)
            continue
        good, reason = core.validate(temp, press)
        if not good:
            bad.append(core.quarantine_line(i, raw, reason))
            logger.warning("第%d行 校验不通过(%s): %r", i, reason, raw)
            continue
        ok_rows.append({"line": i, "temp": temp, "press": press})
        logger.info("第%d行 采集成功: 温度 %.1f℃ 压力 %.2fMPa",
                    i, temp, press)
    total = len(lines)
    bad_csv = os.path.join(out_dir, "bad_records.csv")
    io_utils.write_csv_rows(bad_csv, bad, ["line", "raw", "reason"])
    bad_written = len(io_utils.read_csv_rows(bad_csv))
    levels, row_refs, log_lines = measure_log(log_path)
    logger.info("采集统计（成功/跳过/合计）: %d/%d/%d",
                len(ok_rows), len(bad), total)
    reasons = {}
    for b in bad:
        reasons[b["reason"]] = reasons.get(b["reason"], 0) + 1
    stats_ok = len(ok_rows) + len(bad) == total
    style = stylecheck.scan_project(ROOT)
    result = {"total": total, "ok": len(ok_rows), "bad": len(bad),
              "success_rate": round(len(ok_rows) / max(total, 1), 4),
              "quarantine": bad, "rows": ok_rows,
              "stats_ok": stats_ok,
              "caught_exceptions": sorted(caught),
              "ran_finally": ran_finally, "starter": starter,
              "log": {"path": log_path, "lines": log_lines,
                      "levels": levels, "row_refs": row_refs},
              "bad_records_csv": bad_csv, "bad_csv_rows": bad_written,
              "style_rate": style["rate"],
              "style_violations": style["violations"],
              "style_engine": style["engine"]}
    result["tiers"] = tiers.verdict(
        rate=style["rate"], n_exc_types=len(caught),
        ran_finally=ran_finally, levels=levels, row_refs=row_refs,
        n_bad=len(bad), stats_ok=stats_ok, bad_csv_rows=bad_written,
        log_lines=log_lines)
    sections = [("输入口径", [
        "原始行 %d 条｜温度 0~200℃｜压力 0~5.0MPa" % total,
        "数据来源: %s（现场文件 %s）" % (
            starter, cfg.get("data_file", "未配置") or "未配置")]),
        ("采集统计（实测）", [
            "成功 %d 条｜跳过(隔离) %d 条｜合计 %d 条｜统计自洽: %s"
            % (len(ok_rows), len(bad), total,
               "是" if stats_ok else "否")]),
        ("隔离区", ["第%2d行 %-14r 原因: %s" % (b["line"], b["raw"], b["reason"])
         for b in bad] or ["无坏数据"]),
        ("失败原因分布",
         ["%s: %d 条" % (k, v) for k, v in sorted(reasons.items())] or ["-"]),
        ("日志与异常（logging 实测）", [
            "日志文件: %s（共 %d 行）" % (log_path, log_lines),
            "级别分布: INFO %d / WARNING %d / ERROR %d" % (
                levels.get("INFO", 0), levels.get("WARNING", 0),
                levels.get("ERROR", 0)),
            "可定位到行（日志含'第N行'）: %d 处" % row_refs,
            "本次实际捕获异常类型: %s" % (", ".join(sorted(caught)) or "无"),
            "finally 收尾已执行: %s" % ("是" if ran_finally else "否"),
            "脏数据备查: %s（%d 行）" % (bad_csv, bad_written)]),
        ("编码规范率（PEP 8 实测）", stylecheck.format_section(style, 90.0)),
        ("验收档位判定（实测）", tiers.render_lines(result["tiers"])),
        ("结论与建议", ["坏数据不进结果集，已自动写入 bad_records.csv 备查；"
         "人工复核隔离区后决定重采或补录"])]
    io_utils.ensure_dir(out_dir)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir, echo=False):
    """兼容旧入口：返回报告段（cli 用）。"""
    sections, _ = build(cfg, out_dir, echo=echo)
    return sections
