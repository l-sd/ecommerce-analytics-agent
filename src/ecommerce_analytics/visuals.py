"""Chart builders for the e-commerce analytics deliverables.

Every public builder returns ``(figure, summary)`` so that the same figure can be
embedded in the HTML report, exported to PNG for the README, and re-rendered live
inside the Streamlit dashboard, while ``summary`` carries the numbers that the
report text quotes.

The four figures follow one reading order -- time, channel, product, customer:

1. :func:`gmv_monthly_trend` -- is the business growing, and is the swing driven
   by order count or by basket size?
2. :func:`channel_share_ring` -- where does the revenue come from, and which
   channel is most efficient per order?
3. :func:`product_pareto` -- how concentrated is revenue across SKUs?
4. :func:`rfm_scatter` -- which customer groups deserve attention first?
"""

from __future__ import annotations

import io
import warnings
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from .pipeline import customer_rfm_table

# Ordered by how likely the font is to exist on each target platform.
CJK_FONT_CANDIDATES = [
    "Noto Sans CJK SC",      # Debian/Ubuntu: fonts-noto-cjk
    "Noto Sans SC",
    "Noto Sans CJK JP",      # some Noto packages ship only the JP family name
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",     # Debian/Ubuntu fallback
    "WenQuanYi Micro Hei",
    "Microsoft YaHei",       # Windows
    "SimHei",                # Windows
    "PingFang SC",           # macOS
    "Hiragino Sans GB",      # macOS
    "Arial Unicode MS",      # macOS
]

INK = "#17201d"
GREEN = "#175c4c"
AMBER = "#b66a19"
BLUE = "#3f6f9f"
GREY = "#9aa5a1"

SEGMENT_COLORS = {
    "重要价值客户": GREEN,
    "重要挽留客户": AMBER,
    "潜力客户": BLUE,
    "一般客户": GREY,
}

FIGURE_FILENAMES = {
    "monthly_trend": "fig1_monthly_trend.png",
    "channel_structure": "fig2_channel_structure.png",
    "product_pareto": "fig3_product_pareto.png",
    "rfm_matrix": "fig4_rfm_matrix.png",
}

_FONT_CACHE: str | None = None


