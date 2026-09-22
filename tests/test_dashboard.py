"""Dashboard tests driven through Streamlit's own ``AppTest`` harness.

These run the real ``app.py`` script, so they catch wiring mistakes that unit
tests on the pipeline cannot: a renamed cleaning-log key, a chart that stops
rendering, or a filter that silently does nothing.

Skipped when the dashboard extra is not installed (``pip install -e ".[dev]"``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="install the dashboard extra to run these")

from streamlit.testing.v1 import AppTest  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app.py"
COMMITTED_ANALYSIS = PROJECT_ROOT / "artifacts" / "demo" / "analysis.json"
TIMEOUT = 180


@pytest.fixture(scope="module")
def analysis() -> dict:
    if not COMMITTED_ANALYSIS.exists():
        pytest.skip("committed analysis.json is absent")
    return json.loads(COMMITTED_ANALYSIS.read_text(encoding="utf-8"))


def _run() -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT)
    app.run()
    return app


@pytest.fixture(scope="module")
def default_view() -> AppTest:
    """One run shared by the read-only assertions below."""
    return _run()


def _dataframe_with(app: AppTest, column: str):
    """Find a rendered table by one of its columns.

    ``AppTest.dataframe`` follows the element tree, where column nesting puts the
    sidebar table and the two side-by-side tables in a non-obvious order, so
    looking tables up by index is brittle.
    """
    for frame in app.dataframe:
        if column in frame.value.columns:
            return frame.value
    raise AssertionError(f"no rendered table has a {column!r} column")


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


def test_all_four_charts_are_rendered(default_view):
    assert len(default_view.image) == 4


def test_the_channel_table_lists_every_channel(default_view, analysis):
    channel_table = _dataframe_with(default_view, "渠道")
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
    assert len(default_view.download_button) == 1


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
