"""销售与商品：品类/品牌结构、SKU 集中度、动销率、退款专项。

Two 口径 live here and they must not be mixed:

* category / brand / sell-through are computed on **valid orders**, the same
  baseline as the headline KPIs;
* refunds are computed on **all orders**, because a refunded order is by
  definition excluded from valid orders -- computing the refund rate on the
  valid subset would make it structurally zero.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .common import UNKNOWN, has_dimension, has_values, records, safe_ratio, unavailable, valid_orders

DEFINITIONS = {
    "品类GMV": "有效订单按商品品类汇总的金额之和。",
    "品类占比": "品类 GMV / 有效 GMV；各品类合计应等于 100%。",
    "品牌GMV": "有效订单按品牌汇总的金额之和（品牌来自商品主数据）。",
    "在售SKU数": "商品主数据中在售状态的 SKU 数量。",
    "有销量SKU数": "有效订单中出现过、且存在于主数据在售清单中的 SKU 数量。",
    "动销率": "有销量SKU数 / 在售SKU数。分母必须来自商品主数据，不能用明细反推。",
    "退款率": "已退款订单数 / 该渠道全量订单数（分母是全量，不是有效订单）。",
    "退款金额": "已退款订单金额的绝对值之和，用于衡量退款对 GMV 的侵蚀。",
}


def _category_table(valid: pd.DataFrame, total_gmv: float) -> list[dict[str, Any]]:
    if not has_dimension(valid, "商品品类"):
        return []
    grouped = (
        valid.groupby("商品品类", dropna=False)
        .agg(gmv=("金额", "sum"), orders=("订单号", "nunique"), quantity=("数量", "sum"))
        .reset_index()
    )
    grouped["aov"] = grouped["gmv"] / grouped["orders"].replace(0, pd.NA)
    grouped["gmv_share"] = grouped["gmv"] / total_gmv if total_gmv else None
    grouped = grouped.sort_values("gmv", ascending=False)
    return [
        {
            **row,
            "gmv": round(float(row["gmv"]), 2),
            "aov": round(float(row["aov"]), 2) if row["aov"] is not None else None,
            "gmv_share": safe_ratio(row["gmv"], total_gmv),
        }
        for row in records(grouped)
    ]


def _brand_table(valid: pd.DataFrame, catalog: pd.DataFrame | None, total_gmv: float, top_n: int = 10):
    """Brand comes from the product master, joined on 商品ID."""
    if catalog is None or catalog.empty:
        return []
    lookup = catalog.set_index("商品ID")["品牌"].to_dict()
    enriched = valid.assign(品牌=valid["商品ID"].map(lookup))
    enriched = enriched[enriched["品牌"].notna()]
    if enriched.empty:
        return []
    grouped = (
        enriched.groupby("品牌")
        .agg(gmv=("金额", "sum"), orders=("订单号", "nunique"))
        .reset_index()
        .sort_values("gmv", ascending=False)
        .head(top_n)
    )
    return [
        {**row, "gmv": round(float(row["gmv"]), 2), "gmv_share": safe_ratio(row["gmv"], total_gmv)}
        for row in records(grouped)
    ]


def _sell_through(valid: pd.DataFrame, catalog: pd.DataFrame | None) -> dict[str, Any]:
    if catalog is None or catalog.empty:
        return unavailable("未提供商品主数据表，动销率分母不可得（不能用订单明细反推，否则指标恒为 100%）。")

    on_sale = catalog[catalog["在售状态"] == "在售"] if "在售状态" in catalog.columns else catalog
    on_sale_ids = set(on_sale["商品ID"].dropna().astype(str))
    sold_ids = set(valid["商品ID"].dropna().astype(str)) - {UNKNOWN}
    matched = sold_ids & on_sale_ids
    unsold = sorted(on_sale_ids - sold_ids)
    unregistered = sorted(sold_ids - on_sale_ids)

    return {
        "available": True,
        "reason": None,
        "on_sale_skus": len(on_sale_ids),
        "sold_skus": len(matched),
        "sell_through_rate": safe_ratio(len(matched), len(on_sale_ids)),
        "unsold_skus": unsold,
        "unregistered_skus": unregistered,
        "skus_in_orders": len(sold_ids),
    }


def _refund_table(cleaned: pd.DataFrame) -> dict[str, Any]:
    """Refund metrics on ALL orders, split by channel."""
    all_orders = cleaned.copy()
    all_orders["is_refund"] = all_orders["订单状态"] == "已退款"
    all_orders["refund_amount"] = all_orders["金额"].abs().where(all_orders["is_refund"], 0.0)

    by_channel = (
        all_orders.groupby("渠道", dropna=False)
        .agg(orders=("订单号", "nunique"), refunds=("is_refund", "sum"), refund_amount=("refund_amount", "sum"))
        .reset_index()
    )
    channel_rows = [
        {
            "渠道": row["渠道"],
            "orders": int(row["orders"]),
            "refunds": int(row["refunds"]),
            "refund_rate": safe_ratio(row["refunds"], row["orders"]),
            "refund_amount": round(float(row["refund_amount"]), 2),
        }
        for row in records(by_channel)
    ]
    channel_rows.sort(key=lambda item: item["refund_rate"] or 0, reverse=True)

    reasons: list[dict[str, Any]] = []
    refunds = all_orders[all_orders["is_refund"]]
    if has_values(cleaned, "退款原因"):
        counted = refunds["退款原因"].value_counts()
        total = int(counted.sum())
        reasons = [
            {"退款原因": str(reason), "orders": int(count), "share": safe_ratio(count, total)}
            for reason, count in counted.items()
        ]

    total_orders = int(all_orders["订单号"].nunique())
    refund_orders = int(all_orders["is_refund"].sum())
    return {
        "orders": total_orders,
        "refund_orders": refund_orders,
        "refund_rate": safe_ratio(refund_orders, total_orders),
        "refund_amount": round(float(all_orders["refund_amount"].sum()), 2),
        "by_channel": channel_rows,
        "reasons": reasons,
    }


def summarize_sales(cleaned: pd.DataFrame, catalog: pd.DataFrame | None = None) -> dict[str, Any]:
    """Category, brand, sell-through, and refund metrics."""
    valid = valid_orders(cleaned)
    total_gmv = float(valid["金额"].sum())

    category = _category_table(valid, total_gmv)
    brand = _brand_table(valid, catalog, total_gmv)
    sell_through = _sell_through(valid, catalog)
    refund = _refund_table(cleaned)

    limitations = [
        "退款率的分母是全量订单，核心 KPI 的分母是有效订单；两者不可直接相加或对比。",
        "退款原因来自合成字段，仅用于演示归因表格的组织方式。",
    ]
    if not category:
        limitations.append("订单表未提供商品品类列，品类结构不可用。")
    if catalog is None or catalog.empty:
        limitations.append("未提供商品主数据表，动销率与品牌结构不可用。")

    return {
        "available": True,
        "reason": None,
        "category": category,
        "brand": brand,
        "sell_through": sell_through,
        "refund": refund,
        "definitions": DEFINITIONS,
        "limitations": limitations,
    }
