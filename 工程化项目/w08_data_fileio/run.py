#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""项目唯一入口（薄壳）——真正的命令行逻辑在 src/data_fileio/cli.py。

用法:
  python run.py                 # 按默认配置跑完整流水线并输出报告
  python run.py --config x.yaml # 指定配置文件
  python run.py --outdir out/   # 指定输出目录
  python run.py --quiet         # 只输出到文件，不打印到控制台
  python run.py --tier          # 打印工单 D/C/B/A 档位门槛 + 实测规范率
  python run.py --check         # 环境自检（哪些库装了/没装）
  python run.py --style-only    # 只做 PEP 8 规范体检
  python run.py --set k=v       # 命令行临时覆盖配置（可重复）

为什么 argparse 不在这里：pyproject 的 [project.scripts] 指向
`data_fileio.cli:main`，pip install -e . 后的命令入口与本文件必须同源，
否则会出现"文件入口能跑、命令入口不存在"的脱节。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from data_fileio.cli import main  # noqa: E402  （sys.path 注入后方可导入，src 布局必需）

if __name__ == "__main__":
    sys.exit(main())
