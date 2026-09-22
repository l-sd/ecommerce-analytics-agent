"""Shared helpers for the analysis modules.

Every ``summarize_*`` function follows the same contract:

* it returns a plain ``dict`` that ``json.dumps`` can serialise;
* it never raises when an optional column or companion table is missing --
  instead it reports ``{"available": False, "reason": "..."}`` and the caller
  renders a "not supplied" note;
* it carries its own ``definitions`` so the 口径 travels with the numbers.

That last point matters more than it looks: the same report mixes a
valid-order 口径 (KPIs) with an all-orders 口径 (refunds, fulfilment), and a
number without its denominator is how a demo turns into a wrong claim.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

UNKNOWN = "未知"

# Fulfilment only exists for orders that actually shipped; the rest have no
# carrier and no timestamps by construction.
SHIPPED_STATUSES = ("已完成", "已发货")


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> JSON-safe list of dicts."""
    rows = frame.replace({np.nan: None}).to_dict(orient="records")
    return [{key: native(value) for key, value in row.items()} for row in rows]


def native(value: Any) -> Any:
    """Convert numpy/pandas scalars to plain Python so ``json.dumps`` works."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def valid_orders(cleaned: pd.DataFrame) -> pd.DataFrame:
    """The 口径 baseline every KPI is built on."""
    return cleaned[cleaned["是否有效订单"] & cleaned["金额"].notna()].copy()


def safe_ratio(numerator: Any, denominator: Any, digits: int = 4) -> float | None:
    """Ratio that returns ``None`` instead of dividing by zero.

    A zero denominator is a real outcome on a filtered view, and ``inf`` or
    ``NaN`` would propagate into the JSON as an unusable value.
    """
    if numerator is None or denominator is None:
        return None
    try:
        numerator = float(numerator)
        denominator = float(denominator)
    except (TypeError, ValueError):
        return None
    if denominator == 0 or pd.isna(numerator) or pd.isna(denominator):
        return None
    return round(numerator / denominator, digits)


def share_of(part: Any, whole: Any, digits: int = 4) -> float | None:
    return safe_ratio(part, whole, digits=digits)


def has_values(frame: pd.DataFrame, column: str) -> bool:
    """True when the column exists and carries at least one real value.

    A column the upload never supplied is null everywhere, which is how the
    optional-column degradation is detected.
    """
    return column in frame.columns and bool(frame[column].notna().any())


def has_dimension(frame: pd.DataFrame, column: str) -> bool:
    """Like :func:`has_values` but for columns filled with 未知 when absent."""
    if column not in frame.columns:
        return False
    values = frame[column].dropna()
    return bool((values != UNKNOWN).any())


def unavailable(reason: str, **extra: Any) -> dict[str, Any]:
    """Standard shape for a module that cannot compute its metrics."""
    return {"available": False, "reason": reason, **extra}


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def month_key(series: pd.Series) -> pd.Series:
    """``datetime`` series -> ``YYYY-MM`` strings."""
    return series.dt.to_period("M").astype(str)
