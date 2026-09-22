"""Input-handling errors: wrong file type, missing columns, extra columns."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from ecommerce_analytics.pipeline import REQUIRED_COLUMNS, read_orders, read_orders_stream


def _valid_frame(rows: int = 2) -> pd.DataFrame:
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
            "用户ID": ["U001"] * rows,
            "收货省份": ["浙江"] * rows,
            "订单状态": ["已完成"] * rows,
        }
    )


def test_reads_valid_csv(tmp_path):
    path = tmp_path / "orders.csv"
    _valid_frame().to_csv(path, index=False, encoding="utf-8-sig")

    frame = read_orders(path)

    assert list(frame.columns) == REQUIRED_COLUMNS
    assert len(frame) == 2


def test_reads_csv_with_bom_and_extra_columns(tmp_path):
    path = tmp_path / "orders.csv"
    frame = _valid_frame().assign(备注=["忽略我", "忽略我"])
    frame.to_csv(path, index=False, encoding="utf-8-sig")

    loaded = read_orders(path)

    assert "备注" not in loaded.columns
    assert list(loaded.columns) == REQUIRED_COLUMNS


def test_unsupported_suffix_raises(tmp_path):
    path = tmp_path / "orders.txt"
    path.write_text("订单号,日期\n", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV or Excel"):
        read_orders(path)


def test_json_suffix_raises(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV or Excel"):
        read_orders(path)


def test_missing_columns_are_named_in_the_error(tmp_path):
    path = tmp_path / "orders.csv"
    _valid_frame().drop(columns=["单价", "订单状态"]).to_csv(path, index=False, encoding="utf-8-sig")

    with pytest.raises(ValueError) as excinfo:
        read_orders(path)

    message = str(excinfo.value)
    assert "Missing required columns" in message
    assert "单价" in message
    assert "订单状态" in message


def test_empty_csv_with_headers_is_accepted(tmp_path):
    path = tmp_path / "orders.csv"
    _valid_frame().iloc[0:0].to_csv(path, index=False, encoding="utf-8-sig")

    frame = read_orders(path)

    assert frame.empty
    assert list(frame.columns) == REQUIRED_COLUMNS


def test_reads_excel_sheet(tmp_path):
    path = tmp_path / "orders.xlsx"
    _valid_frame().to_excel(path, sheet_name="订单明细", index=False)

    frame = read_orders(path)

    assert list(frame.columns) == REQUIRED_COLUMNS
    assert len(frame) == 2


def test_excel_with_wrong_sheet_name_raises(tmp_path):
    path = tmp_path / "orders.xlsx"
    _valid_frame().to_excel(path, sheet_name="Sheet1", index=False)

    with pytest.raises(ValueError):
        read_orders(path)


# --- in-memory uploads (used by the dashboard) -------------------------------


def test_read_orders_stream_matches_the_path_reader(tmp_path):
    path = tmp_path / "orders.csv"
    _valid_frame().to_csv(path, index=False, encoding="utf-8-sig")

    from_disk = read_orders(path)
    from_memory = read_orders_stream(io.BytesIO(path.read_bytes()), ".csv")

    pd.testing.assert_frame_equal(from_disk, from_memory)


def test_read_orders_stream_reads_an_excel_upload(tmp_path):
    path = tmp_path / "orders.xlsx"
    _valid_frame().to_excel(path, sheet_name="订单明细", index=False)

    frame = read_orders_stream(io.BytesIO(path.read_bytes()), ".XLSX")

    assert list(frame.columns) == REQUIRED_COLUMNS
    assert len(frame) == 2


def test_read_orders_stream_rejects_an_unsupported_suffix():
    with pytest.raises(ValueError, match="CSV or Excel"):
        read_orders_stream(io.BytesIO(b"a,b\n1,2\n"), ".txt")


def test_read_orders_stream_names_missing_columns():
    payload = _valid_frame().drop(columns=["渠道"]).to_csv(index=False).encode("utf-8-sig")

    with pytest.raises(ValueError, match="渠道"):
        read_orders_stream(io.BytesIO(payload), ".csv")
