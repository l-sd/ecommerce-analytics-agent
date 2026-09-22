from __future__ import annotations

import base64
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .visuals import WIDE_FIGURE_FILENAMES


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_cleaned_csv(path: Path, frame: pd.DataFrame) -> None:
    export = frame.copy()
    export["日期"] = export["日期"].dt.strftime("%Y-%m-%d")
    export.to_csv(path, index=False, encoding="utf-8-sig")


DETAIL_COLUMNS = [
    "订单号", "日期", "渠道", "商品ID", "商品名称", "单价", "数量", "原金额",
    "金额_公式", "用户ID", "收货省份", "订单状态", "是否有效_公式",
    "商品品类", "承诺发货时效", "物流商", "承诺送达时效", "发货时间", "签收时间", "退款原因",
]


def detail_formula_columns() -> dict[str, str]:
    """Column letters for the formula cells, derived from the header list.

    Derived rather than hard-coded on purpose: a literal ``F``/``L`` silently
    points the formulas at the wrong cells the moment a column is inserted, and
    the Excel audit would then fail for a reason nobody can see in the diff.
    """
    letters = {name: get_column_letter(index + 1) for index, name in enumerate(DETAIL_COLUMNS)}
    return {
        "单价": letters["单价"],
        "数量": letters["数量"],
        "订单状态": letters["订单状态"],
        "金额_公式": letters["金额_公式"],
        "是否有效_公式": letters["是否有效_公式"],
    }


def amount_formula(row_index: int, letters: dict[str, str]) -> str:
    price, quantity = letters["单价"], letters["数量"]
    return f'=IF(OR({price}{row_index}="",{quantity}{row_index}=""),"",{price}{row_index}*{quantity}{row_index})'


def valid_formula(row_index: int, letters: dict[str, str]) -> str:
    status = letters["订单状态"]
    return f'=IF(OR({status}{row_index}="已退款",{status}{row_index}="已取消"),"否","是")'


