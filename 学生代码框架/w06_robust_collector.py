# -*- coding: utf-8 -*-
"""W06 健壮的工业数据采集程序 —— 异常处理与日志(含中期诊断)
运行前自动生成含脏数据的样例文件。
"""
import logging
import os

# ---------- 样例数据生成(勿改) ----------
RAW = "W06_raw_data.txt"
if not os.path.exists(RAW):
    with open(RAW, "w", encoding="utf-8") as f:
        f.write("temp,press\n56.2,0.45\n58.1,0.44\nerr,0.46\n57.5,\n61.0,0.47\n")

# ---------- TODO-1 日志配置: 控制台+文件, INFO级, 统一格式 ----------
# 格式: 时间 级别 消息 ; FileHandler(encoding="utf-8")
# logging.basicConfig(...)
logger = logging.getLogger("collector")


def read_lines(path):
    """TODO-2: 打开文件, FileNotFoundError→ERROR日志+返回[];
    逐行yield字符串"""
    # === 你的代码(用with open) ===
    return []


def parse(line):
    """TODO-3: 拆分temp,press并转float; 值错误→ValueError由上层捕获"""
    # === 你的代码 ===
    return 0.0, 0.0


def main():
    ok = skip = fail = 0
    for line in read_lines(RAW):
        if line.startswith("temp"):
            continue
        # TODO-4: try/except/except/finally 完整结构
        # ValueError→WARNING"脏数据跳过"+skip+1
        # 其他Exception→ERROR+fail+1
        # 正常→INFO记录+ok+1
    print(f"采集统计: 成功{ok} 跳过{skip} 失败{fail}")
    # TODO-5(优秀): 脏数据写入bad_records.csv


if __name__ == "__main__":
    main()
    # 中期诊断: 完成后填写平台问卷(课内第4环节)
