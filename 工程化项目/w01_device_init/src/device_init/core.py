# -*- coding: utf-8 -*-
"""核心纯函数：台账变量建模、单位换算、告警分级、f-string 台账卡（零 IO，可单测）。

工单 W01 对照：
  任务1「用不同数据类型定义 ≥6 个变量」→ Device 台账含 10 个字段、4 种类型
        （str 编号/名称/状态、int 转速/投产年、float 温度/压力/电压/功率、bool 运行）
  任务2「使用 f-string 格式化输出设备台账卡」→ card() 全篇 f-string，含对齐宽度
  任务3「完成一次单位换算」→ c_to_f（℃→℉）与 kpa_to_mpa（kPa→MPa）两处（B 档 ≥2 处）
  任务4「变量命名规范 + 关键行注释」→ snake_case，见 stylecheck.py 实测规范率
  验收 A 档「使用 input() 录入并校验（温度范围提示）」→ interactive_card(reader=…)
"""
from dataclasses import dataclass

# 换算常量：系数写常量名而非魔法数字（工单 B05 进阶优化）
FAHREN_SLOPE = 9.0 / 5.0
FAHREN_OFFSET = 32.0
KPA_PER_MPA = 1000.0
PSI_PER_MPA = 14.5038
# 录入校验区间（工单 A 档"温度范围提示"）
TEMP_MIN, TEMP_MAX = -20.0, 200.0


@dataclass(frozen=True)
class Device:
    """设备值对象（不可变）——字段来自 config/rules.yaml，代码零硬编码。

    类型覆盖 4 种：str / int / float / bool（工单 B 档要求）。
    """
    code: str                    # 设备编号：str
    name: str                    # 设备名称：str
    temp: float                  # 温度℃：float
    press_kpa: float             # 压力kPa：float
    rpm: int                     # 转速rpm：int
    status: str = "running"      # 状态文字：str
    voltage: float = 380.0       # 额定电压V：float
    power_kw: float = 7.5        # 额定功率kW：float
    install_year: int = 2024     # 投产年份：int
    running: bool = True         # 运行开关量：bool

    def __post_init__(self):
        if self.temp < -273.15:
            raise ValueError("温度低于绝对零度")
        if self.press_kpa < 0:
            raise ValueError("压力不能为负（%.2f kPa）" % self.press_kpa)
        if self.rpm < 0 or self.install_year < 1900:
            raise ValueError("转速/投产年非法")
        if self.voltage <= 0 or self.power_kw <= 0:
            raise ValueError("电压/功率必须为正")


def c_to_f(c):
    """摄氏度 → 华氏度：℉ = ℃×9/5+32（工单 B05 线性映射）。"""
    return c * FAHREN_SLOPE + FAHREN_OFFSET


def kpa_to_mpa(kpa):
    """千帕 → 兆帕：除以 1000（千进位）。"""
    return kpa / KPA_PER_MPA


def mpa_to_psi(mpa):
    """兆帕 → 磅/平方英寸（进口仪表对接用，第三处换算）。"""
    return mpa * PSI_PER_MPA


def level_of(temp, warn, danger):
    """告警分级：>=danger 停机 / >=warn 预警 / 其余正常（边界值取高等级）。"""
    if temp >= danger:
        return "danger"
    if temp >= warn:
        return "warn"
    return "normal"


def var_table(dev):
    """台账字段 → (变量名, 值, 类型名)：让"≥8 变量 / 4 种类型"可核验。"""
    pairs = [("device_code", dev.code), ("device_name", dev.name),
             ("temp_c", dev.temp), ("press_kpa", dev.press_kpa),
             ("rpm", dev.rpm), ("status", dev.status),
             ("voltage_v", dev.voltage), ("power_kw", dev.power_kw),
             ("install_year", dev.install_year), ("running", dev.running)]
    return [(k, v, type(v).__name__) for k, v in pairs]


