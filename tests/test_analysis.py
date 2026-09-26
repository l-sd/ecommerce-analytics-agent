"""The four business dimensions, plus the facade that assembles them.

``analyze_orders`` used to compute every metric inline; it is now a facade over
``ecommerce_analytics.analysis``. These tests pin the contract from both sides:

* the nine original top-level keys still look the same to the CLI and to the
  dashboard, so nothing downstream had to change;
* each new dimension carries its own 口径 and 局限, and when its source table is
  missing it reports *why* instead of rendering an empty table.

The two roll-up assertions (category, region) are the load-bearing ones: they are
what proves a dimension's numbers are the same numbers the KPI section shows,
rather than a parallel calculation that happens to look similar.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from ecommerce_analytics import visuals
from ecommerce_analytics.analysis import fulfilment as fulfilment_module
from ecommerce_analytics.analysis import valid_orders
from ecommerce_analytics.deliverables import write_html
from ecommerce_analytics.demo_data import CATALOG_COLUMNS, read_catalog, read_traffic, write_demo
from ecommerce_analytics.pipeline import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    analyze_orders,
    clean_orders,
    read_orders,
)

DEMO_ROWS = 3000
DEMO_SEED = 20240601
ORIGINAL_TOP_LEVEL_KEYS = ["notice", "definitions", "kpi", "channel", "monthly", "products_top15", "rfm"]
NEW_TOP_LEVEL_KEYS = ["sources", "traffic", "sales", "users", "fulfilment"]
DIMENSIONS = ["traffic", "sales", "users", "fulfilment"]
# 数据窗口只有一年，所以月份数、以及"迟发率"的分母都按这个窗口断言。
MONTHS_IN_WINDOW = 12


@pytest.fixture(scope="module")
def demo(tmp_path_factory) -> dict:
    """The full three-table demo, read back exactly as the CLI does."""
    work = tmp_path_factory.mktemp("analysis")
    orders_path = work / "synthetic_orders.csv"
    write_demo(orders_path, rows=DEMO_ROWS, seed=DEMO_SEED)
    cleaned, cleaning_log = clean_orders(read_orders(orders_path))
    traffic = read_traffic(work / "synthetic_traffic.csv")
    catalog = read_catalog(work / "synthetic_products.csv")
    return {
        "cleaned": cleaned,
        "cleaning_log": cleaning_log,
        "traffic": traffic,
        "catalog": catalog,
        "analysis": analyze_orders(cleaned, traffic=traffic, catalog=catalog),
    }


@pytest.fixture(scope="module")
def bare(tmp_path_factory) -> dict:
    """A bare 11-column upload: no traffic table, no product master.

    This is the case a real user hits when they upload the order sheet their
    platform exported, so every dimension has to degrade instead of crashing.
    """
    frame = pd.DataFrame(
        {
            "订单号": ["O0001", "O0002", "O0003", "O0004", "O0005"],
            "日期": ["2024-01-05", "2024-01-06", "2024-02-05", "2024-02-06", "2024-03-05"],
            "渠道": ["天猫", "抖音", "天猫", "抖音", None],
            "商品ID": ["P001", "P002", "P001", "P002", "P003"],
            "商品名称": ["甲", "乙", "甲", "乙", "丙"],
            "单价": ["100", "200", "100", "200", "300"],
            "数量": [1, 2, 1, 2, 1],
            "金额": ["100", "400", "100", "400", "300"],
            "用户ID": ["U001", "U002", "U001", "U003", "U004"],
            "收货省份": ["浙江", "广东", "浙江", "江苏", "广东"],
            "订单状态": ["已完成", "已退款", "已完成", "已完成", "已完成"],
        }
    )
    cleaned, cleaning_log = clean_orders(frame)
    return {
        "cleaned": cleaned,
        "cleaning_log": cleaning_log,
        "analysis": analyze_orders(cleaned),
    }


# --- facade compatibility ---------------------------------------------------


def test_the_original_top_level_keys_are_unchanged(demo):
    """The CLI writes these keys and the dashboard reads them; they are frozen."""
    analysis = demo["analysis"]
    for key in ORIGINAL_TOP_LEVEL_KEYS:
        assert key in analysis, key


def test_product_ranking_keeps_readable_names_for_chart_labels(bare):
    products = bare["analysis"]["products_top15"]
    assert {row["product_name"] for row in products} == {"甲", "乙", "丙"}


def test_the_five_new_top_level_keys_are_present(demo):
    analysis = demo["analysis"]
    for key in NEW_TOP_LEVEL_KEYS:
        assert key in analysis, key


def test_the_kpi_block_still_has_its_five_measures(demo):
    kpi = demo["analysis"]["kpi"]
    assert set(kpi) >= {"gmv", "orders", "aov", "customers", "items_per_order"}
    assert kpi["gmv"] > 0
    assert kpi["orders"] > 0


def test_the_analysis_survives_a_json_round_trip(demo):
    """The CLI persists the whole thing, so nothing may be a numpy scalar."""
    dumped = json.dumps(demo["analysis"], ensure_ascii=False)
    assert json.loads(dumped)["kpi"]["gmv"] == demo["analysis"]["kpi"]["gmv"]


def test_each_dimension_declares_its_scope_and_limits(demo):
    """A number without its 口径 is not usable in a report."""
    for dimension in DIMENSIONS:
        module = demo["analysis"][dimension]
        assert module["available"] is True, dimension
        assert module["reason"] is None, dimension
        assert module["definitions"], dimension
        assert module["limitations"], dimension


def test_the_sources_block_reports_what_was_supplied(demo):
    sources = demo["analysis"]["sources"]
    assert sources["orders"]["available"] is True
    assert sources["traffic"]["available"] is True
    assert sources["traffic"]["rows"] == len(demo["traffic"])
    assert sources["catalog"]["available"] is True
    assert sources["catalog"]["rows"] == len(demo["catalog"])


# --- 维度一：流量与转化 -------------------------------------------------------


def test_the_traffic_funnel_is_ordered_and_monotonic(demo):
    funnel = demo["analysis"]["traffic"]["funnel"]
    assert [row["stage"] for row in funnel] == ["曝光", "访客", "加购", "下单"]
    counts = [row["count"] for row in funnel]
    assert all(lower >= upper for lower, upper in zip(counts, counts[1:], strict=False))


def test_the_conversion_rate_uses_visitors_not_exposure(demo):
    """行业口径的转化率分母是访客数；用曝光数会得到一个好看但没有意义的数。"""
    traffic = demo["analysis"]["traffic"]
    totals = {row["stage"]: row["count"] for row in traffic["funnel"]}
    assert traffic["rates"]["下单转化率"] == pytest.approx(totals["下单"] / totals["访客"], abs=1e-4)
    assert traffic["rates"]["全链路转化率"] == pytest.approx(totals["下单"] / totals["曝光"], abs=1e-4)
    assert traffic["rates"]["下单转化率"] > traffic["rates"]["全链路转化率"]


def test_the_traffic_monthly_rows_cover_the_window(demo):
    monthly = demo["analysis"]["traffic"]["monthly"]
    assert len(monthly) == MONTHS_IN_WINDOW
    assert all(row["下单转化率"] is not None for row in monthly)


# --- 维度二：销售与商品 -------------------------------------------------------


def test_the_category_rollup_reproduces_the_valid_gmv(demo):
    """品类 GMV 必须与核心 KPI 同源，否则报告里会出现两个 GMV。"""
    analysis = demo["analysis"]
    values = analysis["validation_values"]
    total = sum(row["gmv"] for row in analysis["sales"]["category"])
    assert total == pytest.approx(values["gmv_from_amount"], abs=0.01)
    assert values["category_gmv_sum"] == pytest.approx(values["gmv_from_amount"], abs=0.01)


def test_the_category_shares_sum_to_one(demo):
    shares = [row["gmv_share"] for row in demo["analysis"]["sales"]["category"]]
    assert sum(shares) == pytest.approx(1.0, abs=1e-4)


def test_the_category_table_carries_average_order_value(demo):
    for row in demo["analysis"]["sales"]["category"]:
        assert row["aov"] == pytest.approx(row["gmv"] / row["orders"], rel=1e-4)


def test_the_brand_table_is_a_top_ten_slice_not_a_rollup(demo):
    """品牌来自商品主数据，只对能连上的订单成立，所以它是一张 TOP 表。

    它因此**不能**回算到总 GMV——把这一点写下来，是为了让"品牌合计对不上"
    看起来像设计而不是 bug。
    """
    analysis = demo["analysis"]
    brand = analysis["sales"]["brand"]
    assert len(brand) == 10
    total = sum(row["gmv"] for row in brand)
    assert 0 < total < analysis["validation_values"]["gmv_from_amount"]


def test_the_sell_through_denominator_comes_from_the_product_master(demo):
    """分母若改用订单明细反推，指标会恒等于 100%——这正是它必须来自主数据的原因。"""
    analysis = demo["analysis"]
    sell = analysis["sales"]["sell_through"]
    assert sell["available"] is True
    assert sell["on_sale_skus"] == int((demo["catalog"]["在售状态"] == "在售").sum())
    assert sell["sold_skus"] <= sell["on_sale_skus"]
    assert sell["sell_through_rate"] == pytest.approx(sell["sold_skus"] / sell["on_sale_skus"], abs=1e-4)
    assert 0 < sell["sell_through_rate"] < 1
    assert analysis["validation_values"]["sell_through_denominator"] == sell["on_sale_skus"]
    assert analysis["validation_values"]["sell_through_numerator"] == sell["sold_skus"]


def test_every_order_sku_is_registered_in_the_master(demo):
    sell = demo["analysis"]["sales"]["sell_through"]
    assert sell["unregistered_skus"] == []
    assert sell["unsold_skus"]
    assert len(sell["unsold_skus"]) == sell["on_sale_skus"] - sell["sold_skus"]


def test_the_refund_rate_uses_the_full_order_denominator(demo):
    """退款率的分母是全量订单（含退款与取消），核心 KPI 用的是有效订单。"""
    analysis = demo["analysis"]
    refund = analysis["sales"]["refund"]
    assert refund["orders"] == len(demo["cleaned"])
    assert refund["orders"] > analysis["kpi"]["orders"]
    assert refund["refund_rate"] == pytest.approx(refund["refund_orders"] / refund["orders"], abs=1e-4)


def test_the_refund_and_cancel_split_reproduces_the_absolute_total(demo):
    """有效 GMV + 退款金额 + 取消金额 == 全量金额绝对值之和。

    Same convention as the ``refund and cancel split`` validation check, which
    reads ``金额`` (the recomputed column) rather than the ``原金额`` original.
    """
    analysis = demo["analysis"]
    values = analysis["validation_values"]
    cleaned = demo["cleaned"]
    cancelled = float(cleaned.loc[cleaned["订单状态"] == "已取消", "金额"].sum())
    total_absolute = float(cleaned["金额"].abs().sum())
    assert total_absolute == pytest.approx(
        values["gmv_from_amount"] + values["refund_amount"] + cancelled, abs=0.01
    )
    assert values["refund_amount"] == pytest.approx(analysis["sales"]["refund"]["refund_amount"], abs=0.01)


def test_the_refund_reasons_are_recorded_and_share_sum_to_one(demo):
    reasons = demo["analysis"]["sales"]["refund"]["reasons"]
    assert reasons
    assert sum(row["share"] for row in reasons) == pytest.approx(1.0, abs=1e-4)


def test_the_refund_channel_table_uses_the_full_order_denominator(demo):
    by_channel = demo["analysis"]["sales"]["refund"]["by_channel"]
    assert sum(row["orders"] for row in by_channel) == len(demo["cleaned"])
    for row in by_channel:
        assert row["refund_rate"] == pytest.approx(row["refunds"] / row["orders"], abs=1e-4)


# --- 维度三：用户 ------------------------------------------------------------


def test_the_repurchase_rate_is_not_degenerate(demo):
    """The demo once had 200 customers and 2 250 orders, which pinned the
    repurchase rate at exactly 100%. A rate of 1.0 means the customer pool is
    too small to be interesting, so assert it sits strictly inside (0, 1)."""
    repurchase = demo["analysis"]["users"]["repurchase"]
    assert 0 < repurchase["repeat_rate"] < 1
    assert repurchase["orders_per_customer"] > 1
    assert repurchase["repeat_customers"] < repurchase["customers"]


def test_the_repurchase_rate_matches_its_own_counts(demo):
    repurchase = demo["analysis"]["users"]["repurchase"]
    assert repurchase["repeat_rate"] == pytest.approx(
        repurchase["repeat_customers"] / repurchase["customers"], abs=1e-4
    )


def test_the_frequency_buckets_partition_the_customer_base(demo):
    repurchase = demo["analysis"]["users"]["repurchase"]
    buckets = repurchase["frequency_buckets"]
    assert [row["bucket"] for row in buckets] == ["1 单", "2 单", "3-4 单", "5 单及以上"]
    assert sum(row["customers"] for row in buckets) == repurchase["customers"]
    assert sum(row["share"] for row in buckets) == pytest.approx(1.0, abs=1e-4)


def test_the_single_order_bucket_excludes_repeat_customers(demo):
    repurchase = demo["analysis"]["users"]["repurchase"]
    single = next(row for row in repurchase["frequency_buckets"] if row["bucket"] == "1 单")
    assert single["customers"] == repurchase["customers"] - repurchase["repeat_customers"]


def test_the_acquisition_curve_counts_first_orders_per_month(demo):
    """首单月份只对能解析日期的订单成立，所以全部订单都没日期的客户落在曲线之外。"""
    users = demo["analysis"]["users"]
    acquisition = users["acquisition"]
    assert len(acquisition) == MONTHS_IN_WINDOW
    months = [row["month"] for row in acquisition]
    assert months == sorted(months)

    # 与复购共用同一个有效订单基线，而不是各算各的。
    known = valid_orders(demo["cleaned"])
    known = known[known["用户ID"] != "未知"]
    first_order = known.groupby("用户ID")["日期"].min()
    assert first_order.isna().any(), "the gap this test explains has disappeared"
    assert sum(row["new_customers"] for row in acquisition) == int(first_order.notna().sum())
    assert int(first_order.notna().sum()) < users["repurchase"]["customers"]


def test_the_top_decile_concentration_is_a_share_of_valid_gmv(demo):
    concentration = demo["analysis"]["users"]["concentration"]
    assert 0 < concentration["top_gmv_share"] < 1
    assert concentration["top_customers"] == max(1, round(concentration["customer_count"] * 0.1))
    assert concentration["small_sample"] is False


def test_the_region_rollup_reproduces_the_valid_gmv(demo):
    analysis = demo["analysis"]
    values = analysis["validation_values"]
    total = sum(row["gmv"] for row in analysis["users"]["region"])
    assert total == pytest.approx(values["gmv_from_amount"], abs=0.01)
    assert values["region_gmv_sum"] == pytest.approx(values["gmv_from_amount"], abs=0.01)


def test_the_region_rows_are_ranked_by_gmv(demo):
    gmv = [row["gmv"] for row in demo["analysis"]["users"]["region"]]
    assert gmv == sorted(gmv, reverse=True)


def test_the_region_customer_count_never_exceeds_the_total(demo):
    total_customers = demo["analysis"]["users"]["repurchase"]["customers"]
    assert all(row["customers"] <= total_customers for row in demo["analysis"]["users"]["region"])


# --- 维度四：履约跟踪 ---------------------------------------------------------


def test_the_fulfilment_funnel_is_monotonic_and_matches_its_parts(demo):
    fulfilment = demo["analysis"]["fulfilment"]
    counts = [row["count"] for row in fulfilment["funnel"]]
    assert [row["stage"] for row in fulfilment["funnel"]] == ["下单", "发货", "签收"]
    assert counts[0] == len(demo["cleaned"])
    assert counts[1] == fulfilment["late"]["shipped_orders"]
    assert counts[2] == fulfilment["delivery"]["delivered_orders"]
    assert all(lower >= upper for lower, upper in zip(counts, counts[1:], strict=False))
    assert fulfilment["funnel_monotonic"] is True


def test_the_late_and_overdue_denominators_are_different_populations(demo):
    """迟发率分母 = 应发订单数；逾期率分母 = 已签收订单数。两者不可互换。"""
    fulfilment = demo["analysis"]["fulfilment"]
    cleaned = demo["cleaned"]
    # 发货时间由下单日期加上时效得到，所以有发货时间就一定有一个可解析的下单日期。
    assert fulfilment["late"]["shipped_orders"] == int(cleaned["发货时间"].notna().sum())
    assert fulfilment["delivery"]["delivered_orders"] == int(cleaned["签收时间"].notna().sum())
    assert fulfilment["delivery"]["delivered_orders"] < fulfilment["late"]["shipped_orders"]
    assert fulfilment["late"]["shipped_orders"] < len(cleaned)


def test_the_late_and_overdue_rates_match_their_own_counts(demo):
    fulfilment = demo["analysis"]["fulfilment"]
    late = fulfilment["late"]
    delivery = fulfilment["delivery"]
    assert late["late_rate"] == pytest.approx(late["late_orders"] / late["shipped_orders"], abs=1e-4)
    assert delivery["overdue_rate"] == pytest.approx(
        delivery["overdue_orders"] / delivery["delivered_orders"], abs=1e-4
    )


def test_the_industry_late_line_is_four_percent_everywhere(demo):
    """Two modules carry the constant; a report that quotes 4% must not be
    describing a threshold the analysis layer does not use."""
    assert fulfilment_module.INDUSTRY_LATE_THRESHOLD == visuals.INDUSTRY_LATE_THRESHOLD == 0.04
    late = demo["analysis"]["fulfilment"]["late"]
    assert late["industry_threshold"] == 0.04
    assert late["above_industry_line"] is (late["late_rate"] > 0.04)


def test_the_ship_lag_histogram_accounts_for_every_shipped_order(demo):
    fulfilment = demo["analysis"]["fulfilment"]
    histogram = fulfilment["ship_lag_histogram"]
    assert sum(row["orders"] for row in histogram) == fulfilment["ship_lag"]["count"]
    assert sum(row["share"] for row in histogram) == pytest.approx(1.0, abs=1e-4)
    assert [row["days"] for row in histogram] == sorted(row["days"] for row in histogram)


def test_the_ship_lag_summary_is_right_skewed(demo):
    """承诺时效多在 1-3 天，所以均值应当高于中位数。"""
    ship_lag = demo["analysis"]["fulfilment"]["ship_lag"]
    assert ship_lag["median"] < ship_lag["mean"] <= ship_lag["max"]
    assert ship_lag["max"] > 0


def test_the_carrier_table_is_ranked_by_late_rate(demo):
    carrier = demo["analysis"]["fulfilment"]["carrier"]
    assert carrier
    rates = [row["late_rate"] for row in carrier]
    assert rates == sorted(rates)
    assert all(row["物流商"] != "未知" for row in carrier)


def test_the_carrier_totals_add_up_to_the_shipped_orders(demo):
    fulfilment = demo["analysis"]["fulfilment"]
    assert sum(row["orders"] for row in fulfilment["carrier"]) == fulfilment["late"]["shipped_orders"]


def test_each_carrier_rate_matches_its_own_counts(demo):
    for row in demo["analysis"]["fulfilment"]["carrier"]:
        assert row["late_rate"] == pytest.approx(row["late_orders"] / row["orders"], abs=1e-4)
        assert row["delivered_orders"] <= row["orders"]


def test_the_fulfilment_monthly_rows_flag_small_samples(demo):
    monthly = demo["analysis"]["fulfilment"]["monthly"]
    assert len(monthly) == MONTHS_IN_WINDOW
    for row in monthly:
        assert row["small_sample"] is (row["shipped_orders"] < 5)


def test_the_fulfilment_monthly_totals_add_up_to_the_funnel(demo):
    fulfilment = demo["analysis"]["fulfilment"]
    assert sum(row["shipped_orders"] for row in fulfilment["monthly"]) == fulfilment["late"]["shipped_orders"]
    assert sum(row["delivered_orders"] for row in fulfilment["monthly"]) == fulfilment["delivery"]["delivered_orders"]


# --- 降级：只有 11 列的上传 ---------------------------------------------------


def test_the_required_column_contract_is_untouched():
    """``test_errors.py`` asserts ``columns == REQUIRED_COLUMNS``; that stays true."""
    assert len(REQUIRED_COLUMNS) == 11
    assert len(OPTIONAL_COLUMNS) == 7
    assert not set(REQUIRED_COLUMNS) & set(OPTIONAL_COLUMNS)


def test_a_bare_upload_still_produces_the_optional_columns(bare):
    """The shape is normalised so downstream code can address the columns; the
    *values* stay null, which is how absence is told apart from 未知."""
    cleaned = bare["cleaned"]
    for column in OPTIONAL_COLUMNS:
        assert column in cleaned.columns, column
    assert cleaned["商品品类"].isna().all()
    assert cleaned["物流商"].isna().all()
    assert cleaned["发货时间"].isna().all()
    assert cleaned["签收时间"].isna().all()
    assert cleaned["退款原因"].isna().all()
    assert bare["cleaning_log"]["optional_columns_absent"] == OPTIONAL_COLUMNS


def test_an_absent_dimension_is_not_reported_as_unknown(bare):
    """``fillna("未知")`` here would make the availability check lie: it would
    say the upload *had* a 商品品类 column whose values were all 未知."""
    cleaned = bare["cleaned"]
    assert not cleaned["商品品类"].eq("未知").any()
    assert not cleaned["物流商"].eq("未知").any()


def test_a_bare_upload_reports_why_each_dimension_is_missing(bare):
    analysis = bare["analysis"]
    assert analysis["traffic"]["available"] is False
    assert "未提供流量表" in analysis["traffic"]["reason"]
    assert analysis["fulfilment"]["available"] is False
    assert "未提供发货时间" in analysis["fulfilment"]["reason"]
    assert analysis["sales"]["sell_through"]["available"] is False
    assert "不能用订单明细反推" in analysis["sales"]["sell_through"]["reason"]
    assert analysis["sources"]["traffic"] == {"available": False, "rows": 0}
    assert analysis["sources"]["catalog"] == {"available": False, "rows": 0}


def test_a_bare_upload_keeps_the_order_only_dimensions_working(bare):
    """退款率与复购只依赖订单明细，因此必须继续给出数字。"""
    analysis = bare["analysis"]
    assert analysis["sales"]["available"] is True
    assert analysis["sales"]["refund"]["orders"] == len(bare["cleaned"])
    assert analysis["users"]["available"] is True
    assert analysis["users"]["repurchase"]["available"] is True
    assert analysis["users"]["region"]
    assert analysis["kpi"]["gmv"] > 0


def test_a_bare_upload_still_renders_a_complete_report(bare, tmp_path):
    """The report must name the missing dimensions rather than skip the section."""
    path = tmp_path / "report.html"
    write_html(path, bare["analysis"], bare["cleaning_log"])
    text = path.read_text(encoding="utf-8")

    for section in ["流量与转化", "销售与商品", "用户分析", "履约跟踪", "渠道分析", "月度趋势", "商品TOP10", "口径与局限"]:
        assert section in text, section
    assert "未提供流量表" in text
    assert "未提供发货时间" in text


def test_a_missing_catalog_disables_sell_through_and_brand_but_not_the_rest(demo):
    """品类来自订单表的列，品牌来自主数据表——所以只有后者随主数据消失。"""
    analysis = analyze_orders(demo["cleaned"], traffic=demo["traffic"])
    assert analysis["sales"]["sell_through"]["available"] is False
    assert "未提供商品主数据表" in analysis["sales"]["sell_through"]["reason"]
    assert analysis["sales"]["brand"] == []
    assert analysis["sales"]["category"]
    assert analysis["sales"]["refund"]["orders"] == len(demo["cleaned"])


def test_the_catalog_schema_is_what_the_sell_through_check_expects(demo):
    catalog = demo["catalog"]
    assert list(catalog.columns) == CATALOG_COLUMNS
    assert catalog["商品ID"].is_unique
    on_sale = int((catalog["在售状态"] == "在售").sum())
    assert on_sale > 0
    # 分母只数在售 SKU，而不是行数——一旦演示数据加入停售 SKU，这两者就会分开。
    assert demo["analysis"]["sales"]["sell_through"]["on_sale_skus"] == on_sale


def test_the_report_names_the_missing_companion_tables_in_its_limitations(bare, demo):
    """A reader has to be able to tell "no data" from "no orders of that kind"."""
    limitations = bare["analysis"]["sales"]["limitations"]
    assert any("未提供商品品类列" in item for item in limitations)
    assert any("未提供商品主数据表" in item for item in limitations)

    # 提供了主数据时，前一条不该再出现——否则局限说明会与实际不符。
    supplied = demo["analysis"]["sales"]["limitations"]
    assert not any("未提供商品品类列" in item for item in supplied)
    assert not any("未提供商品主数据表" in item for item in supplied)
