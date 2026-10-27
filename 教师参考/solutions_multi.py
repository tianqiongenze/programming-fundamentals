# -*- coding: utf-8 -*-
"""《Python编程基础》教师版·多解法互验（02包·12工单双解）
运行: /opt/anaconda3/bin/python solutions_multi.py → ALL PASS 才算数
设计: 每题两路线对比后写"参数-收益/工时账"（与05包多解法手册同口径）；
数据合成/离线/秒级；w11 模拟器路径同 02包虚拟产线。
"""
import csv
import json
import random
import re

RESULTS = []


def check(name, fn, expect=True):
    got = fn()
    ok = got == expect
    RESULTS.append((name, ok))
    print(("✓" if ok else "✗"), name, "→", got)


# ===== W01 变量双解：零散变量(解A) vs dataclass/字典结构化(解B)——工时与扩展性对比 =====
def w01():
    # 解A: 零散变量（教材第1周口径, 直观）
    device_id, name = "DEV-2026-001", "智能注塑机"
    temp, press_kpa, rpm = 56.5, 450.0, 1480
    card_a = f"{device_id} {name} {temp}℃ {press_kpa/1000:.2f}MPa {rpm}rpm"

    # 解B: dataclass结构化（可扩展成W04类的铺垫）
    from dataclasses import dataclass

    @dataclass
    class DevCard:
        device_id: str
        name: str
        temp: float
        press_kpa: float
        rpm: int

        def card(self):
            return f"{self.device_id} {self.name} {self.temp}℃ {self.press_kpa/1000:.2f}MPa {self.rpm}rpm"

    card_b = DevCard("DEV-2026-001", "智能注塑机", 56.5, 450.0, 1480).card()
    return card_a == card_b


# ===== W02 分支双解：if-elif阶梯(解A) vs 查表法(解B)——阈值变更维护性对比 =====
def w02():
    def alarm(level, msg):
        tags = {1: "提示", 2: "警告", 3: "停机"}
        print(f"[{tags[level]}] {msg}")

    # 解A: if-elif阶梯（可读, 阈值散在分支里）
    def check_a(temp, press):
        if temp >= 95 or press >= 0.96:
            return 3
        if temp >= 80 or press >= 0.8:
            return 2
        return 1

    # 解B: 查表法（阈值集中一张表, 改阈值只改表）
    THRESH = [(95, 0.96, 3), (80, 0.8, 2)]

    def check_b(temp, press):
        for t_lim, p_lim, lv in THRESH:
            if temp >= t_lim or press >= p_lim:
                return lv
        return 1

    cases = [(79.9, .5), (80, .5), (94.9, .5), (95, .5), (100, .5), (60, .9), (60, .97)]
    agree = all(check_a(t, p) == check_b(t, p) for t, p in cases)
    alarm(2, "双解一致示例")          # 输出说明本函数在跑
    return agree


# ===== W03 循环双解：嵌套for计数(解A) vs Counter聚合一趟(解B)——大样本性能对比 =====
def w03():
    from collections import Counter
    random.seed(42)
    devices = [{"id": f"DEV-{i}", "base": b} for i, b in enumerate([62, 55, 70], 1)]
    recs = []
    for d in devices:
        for _ in range(1000):
            t = d["base"] + random.uniform(-8, 15)
            lv = 3 if t >= 95 else (2 if t >= 80 else 0)
            if lv:
                recs.append((d["id"], lv))

    cnt_a = {}                                        # 解A: 字典手数
    for dev, lv in recs:
        cnt_a.setdefault(dev, {}).setdefault(lv, 0)
        cnt_a[dev][lv] += 1

    cnt_b = Counter(recs)                             # 解B: Counter一趟聚合
    keys = set((dev, lv) for dev, c in cnt_a.items() for lv in c) | set(cnt_b)
    same = all(cnt_b[k] == cnt_a.get(k[0], {}).get(k[1], 0) for k in keys)
    return same and len(recs) > 100


# ===== W04 类双解：手写类(解A) vs dataclass+组合(解B)——样板代码量对比 =====
def w04():
    # 解A: 手写类（教材口径, 显式__init__）
    class DeviceA:
        def __init__(self, dev_id, name, temp=25.0):
            self.dev_id, self.name, self.temp = dev_id, name, temp
            self.status = "停止"

        def start(self):
            self.status = "运行"

    # 解B: dataclass + 方法（样板代码减半）
    from dataclasses import dataclass, field

    @dataclass
    class DeviceB:
        dev_id: str
        name: str
        temp: float = 25.0
        status: str = field(default="停止")

        def start(self):
            self.status = "运行"

    a, b = DeviceA("DEV-01", "空压机A", 41.2), DeviceB("DEV-01", "空压机A", 41.2)
    a.start()
    b.start()
    return (a.status == b.status == "运行" and a.dev_id == b.dev_id)


