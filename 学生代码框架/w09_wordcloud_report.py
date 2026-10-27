# -*- coding: utf-8 -*-
# [教学脚手架] 下列导入/变量供 TODO 完成后使用，故标注 noqa 而非删除
"""W09 工业故障分析报告生成系统 —— jieba分词+词云"""
import os
from collections import Counter  # noqa: F401

import jieba
import jieba.analyse  # noqa: F401
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "Heiti TC"]  # 中文字体

TEXTS = [
    "1号注塑机液压油温升高报警，影响生产节拍", "3号车床主轴轴承磨损异响，班中巡检发现",
    "空压机B排气压力不足，请尽快处理", "冷却水泵2机械密封泄漏，已挂牌停机",
    "包装机A的PLC通信中断，从站掉线", "5号压铸机液压油污染度超标，滤芯堵塞",
    "辊道输送线电机电流偏高，轴承座发热", "中央冷水机组冷却水温持续偏高，填料结垢",
    "变频器过流报警，负载卡滞需检查", "行车2电缆绝缘老化，接地故障",
    "AGV充电站温度变送器读数漂移，偏差超限", "数控车床冷却系统流量不足，温差增大",
    "注塑机液压电磁阀卡滞，换向失灵", "空压机振动剧烈伴随杂音，轴承磨损",
    "包装线气动调节阀振荡，定位器故障", "压铸机液压油缸内泄，保压不住",
] * 3   # ×3扩成48条(可再合并班级语料)

STOP = set("的 了 在 是 请 尽快 处理 影响 生产 班中 巡检 发现 已 挂牌 停机 需 检查".split())
import os as _os  # noqa: E402  （置于常量定义之后，教学脚手架）
FONT = next((f"fonts/{n}" for n in ("ZH_Font.ttf", "SimHei.ttf")
            if _os.path.exists(f"fonts/{n}")), "SimHei.ttf")  # 资料包字体(含CJK)


def main():
    # TODO-1 分词+停用词过滤 → words列表
    # words = []
    # TODO-2 词频统计(Counter) + Top10柱状图(保存bar.png)
    # TODO-3 jieba.analyse.extract_tags(text, topK=20, withWeight=True) 关键词
    # TODO-4 wordcloud生成词云(保存cloud.png):
    #   from wordcloud import WordCloud
    #   wc = WordCloud(font_path=FONT, width=800, height=400,
    #                  background_color="white").generate(" ".join(words))
    #   wc.to_file("cloud.png")
    # TODO-5 (洞察)打印Top10词, 撰写≤150字故障规律分析(写入工单)
    pass


if __name__ == "__main__":
    main()
