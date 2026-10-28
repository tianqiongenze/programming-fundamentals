# -*- coding: utf-8 -*-
"""工单 W11 四档验收断言——每档钉在实测值上，能力删掉必须红。

判据与 tiers.verdict / pipeline / cli --tier 同源（工单验收标准表）：
D(≥80%) Modbus 实跑+MQTT 发布实跑；C(≥85%) 5 轮采集完整+JSON 规范；
B(≥90%) 断线重连实测（拔线→失败 ERROR→重连成功，尝试≥2 次）；
A(≥90%) 达 B 且订阅回环实测收到逐字节一致的回执。
pipeline 自带真实服务面拉起（课程 mini broker 子进程 + pymodbus 本地
从站），课堂 anaconda 环境下四档应全绿——正向测试钉死这一点；哪天环境
缺库/端口被占导致变红，就是如实报警，禁止为变绿调低门槛。诚实红线测试
（test_D_A_honest...）保证"没实跑成功"绝不会被判达标。
"""
import json
import os

import pytest

from telemetry_upload import cli
from telemetry_upload import config as C
from telemetry_upload import io_utils, pipeline, tiers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "rules.yaml")
OUT = os.path.join(ROOT, "output", "test_run")


@pytest.fixture(scope="module")
def built():
    """跑一次完整流水线，模块内所有断言共用同一批实测值。"""
    sections, result = pipeline.build(C.load_config(CFG), out_dir=OUT)
    return sections, result


def tiers_of(v):
    """verdict 返回 → {档位字母: 判定}，实测与手工构造走同一口径。"""
    return {t["tier"][-2]: t for t in v["tiers"]}


def full_verdict(**over):
    """构造一套"全部实测达标"的输入，供反向测试逐项抽能力。"""
    kw = dict(rate=99.0, rows_ok=True, sent_all=True,
              modbus_real=True, mqtt_real=True,
              rounds_done=5, rounds_need=5, json_ok=True,
              reconnect_attempts=2, log_error_count=1, loopback_ok=True)
    kw.update(over)
    return tiers.verdict(**kw)


def test_C_five_rounds_complete(built):
    """C 档：5 轮采集完整——轮数、每轮行数都取本次实测。"""
    _, r = built
    assert r["rounds_need"] >= 5 and r["rounds"] == r["rounds_need"]
    assert r["rows_ok"] and r["rows_total"] == r["rounds"] * r["devices"]


def test_C_json_structure_is_id_ts_metrics(built):
    """C 档：JSON 结构规范——每条消息恰为 id/ts/metrics，metrics 含 temp/press。"""
    _, r = built
    assert r["json_ok"], "payload 必须严格符合工单 B05 的 id/ts/metrics"
    assert r["payload_count"] == r["rows_total"]
    p = r["payload_sample"]
    assert set(p) == {"id", "ts", "metrics"}
    assert set(p["metrics"]) == {"temp", "press"}
    assert isinstance(p["ts"], int) and str(p["id"])


def test_B_reconnect_actually_attempted(built):
    """B 档：断线重连实测——真实拔线后重连，尝试次数≥2（失败一次+成功一次）。"""
    _, r = built
    assert r["reconnect"]["attempts"] >= 2, (
        "未观察到断线重连演示（实测 %d 次）" % r["reconnect"]["attempts"])


def test_B_run_log_is_real_logging_with_errors(built):
    """B 档：异常日志清晰——run.log 真落盘且反读到 ERROR（拔线后连接失败实录）。"""
    _, r = built
    path = r["log"]["path"]
    assert path.endswith("run.log") and os.path.exists(path)
    assert os.path.getsize(path) > 1000, "logging 必须真落盘，不是 print"
    assert r["log"]["levels"].get("ERROR", 0) >= 1
    assert r["log"]["levels"].get("INFO", 0) >= r["rounds"]


def test_B_measured_style_rate_at_least_90(built):
    _, r = built
    assert r["style_rate"] >= 90.0, (
        "B/A 档门槛≥90%%，实测 %.1f%%（引擎 %s）"
        % (r["style_rate"], r["style_engine"]))


def test_A_loopback_receipt_is_byte_exact(built):
    """A 档：订阅回环回执实测存在且载荷可解析（首条就是打印进日志的那条）。"""
    _, r = built
    lb = r["loopback"]
    assert lb["ok"] and lb["receipts"] >= 1, "回环没收到回执就是未达标"
    p = json.loads(lb["first"])
    assert p["id"] == "PROBE" and set(p) == {"id", "ts", "metrics"}


def test_all_four_tiers_pass_on_real_stack(built):
    """正向钉死：课堂环境（paho+pymodbus+课程 broker 脚本）下四档全绿。"""
    _, r = built
    got = tiers_of(r["tiers"])
    for key in ("D", "C", "B", "A"):
        assert got[key]["pass"], "%s 档实测未达标: %s" % (key, got[key])
    assert r["tiers"]["claimed"] == "优(A)"


