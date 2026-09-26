"""Chart builders: empty-input guards, palette cycling, and PNG output.

The chart layer is the part most exposed to a user-uploaded file rather than the
demo dataset, so these tests pin the guards that keep a thin or unusual channel
mix from taking the whole pipeline down.
"""

from __future__ import annotations

import matplotlib
import pandas as pd
import pytest

from ecommerce_analytics import visuals


@pytest.fixture(autouse=True)
def _headless_backend(monkeypatch):
    """Mirror CI by exporting ``MPLBACKEND=Agg``.

    The env var alone is not enough -- matplotlib resolves its backend when the
    module is first imported, which happens at collection time. Enforcing the
    backend is :func:`visuals._get_pyplot`'s job, and deliberately *not* done
    here so that the tests actually exercise that guard.
    """
    monkeypatch.setenv("MPLBACKEND", "Agg")


@pytest.fixture
def _restore_font_state():
    """Save and restore the module font cache plus the rcParams it mutates."""
    saved_cache = visuals._FONT_CACHE
    saved_family = list(visuals.matplotlib.rcParams["font.sans-serif"])
    yield
    visuals._FONT_CACHE = saved_cache
    visuals.matplotlib.rcParams["font.sans-serif"] = saved_family


def _channel_rows(count: int) -> list[dict]:
    """A channel table with `count` rows, descending by GMV."""
    total = float(count * (count + 1) / 2)
    return [
        {
            "渠道": f"渠道{index}",
            "gmv": float(count - index),
            "orders": 10,
            "aov": 5.0,
            "gmv_share": (count - index) / total,
        }
        for index in range(count)
    ]


def _cleaned_frame(rows: int = 6) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "是否有效订单": [True] * rows,
            "金额": [100.0 * (index + 1) for index in range(rows)],
            "用户ID": [f"U{index}" for index in range(rows)],
            "订单号": [f"O{index}" for index in range(rows)],
            "日期": pd.to_datetime([f"2024-{index + 1:02d}-01" for index in range(rows)]),
        }
    )


def test_font_setup_returns_an_installed_family():
    chosen = visuals.setup_chinese_font()
    assert isinstance(chosen, str) and chosen


def test_font_setup_is_cached_after_the_first_call(_restore_font_state):
    first = visuals.setup_chinese_font()
    assert visuals.setup_chinese_font() is first


def test_missing_cjk_font_warns_and_falls_back(_restore_font_state, monkeypatch):
    """A font-less CI container must degrade to boxes, not crash the run."""
    import matplotlib.font_manager as font_manager

    class _EmptyFontManager:
        ttflist: list = []

    monkeypatch.setattr(visuals, "_FONT_CACHE", None)
    monkeypatch.setattr(font_manager, "fontManager", _EmptyFontManager())
    with pytest.warns(RuntimeWarning, match="No CJK font found"):
        chosen = visuals.setup_chinese_font()
    assert chosen == "DejaVu Sans"


# --- backend selection -------------------------------------------------------


@pytest.mark.parametrize("interactive", ["TkAgg", "tkagg", "QtAgg", "MacOSX"])
def test_get_pyplot_switches_away_from_an_interactive_backend(monkeypatch, interactive):
    """Regression: ``"TkAgg".endswith("agg")`` is true, so a suffix check left
    matplotlib on a backend that needs a display and blew up with a TclError."""
    calls: list[str] = []
    monkeypatch.setattr(visuals.matplotlib, "get_backend", lambda: interactive)
    monkeypatch.setattr(visuals.matplotlib, "use", lambda backend, **kwargs: calls.append(backend))
    visuals._get_pyplot()
    assert calls == ["Agg"]


@pytest.mark.parametrize("headless", ["Agg", "agg"])
def test_get_pyplot_leaves_a_headless_backend_untouched(monkeypatch, headless):
    calls: list[str] = []
    monkeypatch.setattr(visuals.matplotlib, "get_backend", lambda: headless)
    monkeypatch.setattr(visuals.matplotlib, "use", lambda backend, **kwargs: calls.append(backend))
    visuals._get_pyplot()
    assert calls == []


# --- channel ring ------------------------------------------------------------


