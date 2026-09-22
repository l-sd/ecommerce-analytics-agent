"""The companion traffic table: schema, funnel invariants, order conservation.

Exposure and visitor counts only ever come from this table -- they are never
inferred from the order detail, because inferring them would be inventing data.
Shipping a separate table is only honest if the two sides reconcile, so these
tests pin the three properties that make it safe:

* every row is a valid funnel (曝光 >= 访客 >= 加购 >= 下单);
* ``sum(下单数)`` equals the orders that have both a known channel and a
  parseable date -- exactly, not approximately;
* that equality is not vacuous, i.e. the order table really does contain rows
  that no cell can absorb.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ecommerce_analytics.demo_data import (
    CHANNELS,
    TRAFFIC_COLUMNS,
    TRAFFIC_START,
    generate_traffic,
    read_traffic,
    write_demo,
)
from ecommerce_analytics.pipeline import analyze_orders, clean_orders, read_orders

DEMO_ROWS = 3000
DEMO_SEED = 20240601
TRAFFIC_DAYS = 366  # 2024 is a leap year, so the window is a full 366 days.
EXPECTED_TRAFFIC_ROWS = TRAFFIC_DAYS * len(CHANNELS)
FUNNEL_STAGES = ["曝光", "访客", "加购", "下单"]


@pytest.fixture(scope="module")
def demo(tmp_path_factory) -> dict:
    """The three-table demo, written and read back exactly as the CLI does."""
    work = tmp_path_factory.mktemp("traffic")
    orders_path = work / "synthetic_orders.csv"
    write_demo(orders_path, rows=DEMO_ROWS, seed=DEMO_SEED)
    raw = read_orders(orders_path)
    cleaned, cleaning_log = clean_orders(raw)
    return {
        "raw": raw,
        "cleaned": cleaned,
        "cleaning_log": cleaning_log,
        "traffic": read_traffic(work / "synthetic_traffic.csv"),
    }


@pytest.fixture(scope="module")
def summary(demo) -> dict:
    return analyze_orders(demo["cleaned"], traffic=demo["traffic"])["traffic"]


# --- the table itself -------------------------------------------------------


def test_the_table_has_one_row_per_day_per_channel(demo):
    traffic = demo["traffic"]
    assert len(traffic) == EXPECTED_TRAFFIC_ROWS
    assert traffic["日期"].nunique() == TRAFFIC_DAYS
    assert sorted(traffic["渠道"].unique()) == sorted(CHANNELS)
    assert not traffic.duplicated(subset=["日期", "渠道"]).any()


def test_the_window_starts_on_the_declared_date_and_runs_a_full_year(demo):
    traffic = demo["traffic"]
    assert traffic["日期"].min() == pd.Timestamp(TRAFFIC_START)
    assert traffic["日期"].max() == pd.Timestamp(TRAFFIC_START) + pd.Timedelta(days=TRAFFIC_DAYS - 1)


def test_the_columns_are_exactly_the_declared_schema(demo):
    assert list(demo["traffic"].columns) == TRAFFIC_COLUMNS


def test_every_row_is_a_valid_funnel(demo):
    """A row where carts outnumber visitors would make the funnel meaningless."""
    traffic = demo["traffic"]
    assert (traffic["曝光数"] >= traffic["访客数"]).all()
    assert (traffic["访客数"] >= traffic["加购数"]).all()
    assert (traffic["加购数"] >= traffic["下单数"]).all()


def test_the_counts_are_never_negative(demo):
    traffic = demo["traffic"]
    for column in ["曝光数", "访客数", "加购数", "下单数"]:
        assert (traffic[column] >= 0).all(), column


def test_days_without_orders_still_carry_exposure(demo):
    """The organic floor is what gives the funnel a shape on quiet days."""
    traffic = demo["traffic"]
    quiet = traffic[traffic["下单数"] == 0]
    assert not quiet.empty
    assert (quiet["曝光数"] > 0).all()
    assert (quiet["访客数"] > 0).all()


# --- conservation with the order table --------------------------------------


def test_the_order_totals_reconcile_with_the_order_table(summary):
    conservation = summary["conservation"]
    assert conservation["passed"] is True
    assert conservation["difference"] == 0
    assert conservation["traffic_orders"] == conservation["attributable_orders"]


def test_the_reconciliation_is_not_vacuous(demo, summary):
    """The equality only means something if some orders *cannot* be attributed.

    Orders with an unknown channel or an unparseable date have no cell to land
    in. If a regression started dropping them from both sides the difference
    would still be zero, so assert the exclusions exist.
    """
    cleaned = demo["cleaned"]
    unattributable = cleaned[cleaned["渠道"].eq("未知") | cleaned["日期"].isna()]
    assert not unattributable.empty
    assert len(cleaned) - len(unattributable) == summary["conservation"]["attributable_orders"]


def test_the_order_total_is_a_subset_of_the_cleaned_rows(demo, summary):
    assert 0 < summary["conservation"]["traffic_orders"] < len(demo["cleaned"])


# --- funnel totals and rates ------------------------------------------------


def test_the_funnel_covers_every_stage_in_order(summary):
    assert [row["stage"] for row in summary["funnel"]] == FUNNEL_STAGES


def test_the_funnel_totals_never_increase(summary):
    counts = [row["count"] for row in summary["funnel"]]
    assert all(lower >= upper for lower, upper in zip(counts, counts[1:], strict=False))


def test_the_funnel_totals_are_the_column_sums(demo, summary):
    traffic = demo["traffic"]
    for row in summary["funnel"]:
        assert row["count"] == int(traffic[f"{row['stage']}数"].sum())


def test_the_step_rates_match_the_funnel_totals(summary):
    totals = {row["stage"]: row["count"] for row in summary["funnel"]}
    rates = summary["rates"]
    assert rates["访客率"] == pytest.approx(totals["访客"] / totals["曝光"], abs=1e-4)
    assert rates["加购率"] == pytest.approx(totals["加购"] / totals["访客"], abs=1e-4)
    assert rates["下单转化率"] == pytest.approx(totals["下单"] / totals["访客"], abs=1e-4)
    assert rates["全链路转化率"] == pytest.approx(totals["下单"] / totals["曝光"], abs=1e-4)


def test_every_rate_is_a_fraction(summary):
    for name, value in summary["rates"].items():
        assert 0 < value < 1, name


# --- per-channel traffic quality --------------------------------------------


def test_the_channel_table_covers_every_channel_in_the_table(demo, summary):
    exposure = demo["traffic"].groupby("渠道")["曝光数"].sum().sort_values(ascending=False)
    assert [row["渠道"] for row in summary["channel"]] == list(exposure.index)


def test_the_channel_rows_are_ordered_by_exposure(summary):
    exposures = [row["曝光数"] for row in summary["channel"]]
    assert exposures == sorted(exposures, reverse=True)


def test_the_exposure_shares_sum_to_one(summary):
    total = sum(row["曝光份额"] for row in summary["channel"])
    assert total == pytest.approx(1.0, abs=1e-3)


def test_the_share_gap_is_the_difference_of_its_two_shares(summary):
    for row in summary["channel"]:
        assert row["份额差"] == pytest.approx(row["gmv_share"] - row["曝光份额"], abs=1e-4)


def test_the_gmv_share_stops_short_of_one_by_the_unattributable_slice(demo, summary):
    """``gmv_share`` is measured against *total* valid GMV, which includes the
    ``未知`` channel, while the traffic table only holds real channels. The
    shares therefore sum to just under 100%; the gap is the unattributable
    slice, and stating it here stops a reader mistaking it for rounding.

    Each share is rounded to four decimals, so five of them can drift by up to
    2.5e-4 -- hence the loose tolerance rather than an exact comparison.
    """
    analysis = analyze_orders(demo["cleaned"], traffic=demo["traffic"])
    unknown_share = next(row["gmv_share"] for row in analysis["channel"] if row["渠道"] == "未知")
    assert unknown_share > 0
    total = sum(row["gmv_share"] for row in summary["channel"])
    assert total == pytest.approx(1.0 - unknown_share, abs=5e-4)
    assert total < 1.0


def test_each_channel_gmv_matches_the_order_side(demo, summary):
    """The per-channel GMV is the order-side number, not a traffic-side estimate."""
    analysis = analyze_orders(demo["cleaned"], traffic=demo["traffic"])
    order_gmv = {row["渠道"]: row["gmv"] for row in analysis["channel"]}
    for row in summary["channel"]:
        assert row["gmv"] == pytest.approx(order_gmv[row["渠道"]], abs=0.01)


def test_the_per_channel_order_counts_are_covered_by_the_funnel(summary):
    total = sum(row["下单数"] for row in summary["channel"])
    assert total == next(row["count"] for row in summary["funnel"] if row["stage"] == "下单")


# --- monthly breakdown ------------------------------------------------------


def test_the_monthly_breakdown_covers_twelve_months(summary):
    months = [row["month"] for row in summary["monthly"]]
    assert len(months) == 12
    assert months == sorted(months)
    assert months[0] == "2024-01"
    assert months[-1] == "2024-12"


def test_the_monthly_orders_add_up_to_the_funnel(summary):
    monthly = sum(row["下单数"] for row in summary["monthly"])
    assert monthly == next(row["count"] for row in summary["funnel"] if row["stage"] == "下单")


def test_each_month_carries_its_own_conversion_rate(summary):
    for row in summary["monthly"]:
        assert row["下单转化率"] == pytest.approx(row["下单数"] / row["访客数"], abs=1e-4)


# --- reading and generation -------------------------------------------------


def test_generation_is_deterministic(demo):
    first = generate_traffic(demo["raw"])
    second = generate_traffic(demo["raw"])
    pd.testing.assert_frame_equal(first, second)


def test_generating_from_cleaned_orders_gives_the_same_table(demo):
    """``write_demo`` feeds the raw frame; the pipeline feeds the cleaned one.

    Both must land on the same counts, otherwise the committed CSV and a
    freshly generated table would disagree.
    """
    pd.testing.assert_frame_equal(generate_traffic(demo["raw"]), generate_traffic(demo["cleaned"]))


def test_rows_with_unparseable_dates_are_dropped(tmp_path):
    path = tmp_path / "traffic.csv"
    pd.DataFrame(
        [
            {"日期": "2024-01-01", "渠道": "天猫", "曝光数": 10, "访客数": 5, "加购数": 2, "下单数": 1},
            {"日期": "not-a-date", "渠道": "天猫", "曝光数": 10, "访客数": 5, "加购数": 2, "下单数": 1},
        ]
    ).to_csv(path, index=False, encoding="utf-8-sig")

    traffic = read_traffic(path)
    assert len(traffic) == 1
    assert traffic["日期"].iloc[0] == pd.Timestamp("2024-01-01")


def test_non_numeric_counts_become_zero(tmp_path):
    path = tmp_path / "traffic.csv"
    pd.DataFrame(
        [{"日期": "2024-01-01", "渠道": "天猫", "曝光数": "n/a", "访客数": 5, "加购数": 2, "下单数": 1}]
    ).to_csv(path, index=False, encoding="utf-8-sig")

    traffic = read_traffic(path)
    assert int(traffic["曝光数"].iloc[0]) == 0


def test_a_missing_channel_becomes_unknown(tmp_path):
    path = tmp_path / "traffic.csv"
    pd.DataFrame(
        [{"日期": "2024-01-01", "渠道": None, "曝光数": 10, "访客数": 5, "加购数": 2, "下单数": 1}]
    ).to_csv(path, index=False, encoding="utf-8-sig")

    assert read_traffic(path)["渠道"].iloc[0] == "未知"


def test_a_missing_column_is_rejected(tmp_path):
    path = tmp_path / "traffic.csv"
    pd.DataFrame([{"日期": "2024-01-01", "渠道": "天猫"}]).to_csv(path, index=False, encoding="utf-8-sig")

    with pytest.raises(ValueError, match="Missing traffic columns"):
        read_traffic(path)


# --- degradation ------------------------------------------------------------


def test_no_traffic_table_says_so_rather_than_returning_zeros(demo):
    """A missing table must not look like a table full of zeros."""
    summary = analyze_orders(demo["cleaned"])["traffic"]
    assert summary["available"] is False
    assert "未提供流量表" in summary["reason"]
    assert summary["funnel"] == []
    assert summary["rates"] == {}
    assert summary["channel"] == []
    assert summary["monthly"] == []
    assert "conservation" not in summary
    # The 口径 survives, so the report can still explain what it could not show.
    assert summary["definitions"] == analyze_orders(demo["cleaned"], traffic=demo["traffic"])["traffic"]["definitions"]


def test_an_empty_traffic_table_is_treated_as_absent(demo):
    summary = analyze_orders(demo["cleaned"], traffic=demo["traffic"].iloc[0:0])["traffic"]
    assert summary["available"] is False
