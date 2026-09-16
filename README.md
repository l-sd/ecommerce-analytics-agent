# E-commerce Analytics Agent

一个可复现的电商订单分析作品项目：从脏数据体检、清洗和口径确认开始，自动完成 KPI、渠道/商品分析、RFM 用户分层，并生成公式化 Excel、单文件 HTML 报告和验证记录。

> **数据声明：** 仓库中的订单全部由固定随机种子生成，是模拟练习数据，不包含真实企业、客户或交易信息。

![报告预览](docs/report-preview.png)

## 项目产出

- 数据体检：检查重复、日期/金额/数量异常、维度缺失和金额不一致。
- 可追溯清洗：保留原金额，按 `单价 × 数量` 重算金额，并记录清洗规则。
- 业务分析：有效 GMV、订单量、客单价、渠道结构、月度趋势、商品集中度和 RFM 分层。
- 公式化 Excel：3,000 行清洗明细中的金额和有效订单标记由 6,000 个公式生成。
- 单文件 HTML：无需服务端即可打开，展示核心指标、渠道、月份和商品分析。
- 结果验证：GMV 双路径计算、渠道/月度回算、5 行抽样核对、Excel 公式逻辑审计和 HTML 结构检查。

默认演示数据包含 **3,090 行模拟订单、3,000 个唯一订单和 90 行重复记录**。流水线可稳定识别 **46 条日期缺失**和 **59 条可核对金额不一致**记录。完整数据质量结果见 [`artifacts/demo/cleaning_log.json`](artifacts/demo/cleaning_log.json)。

## 快速运行

要求 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

生成可复现的模拟数据：

```powershell
python -m ecommerce_analytics generate-demo --rows 3000 --seed 20240601
```

运行完整分析：

```powershell
python -m ecommerce_analytics run --input data/synthetic_orders.csv --output artifacts/demo
```

## 输出文件

| 文件 | 内容 |
| --- | --- |
| `cleaned_orders.csv` | 去重、标准化并保留追溯字段的清洗明细 |
| `cleaning_log.json` | 原始数据体检和清洗规则 |
| `analysis.json` | KPI、渠道、月度、商品和 RFM 结构化结果 |
| `ecommerce_analysis.xlsx` | 公式化明细、分析表和口径说明 |
| `report.html` | 可独立打开的单文件分析报告 |
| `validation.json` / `validation.md` | 自动化验证结果和人类可读记录 |

仓库提交了默认参数生成的示例产物，招聘者无需运行代码也能直接查看结果。

## 分析口径

- 有效订单：订单状态不为“已退款”或“已取消”，且金额可重算。
- GMV：有效订单的 `单价 × 数量` 之和。
- 客单价：有效 GMV / 有效订单数。
- RFM：排除未知用户和缺失日期后，按最近购买、频次、金额三等分。
- 不计算：UV、转化率、毛利率、ROI 或真实业务增量，因为模拟订单数据不包含相应证据。

## 验证

```powershell
python -m unittest discover -s tests -v
```

默认数据的关键断言：

- 3,090 行、3,000 个唯一订单、90 行重复；
- 46 条日期缺失、140 条单价缺失或不可解析、57 条数量缺失；
- 61 条数量为 0、284 条负数量、335 条金额缺失；
- 59 条可核对金额不一致；
- 渠道和月度汇总能够回算到有效 GMV；
- Excel 公式格式统一，HTML 关键区块完整。

## 项目结构

```text
src/ecommerce_analytics/
  demo_data.py       # 固定种子模拟数据
  pipeline.py        # 数据体检、清洗、KPI、渠道/商品/RFM
  deliverables.py    # Excel、HTML和验证记录
  cli.py             # 命令行入口
tests/               # 可复现性和交付物测试
data/                # 提交的模拟订单及生成清单
artifacts/demo/      # 提交的示例交付物
```

## 局限

这是作品集中的流程演示，不是生产系统。模拟数据的 GMV、复购或商品表现不应被解释为真实业务成果；报告中的建议仅展示分析组织方式。项目不包含数据库、实时任务调度、权限系统或线上监控。

## License

Project code and synthetic data are available under the MIT License. Dependency notices are listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

