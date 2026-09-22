# E-commerce Analytics Agent

[![CI](https://github.com/l-sd/ecommerce-analytics-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/l-sd/ecommerce-analytics-agent/actions/workflows/ci.yml)

一个可复现的电商订单分析作品项目：从脏数据体检、清洗和口径确认开始，自动完成 KPI、渠道/商品分析、RFM 用户分层，并生成公式化 Excel、带图表的单文件 HTML 报告和验证记录；同一套分析逻辑同时驱动一个可交互的在线仪表盘。

> **数据声明：** 仓库中的订单全部由固定随机种子生成，是模拟练习数据，不包含真实企业、客户或交易信息。所有业务结论仅用于演示分析流程。

![报告预览](docs/report-preview.png)

## 在线 Demo

交互式仪表盘：可上传自己的 CSV/XLSX、按日期与渠道筛选、实时重算 KPI、下钻 RFM 分层。

![仪表盘预览](docs/dashboard-preview.png)

> **在线链接待填入** —— 部署到 Streamlit Community Cloud 后，请把地址替换到这一行。

本地启动方式见[快速运行](#快速运行)。

## 项目产出

- **数据体检**：检查重复、日期/金额/数量异常、维度缺失和金额不一致。
- **可追溯清洗**：保留原金额，按 `单价 × 数量` 重算金额，并记录每一条清洗规则。
- **业务分析**：有效 GMV、订单量、客单价、连带率、渠道结构、月度趋势、商品集中度和 RFM 分层。
- **四张业务图表**：时间、渠道、商品、客户四个视角，每张图对应一个具体业务问题。
- **公式化 Excel**：3,000 行清洗明细中的金额和有效订单标记由 6,000 个公式生成。
- **单文件 HTML**：图表以 base64 内嵌，无需服务端、无外部依赖即可打开。
- **结果验证**：GMV 双路径计算、渠道/月度回算、5 行抽样核对、Excel 公式逻辑审计、HTML 结构检查、图表写入与内嵌检查，共 10 项。
- **可复现性**：同一种子重新生成的数据与仓库文件逐字节一致，且由测试守住。

默认演示数据包含 **3,090 行模拟订单、3,000 个唯一订单和 90 行重复记录**。流水线可稳定识别 **46 条日期缺失**和 **59 条可核对金额不一致**记录。完整数据质量结果见 [`artifacts/demo/cleaning_log.json`](artifacts/demo/cleaning_log.json)。

## 分析结论与图表

每张图都回答一个具体问题，而不是只把数据画出来。

| 图 | 业务问题 | 本数据集上的结论 |
| --- | --- | --- |
| 图 1 · 月度 GMV 与订单数趋势 | 生意在变好还是变差？波动来自单量还是客单价？ | 峰值 2024-03（¥961,676），谷值 2024-09（¥618,237），波动 55.6%；与客单价相关系数 **0.94**、与订单数仅 **0.13**，说明**波动由客单价驱动**，而非单量 |
| 图 2 · 渠道 GMV 占比 | 钱主要从哪来？哪个渠道的单笔价值更高？ | 天猫 34.6% 为最大来源；**抖音客单价 ¥5,487 最高**，但 GMV 占比只有 14.8% |
| 图 3 · 商品 GMV 集中度 | 多少 SKU 贡献了 80% 的 GMV？ | **13 个 SKU 即达到 80%**，TOP15 累计 85.4%，第一名单品占 14.2% |
| 图 4 · RFM 分层画像 | 哪一类客户最该优先维护或挽回？ | 「重要挽留客户」48 人（GMV 27.5%）平均 **67 天**未回购，是最该召回的一层；「重要价值客户」37 人（GMV 25.4%）平均 8 天、13.8 次、人均 ¥65,819，三项均为最优 |

<table>
<tr>
<td width="50%"><img src="docs/figures/fig1_monthly_trend.png" alt="月度 GMV 与订单数趋势"></td>
<td width="50%"><img src="docs/figures/fig2_channel_structure.png" alt="渠道 GMV 占比"></td>
</tr>
<tr>
<td colspan="2"><img src="docs/figures/fig3_product_pareto.png" alt="商品 GMV 集中度"></td>
</tr>
<tr>
<td colspan="2"><img src="docs/figures/fig4_rfm_profile.png" alt="RFM 分层画像"></td>
</tr>
</table>

## 快速运行

要求 Python 3.11 或更高版本。

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"          # 分析 + 测试
python -m pip install -e ".[dev,dashboard]"  # 再加上仪表盘
```

生成可复现的模拟数据，并运行完整分析：

```bash
python -m ecommerce_analytics generate-demo --rows 3000 --seed 20240601
python -m ecommerce_analytics run --input data/synthetic_orders.csv --output artifacts/demo
```

启动交互仪表盘：

```bash
streamlit run app.py
```

## 输出文件

| 文件 | 内容 |
| --- | --- |
| `cleaned_orders.csv` | 去重、标准化并保留追溯字段的清洗明细 |
| `cleaning_log.json` | 原始数据体检和清洗规则 |
| `analysis.json` | KPI、渠道、月度、商品、RFM 和图表结论的结构化结果 |
| `ecommerce_analysis.xlsx` | 公式化明细、分析表和口径说明 |
| `report.html` | 带图表的单文件分析报告 |
| `figures/*.png` | 四张业务图表 |
| `validation.json` / `validation.md` | 自动化验证结果和人类可读记录 |

仓库提交了默认参数生成的示例产物，招聘者无需运行代码也能直接查看结果。

## 数据口径治理

每个数字都必须能回答「怎么算的、排除了什么、在哪里验证」。

| 指标 | 口径 | 验证方式 | 排除项 |
| --- | --- | --- | --- |
| 有效订单 | 订单状态不为「已退款」「已取消」，且金额可重算 | 与清洗日志计数交叉核对 | 退款、取消、金额无法重算的订单 |
| GMV | 有效订单的 `单价 × 数量` 之和 | **双路径**：与原始「金额」列分别求和，差额须为 0 | 同上 |
| 客单价 | 有效 GMV / 有效订单数 | 分母口径与「有效订单」一致 | 无 |
| 连带率 | 有效商品件数 / 有效订单数 | 与有效订单数同源 | 数量缺失的订单 |
| 渠道 / 月度 / 商品 | 在有效订单上按维度汇总 | 各维度汇总须能回算到有效 GMV | 渠道缺失记为「未知」；日期缺失不进入月度 |
| RFM | 排除未知用户与缺失日期，按最近购买、频次、金额各三等分 | 分位用 `rank` 后切分，规避并列值 | 未知用户、日期缺失、无效订单 |

**明确不计算**：UV、转化率、毛利率、ROI、复购率、因果效果。模拟订单数据不包含曝光、成本或用户行为证据，任何此类指标都只能是编造。

## 验证

```bash
pytest                                    # 111 个测试
ruff check .                              # 代码风格
```

测试覆盖：数据清洗边界、日期解析（含 Excel 序列号开区间）、输入错误处理、图表空输入与配色循环、RFM 分层画像的分层取值与配色一致性、图表行布局（宽图独占整行）、仪表盘端到端渲染、以及**数据可复现性**。

流水线自带 10 项验证，全部通过后才会以退出码 0 结束；任一项失败会以非零退出码中止，因此可以直接用于 CI 门禁。默认数据的关键断言：

- 3,090 行、3,000 个唯一订单、90 行重复；
- 46 条日期缺失、140 条单价缺失或不可解析、57 条数量缺失；
- 61 条数量为 0、284 条负数量、335 条金额缺失；
- 59 条可核对金额不一致；
- GMV 双路径差额 ¥0.00，渠道和月度汇总均能回算到有效 GMV；
- Excel 6,000 个公式无异常行，HTML 关键区块与 4 张内嵌图表完整。

### 跨平台验证

依赖在 Windows 上从零安装并跑通全流程，实测记录（含 `pip freeze`、可复现性哈希、以及修复的两个真实缺陷）见 [`docs/environment-verified.md`](docs/environment-verified.md)。

CI 在 **Ubuntu / Windows / macOS × Python 3.11 / 3.12 / 3.13** 共 9 个组合上运行 lint、测试和完整流水线，并在 Linux 上安装 `fonts-noto-cjk` 以保证图表中文不出现豆腐块。

## 项目结构

```text
app.py                 # Streamlit 交互仪表盘
src/ecommerce_analytics/
  demo_data.py         # 固定种子模拟数据
  pipeline.py          # 数据体检、清洗、KPI、渠道/商品/RFM
  visuals.py           # 四张业务图表（含跨平台中文字体回退）
  deliverables.py      # Excel、HTML 和验证记录
  cli.py               # 命令行入口
tests/                 # 清洗、日期、错误处理、图表、仪表盘、可复现性
data/                  # 提交的模拟订单及生成清单
artifacts/demo/        # 提交的示例交付物
docs/figures/          # README 引用的图表
packages.txt           # Streamlit Cloud 需要的系统包（CJK 字体）
```

## 局限

这是作品集中的流程演示，不是生产系统。模拟数据的 GMV、复购或商品表现不应被解释为真实业务成果；报告中的建议仅展示分析组织方式。项目不包含数据库、实时任务调度、权限系统或线上监控。

数据仅包含订单明细，因此无法计算 UV、转化率、毛利率、ROI 或因果增量；缺失单价或数量的订单无法重算金额，相关 GMV 口径会排除这些记录。

## License

Project code and synthetic data are available under the MIT License. Dependency notices are listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