def test_channel_ring_handles_more_channels_than_palette_colours():
    """Regression: the palette has six entries, so a seventh channel used to
    raise from the legend's ``zip(..., strict=True)``."""
    figure, summary = visuals.channel_share_ring({"channel": _channel_rows(9)})
    legend = figure.axes[0].get_legend()
    assert len(legend.get_texts()) == 9
    assert summary["channel_count"] == 9


def test_channel_ring_labels_every_channel_share():
    figure, _summary = visuals.channel_share_ring({"channel": _channel_rows(6)})
    labels = [text.get_text() for text in figure.axes[0].get_legend().get_texts()]
    assert labels[0].startswith("渠道0")
    assert labels[0].endswith("%")


def test_channel_ring_renders_a_sliver_without_a_wedge_label():
    """The sub-3% wedge keeps its legend entry but drops its inside label."""
    rows = _channel_rows(6)
    rows[-1]["gmv"] = 0.1
    figure, _summary = visuals.channel_share_ring({"channel": rows})
    assert len(figure.axes[0].get_legend().get_texts()) == 6


@pytest.mark.parametrize(
    ("builder", "payload"),
    [
        (visuals.channel_share_ring, {"channel": []}),
        (visuals.gmv_monthly_trend, {"monthly": []}),
        (visuals.product_pareto, {"products_top15": []}),
    ],
)
def test_empty_analysis_returns_a_placeholder_instead_of_raising(builder, payload):
    figure, summary = builder(payload)
    assert figure is not None
    assert "summary" in summary


def test_rfm_segment_profile_handles_no_customers():
    empty = pd.DataFrame(
        {"是否有效订单": [], "金额": [], "用户ID": [], "订单号": [], "日期": pd.to_datetime([])}
    )
    figure, summary = visuals.rfm_segment_profile(empty)
    assert figure is not None
    assert "summary" in summary


# --- RFM segment profile -----------------------------------------------------

# Means chosen so every tier is distinguishable on every axis, which lets the
# assertions below name a specific expected value instead of just checking shape.
_PROFILE_ROWS = [
    ("重要价值客户", 8.0, 14.0, 65000.0),
    ("重要挽留客户", 67.0, 10.0, 55000.0),
    ("潜力客户", 15.0, 8.0, 30000.0),
    ("一般客户", 34.0, 11.0, 43000.0),
]


def _stub_customer_table(monkeypatch) -> pd.DataFrame:
    """Pin the per-customer table so the chart is tested, not the tercile maths.

    Building a raw frame that lands on all four tiers is brittle -- the tier rule
    reads three separate terciles plus a tie-breaker -- so the seam that matters
    here is "given these customers, is the chart right".
    """
    frame = pd.DataFrame(
        [
            {
                "用户ID": f"U{index}",
                "segment": segment,
                "recency_days": recency,
                "frequency": frequency,
                "monetary": monetary,
            }
            for index, (segment, recency, frequency, monetary) in enumerate(_PROFILE_ROWS)
        ]
    )
    monkeypatch.setattr(visuals, "customer_rfm_table", lambda _valid: frame)
    return frame


def test_rfm_profile_draws_one_panel_per_metric(monkeypatch):
    """R, F and M each get their own axis -- the layout must not collapse."""
    _stub_customer_table(monkeypatch)
    figure, _summary = visuals.rfm_segment_profile(_cleaned_frame(6))

    assert len(figure.axes) == 3
    for ax in figure.axes:
        assert len(ax.patches) == len(_PROFILE_ROWS)


def test_rfm_profile_plots_segment_means_in_gmv_order(monkeypatch):
    """Rows run smallest to largest GMV share, so the top row is the priority tier."""
    _stub_customer_table(monkeypatch)
    figure, summary = visuals.rfm_segment_profile(_cleaned_frame(6))

    expected_order = ["潜力客户", "一般客户", "重要挽留客户", "重要价值客户"]
    labels = [text.get_text() for text in figure.axes[0].get_yticklabels()]
    assert labels == expected_order

    # Panel 1 is R, so the bar widths are the mean recency per tier.
    widths = [patch.get_width() for patch in figure.axes[0].patches]
    assert widths == [15.0, 34.0, 67.0, 8.0]

    assert summary["top_gmv_segment"] == "重要价值客户"
    assert summary["longest_recency_segment"] == "重要挽留客户"
    assert summary["longest_recency_days"] == 67.0
    assert summary["highest_frequency_segment"] == "重要价值客户"
    assert summary["highest_monetary_segment"] == "重要价值客户"


