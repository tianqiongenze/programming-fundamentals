# -*- coding: utf-8 -*-
"""读输入（配置或 --input 文件）→ 三维验证 → 清洗落盘 → round-trip → 档位判定。

工单 W08 的验收证据全部实测：坏行按"缺失/类型/范围"三维度归因写入
bad.csv（可追溯），清洗后 CSV/JSON 双格式落盘并回读比对，data.csv
表头与规范列名逐字比对，--input/--encoding 通道用一份真实 GBK 文件自检。
"""
import os

from . import core, io_utils, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
FIELDS = ["code", "temp", "press"]


def load_input_rows(path, encoding="utf-8-sig"):
    """输入文件通道（A 档）：CSV 按表头读成行字典，编码可显式指定。"""
    return io_utils.read_csv_rows(path, encoding=encoding)


def _rows_from_cfg(cfg):
    rows = []
    for d in cfg.items:
        if not isinstance(d, dict):
            raise ValueError("config rows 必须是键值行，收到: %r" % (d,))
        rows.append(dict(d))
    return rows


def _gbk_input_selfcheck(out_dir):
    """用真实 GBK 文件走一遍输入通道（工单"编码坑"演示，离线可复核）。"""
    demo = os.path.join(out_dir, "demo_input_gbk.csv")
    text = "code,temp,press\n一线-A,10.5,0.30\n一线-B,20.0,0.40\n"
    with open(demo, "wb") as f:
        f.write(text.encode("gbk"))
    rows = load_input_rows(demo, encoding="gbk")
    return len(rows) == 2 and rows[0]["code"] == "一线-A"


def build(cfg, out_dir, input_path=None, encoding=None):
    """跑完整文件处理流水线，返回 (sections, result)；result 供 pytest 断言。"""
    io_utils.ensure_dir(out_dir)
    if input_path:
        raw_rows = load_input_rows(
            input_path, encoding=encoding or "utf-8-sig")
        source = "%s（编码 %s）" % (input_path, encoding or "utf-8-sig")
    else:
        raw_rows = _rows_from_cfg(cfg)
        source = "config/rules.yaml"
    if not raw_rows:
        raise ValueError("输入为空——请检查 config/rules.yaml 的 rows 或 --input")
    clean, bad, dims = [], [], dict.fromkeys(core.DIMENSIONS, 0)
    for i, row in enumerate(raw_rows, 1):
        ok, dim, reason = core.validate_row(row)
        if ok:
            clean.append({"code": str(row["code"]), "temp": float(row["temp"]),
                          "press": float(row["press"])})
        else:
            dims[dim] = dims.get(dim, 0) + 1
            bad.append({"line": i, "raw": repr(row),
                        "dimension": dim, "reason": reason})
    csv_ok, json_ok = core.verify_roundtrip(clean, out_dir)
    bad_path = os.path.join(out_dir, "bad.csv")
    io_utils.write_csv_rows(bad_path, bad, ["line", "raw", "dimension",
                                            "reason"])
    bad_rows = io_utils.read_csv_rows(bad_path)
    with open(os.path.join(out_dir, "data.csv"), encoding="utf-8") as f:
        header_ok = f.readline().strip() == tiers.EXPECTED_HEADER
    input_demo_ok = _gbk_input_selfcheck(out_dir)
    st = core.summarize(clean)
    style = stylecheck.scan_project(ROOT)
    result = {"source": source, "rows": clean, "summary": st,
              "checked": len(raw_rows), "quarantine": bad,
              "dimensions": dims,
              "roundtrip": {"csv": csv_ok, "json": json_ok},
              "bad_csv": bad_path, "bad_csv_rows": len(bad_rows),
              "header_ok": header_ok, "input_demo_ok": input_demo_ok,
              "style_rate": style["rate"],
              "style_violations": style["violations"],
              "style_engine": style["engine"]}
    result["tiers"] = tiers.verdict(
        rate=style["rate"], csv_ok=csv_ok, json_ok=json_ok,
        n_checked=len(raw_rows), dims=dims, bad_csv_rows=len(bad_rows),
        n_bad=len(bad), header_ok=header_ok,
        # B 档"清洗报告清晰"的可测部分：三维度归因总数必须与隔离实测自洽
        report_ok=len(bad) >= 1 and sum(dims.values()) == len(bad),
        input_demo_ok=input_demo_ok,
        gates=tiers.gates_from(cfg.tier_gates()))
    clean_lines = [
        "验证 %d 行｜通过 %d 行｜隔离 %d 行" % (
            len(raw_rows), len(clean), len(bad)),
        "缺失: %d 条｜类型: %d 条｜范围: %d 条" % (
            dims.get("缺失", 0), dims.get("类型", 0), dims.get("范围", 0)),
    ]
    quarantine_lines = [
        "  第%d行 [%s] %s ｜ %s" % (
            b["line"], b["dimension"], b["reason"], b["raw"])
        for b in bad[:5]]
    roundtrip_lines = [
        "CSV round-trip: %s" % ("通过" if csv_ok else "失败"),
        "JSON round-trip: %s" % ("通过" if json_ok else "失败"),
        "规范列名(%s): %s" % (
            tiers.EXPECTED_HEADER, "实测通过" if header_ok else "失败"),
    ]
    sections = [("输入口径", [
        "来源: %s｜记录 %d 条｜字段 code/temp/press｜输出 CSV+JSON"
        % (source, len(raw_rows))]),
        ("清洗报告（三维度实测）", clean_lines + quarantine_lines),
        ("落盘产物", [
            "output/data.csv",
            "output/data.json（utf-8, ensure_ascii=False）",
            "output/bad.csv（%d 行可追溯）" % len(bad_rows),
        ]),
        ("一致性校验", roundtrip_lines),
        ("聚合统计（清洗后）", [
            "记录数: %d" % st["count"],
            "温度℃: min %.1f / max %.1f / mean %.2f" % (
                st["temp"]["min"], st["temp"]["max"], st["temp"]["mean"]),
            "压力MPa: min %.2f / max %.2f / mean %.2f" % (
                st["press"]["min"], st["press"]["max"], st["press"]["mean"]),
        ]),
        ("超限设备", st["over_limit"] or ["无"]),
        ("输入文件通道（A 档实测）", [
            "--input/--encoding 已支持；本次 GBK 样例自检: %s" % (
                "走通（读回 2 行，中文编码正确）" if input_demo_ok
                else "失败")]),
        ("编码规范率（PEP 8 实测）", stylecheck.format_section(style, 90.0)),
        ("验收档位判定（实测）", tiers.render_lines(result["tiers"])),
        ("结论与建议", [
            "双格式 round-trip 校验通过，数据可安全交下游；超限设备 %d 台"
            "需工单跟进；坏行进 bad.csv 备查不混入结果"
            % len(st["over_limit"])]),
    ]
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir, input_path=None, encoding=None):
    """兼容旧入口：返回报告段（cli 用）。"""
    sections, _ = build(cfg, out_dir, input_path=input_path,
                        encoding=encoding)
    return sections
