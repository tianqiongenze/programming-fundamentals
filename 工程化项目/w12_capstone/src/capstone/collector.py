# -*- coding: utf-8 -*-
"""数据采集模块（工单 Z 必备项①）：≥50 条读数 + 全程日志。

三条来源，按"环境也是选型维度"排序，取第一条能跑通的：
  ① 现场 CSV（课程包 `raw_metrics.csv`，可用环境变量 AI_COURSE_DATA 指路）；
  ② Modbus 客户端（装了 pymodbus 且配了 `modbus_host` 才试，否则如实记 MISS）；
  ③ 内置种子采样器——答辩机缺文件时照样拿到 ≥min_rows 条，绝不空跑。
每条来源都写进 self.meta，报告里看得见"这批数到底从哪来"。
"""
import csv
import logging
import os
import random

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
#: 课程包根（工程化项目/w12_capstone → 02-程序设计基础）
COURSE = os.path.normpath(os.path.join(PROJ, "..", ".."))
DEFAULT_CSV = "raw_metrics.csv"


def csv_candidates(name=DEFAULT_CSV):
    """候选 CSV 路径：环境变量 > 课程包根 > 项目内 data/。"""
    return [os.path.join(os.environ.get("AI_COURSE_DATA", ""), name),
            os.path.join(COURSE, name),
            os.path.join(PROJ, "data", name)]


def find_csv(name=DEFAULT_CSV):
    for p in csv_candidates(name):
        if p and os.path.exists(p):
            return os.path.normpath(p)
    return None


class Collector:
    """采集器：把"外部世界"读成统一行结构，坏行只计数不崩流水线。"""

    def __init__(self, min_rows=50, seed=7, csv_name=DEFAULT_CSV, log=None):
        self.min_rows = int(min_rows)
        self.seed = int(seed)
        self.csv_name = str(csv_name)
        self.log = log or logging.getLogger("capstone.collector")
        self.meta = {}

    def collect(self, source=None):
        """返回 (rows, meta)；rows 为 [{'name','temp','press'}]。"""
        for reader, tag in ((self._from_file, "csv"),
                            (self._from_modbus, "modbus"),
                            (self._seeded, "seed")):
            rows = reader(source) if tag == "csv" else reader()
            if rows:
                self.meta = {"channel": tag, "rows": len(rows),
                             "dropped": self.meta.get("dropped", 0),
                             "detail": self.meta.get("detail", "")}
                self.log.info("采集完成：通道=%s %d 条（丢弃 %d 条坏行）",
                              tag, len(rows), self.meta["dropped"])
                return rows, self.meta
        raise ValueError("三种采集通道全部失败——请检查数据文件/网络")

    def _from_file(self, source=None):
        path = source or find_csv(self.csv_name)
        if not path or not os.path.exists(path):
            self.log.warning("CSV 不可用：%s", path or "(未找到)")
            return None
        rows, dropped = [], 0
        with open(path, encoding="utf-8-sig", newline="") as f:
            for rec in csv.DictReader(f):
                row = self._cast(rec)
                if row:
                    rows.append(row)
                else:
                    dropped += 1
        if len(rows) < self.min_rows:
            self.log.warning("CSV 仅 %d 条 < 工单下限 %d，改用种子补齐",
                             len(rows), self.min_rows)
            self.meta["dropped"] = dropped
            self.meta["detail"] = "csv %d 条不足，种子补齐" % len(rows)
            return rows + self._seeded_n(self.min_rows - len(rows))
        self.meta["dropped"] = dropped
        self.meta["detail"] = os.path.relpath(path, COURSE)
        self.log.info("读 CSV %s：有效 %d 条 / 坏行 %d 条", path, len(rows),
                      dropped)
        return rows

    @staticmethod
    def _cast(rec):
        """CSV 行 → 统一结构；缺列/非数值返回 None（坏行交隔离计数）。"""
        try:
            name = (rec.get("device_id") or rec.get("name")
                    or rec.get("设备") or "").strip()
            temp = float(rec.get("temp", ""))
            press = float(rec.get("press", ""))
        except (TypeError, ValueError, AttributeError):
            return None
        return {"name": name or "UNKNOWN", "temp": temp, "press": press}

    def _from_modbus(self):
        """装了 pymodbus 且配置了地址才走；否则如实 MISS（不谎称采到）。"""
        host = os.environ.get("W12_MODBUS_HOST")
        if not host:
            self.log.info("Modbus 通道跳过：未配置 W12_MODBUS_HOST")
            return None
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            self.log.warning("Modbus 通道 MISS：未安装 pymodbus")
            return None
        rows = []
        client = ModbusTcpClient(host, port=int(
            os.environ.get("W12_MODBUS_PORT", "502")), timeout=1.0)
        try:
            if not client.connect():
                raise ConnectionError("Modbus 连接失败")
            rr = client.read_input_registers(0, count=self.min_rows * 2)
            regs = list(rr.registers)
            for i in range(0, len(regs) - 1, 2):
                rows.append({"name": "MODBUS-%02d" % (i // 2),
                             "temp": regs[i] / 10.0,
                             "press": regs[i + 1] / 100.0})
        except Exception as exc:                     # noqa: BLE001 现场兜底
            self.log.warning("Modbus 通道异常，降级到种子：%s", exc)
            return None
        finally:
            client.close()
        self.meta["detail"] = "modbus://%s" % host
        return rows if len(rows) >= self.min_rows else None

    def _seeded(self):
        return self._seeded_n(self.min_rows)

    def _seeded_n(self, n):
        """确定性种子采样：同一 seed 永远同一批数（答辩可复现）。"""
        rnd = random.Random(self.seed)
        self.meta.setdefault("detail", "内置种子 seed=%d" % self.seed)
        return [{"name": "SIM-%02d" % i,
                 "temp": round(rnd.uniform(41.0, 108.0), 1),
                 "press": round(rnd.uniform(0.21, 0.88), 2)}
                for i in range(1, n + 1)]
