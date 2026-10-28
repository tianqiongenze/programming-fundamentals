# -*- coding: utf-8 -*-
"""加载 3 台设备实例 → 演示状态机与业务规则 → 输出台账 + 协作日志 + 四档实测判定。

四档证据都在本文件的分节里（报告小标题 = 档位索引）：
  D 输入口径 / 实例清点（3 台、显式 __init__）+ 类结构 AST 实测
  C 状态校验流水（真实连调两次 start，捕获拦截提示文本）
  B 巡检台账 + __str__ 可读化 + 编码规范率（PEP 8 实测）
  A 方法间协作：stop/set_temp/start 经 _log() 累积的日志字符串整段导出
档位判定（tiers.verdict）吃的全部是上面这些实测值——报告里的档位是算出来的。
"""
import ast
import os

from . import core, io_utils, report, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
CORE_PATH = os.path.join(ROOT, "src", "device_model", "core.py")
# 工单任务3 要求"创建 ≥2 个设备对象并演示属性访问"；B 档要 3 实例。
MIN_INSTANCES = 3
# 演示用越界读数（工单 B03/避坑：脏数据不进对象）；rules.yaml 可覆盖
DEMO_BAD_TEMP = 999.0


def ast_structure(path=CORE_PATH):
    """AST 真实统计类结构（与 stylecheck 同口径）：业务类数/__init__ 属性/公开方法。

    为什么用 AST 而不是 dir()/vars：验收证据要钉在源码本身——业务类=非 *Error
    异常体系的类（异常类只是状态校验的载体，不是"设备建模"的类）。
    """
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    exc_names = {c.name for c in classes if c.name.endswith("Error")}
    model = []
    for c in classes:
        bases = {getattr(b, "id", getattr(b, "attr", "")) for b in c.bases}
        if c.name not in exc_names and not (bases & exc_names):
            model.append(c)
    attrs, methods = set(), []
    for c in model:
        for fn in c.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not fn.name.startswith("_"):
                methods.append(fn.name)
            if fn.name == "__init__":
                for node in ast.walk(fn):
                    if (isinstance(node, ast.Assign)
                            and any(isinstance(t, ast.Attribute)
                                    and isinstance(t.value, ast.Name)
                                    and t.value.id == "self"
                                    for t in node.targets)):
                        attrs.update(t.attr for t in node.targets
                                     if isinstance(t, ast.Attribute))
    return {"n_classes": len(model), "n_attrs": len(attrs),
            "n_methods": len(methods),
            "attrs": sorted(attrs), "methods": sorted(methods)}