def _cell(frame: pd.DataFrame, row: pd.Series, column: str):
    """Read a possibly-absent column and turn it into an Excel-friendly value."""
    if column not in frame.columns:
        return None
    value = row.get(column)
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def write_excel(path: Path, frame: pd.DataFrame, analysis: dict[str, Any], cleaning_log: dict[str, Any]) -> None:
    workbook = Workbook()
    detail = workbook.active
    detail.title = "清洗明细"
    headers = DETAIL_COLUMNS
    letters = detail_formula_columns()
    detail.append(headers)
    _style_header(detail, len(headers))

    for row_index, (_, row) in enumerate(frame.iterrows(), start=2):
        detail.append([
            str(row["订单号"]),
            row["日期"].to_pydatetime() if pd.notna(row["日期"]) else None,
            row["渠道"],
            str(row["商品ID"]),
            row["商品名称"],
            float(row["单价"]) if pd.notna(row["单价"]) else None,
            float(row["数量"]) if pd.notna(row["数量"]) else None,
            float(row["原金额"]) if pd.notna(row["原金额"]) else None,
            amount_formula(row_index, letters),
            str(row["用户ID"]),
            row["收货省份"],
            row["订单状态"],
            valid_formula(row_index, letters),
            _cell(frame, row, "商品品类"),
            _cell(frame, row, "承诺发货时效"),
            _cell(frame, row, "物流商"),
            _cell(frame, row, "承诺送达时效"),
            _cell(frame, row, "发货时间"),
            _cell(frame, row, "签收时间"),
            _cell(frame, row, "退款原因"),
        ])

    widths = [16, 12, 12, 10, 28, 11, 9, 13, 13, 11, 12, 11, 15, 12, 13, 12, 13, 12, 12, 12]
    for index, width in enumerate(widths, start=1):
        detail.column_dimensions[get_column_letter(index)].width = width
    detail.freeze_panes = "A2"
    detail.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(frame) + 1}"
    for row in detail.iter_rows(min_row=2, min_col=6, max_col=9):
        for cell in row:
            cell.number_format = '#,##0.00;[Red](#,##0.00);-'
    for cell in detail["B"][1:]:
        cell.number_format = "yyyy-mm-dd"

    traffic = analysis.get("traffic") or {}
    sales = analysis.get("sales") or {}
    users = analysis.get("users") or {}
    fulfilment = analysis.get("fulfilment") or {}
    traffic_definitions = traffic.get("definitions") or {}
    sales_definitions = sales.get("definitions") or {}
    users_definitions = users.get("definitions") or {}
    fulfilment_definitions = fulfilment.get("definitions") or {}

    summary = workbook.create_sheet("分析摘要")
    summary.append(["指标", "结果", "口径"])
    _style_header(summary, 3)
    kpi = analysis["kpi"]
    rows = [
        ["有效GMV", kpi["gmv"], analysis["definitions"]["gmv"]],
        ["有效订单数", kpi["orders"], analysis["definitions"]["valid_order"]],
        ["客单价", kpi["aov"], analysis["definitions"]["aov"]],
        ["有效客户数", kpi["customers"], "排除未知用户ID"],
        ["连带率", kpi["items_per_order"], "有效销量 / 有效订单数"],
    ]
    # 四个维度的头号指标，与核心 KPI 并列，方便一眼看到全貌。
    dimension_rows = [
        ("下单转化率", (traffic.get("rates") or {}).get("下单转化率"), traffic_definitions.get("下单转化率", "")),
        ("迟发率", (fulfilment.get("late") or {}).get("late_rate"), fulfilment_definitions.get("迟发率", "")),
        ("逾期率", (fulfilment.get("delivery") or {}).get("overdue_rate"), fulfilment_definitions.get("逾期率", "")),
        ("动销率", (sales.get("sell_through") or {}).get("sell_through_rate"), sales_definitions.get("动销率", "")),
        ("复购率", (users.get("repurchase") or {}).get("repeat_rate"), users_definitions.get("复购率", "")),
    ]
    for row in rows:
        summary.append(row)
    for name, value, definition in dimension_rows:
        summary.append([name, value if value is not None else "不可用", definition])
    summary.column_dimensions["A"].width = 20
    summary.column_dimensions["B"].width = 18
    summary.column_dimensions["C"].width = 70
    summary["B2"].number_format = '¥#,##0.00;[Red](¥#,##0.00);-'
    for row_index in range(len(rows) + 2, len(rows) + len(dimension_rows) + 2):
        summary.cell(row=row_index, column=2).number_format = "0.00%"

    _write_table_sheet(workbook, "渠道分析", analysis["channel"])
    _write_table_sheet(workbook, "月度趋势", analysis["monthly"])
    _write_table_sheet(workbook, "商品TOP15", analysis["products_top15"])
    _write_table_sheet(workbook, "RFM分层", analysis["rfm"])
    _write_table_sheet(workbook, "流量与转化", traffic.get("channel") or [])
    _write_table_sheet(workbook, "品类分析", sales.get("category") or [])
    _write_table_sheet(workbook, "品牌分析", sales.get("brand") or [])
    _write_table_sheet(workbook, "退款分析", (sales.get("refund") or {}).get("by_channel") or [])
    _write_table_sheet(workbook, "地域分布", users.get("region") or [])
    _write_table_sheet(workbook, "履约跟踪", fulfilment.get("carrier") or [])

    notes = workbook.create_sheet("口径与验证")
    notes.column_dimensions["A"].width = 26
    notes.column_dimensions["B"].width = 95
    note_rows = [
        ("数据声明", "固定随机种子生成的模拟订单数据，不代表任何真实企业或消费者。"),
        ("原始规模", f'{cleaning_log["raw"]["rows"]:,} 行；唯一订单 {cleaning_log["raw"]["unique_orders"]:,} 个。'),
        ("去重", f'删除重复订单 {cleaning_log["duplicates_removed"]} 行，保留首条记录。'),
        ("金额口径", "金额统一按单价×数量重算，原金额保留用于审计。"),
        ("有效订单", analysis["definitions"]["valid_order"]),
        ("口径范围", analysis["definitions"].get("scope", "")),
        ("可选字段", f'已提供：{"、".join(cleaning_log.get("optional_columns_supplied") or []) or "无"}；'
                     f'未提供：{"、".join(cleaning_log.get("optional_columns_absent") or []) or "无"}。'),
        ("验证", "GMV双路径、渠道回算、月度回算、流量守恒、品类/地域回算、履约单调、公式字符串、抽样和HTML结构由 validation.json 记录。"),
        ("限制", "；".join(analysis["limitations"])),
    ]
    for row in note_rows:
        notes.append(row)
    _style_header(notes, 2, row=1, values=["项目", "说明"])
    for row in notes.iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.save(path)


