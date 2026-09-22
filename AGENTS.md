# Project working rules

- Treat `data/synthetic_orders.csv`, `data/synthetic_traffic.csv`, and
  `data/synthetic_products.csv` as synthetic practice data, never as a real
  company's transactions.
- Preserve raw inputs. Write generated files under a caller-provided output
  directory.
- Keep metric definitions explicit. This project defines valid orders as rows
  whose status is neither `已退款` nor `已取消`.
- Traffic and conversion metrics may only come from the explicit synthetic
  traffic table. Never infer exposure, visitors, or conversion from the order
  detail -- the two sides reconcile through `下单数` and nothing else.
- Do not infer profit, ROI, or causal business impact. The data carries no cost,
  exposure provenance, or experiment design, so any such number would be invented.
- Report a missing dimension as `{"available": false, "reason": ...}` rather than
  rendering an empty table. Never fill an absent optional column with `未知`:
  absence and "unknown" are different states, and conflating them makes the
  availability check lie.
- Keep the denominators apart. 迟发率 divides by shipped orders, 逾期率 by
  delivered orders, 退款率 by all orders, and the core KPIs by valid orders.
  They are not interchangeable and must not be added together.
- Every report must include cleaning decisions, validation results, and known
  limitations.
- Before publishing changes, run `pytest` and `ruff check .`, then the two README
  demo commands from a clean environment. Note that
  `python -m unittest discover -s tests` only picks up the four `unittest`-style
  cases and silently skips the rest, so it is not a substitute for `pytest`.

