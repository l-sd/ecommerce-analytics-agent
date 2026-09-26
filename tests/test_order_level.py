from __future__ import annotations

import io
import json

import pandas as pd

from ecommerce_analytics.real_orders import (
    analyze_order_level,
    clean_order_level,
    read_order_level_stream,
    write_order_level_outputs,
)


def _raw() -> pd.DataFrame:
    return pd.DataFrame({
        "订单编号": ["A1", "A2", "A3"],
        "总金额": ["100.00", "80", "20"],
        "买家实际支付金额": ["90", "0", "20"],
        "收货地址 ": ["浙江", "浙江", "上海"],
        "订单创建时间": ["2020/02/01 10:00", "2020/02/01 11:00", "2020/02/02 12:00"],
        "订单付款时间 ": ["2020/02/01 10:05", "2020/02/01 11:02", "2020/02/02 12:03"],
        "退款金额": ["0", "0", "5"],
    })


def test_reads_headers_with_trailing_spaces_and_gb18030():
    payload = _raw().to_csv(index=False).encode("gb18030")
    frame = read_order_level_stream(io.BytesIO(payload), ".csv")

    assert "订单号" in frame
    assert "收货省份" in frame
    assert "付款时间" in frame


def test_order_level_metrics_and_absent_dimensions():
    cleaned, log = clean_order_level(_raw())
    analysis = analyze_order_level(cleaned)

    assert log["rows_after_deduplication"] == 3
    assert log["unparseable_or_missing_payment_dates"] == 0
    assert analysis["kpi"]["orders"] == 3
    assert analysis["kpi"]["orders_with_payment_timestamp"] == 3
    assert analysis["kpi"]["orders_with_positive_actual_payment"] == 2
    assert analysis["kpi"]["paid_amount"] == 110
    assert analysis["kpi"]["refund_orders"] == 1
    assert analysis["validation"]["daily_orders_reconcile"] is True
    assert analysis["availability"]["product"]["available"] is False
    assert analysis["availability"]["customer_rfm"]["available"] is False


def test_outputs_are_written_and_validation_is_recorded(tmp_path):
    cleaned, log = clean_order_level(_raw())
    analysis = analyze_order_level(cleaned)

    write_order_level_outputs(tmp_path, cleaned, log, analysis)

    assert {path.name for path in tmp_path.iterdir()} >= {
        "cleaned_orders.csv", "cleaning_log.json", "analysis.json", "order_analysis.xlsx",
        "report.html", "validation.json",
    }
    validation = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
    assert validation["status"] == "passed"
    report = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "清洗记录" in report
    assert "全部通过" in report
    assert "未提供用户 ID" in report
    assert pd.read_excel(tmp_path / "order_analysis.xlsx", sheet_name="核心指标").shape[0] > 0
