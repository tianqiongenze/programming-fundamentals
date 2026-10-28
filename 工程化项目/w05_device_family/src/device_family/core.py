# -*- coding: utf-8 -*-
"""设备家族：Device 基类（沿用 W04 成果）+ 3 个子类 + 1 个组合类（has-a 反例）。

对应工单 W05《工业设备继承体系》任务 1~4：
  任务1 1 基类 + ≥2 子类 + 方法覆盖（本项目给 3 个子类，满足 B 档）
  任务2 子类新增个性化方法：PLCDevice.scan_cycle()、VFDDevice.set_freq()
  任务3 多态演示：一个 for 循环喊 start()/stop()，各子类跑各自的实现
  任务4 docstring：每个类与每个公开方法都有一行文档字符串

档位索引：
  D：`Device` 抽象基类 + `PLCDevice`/`VFDDevice`/`SensorDevice` 三个子类 + 覆盖
  C：`start()` 多态循环演示 + 全量 docstring
  B：≥3 子类；覆盖方法内用 `super()` 与父类协作
  A：`WorkStation` 用**组合**而非继承——"工位是一种设备"说不通，故不 is-a Device
     （论证正文见 docs/09-is-a设计判断.md）
"""
import inspect
from abc import ABC, abstractmethod

STATUS_RUN, STATUS_STOP = "运行", "停机"
DEFAULT_WARN, DEFAULT_DANGER = 80.0, 95.0
TEMP_MIN, TEMP_MAX = -40.0, 200.0
SAFE_FREQ = (25.0, 60.0)         # 变频器安全输出区间：低于 25Hz 散热差，高于 60Hz 超速
SAFE_SCAN_MS = (1.0, 1000.0)     # PLC 扫描周期合理区间
SCAN_STEPS = ("输入采样", "程序执行", "输出刷新")


class DeviceError(Exception):
    """设备类家族的业务异常基类。"""


class AlreadyRunningError(DeviceError):
    """重复启动：状态机挡在门外（继承自 W04 的 C 档校验）。"""


class NotRunningError(DeviceError):
    """未运行却执行运行态操作。"""


class UnsafeSettingError(DeviceError, ValueError):
    """设定值越界：既是业务错，也是 ValueError，调用方两种口径都能兜。"""


class Device(ABC):
    """设备抽象基类：编号/温度/状态 + 启停状态机 + 协作日志（W04 成果的升级版）。"""

    family = "通用设备"                        # 类属性：子类覆盖成自己的族名
    plant_code = "PLANT-A"

    def __init__(self, code, temp=0.0, warn=DEFAULT_WARN, danger=DEFAULT_DANGER):
        """基类出厂手续：子类 __init__ 必须先 super().__init__(...) 再补新料。"""
        self.code = str(code)
        self.temp = float(temp)
        self.warn = float(warn)
        self.danger = float(danger)
        self.status = STATUS_STOP
        self.logs = []
        self._log("建档出厂")

    @property
    def running(self):
        """派生只读属性：想改状态只能走 start()/stop()。"""
        return self.status == STATUS_RUN

    def _log(self, msg):
        """追加一行协作日志并返回它（方法与属性协作的最小单元）。"""
        line = "[%02d] %s %s ｜%s｜%.1f℃" % (
            len(self.logs) + 1, self.code, msg, self.status, self.temp)
        self.logs.append(line)
        return line

    def start(self):
        """启动：验状态 → 置运行 → 记日志。子类覆盖时先 `super().start()`。"""
        if self.status == STATUS_RUN:
            self._log("重复启动被拦截（本就是运行态）")
            raise AlreadyRunningError("%s 已在运行，请勿重复启动" % self.code)
        self.status = STATUS_RUN
        return self._log("%s 启动" % self.family)

    def stop(self):
        """停机：未运行却停机同样拦；子类可在覆盖里补本机专属收尾动作。"""
        if self.status != STATUS_RUN:
            self._log("重复停机被拦截（本就停机）")
            raise NotRunningError("%s 未运行，无需停机" % self.code)
        self.status = STATUS_STOP
        return self._log("停机")

    def set_temp(self, value):
        """写温度并做量程校验，脏数据不进对象。"""
        v = float(value)
        if not (TEMP_MIN <= v <= TEMP_MAX):
            self._log("越界读数 %.1f℃ 被拒绝" % v)
            raise UnsafeSettingError("%s 温度 %.1f℃ 超出量程" % (self.code, v))
        self.temp = v
        return self._log("读数刷新")

    def level(self):
        """按本机阈值给出 NORMAL / WARN / DANGER。"""
        if self.temp >= self.danger:
            return "DANGER"
        if self.temp >= self.warn:
            return "WARN"
        return "NORMAL"

    @abstractmethod
    def profile(self):
        """子类必须覆盖：一行说清这台设备的"个性"参数（多态的第二张脸）。"""

    def get_status(self):
        """状态三要素回读：状态 + 读数 + 判级，末尾带族名。"""
        return "%s=%s %.1f℃ [%s]｜%s" % (
            self.code, self.status, self.temp, self.level(), self.family)

    def patrol(self):
        """巡检台账行：公共字段走基类，个性字段走覆盖后的 profile()。"""
        return "%-9s %-11s %-4s %6.1f℃ [%-7s] %s" % (
            self.code, self.family, self.status, self.temp, self.level(), self.profile())

    def log_text(self):
        """导出这台设备的协作日志。"""
        return "\n".join("    " + x for x in self.logs)

    def __str__(self):
        """print(设备) 说人话。"""
        return "%s %s ｜%s｜%.1f℃ [%s]｜%s" % (
            self.code, self.family, self.status, self.temp, self.level(), self.profile())

    def __repr__(self):
        """开发者视角：类名 + 关键字段，一眼还原对象。"""
        return "%s(code=%r, temp=%r)" % (type(self).__name__, self.code, self.temp)


