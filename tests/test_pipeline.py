from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from ecommerce_analytics.deliverables import (
    validate_outputs,
    write_excel,
    write_html,
)
from ecommerce_analytics.demo_data import generate_orders
from ecommerce_analytics.pipeline import analyze_orders, clean_orders, profile_raw

EXPECTED_PROFILE = {
    "rows": 3090,
    "unique_orders": 3000,
    "duplicate_rows": 90,
    "missing_dates": 46,
    "missing_or_unparseable_prices": 140,
    "missing_quantities": 57,
    "zero_quantities": 61,
    "negative_quantities": 284,
    "missing_amounts": 335,
    "checkable_amount_mismatches": 59,
    "missing_channels": 32,
    "missing_product_ids": 66,
    "missing_user_ids": 62,
    "missing_provinces": 33,
}


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = generate_orders(rows=3000, seed=20240601)
        cls.cleaned, cls.log = clean_orders(cls.raw)
        cls.analysis = analyze_orders(cls.cleaned)

    def test_demo_profile_is_reproducible(self) -> None:
        self.assertEqual(profile_raw(self.raw), EXPECTED_PROFILE)

    def test_cleaning_and_rollups(self) -> None:
        self.assertEqual(len(self.cleaned), 3000)
        values = self.analysis["validation_values"]
        self.assertAlmostEqual(values["gmv_from_amount"], values["gmv_from_price_times_quantity"], places=2)
        self.assertAlmostEqual(values["channel_gmv_sum"], values["gmv_from_amount"], places=2)
        self.assertAlmostEqual(
            values["monthly_gmv_sum"] + values["valid_gmv_with_missing_date"],
            values["gmv_from_amount"],
            places=2,
        )

    def test_excel_formulas_and_html_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_excel(output / "ecommerce_analysis.xlsx", self.cleaned, self.analysis, self.log)
            write_html(output / "report.html", self.analysis, self.log)
            validation = validate_outputs(output, self.cleaned, self.analysis, self.log)
            self.assertEqual(validation["status"], "passed")
            workbook = load_workbook(output / "ecommerce_analysis.xlsx", data_only=False)
            self.assertEqual(workbook["清洗明细"]["I2"].value, '=IF(OR(F2="",G2=""),"",F2*G2)')
            self.assertEqual(workbook["清洗明细"]["M2"].value, '=IF(OR(L2="已退款",L2="已取消"),"否","是")')
            workbook.close()


if __name__ == "__main__":
    unittest.main()