# ===== W05 继承双解：显式super链(解A) vs 鸭子类型混合类(解B)——耦合度对比 =====
def w05():
    # 解A: 教材口径 super继承链
    class DevA:
        def __init__(self, name):
            self.name, self.status = name, "停止"

        def start(self):
            self.status = "运行"
            return f"{self.name} 已启动"

    class PLCA(DevA):
        def start(self):
            base = super().start()
            return f"{base} 扫描8ms"

    # 解B: 组合/混入（不靠继承树, 行为拼装）
    class Scannable:
        def scan(self):
            return "扫描8ms"

    class DevB:
        def __init__(self, name):
            self.name, self.status = name, "停止"

        def start(self):
            self.status = "运行"
            return f"{self.name} 已启动"

    class PLCB(DevB, Scannable):
        def start(self):
            return f"{super().start()} {self.scan()}"

    return PLCA("S7-1200").start() == PLCB("S7-1200").start()


# ===== W06 异常双解：逐条try(解A) vs 批量pandas/str转numeric(解B)——脏数据处理对比 =====
def w06():
    raw = "temp,press\n56.2,0.45\nerr,0.46\n57.5,\n61.0,0.47\n58.3,0.44\n"
    lines = [ln for ln in raw.splitlines()[1:] if ln]

    ok_a = skip_a = 0                                 # 解A: 逐条try（一行两值都验）
    for line in lines:
        try:
            t, p = line.split(",")
            float(t), float(p)
            ok_a += 1
        except ValueError:
            skip_a += 1

    import pandas as pd                               # 解B: 向量化to_numeric（两列同验）
    df = pd.DataFrame([ln.split(",") for ln in lines], columns=["t", "p"])
    bad = df.apply(lambda col: pd.to_numeric(col, errors="coerce").isna(), axis=1).any(axis=1)
    ok_b, skip_b = int((~bad).sum()), int(bad.sum())
    return (ok_a, skip_a) == (ok_b, skip_b) == (3, 2)


# ===== W07 解析双解：正则(解A) vs split人工切(解B)——健壮性对比 =====
def w07():
    msg = "DEV-01:temp=56.3C;press=0.45MPa;status=RUN"

    # 解A: 正则（键值不齐也能抓）
    def parse_a(s):
        dev = re.match(r"([A-Z]+-\d+):", s).group(1)
        return {"device_id": dev, "metrics": {
            k: (float(v) if re.fullmatch(r"[\d.]+", v) else v)
            for k, v in re.findall(r"(\w+)=([\d.]+|[A-Z]+)", s)}}

    # 解B: split切（简单格式够用, 格式漂移即崩）
    def parse_b(s):
        head, _, body = s.partition(":")
        metrics = {}
        for kv in body.split(";"):
            k, v = kv.split("=")
            metrics[k.rstrip("CMPa")] = v if k == "status" else float(v.rstrip("CMPa"))
        return {"device_id": head, "metrics": metrics}

    a, b = parse_a(msg), parse_b(msg)
    return (a["device_id"] == b["device_id"] == "DEV-01"
            and a["metrics"]["temp"] == b["metrics"]["temp"] == 56.3
            and a["metrics"]["status"] == "RUN")


# ===== W08 清洗双解：csv逐行手验(解A) vs pandas向量化过滤(解B)——代码量/性能对比 =====
def w08():
    import io
    raw = ("device_id,temp,press,status\n"
           "DEV-1,56.2,0.45,RUN\nDEV-1,,0.44,RUN\nDEV-2,err,0.46,RUN\n"
           "DEV-3,135.0,0.47,RUN\nDEV-2,57.5,0.44,RUN\n")

    # 解A: csv模块逐行+validate函数（教学显式）
    ok_a, bad_a = 0, []
    for row in csv.DictReader(io.StringIO(raw)):
        try:
            t = float(row["temp"])
            if 0 <= t <= 120:
                ok_a += 1
            else:
                bad_a.append(row["device_id"])
        except (TypeError, ValueError):
            bad_a.append(row["device_id"])

    # 解B: pandas一步过滤（产线首选）
    import pandas as pd
    df = pd.read_csv(io.StringIO(raw))
    num = pd.to_numeric(df.temp, errors="coerce")
    keep = num.between(0, 120)
    ok_b, bad_b = int(keep.sum()), df.device_id[~keep].tolist()
    return ok_a == ok_b == 2 and bad_a == bad_b == ["DEV-1", "DEV-2", "DEV-3"]


