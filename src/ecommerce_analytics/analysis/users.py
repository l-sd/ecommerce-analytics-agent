"""用户维度：复购、获客节奏、贡献集中度、地域分布。

The customer definition matches :func:`pipeline.customer_rfm_table` -- valid
orders, a known user ID -- so the RFM tiers and the numbers here never
contradict each other on the same screen.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .common import UNKNOWN, has_dimension, records, safe_ratio, valid_orders

DEFINITIONS = {
    "有效客户数": "有效订单中出现过、且用户ID已知的去重客户数。",
    "复购客户数": "在有效订单中下单次数 ≥ 2 的客户数。",
    "复购率": "复购客户数 / 有效客户数。",
    "客均订单数": "有效订单数 / 有效客户数。",
    "首单月份": "客户在观察窗口内第一次有效下单的月份；窗口之前没有历史，因此不能区分真实新客与老客。",
    "Top10%客户GMV占比": "按客户累计金额降序，取前 10% 客户的金额之和 / 有效 GMV。",
}

_FREQUENCY_BUCKETS = [(1, 1, "1 单"), (2, 2, "2 单"), (3, 4, "3-4 单"), (5, 10**9, "5 单及以上")]


def _customer_table(valid: pd.DataFrame) -> pd.DataFrame:
    customers = valid[valid["用户ID"] != UNKNOWN].groupby("用户ID").agg(
        orders=("订单号", "nunique"),
        monetary=("金额", "sum"),
        first_order=("日期", "min"),
    ).reset_index()
    return customers


def _repurchase(customers: pd.DataFrame) -> dict[str, Any]:
    if customers.empty:
        return {"available": False, "reason": "没有已知用户的有效订单。"}
    total = len(customers)
    repeat = int((customers["orders"] >= 2).sum())
    buckets = []
    for low, high, label in _FREQUENCY_BUCKETS:
        count = int(((customers["orders"] >= low) & (customers["orders"] <= high)).sum())
        buckets.append({"bucket": label, "customers": count, "share": safe_ratio(count, total)})
    return {
        "available": True,
        "reason": None,
        "customers": total,
        "repeat_customers": repeat,
        "repeat_rate": safe_ratio(repeat, total),
        "orders_per_customer": safe_ratio(customers["orders"].sum(), total),
        "frequency_buckets": buckets,
    }


def _acquisition(customers: pd.DataFrame) -> list[dict[str, Any]]:
    dated = customers[customers["first_order"].notna()]
    if dated.empty:
        return []
    grouped = (
        dated.assign(month=dated["first_order"].dt.to_period("M").astype(str))
        .groupby("month")
        .size()
        .reset_index(name="new_customers")
    )
    return records(grouped)


def _concentration(customers: pd.DataFrame, total_gmv: float) -> dict[str, Any]:
    if customers.empty:
        return {"available": False, "reason": "没有已知用户的有效订单。"}
    ranked = customers.sort_values("monetary", ascending=False)
    # At least one customer, so a tiny filtered view still produces a number.
    cut = max(1, int(round(len(ranked) * 0.1)))
    top = ranked.head(cut)
    return {
        "available": True,
        "reason": None,
        "customer_count": int(len(ranked)),
        "top_customers": cut,
        "top_gmv": round(float(top["monetary"].sum()), 2),
        "top_gmv_share": safe_ratio(top["monetary"].sum(), total_gmv),
        "small_sample": len(ranked) < 10,
    }


def _region(valid: pd.DataFrame, total_gmv: float) -> list[dict[str, Any]]:
    if not has_dimension(valid, "收货省份"):
        return []
    grouped = (
        valid.groupby("收货省份", dropna=False)
        .agg(gmv=("金额", "sum"), orders=("订单号", "nunique"), customers=("用户ID", "nunique"))
        .reset_index()
        .sort_values("gmv", ascending=False)
    )
    rows = []
    for row in records(grouped):
        rows.append({
            **row,
            "gmv": round(float(row["gmv"]), 2),
            "gmv_share": safe_ratio(row["gmv"], total_gmv),
            "aov": safe_ratio(row["gmv"], row["orders"], digits=2),
        })
    return rows


def summarize_users(cleaned: pd.DataFrame) -> dict[str, Any]:
    """Repurchase, acquisition, concentration, and regional distribution."""
    valid = valid_orders(cleaned)
    total_gmv = float(valid["金额"].sum())
    customers = _customer_table(valid)

    limitations = [
        "数据窗口只有一年且没有更早历史，因此无法区分真实新客与老客；这里只展示首单月份分布。",
        "复购率基于订单明细推算，未做同一自然人多账号合并，也未排除代购等场景。",
    ]
    if customers.empty:
        limitations.append("没有已知用户ID的有效订单，用户维度不可用。")

    return {
        "available": not customers.empty,
        "reason": None if not customers.empty else "没有已知用户的有效订单。",
        "repurchase": _repurchase(customers),
        "acquisition": _acquisition(customers),
        "concentration": _concentration(customers, total_gmv),
        "region": _region(valid, total_gmv),
        "definitions": DEFINITIONS,
        "limitations": limitations,
    }
