# -*- coding: utf-8 -*-
"""PEP 8 规范率实测器（每张工单每一档都要求"规范率≥N%"，本模块使其可测量）。

设计要点（对应工单 B06 PEP 8 启蒙"规范率可量化"）：
  1. 引擎优先级：pycodestyle（业界标准）→ 内置兜底检查器（零依赖）。
     课堂环境可能没装 linter，所以降级路径必须真实可用——"环境也是选型维度"。
  2. 参数来自 pyproject.toml 的 [tool.pycodestyle] / [tool.stylecheck]，
     做到"改配置不改代码"（与 config/rules.yaml 同一原则）。
  3. 规范率定义（公式写进报告，便于复核）：
         规范率 = (1 - 违规条数 / 有效行数) × 100%
     "有效行数"= 参与统计文件中的非空行数；空行不构成代码规范问题。
  4. 纯计算、零副作用：只读文件、不写文件，可被 run.py 与 pytest 同时调用。

对应 GB/T 8566 质量保证过程 + GB/T 15532 测试规范：静态检查属"非运行时测试"。
"""
import os
import re

DEFAULT_MAX_LINE_LENGTH = 100
DEFAULT_IGNORE = ("E121", "E123", "E126", "E226", "E24", "E704", "W503", "W504")
DEFAULT_SCOPE = ("run.py", "cli.py", "src", "tests")

# ── 内置兜底规则：pycodestyle 高频项子集（无第三方依赖时独立运行）──
_BUILTIN = [
    ("W291", re.compile(r"[ \t]+$"), "trailing whitespace"),
    ("E703", re.compile(r";\s*(?:#.*)?$"), "statement ends with a semicolon"),
    ("E722", re.compile(r"^\s*except\s*:"), "bare except"),
    ("E711", re.compile(r"(==|!=)\s*None\b"), "comparison to None"),
    ("E712", re.compile(r"(==|!=)\s*(True|False)\b"), "comparison to True/False"),
    ("E231", re.compile(r",(?=\S)"), "missing whitespace after ','"),
    ("W191", re.compile(r"^\t"), "indentation contains tabs"),
]


def _read_toml(path):
    """优先用标准库 tomllib（3.11+）；缺失时返回 None 走手写解析。"""
    try:
        import tomllib
    except ImportError:
        return None
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def _toml_section_fallback(path, name):
    """无 tomllib 时的简单解析：只取 [tool.name] 下的 key = value 行。"""
    out = {}
    if not os.path.exists(path):
        return out
    inside = False
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("["):
                inside = (line == "[tool.%s]" % name)
                continue
            if inside and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    return out


def _as_list(v):
    """把 '["a", "b"]' 或真 list 归一化为 list[str]。"""
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [x.strip().strip('"').strip("'")
            for x in str(v).strip("[]").split(",") if x.strip()]


def load_options(root):
    """配置优先级：[tool.pycodestyle] > [tool.flake8] > [tool.stylecheck] > 默认。"""
    py = os.path.join(root, "pyproject.toml")
    pc, sc = {}, {}
    data = _read_toml(py)
    if data is not None:
        tool = data.get("tool", {})
        pc = dict(tool.get("flake8", {}) or {})
        pc.update(tool.get("pycodestyle", {}) or {})
        sc = tool.get("stylecheck", {}) or {}
    else:
        pc = dict(_toml_section_fallback(py, "flake8"))
        pc.update(_toml_section_fallback(py, "pycodestyle"))
        sc = _toml_section_fallback(py, "stylecheck")
    mll = pc.get("max_line_length", pc.get("max-line-length"))
    return {
        "max_line_length": int(mll) if mll else DEFAULT_MAX_LINE_LENGTH,
        "ignore": _as_list(pc.get("ignore", list(DEFAULT_IGNORE))),
        "scope": _as_list(sc.get("scope", sc.get("paths", list(DEFAULT_SCOPE)))),
    }