def setup_chinese_font() -> str:
    """Point matplotlib at an installed CJK font and return the family name used.

    Falls back to DejaVu Sans with a warning when no CJK font is present. A
    font-less runner (bare CI container, slim cloud image) should degrade to
    boxes in the labels rather than fail the whole pipeline.
    """
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE

    from matplotlib import font_manager

    available = {font.name for font in font_manager.fontManager.ttflist}
    chosen = next((name for name in CJK_FONT_CANDIDATES if name in available), None)
    if chosen is None:
        warnings.warn(
            "No CJK font found; Chinese labels will render as boxes. "
            "Install fonts-noto-cjk on Debian/Ubuntu.",
            RuntimeWarning,
            stacklevel=2,
        )
        chosen = "DejaVu Sans"

    matplotlib.rcParams["font.sans-serif"] = [chosen, "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    _FONT_CACHE = chosen
    return chosen


def _get_pyplot():
    """Return ``matplotlib.pyplot`` with a non-interactive backend and CJK font.

    ``matplotlib.use`` has to run before pyplot is first imported, so this is the
    only place the module imports pyplot. Callers may also set the backend
    themselves beforehand (``MPLBACKEND=Agg`` in CI).

    The backend is compared exactly rather than by suffix: ``"TkAgg"`` and
    ``"QtAgg"`` also end in ``"agg"`` but still need a display, so a suffix check
    would leave matplotlib on an interactive backend and fail on a machine with a
    broken or absent Tk.

    The font is configured here rather than only in :func:`build_all_figures` so
    that calling a single builder directly -- as the dashboard and ad-hoc checks
    do -- cannot silently fall back to DejaVu Sans and render Chinese as boxes.
    """
    setup_chinese_font()
    if matplotlib.get_backend().lower() != "agg":
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _style_axes(ax) -> None:
    ax.grid(axis="y", color="#e3e7e5", linewidth=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d7ddd9")
    ax.tick_params(colors="#66736e", labelsize=9)


def _empty_figure(title: str, message: str):
    plt = _get_pyplot()
    fig, ax = plt.subplots(figsize=(7.0, 2.6), dpi=160)
    ax.text(0.5, 0.5, message, ha="center", va="center", color="#66736e", fontsize=11)
    ax.set_title(title, fontsize=12, color=INK, pad=10)
    ax.axis("off")
    return fig


def figure_png_bytes(figure, dpi: int = 160) -> bytes:
    """Serialise a figure to PNG bytes (used by the Streamlit dashboard cache)."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    buffer.seek(0)
    return buffer.read()


def gmv_monthly_trend(analysis: dict[str, Any]):
    """GMV per month with order count on a secondary axis."""
    plt = _get_pyplot()
    monthly = analysis.get("monthly") or []
    if not monthly:
        return _empty_figure("月度 GMV 趋势", "无可用月度数据"), {"summary": "无可用月度数据"}

    months = [str(row["month"]) for row in monthly]
    gmv = [float(row["gmv"]) for row in monthly]
    orders = [int(row["orders"]) for row in monthly]

    fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=160)
    ax.bar(months, gmv, width=0.6, color=GREEN, label="GMV")
    ax.set_ylabel("GMV（万元）", fontsize=10, color=INK)
    ax.set_xlabel("月份", fontsize=10, color=INK)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value / 10000:,.0f}"))
    _style_axes(ax)
    ax.tick_params(axis="x", rotation=45)

    twin = ax.twinx()
    twin.plot(months, orders, color=AMBER, marker="o", markersize=4, linewidth=1.8, label="订单数")
    twin.set_ylabel("有效订单数", fontsize=10, color=INK)
    twin.spines["top"].set_visible(False)
    twin.tick_params(colors="#66736e", labelsize=9)

    handles = ax.get_legend_handles_labels()[0] + twin.get_legend_handles_labels()[0]
    labels = ax.get_legend_handles_labels()[1] + twin.get_legend_handles_labels()[1]
    ax.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=2,
        fontsize=9,
        frameon=False,
    )
    ax.set_title("月度 GMV 与订单数趋势（模拟数据）", fontsize=12, color=INK, pad=30)

    peak = max(monthly, key=lambda row: row["gmv"])
    trough = min(monthly, key=lambda row: row["gmv"])
    swing = (peak["gmv"] - trough["gmv"]) / trough["gmv"] if trough["gmv"] else None

    # GMV = orders x AOV, so whichever series correlates more strongly with GMV
    # is the one explaining the monthly swing.
    aov = [float(row["aov"]) for row in monthly if row.get("aov") is not None]
    gmv_series = pd.Series(gmv)
    order_corr = gmv_series.corr(pd.Series(orders)) if len(gmv) > 1 else None
    aov_corr = gmv_series.corr(pd.Series(aov)) if len(aov) == len(gmv) and len(gmv) > 1 else None
    if order_corr is None or aov_corr is None or pd.isna(order_corr) or pd.isna(aov_corr):
        driver = None
    else:
        driver = "订单量" if order_corr >= aov_corr else "客单价"

    summary = {
        "peak_month": peak["month"],
        "peak_gmv": round(float(peak["gmv"]), 2),
        "trough_month": trough["month"],
        "trough_gmv": round(float(trough["gmv"]), 2),
        "swing_ratio": round(swing, 4) if swing is not None else None,
        "driver": driver,
        "corr_orders": round(float(order_corr), 4) if order_corr is not None and not pd.isna(order_corr) else None,
        "corr_aov": round(float(aov_corr), 4) if aov_corr is not None and not pd.isna(aov_corr) else None,
    }
    return fig, summary


def _contrast_text_color(facecolor) -> str:
    """Pick white or ink for text sitting on a filled wedge."""
    from matplotlib.colors import to_hex

    value = to_hex(facecolor).lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#ffffff" if luminance < 0.55 else INK


def channel_share_ring(analysis: dict[str, Any]):
    """Donut chart of GMV share by channel.

    The channel name lives in the legend rather than on the wedge: the
    "unknown" bucket is under 1% of GMV, so an outer label would collide with
    its neighbour. The wedge keeps only the percentage, and the legend carries
    the exact share for every channel including the sliver.
    """
    plt = _get_pyplot()
    channel = analysis.get("channel") or []
    if not channel:
        return _empty_figure("渠道 GMV 结构", "无可用渠道数据"), {"summary": "无可用渠道数据"}

    labels = [str(row["渠道"]) for row in channel]
    values = [float(row["gmv"]) for row in channel]
    shares = [float(row.get("gmv_share") or 0) for row in channel]
    # Cycle the palette so a dataset with more channels than colours still gets
    # one colour per wedge instead of silently sharing the last one.
    palette = [GREEN, AMBER, BLUE, "#7f9c8f", GREY, "#c9d2ce"]
    colors = [palette[index % len(palette)] for index in range(len(values))]

    def percent_label(pct: float) -> str:
        """``autopct`` receives the share in percent, not the raw value.

        Slivers thinner than 3% are left unlabelled because the text would not fit.
        """
        return f"{pct:.1f}%" if pct >= 3 else ""

    fig, ax = plt.subplots(figsize=(7.8, 3.9), dpi=160)
    # ``pie`` returns a 3-tuple whenever ``autopct`` is set, even with no
    # ``labels`` -- the middle element is then an empty list.
    wedges, _texts, autotexts = ax.pie(
        values,
        autopct=percent_label,
        startangle=90,
        colors=colors,
        pctdistance=0.79,
        wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 1.2},
        textprops={"fontsize": 9, "color": INK},
    )
    for wedge, autotext in zip(wedges, autotexts, strict=True):
        autotext.set_color(_contrast_text_color(wedge.get_facecolor()))
        autotext.set_fontsize(9)

    total = sum(values)
    ax.text(0, 0, f"有效 GMV\n{total / 10000:,.0f} 万", ha="center", va="center", fontsize=11, color=GREEN)
    ax.set_aspect("equal")
    ax.set_title("渠道 GMV 占比（模拟数据）", fontsize=12, color=INK, pad=12)

    handles = [
        Patch(facecolor=color, label=f"{name}  {share * 100:.1f}%")
        for name, share, color in zip(labels, shares, colors, strict=True)
    ]
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=9,
        labelcolor=INK,
        handlelength=1.2,
    )

    top = channel[0]
    best_aov = max(channel, key=lambda row: row.get("aov") or 0)
    summary = {
        "top_channel": top["渠道"],
        "top_channel_share": round(float(top["gmv_share"]), 4),
        "best_aov_channel": best_aov["渠道"],
        "best_aov": round(float(best_aov["aov"]), 2) if best_aov.get("aov") is not None else None,
        "channel_count": len(channel),
    }
    return fig, summary


def product_pareto(analysis: dict[str, Any], top_n: int = 15):
    """GMV bars for the top SKUs with a cumulative-share line."""
    plt = _get_pyplot()
    products = (analysis.get("products_top15") or [])[:top_n]
    if not products:
        return _empty_figure("商品 GMV 集中度", "无可用商品数据"), {"summary": "无可用商品数据"}

    names = [str(row["product_normalized"])[:10] for row in products]
    gmv = [float(row["gmv"]) for row in products]
    cumulative = [float(row.get("cumulative_share") or 0) * 100 for row in products]

    fig, ax = plt.subplots(figsize=(7.6, 3.6), dpi=160)
    ax.bar(range(len(names)), gmv, width=0.62, color=GREEN, label="单品 GMV")
    ax.set_ylabel("GMV（万元）", fontsize=10, color=INK)
    ax.set_xlabel("商品（按 GMV 降序）", fontsize=10, color=INK)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value / 10000:,.0f}"))
    _style_axes(ax)

    twin = ax.twinx()
    twin.plot(range(len(names)), cumulative, color=AMBER, marker="o", markersize=4, linewidth=1.8, label="累计占比")
    twin.axhline(80, color="#c25b4a", linewidth=1.0, linestyle="--")
    twin.text(2, 82, "80% 线", ha="left", va="bottom", fontsize=8, color="#c25b4a")
    twin.set_ylabel("累计 GMV 占比（%）", fontsize=10, color=INK)
    twin.set_ylim(0, 105)
    twin.spines["top"].set_visible(False)
    twin.tick_params(colors="#66736e", labelsize=9)

    handles = ax.get_legend_handles_labels()[0] + twin.get_legend_handles_labels()[0]
    labels = ax.get_legend_handles_labels()[1] + twin.get_legend_handles_labels()[1]
    ax.legend(handles, labels, loc="upper right", fontsize=9, frameon=False)
    ax.set_title(f"商品 GMV 集中度：TOP{len(names)} 帕累托（模拟数据）", fontsize=12, color=INK, pad=12)

    crossing = next((index + 1 for index, value in enumerate(cumulative) if value >= 80), None)
    summary = {
        "top_n": len(names),
        "top_n_cumulative_share": round(cumulative[-1] / 100, 4),
        "skus_for_80_percent": crossing,
        "top1_share": round(float(products[0]["gmv_share"]), 4),
    }
    return fig, summary


def rfm_scatter(cleaned: pd.DataFrame):
    """Customer scatter of recency against frequency, sized by monetary value.

    Uses the same :func:`customer_rfm_table` as the RFM summary so that segment
    colours here always match the ``rfm`` table in ``analysis.json``.
    """
    plt = _get_pyplot()
    valid = cleaned[cleaned["是否有效订单"] & cleaned["金额"].notna()]
    customers = customer_rfm_table(valid)
    if customers.empty:
        return _empty_figure("RFM 客户分层", "无可用客户数据"), {"summary": "无可用客户数据"}

    fig, ax = plt.subplots(figsize=(6.6, 4.2), dpi=160)
    monetary = customers["monetary"].astype(float)
    scale = 900 / monetary.max() if monetary.max() else 1
    for segment in ["重要价值客户", "重要挽留客户", "潜力客户", "一般客户"]:
        group = customers[customers["segment"] == segment]
        if group.empty:
            continue
        ax.scatter(
            group["recency_days"].astype(float),
            group["frequency"].astype(float),
            s=(group["monetary"].astype(float) * scale).clip(lower=18),
            color=SEGMENT_COLORS[segment],
            alpha=0.72,
            edgecolors="white",
            linewidths=0.7,
            label=f"{segment}（{len(group)} 人）",
        )
    ax.set_xlabel("R：距最近一次购买天数（越左越活跃）", fontsize=10, color=INK)
    ax.set_ylabel("F：购买次数", fontsize=10, color=INK)
    _style_axes(ax)
    ax.grid(axis="x", color="#eef1ef", linewidth=0.7)
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    ax.set_title("RFM 客户分层：活跃度 × 购买频次（点大小＝金额）", fontsize=12, color=INK, pad=12)

    ranked = customers.groupby("segment").agg(customers=("用户ID", "count"), gmv=("monetary", "sum"))
    ranked["customer_share"] = ranked["customers"] / ranked["customers"].sum()
    ranked["gmv_share"] = ranked["gmv"] / ranked["gmv"].sum()
    top_priority = ranked.sort_values("gmv_share", ascending=False).index[0]

    summary = {
        "customer_count": int(len(customers)),
        "segment_count": int(customers["segment"].nunique()),
        "top_gmv_segment": top_priority,
        "top_gmv_share": round(float(ranked.loc[top_priority, "gmv_share"]), 4),
        "top_gmv_customers": int(ranked.loc[top_priority, "customers"]),
    }
    return fig, summary


def _iter_figures(analysis: dict[str, Any], cleaned: pd.DataFrame):
    """Yield ``(key, figure, summary)`` for the four charts, in reading order."""
    yield "monthly_trend", *gmv_monthly_trend(analysis)
    yield "channel_structure", *channel_share_ring(analysis)
    yield "product_pareto", *product_pareto(analysis)
    yield "rfm_matrix", *rfm_scatter(cleaned)


def build_all_figures(
    analysis: dict[str, Any],
    cleaned: pd.DataFrame,
    output_dir: Path | None = None,
    dpi: int = 160,
) -> dict[str, Any]:
    """Render all four figures, optionally writing PNGs.

    Returns a mapping of figure key to ``{"path": Path | None, "summary": dict}``.
    """
    setup_chinese_font()
    plt = _get_pyplot()

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {}
    for key, figure, summary in _iter_figures(analysis, cleaned):
        path = None
        if output_dir is not None:
            path = output_dir / FIGURE_FILENAMES[key]
            figure.savefig(path, format="png", dpi=dpi, bbox_inches="tight")
        results[key] = {"path": path, "summary": summary}
        plt.close(figure)
    return results


def render_all_figures(
    analysis: dict[str, Any],
    cleaned: pd.DataFrame,
    dpi: int = 160,
) -> dict[str, dict[str, Any]]:
    """Render all four figures to PNG bytes.

    The dashboard needs pixels rather than files, and it must not hold open
    matplotlib figures across Streamlit reruns, so every figure is closed before
    this returns. Same builders, same summaries as :func:`build_all_figures`.
    """
    setup_chinese_font()
    plt = _get_pyplot()

    payloads: dict[str, dict[str, Any]] = {}
    for key, figure, summary in _iter_figures(analysis, cleaned):
        payloads[key] = {"png": figure_png_bytes(figure, dpi=dpi), "summary": summary}
        plt.close(figure)
    return payloads