class PLCDevice(Device):
    """PLC 控制器：is-a 设备；个性是"扫描周期"（一个周期三步走）。"""

    family = "PLC 控制器"

    def __init__(self, code, temp=0.0, scan_ms=100.0, **kw):
        """先办父类手续（工单避坑第一条：漏 super() 父类属性全空），再补扫描周期。"""
        super().__init__(code, temp, **kw)
        self.scan_ms = float(scan_ms)
        self.cycle_count = 0

    def scan_cycle(self):
        """跑一个扫描周期：输入采样 → 程序执行 → 输出刷新，返回周期流水文本。"""
        if not (SAFE_SCAN_MS[0] <= self.scan_ms <= SAFE_SCAN_MS[1]):
            self._log("非法扫描周期 %.1fms 被拒绝" % self.scan_ms)
            raise UnsafeSettingError("%s 扫描周期 %.1fms 超出 %.0f~%.0fms"
                                     % (self.code, self.scan_ms,
                                        SAFE_SCAN_MS[0], SAFE_SCAN_MS[1]))
        self.cycle_count += 1
        return "%s 第%d个扫描周期 %.0fms｜%s" % (
            self.code, self.cycle_count, self.scan_ms, " → ".join(SCAN_STEPS))

    def start(self):
        """覆盖父类 start()：先让父类完成通用启动，再补 PLC 上电自检（super 协作）。"""
        base = super().start()
        return "%s ｜上电自检: %s" % (base, self.scan_cycle())

    def profile(self):
        """个性档案：扫描周期。"""
        return "扫描周期 %.0fms｜已跑 %d 周期" % (self.scan_ms, self.cycle_count)


class VFDDevice(Device):
    """变频器：is-a 设备；个性是"频率设定"（25~60Hz 安全区间）。"""

    family = "变频器"

    def __init__(self, code, temp=0.0, freq_hz=50.0, **kw):
        """父类字段先建，再用 set_freq() 落频率——校验只在 set_freq 一处。"""
        super().__init__(code, temp, **kw)
        self.freq_hz = 0.0
        self.set_freq(freq_hz)

    def set_freq(self, hz):
        """设定输出频率；越界抛 UnsafeSettingError（防电机低速过热/超速）。"""
        v = float(hz)
        if not (SAFE_FREQ[0] <= v <= SAFE_FREQ[1]):
            self._log("非法频率 %.1fHz 被拒绝（安全区间 25~60Hz）" % v)
            raise UnsafeSettingError("%s 频率 %.1fHz 超出 25~60Hz" % (self.code, v))
        self.freq_hz = v
        return self._log("频率设定 %.1fHz" % v)

    def start(self):
        """覆盖：父类启动 + 按设定频率爬升。"""
        base = super().start()
        return "%s ｜按 %.1fHz 爬升" % (base, self.freq_hz)

    def stop(self):
        """覆盖：父类停机 + 自由停车曲线收尾。"""
        base = super().stop()
        return "%s ｜频率回零（原 %.1fHz）" % (base, self.freq_hz)

    def profile(self):
        """个性档案：当前频率。"""
        return "设定频率 %.1fHz" % self.freq_hz