def card(dev, cfg):
    """渲染设备台账卡——全篇 f-string，含 :>8 / :^10 / :.1f 等格式规格。"""
    f_temp = c_to_f(dev.temp)                      # 换算①  ℃ → ℉
    press_mpa = kpa_to_mpa(dev.press_kpa)           # 换算②  kPa → MPa
    press_psi = mpa_to_psi(press_mpa)               # 换算③  MPa → psi
    lv = level_of(dev.temp, cfg.warn, cfg.danger)
    run_mark = "运行中" if dev.running and dev.status == "running" else "已停机"
    return [
        f"{' 设 备 台 账 卡 ':=^44}",
        f"设备编号 : {dev.code:>12}",
        f"设备名称 : {dev.name:<12} 状态 : {dev.status}（{run_mark}）",
        f"温度     : {dev.temp:>7.1f} ℃  =  {f_temp:>6.1f} ℉   （换算①℃→℉）",
        f"压力     : {dev.press_kpa:>7.1f} kPa = {press_mpa:>5.3f} MPa"
        f" = {press_psi:>6.2f} psi（换算②③）",
        f"转速     : {dev.rpm:>7d} rpm   额定电压 : {dev.voltage:.0f} V",
        f"额定功率 : {dev.power_kw:.2f} kW  投产年份 : {dev.install_year:d}",
        f"运行开关量 running = {dev.running!r}  →  台账共 {len(vars(dev))} 个字段",
        f"告警级别 : {lv.upper():<8}（预警线 {cfg.warn:.1f}℃ / 停机线 {cfg.danger:.1f}℃）",
    ]


def parse_temp(text, prompt_value="温度"):
    """把录入文本转 float 并做范围校验；非法返回 (None, 提示语)。"""
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None, f"{prompt_value}「{text}」不是数字，请重输（例：56.5）"
    if not (TEMP_MIN <= value <= TEMP_MAX):
        return None, (f"{prompt_value} {value:.1f}℃ 超出车间允许区间 "
                      f"{TEMP_MIN:.0f}~{TEMP_MAX:.0f}℃，请重输")
    return value, ""


def parse_nonneg(text, prompt_value="压力"):
    """≥0 数值校验（录入侧复用，避免同一逻辑写两遍）。"""
    value = parse_num(text)
    if value is None or value < 0:
        return False, f"{prompt_value}「{text}」需为 ≥0 的数字，请重输"
    return True, ""


def interactive_card(cfg, reader=input):
    """A 档：input() 录入 + 校验（温度范围提示），返回台账卡行列表。

    reader 参数化：课堂用 input()，自动化测试传一个假读函数（可复现）。
    """
    def ask(prompt, default=None, checker=None):
        while True:
            raw = str(reader(prompt)).strip()
            if not raw and default is not None:
                return default
            if checker is None:
                return raw
            ok, msg = checker(raw)
            if ok:
                return raw
            print(f"  [校验未通过] {msg}")

    code = ask("设备编号（如 DEV-2026-009）：", default="DEV-MANUAL-001")
    name = ask("设备名称：", default="人工录入设备")
    temp = float(ask(f"温度℃（{TEMP_MIN:.0f}~{TEMP_MAX:.0f}）：",
                     checker=parse_temp))
    press = float(ask("压力 kPa（≥0）：", default="450", checker=parse_nonneg))
    volt = float(ask("额定电压 V：", default="380", checker=parse_nonneg))
    year = int(float(ask("投产年份：", default="2024")))
    running = ask("是否在运行（y/n）：",
                  default="y").lower() in ("y", "yes", "true", "1")
    dev = Device(code=code, name=name, temp=temp, press_kpa=press, rpm=1480,
                 status="running" if running else "stopped", voltage=volt,
                 install_year=year, running=running)
    lines = [f"[A 档交互录入] 编号 {dev.code}｜温度 {dev.temp:.1f}℃｜"
             f"校验区间 {TEMP_MIN:.0f}~{TEMP_MAX:.0f}℃"]
    return lines + card(dev, cfg)


def parse_num(text):
    """宽松转 float，失败返回 None（录入校验与统计复用）。"""
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None
