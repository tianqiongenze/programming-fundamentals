# -*- coding: utf-8 -*-
# [教学脚手架] 下列导入/变量供 TODO 完成后使用，故标注 noqa 而非删除
"""W08 工业数据文件处理系统 —— 文件IO与数据验证
运行自动生成脏数据样例 raw_metrics.csv。
"""
import csv
import json  # noqa: F401
import os
import random

RAW = "raw_metrics.csv"
CLEAN = "clean_metrics.csv"
BAD = "bad_records.csv"

# ---- 样例生成(勿改): 60行, 含缺失/类型错/越界 ----
if not os.path.exists(RAW):
    random.seed(7)
    with open(RAW, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["device_id", "temp", "press", "status"])
        for i in range(60):
            t = round(random.uniform(40, 90), 1)
            if i % 17 == 3:
                t = ""              # 缺失
            if i % 23 == 5:
                t = "err"           # 类型错
            if i % 29 == 7:
                t = 135.0           # 越界
            w.writerow([f"DEV-{i % 3 + 1:02d}", t,
                        round(random.uniform(0.3, 0.6), 2), "RUN"])


def validate(row):
    """TODO-1 三维验证: 返回错误类型或None
    缺失(temp为空)/类型(非数值)/范围(temp>120或<0)"""
    # === 你的代码 ===
    return None


def main():
    ok, bad_rows = 0, []  # noqa: F841
    # TODO-2: with open读取RAW, 逐行validate
    #   None→写入CLEAN并ok+1 ; 错误→bad_rows.append([行内容,错误类型])
    # TODO-3: bad_rows写入BAD(带表头)
    # TODO-4: 输出清洗报告: 总数/成功/各错误类型计数
    print("清洗报告: ...")


if __name__ == "__main__":
    main()
    # 决策(写进工单): 温度135℃是"越界剔除"还是"真实过热保留"? 说明理由
