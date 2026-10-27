# -*- coding: utf-8 -*-
# [教学脚手架] 下列导入/变量供 TODO 完成后使用，故标注 noqa 而非删除
"""W11 工业互联网数据采集系统 —— Modbus采集 + MQTT上报
前置: 先启动虚拟产线(见README): mini_modbus_server.py 5020 1 与 mini_mqtt_broker.py
"""
import json  # noqa: F401
import time

from pymodbus.client import ModbusTcpClient as Client  # noqa: F401
import paho.mqtt.client as mqtt

PLC_HOST, PLC_PORT = "127.0.0.1", 5020
BROKER = "127.0.0.1"
TOPIC = "device/1/status"
NAMES = ["temp_c", "press_mpa", "vib_mm_s", "rpm", "status"]


def read_plc():
    """TODO-1: 连接PLC读40001-40005(地址0-4), ÷10还原工程值(status除外)
    pymodbus 3.x: c=Client(host=host, port=port); c.connect();
                  rr=c.read_holding_registers(address=0, count=5); rr.registers
    返回 dict 或 None(失败)"""
    # === 你的代码 ===
    return None


def publish(mq, data):
    """TODO-2: JSON序列化后发布到TOPIC (保留质量戳时间戳字段ts)"""
    # payload = json.dumps({"device_id":"DEV-1","ts":...,"metrics":data}, ensure_ascii=False)
    # === 你的代码 ===
    pass


def main():
    # paho-mqtt 2.x要求显式指定callback API版本（VERSION1保持经典on_connect签名）
    mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    # TODO-3: 连接Broker(connect/loop_start), 失败时try捕获
    for i in range(5):
        data = read_plc()
        if data is None:
            print("采集失败, 重试...")
            time.sleep(1)
            continue
        print("第%02d轮:" % (i + 1), data)
        publish(mq, data)
        time.sleep(2)              # TODO-4(决策): 间隔取几秒? 写入工单
    # TODO-5(优秀): 订阅device/1/status回环验证(on_message打印回执)
    mq.loop_stop()


if __name__ == "__main__":
    main()
