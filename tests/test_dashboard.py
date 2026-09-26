"""Dashboard tests driven through Streamlit's own ``AppTest`` harness.

These run the real ``app.py`` script, so they catch wiring mistakes that unit
tests on the pipeline cannot: a renamed cleaning-log key, a chart that stops
rendering, or a filter that silently does nothing.

Skipped when the dashboard extra is not installed (``pip install -e ".[dev]"``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="install the dashboard extra to run these")

from streamlit.testing.v1 import AppTest  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app.py"
TIMEOUT = 180


@pytest.fixture(scope="module")
def analysis() -> dict:
    from ecommerce_analytics.demo_data import read_catalog, read_traffic
    from ecommerce_analytics.pipeline import analyze_orders, clean_orders, read_orders

    root = PROJECT_ROOT / "data" / "portfolio_demo"
    cleaned, _ = clean_orders(read_orders(root / "synthetic_orders.csv"))
    return analyze_orders(
        cleaned,
        traffic=read_traffic(root / "synthetic_traffic.csv"),
        catalog=read_catalog(root / "synthetic_products.csv"),
    )


def _run() -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT)
    app.run()
    return app


@pytest.fixture(scope="module")
def default_view() -> AppTest:
    """One run shared by the read-only assertions below."""
    return _run()


def _dataframe_with(app: AppTest, *columns: str):
    """Find a rendered table by the columns it carries.

    ``AppTest.dataframe`` follows the element tree, where column nesting puts the
    sidebar table and the side-by-side tables in a non-obvious order, so looking
    tables up by index is brittle. Several tables now share a ``渠道`` column
    (the channel detail, the channel traffic quality and the refund-rate tables),
    so a single column is no longer a unique key -- pass every column the target
    table is expected to have and the first exact match wins.
    """
    for frame in app.dataframe:
        if all(column in frame.value.columns for column in columns):
            return frame.value
    joined = ", ".join(repr(column) for column in columns)
    raise AssertionError(f"no rendered table has all of: {joined}")


def test_dashboard_renders_without_error(default_view):
    assert not default_view.exception


def test_the_five_kpi_cards_match_the_committed_analysis(default_view, analysis):
    kpi = analysis["kpi"]
    rendered = {metric.label: metric.value for metric in default_view.metric}

    assert rendered["有效 GMV"] == f"¥{kpi['gmv']:,.0f}"
    assert rendered["有效订单"] == f"{kpi['orders']:,}"
    assert rendered["客单价"] == f"¥{kpi['aov']:,.0f}"
    assert rendered["有效客户"] == f"{kpi['customers']:,}"
    assert rendered["连带率"] == f"{kpi['items_per_order']:,.2f}"


def test_all_nine_charts_are_rendered(default_view):
    """``st.tabs`` runs every tab body on each rerun (the inactive ones are only
    hidden with CSS), so all nine figures are in the element tree at once."""
    assert len(default_view.image) == 9


def test_the_channel_table_lists_every_channel(default_view, analysis):
    channel_table = _dataframe_with(default_view, "渠道", "客单价")
    assert len(channel_table) == len(analysis["channel"])
    assert list(channel_table["渠道"]) == [row["渠道"] for row in analysis["channel"]]


def test_the_rfm_table_lists_every_segment(default_view, analysis):
    rfm_table = _dataframe_with(default_view, "分层")
    assert set(rfm_table["分层"]) == {row["segment"] for row in analysis["rfm"]}


def test_the_rfm_drilldown_offers_every_segment(default_view):
    options = default_view.selectbox[0].options
    assert options[0] == "全部"
    assert set(options[1:]) == {"重要价值客户", "重要挽留客户", "潜力客户", "一般客户"}


def test_a_download_button_is_available(default_view):
    assert len(default_view.download_button) >= 3


def test_six_business_analysis_tabs_are_present(default_view):
    labels = [tab.label for tab in default_view.tabs]
    assert labels == ["经营总览", "渠道与转化", "商品分析", "用户/RFM", "退款与履约", "数据质量"]


def test_the_default_view_keeps_orders_with_missing_dates(default_view):
    """No date window is active, so the undated orders still count towards GMV."""
    captions = " ".join(caption.value for caption in default_view.caption)
    assert "日期缺失" in captions
    assert "已按日期范围筛选" not in captions


def test_the_channel_filter_recomputes_the_kpis(analysis):
    """Selecting one channel must drop the other channels out of every KPI."""
    top_channel = analysis["channel"][0]

    app = _run()
    app.multiselect[0].set_value([top_channel["渠道"]])
    app.run()

    assert not app.exception
    rendered = {metric.label: metric.value for metric in app.metric}
    assert rendered["有效 GMV"] == f"¥{top_channel['gmv']:,.0f}"
    assert rendered["有效订单"] == f"{top_channel['orders']:,}"


def test_clearing_the_channel_filter_falls_back_to_every_channel(default_view, analysis):
    """Clearing a multi-select is easy to do by accident, so it must not empty
    the page; the caption states the fallback instead."""
    app = _run()
    app.multiselect[0].set_value([])
    app.run()

    assert not app.exception
    captions = " ".join(caption.value for caption in app.caption)
    assert "未选择渠道" in captions

    rendered = {metric.label: metric.value for metric in app.metric}
    assert rendered["有效 GMV"] == f"¥{analysis['kpi']['gmv']:,.0f}"


def test_narrowing_the_date_range_switches_to_the_filtered_caption():
    app = _run()
    app.date_input[0].set_value((app.date_input[0].value[0], app.date_input[0].value[0]))
    app.run()

    assert not app.exception
    captions = " ".join(caption.value for caption in app.caption)
    assert "已按日期范围筛选" in captions
