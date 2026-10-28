# -*- coding: utf-8 -*-
"""控制台入口：pyproject.toml 的 [project.scripts] 声明的正是本模块 main()。

pip install -e . 之后可直接键入脚本名（等价 python run.py）：
  w08_data_fileio                 跑完整流水线并落盘 output/
  w08_data_fileio --check         环境自检（工单"预习自测"：报告装了哪些库）
  w08_data_fileio --tier          打印工单 D/C/B/A 档位门槛 + 实测规范率
  w08_data_fileio --style-only    只做 PEP 8 规范体检（不跑业务）
  w08_data_fileio --set k=v       命令行临时覆盖配置（改配置不改代码的延伸）
"""
import argparse
import os

from . import config as C
from . import pipeline as P
from . import stylecheck as S
from . import tiers as T

ROOT = S.project_root(os.path.abspath(__file__))
SCRIPT = "w08_data_fileio"
DESC = "工业数据文件处理（02-程序设计基础 W08 第15次课）"
# 工单四档门槛的单一出处在 tiers.py（与 tests/test_tiers.py 同一判据）
TIERS = T.TIERS
CLAIMED = "A（--input/--encoding 命令行参数）"


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
    ap.add_argument("--input", default=None,
                    help="输入数据文件（CSV，A 档命令行选文件）")
    ap.add_argument("--encoding", default=None,
                    help="输入文件编码（现场 GBK 文件演示：--encoding gbk）")
    ap.add_argument("--set", dest="overrides", action="append", metavar="K=V",
                    help="临时覆盖配置项，可重复使用")
    a = ap.parse_args(argv)

    if a.check:
        return env_check()
    if a.tier:
        cfg = apply_overrides(C.load_config(a.config), a.overrides)
        _sections, result = P.build(cfg, out_dir=a.outdir,
                                    input_path=a.input, encoding=a.encoding)
        stats = S.scan_project(ROOT)
        v = result["tiers"]
        print("工单 %s 验收档位（实测规范率 %.1f%%，引擎 %s）:"
              % (DESC, stats["rate"], stats["engine"]))
        for line in T.render_lines(v):
            print("  " + line)
        print("  承诺档位: %s ｜ 实测达成: %s" % (CLAIMED, v["claimed"]))
        return 0
    if a.style_only:
        stats = S.scan_project(ROOT)
        print("\n".join(S.format_section(stats, float(
            C.load_config(a.config).get("style_min", 85.0)))))
        return 0 if stats["violations"] == 0 else 1

    cfg = apply_overrides(C.load_config(a.config), a.overrides)
    sections = P.run(cfg, out_dir=a.outdir, input_path=a.input,
                     encoding=a.encoding)
    if not a.quiet:
        from . import report as R
        print(R.render(sections))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
