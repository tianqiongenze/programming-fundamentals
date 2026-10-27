# -*- coding: utf-8 -*-
"""《Python编程基础》教师参考实现（W01~W12）
用法: python solutions.py w01 | w02 | ... | w12
W09/W10/W11 需对应第三方库; W11需先启动虚拟产线两个模拟器。
"""
import json
import random
import re
import sys

# ======================================================================


def w01():
    device_id = "DEV-2026-001"
    name = "智能注塑机"
    running = True
    temp = 56.5
    press_kpa = 450.0
    rpm = 1480

    def c_to_f(c):
        return c * 9 / 5 + 32

    print("====== 设备台账卡 ======")
    print(f"编号: {device_id}")
    print(f"名称: {name:<10} 状态: {'运行' if running else '停止'}")
    print(f"温度: {temp:>6.1f}℃ ({c_to_f(temp):.1f}℉)")
    print(f"压力: {press_kpa / 1000:.2f}MPa  转速: {rpm}rpm")


def w02():
    def alarm(level, msg):
        tags = {1: "提示", 2: "警告", 3: "停机"}
        import time
        print(f"[{tags[level]}] {time.strftime('%H:%M:%S')} {msg}")

    def check(temp, press):
        if temp >= 95 or press >= 0.96:
            alarm(3, f"温度{temp}℃/压力{press}MPa超危险线, 立即停机!")
        elif temp >= 80 or press >= 0.8:
            alarm(2, f"温度{temp}℃/压力{press}MPa超预警线")
        else:
            alarm(1, "运行正常")

    for t in [79.9, 80, 94.9, 95, 100]:
        check(t, 0.5)


def w03():
    random.seed(42)
    devices = [{"id": "DEV-01", "name": "空压机A", "base": 62},
               {"id": "DEV-02", "name": "冷却泵", "base": 55},
               {"id": "DEV-03", "name": "注塑机", "base": 70}]
    stats = {d["id"]: {2: 0, 3: 0} for d in devices}

    def check_level(temp):
        return 3 if temp >= 95 else (2 if temp >= 80 else 0)

    for d in devices:
        for _ in range(10):
            t = d["base"] + random.uniform(-8, 15)
            lv = check_level(t)
            if lv:
                stats[d["id"]][lv] += 1
                print(f"[{d['id']}]{d['name']} 温度{t:.1f}℃ → "
                      f"{'警告' if lv == 2 else '停机'}")
    print("== 告警统计 ==")
    for k, v in stats.items():
        print(k, "警告", v[2], "停机", v[3])


def w04():
    class Device:
        def __init__(self, dev_id, name, temp=25.0):
            self.dev_id, self.name, self.temp = dev_id, name, temp
            self.status = "停止"

        def start(self):
            if self.status == "运行":
                print(f"{self.name} 已在运行, 请勿重复启动")
                return
            self.status = "运行"
            print(f"{self.name} 启动成功")

        def stop(self):
            self.status = "停止"
            print(f"{self.name} 已停止")

        def get_status(self):
            return f"{self.dev_id} {self.name}: {self.status} {self.temp}℃"

        def __str__(self):
            return self.get_status()

    d1, d2 = Device("DEV-01", "空压机A", 41.2), Device("DEV-02", "冷却泵")
    d1.start()
    d1.start()
    d2.start()
    d1.stop()
    print(d1)
    print(d2.get_status())


def w05():
    class Device:
        def __init__(self, dev_id, name):
            self.dev_id, self.name, self.status = dev_id, name, "停止"

        def start(self):
            self.status = "运行"
            print(f"{self.name} 已启动")

        def report(self):
            return f"{self.dev_id} {self.name}: {self.status}"

    class PLC(Device):
        def __init__(self, dev_id, name, scan_ms=10):
            super().__init__(dev_id, name)
            self.scan_ms = scan_ms

        def start(self):                      # 覆盖
            super().start()
            print(f"  扫描周期: {self.scan_ms}ms")

    class VFD(Device):
        def set_freq(self, f):
            if 0 <= f <= 50:
                self.freq = f
                print(f"{self.name} 频率设定 {f}Hz")
            else:
                print("频率超范围(0-50Hz)")

    devices = [PLC("DEV-01", "S7-1200", 8), VFD("DEV-02", "ABB变频器"),
               Device("DEV-03", "温度变送器")]
    for d in devices:                         # 多态: 统一调用不同行为
        d.start()
        print(d.report())
    devices[1].set_freq(35)


def w06():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler("w06.log", encoding="utf-8")])
    log = logging.getLogger("collector")

    raw = "temp,press\n56.2,0.45\nerr,0.46\n57.5,\n61.0,0.47\n58.3,0.44\n"
    ok = skip = 0
    for i, line in enumerate(raw.splitlines()):
        if line.startswith("temp"):
            continue
        try:
            t, p = line.split(",")
            float(t), float(p)
            log.info("第%d条采集成功: %s", i, line)
            ok += 1
        except ValueError:
            log.warning("脏数据跳过: %r", line)
            skip += 1
        finally:
            pass
    print(f"采集统计: 成功{ok} 跳过{skip}")


def w07():
    msg = "DEV-01:temp=56.3C;press=0.45MPa;status=RUN"
    m = re.match(r"([A-Z]+-\d+):", msg)
    dev = m.group(1) if m else None
    metrics = {}
    for k, v in re.findall(r"(\w+)=([\d.]+|[A-Z]+)", msg):
        metrics[k] = float(v) if re.fullmatch(r"[\d.]+", v) else v
    print({"device_id": dev, "metrics": metrics})

    csv_line = "DEV-02,55.1,0.44,RUN"
    d, t, p, s = csv_line.split(",")
    print({"device_id": d,
           "metrics": {"temp": float(t), "press": float(p), "status": s}})

    j = json.loads('{"device_id":"DEV-03","temp":54.8,"press":0.46}')
    print({"device_id": j.pop("device_id"), "metrics": j})


