# -*- coding: utf-8 -*-
"""设备类：显式 __init__ 出厂建档 + 状态机校验 + __str__ 可读化 + 方法间协作日志。

对应工单 W04《工业设备类设计》任务 1~4：
  任务1 ≥2 属性 + ≥2 方法（start/stop/get_status）；
  任务2 使用 __init__ 构造方法（本课刻意**不用** dataclass，让 `self` 看得见）；
  任务3 创建 ≥2（实测 3）个设备对象并演示属性访问、方法调用；
  任务4 打印对象输出可读信息（__str__，另附 __repr__ 给开发者看）。

档位与代码位置的对应关系（验收时按此索引）：
  D：本类的 __init__ + start/stop + 3 个实例（config/rules.yaml devices）
  C：start/stop 入口的状态校验（抛 AlreadyRunningError / NotRunningError）
  B：≥3 属性 + ≥3 方法 + __str__/get_status + 3 实例 + 规范率≥90%
  A：方法间协作——start/stop/set_temp 全部经 _log() 往 self.logs 累积日志字符串
"""
from datetime import datetime

STATUS_RUN = "运行"
STATUS_STOP = "停机"
# 全厂设备体温物理量程：超出即判定为脏数据（工单"避坑"：别让脏值进对象）
TEMP_MIN, TEMP_MAX = -40.0, 200.0
DEFAULT_WARN, DEFAULT_DANGER = 80.0, 95.0


class DeviceError(Exception):
    """设备操作错误基类——调用方可以只兜这一层。"""


class AlreadyRunningError(DeviceError):
    """设备已在运行，禁止重复启动（C 档状态校验）。"""


class NotRunningError(DeviceError):
    """设备未运行，禁止执行仅运行态可做的操作（C 档状态校验）。"""


class OutOfRangeError(DeviceError, ValueError):
    """读数越界：既是设备业务错，也是 ValueError（便于外层按两种口径兜）。"""