def _style_header(sheet, columns: int, row: int = 1, values: list[str] | None = None) -> None:
    if values:
        for index, value in enumerate(values, start=1):
            sheet.cell(row=row, column=index, value=value)
    fill = PatternFill("solid", fgColor="175C4C")
    font = Font(name="Microsoft YaHei", color="FFFFFF", bold=True)
    side = Side(style="thin", color="D7DDD9")
    for column in range(1, columns + 1):
        cell = sheet.cell(row=row, column=column)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=side)


def _write_table_sheet(workbook: Workbook, name: str, records: list[dict[str, Any]]) -> None:
    sheet = workbook.create_sheet(name)
    if not records:
        sheet.append(["暂无数据"])
        return
    columns = list(records[0].keys())
    sheet.append(columns)
    _style_header(sheet, len(columns))
    for record in records:
        sheet.append([record.get(column) for column in columns])
    for index, column in enumerate(columns, start=1):
        longest = max(len(str(column)), *(len(str(record.get(column, ""))) for record in records))
        sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 11), 30)
    sheet.freeze_panes = "A2"


FIGURE_CAPTIONS = [
    ("fig1_monthly_trend.png", "图 1 · 月度 GMV 与订单数趋势", "看时间：生意在变好还是变差，波动来自单量还是客单价。"),
    ("fig2_channel_structure.png", "图 2 · 渠道 GMV 占比", "看渠道：钱主要从哪来，哪个渠道的单笔价值更高。"),
    ("fig3_product_pareto.png", "图 3 · 商品 GMV 集中度", "看商品：多少 SKU 贡献了 80% 的 GMV，备货该向哪倾斜。"),
    ("fig4_rfm_profile.png", "图 4 · RFM 分层画像", "看客户：哪一类人最该优先维护或挽回。"),
    ("fig5_traffic_funnel.png", "图 5 · 流量与转化漏斗", "看转化：从曝光到下单，哪一层掉得最狠。"),
    ("fig6_channel_traffic_quality.png", "图 6 · 渠道流量质量", "看效率：流量多的渠道不等于赚钱的渠道。"),
    ("fig7_category_gmv.png", "图 7 · 品类 GMV 结构", "看品类：GMV 集中在哪几个类目，长尾有多长。"),
    ("fig8_fulfilment_delivery_lag.png", "图 8 · 发货时效分布", "看履约：发货时效的长尾就是迟发订单，迟发率是否越过 4% 线。"),
    ("fig9_fulfilment_trend.png", "图 9 · 迟发与逾期趋势", "看趋势：迟发率与逾期率逐月是否失控，哪个月最需要盯。"),
]

# Ratio keys that must render as percentages. Listed explicitly rather than
# guessed from the value, because several of these sit in the same table as raw
# counts and a bare float would read as a number of orders.
PERCENT_KEYS = {
    "gmv_share",
    "cumulative_share",
    "份额差",
    "曝光份额",
    "访客率",
    "加购率",
    "下单转化率",
    "全链路转化率",
    "late_rate",
    "overdue_rate",
    "refund_rate",
    "sell_through_rate",
    "repeat_rate",
    "customer_share",
}

# The RFM profile is a three-panel small multiple and the pareto chart carries a
# long rotated SKU axis, so both are roughly twice as wide as the other two. In a
# two-column grid they would be scaled down until their labels stop being legible,
# so they get a full-width row each. The set is defined in ``visuals`` because the
# dashboard has to apply the same rule.
WIDE_FIGURES = WIDE_FIGURE_FILENAMES


