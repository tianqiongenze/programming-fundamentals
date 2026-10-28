# -*- coding: utf-8 -*-
"""控制台入口：pyproject.toml 的 [project.scripts] 声明的正是本模块 main()。

pip install -e . 之后可直接键入脚本名（等价 python run.py）：
  w12_capstone                 跑完整流水线并落盘 output/
  w12_capstone --check         环境自检（工单"预习自测"：报告装了哪些库）
  w12_capstone --tier          打印工单 D/C/B/A 档位门槛 + 实测规范率
  w12_capstone --style-only    只做 PEP 8 规范体检（不跑业务）
  w12_capstone --set k=v       命令行临时覆盖配置（改配置不改代码的延伸）
"""
import argparse
import json
import os

from . import config as C
from . import pipeline as P
from . import stylecheck as S

ROOT = S.project_root(os.path.abspath(__file__))
SCRIPT = "w12_capstone"
DESC = "综合数据处理与项目交付（02-程序设计基础 W12 第23次课）"
# 工单四档：末列是"承诺档位"（本项目 run.py 实测并写进 output/report.txt）
TIERS = [
    ("及格(D)",
     "功能基本完整；能演示主流程（≥50 条数据）",
     80),
    ("良好(C)",
     "功能完整；讲清设计思路（Collector/Reporter 两类）",
     85),
    ("优秀(B)",
     "技术细节深入；有合理创新点（复用 W02/06/08/10）",
     90),
    ("优(A)",
     "架构图清晰；有明显工业应用价值",
     95),
]


def measured_claimed():
    """实测档位只认上一次 run.py 落盘的判定，不在代码里自称承诺。"""
    path = os.path.join(ROOT, "output", "result.json")
    try:
        with open(path, encoding="utf-8") as f:
            return (json.load(f).get("tiers") or {}).get("claimed")
    except (OSError, ValueError):
        return None


def _typed(v):
    """命令行传进来的永远是 str——按 int/float/bool 试还原（见工单 B03）。"""
    low = v.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            continue
    return v


def apply_overrides(cfg, pairs):
    """--set key=value 覆盖配置项（raw + 具名属性双写，保持口径一致）。"""
    for kv in pairs or []:
        key, _, val = kv.partition("=")
        key, val = key.strip(), val.strip()
        if not key or not _:
            raise SystemExit("--set 需写作 key=value，收到: %r" % kv)
        cfg.raw[key] = _typed(val)
        if hasattr(cfg, key) and key != "items":
            setattr(cfg, key, _typed(val))
    return cfg


def env_check():
    """环境自检：打印第三方库可用性——"环境也是选型维度"（课堂离线照样跑）。"""
    mods = ["yaml", "pycodestyle", "flake8", "jieba", "wordcloud", "PIL",
            "matplotlib", "reportlab", "paho.mqtt.client", "pymodbus.client",
            "numpy", "pandas"]
    print("[%s] 环境自检 · Python %s" % (SCRIPT, __import__("sys").version.split()[0]))
    for m in mods:
        try:
            mod = __import__(m, fromlist=["_"])
            ver = getattr(mod, "__version__", "已安装")
            print("  OK   %-18s %s" % (m, ver))
        except ImportError:
            print("  MISS %-18s 将走内置兜底路径（不影响交付）" % m)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog=SCRIPT, description=DESC)
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "rules.yaml"))
    ap.add_argument("--outdir", default=os.path.join(ROOT, "output"))
    ap.add_argument("--quiet", action="store_true", help="只落盘，不打印报告正文")
    ap.add_argument("--check", action="store_true", help="环境自检")
    ap.add_argument("--tier", action="store_true", help="打印工单档位门槛")
    ap.add_argument("--style-only", action="store_true", help="只跑规范体检")
    ap.add_argument("--set", dest="overrides", action="append", metavar="K=V",
                    help="临时覆盖配置项，可重复使用")
    a = ap.parse_args(argv)

    if a.check:
        return env_check()
    if a.tier:
        stats = S.scan_project(ROOT)
        print("工单 %s 验收档位（实测规范率 %.1f%%）:" % (DESC, stats["rate"]))
        for name, need, gate in TIERS:
            mark = "规范率达标" if stats["rate"] >= gate else "规范率不足"
            print("  %-8s 规范率≥%2.0f%% [%s]（本行只判规范率门）｜ 工单原文: %s"
                  % (name, gate, mark, need))
        print("  体检引擎: %s ｜ 功能门与实测档位见 output/report.txt 判定段"
              % stats["engine"])
        got = measured_claimed()
        print("  实测档位: %s" % (got or "尚未实跑（先运行 run.py 生成实测判定）"))
        return 0
    if a.style_only:
        stats = S.scan_project(ROOT)
        print("\n".join(S.format_section(stats, float(
            C.load_config(a.config).get("style_min", 85.0)))))
        return 0 if stats["violations"] == 0 else 1

    cfg = apply_overrides(C.load_config(a.config), a.overrides)
    sections = P.run(cfg, out_dir=a.outdir)
    if not a.quiet:
        from . import report as R
        print(R.render(sections))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
