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
from .demo_data import write_demo
from .pipeline import analyze_orders, clean_orders, read_orders
from .visuals import build_all_figures


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
    raw = read_orders(args.input)
    cleaned, cleaning_log = clean_orders(raw)
    analysis = analyze_orders(cleaned)

    figures: dict[str, Path] = {}
    if not args.no_figures:
        figures, insights = _render_figures(analysis, cleaned, output_dir)
        analysis["figure_insights"] = insights

    write_cleaned_csv(output_dir / "cleaned_orders.csv", cleaned)
    write_json(output_dir / "cleaning_log.json", cleaning_log)
    write_json(output_dir / "analysis.json", analysis)
    write_excel(output_dir / "ecommerce_analysis.xlsx", cleaned, analysis, cleaning_log)
    write_html(output_dir / "report.html", analysis, cleaning_log, figures=figures)
    validation = validate_outputs(output_dir, cleaned, analysis, cleaning_log, figures=figures)
    write_json(output_dir / "validation.json", validation)
    write_validation_markdown(output_dir / "validation.md", validation)
    print(f"Pipeline {validation['status']}: {output_dir}")
    if validation["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