def iter_files(root, scope):
    """按 scope 收集待检 .py 文件（跳过缓存/虚拟环境/输出目录）。"""
    skip_dirs = {"__pycache__", ".pytest_cache", ".git", "output", "docs",
                 "build", "dist", ".venv", "venv", ".idea", "node_modules"}
    found = []
    for item in scope:
        p = os.path.join(root, item)
        if os.path.isfile(p):
            found.append(p)
        elif os.path.isdir(p):
            for dirpath, dirnames, names in os.walk(p):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                for n in sorted(names):
                    if n.endswith(".py"):
                        found.append(os.path.join(dirpath, n))
    out, seen = [], set()
    for f in found:
        key = os.path.abspath(f)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def count_lines(path):
    """有效行数：非空行（注释行计入——注释同样受 E501 约束）。"""
    with open(path, encoding="utf-8", errors="replace") as f:
        return sum(1 for line in f if line.strip())


# ── 引擎 1：pycodestyle（业界标准）────────────────────────────────
def pycodestyle_engine():
    """可用性探测：装了就用业界标准，没装就走内置兜底（返回 None）。"""
    try:
        import pycodestyle
    except ImportError:
        return None
    return pycodestyle


def _scan_pycodestyle(files, opt):
    """静默采集 (file, line, code, message)：不向 stdout 打印任何内容。"""
    pc = pycodestyle_engine()

    class Collector(pc.StandardReport):
        def __init__(self, options):
            super().__init__(options)
            self.hits = []

        def error(self, line_number, offset, text, check):
            code = super().error(line_number, offset, text, check)
            if code:
                self.hits.append((self.filename, line_number, code, text[5:]))
            return code

        def get_file_results(self):
            self._deferred_print = []      # 静默：命中已收集，不落 stdout
            return self.file_errors

    sg = pc.StyleGuide(quiet=True, max_line_length=opt["max_line_length"],
                       ignore=list(opt["ignore"]))
    init = getattr(sg, "init_report", None) or sg.init_reporter
    rep = init(Collector)
    for f in files:
        try:
            sg.check_files([f])
        except Exception:                  # 单文件解析失败不拖垮整体体检
            rep.hits.append((f, 0, "E999", "checker failed"))
    return rep.hits, "pycodestyle %s（业界标准）" % getattr(pc, "__version__", "?")


# ── 引擎 2：内置兜底检查器（零依赖）───────────────────────────────
_STR = re.compile(r"'''[\s\S]*?'''|"
                  r'"""[\s\S]*?"""|'
                  r"'(?:\\.|[^'\n])*'|"
                  r'"(?:\\.|[^"\n])*"|'
                  r"#.*")


def _strip_strings(line):
    """去掉字符串字面量与行尾注释——避免 E231/E712 这类规则在文本内误报。"""
    return _STR.sub("", line)


def _scan_builtin(files, opt):
    hits = []
    mll = int(opt["max_line_length"])
    ignore = set(opt["ignore"])
    rules = list(_BUILTIN)
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            hits.append((path, 0, "E902", "unreadable file"))
            continue
        blanks = 0
        for no, line in enumerate(lines, 1):
            if not line.strip():
                blanks += 1
                if blanks > 2:
                    hits.append((path, no, "E303", "too many blank lines"))
                continue
            blanks = 0
            if len(line) > mll:
                hits.append((path, no, "E501", "line too long (%d > %d)"
                             % (len(line), mll)))
            if not line[:1].isspace() and line.lstrip().startswith(("def ", "class ")):
                j = no - 2                       # 上一行（0 基下标）
                while j >= 0 and lines[j].lstrip().startswith(("#", "@")):
                    j -= 1                       # 注释/装饰器与 def 同属一块
                gap = 0
                while j >= 0 and not lines[j].strip():
                    gap += 1
                    j -= 1
                if j >= 0 and gap < 2:
                    hits.append((path, no, "E302", "expected 2 blank lines"))
            if "noqa" in line:
                continue
            probe = _strip_strings(line)
            for code, rex, msg in rules:
                if code in ignore:
                    continue
                # W291 看原始行；其余规则看去字符串/注释后的行
                if rex.search(line if code == "W291" else probe):
                    hits.append((path, no, code, msg))
    return hits, "内置兜底 PEP8 子集（未安装 pycodestyle）"


