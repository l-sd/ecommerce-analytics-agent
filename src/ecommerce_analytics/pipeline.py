from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .analysis import (
    native,
    records,
    summarize_fulfilment,
    summarize_kpi,
    summarize_sales,
    summarize_sources,
    summarize_traffic,
    summarize_users,
    valid_orders,
)

# Backwards-compatible private aliases: the helpers moved to ``analysis.common``
# so every module shares one JSON-serialisation rule, but the old names stay
# importable from here.
_records = records
_native = native

REQUIRED_COLUMNS = [
    "订单号", "日期", "渠道", "商品ID", "商品名称", "单价", "数量", "金额", "用户ID", "收货省份", "订单状态"
]
# Optional columns enrich the analysis but are not demanded of an upload: a file
# with only the eleven required columns still loads, and the modules that need
# these degrade to ``available=False`` instead of raising.
OPTIONAL_COLUMNS = [
    "商品品类", "承诺发货时效", "物流商", "承诺送达时效", "发货时间", "签收时间", "退款原因",
]
OPTIONAL_DATE_COLUMNS = ["发货时间", "签收时间"]
# 退款原因只对退款单有意义，非退款单保持空值，不做「未知」填充。
OPTIONAL_DIMENSION_COLUMNS = ["商品品类", "物流商"]
UNKNOWN = "未知"
INVALID_STATUSES = {"已退款", "已取消"}


def _select_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the required columns plus whichever optional ones the file carries.

    Missing *required* columns are still a hard error; missing optional columns
    are simply absent from the result, so :func:`clean_orders` can tell "column
    not supplied" apart from "column supplied but blank".
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    selected = list(REQUIRED_COLUMNS) + [column for column in OPTIONAL_COLUMNS if column in frame.columns]
    return frame[selected].copy()


def read_orders_stream(stream: io.IOBase, suffix: str) -> pd.DataFrame:
    """Read orders from an open file or in-memory upload.

    Split out from :func:`read_orders` so the dashboard can hand over the bytes
    of an uploaded file without first writing a temporary file to disk.
    """
    suffix = suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(stream, encoding="utf-8-sig", dtype={"订单号": "string"})
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(stream, sheet_name="订单明细", dtype={"订单号": "string"})
    else:
        raise ValueError("Input must be a CSV or Excel file.")
    return _select_columns(frame)


def read_orders(path: Path) -> pd.DataFrame:
    path = Path(path)
    with path.open("rb") as handle:
        return read_orders_stream(handle, path.suffix)


def numeric_price(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.replace("¥", "", regex=False)
    text = text.str.replace(",", "", regex=False).str.replace("元", "", regex=False).str.strip()
    return pd.to_numeric(text, errors="coerce")


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (int, float)) and 40000 < float(value) < 60000:
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(value))
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(text, errors="coerce")


def profile_raw(frame: pd.DataFrame) -> dict[str, int]:
    price = numeric_price(frame["单价"])
    quantity = pd.to_numeric(frame["数量"], errors="coerce")
    amount = pd.to_numeric(frame["金额"], errors="coerce")
    calculated = price * quantity
    checkable = amount.notna() & calculated.notna()
    return {
        "rows": int(len(frame)),
        "unique_orders": int(frame["订单号"].nunique()),
        "duplicate_rows": int(frame["订单号"].duplicated().sum()),
        "missing_dates": int(frame["日期"].isna().sum()),
        "missing_or_unparseable_prices": int(price.isna().sum()),
        "missing_quantities": int(quantity.isna().sum()),
        "zero_quantities": int((quantity == 0).sum()),
        "negative_quantities": int((quantity < 0).sum()),
        "missing_amounts": int(amount.isna().sum()),
        "checkable_amount_mismatches": int((checkable & ((amount - calculated).abs() > 0.01)).sum()),
        "missing_channels": int(frame["渠道"].isna().sum()),
        "missing_product_ids": int(frame["商品ID"].isna().sum()),
        "missing_user_ids": int(frame["用户ID"].isna().sum()),
        "missing_provinces": int(frame["收货省份"].isna().sum()),
    }