def w08():
    import csv
    import os
    random.seed(7)
    raw = "raw_demo.csv"
    if not os.path.exists(raw):
        with open(raw, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["device_id", "temp", "press", "status"])
            for i in range(60):
                t = round(random.uniform(40, 90), 1)
                if i % 17 == 3:
                    t = ""
                if i % 23 == 5:
                    t = "err"
                if i % 29 == 7:
                    t = 135.0
                w.writerow([f"DEV-{i % 3 + 1:02d}", t,
                            round(random.uniform(.3, .6), 2), "RUN"])

    def validate(row):
        t = row["temp"]
        if t in ("", None):
            return "缺失"
        try:
            t = float(t)
        except ValueError:
            return "类型"
        if not 0 <= t <= 120:
            return "范围"
        return None

    ok, bad, counter = 0, [], {"缺失": 0, "类型": 0, "范围": 0}
    with open(raw, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            err = validate(row)
            if err is None:
                ok += 1
            else:
                bad.append((row, err))
                counter[err] += 1
    with open("bad_records.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["device_id", "temp", "err"])
        for row, e in bad:
            w.writerow([row["device_id"], row["temp"], e])
    print(f"清洗报告: 总60 成功{ok} 问题{len(bad)} {counter}")


def w09():
    import jieba
    import jieba.analyse
    from collections import Counter
    texts = ["1号注塑机液压油温升高报警", "3号车床主轴轴承磨损异响",
             "空压机排气压力不足", "PLC通信中断从站掉线",
             "冷却水温持续偏高填料结垢", "变频器过流报警负载卡滞"] * 3
    stop = set("的 了 在 是 请 尽快 影响 报警 需".split())
    words = [w for t in texts for w in jieba.cut(t)
             if w not in stop and len(w) > 1]
    print("Top10:", Counter(words).most_common(10))
    print("关键词:", jieba.analyse.extract_tags(" ".join(texts), topK=8))
    # 词云部分同starter注释(需wordcloud+字体)


def w10():
    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Image as RLImage, Paragraph,
                                    SimpleDocTemplate, Table, TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet

    pdfmetrics.registerFont(TTFont("SimHei", "fonts/ZH_Font.ttf"))
    img = Image.new("RGB", (400, 300), (200, 200, 200))
    d = ImageDraw.Draw(img)
    d.rectangle([120, 80, 210, 120], outline=(255, 0, 0), width=3)
    d.text((120, 66), "scratch 9.0mm", fill=(255, 0, 0))
    d.rectangle([220, 150, 265, 195], outline=(255, 0, 0), width=3)
    d.text((220, 136), "pit 4.5mm2", fill=(255, 0, 0))
    img.save("marked.png")

    st = getSampleStyleSheet()
    st["Title"].fontName = st["Normal"].fontName = "SimHei"
    tbl = Table([["缺陷", "尺寸", "判定"], ["划痕", "9.0mm", "超差"],
                 ["凹坑", "4.5mm²", "合格"]])
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black"),
                             ("FONTNAME", (0, 0), (-1, -1), "SimHei")]))
    SimpleDocTemplate("质量日报.pdf", pagesize=A4).build([
        Paragraph("设备质量日报", st["Title"]), Paragraph(
            "结论: 发现划痕1处超差, 建议复检。", st["Normal"]),
        RLImage("marked.png", width=120 * mm, height=90 * mm), tbl])
    print("已生成 质量日报.pdf")


def _ensure_local_sims():
    """教师参考一键可跑: 自动拉起本地Modbus(5020)与MQTT(1883)模拟服务, 进程随本脚本退出"""
    import subprocess
    import sys
    import os
    import atexit
    import time as _t
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sims = [(os.path.join(base, "虚拟产线", "mini_modbus_server.py"), ["5020", "1"]),
            (os.path.join(base, "虚拟产线", "mini_mqtt_broker.py"), [])]
    procs = []
    for script, args in sims:
        if os.path.exists(script):
            p_ = subprocess.Popen([sys.executable, script] + args,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            procs.append(p_)
            atexit.register(p_.terminate)
    _t.sleep(1.5)
    return procs


def w11():
    import time
    import json
    from pymodbus.client import ModbusTcpClient as Client
    import paho.mqtt.client as mqtt

    _ensure_local_sims()
    c = Client(host="127.0.0.1", port=5020)
    c.connect()
    mq = mqtt.Client()
    mq.connect("127.0.0.1", 1883)
    mq.loop_start()
    names = ["temp_c", "press_mpa", "vib_mm_s", "rpm", "status"]
    for i in range(5):
        rr = c.read_holding_registers(address=0, count=5)
        vals = rr.registers
        data = {n: (v / 10 if n != "status" else v)
                for n, v in zip(names, vals)}
        payload = json.dumps({"device_id": "DEV-1",
                              "ts": time.strftime("%H:%M:%S"),
                              "metrics": data}, ensure_ascii=False)
        mq.publish("device/1/status", payload)
        print("上报:", payload)
        time.sleep(2)
    mq.loop_stop()
    c.close()


def w12():
    """综合项目: 直接组合w08清洗+w02阈值+w10报告"""
    print("=== 综合系统演示 ===")
    w08()          # 采集(模拟)+清洗
    w02()          # 异常检测(阈值)
    print("报告生成复用 w10() ...")


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "w01"
    {"w01": w01, "w02": w02, "w03": w03, "w04": w04, "w05": w05,
     "w06": w06, "w07": w07, "w08": w08, "w09": w09, "w10": w10,
     "w11": w11, "w12": w12}[task]()
