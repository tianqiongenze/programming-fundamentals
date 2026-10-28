# -*- coding: utf-8 -*-
"""本地真实服务面：课程包自研 mini broker 子进程 + pymodbus 本地从站。

"环境也是选型维度"（与 w06/w12 同一原则）：
  * 配置端口已有外部服务（课堂虚拟产线/机房 mosquitto）→ 直接复用；
  * 不可达 → 在拉起本地真实服务：mini broker 是真实 TCP socket 服务、
    pymodbus 从站是真实 Modbus TCP 协议栈——paho/pymodbus 客户端走的
    都是真 socket，不是内存里"假装"成功；
  * 拉不起来 → 如实返回原因（pipeline 降级并标注通道来源，绝不谎称实跑）。
"""
import asyncio
import os
import socket
import subprocess
import sys
import threading
import time
import warnings

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
#: 课程包根（工程化项目/w11 → 02-程序设计基础），自研 broker 在虚拟产线/
COURSE = os.path.normpath(os.path.join(PROJ, "..", ".."))
BROKER_SCRIPT = os.path.join(COURSE, "虚拟产线", "mini_mqtt_broker.py")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_open(host, port, timeout=0.3):
    try:
        with socket.create_connection((host, int(port)), timeout):
            return True
    except OSError:
        return False


def _wait_port(host, port, deadline=5.0):
    end = time.time() + deadline
    while time.time() < end:
        if port_open(host, port):
            return True
        time.sleep(0.1)
    return False


class BrokerService:
    """课程包自研 mini_mqtt_broker（MQTT 3.1.1 子集，QoS0，真实 TCP）。"""

    def __init__(self, host="127.0.0.1", port=1883):
        self.host = host
        self.port = int(port)
        self.proc = None
        self.owned = False
        self.detail = ""

    def start(self):
        if port_open(self.host, self.port):
            self.detail = "复用外部 broker %s:%d（未接管）" % (
                self.host, self.port)
            return True
        if not os.path.exists(BROKER_SCRIPT):
            self.detail = "mini_mqtt_broker.py 缺失: %s" % BROKER_SCRIPT
            return False
        self.proc = subprocess.Popen(
            [sys.executable, BROKER_SCRIPT, str(self.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.owned = True
        if _wait_port(self.host, self.port):
            self.detail = "已拉起自研 mini broker（子进程 %d, 端口 %d）" % (
                self.proc.pid, self.port)
            return True
        self.stop()
        self.detail = "mini broker 拉起超时（端口 %d 未就绪）" % self.port
        return False

    def kill(self):
        """真实拔线：终止 broker 进程，在途连接即刻失依赖。"""
        if self.proc and self.owned:
            self.proc.kill()
            self.proc.wait()

    def restart(self):
        self.kill()
        time.sleep(0.2)
        return self.start()

    def stop(self):
        self.kill()
        self.proc = None


class ModbusService:
    """pymodbus 本地从站（真实 Modbus TCP 协议栈，寄存器=设备×2）。

    3.15 起 datastore API 改版（ModbusSlaveContext → ModbusDeviceContext），
    若本机版本较旧则 import 失败——start() 如实捕获降级，绝不谎称实跑；
    个别版本的启动告警属教学噪音，统一屏蔽。
    """

    def __init__(self, values):
        self.values = [int(v) for v in values]
        self.port = free_port()
        self.detail = ""
        self._loop = None
        self._thread = None
        self._server_fut = None

    def start(self):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from pymodbus.datastore import (ModbusDeviceContext,
                                                ModbusServerContext,
                                                ModbusSequentialDataBlock)
                from pymodbus.server import StartAsyncTcpServer
        except ImportError as exc:
            self.detail = "pymodbus 未安装: %s" % exc
            return False
        if not self.values:
            self.detail = "无寄存器数据可挂载"
            return False

        async def serve():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                dev = ModbusDeviceContext(
                    hr=ModbusSequentialDataBlock(1, self.values))
                ctx = ModbusServerContext(devices=dev, single=True)
                await StartAsyncTcpServer(context=ctx,
                                          address=("127.0.0.1", self.port))
        try:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._loop.run_forever,
                                            daemon=True)
            self._thread.start()
            fut = asyncio.run_coroutine_threadsafe(serve(), self._loop)
            self._server_fut = fut
        except Exception as exc:
            self.detail = "pymodbus 从站启动失败: %s" % exc
            return False
        if _wait_port("127.0.0.1", self.port):
            self.detail = "已拉起 pymodbus 本地从站（端口 %d，真实协议栈）" % (
                self.port)
            return True
        self.stop()
        self.detail = "pymodbus 从站启动超时"
        return False

    def stop(self):
        try:
            if self._loop and self._loop.is_running():
                # loop 线程内先取消全部任务、再延迟停 loop：直接 loop.stop
                # 会让 serve 任务停在 cancelling 状态被 GC，打出
                # "Task was destroyed" 噪音——控制台与日志都必须干净
                self._loop.call_soon_threadsafe(self._shutdown)
            if self._thread:
                self._thread.join(timeout=2.0)
        except Exception:
            pass

    def _shutdown(self):
        for task in asyncio.all_tasks(self._loop):
            task.cancel()
        self._loop.call_later(0.05, self._loop.stop)
