"""流量与转化：漏斗、环节转化率、渠道流量质量。

Data source is the companion traffic table, never the order detail. Exposure and
visitor counts cannot be inferred from orders -- doing so would be inventing
data, and the whole point of shipping a separate table is that the two
reconcile through ``下单数`` instead of through an assumption.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .common import UNKNOWN, has_values, records, safe_ratio, unavailable, valid_orders

FUNNEL_STAGES = ["曝光", "访客", "加购", "下单"]
_STAGE_COLUMNS = {"曝光": "曝光数", "访客": "访客数", "加购": "加购数", "下单": "下单数"}

DEFINITIONS = {
    "曝光数": "流量表中该渠道当日的商品曝光次数之和（PV）。",
    "访客数": "流量表中该渠道当日的去重访客数之和（UV）。",
    "加购数": "流量表中该渠道当日加入购物车的次数之和。",
    "下单数": "由订单明细按渠道×日期分组统计得到，因此与订单表天然守恒。",
    "访客率": "访客数 / 曝光数。",
    "加购率": "加购数 / 访客数。",
    "下单转化率": "下单数 / 访客数；这是行业口径的转化率。",
    "全链路转化率": "下单数 / 曝光数。",
}


def _funnel_rows(traffic: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"stage": stage, "count": int(traffic[_STAGE_COLUMNS[stage]].sum())} for stage in FUNNEL_STAGES
    ]


def _conservation(cleaned: pd.DataFrame, traffic: pd.DataFrame) -> dict[str, Any]:
    """``sum(下单数)`` must equal the orders that can be attributed to a cell.

    Orders with an unknown channel or an unparseable date have no cell to land
    in, so they are excluded from the right-hand side rather than quietly
    dropped from both.
    """
    attributable = cleaned[cleaned["渠道"].ne(UNKNOWN) & cleaned["日期"].notna()]
    traffic_orders = int(traffic["下单数"].sum())
    order_rows = int(len(attributable))
    difference = traffic_orders - order_rows
    return {
        "traffic_orders": traffic_orders,
        "attributable_orders": order_rows,
        "difference": difference,
        "passed": difference == 0,
    }


def summarize_traffic(cleaned: pd.DataFrame, traffic: pd.DataFrame | None) -> dict[str, Any]:
    """Funnel totals, step rates, and per-channel traffic quality."""
    if traffic is None or traffic.empty:
        return unavailable(
            "未提供流量表，曝光/访客/加购不可用；转化率无法计算。",
            funnel=[],
            rates={},
            channel=[],
            monthly=[],
            definitions=DEFINITIONS,
        )

    funnel = _funnel_rows(traffic)
    totals = {row["stage"]: row["count"] for row in funnel}
    rates = {
        "访客率": safe_ratio(totals["访客"], totals["曝光"]),
        "加购率": safe_ratio(totals["加购"], totals["访客"]),
        "下单转化率": safe_ratio(totals["下单"], totals["访客"]),
        "全链路转化率": safe_ratio(totals["下单"], totals["曝光"]),
    }

    # 成交侧对照：流量份额与 GMV 份额的差额说明流量是否"划算"。
    valid = valid_orders(cleaned)
    gmv_by_channel = valid.groupby("渠道")["金额"].sum()
    total_gmv = float(gmv_by_channel.sum())

    by_channel = traffic.groupby("渠道", dropna=False)[
        ["曝光数", "访客数", "加购数", "下单数"]
    ].sum().reset_index()
    total_exposure = int(by_channel["曝光数"].sum())
    channel_rows = []
    for row in records(by_channel):
        channel = row["渠道"]
        gmv = float(gmv_by_channel.get(channel, 0.0))
        exposure_share = safe_ratio(row["曝光数"], total_exposure)
        gmv_share = safe_ratio(gmv, total_gmv)
        channel_rows.append({
            **row,
            "gmv": round(gmv, 2),
            "gmv_share": gmv_share,
            "曝光份额": exposure_share,
            "份额差": (
                round(gmv_share - exposure_share, 4)
                if gmv_share is not None and exposure_share is not None
                else None
            ),
            "下单转化率": safe_ratio(row["下单数"], row["访客数"]),
            "加购率": safe_ratio(row["加购数"], row["访客数"]),
            "访客率": safe_ratio(row["访客数"], row["曝光数"]),
        })
    channel_rows.sort(key=lambda item: item["曝光数"], reverse=True)

    monthly = (
        traffic.assign(month=traffic["日期"].dt.to_period("M").astype(str))
        .groupby("month")[["曝光数", "访客数", "加购数", "下单数"]]
        .sum()
        .reset_index()
    )
    monthly_rows = [
        {**row, "下单转化率": safe_ratio(row["下单数"], row["访客数"])} for row in records(monthly)
    ]

    limitations = [
        "曝光、访客与加购来自合成的流量表，不是真实埋点数据；漏斗形状用于演示口径，不代表真实转化水平。",
        "下单数由订单明细回填，因此漏斗末端与订单表严格守恒，但这意味着它不含未成交的浏览行为。",
    ]
    if not has_values(cleaned, "日期"):
        limitations.append("订单表没有可解析日期，无法按日/月拆分流量。")

    return {
        "available": True,
        "reason": None,
        "funnel": funnel,
        "rates": rates,
        "channel": channel_rows,
        "monthly": monthly_rows,
        "conservation": _conservation(cleaned, traffic),
        "definitions": DEFINITIONS,
        "limitations": limitations,
    }