def test_rfm_profile_bar_colours_follow_the_segment_map(monkeypatch):
    """A tier keeps its colour across all three panels and matches the summary table."""
    _stub_customer_table(monkeypatch)
    figure, _summary = visuals.rfm_segment_profile(_cleaned_frame(6))

    expected = [
        matplotlib.colors.to_rgba(visuals.SEGMENT_COLORS[segment])
        for segment, *_ in sorted(_PROFILE_ROWS, key=lambda row: row[3])
    ]
    for ax in figure.axes:
        assert [patch.get_facecolor() for patch in ax.patches] == expected


def test_style_axes_grid_follows_the_value_axis():
    """Horizontal bars read against x, so the grid has to move with them.

    Regression: a fixed y-axis grid drew lines between the bars instead of behind
    them once the RFM chart switched from a scatter to horizontal bars.
    """
    figure = visuals.matplotlib.figure.Figure()
    ax = figure.add_subplot(111)
    visuals._style_axes(ax, grid_axis="x")

    assert all(line.get_visible() for line in ax.xaxis.get_gridlines())
    assert not any(line.get_visible() for line in ax.yaxis.get_gridlines())


# --- chart row layout --------------------------------------------------------


def test_wide_figures_resolve_to_the_expected_filenames():
    """The report looks the rule up by filename, the dashboard by key."""
    assert visuals.WIDE_FIGURE_FILENAMES == {"fig3_product_pareto.png", "fig4_rfm_profile.png"}
    assert all(key in visuals.FIGURE_FILENAMES for key in visuals.WIDE_FIGURE_KEYS)


def test_chart_rows_gives_wide_charts_a_row_of_their_own():
    """Wide charts must not be halved into a pair, and order must be preserved."""
    order = ["monthly_trend", "channel_structure", "product_pareto", "rfm_profile"]
    assert visuals.chart_rows(order) == [
        ["monthly_trend", "channel_structure"],
        ["product_pareto"],
        ["rfm_profile"],
    ]


def test_chart_rows_flushes_a_pending_pair_before_a_wide_chart():
    """An odd narrow chart must not be stranded behind a wide one."""
    order = ["monthly_trend", "product_pareto", "channel_structure"]
    assert visuals.chart_rows(order) == [
        ["monthly_trend"],
        ["product_pareto"],
        ["channel_structure"],
    ]


def test_chart_rows_handles_an_empty_order():
    assert visuals.chart_rows([]) == []


# --- monthly trend -----------------------------------------------------------


def test_monthly_driver_follows_basket_size_when_order_count_is_flat():
    """GMV rising while order count falls means AOV is the driver."""
    analysis = {
        "monthly": [
            {"month": "2024-01", "gmv": 100.0, "orders": 20, "aov": 5.0},
            {"month": "2024-02", "gmv": 200.0, "orders": 15, "aov": 13.33},
            {"month": "2024-03", "gmv": 300.0, "orders": 10, "aov": 30.0},
        ]
    }
    _figure, summary = visuals.gmv_monthly_trend(analysis)
    assert summary["driver"] == "客单价"
    assert summary["peak_month"] == "2024-03"
    assert summary["trough_month"] == "2024-01"


def test_monthly_driver_is_none_with_a_single_month():
    """A single point has no correlation, so no driver is claimed."""
    analysis = {"monthly": [{"month": "2024-01", "gmv": 100.0, "orders": 20, "aov": 5.0}]}
    _figure, summary = visuals.gmv_monthly_trend(analysis)
    assert summary["driver"] is None
    assert summary["swing_ratio"] == 0.0


# --- pareto ------------------------------------------------------------------


