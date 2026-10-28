# 09 is-a 设计判断：为什么"工位"不用继承（工单 W05 优(A) 档交付物）

> 项目：设备继承体系 · 结论先行：**能用"是一种（is-a）"说出口的才继承，
> 只能说"有（has-a）"的必须用组合。** 本项目里 `PLC 是一种设备` → 继承；
> `工位有一堆设备` → 组合。代码位置：`src/device_family/core.py`
> （`Device`/`PLCDevice`/`VFDDevice`/`SensorDevice`/`WorkStation`）。

## 1. 判断口径（三问法）

| 问题 | PLC 控制器 | 产线工位 |
|---|---|---|
| ① 能否说出"X **是一种** Y"？ | "PLC 是一种设备" ✅ | "工位是一种设备" ❌（说不通） |
| ② 它有没有父类的全部字段？ | 编号、温度、状态都有 ✅ | 工位**没有温度**，也无所谓启停状态 ❌ |
| ③ 替换成父类型后 Liskov 还成立吗？ | `List[Device]` 里放 PLC 完全正常 ✅ | 把工位当设备调用 `scan_cycle()` 会当场炸 ❌ |

三问里有两问答"否"，就说明真实关系是**持有**而不是**是一种**——
所以 `WorkStation` 写成 `class WorkStation:`（不带父类），
用 `self.devices` 这个**成员列表**去装设备。

实测证据（`python run.py` 报告『is-a 判断』分节，机器数出来的，不是手写）：

```
issubclass(PLCDevice, Device)    = True   → PLC 是一种设备：继承
issubclass(WorkStation, Device)  = False  → 工位不是一种设备：组合
WorkStation 有 temp 属性吗        = False  → 没有温度可谈，所以不能继承 Device
```

## 2. 如果硬用继承会发生什么（反面推演）

假设当初写成 `class WorkStation(Device)`，会连锁引出四个坑：

1. **被迫继承用不上的字段**：`__init__` 里得给工位编造一个 `temp`、`warn`、
   `danger`。数值填多少都没物理意义，只能填 0.0 骗过校验——这就是"假数据"。
2. **被迫实现没有意义的抽象方法**：`Device.profile()` 是抽象方法，工位要么
   写"量程 0~0℃"这种废话，要么把抽象方法降级成可选——基类约束当场失效
   （报告『抽象基类约束』分节实测：抽象基类不可实例化，abc 生效）。
3. **状态机语义被污染**：`start()` 会给工位打出"通用设备 启动｜0.0℃"的日志，
   巡检台账里混进一行不是设备的记录，`patrol()` 的口径就再也不可信。
4. **子类越加越歪**：以后再加"车间""班组""厂区"，全都 `Device` 的子类，
   继承树长成一棵"什么都是设备"的圣诞树；想改一次 `Device.start()`
   要评估几十条调用链——这正是工单 B01"为了复用而硬凑关系是误用"的现场。

## 3. 组合版本长什么样（正面写法）

```python
class WorkStation:                      # 注意：没有 (Device)
    """产线工位：has-a 一组设备。"""
    def __init__(self, code, devices=None):
        self.code = str(code)
        self.devices = list(devices or [])   # 组合：成员放进列表

    def start_all(self):
        """一键全启：一句 for d in self.devices: d.start() —— 多态实战。"""
        return [d.start() for d in self.devices]
```

关键收益：**工位代码里 0 处 `isinstance`**。中控屏"一键全启"按钮只要
`station.start_all()`，PLC 自己跑扫描自检、变频器自己按频率爬升、传感器
自己刷新量程——调用方完全不认识具体类型（工单 B04 多态的本来面目）。
新增第 5 种设备（比如机械手）时，`WorkStation` 一行都不用改。

`add()` 里保留了**鸭子类型检查**（有没有 `start/stop/patrol`），
这就是 Python 版的多态契约：不要求"是不是 Device 的子孙"，
只要求"能不能响应这三个消息"。想要更硬的约束可以再包一层 `abc.ABC`，
但别为了约束而继承。

## 4. 那"传感器"为什么可以继承？

传感器 `is-a` 设备：它有编号、有温度、要启停、要上报判级，
父类的 `start/stop/set_temp/level/__str__` 它**全部用得上**，
自己只新增 `read_once()`（ADC 计数换算）和 `calibrate()`（零点标定）两个个性方法，
`profile()` 覆盖成"量程 0~150℃"。覆盖 `start()` 时用
`super().start()` 借父类实现再补自己的动作（报告『super() 协作证据』实测
3 处 super() 协作），这就是 B 档要的"覆盖方法内用 super() 协作"。

## 5. 一张表记住选型

| 关系 | 中文口令 | 写法 | 本项目实例 |
|---|---|---|---|
| is-a（是一种） | "X 是一种 Y" | `class X(Y)` 继承 | `PLCDevice/VFDDevice/SensorDevice → Device` |
| has-a（有一个） | "X 里装着 Y" | `self.ys = [...]` 组合 | `WorkStation.devices` |
| uses-a（用一下） | "X 的方法收 Y 当参数" | 形参传入 | `from_dict(d)`、`_extra_args(cls, d)` |

> 经验法则：**继承拿不准时，先写组合。** 组合改起来只动一个类；
> 继承改起来要动整棵树——"选错方向后期重构很痛"（工单 B01 进阶原话）。
