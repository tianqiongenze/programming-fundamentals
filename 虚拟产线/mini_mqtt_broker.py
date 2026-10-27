# -*- coding: utf-8 -*-
"""
mini MQTT 代理（纯Python标准库, 教学子集: CONNECT/PUBLISH/SUBSCRIBE, QoS0）
—— W11《工业互联网数据采集系统》离线环境
用法:  python mini_mqtt_broker.py [port]      # 默认1883
说明:
  * 实现 MQTT 3.1.1 报文的最小子集, 供 paho-mqtt 客户端本机联调;
  * 支持: CONNECT/CONNACK, SUBSCRIBE/SUBACK, PUBLISH(QoS0, 主题通配符 + 与 # );
  * 不支持: QoS1/2、RETAIN、持久会话——教学中正好用于演示"QoS差异"话题。
自测:  mosquitto_pub/sub 或 paho-mqtt 连 127.0.0.1:1883
"""
import socket
import threading
import sys


class MiniBroker:
    def __init__(self):
        self.subs = {}                        # topic过滤串 -> set(client)
        self.lock = threading.Lock()

    # ---------- MQTT报文工具 ----------
    @staticmethod
    def enc_remaining(n):
        out = b""
        while True:
            b = n % 128
            n //= 128
            out += bytes([b | 0x80 if n else b])
            if not n:
                return out

    @staticmethod
    def dec_remaining(buf, i):
        mul, val, = 1, 0
        while True:
            b = buf[i]
            i += 1
            val += (b & 0x7F) * mul
            if not b & 0x80:
                return val, i
            mul *= 128

    @staticmethod
    def topic_match(flt, topic):
        """主题过滤器匹配（MQTT 3.1.1 语义）：
        '+' 匹配**一层**（device/+/status ↔ device/DEV-A1/status），
        '#' 匹配其后所有层（device/# ↔ device/A/status/extra）。"""
        if "#" in flt:
            head = flt.rpartition("#")[0].rstrip("/")
            if not head:                        # 根过滤器 "#" 匹配一切
                return True
            return topic == head or topic.startswith(head + "/")
        f, t = flt.split("/"), topic.split("/")
        return len(f) == len(t) and all(a == "+" or a == b for a, b in zip(f, t))

    def route(self, topic, payload, sender):
        with self.lock:
            targets = [c for f, cs in self.subs.items()
                       if self.topic_match(f, topic) for c in cs if c is not sender]
        for c in targets:
            try:
                body = struct_h(len(topic)) + topic.encode() + payload
                pkt = bytes([0x30]) + self.enc_remaining(len(body)) + body
                c.sendall(pkt)
            except OSError:
                pass

    def handle(self, conn):
        try:
            buf = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while len(buf) >= 2:
                    rl, i = self.dec_remaining(buf, 1)
                    if len(buf) < i + rl:
                        break
                    pkt, buf = buf[:i + rl], buf[i + rl:]
                    self.on_packet(conn, pkt)
        except OSError:
            pass
        finally:
            with self.lock:
                for cs in self.subs.values():
                    cs.discard(conn)
            conn.close()

    def on_packet(self, conn, pkt):
        ptype = pkt[0] >> 4
        if ptype == 1:                        # CONNECT → CONNACK
            conn.sendall(b"\x20\x02\x00\x00")
        elif ptype == 8:                      # SUBSCRIBE → SUBACK
            rl, i = self.dec_remaining(pkt, 1)
            topic_len = struct_h_parse(pkt[i + 2:i + 4])
            topic = pkt[i + 4:i + 4 + topic_len].decode()
            with self.lock:
                self.subs.setdefault(topic, set()).add(conn)
            conn.sendall(b"\x90\x03" + pkt[i:i + 2] + b"\x00")
        elif ptype == 3:                      # PUBLISH(QoS0)
            rl, i = self.dec_remaining(pkt, 1)
            tl = struct_h_parse(pkt[i:i + 2])
            topic = pkt[i + 2:i + 2 + tl].decode()
            payload = pkt[i + 2 + tl:]
            self.route(topic, payload, conn)


def struct_h(v):
    return v.to_bytes(2, "big")


def struct_h_parse(b):
    return int.from_bytes(b, "big")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 1883
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(16)
    print(f"mini MQTT代理运行于 0.0.0.0:{port} (QoS0, 支持+/ #通配)")
    broker = MiniBroker()
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=broker.handle, args=(conn,), daemon=True).start()
