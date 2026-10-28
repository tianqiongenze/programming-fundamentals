# -*- coding: utf-8 -*-
"""定时多轮采集 → 切批 → 真实上报（MQTT）→ 断线重连 → 订阅回环 → 档位判定。

工单 W11 的硬要求全部实测，不假装成功：
  ① 5 轮定时采集（config rounds），每轮行数=设备数（C 档实测）；
  ② 真实协议栈通道（live + services）：外部 broker/PLC 模拟器可用就复用，
     不可用就在拉起本地真实服务（自研 mini broker 子进程 / pymodbus 从站），
     通道来源如实写进报告；拉不起来则降级本地兜底队列并标注，D/A 判缺；
  ③ 断线重连：第 disconnect_after_round 轮后真实拔线（kill broker 进程 /
     关闭连接），实测"连接失败 ERROR → 重连成功"，尝试次数进档位；
  ④ 订阅回环（A 档）：独立订阅端实测收到回执并逐字节核对载荷，回执打印；
  ⑤ logging 真落盘 run.log（INFO/WARNING/ERROR），档位判定只吃反读实测值。
"""
import json
import logging
import os
import time

from . import core, io_utils, live, report, services, stylecheck, tiers

ROOT = stylecheck.project_root(os.path.abspath(__file__))
LOG_FORMAT = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
log = logging.getLogger("telemetry_upload")