class Device:
    """设备类＝图纸：实例属性存每台自己的数据，行为与数据绑在一起才是对象。"""

    # 类属性＝全厂共享的"公告栏"（工单 B01 进阶）：所有设备同一厂区码，省内存
    plant_code = "PLANT-A"

    def __init__(self, code, kind, temp=0.0, warn=DEFAULT_WARN, danger=DEFAULT_DANGER):
        """构造器：出生即建档。self 就是"当前这台设备自己"，调用时 Python 自动传。"""
        self.code = str(code)                       # 属性1 编号（工单点名的 id）
        self.kind = str(kind)                       # 属性2 名称/型号（工单点名的 name）
        self.temp = float(temp)                     # 属性3 温度
        self.warn = float(warn)                     # 属性4 本机预警线（可覆盖全局）
        self.danger = float(danger)                 # 属性5 本机停机线
        self.status = STATUS_STOP                   # 属性6 状态（只能由方法改写）
        self.logs = []                              # 属性7 操作日志（A 档协作载体）
        self._log("建档出厂")

    @property
    def running(self):
        """派生只读属性：由 status 算出来。外部 `d.running = True` 会 AttributeError，
        因此想改状态就只能走 start()/stop()——状态机的门只能从里面开。"""
        return self.status == STATUS_RUN

    def _log(self, msg):
        """方法间协作的唯一入口：任何状态/读数变化都往 self.logs 追加一行字符串。"""
        line = "[%02d] %s %s ｜%s｜%.1f℃" % (
            len(self.logs) + 1, self.code, msg, self.status, self.temp)
        self.logs.append(line)
        return line

    def start(self):
        """启动：先验状态再干活（工单 B06）。重复启动 → 记日志 + 抛异常。"""
        if self.status == STATUS_RUN:
            self._log("重复启动被拦截（本就是运行态）")
            raise AlreadyRunningError("%s 已在运行，请勿重复启动" % self.code)
        self.status = STATUS_RUN
        return self._log("启动成功")

    def stop(self):
        """停机：未运行却停机同样拦。A 档"stop 后自动记录日志字符串"即此行为。"""
        if self.status != STATUS_RUN:
            self._log("重复停机被拦截（本就停机）")
            raise NotRunningError("%s 未运行，无需停机" % self.code)
        self.status = STATUS_STOP
        return self._log("停机（此刻温度 %.1f℃）" % self.temp)

    def set_temp(self, value):
        """写温度并做量程校验——把脏数据挡在对象门外。"""
        v = float(value)
        if not (TEMP_MIN <= v <= TEMP_MAX):
            self._log("越界读数 %.1f℃ 被拒绝（量程 %.0f~%.0f）" % (v, TEMP_MIN, TEMP_MAX))
            raise OutOfRangeError("%s 温度 %.1f℃ 超出量程" % (self.code, v))
        self.temp = v
        return self._log("读数刷新")

    def level(self, warn=None, danger=None):
        """按阈值给出判级；传参时临时覆盖本机阈值（不写回实例）。"""
        w = self.warn if warn is None else float(warn)
        d = self.danger if danger is None else float(danger)
        if self.temp >= d:
            return "DANGER"
        if self.temp >= w:
            return "WARN"
        return "NORMAL"

    def get_status(self):
        """任务1 点名的方法：一行内同时给回状态、读数、判级三要素。"""
        return "%s=%s %.1f℃ [%s]" % (self.code, self.status, self.temp, self.level())

    def patrol(self, warn=None, danger=None):
        """巡检台账行：状态 + 温度 + 判级（复用 get_status 的判级口径）。"""
        return "%-7s %-10s %-6s %6.1f℃ [%-7s] %s" % (
            self.code, self.kind, self.status, self.temp,
            self.level(warn, danger), self.plant_code)

    def log_text(self):
        """A 档证据：把这台设备的协作日志整段取出来。"""
        return "\n".join("    " + x for x in self.logs)

    def __str__(self):
        """任务4：print(对象) 说人话，不再输出 <...Device object at 0x7f...>。

        注意 __str__ 必须 return 字符串（工单 B05 误区），拼数字会 TypeError。
        """
        return "%s %s ｜%s｜%.1f℃ [%s]" % (
            self.code, self.kind, self.status, self.temp, self.level())

    def __repr__(self):
        """给开发者看（交互式回显）：要能一眼还原这个对象。"""
        return "Device(code=%r, kind=%r, temp=%r, warn=%r, danger=%r)" % (
            self.code, self.kind, self.temp, self.warn, self.danger)


def build_devices(items, cfg):
    """dict 清单 → Device 实例清单（演示"属性访问"与"构造参数来自配置"）。"""
    devs = []
    for d in items:
        devs.append(Device(
            code=d["code"], kind=d["kind"], temp=float(d.get("temp", 0.0)),
            warn=float(d.get("warn", cfg.warn)), danger=float(d.get("danger", cfg.danger))))
    return devs


def instance_census(devs):
    """实例独立性证据（工单 B01 误区：改 d1 不影响 d2）：逐台列 __dict__ 字段数。"""
    rows = []
    for d in devs:
        rows.append("  %-7s 实例属性 %2d 个 ｜ 类属性共享: plant_code=%s ｜ 日志 %d 行"
                    % (d.code, len(d.__dict__), d.plant_code, len(d.logs)))
    return rows


def independence_demo(devs):
    """现场证明"各实例各一份属性"：改第 1 台温度，其余读数不变。"""
    if len(devs) < 2:
        return ["实例不足 2 台，无法演示独立性"]
    before = [d.temp for d in devs]
    devs[0].set_temp(devs[0].temp + 5.0)
    after = [d.temp for d in devs]
    touched = [i for i, (b, a) in enumerate(zip(before, after)) if b != a]
    verdict = "实例隔离成立（只动了 1 台）" if touched == [0] else "隔离被破坏！"
    return ["  改前读数: %s" % before,
            "  只动 devs[0] +5℃ 后: %s" % after,
            "  实际变化实例下标: %s → %s" % (touched, verdict)]


def stamp():
    """日志/报告用时间戳（与 report.py 的生成时间同一口径）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