def test_D_A_honest_when_channel_missing(built):
    """诚实红线：通道没实跑成功，D 必须判未达标；没回环回执，A 必须未达标。"""
    _, r = built
    got = tiers_of(r["tiers"])
    m = r["tiers"]["measured"]
    assert got["D"]["functional"] == bool(
        m["modbus_real"] and m["mqtt_real"] and m["rows_ok"]
        and m["sent_all"])
    assert got["A"]["functional"] == bool(got["B"]["functional"]
                                          and m["loopback_ok"])
    if not (m["modbus_real"] and m["mqtt_real"]):
        assert got["D"]["pass"] is False, "无服务端却称 D 达标＝造假"
    if not m["loopback_ok"]:
        assert got["A"]["pass"] is False, "无回环回执却称 A 达标＝造假"


def test_claimed_is_highest_passing_tier(built):
    """档位是算出来的：claimed 必须等于实测通过的最高档。"""
    _, r = built
    passed = [t["tier"] for t in r["tiers"]["tiers"] if t["pass"]]
    expect = passed[-1] if passed else "未达 D 档"
    assert r["tiers"]["claimed"] == expect


def test_result_json_persisted(built):
    """落盘可备查：result.json 里的档位判定与内存实测一致，且真实成文。"""
    _, r = built
    path = os.path.join(OUT, "result.json")
    assert os.path.getsize(path) > 1000
    data = io_utils.read_json(path)
    assert data["tiers"]["claimed"] == r["tiers"]["claimed"]


def test_report_contains_tier_and_log_evidence(built):
    """报告证据链：档位判定段、run.log 路径与回环回执都要成文。"""
    sections, r = built
    text = "\n".join("%s\n%s" % (t, "\n".join(ls)) for t, ls in sections)
    assert "验收档位判定（实测）" in text and "run.log" in text
    assert "订阅回环" in text and "首条回执" in text
    assert "未达标" in text or r["tiers"]["claimed"] == "优(A)"


def test_gate_fails_below_minimum():
    """档位是算出来的：只采了 4 轮或从未重连，C/B 必须判不达标。"""
    weak = tiers.verdict(rate=99.0, rows_ok=True, sent_all=True,
                         modbus_real=False, mqtt_real=False,
                         rounds_done=4, rounds_need=5, json_ok=True,
                         reconnect_attempts=1, log_error_count=0,
                         loopback_ok=False)
    got = tiers_of(weak)
    assert got["C"]["pass"] is False and got["B"]["pass"] is False


def test_tier_claim_drops_when_capability_removed():
    """反向证明：抽掉重连能力，B/A 当场掉档，其余档不受牵连。"""
    full = full_verdict()
    assert tiers_of(full)["D"]["pass"] and tiers_of(full)["A"]["pass"]
    down = full_verdict(reconnect_attempts=1)
    got = tiers_of(down)
    assert not got["B"]["pass"] and not got["A"]["pass"]
    assert got["C"]["pass"] and got["D"]["pass"]


def test_A_drops_when_loopback_removed():
    """反向证明：订阅回环收不到回执（A 档能力删掉），档位必须从 A 掉回 B。"""
    down = full_verdict(loopback_ok=False)
    got = tiers_of(down)
    assert got["B"]["pass"] and not got["A"]["pass"]
    assert down["claimed"] == "优秀(B)"


def test_D_drops_when_channel_fabricated():
    """反向证明：Modbus 没实跑（虚拟兜底冒充），D 当场塌，C 仍按自身口径。"""
    down = full_verdict(modbus_real=False)
    got = tiers_of(down)
    assert not got["D"]["pass"] and got["C"]["pass"]


def test_gates_are_externalized_in_rules_yaml(built):
    """门槛数字外置在 rules.yaml 的 tiers 段，config.py 读出并生效。"""
    cfg = C.load_config(CFG)
    gates = cfg.tier_gates()
    assert gates.get("D") == 80.0 and gates.get("B") == 90.0
    _, r = built
    m = r["tiers"]["measured"]
    v = tiers.verdict(rate=82.0, rows_ok=m["rows_ok"],
                      sent_all=m["sent_all"], modbus_real=m["modbus_real"],
                      mqtt_real=m["mqtt_real"],
                      rounds_done=m["rounds_done"],
                      rounds_need=m["rounds_need"], json_ok=m["json_ok"],
                      reconnect_attempts=m["reconnect_attempts"],
                      log_error_count=m["log_error_count"],
                      loopback_ok=m["loopback_ok"],
                      gates=tiers.gates_from(gates))
    got = tiers_of(v)
    assert got["D"]["pass"] and not got["C"]["pass"], (
        "82% 应达 D(≥80) 而不达 C(≥85)——门槛必须来自 rules.yaml")


def test_report_contains_manual_items(built):
    """人工答辩项（截图归档、PLC 口径核对）如实写进报告，机器不代判。"""
    sections, _ = built
    text = "\n".join("\n".join(x) for _t, x in sections)
    assert "人工答辩项" in text and tiers.manual


def test_cli_quiet_run_exits_zero_and_reports(tmp_path):
    """run.py --quiet 全链路：退出码 0，report.txt 带档位判定段且成文。"""
    out = str(tmp_path / "cli_run")
    rc = cli.main(["--quiet", "--config", CFG, "--outdir", out])
    assert rc == 0
    path = os.path.join(out, "report.txt")
    assert os.path.getsize(path) > 1000
    text = open(path, encoding="utf-8").read()
    assert "验收档位判定（实测）" in text
    assert os.path.exists(os.path.join(out, "run.log"))
