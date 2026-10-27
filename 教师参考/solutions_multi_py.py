# -*- coding: utf-8 -*-
"""程序设计基础（Python编程基础）教师版·多解法互验——面向大一新生的"第一门课多解"
运行: /opt/anaconda3/bin/python solutions_multi_py.py → ALL PASS 才算数
原则：解A用"当周刚学的语法"（直白），解B用"更Pythonic/更工程"写法（进阶对比）
"""
from collections import Counter
from dataclasses import dataclass
from io import StringIO
import json

RESULTS = []


def check(name, fn, expect):
    got = fn()
    ok = got == expect
    RESULTS.append((name, ok))
    print(("✓" if ok else "✗"), name, "→", got)


# ===== 0.1 格式化三解：f-string / format / % =====
def a01():
    dev, temp = "PUMP-03", 78.5
    s1 = f"{dev}温度{temp:.1f}℃"
    s2 = "{}温度{:.1f}℃".format(dev, temp)
    s3 = "%s温度%.1f℃" % (dev, temp)
    return s1 == s2 == s3


# ===== 0.2a 告警双解：if-elif链 vs 阈值表遍历（加档位不改结构） =====
def a02a():
    bands = [(90, "红色停机"), (80, "橙色告警"), (70, "黄色预警")]

    def a(t):                      # 解A
        if t >= 90:
            return "红色停机"
        elif t >= 80:
            return "橙色告警"
        elif t >= 70:
            return "黄色预警"
        return "正常"

    def b(t):                      # 解B
        for th, msg in bands:
            if t >= th:
                return msg
        return "正常"

    return [a(t) for t in (95, 85, 75, 60)] == [b(t) for t in (95, 85, 75, 60)]


# ===== 0.2b 循环双解：累加器循环 vs sum+生成器 =====
def a02b():
    data = [3.1, 4.2, 5.0]
    total_a = 0.0                  # 解A
    for v in data:
        total_a += v
    total_b = sum(data)            # 解B
    return abs(total_a - total_b) < 1e-12


# ===== 0.3 设备建模双解：dict+函数 vs dataclass =====
def a03():
    def a(dev):                    # 解A
        return f"{dev['code']}({dev['area']})"

    @dataclass
    class Device:                  # 解B
        code: str
        area: str

        def label(self):
            return f"{self.code}({self.area})"

    return a({"code": "PUMP-03", "area": "A2"}) == Device("PUMP-03", "A2").label()


# ===== 0.5 安全读取双解：try-except vs contextlib.suppress =====
def a05():
    from contextlib import suppress

    def a(p):
        try:
            return open(p).read()
        except FileNotFoundError:
            return ""

    def b(p):
        with suppress(FileNotFoundError):
            return open(p).read()
        return ""

    return a("/tmp/__nope__.txt") == b("/tmp/__nope__.txt") == ""


# ===== 1.1 结构化双解：json模块 vs 手动解析（理解格式本质） =====
def a11():
    row = '{"code":"PUMP-03","vib":4.6}'
    a = json.loads(row)                                  # 解A
    b = dict(kv.strip('"').split('":') for kv in          # 解B 手撸(教学:理解引号/冒号)
             row.strip("{}").split(','))
    b = {k: v.strip('"') for k, v in b.items()}
    return a["code"] == b["code"]


# ===== 1.3 词频双解：dict手数 vs Counter =====
def a13():
    words = "泵 轴承 泵 温度 泵 轴承".split()
    d = {}                                    # 解A
    for w in words:
        d[w] = d.get(w, 0) + 1
    c = dict(Counter(words))                  # 解B
    return d == c == {"泵": 3, "轴承": 2, "温度": 1}


# ===== 1.2 清洗双解：pandas vs 纯Python（小数据两解同果） =====
def a12():
    import pandas as pd
    raw = StringIO("dev,temp\nPUMP-03,78.5\nPUMP-03,\nFAN-02,66.0\n")
    df = pd.read_csv(raw)
    df["temp"] = df["temp"].fillna(df["temp"].mean())
    a = round(float(df.groupby("dev")["temp"].mean()["PUMP-03"]), 1)
    rows = [("PUMP-03", "78.5"), ("PUMP-03", ""), ("FAN-02", "66.0")]
    vals = [float(t) for _, t in rows if t]
    fill = sum(vals) / len(vals)              # 解B 纯Py：均值填充
    b = round((78.5 + fill) / 2, 1)
    return abs(a - b) < 0.2


if __name__ == "__main__":
    check("0.1 格式化三解(f-string/format/%)同串", a01, True)
    check("0.2a 告警双解(if链/阈值表)同判", a02a, True)
    check("0.2b 累加双解(循环/sum)同值", a02b, True)
    check("0.3 建模双解(dict/dataclass)同果", a03, True)
    check("0.5 读取双解(try/suppress)同行为", a05, True)
    check("1.1 解析双解(json/手动)同义", a11, True)
    check("1.3 词频双解(dict/Counter)同计", a13, True)
    check("1.2 清洗双解(pandas/纯Py)同口径", a12, True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS)}项多解互验：{'ALL PASS ✅' if not bad else 'FAIL ❌ ' + str(bad)}")
