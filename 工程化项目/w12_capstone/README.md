# 综合数据处理与项目交付（02-程序设计基础 · W12 第23次课）

> **第三种代码形态：Python 工程化项目** —— 多文件、规则外置、测试齐全、文档完备，
> 符合 GB/T 8566（软件生存周期过程）/ GB/T 9385（需求规格）/ GB/T 15532（测试规范）/
> GB/T 8567（文档编制），并以 TOGAF 四域描述架构。

## 一、30 秒跑起来
```bash
cd W12_capstone
python run.py                 # 输出到 output/ 并打印摘要
python run.py --check         # 环境自检：reportlab/wordcloud 装了没
python run.py --tier          # 打印工单 D/C/B/A 档位 + 实测规范率
python run.py --style-only    # 只做 PEP 8 规范体检（不跑业务）
python -m pytest -q           # 全量测试（应全绿）
```
答辩演示前的自检顺序：`--check` → `--style-only` → `run.py` → 拿 `output/`
里的 PDF + 词云 + run.log 讲数据流；评委问"脏数据怎么办"就翻
`output/quarantine.json`（每条坏数据都有行号、原文和归因维度）。

## 二、目录结构
```
W12_capstone/
├── run.py                  # 唯一入口（薄壳：挂 src 后调 cli.main）
├── pyproject.toml          # 包元数据 + [project.scripts] w12_capstone
├── requirements.txt        # 依赖清单
├── config/rules.yaml       # 规则外置：改配置不改代码（含采集下限/规范率线）
├── src/capstone/
│   ├── cli.py              # 控制台入口：--check/--tier/--style-only/--set
│   ├── config.py           # YAML 加载 + Settings（含 yaml_lite 兜底）
│   ├── collector.py        # ① 数据采集类 Collector（CSV > Modbus > 种子兜底）
│   ├── core.py             # 纯函数领域逻辑（解析/三维度清洗/分级/词频）
│   ├── reporter.py         # ④ 交付物生成类 Reporter（txt + PDF 图文 + 词云）
│   ├── stylecheck.py       # 规范率实测引擎（pycodestyle，缺库走内置兜底）
│   ├── io_utils.py         # CSV/JSON/原子写
│   ├── report.py           # 报告渲染
│   └── pipeline.py         # 采集 → 清洗 → 分级/词频 → 交付物 → 档位判定
├── output/                 # report.txt / deliverable.pdf / keyword_cloud.png /
│                           # clean_data.csv / quarantine.json / result.json / run.log
├── tests/
│   ├── test_core.py        # 正常/边界/异常三档
│   ├── test_config.py      # 配置加载与校验
│   └── test_tiers.py       # 工单 D/C/B/A 档位实测断言（含"档位会咬人"反证）
└── docs/                   # 01~08 全套过程文档（见下）
```

### 工单 Z 七项必备模块 → 代码位置
| 必备模块 | 落在哪 | 实测证据 |
|---|---|---|
| 数据采集（≥50 条） | `collector.Collector` | 报告"输入口径"段的通道与条数 |
| 清洗与验证（三维度） | `core.triage` | `完整性/有效性/范围` 计数 + 隔离区 |
| 异常检测（阈值规则） | `core.level` | `normal/warn/danger` 分级统计 |
| 报告生成（PDF 图文） | `reporter.Reporter.pdf` | `output/deliverable.pdf` 字节数 |
| OOP 设计（≥2 个类） | `Collector` / `Reporter` | `tests/test_tiers.py` 实例化断言 |
| 异常与日志 | `logging` → `output/run.log` | 每条采集/生成动作一行日志 |
| README | 本文件 | 运行说明 + 分工贡献表 |

## 三、过程文档（GB/T 8567 文档编制）
| 文档 | 对应标准/方法 |
|---|---|
| [01 需求规格](docs/01-需求规格.md) | GB/T 9385 |
| [02 架构说明](docs/02-架构说明.md) | TOGAF 四域 |
| [03 设计说明](docs/03-设计说明.md) | 模块设计与异常策略 |
| [04 测试计划与报告](docs/04-测试计划与报告.md) | GB/T 15532 |
| [05 运行手册](docs/05-运行手册.md) | GB/T 8566 运行过程 |
| [06 配置管理与变更记录](docs/06-配置管理与变更记录.md) | GB/T 8566 配置管理 |
| [07 ADR-001](docs/07-ADR-001-架构决策记录.md) | 架构决策记录 |
| [08 国标与TOGAF映射](docs/08-国标与TOGAF映射.md) | GB/T 8566 过程组落地 |

## 四、三种代码形态的定位
| 形态 | 目录 | 定位 |
|---|---|---|
| ① starter | `../学生代码框架/` | 学生填空起步（TODO 骨架） |
| ② 教师参考 | `../教师参考/` | 完成态参考（单文件示意） |
| ③ **工程化项目（本目录）** | `../工程化项目/` | **企业级工程结构 + 全套流程资料** |

## 五、验收口径
- `python -m pytest -q` 全绿（含 `tests/test_tiers.py` 的 D/C/B/A 档位实测断言）
- `python run.py` 生成 `output/report.txt` + PDF 图文 + 词云 + run.log
- 规范率不写常量：`run.py --style-only` 现算，报告里的数字与它同源
- 配置修改不需改代码；二次运行结果一致（采集种子固定，答辩可复现）
- 过程文档 8 份齐全，可直接用于期末答辩的材料链

## 六、分工贡献表（小组答辩必填，示例三行）
| 模块 | 责任人 | 对应工单条目 | commit 前缀 |
|---|---|---|---|
| 数据采集 `collector.py` | 组员A | 必备项① ≥50 条 | `feat(collector):` |
| 清洗与分级 `core.py` | 组员B | 必备项②③ | `feat(core):` |
| 交付物 `reporter.py` | 组员C | 必备项④（PDF 图文） | `feat(reporter):` |
| 文档与测试 `docs/` `tests/` | 组员D | 必备项⑥⑦ | `test:` / `docs:` |

> 答辩硬要求：代码上传 GitHub/Gitee，现场克隆即跑；缺 README 或不能一键运行扣 20%。
> 每人至少能讲自己那段的 **why**（个人问责制），讲不清扣个人分。
