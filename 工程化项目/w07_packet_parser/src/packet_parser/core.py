# -*- coding: utf-8 -*-
"""工业报文解析器：策略模式 + 路由表（新增格式零改动调用方）。

键值报文用正则提取（工单 W07 任务要求①）：按"键=值"配对抓取，
天然与字段顺序无关——乱序报文照样解析（B 档容错项）。
"""
import json
import re

KV_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>[^;]+)")


def parse_json(s):
    """JSON 报文 -> 读数 dict。"""
    d = json.loads(s)
    return {"id": str(d["id"]), "temp": float(d["t"]), "press": float(d["p"])}


def parse_csv(s):
    """逗号报文: D2,81.0,0.50"""
    a = [x.strip() for x in s.split(",")]
    if len(a) != 3:
        raise ValueError("CSV 字段数不为3")
    return {"id": a[0], "temp": float(a[1]), "press": float(a[2])}


def parse_kv(s):
    """键值报文: id=D3;t=95.5;p=0.66（正则提取键值，顺序无关）。"""
    out = {m.group("key"): m.group("val").strip() for m in KV_RE.finditer(s)}
    return {"id": out["id"], "temp": float(out["t"]), "press": float(out["p"])}


PARSERS = [
    ("json", lambda s: s.strip().startswith("{"), parse_json),
    ("kv", lambda s: "=" in s and ";" in s, parse_kv),
    ("csv", lambda s: s.count(",") == 2, parse_csv),
]


def parse(packet):
    """按路由表顺序尝试解析；全部失败返回 None（交调用方隔离）。"""
    for name, match, fn in PARSERS:
        try:
            if match(packet):
                d = fn(packet)
                d["format"] = name
                return d
        except (ValueError, KeyError, json.JSONDecodeError):
            continue
    return None


def failure_reason(packet):
    """隔离归因（B 档"缺字段/乱序容错"的可复核证据）：

    命中某格式路由但取值失败 → 缺字段/值错误（写明格式名）；
    没有任何路由命中 → 未知格式。只做归因，不改变 parse 的 None 语义。
    """
    for name, match, fn in PARSERS:
        try:
            if match(packet):
                fn(packet)
        except (ValueError, KeyError, IndexError, json.JSONDecodeError):
            return "%s 格式缺字段/值错误" % name
    return "未知格式"
