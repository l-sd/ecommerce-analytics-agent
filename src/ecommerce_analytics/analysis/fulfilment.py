"""履约跟踪：发货时效、迟发率、签收时效、逾期率、物流商对比。

This is the dimension a 订单跟踪 role is actually measured on, and it uses the
**all-orders** 口径 rather than the valid-order baseline: a cancelled order still
went through (or failed) the fulfilment process, and excluding it would flatter
the late rate.

Two denominators that look alike and must not be confused:

* 迟发率 = 迟发订单数 / 应发订单数   (orders that produced a shipping event)
* 逾期率 = 逾期订单数 / 已签收订单数 (orders that produced a delivery event)

The industry late-shipment guideline is 4%; it is reported as a reference line,
not as a pass/fail threshold for synthetic data.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .common import has_values, safe_ratio, unavailable

DEFINITIONS = {
    "发货时效": "发货时间 − 下单日期，单位天。",
    "应发订单数": "产生发货时间的订单数（已发货 + 已完成）。待发货尚未发货，无法判定迟发。",
    "迟发订单数": "发货时效 > 承诺发货时效的订单数。",
    "迟发率": "迟发订单数 / 应发订单数。行业常设考核线为 4%。",
    "签收时效": "签收时间 − 发货时间，单位天。",
    "已签收订单数": "产生签收时间的订单数（已完成）。",
    "逾期订单数": "签收时效 > 承诺送达时效的订单数。",
    "逾期率": "逾期订单数 / 已签收订单数。分母是已签收订单，不是全量订单。",
}

INDUSTRY_LATE_THRESHOLD = 0.04


def _describe(series: pd.Series) -> dict[str, Any]:
    clean = series.dropna()
    if clean.empty:
        return {"count": 0, "mean": None, "median": None, "p90": None, "max": None}
    return {
        "count": int(len(clean)),
        "mean": round(float(clean.mean()), 2),
        "median": round(float(clean.median()), 2),
        "p90": round(float(clean.quantile(0.9)), 2),
        "max": int(clean.max()),
    }


def _histogram(series: pd.Series) -> list[dict[str, Any]]:
    counted = series.dropna().astype(int).value_counts().sort_index()
    total = int(counted.sum())
    return [
        {"days": int(days), "orders": int(count), "share": safe_ratio(count, total)}
        for days, count in counted.items()
    ]


def summarize_fulfilment(cleaned: pd.DataFrame) -> dict[str, Any]:
    """Shipping lag, late rate, delivery lag, overdue rate, carrier breakdown."""
    if not has_values(cleaned, "发货时间"):
        return unavailable(
            "未提供发货时间/承诺时效字段，履约指标不可用。",
            ship_lag={},
            late={},
            delivery={},
            carrier=[],
            monthly=[],
            funnel=[],
            definitions=DEFINITIONS,
        )

    shipped = cleaned[cleaned["发货时间"].notna()].copy()
    shipped["发货时效"] = (shipped["发货时间"] - shipped["日期"]).dt.days
    shipped = shipped[shipped["发货时效"].notna()]
    late_mask = shipped["发货时效"] > shipped["承诺发货时效"]

    delivered = cleaned[cleaned["签收时间"].notna() & cleaned["发货时间"].notna()].copy()
    delivered["签收时效"] = (delivered["签收时间"] - delivered["发货时间"]).dt.days
    delivered = delivered[delivered["签收时效"].notna()]
    overdue_mask = delivered["签收时效"] > delivered["承诺送达时效"]

    late_rate = safe_ratio(int(late_mask.sum()), len(shipped))
    overdue_rate = safe_ratio(int(overdue_mask.sum()), len(delivered))

    carrier_rows: list[dict[str, Any]] = []
    if has_values(cleaned, "物流商"):
        for carrier, group in shipped.groupby("物流商"):
            if carrier == "未知":
                continue
            group_delivered = delivered[delivered["物流商"] == carrier]
            carrier_late = group["发货时效"] > group["承诺发货时效"]
            carrier_overdue = (
                group_delivered["签收时效"] > group_delivered["承诺送达时效"]
                if not group_delivered.empty
                else pd.Series(dtype=bool)
            )
            carrier_rows.append({
                "物流商": str(carrier),
                "orders": int(len(group)),
                "mean_ship_lag": round(float(group["发货时效"].mean()), 2),
                "late_orders": int(carrier_late.sum()),
                "late_rate": safe_ratio(int(carrier_late.sum()), len(group)),
                "delivered_orders": int(len(group_delivered)),
                "mean_delivery_lag": (
                    round(float(group_delivered["签收时效"].mean()), 2) if not group_delivered.empty else None
                ),
                "overdue_rate": safe_ratio(int(carrier_overdue.sum()), len(group_delivered)),
            })
        carrier_rows.sort(key=lambda item: item["late_rate"] or 0)

    monthly_rows: list[dict[str, Any]] = []
    if has_values(cleaned, "日期"):
        shipped_month = shipped.assign(month=shipped["日期"].dt.to_period("M").astype(str))
        delivered_month = delivered.assign(month=delivered["日期"].dt.to_period("M").astype(str))
        for month in sorted(set(shipped_month["month"]) | set(delivered_month["month"])):
            month_shipped = shipped_month[shipped_month["month"] == month]
            month_delivered = delivered_month[delivered_month["month"] == month]
            month_late = month_shipped["发货时效"] > month_shipped["承诺发货时效"]
            month_overdue = month_delivered["签收时效"] > month_delivered["承诺送达时效"]
            monthly_rows.append({
                "month": month,
                "shipped_orders": int(len(month_shipped)),
                "late_rate": safe_ratio(int(month_late.sum()), len(month_shipped)),
                "delivered_orders": int(len(month_delivered)),
                "overdue_rate": safe_ratio(int(month_overdue.sum()), len(month_delivered)),
                # Below five orders a monthly rate is noise, so the chart skips it.
                "small_sample": len(month_shipped) < 5,
            })

    funnel = [
        {"stage": "下单", "count": int(cleaned["订单号"].nunique())},
        {"stage": "发货", "count": int(shipped["订单号"].nunique())},
        {"stage": "签收", "count": int(delivered["订单号"].nunique())},
    ]
    monotonic = funnel[0]["count"] >= funnel[1]["count"] >= funnel[2]["count"]

    limitations = [
        "发货/签收时间与承诺时效均为合成字段，仅用于演示履约口径的组织方式。",
        "待发货订单尚未产生发货时间，无法判定是否迟发，因此不进入迟发率分母。",
        "数据窗口末端的订单可能仍在途，签收率会被低估。",
    ]

    return {
        "available": True,
        "reason": None,
        "ship_lag": _describe(shipped["发货时效"]),
        "ship_lag_histogram": _histogram(shipped["发货时效"]),
        "late": {
            "shipped_orders": int(len(shipped)),
            "late_orders": int(late_mask.sum()),
            "late_rate": late_rate,
            "industry_threshold": INDUSTRY_LATE_THRESHOLD,
            "above_industry_line": late_rate is not None and late_rate > INDUSTRY_LATE_THRESHOLD,
        },
        "delivery": {
            "delivered_orders": int(len(delivered)),
            "mean_lag": round(float(delivered["签收时效"].mean()), 2) if not delivered.empty else None,
            "overdue_orders": int(overdue_mask.sum()),
            "overdue_rate": overdue_rate,
        },
        "carrier": carrier_rows,
        "monthly": monthly_rows,
        "funnel": funnel,
        "funnel_monotonic": bool(monotonic),
        "definitions": DEFINITIONS,
        "limitations": limitations,
    }
