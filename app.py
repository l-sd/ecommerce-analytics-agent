"""Interactive dashboard for the e-commerce order analysis pipeline.

Run it locally::

    pip install -e ".[dashboard]"
    streamlit run app.py

The dashboard opens the committed demo dataset by default and also accepts a CSV
or XLSX upload with the same eleven required columns, so a reviewer can put their
own file through the same cleaning rules and 口径 without touching the command
line.

Everything shown is recomputed from the filtered rows -- the KPI cards, the nine
charts and the RFM drill-down all come from the same :func:`analyze_orders` call
the CLI uses, so the numbers here match ``artifacts/demo/analysis.json`` whenever
no filter is applied.

Layout note: the five tabs mirror the four industry analysis dimensions plus
fulfilment. ``st.tabs`` renders every tab body on each rerun (inactive tabs are
hidden with CSS, not skipped), so nothing here is lazy -- a reviewer can see
everything without clicking, and ``AppTest`` can assert on all of it.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import matplotlib

# Force a headless backend before anything imports pyplot. Streamlit Cloud has no
# display, and a Windows machine with a partial Tk install raises on the first
# figure; visuals._get_pyplot() enforces the same thing, this just does it early.
matplotlib.use("Agg")

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ecommerce_analytics import visuals
from ecommerce_analytics.demo_data import read_catalog, read_traffic
from ecommerce_analytics.pipeline import (
    analyze_orders,
    clean_orders,
    customer_rfm_table,
    read_orders,
    read_orders_stream,
)

DEFAULT_DATASET = PROJECT_ROOT / "data" / "synthetic_orders.csv"
DEFAULT_TRAFFIC = PROJECT_ROOT / "data" / "synthetic_traffic.csv"
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "synthetic_products.csv"
UPLOAD_TYPES = ["csv", "xlsx"]

# Reading order per tab. The wide charts (pareto, RFM) still get a row of their
# own -- visuals.chart_rows applies the same rule here as in the HTML report.
TAB_CHARTS: dict[str, list[str]] = {
    "overview": ["monthly_trend", "channel_structure"],
    "traffic": ["traffic_funnel", "channel_traffic_quality"],
    "sales": ["category_gmv", "product_pareto"],
    "users": ["rfm_profile"],
    "fulfilment": ["fulfilment_delivery_lag", "fulfilment_trend"],
}
CHART_ORDER = [key for keys in TAB_CHARTS.values() for key in keys]
CHART_TITLES = {
    "monthly_trend": "图 1 · 月度 GMV 与订单数趋势",
    "channel_structure": "图 2 · 渠道 GMV 占比",
    "product_pareto": "图 3 · 商品 GMV 集中度",
    "rfm_profile": "图 4 · RFM 分层画像",
    "traffic_funnel": "图 5 · 流量与转化漏斗",
    "channel_traffic_quality": "图 6 · 渠道流量质量",
    "category_gmv": "图 7 · 品类 GMV 结构",
    "fulfilment_delivery_lag": "图 8 · 发货时效分布",
    "fulfilment_trend": "图 9 · 迟发与逾期趋势",
}
SEGMENT_ORDER = ["重要价值客户", "重要挽留客户", "潜力客户", "一般客户"]


# --- data loading ------------------------------------------------------------


@st.cache_data(show_spinner=False)
def load_from_disk(path: str) -> tuple[pd.DataFrame, dict]:
    """Clean the bundled dataset. Cached on the file path."""
    return clean_orders(read_orders(Path(path)))


@st.cache_data(show_spinner=False)
def load_from_upload(payload: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
    """Clean an uploaded file. Cached on the raw bytes, so re-runs are free."""
    return clean_orders(read_orders_stream(io.BytesIO(payload), Path(filename).suffix))


@st.cache_data(show_spinner=False)
def load_traffic(path: str) -> pd.DataFrame | None:
    """Load the companion traffic table, or ``None`` when it is not present."""
    candidate = Path(path)
    return read_traffic(candidate) if candidate.exists() else None


@st.cache_data(show_spinner=False)
def load_catalog(path: str) -> pd.DataFrame | None:
    """Load the companion product master, or ``None`` when it is not present."""
    candidate = Path(path)
    return read_catalog(candidate) if candidate.exists() else None


@st.cache_data(show_spinner=False)
def analyse(cleaned: pd.DataFrame, traffic: pd.DataFrame | None, catalog: pd.DataFrame | None) -> dict:
    return analyze_orders(cleaned, traffic=traffic, catalog=catalog)


@st.cache_data(show_spinner=False)
def render_charts(analysis: dict, cleaned: pd.DataFrame) -> dict[str, dict]:
    """Render every chart to PNG bytes. Cached on the filtered inputs."""
    return visuals.render_all_figures(analysis, cleaned)


# --- formatting helpers ------------------------------------------------------


def money(value: float | None) -> str:
    return "—" if value is None else f"¥{value:,.0f}"


def decimal(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:,.{digits}f}"


def percent(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}%"


def dig(node: Any, *path: str) -> Any:
    """Read a nested dict field, returning ``None`` the moment the path breaks.

    Every dimension can be unavailable (no traffic table, no catalogue), so the
    KPI row must not assume a key exists.
    """
    current = node
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def log_value(log: dict, *path: str, default: int = 0) -> int:
    """Read a nested cleaning-log field, falling back to 0 when absent."""
    node: object = log
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return int(node) if isinstance(node, (int, float)) else default


def monthly_takeaway(summary: dict) -> str:
    if summary.get("driver") is None:
        return "样本月份不足，无法判断波动来自单量还是客单价。"
    return (
        f"峰值 {summary['peak_month']}（{money(summary['peak_gmv'])}），"
        f"谷值 {summary['trough_month']}（{money(summary['trough_gmv'])}），"
        f"波动 {percent(summary['swing_ratio'])}；"
        f"相关系数显示波动主要由**{summary['driver']}**解释。"
    )


def channel_takeaway(summary: dict) -> str:
    if summary.get("top_channel") is None:
        return "当前筛选下没有可用渠道数据。"
    return (
        f"{summary['channel_count']} 个渠道中，{summary['top_channel']} 占比最高"
        f"（{percent(summary['top_channel_share'])}）；"
        f"单笔价值最高的是 {summary['best_aov_channel']}（{money(summary['best_aov'])}）。"
    )


def pareto_takeaway(summary: dict) -> str:
    if summary.get("top_n") is None:
        return "当前筛选下没有可用商品数据。"
    if summary.get("skus_for_80_percent") is None:
        return f"TOP{summary['top_n']} 商品累计占比 {percent(summary['top_n_cumulative_share'])}，未触及 80% 线。"
    return (
        f"**{summary['skus_for_80_percent']} 个 SKU** 即贡献 80% 的 GMV；"
        f"第一名单品占 {percent(summary['top1_share'])}。"
    )


def rfm_takeaway(summary: dict) -> str:
    if summary.get("customer_count") is None:
        return "当前筛选下没有可参与 RFM 分层的客户。"
    return (
        f"{summary['customer_count']} 位客户分为 {summary['segment_count']} 层；"
        f"GMV 贡献最高的是**{summary['top_gmv_segment']}**"
        f"（{summary['top_gmv_customers']} 人，占 {percent(summary['top_gmv_share'])}）。"
    )


def traffic_funnel_takeaway(summary: dict) -> str:
    if summary.get("order_rate") is None:
        return "未提供流量表，转化率不可用。"
    return (
        f"曝光 {summary['exposure']:,} → 访客 {summary['visitors']:,} → 加购 {summary['carts']:,} "
        f"→ 下单 {summary['orders']:,}；"
        f"访客→下单 **{percent(summary['order_rate'], 2)}**，全链路 {percent(summary['full_rate'], 2)}。"
    )


def channel_traffic_takeaway(summary: dict) -> str:
    if summary.get("best_channel") is None:
        return "未提供流量表，渠道流量质量不可用。"
    text = (
        f"转化率最高的是**{summary['best_channel']}**（{percent(summary['best_conversion'], 2)}）"
    )
    if summary.get("worst_conversion"):
        gap = summary["best_conversion"] / summary["worst_conversion"]
        text += (
            f"，最低的是 {summary['worst_channel']}（{percent(summary['worst_conversion'], 2)}）"
            f"，差距约 {gap:.1f} 倍"
        )
    return text + "。"


def category_takeaway(summary: dict) -> str:
    if summary.get("top_category") is None:
        return "当前筛选下没有可用品类数据。"
    return (
        f"**{summary['top_category']}** 贡献 {percent(summary['top_share'])} 的 GMV，"
        f"前三类目合计 {percent(summary['top3_share'])}；"
        f"最低的是 {summary['lowest_category']}（{percent(summary['lowest_share'])}）。"
    )


def delivery_lag_takeaway(summary: dict) -> str:
    if summary.get("late_rate") is None:
        return "未提供履约字段，发货时效不可用。"
    verdict = "高于" if summary.get("above_industry_line") else "低于"
    return (
        f"平均发货时效 {decimal(summary['mean_lag'])} 天"
        f"（中位 {decimal(summary['median_lag'], 1)} 天，最长 {summary['max_lag']} 天）；"
        f"迟发率 **{percent(summary['late_rate'], 2)}**，{verdict}行业考核线 "
        f"{percent(summary['industry_threshold'], 0)}。"
    )


def fulfilment_trend_takeaway(summary: dict) -> str:
    if summary.get("mean_late_rate") is None:
        return "未提供履约字段，趋势不可用。"
    return (
        f"{summary['months']} 个月中，迟发率均值 {percent(summary['mean_late_rate'], 2)}，"
        f"峰值出现在 **{summary['peak_late_month']}**（{percent(summary['peak_late_rate'], 2)}）；"
        f"逾期率均值 {percent(summary['mean_overdue_rate'], 2)}。"
    )


TAKEAWAYS = {
    "monthly_trend": monthly_takeaway,
    "channel_structure": channel_takeaway,
    "product_pareto": pareto_takeaway,
    "rfm_profile": rfm_takeaway,
    "traffic_funnel": traffic_funnel_takeaway,
    "channel_traffic_quality": channel_traffic_takeaway,
    "category_gmv": category_takeaway,
    "fulfilment_delivery_lag": delivery_lag_takeaway,
    "fulfilment_trend": fulfilment_trend_takeaway,
}


# --- filtering ---------------------------------------------------------------


def apply_filters(
    cleaned: pd.DataFrame,
    date_range: tuple | None,
    channels: list[str],
) -> tuple[pd.DataFrame, bool]:
    """Return the filtered frame and whether a date window was actually applied.

    An empty channel selection means "no channel restriction" rather than "no
    rows": clearing a multi-select is easy to do by accident, and an empty
    dashboard is a worse outcome than a slightly looser filter. The caller says
    so in a caption.

    Rows with an unparseable date are kept only when no date window is active, so
    the default view still matches ``artifacts/demo/analysis.json``.
    """
    filtered = cleaned
    if channels:
        filtered = filtered[filtered["渠道"].isin(channels)]

    date_filter_active = False
    if date_range is not None:
        start, end = date_range
        dated = cleaned["日期"].dropna()
        full_window = not dated.empty and (start, end) == (dated.min().date(), dated.max().date())
        if not full_window:
            date_filter_active = True
            lower = pd.Timestamp(start)
            upper = pd.Timestamp(end) + pd.Timedelta(days=1)
            filtered = filtered[filtered["日期"].between(lower, upper, inclusive="left")]
    return filtered.copy(), date_filter_active


def apply_traffic_filters(
    traffic: pd.DataFrame | None,
    date_range: tuple | None,
    channels: list[str],
    date_filter_active: bool,
) -> pd.DataFrame | None:
    """Filter the traffic table with exactly the same rules as the orders.

    Both sides have to move together: ``sum(下单数)`` only reconciles with the
    order table while the two are narrowed identically.
    """
    if traffic is None or traffic.empty:
        return traffic
    filtered = traffic
    if channels:
        filtered = filtered[filtered["渠道"].isin(channels)]
    if date_filter_active and date_range is not None:
        start, end = date_range
        lower = pd.Timestamp(start)
        upper = pd.Timestamp(end) + pd.Timedelta(days=1)
        filtered = filtered[filtered["日期"].between(lower, upper, inclusive="left")]
    return filtered.copy()


# --- page --------------------------------------------------------------------


def _metric_row(columns, items: list[tuple[str, str]]) -> None:
    for column, (label, value) in zip(columns, items, strict=True):
        column.metric(label, value)


def _render_chart_group(charts: dict, keys: list[str]) -> None:
    for row in visuals.chart_rows(keys):
        chart_columns = st.columns(len(row))
        for column, key in zip(chart_columns, row, strict=True):
            with column:
                st.image(charts[key]["png"], width="stretch")
                st.markdown(f"**{CHART_TITLES[key]}**")
                st.caption(TAKEAWAYS[key](charts[key]["summary"]))


def _unavailable(module: dict | None, label: str) -> bool:
    """Render the reason a dimension is empty, and say whether to stop."""
    if module and module.get("available"):
        return False
    reason = (module or {}).get("reason") or f"{label}不可用。"
    st.info(reason)
    return True


def _table_or_note(rows: list[dict], note: str) -> None:
    st.dataframe(pd.DataFrame(rows) if rows else pd.DataFrame({"提示": [note]}), hide_index=True)


def main() -> None:
    st.set_page_config(page_title="电商订单分析仪表盘", layout="wide")
    st.title("电商订单分析仪表盘")
    st.caption(
        "模拟练习数据，由固定随机种子生成，不含任何真实企业、客户或交易信息。"
        "清洗、KPI 口径与 CLI 完全一致。"
    )

    # --- sidebar -------------------------------------------------------------
    with st.sidebar:
        st.header("数据源")
        upload = st.file_uploader(
            "上传订单明细（CSV / XLSX）",
            type=UPLOAD_TYPES,
            help="需包含订单号、日期、渠道、商品ID、商品名称、单价、数量、金额、用户ID、收货省份、订单状态。"
            "商品品类、物流商、承诺时效、发货时间、签收时间、退款原因为可选列，缺失时对应维度会自动跳过。",
        )

        if upload is not None:
            try:
                cleaned, cleaning_log = load_from_upload(upload.getvalue(), upload.name)
            except ValueError as error:
                st.error(f"无法读取该文件：{error}")
                st.stop()
            except Exception as error:  # noqa: BLE001 - surfaced to the user verbatim
                st.error(f"解析失败：{error}")
                st.stop()
            st.success(f"已载入 {upload.name}")
            traffic, catalog = None, None
            st.caption("上传文件不带流量表与商品主数据表，流量与动销率维度会自动跳过。")
        else:
            cleaned, cleaning_log = load_from_disk(str(DEFAULT_DATASET))
            traffic = load_traffic(str(DEFAULT_TRAFFIC))
            catalog = load_catalog(str(DEFAULT_CATALOG))
            st.info("当前使用仓库内置的模拟数据。上传文件可替换。")
            sources = []
            if traffic is not None:
                sources.append(f"流量表 {len(traffic):,} 行")
            if catalog is not None:
                sources.append(f"商品主数据 {len(catalog):,} 行")
            if sources:
                st.caption("伴随表：" + "；".join(sources))

        if cleaned.empty:
            st.error("清洗后没有可用订单，请检查文件内容。")
            st.stop()

        st.divider()
        st.header("筛选")

        dated = cleaned["日期"].dropna()
        if dated.empty:
            st.warning("数据中没有可解析的日期，日期筛选不可用。")
            date_range = None
        else:
            date_range = st.date_input(
                "日期范围",
                value=(dated.min().date(), dated.max().date()),
                min_value=dated.min().date(),
                max_value=dated.max().date(),
            )
            if isinstance(date_range, tuple) and len(date_range) != 2:
                date_range = None

        all_channels = sorted(cleaned["渠道"].dropna().unique().tolist())
        channels = st.multiselect(
            "渠道",
            options=all_channels,
            default=all_channels,
            help="清空选择表示不限制渠道，仍按全部渠道展示。",
        )

        st.divider()
        st.header("数据体检")
        # Label the stage each count comes from: the raw profile and the
        # post-deduplication frame disagree (46 vs 45 missing dates), and showing
        # both numbers unlabelled reads like a contradiction.
        health = {
            "原始行数": log_value(cleaning_log, "raw", "rows"),
            "去重后行数": log_value(cleaning_log, "rows_after_deduplication"),
            "重复记录": log_value(cleaning_log, "duplicates_removed"),
            "日期缺失（去重后）": log_value(cleaning_log, "dates_unparseable_after_deduplication"),
            "金额不一致（原始体检）": log_value(cleaning_log, "raw", "checkable_amount_mismatches"),
            "退款或取消（去重后）": log_value(cleaning_log, "refund_or_cancel_orders"),
        }
        st.dataframe(
            pd.DataFrame({"项目": list(health), "数量": list(health.values())}),
            hide_index=True,
        )
        rules = cleaning_log.get("rules") or []
        if rules:
            with st.expander(f"清洗规则（{len(rules)} 条）"):
                for rule in rules:
                    st.markdown(f"- {rule}")

    # --- filtered view -------------------------------------------------------
    filtered, date_filter_active = apply_filters(cleaned, date_range, channels)
    if filtered.empty:
        st.warning("当前筛选条件下没有订单，请放宽筛选。")
        st.stop()

    if not channels:
        st.caption("未选择渠道，已按全部渠道展示。")
    if date_filter_active:
        st.caption("已按日期范围筛选，日期缺失的订单不参与统计。")
    else:
        missing_dates = int(filtered["日期"].isna().sum())
        if missing_dates:
            st.caption(f"当前为全量数据，其中 {missing_dates} 条订单日期缺失（计入 GMV，不进入月度趋势）。")

    filtered_traffic = apply_traffic_filters(traffic, date_range, channels, date_filter_active)
    analysis = analyse(filtered, filtered_traffic, catalog)
    kpi = analysis["kpi"]
    charts = render_charts(analysis, filtered)

    traffic_summary = analysis.get("traffic") or {}
    sales_summary = analysis.get("sales") or {}
    users_summary = analysis.get("users") or {}
    fulfilment_summary = analysis.get("fulfilment") or {}

    overview_tab, traffic_tab, sales_tab, users_tab, fulfilment_tab = st.tabs(
        ["概览", "流量与转化", "销售与商品", "用户", "履约跟踪"]
    )

    # --- 概览 ----------------------------------------------------------------
    with overview_tab:
        st.subheader("核心 KPI")
        _metric_row(st.columns(5), [
            ("有效 GMV", money(kpi["gmv"])),
            ("有效订单", f"{kpi['orders']:,}"),
            ("客单价", money(kpi["aov"])),
            ("有效客户", f"{kpi['customers']:,}"),
            ("连带率", decimal(kpi["items_per_order"])),
        ])

        st.subheader("四大维度与履约")
        _metric_row(st.columns(5), [
            ("下单转化率", percent(dig(analysis, "traffic", "rates", "下单转化率"), 2)),
            ("动销率", percent(dig(analysis, "sales", "sell_through", "sell_through_rate"))),
            ("复购率", percent(dig(analysis, "users", "repurchase", "repeat_rate"))),
            ("迟发率", percent(dig(analysis, "fulfilment", "late", "late_rate"), 2)),
            ("逾期率", percent(dig(analysis, "fulfilment", "delivery", "overdue_rate"), 2)),
        ])
        st.caption("前五项为有效订单口径；迟发率分母为应发订单，逾期率分母为已签收订单。")

        _render_chart_group(charts, TAB_CHARTS["overview"])

        left, right = st.columns([1, 1])
        with left:
            st.subheader("渠道明细")
            channel_rows = [
                {
                    "渠道": row["渠道"],
                    "GMV": money(row["gmv"]),
                    "订单数": row["orders"],
                    "客单价": money(row["aov"]),
                    "GMV占比": percent(row["gmv_share"]),
                }
                for row in analysis["channel"]
            ]
            st.dataframe(pd.DataFrame(channel_rows), hide_index=True)
        with right:
            st.subheader("RFM 分层")
            rfm_rows = [
                {
                    "分层": row["segment"],
                    "客户数": row["customers"],
                    "GMV": money(row["gmv"]),
                    "客户占比": percent(row["customer_share"]),
                    "GMV占比": percent(row["gmv_share"]),
                }
                for row in analysis["rfm"]
            ]
            st.dataframe(pd.DataFrame(rfm_rows), hide_index=True)

    # --- 流量与转化 ----------------------------------------------------------
    with traffic_tab:
        if not _unavailable(traffic_summary, "流量与转化"):
            rates = traffic_summary.get("rates") or {}
            _metric_row(st.columns(4), [
                ("访客率", percent(rates.get("访客率"), 2)),
                ("加购率", percent(rates.get("加购率"), 2)),
                ("下单转化率", percent(rates.get("下单转化率"), 2)),
                ("全链路转化率", percent(rates.get("全链路转化率"), 3)),
            ])
            _render_chart_group(charts, TAB_CHARTS["traffic"])

            funnel = traffic_summary.get("funnel") or []
            exposure = funnel[0]["count"] if funnel else 0
            st.subheader("漏斗明细")
            _table_or_note(
                [
                    {
                        "阶段": row["stage"],
                        "数量": f"{row['count']:,}",
                        "占曝光比": percent(row["count"] / exposure if exposure else None, 2),
                    }
                    for row in funnel
                ],
                "无漏斗数据",
            )

            st.subheader("渠道流量质量")
            st.caption("份额差 = GMV 份额 − 曝光份额；正数说明该渠道的流量比它的曝光更值钱。")
            _table_or_note(
                [
                    {
                        "渠道": row["渠道"],
                        "曝光数": f"{row['曝光数']:,}",
                        "访客数": f"{row['访客数']:,}",
                        "下单数": f"{row['下单数']:,}",
                        "下单转化率": percent(row["下单转化率"], 2),
                        "GMV占比": percent(row["gmv_share"]),
                        "曝光份额": percent(row["曝光份额"]),
                        "份额差": percent(row["份额差"]),
                    }
                    for row in traffic_summary.get("channel") or []
                ],
                "无渠道流量数据",
            )

            conservation = traffic_summary.get("conservation") or {}
            if conservation:
                mark = "一致" if conservation.get("passed") else "不一致"
                st.caption(
                    f"守恒校验：流量表下单数合计 {conservation.get('traffic_orders'):,}，"
                    f"订单表中渠道与日期可归属的订单 {conservation.get('attributable_orders'):,}，{mark}。"
                )

    # --- 销售与商品 ----------------------------------------------------------
    with sales_tab:
        _metric_row(st.columns(4), [
            ("有效 GMV", money(kpi["gmv"])),
            ("商品件数", decimal(kpi["quantity"], 0)),
            ("动销率", percent(dig(analysis, "sales", "sell_through", "sell_through_rate"))),
            ("退款率", percent(dig(analysis, "sales", "refund", "refund_rate"), 2)),
        ])

        sell = sales_summary.get("sell_through") or {}
        if sell.get("available"):
            unsold = sell.get("unsold_skus") or []
            st.caption(
                f"动销率 = {sell['sold_skus']} 个有销量 SKU / {sell['on_sale_skus']} 个在售 SKU（分母来自商品主数据）；"
                f"滞销 {len(unsold)} 个：{'、'.join(unsold) if unsold else '无'}。"
            )
        else:
            st.info(sell.get("reason") or "未提供商品主数据表，动销率不可用。")

        _render_chart_group(charts, TAB_CHARTS["sales"])

        left, right = st.columns([1, 1])
        with left:
            st.subheader("品类 GMV")
            _table_or_note(
                [
                    {
                        "品类": row["商品品类"],
                        "GMV": money(row["gmv"]),
                        "订单数": row["orders"],
                        "客单价": money(row["aov"]),
                        "GMV占比": percent(row["gmv_share"]),
                    }
                    for row in sales_summary.get("category") or []
                ],
                "未提供商品品类列",
            )
        with right:
            st.subheader("品牌 GMV（TOP10）")
            _table_or_note(
                [
                    {
                        "品牌": row["品牌"],
                        "GMV": money(row["gmv"]),
                        "订单数": row["orders"],
                        "GMV占比": percent(row["gmv_share"]),
                    }
                    for row in sales_summary.get("brand") or []
                ],
                "未提供商品主数据表",
            )

        refund = sales_summary.get("refund") or {}
        st.subheader("渠道退款率")
        st.caption("分母为该渠道的全量订单数（含退款与取消），与核心 KPI 的有效订单口径不同。")
        _table_or_note(
            [
                {
                    "渠道": row["渠道"],
                    "订单数": row["orders"],
                    "退款数": row["refunds"],
                    "退款率": percent(row["refund_rate"], 2),
                    "退款金额": money(row["refund_amount"]),
                }
                for row in refund.get("by_channel") or []
            ],
            "无退款数据",
        )

        if refund.get("reasons"):
            st.subheader("退款原因分布")
            _table_or_note(
                [
                    {"退款原因": row["退款原因"], "订单数": row["orders"], "占比": percent(row["share"])}
                    for row in refund["reasons"]
                ],
                "未提供退款原因列",
            )

    # --- 用户 ----------------------------------------------------------------
    with users_tab:
        repurchase = users_summary.get("repurchase") or {}
        concentration = users_summary.get("concentration") or {}
        _metric_row(st.columns(4), [
            ("有效客户", f"{kpi['customers']:,}"),
            ("复购率", percent(repurchase.get("repeat_rate"))),
            ("客均订单", decimal(repurchase.get("orders_per_customer"))),
            ("Top10%客户GMV占比", percent(concentration.get("top_gmv_share"))),
        ])

        _render_chart_group(charts, TAB_CHARTS["users"])

        left, right = st.columns([1, 1])
        with left:
            st.subheader("购买频次分布")
            _table_or_note(
                [
                    {"购买次数": row["bucket"], "客户数": row["customers"], "占比": percent(row["share"])}
                    for row in repurchase.get("frequency_buckets") or []
                ],
                "无已知用户的有效订单",
            )
        with right:
            st.subheader("首单月份分布")
            st.caption("窗口内首单即为新客；数据没有更早历史，因此不能区分真实新客与老客。")
            _table_or_note(
                [
                    {"首单月份": row["month"], "新客数": row["new_customers"]}
                    for row in users_summary.get("acquisition") or []
                ],
                "日期不可用",
            )

        st.subheader("地域分布")
        _table_or_note(
            [
                {
                    "省份": row["收货省份"],
                    "GMV": money(row["gmv"]),
                    "订单数": row["orders"],
                    "客户数": row["customers"],
                    "客单价": money(row["aov"]),
                    "GMV占比": percent(row["gmv_share"]),
                }
                for row in users_summary.get("region") or []
            ],
            "未提供收货省份列",
        )

        st.subheader("RFM 客户下钻")
        valid = filtered[filtered["是否有效订单"] & filtered["金额"].notna()]
        customers = customer_rfm_table(valid)
        if customers.empty:
            st.info("当前筛选下没有可参与 RFM 分层的客户（需要有效订单、已知用户且日期可解析）。")
        else:
            present = [segment for segment in SEGMENT_ORDER if segment in set(customers["segment"])]
            choice = st.selectbox("选择分层", options=["全部", *present])
            subset = customers if choice == "全部" else customers[customers["segment"] == choice]
            st.caption(f"共 {len(subset)} 位客户。金额为该客户在有效订单上的累计消费。")

            detail = pd.DataFrame(
                {
                    "用户ID": subset["用户ID"],
                    "最近购买": subset["last_order"].dt.strftime("%Y-%m-%d"),
                    "距今(天)": subset["recency_days"],
                    "购买次数": subset["frequency"],
                    "累计金额": subset["monetary"].round(2),
                    "分层": subset["segment"],
                }
            ).sort_values("累计金额", ascending=False)
            st.dataframe(detail, hide_index=True)
            st.download_button(
                "下载客户明细 CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name="rfm_customers.csv",
                mime="text/csv",
            )

    # --- 履约跟踪 ------------------------------------------------------------
    with fulfilment_tab:
        if not _unavailable(fulfilment_summary, "履约跟踪"):
            late = fulfilment_summary.get("late") or {}
            delivery = fulfilment_summary.get("delivery") or {}
            ship = fulfilment_summary.get("ship_lag") or {}
            _metric_row(st.columns(5), [
                ("平均发货时效", f"{decimal(ship.get('mean'))} 天"),
                ("迟发率", percent(late.get("late_rate"), 2)),
                ("行业考核线", percent(late.get("industry_threshold"), 0)),
                ("平均签收时效", f"{decimal(delivery.get('mean_lag'))} 天"),
                ("逾期率", percent(delivery.get("overdue_rate"), 2)),
            ])
            if late.get("above_industry_line"):
                st.warning(
                    f"迟发率 {percent(late.get('late_rate'), 2)} 高于行业常设的 "
                    f"{percent(late.get('industry_threshold'), 0)} 考核线，"
                    f"{late.get('late_orders'):,} / {late.get('shipped_orders'):,} 单迟发。"
                )

            _render_chart_group(charts, TAB_CHARTS["fulfilment"])

            st.subheader("物流商对比")
            st.caption("按迟发率升序；平均发货时效与迟发率均按全量订单口径计算。")
            _table_or_note(
                [
                    {
                        "物流商": row["物流商"],
                        "订单数": row["orders"],
                        "平均发货时效": decimal(row["mean_ship_lag"]),
                        "迟发率": percent(row["late_rate"], 2),
                        "已签收": row["delivered_orders"],
                        "平均签收时效": decimal(row["mean_delivery_lag"]),
                        "逾期率": percent(row["overdue_rate"], 2),
                    }
                    for row in fulfilment_summary.get("carrier") or []
                ],
                "未提供物流商列",
            )

            st.subheader("履约漏斗")
            funnel = fulfilment_summary.get("funnel") or []
            if funnel:
                st.caption(
                    " → ".join(f"{row['stage']} {row['count']:,} 单" for row in funnel)
                    + f"；单调性校验{'通过' if fulfilment_summary.get('funnel_monotonic') else '未通过'}。"
                )

            st.subheader("月度迟发与逾期")
            _table_or_note(
                [
                    {
                        "月份": row["month"],
                        "已发货": row["shipped_orders"],
                        "迟发率": percent(row["late_rate"], 2),
                        "已签收": row["delivered_orders"],
                        "逾期率": percent(row["overdue_rate"], 2),
                    }
                    for row in fulfilment_summary.get("monthly") or []
                ],
                "日期不可用",
            )

    # --- limitations ---------------------------------------------------------
    st.subheader("口径与局限")
    for item in analysis["limitations"]:
        st.markdown(f"- {item}")
    st.caption("本页仅演示分析流程，模拟数据的结果不应被解读为真实业务成果。")


if __name__ == "__main__":
    main()