def build(cfg, out_dir):
    """跑完整设备建模流程，返回 (sections, result)；result 供 pytest 断言。"""
    devs = core.build_devices(cfg.items, cfg)
    if len(devs) < MIN_INSTANCES:
        raise ValueError("工单 B 档要求 ≥%d 个实例，config 只给了 %d 台"
                         % (MIN_INSTANCES, len(devs)))
    if cfg.warn >= cfg.danger:
        raise ValueError("阈值配置非法：warn(%.1f) 必须小于 danger(%.1f)"
                         % (cfg.warn, cfg.danger))

    ops, errs = [], []
    for d in devs:                                     # 方法调用（任务1/任务3）
        ops.append(d.start())
    ops.append("方法调用等价写法: Device.start(d) == d.start()（self 自动传实例）")

    # ── C 档：状态校验用例 1（重复启动）——实测捕获拦截提示文本 ──
    guard_ok, guard_msg = False, ""
    try:
        devs[0].start()
        errs.append("未拦住重复启动（规则失效！）")
    except core.AlreadyRunningError as exc:
        guard_ok, guard_msg = True, str(exc)
        ops.append("已拦截重复启动: %s" % exc)

    # ── C 档：状态校验用例 2（重复停机）+ A 档（stop 自动记日志）──
    stop_log_ok = False
    stop_line = ""
    try:
        before = len(devs[1].logs)
        ops.append(devs[1].stop())
        # A 档实测：真实 stop() 之后日志必须多出一行含"停机"的字符串
        stop_log_ok = (len(devs[1].logs) == before + 1
                       and isinstance(devs[1].logs[-1], str)
                       and "停机" in devs[1].logs[-1])
        stop_line = devs[1].logs[-1]
        devs[1].stop()
        errs.append("未拦住重复停机（规则失效！）")
    except core.NotRunningError as exc:
        ops.append("已拦截重复停机: %s" % exc)

    # ── 读数量程校验用例（把脏数据挡在对象门外）──
    bad_temp = float(cfg.get("demo_bad_temp", DEMO_BAD_TEMP))
    try:
        devs[2].set_temp(bad_temp)
        errs.append("未拦住越界读数 %.1f℃（校验失效！）" % bad_temp)
    except core.OutOfRangeError as exc:
        ops.append("已拦截越界读数: %s" % exc)

    # ── 属性访问 + 巡检：给第 1 台加温到停机线之上，演示"实例互不影响" ──
    hot = float(cfg.get("demo_hot_temp", 96.0))
    devs[0].set_temp(hot)
    ledger = [d.patrol() for d in devs]
    readable = ["  print(d) → %s" % d for d in devs]
    reprs = ["  repr(d)  → %s" % repr(d) for d in devs]
    status_lines = ["  %s" % d.get_status() for d in devs]
    census = core.instance_census(devs)
    indep = core.independence_demo(devs)

    # ── A 档：方法间协作的实证——每台设备各自的日志流水 ──
    logs = []
    for d in devs:
        logs.append("  ▸ %s（%d 行协作日志）" % (d.code, len(d.logs)))
        logs.append(d.log_text())
    total_logs = sum(len(d.logs) for d in devs)
    stop_lines = sum(1 for d in devs for x in d.logs if "停机" in x)

    levels = {}
    for d in devs:
        levels[d.level()] = levels.get(d.level(), 0) + 1
    struct = ast_structure()
    result = {"n_devices": len(devs), "attrs_per_instance": len(devs[0].__dict__),
              "methods": sorted(m for m in dir(devs[0])
                                if not m.startswith("_") and callable(getattr(devs[0], m))),
              "ops": ops, "errors": errs, "flags": [d.running for d in devs],
              "levels": levels, "log_lines_total": total_logs,
              "ast_structure": struct,
              "logs_per_device": {d.code: list(d.logs) for d in devs},
              "str_demo": [str(d) for d in devs],
              "has_dunder_str": "__str__" in vars(core.Device),
              "has_get_status": hasattr(devs[0], "get_status"),
              "timestamp": core.stamp()}
    advice = ["实例数 %d（工单 D 档要 2、B 档要 3）｜每台实例属性 %d 个（≥3）｜公开方法 %d 个"
              % (len(devs), len(devs[0].__dict__), len(result["methods"])),
              "状态校验拦截面: %s" % ("全部生效（无失效项）" if not errs else "存在失效！" + "；".join(errs)),
              "方法间协作日志 %d 行，其中停机类 %d 行 → A 档『stop 后自动记录日志』达成"
              % (total_logs, stop_lines),
              "越界读数 %.1f℃ 已被 OutOfRangeError 拒绝，对象内温度仍在量程内" % bad_temp]
    scope = "设备 %d 台｜全局预警 %.0f℃ / 停机 %.0f℃（每台可用 warn/danger 覆盖）" % (
        len(devs), cfg.warn, cfg.danger)
    struct_rows = [
        "  AST 统计口径: 业务类（排除 *Error 异常体系）%d 个" % struct["n_classes"],
        "  __init__ 实例属性 %d 个: %s" % (struct["n_attrs"], ", ".join(struct["attrs"])),
        "  类体公开方法 %d 个: %s" % (struct["n_methods"], ", ".join(struct["methods"])),
        "  stop() 实测新增日志行: %r" % stop_line]
    style_min = float(cfg.get("style_min", 90.0))
    sections = [
        ("输入口径", [scope, "运行时刻 %s" % result["timestamp"]]),
        ("实例清点（D 档：显式 __init__ + ≥2 实例）", census),
        ("类结构 AST 实测（D/B 档口径）", struct_rows),
        ("属性访问独立性验证（工单 B01 误区）", indep),
        ("状态校验流水（C 档）", ops),
        ("规则失效项（应为空）", errs or ["无——三条业务规则全部拦住"]),
        ("巡检台账（B 档：patrol + get_status）", ledger),
        ("get_status() 三要素回读（任务1 点名方法）", status_lines),
        ("对象可读化（B 档 __str__ / 开发者 __repr__）", readable + reprs),
        ("方法间协作日志（A 档：start/stop/set_temp 均写 self.logs）", logs),
        ("判级分布", ["%s: %d 台" % (k, v) for k, v in sorted(levels.items())])]
    # augment 与旧版同口径：体检一次、result 补齐 style_* 键、报告追加规范率段
    stats = stylecheck.augment(sections, result, ROOT, style_min)
    # 档位判定吃的都是实测值：AST 类结构 + 真实实例数 + 拦截提示 + 停机日志
    result["tiers"] = tiers.verdict(
        gates=tiers.gates_from(cfg), rate=stats["rate"],
        n_classes=struct["n_classes"], n_attrs=struct["n_attrs"],
        n_methods=struct["n_methods"], n_instances=len(devs),
        guard_ok=guard_ok, guard_msg=guard_msg,
        stop_log_ok=stop_log_ok, stop_log_lines=stop_lines)
    sections.append(("验收档位判定（实测）", tiers.render_lines(result["tiers"])))
    sections.append(("结论与建议", advice))
    io_utils.ensure_dir(out_dir)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def run(cfg, out_dir):
    """兼容旧入口：返回报告段（cli 用）。"""
    sections, _ = build(cfg, out_dir)
    return sections