def clean_orders(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_profile = profile_raw(frame)
    supplied_optional = [column for column in OPTIONAL_COLUMNS if column in frame.columns]
    cleaned = frame.drop_duplicates(subset=["订单号"], keep="first").reset_index(drop=True).copy()
    cleaned["原始日期"] = cleaned["日期"]
    cleaned["日期"] = cleaned["日期"].map(parse_date)
    cleaned["单价"] = numeric_price(cleaned["单价"])
    cleaned["数量"] = pd.to_numeric(cleaned["数量"], errors="coerce")
    cleaned["原金额"] = pd.to_numeric(cleaned["金额"], errors="coerce")
    cleaned["金额"] = cleaned["单价"] * cleaned["数量"]
    cleaned["是否有效订单"] = ~cleaned["订单状态"].isin(INVALID_STATUSES)
    for column in ["渠道", "商品ID", "商品名称", "用户ID", "收货省份"]:
        cleaned[column] = cleaned[column].fillna(UNKNOWN)

    # Optional columns are normalised into existence so every downstream module
    # sees one shape. A column the file never carried stays null instead of
    # turning into 未知, which would read as "supplied but blank" and make the
    # availability flags lie.
    for column in OPTIONAL_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = pd.NA
    for column in OPTIONAL_DATE_COLUMNS:
        cleaned[column] = cleaned[column].map(parse_date)
    for column in ["承诺发货时效", "承诺送达时效"]:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    for column in OPTIONAL_DIMENSION_COLUMNS:
        if column in supplied_optional:
            cleaned[column] = cleaned[column].fillna(UNKNOWN)

    log = {
        "dataset_type": "synthetic",
        "raw": raw_profile,
        "rows_after_deduplication": int(len(cleaned)),
        "duplicates_removed": int(raw_profile["duplicate_rows"]),
        "dates_unparseable_after_deduplication": int(cleaned["日期"].isna().sum()),
        "prices_unparseable_after_deduplication": int(cleaned["单价"].isna().sum()),
        "amounts_unresolvable_after_recalculation": int(cleaned["金额"].isna().sum()),
        "valid_orders": int(cleaned["是否有效订单"].sum()),
        "refund_or_cancel_orders": int((~cleaned["是否有效订单"]).sum()),
        "optional_columns_supplied": supplied_optional,
        "optional_columns_absent": [column for column in OPTIONAL_COLUMNS if column not in supplied_optional],
        "orders_with_shipping_date": int(cleaned["发货时间"].notna().sum()),
        "orders_with_delivery_date": int(cleaned["签收时间"].notna().sum()),
        "refund_reasons_recorded": int(cleaned["退款原因"].notna().sum()),
        "rules": [
            "Deduplicate by order ID and keep the first row.",
            "Normalize mixed date formats; preserve unparseable dates as missing.",
            "Remove currency symbols and thousands separators from unit prices.",
            "Recalculate amount as unit price multiplied by quantity; preserve original amount.",
            "Keep refunded and cancelled rows but exclude them from valid-order KPIs.",
            "Fill missing dimensions with 未知 without inventing values.",
            "Parse shipping and delivery timestamps with the same mixed-format rules as the order date.",
            "Treat optional columns that the file does not carry as absent, not as 未知.",
        ],
    }
    return cleaned, log


def normalize_product_name(value: object) -> str:
    return re.sub(r"\s+", "", str(value)).lower()


def _tercile(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Split a numeric series into three ranked tiers labelled 1-3.

    Ranks are computed first so ``qcut`` never sees duplicate bin edges (which
    raises on tied values). With fewer than three customers every row is tier 1.
    """
    if len(series) < 3:
        return pd.Series(1, index=series.index, dtype="int64")
    ranks = series.rank(method="first", ascending=ascending)
    return pd.qcut(ranks, 3, labels=[1, 2, 3]).astype(int)


def _segment_label(row: pd.Series) -> str:
    if row["R"] == 3 and row["F"] >= 2 and row["M"] >= 2:
        return "重要价值客户"
    if row["R"] == 1 and (row["F"] >= 2 or row["M"] >= 2):
        return "重要挽留客户"
    if row["R"] >= 2 and row["F"] == 1:
        return "潜力客户"
    return "一般客户"


RFM_CUSTOMER_COLUMNS = [
    "用户ID", "last_order", "frequency", "monetary", "recency_days", "R", "F", "M", "segment",
]


def customer_rfm_table(valid: pd.DataFrame) -> pd.DataFrame:
    """Per-customer RFM table.

    Shared by the RFM summary and the RFM scatter figure so that both always
    agree on tier boundaries and segment labels.
    """
    customers = valid[(valid["用户ID"] != "未知") & valid["日期"].notna()].groupby("用户ID").agg(
        last_order=("日期", "max"), frequency=("订单号", "nunique"), monetary=("金额", "sum")
    ).reset_index()
    if customers.empty:
        return pd.DataFrame(columns=RFM_CUSTOMER_COLUMNS)
    cutoff = customers["last_order"].max()
    customers["recency_days"] = (cutoff - customers["last_order"]).dt.days
    customers["R"] = _tercile(customers["recency_days"], ascending=False)
    customers["F"] = _tercile(customers["frequency"])
    customers["M"] = _tercile(customers["monetary"])
    customers["segment"] = customers.apply(_segment_label, axis=1)
    return customers[RFM_CUSTOMER_COLUMNS]


def _rfm_segments(valid: pd.DataFrame) -> pd.DataFrame:
    customers = customer_rfm_table(valid)
    if customers.empty:
        return pd.DataFrame(columns=["segment", "customers", "gmv", "customer_share", "gmv_share"])
    summary = customers.groupby("segment").agg(customers=("用户ID", "count"), gmv=("monetary", "sum")).reset_index()
    summary["customer_share"] = summary["customers"] / summary["customers"].sum()
    summary["gmv_share"] = summary["gmv"] / summary["gmv"].sum()
    return summary.sort_values("gmv", ascending=False)


def analyze_orders(
    cleaned: pd.DataFrame,
    traffic: pd.DataFrame | None = None,
    catalog: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Analyse cleaned orders, optionally enriched by companion tables.

    ``traffic`` and ``catalog`` are optional on purpose: a reviewer who uploads
    only an order sheet still gets the original KPI/channel/monthly/product/RFM
    block, and the dimensions that need a companion table report
    ``available: False`` instead of raising.

    The nine keys that existed before the four-dimension work are preserved
    verbatim in name and meaning, so the Excel writer, the HTML report, the
    dashboard, and the existing tests keep working unchanged.
    """
    valid = valid_orders(cleaned)
    valid_gmv = float(valid["金额"].sum())

    channel = valid.groupby("渠道", dropna=False).agg(
        gmv=("金额", "sum"), orders=("订单号", "nunique"), quantity=("数量", "sum")
    ).reset_index()
    channel["aov"] = channel["gmv"] / channel["orders"]
    channel["gmv_share"] = channel["gmv"] / valid_gmv
    channel = channel.sort_values("gmv", ascending=False)

    dated = valid[valid["日期"].notna()].copy()
    dated["month"] = dated["日期"].dt.to_period("M").astype(str)
    monthly = dated.groupby("month").agg(
        gmv=("金额", "sum"), orders=("订单号", "nunique"), quantity=("数量", "sum")
    ).reset_index()
    monthly["aov"] = monthly["gmv"] / monthly["orders"]

    products = valid.assign(product_normalized=valid["商品名称"].map(normalize_product_name)).groupby(
        "product_normalized"
    ).agg(gmv=("金额", "sum"), orders=("订单号", "nunique"), quantity=("数量", "sum")).reset_index()
    products = products.sort_values("gmv", ascending=False)
    products["gmv_share"] = products["gmv"] / valid_gmv
    products["cumulative_share"] = products["gmv"].cumsum() / valid_gmv

    rfm = _rfm_segments(valid)
    source_formula = (valid["单价"] * valid["数量"]).sum()
    date_missing_gmv = valid.loc[valid["日期"].isna(), "金额"].sum()

    # --- four dimensions plus fulfilment ------------------------------------
    traffic_summary = summarize_traffic(cleaned, traffic)
    sales_summary = summarize_sales(cleaned, catalog)
    users_summary = summarize_users(cleaned)
    fulfilment_summary = summarize_fulfilment(cleaned)
    conservation = traffic_summary.get("conservation") or {}

    return {
        "notice": "Synthetic practice data; not real company transactions.",
        "definitions": {
            "valid_order": "订单状态不为已退款或已取消，且重算金额非空",
            "gmv": "有效订单的单价×数量之和",
            "aov": "有效GMV / 有效订单数",
            "rfm": "排除未知用户和缺失日期后，按最近购买、频次、金额三等分",
            "scope": "核心KPI、渠道、月度、商品、RFM 与四个维度的用户/商品指标均基于有效订单；退款与履约指标基于全量订单。",
        },
        "kpi": summarize_kpi(valid),
        "channel": _records(channel),
        "monthly": _records(monthly),
        "products_top15": _records(products.head(15)),
        "rfm": _records(rfm),
        "sources": summarize_sources(traffic, catalog),
        "traffic": traffic_summary,
        "sales": sales_summary,
        "users": users_summary,
        "fulfilment": fulfilment_summary,
        "validation_values": {
            "gmv_from_amount": round(valid_gmv, 2),
            "gmv_from_price_times_quantity": round(float(source_formula), 2),
            "channel_gmv_sum": round(float(channel["gmv"].sum()), 2),
            "monthly_gmv_sum": round(float(monthly["gmv"].sum()), 2),
            "valid_gmv_with_missing_date": round(float(date_missing_gmv), 2),
            "traffic_orders": conservation.get("traffic_orders"),
            "attributable_orders": conservation.get("attributable_orders"),
            "category_gmv_sum": round(sum(row["gmv"] for row in sales_summary["category"]), 2),
            "region_gmv_sum": round(sum(row["gmv"] for row in users_summary["region"]), 2),
            "refund_amount": sales_summary["refund"]["refund_amount"],
            "fulfilment_funnel": fulfilment_summary.get("funnel") or [],
            "sell_through_denominator": (sales_summary["sell_through"] or {}).get("on_sale_skus"),
            "sell_through_numerator": (sales_summary["sell_through"] or {}).get("sold_skus"),
        },
        "limitations": [
            "数据由固定随机种子生成，不代表任何真实企业、消费者或经营表现。",
            "流量、履约与商品主数据均为合成表；转化率、迟发率、逾期率等指标只用于演示口径的组织方式。",
            "缺失单价或数量的订单无法重算金额，相关GMV口径会排除这些记录。",
            "RFM结果仅用于演示分析流程，不应直接转化为真实营销策略。",
            "退款与履约指标使用全量订单口径，核心KPI使用有效订单口径，两者不可直接相加。",
            "数据中不含成本与实验设计，因此无法计算毛利率、ROI或因果效果。",
        ],
    }

