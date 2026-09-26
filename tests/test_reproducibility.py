"""The committed dataset must be reproducible from its documented seed.

``README`` promises the demo data can be regenerated, and the analysis numbers in
``artifacts/demo`` only stay meaningful if that promise holds. This turns the
promise into a check that runs on every platform in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ecommerce_analytics.demo_data import CARRIER_WEIGHTS, CARRIERS, _pick, write_demo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMMITTED_DATASET = PROJECT_ROOT / "data" / "synthetic_orders.csv"
COMMITTED_MANIFEST = PROJECT_ROOT / "data" / "synthetic_orders.manifest.json"
DOCUMENTED_ROWS = 3000
DOCUMENTED_SEED = 20240601
PORTFOLIO_ROWS = 4854


def _normalise(payload: bytes) -> bytes:
    """Ignore line-ending differences between checkouts and platforms."""
    return payload.replace(b"\r\n", b"\n")


@pytest.mark.skipif(not COMMITTED_DATASET.exists(), reason="committed dataset is absent")
def test_committed_dataset_matches_the_documented_seed(tmp_path):
    regenerated = tmp_path / "synthetic_orders.csv"

    write_demo(regenerated, rows=DOCUMENTED_ROWS, seed=DOCUMENTED_SEED)

    assert _normalise(regenerated.read_bytes()) == _normalise(COMMITTED_DATASET.read_bytes())


@pytest.mark.skipif(not COMMITTED_MANIFEST.exists(), reason="committed manifest is absent")
def test_committed_manifest_matches_the_documented_seed(tmp_path):
    regenerated = tmp_path / "synthetic_orders.csv"

    manifest = write_demo(regenerated, rows=DOCUMENTED_ROWS, seed=DOCUMENTED_SEED)

    assert manifest["seed"] == DOCUMENTED_SEED
    assert manifest["base_unique_orders"] == DOCUMENTED_ROWS
    assert manifest["rows_with_duplicates"] == DOCUMENTED_ROWS + manifest["duplicate_rows"]


def test_generation_is_deterministic_for_the_same_seed(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    write_demo(first, rows=500, seed=7)
    write_demo(second, rows=500, seed=7)

    assert first.read_bytes() == second.read_bytes()


def test_different_seeds_produce_different_data(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    write_demo(first, rows=500, seed=7)
    write_demo(second, rows=500, seed=8)

    assert first.read_bytes() != second.read_bytes()


def test_carrier_boundary_is_stable_across_python_versions():
    assert _pick(CARRIERS, CARRIER_WEIGHTS, 0.88) == "圆通"


def test_portfolio_demo_has_4999_reproducible_order_rows_and_companions(tmp_path):
    regenerated = tmp_path / "synthetic_orders.csv"
    manifest = write_demo(regenerated, rows=PORTFOLIO_ROWS, seed=DOCUMENTED_SEED)

    assert manifest["rows_with_duplicates"] == 4999
    assert manifest["base_unique_orders"] == PORTFOLIO_ROWS
    assert manifest["duplicate_rows"] == 145
    assert manifest["traffic_rows"] == 366 * 5
    assert manifest["catalog_rows"] == 50

    committed_dir = PROJECT_ROOT / "data" / "portfolio_demo"
    assert _normalise(regenerated.read_bytes()) == _normalise(
        (committed_dir / "synthetic_orders.csv").read_bytes()
    )
    assert _normalise((tmp_path / "synthetic_traffic.csv").read_bytes()) == _normalise(
        (committed_dir / "synthetic_traffic.csv").read_bytes()
    )
    assert _normalise((tmp_path / "synthetic_products.csv").read_bytes()) == _normalise(
        (committed_dir / "synthetic_products.csv").read_bytes()
    )
