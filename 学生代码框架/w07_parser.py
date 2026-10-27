# -*- coding: utf-8 -*-
# [教学脚手架] 下列导入/变量供 TODO 完成后使用，故标注 noqa 而非删除
"""W07 工业数据格式转换工具 —— 容器+正则(六步法: 决策→实施)"""
import json  # noqa: F401
import re  # noqa: F401

# 三种原始格式样例(可扩充)
MSG = "DEV-01:temp=56.3C;press=0.45MPa;status=RUN"
CSV_LINE = "DEV-02,55.1,0.44,RUN"
JSON_STR = '{"device_id": "DEV-03", "temp": 54.8, "press": 0.46, "status": "RUN"}'


def parse_message(msg):
    r"""TODO-1 正则解析报文串 → 标准字典
    目标: {"device_id":"DEV-01","metrics":{"temp":56.3,"press":0.45,"status":"RUN"}}
    提示: re.match(r'([A-Z]+-\d+):', msg)取ID; re.findall(r'(\w+)=([\d.]+|\w+)', ...)取键值
    数值自动转float(用try或判断)"""
    # === 你的代码 ===
    return {}


def parse_csv(line):
    """TODO-2 CSV行解析 → 同样的标准字典"""
    # === 你的代码 ===
    return {}


def parse_json(text):
    """TODO-3 json.loads后重组为标准字典(metrics嵌套)"""
    # === 你的代码 ===
    return {}


if __name__ == "__main__":
    # TODO-4: 三种格式各转一条, 打印对照, 验证结构一致
    # TODO-5(优秀): 容错——缺字段/乱序也能出结果(缺的置None)
    pass
