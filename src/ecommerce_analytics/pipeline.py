from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = [
    "订单号", "日期", "渠道", "商品ID", "商品名称", "单价", "数量", "金额", "用户ID", "收货省份", "订单状态"
]
INVALID_STATUSES = {"已退款", "已取消"}


def read_orders(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"订单号": "string"})
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, sheet_name="订单明细", dtype={"订单号": "string"})
    else:
        raise ValueError("Input must be a CSV or Excel file.")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    return frame[REQUIRED_COLUMNS].copy()


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
    cleaned = frame.drop_duplicates(subset=["订单号"], keep="first").reset_index(drop=True).copy()
    cleaned["原始日期"] = cleaned["日期"]
    cleaned["日期"] = cleaned["日期"].map(parse_date)
    cleaned["单价"] = numeric_price(cleaned["单价"])
    cleaned["数量"] = pd.to_numeric(cleaned["数量"], errors="coerce")
    cleaned["原金额"] = pd.to_numeric(cleaned["金额"], errors="coerce")
    cleaned["金额"] = cleaned["单价"] * cleaned["数量"]
    cleaned["是否有效订单"] = ~cleaned["订单状态"].isin(INVALID_STATUSES)
    for column in ["渠道", "商品ID", "商品名称", "用户ID", "收货省份"]:
        cleaned[column] = cleaned[column].fillna("未知")

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
        "rules": [
            "Deduplicate by order ID and keep the first row.",
            "Normalize mixed date formats; preserve unparseable dates as missing.",
            "Remove currency symbols and thousands separators from unit prices.",
            "Recalculate amount as unit price multiplied by quantity; preserve original amount.",
            "Keep refunded and cancelled rows but exclude them from valid-order KPIs.",
            "Fill missing dimensions with 未知 without inventing values.",
        ],
    }
    return cleaned, log


def normalize_product_name(value: object) -> str:
    return re.sub(r"\s+", "", str(value)).lower()


def _rfm_segments(valid: pd.DataFrame) -> pd.DataFrame:
    customers = valid[(valid["用户ID"] != "未知") & valid["日期"].notna()].groupby("用户ID").agg(
        last_order=("日期", "max"), frequency=("订单号", "nunique"), monetary=("金额", "sum")
    ).reset_index()
    if customers.empty:
        return pd.DataFrame(columns=["segment", "customers", "gmv", "customer_share", "gmv_share"])
    cutoff = customers["last_order"].max()
    customers["recency_days"] = (cutoff - customers["last_order"]).dt.days
    r_rank = customers["recency_days"].rank(method="first", ascending=False)
    f_rank = customers["frequency"].rank(method="first")
    m_rank = customers["monetary"].rank(method="first")
    customers["R"] = pd.qcut(r_rank, 3, labels=[1, 2, 3]).astype(int)
    customers["F"] = pd.qcut(f_rank, 3, labels=[1, 2, 3]).astype(int)
    customers["M"] = pd.qcut(m_rank, 3, labels=[1, 2, 3]).astype(int)

    def label(row: pd.Series) -> str:
        if row["R"] == 3 and row["F"] >= 2 and row["M"] >= 2:
            return "重要价值客户"
        if row["R"] == 1 and (row["F"] >= 2 or row["M"] >= 2):
            return "重要挽留客户"
        if row["R"] >= 2 and row["F"] == 1:
            return "潜力客户"
        return "一般客户"

    customers["segment"] = customers.apply(label, axis=1)
    summary = customers.groupby("segment").agg(customers=("用户ID", "count"), gmv=("monetary", "sum")).reset_index()
    summary["customer_share"] = summary["customers"] / summary["customers"].sum()
    summary["gmv_share"] = summary["gmv"] / summary["gmv"].sum()
    return summary.sort_values("gmv", ascending=False)


def analyze_orders(cleaned: pd.DataFrame) -> dict[str, Any]:
    valid = cleaned[cleaned["是否有效订单"] & cleaned["金额"].notna()].copy()
    valid_gmv = float(valid["金额"].sum())
    valid_orders = int(valid["订单号"].nunique())
    quantity = float(valid["数量"].sum())
    customers = int(valid.loc[valid["用户ID"] != "未知", "用户ID"].nunique())

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

    return {
        "notice": "Synthetic practice data; not real company transactions.",
        "definitions": {
            "valid_order": "订单状态不为已退款或已取消，且重算金额非空",
            "gmv": "有效订单的单价×数量之和",
            "aov": "有效GMV / 有效订单数",
            "rfm": "排除未知用户和缺失日期后，按最近购买、频次、金额三等分",
        },
        "kpi": {
            "gmv": round(valid_gmv, 2),
            "orders": valid_orders,
            "aov": round(valid_gmv / valid_orders, 2) if valid_orders else None,
            "quantity": round(quantity, 2),
            "customers": customers,
            "items_per_order": round(quantity / valid_orders, 2) if valid_orders else None,
        },
        "channel": _records(channel),
        "monthly": _records(monthly),
        "products_top15": _records(products.head(15)),
        "rfm": _records(rfm),
        "validation_values": {
            "gmv_from_amount": round(valid_gmv, 2),
            "gmv_from_price_times_quantity": round(float(source_formula), 2),
            "channel_gmv_sum": round(float(channel["gmv"].sum()), 2),
            "monthly_gmv_sum": round(float(monthly["gmv"].sum()), 2),
            "valid_gmv_with_missing_date": round(float(date_missing_gmv), 2),
        },
        "limitations": [
            "数据由固定随机种子生成，不代表任何真实企业、消费者或经营表现。",
            "数据仅包含订单明细，无法计算UV、转化率、毛利率、ROI或因果效果。",
            "缺失单价或数量的订单无法重算金额，相关GMV口径会排除这些记录。",
            "RFM结果仅用于演示分析流程，不应直接转化为真实营销策略。",
        ],
    }


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = frame.replace({np.nan: None}).to_dict(orient="records")
    return [{key: _native(value) for key, value in row.items()} for row in records]


def _native(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value

