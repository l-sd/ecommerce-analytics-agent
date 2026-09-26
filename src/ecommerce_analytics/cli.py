from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from .deliverables import (
    validate_outputs,
    write_cleaned_csv,
    write_excel,
    write_html,
    write_json,
    write_validation_markdown,
)
from .demo_data import read_catalog, read_traffic, write_demo
from .pipeline import analyze_orders, clean_orders, read_orders
from .real_orders import analyze_order_level, clean_order_level, read_order_level, write_order_level_outputs
from .visuals import build_all_figures

# Companion tables live next to the order sheet. When they are absent the run
# still succeeds and the dependent dimensions report themselves unavailable,
# which is what an upload of a bare order sheet should do.
TRAFFIC_FILENAME = "synthetic_traffic.csv"
CATALOG_FILENAME = "synthetic_products.csv"


def _load_companion(input_path: Path, filename: str, reader):
    candidate = Path(input_path).parent / filename
    if not candidate.exists():
        return None
    try:
        return reader(candidate)
    except ValueError as error:
        print(f"Skipping {filename}: {error}")
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecommerce_analytics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("generate-demo", help="Generate reproducible synthetic order data.")
    demo.add_argument("--rows", type=int, default=3000, help="Number of unique base orders.")
    demo.add_argument("--seed", type=int, default=20240601, help="Random seed.")
    demo.add_argument("--output", type=Path, default=Path("data/synthetic_orders.csv"))

    run = subparsers.add_parser("run", help="Run cleaning, analysis, reporting, and validation.")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument(
        "--no-figures",
        action="store_true",
        help="Skip chart rendering (faster runs; the HTML report then omits the chart section).",
    )
    return parser


def _render_figures(
    analysis: dict[str, Any],
    cleaned: pd.DataFrame,
    output_dir: Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Render the four analysis charts and return (filename -> path, insights)."""
    results = build_all_figures(analysis, cleaned, output_dir=output_dir / "figures")
    paths = {result["path"].name: result["path"] for result in results.values() if result["path"]}
    insights = {key: result["summary"] for key, result in results.items()}
    return paths, insights


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "generate-demo":
        manifest = write_demo(args.output, rows=args.rows, seed=args.seed)
        print(f"Generated {manifest['rows_with_duplicates']:,} synthetic rows at {args.output}")
        return

    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        raw = read_orders(args.input)
    except ValueError:
        # Public platform exports often have order-level fields but no item,
        # quantity, customer, or status fields. Route these through a separate
        # profile instead of fabricating values to satisfy the demo schema.
        order_level_raw = read_order_level(args.input)
        order_level_cleaned, order_level_log = clean_order_level(order_level_raw)
        order_level_analysis = analyze_order_level(order_level_cleaned)
        write_order_level_outputs(output_dir, order_level_cleaned, order_level_log, order_level_analysis)
        print(f"Order-level analysis completed. Output: {output_dir}")
        if not all(value is not False for value in order_level_analysis["validation"].values()):
            raise SystemExit(1) from None
        return

    cleaned, cleaning_log = clean_orders(raw)
    traffic = _load_companion(args.input, TRAFFIC_FILENAME, read_traffic)
    catalog = _load_companion(args.input, CATALOG_FILENAME, read_catalog)
    analysis = analyze_orders(cleaned, traffic=traffic, catalog=catalog)

    figures: dict[str, Path] = {}
    if not args.no_figures:
        figures, insights = _render_figures(analysis, cleaned, output_dir)
        analysis["figure_insights"] = insights

    write_cleaned_csv(output_dir / "cleaned_orders.csv", cleaned)
    write_json(output_dir / "cleaning_log.json", cleaning_log)
    write_json(output_dir / "analysis.json", analysis)
    write_excel(output_dir / "ecommerce_analysis.xlsx", cleaned, analysis, cleaning_log)
    write_html(output_dir / "report.html", analysis, cleaning_log, figures=figures)
    validation = validate_outputs(
        output_dir, cleaned, analysis, cleaning_log, figures=figures, traffic=traffic
    )
    write_json(output_dir / "validation.json", validation)
    write_validation_markdown(output_dir / "validation.md", validation)
    print(f"Pipeline {validation['status']}: {output_dir}")
    if validation["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
