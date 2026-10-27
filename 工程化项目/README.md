# 02-程序设计基础 · 工程化项目索引（第三种代码形态）

> 74号轮 · 每个周次一个**可运行的 Python 工程化项目**：多文件分层、规则外置、pytest 三档测试、8 份国标/TOGAF 过程文档，共 12 个周次全覆盖。

## 一、三种代码形态的定位

| 形态 | 目录 | 定位 |
|---|---|---|
| ① starter | `../学生代码框架/` | 学生填空起步（TODO 骨架） |
| ② 教师参考 | `../教师参考/` | 完成态参考（单文件示意） |
| ③ **工程化项目（本目录）** | `工程化项目/` | **企业级工程结构 + 全套流程资料** |

## 二、项目清单（12 个）

| # | 工单 | 周次 | 目录 | 核心功能 |
|---|---|---|---|---|
| 1 | 02-W01 | W01 第1次课 | `W01_device_init/` | 设备参数初始化系统 |
| 2 | 02-W02 | W02 第3次课 | `W02_alarm_engine/` | 设备多级告警判定引擎 |
| 3 | 02-W03 | W03 第5次课 | `W03_patrol_loop/` | 多设备巡检循环模拟 |
| 4 | 02-W04 | W04 第7次课 | `W04_device_model/` | 设备对象建模 |
| 5 | 02-W05 | W05 第9次课 | `W05_device_family/` | 设备继承体系 |
| 6 | 02-W06 | W06 第11次课 | `W06_robust_collector/` | 健壮工业数据采集 |
| 7 | 02-W07 | W07 第13次课 | `W07_packet_parser/` | 工业报文解析器 |
| 8 | 02-W08 | W08 第15次课 | `W08_data_fileio/` | 工业数据文件处理 |
| 9 | 02-W09 | W09 第17次课 | `W09_text_report/` | 故障文本词频报告 |
| 10 | 02-W10 | W10 第19次课 | `W10_daily_report/` | 质量日报生成 |
| 11 | 02-W11 | W11 第21次课 | `W11_telemetry_upload/` | 虚拟设备采数与云端上报 |
| 12 | 02-W12 | W12 第23次课 | `W12_capstone/` | 综合数据处理与项目交付 |

## 三、每个项目的结构（23 个文件）

```
<slug>/
├── README.md               # 三种形态定位 + 目录 + 验收口径
├── pyproject.toml          # 包元数据 + pytest 配置
├── requirements.txt        # 依赖清单
├── .gitignore
├── run.py                  # 唯一入口（argparse CLI）
├── config/rules.yaml       # 规则外置：改配置不改代码
├── src/<pkg>/
│   ├── config.py           # YAML 加载 + Settings（含 yaml_lite 零依赖兜底）
│   ├── core.py             # 纯函数领域逻辑（零 IO，可单测）
│   ├── io_utils.py         # CSV/JSON/原子写
│   ├── report.py           # 报告渲染
│   └── pipeline.py         # load → process → evaluate → report 编排
├── tests/
│   ├── test_core.py        # 正常 / 边界 / 异常三档
│   └── test_config.py      # 配置加载与校验
└── docs/                   # 8 份过程文档
    ├── 01-需求规格.md       # GB/T 9385
    ├── 02-架构说明.md       # TOGAF 四域
    ├── 03-设计说明.md
    ├── 04-测试计划与报告.md  # GB/T 15532
    ├── 05-运行手册.md
    ├── 06-配置管理与变更记录.md  # GB/T 8566 配置管理
    ├── 07-ADR-001-架构决策记录.md
    └── 08-国标与TOGAF映射.md  # GB/T 8566 过程组落地表

## 四、30 秒跑起来

```bash
cd <slug>
python run.py                 # 输出 output/report.txt + result.json
python -m pytest -q           # 全量测试（应全绿）
```

## 五、验收口径

- `python -m pytest -q` 全绿；`python run.py` 生成 `output/report.txt`
- 配置修改不需改代码；二次运行结果一致（随机种子固定）
- 8 份过程文档齐全，可直接构成期末答辩的材料链

## 六、生成与重放

生成器：`_docx_work/eng/`（`eng_gen.py` + `eng_specs.py` + `specs_01/02/03/05.py`）
重放：`python _docx_work/eng/eng_gen.py --build`　验证：`python _docx_work/eng/verify_projects.py`

> 本索引由生成器自动产出（改 `specs_*.py` 后重跑 `eng_gen.py --build`，索引同步更新）。
