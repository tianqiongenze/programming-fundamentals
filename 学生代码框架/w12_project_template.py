# -*- coding: utf-8 -*-
# [教学脚手架] 下列导入/变量供 TODO 完成后使用，故标注 noqa 而非删除
"""W12 综合项目《工业互联网完整数据处理系统》—— 项目模板(骨架)
分工建议(ABCD): 架构/开发/测试/文档, 每人至少负责一个类并答辩一题。
"""
import json  # noqa: F401
import logging
import random
import time

logger = logging.getLogger("system")
# TODO-0: logging配置(复用W06: 控制台+文件, UTF-8)


class Collector:
    """采集模块: 优先Modbus(W11); 无环境时用simulate()离线模式"""

    def __init__(self, mode="sim"):
        self.mode = mode

    def simulate(self, n=60):
        """TODO-1: 生成n条模拟数据(含约10%脏数据)"""
        rows = []
        for i in range(n):
            t = round(random.uniform(45, 100), 1)
            if random.random() < 0.1:
                t = random.choice(["", "err"])
            rows.append({"device_id": f"DEV-{i % 3 + 1:02d}",
                         "ts": time.strftime("%H:%M:%S"),
                         "temp": t, "press": round(random.uniform(.3, .6), 2)})
        return rows

    def collect(self):
        # TODO-2(进阶): modbus模式调用W11的read_plc
        return self.simulate()


class Cleaner:
    """TODO-3 清洗模块: 复用W08三维验证(缺失/类型/范围)"""

    def clean(self, rows):
        # === 返回(干净行, 问题行) ===
        return rows, []


class Analyzer:
    """TODO-4 分析模块: 阈值异常检测(复用W02) + 简单统计(均值/最大)"""

    def analyze(self, rows):
        return {"alerts": [], "mean_temp": 0}


class Reporter:
    """TODO-5 报告模块: 复用W10生成PDF; 复用W09词云(优秀)"""

    def build(self, stats, path="项目报告.pdf"):
        pass


def main():
    rows = Collector().collect()
    clean, bad = Cleaner().clean(rows)
    stats = Analyzer().analyze(clean)
    print("原始%d 干净%d 问题%d" % (len(rows), len(clean), len(bad)))
    print(stats)
    Reporter().build(stats)


if __name__ == "__main__":
    main()