def scan_project(root):
    """体检入口：返回规范率实测结果（供报告、控制台与 pytest 断言使用）。"""
    opt = load_options(root)
    files = iter_files(root, opt["scope"])
    if not files:
        raise FileNotFoundError("规范体检未找到任何 .py 文件：%s" % root)
    if pycodestyle_engine() is not None:
        hits, engine_desc = _scan_pycodestyle(files, opt)
        kind = "pycodestyle"
    else:
        hits, engine_desc = _scan_builtin(files, opt)
        kind = "builtin"
    lines = sum(count_lines(f) for f in files)
    total = len(hits)
    bad_lines = len({"%s:%s" % (h[0], h[1]) for h in hits})
    rate = round((1.0 - total / float(lines)) * 100, 1) if lines else 0.0
    by_code = {}
    for h in hits:
        by_code[h[2]] = by_code.get(h[2], 0) + 1
    return {"engine": engine_desc, "engine_kind": kind,
            "files": len(files), "lines": lines, "violations": total,
            "violation_lines": bad_lines, "rate": rate,
            "max_line_length": opt["max_line_length"],
            "ignore": list(opt["ignore"]), "scope": opt["scope"],
            "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
            "top": [(os.path.relpath(h[0], root), h[1], h[2], h[3])
                    for h in sorted(hits, key=lambda x: (x[2], x[0], x[1]))[:10]]}


def format_section(stats, threshold):
    """把体检结果渲染成报告段落（工单"规范率≥N%"的实测证据）。"""
    verdict = "达标" if stats["rate"] >= threshold else "未达标"
    n_v, n_l = stats["violations"], stats["violation_lines"]
    dist = "（零违规）"
    if stats["by_code"]:
        head = list(stats["by_code"].items())[:6]
        dist = "｜分布: " + ", ".join("%s×%d" % (code, cnt) for code, cnt in head)
    out = [
        "体检引擎: %s" % stats["engine"],
        "统计范围: %s（%d 个文件 / %d 有效行）"
        % (", ".join(stats["scope"]), stats["files"], stats["lines"]),
        "公式: 规范率 = (1 - 违规条数 / 有效行数) × 100%",
        "违规条数: %d（涉及 %d 行）%s" % (n_v, n_l, dist),
        "规范率实测: %.1f%%｜工单门槛: ≥%.0f%% → %s"
        % (stats["rate"], threshold, verdict),
    ]
    if stats["top"]:
        out.append("待修条目（前 %d 条，file:line 可定位）:" % len(stats["top"]))
        out.extend("  %s:%d %s %s" % t for t in stats["top"])
    return out


def project_root(file_here):
    """由 src/<pkg>/xxx.py 反推项目根目录（三层 dirname）。"""
    here = os.path.abspath(file_here)
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def augment(sections, result, root, threshold):
    """把体检并入报告段与 result.json——run.py / cli.py / pytest 共用同一实测值。"""
    stats = scan_project(root)
    result["style_engine"] = stats["engine"]
    result["style_engine_kind"] = stats["engine_kind"]
    result["style_checked_files"] = stats["files"]
    result["style_checked_lines"] = stats["lines"]
    result["style_violations"] = stats["violations"]
    result["style_rate"] = stats["rate"]
    result["style_threshold"] = float(threshold)
    result["style_meets"] = bool(stats["rate"] >= float(threshold))
    sections.append(("编码规范率（PEP 8 实测）", format_section(stats, threshold)))
    return stats