class SensorDevice(Device):
    """温度传感器：is-a 设备；个性是"量程 + 原始计数换算"。"""

    family = "传感器"

    def __init__(self, code, temp=0.0, range_lo=0.0, range_hi=150.0, unit="℃", **kw):
        """父类字段先建，再补量程与单位。"""
        super().__init__(code, temp, **kw)
        self.range_lo = float(range_lo)
        self.range_hi = float(range_hi)
        self.unit = str(unit)

    def read_once(self, raw_counts):
        """把 0~4095 的原始 ADC 计数换算成工程量；超量程视为脏数据。"""
        counts = int(raw_counts)
        if not (0 <= counts <= 4095):
            self._log("非法 ADC 计数 %d 被拒绝" % counts)
            raise UnsafeSettingError("%s ADC 计数 %d 越界（0~4095）" % (self.code, counts))
        span = self.range_hi - self.range_lo
        self.set_temp(self.range_lo + span * counts / 4095.0)
        return "%s ADC %4d → %.1f%s" % (self.code, counts, self.temp, self.unit)

    def calibrate(self, offset):
        """零点标定：把偏移量记进日志并回读新零点。"""
        self.range_lo = self.range_lo + float(offset)
        return self._log("零点标定 %+0.1f%s，新量程 %.1f~%.1f" % (
            float(offset), self.unit, self.range_lo, self.range_hi))

    def profile(self):
        """个性档案：量程。"""
        return "量程 %.0f~%.0f%s" % (self.range_lo, self.range_hi, self.unit)


class WorkStation:
    """产线工位：**组合**（has-a）一组设备，刻意不继承 Device。

    A 档 is-a 判断的代码化证据：把"工位是一种设备"说一遍，说不通——
    工位没有温度、不能启动、也不响应扫描周期，它只是**持有**设备并按多态调度。
    所以用成员变量 `self.devices` 而不是 `class WorkStation(Device)`。
    """

    def __init__(self, code, devices=None):
        """工位出厂只带编号和成员名单——刻意没有 temp/status 等设备字段。"""
        self.code = str(code)
        self.devices = list(devices or [])

    def add(self, dev):
        """挂载一台设备：只要求它有 start()/stop()/patrol()——鸭子类型。"""
        for need in ("start", "stop", "patrol"):
            if not hasattr(dev, need):
                raise TypeError("成员 %s 缺少 %s()，进不了统一调度名单" % (dev, need))
        self.devices.append(dev)
        return "%s 已挂载 %d 台成员" % (self.code, len(self.devices))

    def start_all(self):
        """一键全启：一句 `for d in self.devices: d.start()`——多态实战（B04）。"""
        return [d.start() for d in self.devices]

    def stop_all(self):
        """一键全停：新增设备类型不用改这里一行（开闭原则）。"""
        return [d.stop() for d in self.devices]

    def ledger(self):
        """台账：只调成员的 patrol()，工位自己不认识任何具体子类。"""
        return [d.patrol() for d in self.devices]

    def __str__(self):
        """print(工位)：报告组合了几台、各属哪些类型——自己不是设备，不报温度。"""
        return "工位 %s（组合 %d 台设备，类型: %s）" % (
            self.code, len(self.devices),
            "/".join(sorted({type(d).__name__ for d in self.devices})) or "-")


REGISTRY = {"plc": PLCDevice, "vfd": VFDDevice, "sensor": SensorDevice}
EXTRA_KEYS = ("scan_ms", "freq_hz", "range_lo", "range_hi", "unit")


def _extra_args(cls, d):
    """按子类签名挑配置键——配置多写字段不会炸，少写有默认值。"""
    known = set(inspect.signature(cls).parameters)
    return {k: d[k] for k in EXTRA_KEYS if k in known and k in d}


def from_dict(d):
    """工厂：依 type 分派到具体子类；新类型只需注册一行，调度层零改动。"""
    t = str(d.get("type", "")).lower()
    cls = REGISTRY.get(t)
    if cls is None:
        raise ValueError("未知设备类型 %r；已注册: %s"
                         % (t, "/".join(sorted(REGISTRY))))
    base = dict(code=str(d["code"]), temp=float(d.get("temp", 0.0)),
                warn=float(d.get("warn", DEFAULT_WARN)),
                danger=float(d.get("danger", DEFAULT_DANGER)))
    return cls(**base, **_extra_args(cls, d))


def subclasses(cls=Device):
    """递归列出某基类的全部具体子类（家族谱系）。"""
    found = []
    for c in cls.__subclasses__():
        found.append(c)
        found.extend(subclasses(c))
    return found


def lineage(obj):
    """继承链可读文本：按 MRO 从具体类写到 Device。"""
    return " → ".join(c.__name__ for c in type(obj).__mro__ if c is not object)