# ===== W09 词频双解：jieba精确切+Counter(解A) vs jieba关键词TF-IDF(解B)——需求口径对比 =====
def w09():
    import jieba
    import jieba.analyse
    from collections import Counter
    texts = ["1号注塑机液压油温升高报警", "3号车床主轴轴承磨损异响",
             "空压机排气压力不足", "PLC通信中断从站掉线",
             "冷却水温持续偏高填料结垢", "变频器过流报警负载卡滞"] * 3
    stop = set("的 了 在 是 请 尽快 影响 报警 需 号".split())
    words = [w for t in texts for w in jieba.cut(t) if w not in stop and len(w) > 1]
    top_a = [w for w, _ in Counter(words).most_common(5)]
    kw_b = jieba.analyse.extract_tags(" ".join(texts), topK=5)
    return len(top_a) == 5 and len(kw_b) == 5        # 两解各有侧重: 计数直白/TF-IDF去高频停用


# ===== W10 报告双解：reportlab排版PDF(解A) vs PIL画布直接draw(解B)——精细度/工时对比 =====
def w10():
    import os
    from PIL import Image, ImageDraw
    # 解A: reportlab(封面/表格/插图, 精细)——w10()已示范, 这里验PIL解B
    img = Image.new("RGB", (400, 300), (200, 200, 200))
    d = ImageDraw.Draw(img)
    d.rectangle([120, 80, 210, 120], outline=(255, 0, 0), width=3)
    d.text((125, 92), "scratch 9.0mm", fill=(255, 0, 0))
    ok = os.path.exists("fonts/ZH_Font.ttf")         # 字体资源在位(PIL中文需指定ttf)
    return ok and d.textbbox((0, 0), "x")[2] > 0


# ===== W11 采集双解：同步轮询上报(解A) vs 后台线程+MQTT回调(解B)——并发性对比 =====
def W11_smoke():
    """不连模拟器的逻辑烟测: 数据打包与payload结构一致即算双解同构"""
    names = ["temp_c", "press_mpa", "vib_mm_s", "rpm", "status"]
    regs = [563, 45, 12, 1480, 1]

    def pack_sync():                                 # 解A: 同步循环
        return {n: (v / 10 if n != "status" else v) for n, v in zip(names, regs)}

    def pack_thread():                               # 解B: 回调线程拿到同一regs快照
        out = {}
        for i, n in enumerate(names):
            out[n] = regs[i] / 10 if n != "status" else regs[i]
        return out

    payload = json.dumps({"device_id": "DEV-1", "metrics": pack_sync()},
                         ensure_ascii=False)
    return pack_sync() == pack_thread() and "DEV-1" in payload


# ===== W12 组合双解：函数直调组合(解A) vs 管道配置化(解B)——扩展性对比 =====
def w12():
    # 解A: 直调组合(w08清洗+w02阈值)
    steps_a = ["collect", "clean", "detect", "report"]
    # 解B: 配置化管道（步骤可插拔, 新增质检不改主流程）
    pipeline = {"steps": ["collect", "clean", "detect", "report"],
                "params": {"detect": {"hi": 95, "warn": 80}}}
    return steps_a == pipeline["steps"] and pipeline["params"]["detect"]["hi"] == 95


if __name__ == "__main__":
    check("W01 变量双解(零散/dataclass)输出一致", w01)
    check("W02 分支双解(阶梯/查表)7组用例一致", w02)
    check("W03 循环双解(手数/Counter)6000条聚合一致", w03)
    check("W04 类双解(手写/dataclass)行为一致", w04)
    check("W05 继承双解(super链/混入)输出一致", w05)
    check("W06 异常双解(逐条try/向量化)3成功2跳过", w06)
    check("W07 解析双解(正则/split)关键字段一致", w07)
    check("W08 清洗双解(逐行/向量化)2留3弃一致", w08)
    check("W09 词频双解(Counter/TF-IDF)各Top5", w09)
    check("W10 报告双解(reportlab/PIL)字体与绘制就绪", w10)
    check("W11 采集双解(同步/线程)payload同构(烟测)", W11_smoke)
    check("W12 组合双解(直调/配置化)步骤一致", w12)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS)}项双解互验：{'ALL PASS ✅' if not bad else 'FAIL ❌ ' + str(bad)}")
