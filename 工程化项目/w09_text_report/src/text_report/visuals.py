# -*- coding: utf-8 -*-
"""词云 / 词频柱状图渲染（工单 W09 的"可视化"实测项）。

与 w12 同源的原则：缺库/缺字体就如实返回 (None, 原因)，绝不写"看起来像"
的空文件糊弄验收；中文字体走候选链（环境变量 > 课程包 fonts/ > 项目内
fonts/），词云禁止默认字体（工单避坑：方块字）。
"""
import os

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
#: 课程包根（工程化项目/w09_text_report → 02-程序设计基础）
COURSE = os.path.normpath(os.path.join(PROJ, "..", ".."))
_FONT_NAMES = ("ZH_Font.ttf", "NotoSansSC-Regular.otf", "simhei.ttf")


def find_font():
    """中文字体候选：环境变量 > 课程包 fonts/ > 项目内 fonts/。"""
    out = [os.environ.get("AI_COURSE_FONT")]
    for base in (os.path.join(COURSE, "fonts"), os.path.join(PROJ, "fonts")):
        for name in _FONT_NAMES:
            out.append(os.path.join(base, name))
    return next((os.path.normpath(p) for p in out
                 if p and os.path.exists(p)), None)


def wordcloud_png(words, out_dir, name="wordcloud.png"):
    """词云 PNG：真实渲染，返回 (路径|None, 说明, 字节数实测)。"""
    path = os.path.join(out_dir, name)
    try:
        from wordcloud import WordCloud
        from PIL import Image  # noqa: F401 校验 Pillow 依赖
    except ImportError as exc:
        return None, "未安装 wordcloud/Pillow: %s" % exc, 0
    if not words:
        return None, "无关键词可画（故障文本为空）", 0
    font = find_font()
    wc = WordCloud(width=800, height=400, background_color="white",
                   font_path=font, max_words=40, random_state=7)
    wc.generate_from_frequencies({str(w): int(c) for w, c in words})
    wc.to_image().save(path)
    return path, "wordcloud + Pillow 真实渲染（字体 %s）" % (
        os.path.basename(font) if font else "内置默认"), os.path.getsize(path)


def top10_chart(words, out_dir, name="top10.png"):
    """Top10 词频横向柱状图（matplotlib，工单任务要求⑤）。"""
    path = os.path.join(out_dir, name)
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
    except ImportError as exc:
        return None, "未安装 matplotlib: %s" % exc, 0
    if not words:
        return None, "无词可画", 0
    labels = [str(w) for w, _ in words][::-1]
    counts = [int(c) for _, c in words][::-1]
    font = find_font()
    if font:
        from matplotlib import font_manager
        font_manager.fontManager.addfont(font)
        fam = font_manager.FontProperties(fname=font).get_name()
        plt.rcParams["font.family"] = [fam, "DejaVu Sans"]
    fig = plt.figure(figsize=(6, 4), dpi=120)
    ax = fig.add_subplot(111)
    ax.barh(range(len(labels)), counts, color="#c0392b")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_title("Top%d 故障关键词词频" % len(labels))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path, "matplotlib 真实渲染", os.path.getsize(path)


def file_evidence(path):
    """产物实测三件套：是否存在 / 字节数（虚报"已生成"会被这里抓到）。"""
    ok = bool(path) and os.path.exists(path)
    return ok, os.path.getsize(path) if ok else 0
