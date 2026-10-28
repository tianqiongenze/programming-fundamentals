# -*- coding: utf-8 -*-
"""真实通道探测与持久链路：Modbus 采数 + MQTT 发布/订阅回环（工单 W11）。

一律走真实 TCP 协议栈（pymodbus / paho-mqtt）。课程自研 mini broker
只支持 QoS0——发布/订阅一律 QoS0，回环必须逐字节核对收到的载荷，
"没收到/收错了"如实判缺。**缺服务就标未达标，不假装成功。**
"""
import logging
import time

log = logging.getLogger("telemetry_upload.live")


def _new_client(client_id="w11"):
    """paho-mqtt 1.x/2.x 兼容的客户端构造。"""
    import paho.mqtt.client as mqtt
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                           client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id)


def modbus_read_round(host, port, count=2, retries=1, timeout=0.5):
    """读保持寄存器并 ÷10 还原工程值；连接失败按工单要求重试。

    返回 (rows|None, attempts, detail)——attempts 实测"断线重连"发生了几次。
    """
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError as exc:
        return None, 0, "pymodbus 未安装: %s" % exc
    attempts = 0
    last = ""
    for _ in range(retries + 1):
        attempts += 1
        client = ModbusTcpClient(host, port=port, timeout=timeout)
        try:
            if not client.connect():
                raise ConnectionError("connect() 返回失败")
            rr = client.read_holding_registers(0, count=count)
            regs = list(rr.registers)
            rows = [{"code": "MODBUS-%02d" % (i // 2 + 1),
                     "temp": regs[i] / 10.0, "press": regs[i + 1] / 10.0}
                    for i in range(0, len(regs) - 1, 2)]
            return rows, attempts, "实跑成功（%d 寄存器）" % len(regs)
        except (OSError, ConnectionError, AttributeError,
                ValueError) as exc:
            last = "%s: %s" % (type(exc).__name__, exc)
            log.error("Modbus 第 %d 次连接 %s:%d 失败: %s",
                      attempts, host, port, last)
        finally:
            client.close()
    return None, attempts, last


def probe_connect(host, port):
    """新建真实 TCP 连接实测端口通断（断线/重连判定的物证）。"""
    client = _new_client("w11-probe")
    try:
        client.connect(host, int(port), 2)
        client.disconnect()
        return True, "连接成功"
    except (OSError, ValueError) as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


class MqttLink:
    """一条持久 MQTT 发布链路：真实 connect / publish(QoS0) / reconnect。

    刻意不起 paho 网络线程：无线程时 publish 由调用线程同步把字节写进
    真实 socket（内部即时 loop_write），既拿到确定性证据，也杜绝"隐形
    自动重连"与断线重连演示打架。QoS0 无 PUBACK，以 is_published（已
    释放写入 socket）为发布成功证据；写失败/掉线在途则如实判 False，
    由上层 send_with_retry 兜底——宁可慢不可丢。
    """

    def __init__(self, host, port, topic, client_id="w11-pub"):
        self.host = host
        self.port = int(port)
        self.topic = topic
        self.client_id = client_id
        self.client = None

    def connect(self):
        self.client = _new_client(self.client_id)
        self.client.connect(self.host, self.port, 10)

    def publish(self, payload, timeout=1.5):
        """QoS0 真实投递：字节写完（is_published）才算成功。"""
        if self.client is None:
            return False
        try:
            info = self.client.publish(self.topic, payload, qos=0)
            if int(info.rc) != 0:
                return False
            deadline = time.time() + timeout
            while not info.is_published() and time.time() < deadline:
                self.client.loop_write(0.05)
            return info.is_published()
        except (OSError, RuntimeError, ValueError):
            return False

    def hard_disconnect(self):
        """真实拔线（外部 broker 场景）：关闭连接，也没有线程可暗中重连。"""
        try:
            if self.client:
                self.client.disconnect()
        except (OSError, ValueError):
            pass

    def reconnect(self):
        self.client.reconnect()

    def close(self):
        try:
            if self.client:
                self.client.disconnect()
        except (OSError, ValueError):
            pass


def subscribe_loopback(topic, payload, host="127.0.0.1", port=1883,
                       wait=1.5):
    """订阅回环验证（A 档）：独立订阅端实测收到并逐字节核对回执。

    broker 不向发布者自身转发（MQTT 语义），故用两个真实客户端：
    订阅端先 SUBSCRIBE，发布端再 PUBLISH（网络线程实写 socket），
    订阅端收到才算回环成立。返回 (ok, 收到条数, 首条回执载荷, detail)。
    """
    got = []
    sub = _new_client("w11-loopback-sub")
    sub.on_message = lambda c, u, m: got.append(m)
    try:
        sub.connect(host, int(port), 5)
    except (OSError, ValueError) as exc:
        return False, 0, "", "broker 不可达: %s" % exc
    sub.subscribe(topic, qos=0)
    sub.loop_start()
    time.sleep(0.2)  # 等 SUBACK 落地再发布，避免回环丢首条
    pub = _new_client("w11-loopback-pub")
    try:
        pub.connect(host, int(port), 5)
        # 不起线程：publish 同步写字节，再留一个短超时兜住半开连接
        info = pub.publish(topic, payload, qos=0)
        deadline = time.time() + 1.0
        while not info.is_published() and time.time() < deadline:
            pub.loop_write(0.05)
        pub.disconnect()
    except (OSError, ValueError, RuntimeError) as exc:
        sub.loop_stop()
        sub.disconnect()
        return False, 0, "", "发布端不可达: %s" % exc
    deadline = time.time() + wait
    while not got and time.time() < deadline:
        time.sleep(0.05)
    sub.loop_stop()
    sub.disconnect()
    want = payload.encode("utf-8")
    matched = [m for m in got if bytes(m.payload) == want]
    first = matched[0].payload.decode("utf-8", "replace") if matched else ""
    return (len(matched) >= 1), len(got), first, (
        "收到 %d 条（载荷逐字节一致 %d 条）" % (len(got), len(matched)))
