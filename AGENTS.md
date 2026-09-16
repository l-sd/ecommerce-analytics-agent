# Project working rules

- Treat `data/synthetic_orders.csv` as synthetic practice data, never as a real
  company's transactions.
- Preserve raw inputs. Write generated files under a caller-provided output
  directory.
- Keep metric definitions explicit. This project defines valid orders as rows
  whose status is neither `已退款` nor `已取消`.
- Do not infer traffic, conversion, profit, ROI, or causal business impact from
  order-only data.
- Every report must include cleaning decisions, validation results, and known
  limitations.
- Before publishing changes, run `python -m unittest discover -s tests -v` and
  the two README demo commands from a clean environment.

