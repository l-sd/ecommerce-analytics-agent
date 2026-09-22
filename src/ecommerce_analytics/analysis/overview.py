"""概览层：核心 KPI 与数据来源清单。

The KPI block is the same one the CLI, the Excel summary sheet, and the HTML
report have always used -- it is extracted here so the dashboard and the
pipeline cannot drift apart on the headline numbers.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .common import UNKNOWN


def summarize_kpi(valid: pd.DataFrame) -> dict[str, Any]:
    """Headline KPIs on the valid-order baseline."""
    valid_gmv = float(valid["金额"].sum())
    valid_orders = int(valid["订单号"].nunique())
    quantity = float(valid["数量"].sum())
    customers = int(valid.loc[valid["用户ID"] != UNKNOWN, "用户ID"].nunique())
    return {
        "gmv": round(valid_gmv, 2),
        "orders": valid_orders,
        "aov": round(valid_gmv / valid_orders, 2) if valid_orders else None,
        "quantity": round(quantity, 2),
        "customers": customers,
        "items_per_order": round(quantity / valid_orders, 2) if valid_orders else None,
    }


def summarize_sources(
    traffic: pd.DataFrame | None,
    catalog: pd.DataFrame | None,
) -> dict[str, Any]:
    """Which companion tables the caller supplied.

    The dashboard reads this to explain an empty panel: "traffic table not
    supplied" is a very different message from "the filter returned nothing".
    """
    return {
        "orders": {"available": True},
        "traffic": {
            "available": traffic is not None and not traffic.empty,
            "rows": int(len(traffic)) if traffic is not None else 0,
        },
        "catalog": {
            "available": catalog is not None and not catalog.empty,
            "rows": int(len(catalog)) if catalog is not None else 0,
        },
    }