def test_pareto_reports_the_sku_that_crosses_eighty_percent():
    analysis = {
        "products_top15": [
            {"product_normalized": "A", "gmv": 50.0, "gmv_share": 0.5, "cumulative_share": 0.5},
            {"product_normalized": "B", "gmv": 30.0, "gmv_share": 0.3, "cumulative_share": 0.8},
            {"product_normalized": "C", "gmv": 20.0, "gmv_share": 0.2, "cumulative_share": 1.0},
        ]
    }
    _figure, summary = visuals.product_pareto(analysis)
    assert summary["skus_for_80_percent"] == 2
    assert summary["top1_share"] == 0.5


def test_pareto_shows_full_product_names_and_keeps_legend_outside_plot():
    product_name = "华为平板 MatePad 11"
    analysis = {
        "products_top15": [
            {
                "product_normalized": "华为平板matepad11",
                "product_name": product_name,
                "gmv": 50.0,
                "gmv_share": 1.0,
                "cumulative_share": 1.0,
            }
        ]
    }
    figure, _summary = visuals.product_pareto(analysis)
    assert figure.axes[0].get_xticklabels()[0].get_text() == product_name
    assert len(figure.legends) == 1
    assert figure.axes[0].get_legend() is None


def test_pareto_returns_none_when_eighty_percent_is_never_reached():
    analysis = {
        "products_top15": [
            {"product_normalized": "A", "gmv": 10.0, "gmv_share": 0.1, "cumulative_share": 0.1},
            {"product_normalized": "B", "gmv": 10.0, "gmv_share": 0.1, "cumulative_share": 0.2},
        ]
    }
    _figure, summary = visuals.product_pareto(analysis)
    assert summary["skus_for_80_percent"] is None


# --- output ------------------------------------------------------------------


def test_build_all_figures_writes_every_png(tmp_path):
    analysis = {
        "monthly": [{"month": "2024-01", "gmv": 100.0, "orders": 20, "aov": 5.0}],
        "channel": _channel_rows(3),
        "products_top15": [
            {"product_normalized": "A", "gmv": 50.0, "gmv_share": 0.5, "cumulative_share": 0.5},
            {"product_normalized": "B", "gmv": 50.0, "gmv_share": 0.5, "cumulative_share": 1.0},
        ],
    }
    results = visuals.build_all_figures(analysis, _cleaned_frame(), output_dir=tmp_path)
    assert set(results) == set(visuals.FIGURE_FILENAMES)
    for key, result in results.items():
        assert result["path"] == tmp_path / visuals.FIGURE_FILENAMES[key]
        assert result["path"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert "summary" in result


def test_build_all_figures_without_output_dir_skips_writing():
    analysis = {
        "monthly": [{"month": "2024-01", "gmv": 100.0, "orders": 20, "aov": 5.0}],
        "channel": _channel_rows(2),
        "products_top15": [
            {"product_normalized": "A", "gmv": 50.0, "gmv_share": 0.5, "cumulative_share": 1.0},
        ],
    }
    results = visuals.build_all_figures(analysis, _cleaned_frame())
    assert all(result["path"] is None for result in results.values())


def test_figure_png_bytes_returns_a_png():
    figure, _summary = visuals.channel_share_ring({"channel": _channel_rows(2)})
    payload = visuals.figure_png_bytes(figure)
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"


def _small_analysis() -> dict:
    return {
        "monthly": [{"month": "2024-01", "gmv": 100.0, "orders": 20, "aov": 5.0}],
        "channel": _channel_rows(2),
        "products_top15": [
            {"product_normalized": "A", "gmv": 50.0, "gmv_share": 0.5, "cumulative_share": 1.0},
        ],
    }


def test_render_all_figures_returns_png_bytes():
    payloads = visuals.render_all_figures(_small_analysis(), _cleaned_frame())
    assert set(payloads) == set(visuals.FIGURE_FILENAMES)
    for result in payloads.values():
        assert result["png"][:8] == b"\x89PNG\r\n\x1a\n"
        assert "summary" in result


def test_render_all_figures_leaves_no_figure_open():
    """The dashboard renders on every rerun, so a leaked figure would pile up."""
    visuals._get_pyplot().close("all")
    visuals.render_all_figures(_small_analysis(), _cleaned_frame())
    assert visuals._get_pyplot().get_fignums() == []
