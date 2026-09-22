"""Date parsing: mixed formats, Excel serial numbers, and unparseable input.

The synthetic generator injects several date formats on purpose, so these cases
are the ones that actually appear in the demo dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ecommerce_analytics.pipeline import parse_date


@pytest.mark.parametrize(
    "value",
    [None, np.nan, pd.NaT, "", "   ", "不是日期", "2024-13-45", 1234567, 0, -5],
)
def test_unparseable_values_become_nat(value):
    assert pd.isna(parse_date(value))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("20240601", "2024-06-01"),
        (20240601, "2024-06-01"),
        ("2024/6/1", "2024-06-01"),
        ("2024-06-01", "2024-06-01"),
        ("2024-06-01 00:00:00", "2024-06-01"),
    ],
)
def test_common_formats(value, expected):
    assert parse_date(value) == pd.Timestamp(expected)


@pytest.mark.parametrize(
    ("serial", "expected"),
    [
        (40001, "2009-07-07"),
        (45000, "2023-03-15"),
        (59999, "2064-04-07"),
    ],
)
def test_excel_serials_are_converted(serial, expected):
    assert parse_date(serial) == pd.Timestamp(expected)


@pytest.mark.parametrize("serial", [40000, 60000])
def test_excel_serial_range_is_exclusive_at_both_ends(serial):
    """The guard is ``40000 < value < 60000``, so the endpoints fall through to
    string parsing and are dropped. Documented here so the boundary is explicit;
    the demo dataset never produces these values.
    """
    assert pd.isna(parse_date(serial))


@pytest.mark.parametrize("value", [39999, 60001])
def test_values_outside_the_serial_window_are_not_dates(value):
    assert pd.isna(parse_date(value))


def test_eight_digit_string_is_not_treated_as_a_serial():
    """``20240601`` is far above the serial window, so it takes the YYYYMMDD path."""
    assert parse_date("20240601") == pd.Timestamp("2024-06-01")
