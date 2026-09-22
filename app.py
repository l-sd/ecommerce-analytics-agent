"""Interactive dashboard for the e-commerce order analysis pipeline.

Run it locally::

    pip install -e ".[dashboard]"
    streamlit run app.py

The dashboard opens the committed demo dataset by default and also accepts a CSV
or XLSX upload with the same eleven columns, so a reviewer can put their own file
through the same cleaning rules and 口径 without touching the command line.

Everything shown is recomputed from the filtered rows -- the KPI cards, the four
charts and the RFM drill-down all come from the same :func:`analyze_orders` call
the CLI uses, so the numbers here match ``artifacts/demo/analysis.json`` whenever
no filter is applied.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

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
from ecommerce_analytics.pipeline import (
    analyze_orders,
    clean_orders,
    customer_rfm_table,
    read_orders,
    read_orders_stream,
)

DEFAULT_DATASET = PROJECT_ROOT / "data" / "synthetic_orders.csv"
UPLOAD_TYPES = ["csv", "xlsx"]
CHART_ORDER = ["monthly_trend", "channel_structure", "product_pareto", "rfm_profile"]
CHART_TITLES = {
    "monthly_trend": "图 1 · 月度 GMV 与订单数趋势",
    "channel_structure": "图 2 · 渠道 GMV 占比",
    "product_pareto": "图 3 · 商品 GMV 集中度",
    "rfm_profile": "图 4 · RFM 分层画像",
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
def analyse(cleaned: pd.DataFrame) -> dict:
    return analyze_orders(cleaned)


@st.cache_data(show_spinner=False)
def render_charts(analysis: dict, cleaned: pd.DataFrame) -> dict[str, dict]:
    """Render the four charts to PNG bytes. Cached on the filtered inputs."""
    return visuals.render_all_figures(analysis, cleaned)


# --- formatting helpers ------------------------------------------------------


def money(value: float | None) -> str:
    return "—" if value is None else f"¥{value:,.0f}"


def decimal(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:,.{digits}f}"


def percent(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}%"


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
    return (
        f"{summary['channel_count']} 个渠道中，{summary['top_channel']} 占比最高"
        f"（{percent(summary['top_channel_share'])}）；"
        f"单笔价值最高的是 {summary['best_aov_channel']}（{money(summary['best_aov'])}）。"
    )


def pareto_takeaway(summary: dict) -> str:
    if summary.get("skus_for_80_percent") is None:
        return f"TOP{summary['top_n']} 商品累计占比 {percent(summary['top_n_cumulative_share'])}，未触及 80% 线。"
    return (
        f"**{summary['skus_for_80_percent']} 个 SKU** 即贡献 80% 的 GMV；"
        f"第一名单品占 {percent(summary['top1_share'])}。"
    )


def rfm_takeaway(summary: dict) -> str:
    return (
        f"{summary['customer_count']} 位客户分为 {summary['segment_count']} 层；"
        f"GMV 贡献最高的是**{summary['top_gmv_segment']}**"
        f"（{summary['top_gmv_customers']} 人，占 {percent(summary['top_gmv_share'])}）。"
    )


TAKEAWAYS = {
    "monthly_trend": monthly_takeaway,
    "channel_structure": channel_takeaway,
    "product_pareto": pareto_takeaway,
    "rfm_profile": rfm_takeaway,
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


# --- page --------------------------------------------------------------------


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
            help="需包含订单号、日期、渠道、商品ID、商品名称、单价、数量、金额、用户ID、收货省份、订单状态。",
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
        else:
            cleaned, cleaning_log = load_from_disk(str(DEFAULT_DATASET))
            st.info("当前使用仓库内置的模拟数据。上传文件可替换。")

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

    analysis = analyse(filtered)
    kpi = analysis["kpi"]

    columns = st.columns(5)
    columns[0].metric("有效 GMV", money(kpi["gmv"]))
    columns[1].metric("有效订单", f"{kpi['orders']:,}")
    columns[2].metric("客单价", money(kpi["aov"]))
    columns[3].metric("有效客户", f"{kpi['customers']:,}")
    columns[4].metric("连带率", decimal(kpi["items_per_order"]))

    # --- charts --------------------------------------------------------------
    st.subheader("分析图表")
    charts = render_charts(analysis, filtered)
    # Wide charts get a row to themselves; see visuals.WIDE_FIGURE_KEYS.
    for row in visuals.chart_rows(CHART_ORDER):
        chart_columns = st.columns(len(row))
        for column, key in zip(chart_columns, row, strict=True):
            with column:
                st.image(charts[key]["png"], width="stretch")
                st.markdown(f"**{CHART_TITLES[key]}**")
                st.caption(TAKEAWAYS[key](charts[key]["summary"]))

    # --- tables --------------------------------------------------------------
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

    # --- RFM drill-down ------------------------------------------------------
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

    # --- limitations ---------------------------------------------------------
    st.subheader("口径与局限")
    for item in analysis["limitations"]:
        st.markdown(f"- {item}")
    st.caption(
        "本页仅演示分析流程，模拟数据的结果不应被解读为真实业务成果。"
    )


if __name__ == "__main__":
    main()
