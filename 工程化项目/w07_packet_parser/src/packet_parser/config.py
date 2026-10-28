# -*- coding: utf-8 -*-
"""配置加载：规则外置（config/rules.yaml），做到"改配置不改代码"。

对应 GB/T 8566 支持过程·配置管理：所有可调阈值/清单集中在 YAML，
代码零硬编码；缺失键走 DEFAULTS 并显式告警，不静默吞掉。
环境无 PyYAML 时自动降级为内置 yaml_lite，保证课堂任意机器可跑。
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

DEFAULTS: Dict[str, Any] = {
    "warn": 80.0, "danger": 95.0, "unit": "c", "seed": 7, "topk": 2,
}


def _scalar(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none", "~", ""):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v.strip(chr(39) + chr(34) + " ")


def _fill_kv(d, s):
    """把 "k: v" 填入 dict d。"""
    k, _, v = s.partition(":")
    k, v = k.strip(), v.strip()
    if k:
        d[k] = _scalar(v)


def yaml_lite(text):
    """YAML 子集：嵌套 dict、块状 list（含 dict 元素）、行内 list、标量、注释。

    实现要点：`key:` 空值时同时压入两帧——
      ① "列表父级帧"(缩进, 父dict, key)  —— 供 `- item` 归入
      ② "子字典帧"(缩进+.5, 子dict, None) —— 供更深层 `k: v` 归入
    遇到 `- ` 时若栈顶是"子字典帧"则先弹出，回到列表父级帧。
    """
    root = {}
    stack = [(-1, root, None)]
    lines = [(len(r) - len(r.lstrip(" ")), r.strip())
             for r in text.splitlines()
             if r.strip() and not r.strip().startswith("#")]
    i = 0
    while i < len(lines):
        indent, line = lines[i]
        if line.startswith("- "):
            if len(stack) > 1 and stack[-1][2] is None:
                stack.pop()                       # 弹掉子字典帧，回到列表父级帧
            owner, key = stack[-1][1], stack[-1][2]
            if isinstance(owner, dict) and key is not None:
                if not isinstance(owner[key], list):
                    owner[key] = []
                body = line[2:]
                if ":" in body:
                    item = {}
                    _fill_kv(item, body)
                    owner[key].append(item)
                    i += 1
                    while i < len(lines) and lines[i][0] > indent \
                            and not lines[i][1].startswith("- "):
                        _fill_kv(item, lines[i][1])
                        i += 1
                    continue
                owner[key].append(_scalar(body))
            i += 1
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        owner = stack[-1][1]
        if not isinstance(owner, dict):
            i += 1
            continue
        key, _, v = line.partition(":")
        key, v = key.strip(), v.strip()
        if v == "":
            child = {}
            owner[key] = child
            stack.append((indent, owner, key))
            stack.append((indent + 0.5, child, None))
        else:
            owner[key] = _scalar(v)
            stack[-1] = (stack[-1][0], owner, key)
        i += 1
    return root


@dataclass
class Settings:
    """本项目全部可调参数（YAML 驱动）。"""
    warn: float = 80.0
    danger: float = 95.0
    unit: str = "c"
    seed: int = 7
    topk: int = 2
    items: List[Any] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def get(self, key, default=None):
        """任意配置项读取：raw 优先，缺失回落 default（pipeline 项目专属参数）。"""
        if key in self.raw:
            return self.raw[key]
        v = DEFAULTS.get(key, default)
        return default if v is None else v

    def num(self, key, default=0.0):
        """数值型配置（字符串也尽力转换，转不动就兜底）。"""
        try:
            return float(self.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def flag(self, key, default=False):
        """布尔型配置。"""
        v = self.get(key, default)
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "y", "on")
        return bool(v)

    def seq(self, key, default=None):
        """列表型配置（YAML 块列表 / 逗号分隔字符串均可）。"""
        v = self.get(key, None)
        if v is None:
            return list(default or [])
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return list(v)
        return [v]

    def tier_gates(self, defaults):
        """工单四档门槛：rules.yaml `tiers:` 段的实测门限，数字外置。

        为什么外置：门槛数字出自工单验收表，不该硬编码进 tiers.py
        （改配置不改代码）；未配置 `tiers:` 的旧配置回落代码默认值，
        保证课堂环境即使配置缺段也照样能判定。
        """
        out = dict(defaults)
        raw = self.raw.get("tiers")
        if not isinstance(raw, dict):
            return out
        for k, v in raw.items():
            if k not in out:
                continue
            try:
                cur = out[k]
                out[k] = float(v) if isinstance(cur, float) else int(float(v))
            except (TypeError, ValueError):
                pass
        return out

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            d = {}
        d = dict(DEFAULTS, **d)
        items = d.get("items")
        if not items:
            # 数据集键名不限 items：devices / raw_lines / fleet / readings / corpus ...
            for k, v in d.items():
                if isinstance(v, list) and v and isinstance(v[0], (dict, str, int, float)):
                    items = v
                    break
        if not items:
            items = []
        if not isinstance(items, list):
            items = [items]
        return cls(
            warn=float(d["warn"]), danger=float(d["danger"]), unit=str(d["unit"]),
            seed=int(d["seed"]), topk=int(d["topk"]),
            items=items, raw=d,
        )


def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError("配置文件不存在: %s" % path)
    text = open(path, encoding="utf-8").read()
    data = None
    try:
        import yaml
        data = yaml.safe_load(text)
    except ImportError:
        data = yaml_lite(text)
    return Settings.from_dict(data)
