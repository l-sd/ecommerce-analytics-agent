"""Analysis modules, one per business dimension.

``pipeline.analyze_orders`` is the facade the CLI, the dashboard, and the tests
call; these modules hold the actual computation so a dimension can be read,
tested, and changed on its own.

Import order note: ``pipeline`` re-exports ``records``/``native`` from here, so
these modules must not import ``pipeline`` at module scope -- that would be a
cycle. ``customer_rfm_table`` stays in ``pipeline`` and is imported lazily by
the callers that need it.
"""

from __future__ import annotations

from .common import (
    UNKNOWN,
    has_dimension,
    has_values,
    native,
    records,
    safe_ratio,
    share_of,
    unavailable,
    valid_orders,
)
from .fulfilment import summarize_fulfilment
from .overview import summarize_kpi, summarize_sources
from .sales import summarize_sales
from .traffic import summarize_traffic
from .users import summarize_users

__all__ = [
    "UNKNOWN",
    "has_dimension",
    "has_values",
    "native",
    "records",
    "safe_ratio",
    "share_of",
    "summarize_fulfilment",
    "summarize_kpi",
    "summarize_sales",
    "summarize_sources",
    "summarize_traffic",
    "summarize_users",
    "unavailable",
    "valid_orders",
]
