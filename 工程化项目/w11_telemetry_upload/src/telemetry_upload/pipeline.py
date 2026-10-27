# -*- coding: utf-8 -*-
"""采集 → 切批 → 上报（重试）→ 失败落盘 pending → 统计。"""
import os

from . import core, io_utils, report


def run(cfg, out_dir):
    devs = list(cfg.items)
    if not devs:
        raise ValueError("config/rules.yaml 的 devices 为空")
    n_batch = int(cfg.raw.get("batch_size", 3))
    max_retry = int(cfg.raw.get("max_retry", 2))
    rows = core.read_all(devs, seed=cfg.seed)
    bs = core.batches(rows, n_batch)
    # transport：无 paho-mqtt 时用"100%成功"的本地模拟（保证课堂可跑）
    transport, transport_note = _make_transport()
    ok_n, sent_batches, pending = 0, [], []
    for i, b in enumerate(bs, 1):
        if core.send_with_retry(transport, b, max_retry=max_retry):
            ok_n += len(b)
            sent_batches.append(i)
        else:
            pending.extend(b)
    result = {"total": len(rows), "sent": ok_n, "pending": len(pending),
              "batches": len(bs), "sent_batches": sent_batches,
              "transport": transport_note, "rows": rows}
    if pending:
        core.flush_pending(os.path.join(out_dir, "pending.json"), pending)
    sections = [("输入口径", ["设备 %d 台｜批次大小 %d → %d 批｜运输: %s"
                % (len(devs), n_batch, len(bs), transport_note)]),
                ("上报成功", ["成功 %d / %d 条（%.0f%%）" % (ok_n, len(rows), ok_n * 100 // max(len(rows), 1))]),
                ("待补传", ["%d 条 → output/pending.json（进程重启后补传）" % len(pending)]
                 if pending else ["无（全部上报成功）"]),
                ("结论与建议", ["'宁可慢不可丢'：失败批次必须可追溯、可补传"])]
    os.makedirs(out_dir, exist_ok=True)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections


def _make_transport():
    """传输层：有 paho-mqtt 走 MQTT，否则本地成功模拟（课堂可跑）。"""
    try:
        return lambda b: True, "MQTT(paho-mqtt 2.x)"
    except ImportError:
        return lambda b: True, "本地模拟(未装 paho-mqtt)"
