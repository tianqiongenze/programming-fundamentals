# -*- coding: utf-8 -*-
"""
mini Modbus TCP 模拟器（纯Python标准库, 教学用）—— W11《工业互联网数据采集系统》
模拟一台"PLC": 保持寄存器映射为工业测点, 数值按物理规律缓慢波动。
用法:  python mini_modbus_server.py [port] [unit_id]
       默认 5020 / 1 ; 开3个终端换端口即得3台PLC
支持功能码: 0x03 读保持寄存器(限1-8个)
寄存器表(每台PLC):
  40001 温度℃(20-90波动)   40002 压力MPa(0.1-0.9×10)   40003 振动mm/s(1-8×10)
  40004 转速rpm/10         40005 状态字(0正常/1告警)
pymodbus客户端示例见 学生代码框架/W11_collector.py
"""
import socket
import struct
import sys
import threading
import time


class PlcSimulator:
    REG_COUNT = 8

    def __init__(self, unit_id=1):
        self.unit = unit_id
        self.t0 = time.time()
        self.lock = threading.Lock()

    def registers(self):
        """按时间演化的测点值(×10定点存储, 仿真常见做法)"""
        t = time.time() - self.t0
        temp = 55 + 15 * __import__("math").sin(t / 20 + self.unit)
        press = 5 + 2 * __import__("math").sin(t / 15)
        vib = 30 + 25 * abs(__import__("math").sin(t / 8 + self.unit))
        rpm = 1480 + 40 * __import__("math").sin(t / 30)
        status = 1 if vib / 10 > 4.5 else 0        # 振动>4.5mm/s置告警位
        regs = [int(temp * 10), int(press * 10), int(vib),
                int(rpm / 10), status, 0, 0, 0]
        return regs

    def handle(self, conn):
        try:
            while True:
                head = conn.recv(7)                # MBAP头
                if len(head) < 7:
                    break
                tid, pid, length, uid = struct.unpack(">HHHB", head)
                body = conn.recv(length - 1)
                if len(body) < 4:
                    break
                fc, addr, qty = struct.unpack(">BHH", body[:5])
                with self.lock:
                    regs = self.registers()
                if fc == 3 and 0 <= addr < self.REG_COUNT and 1 <= qty <= 8:
                    vals = regs[addr:addr + qty]
                    payload = struct.pack(">B", fc) + struct.pack(">B", qty * 2)
                    for v in vals[:qty]:
                        payload += struct.pack(">H", v)
                else:                              # 异常响应: 功能码+0x80
                    payload = struct.pack(">BB", fc + 0x80, 2)
                # MBAP长度字段=其后字节数=unit(1)+PDU; 事务/单元ID回显请求
                conn.sendall(struct.pack(">HHHB", tid, 0,
                                         len(payload) + 1, uid) + payload)
        except (ConnectionResetError, OSError):
            pass
        finally:
            conn.close()

    def serve(self, port):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(8)
        print(f"PLC模拟器#{self.unit} 运行于 0.0.0.0:{port} "
              f"(保持寄存器: 40001温度 40002压力 40003振动 40004转速 40005状态)")
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=self.handle, args=(conn,),
                             daemon=True).start()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5020
    unit = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    PlcSimulator(unit).serve(port)