def _embed_figure(path: Path) -> str:
    """Base64-encode a PNG so the report stays a single offline file."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _figure_section(figures: dict[str, Path] | None) -> str:
    if not figures:
        return ""
    cards = []
    for filename, title, caption in FIGURE_CAPTIONS:
        path = figures.get(filename)
        if path is None or not Path(path).exists():
            continue
        extra = " wide" if filename in WIDE_FIGURES else ""
        cards.append(
            f'<figure class="chart{extra}"><img src="{_embed_figure(Path(path))}" alt="{html.escape(title)}">'
            f"<figcaption><b>{html.escape(title)}</b><span>{html.escape(caption)}</span></figcaption></figure>"
        )
    if not cards:
        return ""
    return f'<h2>分析图表</h2><section class="charts">{"".join(cards)}</section>'


def _dimension_section(title: str, module: dict[str, Any], body: str) -> str:
    """A dimension heading, or the reason it could not be computed.

    An unavailable dimension says *why* rather than silently rendering an empty
    table -- "no traffic table supplied" is actionable, an empty grid is not.
    """
    if not module.get("available"):
        reason = html.escape(str(module.get("reason") or "该维度数据不可用。"))
        return f"<h2>{html.escape(title)}</h2><p>{reason}</p>"
    return f"<h2>{html.escape(title)}</h2>{body}"


def write_html(
    path: Path,
    analysis: dict[str, Any],
    cleaning_log: dict[str, Any],
    figures: dict[str, Path] | None = None,
) -> None:
    kpi = analysis["kpi"]
    traffic = analysis.get("traffic") or {}
    sales = analysis.get("sales") or {}
    users = analysis.get("users") or {}
    fulfilment = analysis.get("fulfilment") or {}

    channel_rows = _table_rows(analysis["channel"], ["渠道", "gmv", "orders", "aov", "gmv_share"])
    product_rows = _table_rows(
        analysis["products_top15"][:10], ["product_normalized", "gmv", "orders", "gmv_share", "cumulative_share"]
    )
    monthly_rows = _table_rows(analysis["monthly"], ["month", "gmv", "orders", "aov"])
    max_channel = max((row["gmv"] for row in analysis["channel"]), default=1)
    bars = "".join(
        f'<div class="bar-row"><span>{html.escape(str(row["渠道"]))}</span>'
        f'<div class="track"><i style="width:{row["gmv"] / max_channel * 100:.1f}%"></i></div>'
        f'<b>¥{row["gmv"]:,.0f}</b></div>' for row in analysis["channel"]
    )
    limitations = "".join(f"<li>{html.escape(item)}</li>" for item in analysis["limitations"])
    validation_values = analysis["validation_values"]
    figures_html = _figure_section(figures)

    # --- 流量与转化 ---------------------------------------------------------
    funnel = traffic.get("funnel") or []
    exposure = funnel[0]["count"] if funnel else 0
    funnel_records = [
        {"阶段": row["stage"], "数量": row["count"], "占曝光比": (row["count"] / exposure) if exposure else None}
        for row in funnel
    ]
    rates = traffic.get("rates") or {}
    rate_line = "；".join(f"{name} {value * 100:.2f}%" for name, value in rates.items() if value is not None)
    traffic_body = (
        f"<p>{html.escape(rate_line) if rate_line else '转化率不可用。'}</p>"
        + _table(["阶段", "数量", "占曝光比"], _table_rows(funnel_records, ["阶段", "数量", "占曝光比"]))
        + "<h3>渠道流量质量</h3>"
        + _table(
            ["渠道", "曝光数", "访客数", "加购数", "下单数", "下单转化率", "GMV占比"],
            _table_rows(
                traffic.get("channel") or [],
                ["渠道", "曝光数", "访客数", "加购数", "下单数", "下单转化率", "gmv_share"],
            ),
        )
    )

    # --- 销售与商品 ---------------------------------------------------------
    sell = sales.get("sell_through") or {}
    refund = sales.get("refund") or {}
    if sell.get("available"):
        unsold = sell.get("unsold_skus") or []
        sell_line = (
            f'动销率 {sell["sell_through_rate"] * 100:.1f}%（{sell["sold_skus"]} / {sell["on_sale_skus"]} 个在售 SKU）；'
            f'滞销 {len(unsold)} 个：{"、".join(unsold) if unsold else "无"}。'
        )
    else:
        sell_line = "未提供商品主数据表，动销率不可用。"
    if refund.get("refund_rate") is not None:
        refund_line = (
            f'退款率 {refund["refund_rate"] * 100:.2f}%（{refund["refund_orders"]:,} / {refund["orders"]:,} 单），'
            f'退款金额 ¥{refund["refund_amount"]:,.2f}。'
        )
    else:
        refund_line = "退款率不可用。"
    sales_body = (
        f"<p>{html.escape(sell_line)}</p><p>{html.escape(refund_line)}</p>"
        + "<h3>品类 GMV</h3>"
        + _table(
            ["品类", "GMV", "订单数", "GMV占比"],
            _table_rows(sales.get("category") or [], ["商品品类", "gmv", "orders", "gmv_share"]),
        )
        + "<h3>品牌 GMV（TOP10）</h3>"
        + _table(
            ["品牌", "GMV", "订单数", "GMV占比"],
            _table_rows(sales.get("brand") or [], ["品牌", "gmv", "orders", "gmv_share"]),
        )
        + "<h3>渠道退款率</h3>"
        + _table(
            ["渠道", "订单数", "退款数", "退款率", "退款金额"],
            _table_rows(
                refund.get("by_channel") or [], ["渠道", "orders", "refunds", "refund_rate", "refund_amount"]
            ),
        )
    )

    # --- 用户分析 -----------------------------------------------------------
    repurchase = users.get("repurchase") or {}
    concentration = users.get("concentration") or {}
    if repurchase.get("available"):
        user_line = (
            f'复购率 {repurchase["repeat_rate"] * 100:.1f}%'
            f'（{repurchase["repeat_customers"]:,} / {repurchase["customers"]:,} 位客户）；'
            f'客均订单 {repurchase["orders_per_customer"]:.2f} 单。'
        )
    else:
        user_line = "没有已知用户的有效订单，复购指标不可用。"
    if concentration.get("available"):
        user_line += (
            f' Top 10% 客户（{concentration["top_customers"]:,} 位）贡献 {concentration["top_gmv_share"] * 100:.1f}% 的 GMV。'
        )
    users_body = (
        f"<p>{html.escape(user_line)}</p>"
        + "<h3>购买频次分布</h3>"
        + _table(
            ["购买次数", "客户数", "占比"],
            _table_rows(repurchase.get("frequency_buckets") or [], ["bucket", "customers", "share"]),
        )
        + "<h3>地域分布（TOP10）</h3>"
        + _table(
            ["省份", "GMV", "订单数", "客户数", "GMV占比"],
            _table_rows((users.get("region") or [])[:10], ["收货省份", "gmv", "orders", "customers", "gmv_share"]),
        )
    )

    # --- 履约跟踪 -----------------------------------------------------------
    late = fulfilment.get("late") or {}
    delivery = fulfilment.get("delivery") or {}
    if late.get("late_rate") is not None:
        verdict = "高于" if late.get("above_industry_line") else "低于"
        fulfil_line = (
            f'迟发率 {late["late_rate"] * 100:.2f}%（{late["late_orders"]:,} / {late["shipped_orders"]:,} 单），'
            f'{verdict}行业考核线 {late["industry_threshold"] * 100:.0f}%；'
        )
    else:
        fulfil_line = "迟发率不可用；"
    if delivery.get("overdue_rate") is not None:
        fulfil_line += (
            f'逾期率 {delivery["overdue_rate"] * 100:.2f}%'
            f'（{delivery["overdue_orders"]:,} / {delivery["delivered_orders"]:,} 单已签收），'
            f'平均签收时效 {delivery["mean_lag"]:.2f} 天。'
        )
    else:
        fulfil_line += "逾期率不可用。"
    fulfilment_body = (
        f"<p>{html.escape(fulfil_line)}</p>"
        + "<h3>物流商对比</h3>"
        + _table(
            ["物流商", "订单数", "平均发货时效", "迟发率", "已签收", "平均签收时效", "逾期率"],
            _table_rows(
                fulfilment.get("carrier") or [],
                ["物流商", "orders", "mean_ship_lag", "late_rate", "delivered_orders", "mean_delivery_lag", "overdue_rate"],
            ),
        )
    )

    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>电商订单分析报告（模拟数据）</title><style>
:root{{--ink:#17201d;--muted:#66736e;--green:#175c4c;--mint:#dfece7;--paper:#f7f8f6;--line:#d7ddd9;--amber:#b66a19}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 "Microsoft YaHei",Arial,sans-serif}}
main{{max-width:1120px;margin:auto;padding:42px 28px 64px}}header{{border-bottom:3px solid var(--green);padding-bottom:20px;margin-bottom:28px}}
h1{{font-size:34px;line-height:1.2;margin:0 0 8px}}h2{{font-size:21px;margin:34px 0 12px}}h3{{font-size:16px;margin:20px 0 8px;color:var(--green)}}p{{margin:7px 0;color:var(--muted)}}
.notice{{display:inline-block;color:#713f12;background:#fef3c7;border:1px solid #f5d98d;padding:5px 10px;border-radius:4px;font-weight:700}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:20px 0}}.kpi{{background:white;border:1px solid var(--line);padding:16px;border-radius:6px}}
.kpi span{{display:block;color:var(--muted);font-size:12px}}.kpi strong{{display:block;font-size:22px;margin-top:5px;color:var(--green)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}.panel{{background:white;border:1px solid var(--line);padding:18px;border-radius:6px}}
.bar-row{{display:grid;grid-template-columns:78px 1fr 110px;gap:10px;align-items:center;margin:10px 0}}.track{{height:12px;background:#edf1ef}}.track i{{display:block;height:100%;background:var(--green)}}
table{{width:100%;border-collapse:collapse;background:white;font-size:13px}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right}}th{{background:var(--mint);color:var(--green)}}th:first-child,td:first-child{{text-align:left}}
code{{background:#eef1ef;padding:2px 5px;border-radius:3px}}ul{{padding-left:20px;color:var(--muted)}}footer{{margin-top:34px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.chart{{margin:0;background:white;border:1px solid var(--line);padding:12px;border-radius:6px}}.chart.wide{{grid-column:1/-1}}
.chart img{{width:100%;height:auto;display:block}}.chart figcaption{{margin-top:8px;font-size:12px;color:var(--muted)}}
.chart figcaption b{{display:block;color:var(--ink);font-size:13px;margin-bottom:2px}}
@media(max-width:800px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}.charts{{grid-template-columns:1fr}}main{{padding:26px 14px}}h1{{font-size:28px}}}}
</style></head><body><main>
<header><span class="notice">模拟数据 / Synthetic data</span><h1>电商订单分析自动化报告</h1>
<p>从数据体检、清洗、KPI、流量/转化、销售/商品、用户、履约到Excel/HTML交付与验证的可复现工作流。</p></header>
<section class="kpis">
<div class="kpi"><span>有效GMV</span><strong>¥{kpi["gmv"]:,.0f}</strong></div>
<div class="kpi"><span>有效订单</span><strong>{kpi["orders"]:,}</strong></div>
<div class="kpi"><span>客单价</span><strong>¥{kpi["aov"]:,.0f}</strong></div>
<div class="kpi"><span>有效客户</span><strong>{kpi["customers"]:,}</strong></div>
<div class="kpi"><span>连带率</span><strong>{kpi["items_per_order"]:.2f}</strong></div>
</section>
{figures_html}
<section class="grid"><div class="panel"><h2>渠道GMV</h2>{bars}</div><div class="panel"><h2>数据体检</h2>
<p>原始 {cleaning_log["raw"]["rows"]:,} 行，识别重复 {cleaning_log["raw"]["duplicate_rows"]} 行、日期缺失 {cleaning_log["raw"]["missing_dates"]} 条、金额不一致 {cleaning_log["raw"]["checkable_amount_mismatches"]} 条。</p>
<p>去重后 {cleaning_log["rows_after_deduplication"]:,} 行；金额按 <code>单价 × 数量</code> 重算，并保留原金额追溯。</p>
<p>GMV双路径差额：¥{abs(validation_values["gmv_from_amount"]-validation_values["gmv_from_price_times_quantity"]):,.2f}</p></div></section>
{_dimension_section("流量与转化", traffic, traffic_body)}
{_dimension_section("销售与商品", sales, sales_body)}
{_dimension_section("用户分析", users, users_body)}
{_dimension_section("履约跟踪", fulfilment, fulfilment_body)}
<h2>渠道分析</h2>{_table(["渠道","GMV","订单数","客单价","GMV占比"], channel_rows)}
<h2>月度趋势</h2>{_table(["月份","GMV","订单数","客单价"], monthly_rows)}
<h2>商品TOP10</h2>{_table(["商品","GMV","订单数","GMV占比","累计占比"], product_rows)}
<h2>口径与局限</h2><ul>{limitations}</ul>
<footer>生成日期：{dt.date.today().isoformat()}。报告仅展示模拟数据分析流程，不构成真实经营判断。</footer>
</main></body></html>"""
    path.write_text(document, encoding="utf-8")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body = "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows)
    return f"<div style='overflow:auto'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _table_rows(records: list[dict[str, Any]], keys: list[str]) -> list[list[str]]:
    rows = []
    for record in records:
        row = []
        for key in keys:
            value = record.get(key)
            if value is None:
                formatted = "—"
            elif key in {"gmv", "aov", "refund_amount"}:
                formatted = f"¥{value:,.2f}"
            elif key in PERCENT_KEYS:
                formatted = f"{value:.1%}"
            elif isinstance(value, bool):
                formatted = "是" if value else "否"
            elif isinstance(value, int):
                formatted = f"{value:,}"
            elif isinstance(value, float):
                formatted = f"{value:,.2f}"
            else:
                formatted = str(value)
            row.append(html.escape(formatted))
        rows.append(row)
    return rows


