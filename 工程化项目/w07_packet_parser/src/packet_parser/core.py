# -*- coding: utf-8 -*-
"""工业报文解析器：策略模式 + 路由表（新增格式零改动调用方）。"""
import json


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
    """键值报文: id=D3;t=95.5;p=0.66"""
    out = {}
    for kv in s.split(";"):
        k, _, v = kv.partition("=")
        out[k.strip()] = v.strip()
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
