"""Cleaning and analysis edge cases: empty, all-refunded, all-missing, tied ranks."""

from __future__ import annotations

import pandas as pd
import pytest

from ecommerce_analytics.pipeline import analyze_orders, clean_orders, numeric_price


def _frame(rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "订单号": [f"O{index:04d}" for index in range(rows)],
            "日期": ["2024-01-05"] * rows,
            "渠道": ["天猫"] * rows,
            "商品ID": ["P001"] * rows,
            "商品名称": ["测试商品"] * rows,
            "单价": ["¥1,299.00"] * rows,
            "数量": [1] * rows,
            "金额": ["1,299.00"] * rows,
            "用户ID": [f"U{index:03d}" for index in range(rows)],
            "收货省份": ["浙江"] * rows,
            "订单状态": ["已完成"] * rows,
        }
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("¥5,999", 5999.0),
        ("5999元", 5999.0),
        ("¥ 1,299.50", 1299.5),
        ("1299.00", 1299.0),
        ("0", 0.0),
        ("-100", -100.0),
        ("29.9", 29.9),
    ],
)
def test_numeric_price_parses_dirty_formats(raw, expected):
    assert numeric_price(pd.Series([raw])).iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["abc", "¥", "", "  ", "一三九"])
def test_numeric_price_returns_na_for_unparseable(raw):
    assert pd.isna(numeric_price(pd.Series([raw])).iloc[0])


def test_numeric_price_accepts_native_numbers():
    result = numeric_price(pd.Series([0, -100, 29.9]))

    assert result.tolist() == [0.0, -100.0, 29.9]


def test_empty_frame_is_handled():
    cleaned, log = clean_orders(_frame(0))

    assert cleaned.empty
    assert log["raw"]["rows"] == 0
    assert log["duplicates_removed"] == 0


def test_duplicate_order_keeps_first_row():
    frame = _frame(2)
    doubled = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)

    cleaned, log = clean_orders(doubled)

    assert len(cleaned) == 2
    assert log["duplicates_removed"] == 1


def test_amount_is_recalculated_and_original_preserved():
    frame = _frame(1)
    frame["单价"] = "100"
    frame["数量"] = 3
    frame["金额"] = "250"

    cleaned, _ = clean_orders(frame)

    assert cleaned.loc[0, "金额"] == pytest.approx(300.0)
    assert cleaned.loc[0, "原金额"] == pytest.approx(250.0)


def test_zero_quantity_yields_zero_amount_rather_than_missing():
    frame = _frame(1)
    frame["数量"] = 0

    cleaned, _ = clean_orders(frame)

    assert cleaned.loc[0, "金额"] == pytest.approx(0.0)
    assert pd.notna(cleaned.loc[0, "金额"])


def test_missing_dimensions_are_filled_with_unknown():
    frame = _frame(2)
    frame.loc[0, "渠道"] = None
    frame.loc[0, "收货省份"] = None

    cleaned, _ = clean_orders(frame)

    assert cleaned.loc[0, "渠道"] == "未知"
    assert cleaned.loc[0, "收货省份"] == "未知"


def test_all_refunded_orders_produce_no_valid_kpi():
    frame = _frame(3)
    frame["订单状态"] = "已退款"

    cleaned, log = clean_orders(frame)
    analysis = analyze_orders(cleaned)

    assert log["valid_orders"] == 0
    assert log["refund_or_cancel_orders"] == 3
    assert analysis["kpi"]["orders"] == 0
    assert analysis["kpi"]["aov"] is None


def test_all_missing_prices_produce_no_valid_kpi():
    frame = _frame(3)
    frame["单价"] = None

    cleaned, _ = clean_orders(frame)
    analysis = analyze_orders(cleaned)

    assert analysis["kpi"]["orders"] == 0
    assert analysis["kpi"]["gmv"] == pytest.approx(0.0)
    assert analysis["kpi"]["aov"] is None


def test_single_customer_does_not_break_rfm():
    frame = _frame(2)
    frame["用户ID"] = "U001"

    cleaned, _ = clean_orders(frame)
    analysis = analyze_orders(cleaned)

    assert sum(row["customers"] for row in analysis["rfm"]) == 1


def test_tied_recency_values_do_not_break_terciles():
    frame = _frame(6)
    frame["日期"] = "2024-01-05"

    cleaned, _ = clean_orders(frame)
    analysis = analyze_orders(cleaned)

    assert sum(row["customers"] for row in analysis["rfm"]) == 6


def test_small_customer_count_still_labels_every_customer():
    frame = _frame(2)

    cleaned, _ = clean_orders(frame)
    analysis = analyze_orders(cleaned)

    assert sum(row["customers"] for row in analysis["rfm"]) == 2
    assert all(row["segment"] for row in analysis["rfm"])


def test_unknown_users_are_excluded_from_rfm():
    frame = _frame(4)
    frame.loc[0:1, "用户ID"] = None

    cleaned, _ = clean_orders(frame)
    analysis = analyze_orders(cleaned)

    assert sum(row["customers"] for row in analysis["rfm"]) == 2