def validate_outputs(
    output_dir: Path,
    cleaned: pd.DataFrame,
    analysis: dict[str, Any],
    cleaning_log: dict[str, Any],
    figures: dict[str, Path] | None = None,
    traffic: pd.DataFrame | None = None,
) -> dict[str, Any]:
    values = analysis["validation_values"]
    traffic_summary = analysis.get("traffic") or {}
    sales = analysis.get("sales") or {}
    users = analysis.get("users") or {}
    fulfilment = analysis.get("fulfilment") or {}
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    add("raw row count retained in log", cleaning_log["raw"]["rows"] >= len(cleaned), str(cleaning_log["raw"]["rows"]))
    add("deduplication", len(cleaned) == cleaning_log["raw"]["unique_orders"], f"{len(cleaned)} rows")
    add(
        "GMV dual calculation",
        abs(values["gmv_from_amount"] - values["gmv_from_price_times_quantity"]) <= 0.01,
        f'{values["gmv_from_amount"]} vs {values["gmv_from_price_times_quantity"]}',
    )
    add("channel roll-up", abs(values["channel_gmv_sum"] - values["gmv_from_amount"]) <= 0.01, str(values["channel_gmv_sum"]))
    add(
        "monthly roll-up with missing dates",
        abs(values["monthly_gmv_sum"] + values["valid_gmv_with_missing_date"] - values["gmv_from_amount"]) <= 0.01,
        f'{values["monthly_gmv_sum"]} + {values["valid_gmv_with_missing_date"]}',
    )

    workbook_path = output_dir / "ecommerce_analysis.xlsx"
    workbook = load_workbook(workbook_path, data_only=False, read_only=False)
    sheet = workbook["清洗明细"]
    letters = detail_formula_columns()
    amount_column = DETAIL_COLUMNS.index("金额_公式") + 1
    valid_column = DETAIL_COLUMNS.index("是否有效_公式") + 1
    formula_count = 0
    bad_formulas = []
    for row_number in range(2, sheet.max_row + 1):
        amount_cell = sheet.cell(row=row_number, column=amount_column).value
        valid_cell = sheet.cell(row=row_number, column=valid_column).value
        formula_count += 2
        if amount_cell != amount_formula(row_number, letters) or valid_cell != valid_formula(row_number, letters):
            bad_formulas.append(row_number)
    workbook.close()
    add("Excel formula audit", not bad_formulas, f"{formula_count} formulas; bad rows: {bad_formulas[:5]}")

    html_text = (output_dir / "report.html").read_text(encoding="utf-8")
    required_sections = [
        "模拟数据", "流量与转化", "销售与商品", "用户分析", "履约跟踪",
        "渠道分析", "月度趋势", "商品TOP10", "口径与局限",
    ]
    if figures:
        required_sections.append("分析图表")
    missing_sections = [section for section in required_sections if section not in html_text]
    add("HTML report structure", not missing_sections, f"missing: {missing_sections}")

    figure_paths = [Path(path) for path in (figures or {}).values() if path is not None]
    if figure_paths:
        missing_figures = [path.name for path in figure_paths if not path.exists()]
        add("chart files written", not missing_figures, f"{len(figure_paths)} charts; missing: {missing_figures}")
        embedded = html_text.count("data:image/png;base64,")
        add("charts embedded in HTML", embedded >= len(figure_paths), f"{embedded} embedded figures")

    sampled = cleaned.sample(min(5, len(cleaned)), random_state=42)
    sample_failures = 0
    for _, row in sampled.iterrows():
        expected = row["单价"] * row["数量"] if pd.notna(row["单价"]) and pd.notna(row["数量"]) else None
        actual = row["金额"]
        if expected is None:
            if pd.notna(actual):
                sample_failures += 1
        elif pd.isna(actual) or abs(float(expected) - float(actual)) > 0.01:
            sample_failures += 1
    add("sample recalculation", sample_failures == 0, f"{len(sampled)} rows checked")

    # --- 四个维度带来的守恒校验 -------------------------------------------
    # 逐行校验，比只比合计更强：合计单调并不能推出每一行都单调。
    if traffic is not None and not traffic.empty:
        monotonic = (
            bool((traffic["曝光数"] >= traffic["访客数"]).all())
            and bool((traffic["访客数"] >= traffic["加购数"]).all())
            and bool((traffic["加购数"] >= traffic["下单数"]).all())
        )
        add("traffic funnel monotonicity", monotonic, f"{len(traffic)} rows checked")
    elif traffic_summary.get("available"):
        counts = [row["count"] for row in traffic_summary.get("funnel") or []]
        add(
            "traffic funnel monotonicity",
            all(lower >= upper for lower, upper in zip(counts, counts[1:], strict=False)),
            f"totals {counts}",
        )

    conservation = traffic_summary.get("conservation")
    if conservation:
        add(
            "traffic order conservation",
            conservation.get("passed", False),
            f'{conservation.get("traffic_orders")} vs {conservation.get("attributable_orders")}',
        )

    if sales.get("category"):
        add(
            "category roll-up",
            abs(values["category_gmv_sum"] - values["gmv_from_amount"]) <= 0.01,
            f'{values["category_gmv_sum"]} vs {values["gmv_from_amount"]}',
        )

    if users.get("region"):
        add(
            "region roll-up",
            abs(values["region_gmv_sum"] - values["gmv_from_amount"]) <= 0.01,
            f'{values["region_gmv_sum"]} vs {values["gmv_from_amount"]}',
        )

    funnel = fulfilment.get("funnel") or []
    if funnel:
        counts = [row["count"] for row in funnel]
        add(
            "fulfilment funnel monotonicity",
            all(lower >= upper for lower, upper in zip(counts, counts[1:], strict=False)),
            f"下单/发货/签收 = {counts}",
        )

    sell = sales.get("sell_through") or {}
    if sell.get("available"):
        denominator = int(sell.get("on_sale_skus") or 0)
        numerator = int(sell.get("sold_skus") or 0)
        # 分母必须来自商品主数据；若退化成用明细反推，这个等式会恒等于 100%。
        add(
            "sell-through denominator from catalog",
            denominator > 0 and 0 <= numerator <= denominator,
            f"{numerator} / {denominator}",
        )

    refund_amount = float(values.get("refund_amount") or 0.0)
    cancelled_amount = float(cleaned.loc[cleaned["订单状态"] == "已取消", "金额"].sum())
    total_absolute = float(cleaned["金额"].abs().sum())
    add(
        "refund and cancel split",
        abs(total_absolute - (values["gmv_from_amount"] + refund_amount + cancelled_amount)) <= 0.01,
        f'{total_absolute} vs {values["gmv_from_amount"]} + {refund_amount} + {cancelled_amount}',
    )

    result = {
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "dataset": "synthetic",
        "checks": checks,
        "files": [
            "analysis.json",
            "cleaned_orders.csv",
            "cleaning_log.json",
            "ecommerce_analysis.xlsx",
            "report.html",
            "validation.json",
            "validation.md",
        ]
        + [path.name for path in figure_paths],
    }
    return result


def write_validation_markdown(path: Path, validation: dict[str, Any]) -> None:
    lines = ["# Validation record", "", "Dataset: synthetic practice data", ""]
    for check in validation["checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        lines.append(f'- [{mark}] {check["name"]}: {check["detail"]}')
    lines.extend(["", f'Overall status: **{validation["status"].upper()}**', ""])
    path.write_text("\n".join(lines), encoding="utf-8")