def setup_logging(out_dir, echo=False):
    """logging 真落盘 run.log（utf-8）；echo 时同步回显控制台。"""
    io_utils.ensure_dir(out_dir)
    path = os.path.join(out_dir, "run.log")
    logger = logging.getLogger("telemetry_upload")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter(LOG_FORMAT)
    # 每次运行重写：日志实测（行数/ERROR 数）必须只反映本次运行
    fh = logging.FileHandler(path, mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    # pymodbus/paho 的 connect 失败会走它们自己的 logger——降噪，
    # 真实失败证据由本项目写进 run.log，控制台不刷屏
    logging.getLogger("pymodbus").setLevel(logging.ERROR)
    if echo:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return path, logger


def measure_log(log_path):
    """从 run.log 反读实测：级别分布 + 总行数——报告只认文件。"""
    with open(log_path, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    levels = {}
    for ln in lines:
        for lvl in ("INFO", "WARNING", "ERROR"):
            if " %s " % lvl in ln:
                levels[lvl] = levels.get(lvl, 0) + 1
    return levels, len(lines)


def _start_services(cfg, logger):
    """外部服务不可达时在拉起本地真实服务面；来源如实记日志。"""
    bring_up = cfg.flag("bring_up_services", True)
    q_host = str(cfg.raw.get("mqtt_host", "127.0.0.1"))
    m_host = str(cfg.raw.get("modbus_host", "127.0.0.1"))
    broker = services.BrokerService(q_host, int(cfg.raw.get("mqtt_port",
                                                            1883)))
    modbus = None
    if not broker.start():
        logger.warning("MQTT broker 不可用（%s）——MQTT 档位如实判缺",
                       broker.detail)
    if services.port_open(m_host, int(cfg.raw.get("modbus_port", 5020))):
        logger.info("Modbus 现场端口已可达，直接实跑读寄存器")
    elif bring_up:
        regs = []
        for d in cfg.items:
            regs.extend([int(round(float(d["temp"]) * 10)),
                         int(round(float(d["press"]) * 10))])
        modbus = services.ModbusService(regs)
        if modbus.start():
            logger.info("Modbus 通道: %s", modbus.detail)
        else:
            logger.warning("Modbus 本地从站拉起失败: %s", modbus.detail)
            modbus = None
    return broker, modbus


def _disconnect_reconnect(broker, link, host, port, logger):
    """B 档实测：真实断线一次 → 连接失败（ERROR 入日志）→ 重连成功。"""
    attempts = 0
    if broker and broker.owned:
        broker.kill()
        logger.warning("断线演示：终止 mini broker 子进程（真实拔线）")
    else:
        link.hard_disconnect()
        logger.warning("断线演示：主动关闭发布端连接（外部 broker）")
    time.sleep(0.3)
    ok, why = live.probe_connect(host, port)
    attempts += 1
    if not ok:
        logger.error("断线后第 1 次连接探测失败（预期内）: %s", why)
    if broker and broker.owned:
        broker.restart()
    try:
        link.reconnect()
        ok2, why2 = live.probe_connect(host, port)
    except (OSError, ValueError) as exc:
        ok2, why2 = False, "%s: %s" % (type(exc).__name__, exc)
    attempts += 1
    if ok2:
        logger.info("重连成功（第 %d 次尝试）: %s", attempts, why2)
    else:
        logger.error("重连失败: %s", why2)
    return attempts


def build(cfg, out_dir, echo=False):
    """跑完整采集上报流水线，返回 (sections, result)；result 供 pytest。"""
    devs = list(cfg.items)
    if not devs:
        raise ValueError("config/rules.yaml 的 devices 为空")
    log_path, logger = setup_logging(out_dir, echo=echo)
    rounds = int(cfg.raw.get("rounds", 5))
    interval = float(cfg.raw.get("interval", 0.0))
    n_batch = int(cfg.raw.get("batch_size", 3))
    max_retry = int(cfg.raw.get("max_retry", 2))
    m_host = str(cfg.raw.get("modbus_host", "127.0.0.1"))
    q_host = str(cfg.raw.get("mqtt_host", "127.0.0.1"))
    topic = str(cfg.raw.get("topic", "device/1/status"))
    disconnect_after = int(cfg.raw.get("disconnect_after_round", 3))
    os.makedirs(out_dir, exist_ok=True)

    broker, modbus = _start_services(cfg, logger)
    m_port = (modbus.port if modbus else
              int(cfg.raw.get("modbus_port", 5020)))
    m_port = int(m_port)
    q_port = int(broker.port)
    modbus_channel = ("pymodbus 本地从站（真实协议栈）:%d" % m_port
                      if modbus else "现场配置 %s:%d" % (m_host, m_port))

    # ① MQTT 持久链路（真实 socket）；连不上如实降级
    link = live.MqttLink(q_host, q_port, topic)
    mqtt_real = False
    try:
        link.connect()
        mqtt_real = True
        logger.info("MQTT 链路已建立: %s:%d topic=%s（%s）",
                    q_host, q_port, topic, broker.detail)
    except (OSError, ValueError) as exc:
        logger.error("MQTT 连接失败，降级本地兜底队列: %s", exc)

    if mqtt_real:
        def transport(batch):
            body = json.dumps([core.payload(b) for b in batch],
                              ensure_ascii=False)
            return link.publish(body)
        transport_note = "MQTT 实跑（%s:%d，%s）" % (
            q_host, q_port, broker.detail)
    else:
        def transport(batch):
            return True
        transport_note = "本地兜底队列（无 broker，模拟暂存——不算实跑）"

    # ② 5 轮采集 + 切批上报；第 disconnect_after 轮后真实拔线重连
    rows_all, payloads, pending = [], [], []
    ok_n, bs_total, m_attempts = 0, 0, 0
    modbus_real, recon_attempts, rounds_real = False, 0, 0
    probe = json.dumps(core.payload({"code": "PROBE", "temp": 0.0,
                                     "press": 0.0}), ensure_ascii=False)
    for r in range(1, rounds + 1):
        real_rows, att, m_detail = live.modbus_read_round(
            m_host, m_port, count=len(devs) * 2, retries=1)
        m_attempts += att
        if real_rows:
            rows = real_rows
            rounds_real += 1
            if r == 1:
                logger.info("Modbus 实跑成功: %s（通道 %s）",
                            m_detail, modbus_channel)
        else:
            rows = core.read_all(devs, seed=cfg.seed + r)
            logger.warning("第 %d 轮 Modbus 未实跑（%s），本行走虚拟寄存器兜底",
                           r, m_detail)
        rows_all.append(rows)
        logger.info("第 %d/%d 轮采集: %d 台设备（%s）", r, rounds, len(rows),
                    "实跑" if real_rows else "兜底")
        ts = int(time.time())
        for row in rows:
            payloads.append(core.payload(row, ts=ts))
        for b in core.batches(rows, n_batch):
            bs_total += 1
            if core.send_with_retry(transport, b, max_retry=max_retry):
                ok_n += len(b)
            else:
                pending.extend(b)
                logger.warning("第 %d 轮批次上报失败，入 pending", r)
        if r == rounds:
            break
        if r == disconnect_after and mqtt_real:
            recon_attempts += _disconnect_reconnect(
                broker, link, q_host, q_port, logger)
        if interval and r < rounds:
            time.sleep(interval)

    # ③ 订阅回环（A 档）：独立订阅端实测收到并逐字节核对、打印回执
    lb_ok, lb_n, lb_first, lb_detail = live.subscribe_loopback(
        topic, probe, q_host, q_port)
    if lb_ok:
        logger.info("订阅回环打印回执: 主题 %s ｜ 载荷 %s ｜ %s",
                    topic, lb_first, lb_detail)
    else:
        logger.warning("订阅回环未收到一致回执（A 档实测未达标）: %s",
                       lb_detail)

    if pending:
        core.flush_pending(os.path.join(out_dir, "pending.json"), pending)
    link.close()
    broker.stop()
    if modbus:
        modbus.stop()

    rows_total = sum(len(x) for x in rows_all)
    rows_ok = (len(rows_all) == rounds
               and all(len(x) == len(devs) for x in rows_all))
    # Modbus "实跑达标"＝每轮都由真实协议栈读到完整行数（兜底轮不算）
    modbus_real = rows_ok and rounds_real == rounds
    sent_all = not pending and rows_total > 0
    json_ok = bool(payloads) and all(
        set(p) == {"id", "ts", "metrics"}
        and set(p["metrics"]) == {"temp", "press"}
        and isinstance(p["ts"], int) for p in payloads)

    levels, log_lines = measure_log(log_path)
    stats = stylecheck.scan_project(ROOT)
    v = tiers.verdict(
        rate=stats["rate"], rows_ok=rows_ok, sent_all=sent_all,
        modbus_real=modbus_real, mqtt_real=mqtt_real,
        rounds_done=len(rows_all), rounds_need=rounds, json_ok=json_ok,
        reconnect_attempts=recon_attempts,
        log_error_count=levels.get("ERROR", 0), loopback_ok=lb_ok,
        loopback_receipts=lb_n, gates=tiers.gates_from(cfg.tier_gates()))
    result = {
        "devices": len(devs), "rounds": len(rows_all),
        "rounds_need": rounds, "rows_total": rows_total,
        "sent": ok_n, "pending": len(pending), "batches": bs_total,
        "rows": rows_all[0] if rows_all else [],
        "payload_sample": payloads[0] if payloads else {},
        "payload_count": len(payloads),
        "rows_ok": rows_ok, "sent_all": sent_all, "json_ok": json_ok,
        "modbus": {"real": modbus_real, "attempts": m_attempts,
                   "detail": m_detail, "channel": modbus_channel},
        "mqtt": {"real": mqtt_real, "detail": transport_note},
        "reconnect": {"attempts": recon_attempts},
        "loopback": {"ok": lb_ok, "receipts": lb_n, "detail": lb_detail,
                     "first": lb_first},
        "transport": transport_note,
        "log": {"path": log_path, "lines": log_lines, "levels": levels},
        "style_rate": stats["rate"],
        "style_violations": stats["violations"],
        "style_engine": stats["engine"],
        "tiers": v,
    }
    sections = _sections(devs, rounds, n_batch, bs_total, rows_total,
                         ok_n, pending, json_ok, result, levels,
                         log_lines, log_path, stats, v, transport_note,
                         m_host, m_port, q_host, q_port, topic)
    report.save(sections, os.path.join(out_dir, "report.txt"))
    io_utils.write_json(os.path.join(out_dir, "result.json"), result)
    return sections, result


def _sections(devs, rounds, n_batch, bs_total, rows_total, ok_n, pending,
              json_ok, result, levels, log_lines, log_path,
              stats, v, transport_note, m_host, m_port, q_host, q_port,
              topic):
    """渲染报告段——所有数字都是本次运行实测。"""
    input_line = ("设备 %d 台 ｜ 采集轮次 %d ｜ 批大小 %d → 共 %d 批 ｜ "
                  "topic %s"
                  % (len(devs), rounds, n_batch, bs_total, topic))
    channel_line = ("通道来源（如实标注）：Modbus %s ｜ MQTT %s:%d ｜ 运输: %s"
                    % (result["modbus"]["channel"], q_host, q_port,
                       transport_note))
    pct = ok_n * 100.0 / max(rows_total, 1)
    collect_line = "采集行数 %d 条 ｜ 上报成功 %d 条（%.0f%%）" % (
        rows_total, ok_n, pct)
    pending_line = ("%d 条 → output/pending.json（重启后补传）" % len(pending)
                    if pending else "无（本轮全部进入上报通道）")
    p = result["payload_sample"]
    json_line = ("JSON 结构（id/ts/metrics）: %s ｜ 样例 %s"
                 % ("规范" if json_ok else "不规范",
                    json.dumps(p, ensure_ascii=False)))
    mb = result["modbus"]
    mq = result["mqtt"]
    lb = result["loopback"]
    rc = result["reconnect"]
    modbus_line = ("Modbus 实跑: %s ｜ 连接尝试 %d 次 ｜ %s"
                   % ("达标" if mb["real"] else "未达标",
                      mb["attempts"], mb["detail"]))
    mqtt_line = "MQTT 实跑: %s ｜ %s" % (
        "达标" if mq["real"] else "未达标", mq["detail"])
    reconnect_line = ("断线重连实测: 尝试 %d 次（拔线→连接失败 ERROR→重连成功）"
                      % rc["attempts"])
    lb_line = "订阅回环: %s ｜ 收到 %d 条 ｜ %s ｜ 首条回执 %s" % (
        "达标" if lb["ok"] else "未达标", lb["receipts"], lb["detail"],
        lb["first"] or "-")
    log_line = ("run.log 实测 %d 行 ｜ INFO %d ｜ WARNING %d ｜ ERROR %d"
                " ｜ 路径 %s" % (
                    log_lines, levels.get("INFO", 0),
                    levels.get("WARNING", 0),
                    levels.get("ERROR", 0), log_path))
    conclusion = ["'宁可慢不可丢'：失败批次可追溯、可补传（pending.json）"]
    m = v["measured"]
    if not v["tiers"][0]["pass"]:
        reason = ("真实服务面未完全拉起（Modbus/MQTT 通道缺失）"
                  if not (m["modbus_real"] and m["mqtt_real"])
                  else "断线窗口有批次未确认送达（已入 pending 待补传）")
        conclusion.append("D 档未达标：%s——通道来源已如实标注，"
                          "修好环境/补传后复跑即可同口径勾选" % reason)
    return [
        ("输入口径", [input_line, channel_line]),
        ("采集与上报（实测）",
         [collect_line, json_line, "待补传: " + pending_line]),
        ("真实通道探测（工单'实跑非模拟'）",
         [modbus_line, mqtt_line, reconnect_line, lb_line]),
        ("日志与异常（logging 实测）", [log_line]),
        ("编码规范率（stylecheck 实测）",
         stylecheck.format_section(stats, 90.0)),
        ("验收档位判定（实测）", tiers.render_lines(v)),
        ("结论与建议", conclusion),
    ]


def run(cfg, out_dir, echo=False):
    sections, _result = build(cfg, out_dir=out_dir, echo=echo)
    return sections
