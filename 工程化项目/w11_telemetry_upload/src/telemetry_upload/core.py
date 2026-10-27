# -*- coding: utf-8 -*-
"""采数、切批、重试与断网降级（传输层可注入，便于离线测试）。"""
import json
import os
import time


def read_all(devices, seed=0):
    """按种子固定生成一轮寄存器读数（虚拟设备）。"""
    import random
    r = random.Random(seed)
    return [{"code": str(d["code"]),
             "temp": round(r.uniform(float(d["temp"]) - 2, float(d["temp"]) + 2), 2),
             "press": round(r.uniform(float(d["press"]) - 0.02, float(d["press"]) + 0.02), 3)}
            for d in devices]


def batches(items, size):
    """按 size 切批；size<=0 视为不合批（整批）。"""
    size = int(size)
    if size <= 0:
        return [list(items)]
    return [items[i:i + size] for i in range(0, len(items), size)]


def send_with_retry(transport, batch, max_retry=2, backoff=0.0):
    """指数退避重试；成功 True，失败 False（由调用方入 pending）。"""
    for attempt in range(max_retry + 1):
        try:
            if transport(batch):
                return True
        except Exception:
            pass
        if attempt < max_retry and backoff:
            time.sleep(backoff * (2 ** attempt))
    return False


def flush_pending(path, pending):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)
    return path
