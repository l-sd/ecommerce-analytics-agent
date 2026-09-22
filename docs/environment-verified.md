# 环境验证记录

> 验证日期：2026-09-22
> 验证平台：Windows 11 (10.0.26100) · Python 3.12.5 (MSC v.1940 64-bit)
> 虚拟环境：独立 venv，非系统 Python

本文件记录一次**从零安装到全流程跑通**的实测结果，用来回答两个问题：

1. 依赖声明能否在一台干净机器上成功解析并安装？
2. 装完之后，流水线、图表和测试是否真的可复现？

## 一、依赖解析

修复前 `pyproject.toml` 声明 `requires-python = ">=3.11"` 与 `numpy>=2.3,<3`，这是一个**无法同时满足**的组合：numpy 2.5.x 系列不提供 cp311 wheel。实测证据：

```text
$ pip download numpy==2.5.3 --python-version 311 --only-binary=:all:
ERROR: Could not find a version that satisfies the requirement numpy==2.5.3
```

PyPI 元数据确认 numpy 2.5.3 的 `cp311` wheel 数量为 **0**。因此下限调整为 `numpy>=2.2,<3`，让 Python 3.11 解析到 2.4.x、Python 3.12 解析到 2.5.x。

修复后的实测安装结果：

```text
$ pip install -e ".[dev]"
Successfully installed ecommerce-analytics-agent-0.1.0
  matplotlib-3.11.2  numpy-2.5.3  openpyxl-3.1.5  pandas-3.0.6
  pytest-9.1.1  ruff-0.16.8
```

## 二、安装清单（`pip freeze`）

```text
colorama==0.4.6
contourpy==1.4.0
cycler==0.12.1
et_xmlfile==2.0.0
fonttools==4.65.0
iniconfig==2.3.0
kiwisolver==1.5.1
matplotlib==3.11.2
numpy==2.5.3
openpyxl==3.1.5
packaging==26.3
pandas==3.0.6
pillow==12.3.0
pluggy==1.6.0
Pygments==2.21.0
pyparsing==3.3.3
pytest==9.1.1
python-dateutil==2.9.0.post0
ruff==0.16.8
six==1.17.0
tzdata==2026.4
```

## 三、验证结论

| 检查项 | 结果 |
| --- | --- |
| `pip install -e ".[dev]"` 干净环境安装 | 通过 |
| 模拟数据可复现性（同种子重生成） | 通过，sha256 一致 |
| 完整流水线 `run` | 通过，10 项验证全部 PASSED |
| 自动化测试 | 通过，81 个测试全绿 |
| 代码风格 `ruff check src tests` | 通过，0 问题 |
| 四张业务图表渲染（中文无豆腐块） | 通过 |
| HTML 报告内嵌图表 | 通过，4 张图以 base64 内嵌，单文件可离线打开 |

**可复现性证据**：用同一随机种子重新生成数据，与仓库中已提交的文件逐字节一致。

```text
data/synthetic_orders.csv        sha256=ea4ecc065cc24af7  bytes=294607
（重新生成）                      sha256=ea4ecc065cc24af7  bytes=294607
```

## 四、本次修复的两个真实缺陷

这两个都不是"猜出来的风险"，而是在干净环境实测中被触发后定位的。

### 1. 依赖区间自相矛盾（阻断安装）

见上文第一节。原声明在 Python 3.11 上直接安装失败。

### 2. matplotlib 后端判定错误（阻断图表）

`visuals._get_pyplot()` 原本用后缀判断当前后端是否无头：

```python
if not str(matplotlib.get_backend()).lower().endswith("agg"):  # 错误
    matplotlib.use("Agg")
```

`"TkAgg"`、`"QtAgg"` 同样以 `"agg"` 结尾，因此这个判断会把**需要图形界面**的后端误判为无头后端，跳过切换。在本机（Tk 安装残缺）表现为 `plt.subplots()` 抛 `_tkinter.TclError: Can't find a usable tk.tcl`。

修正为精确比较：

```python
if matplotlib.get_backend().lower() != "agg":
    matplotlib.use("Agg")
```

这条缺陷在 Windows 开发机上才会暴露，在无 Tk 的 Linux 容器上会自动回退到 Agg 而掩盖问题。修复后 `tests/test_visuals.py` 用 `TkAgg` / `QtAgg` / `MacOSX` 参数化锁定了该行为。

## 五、复现方式

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"

python -m ecommerce_analytics generate-demo --rows 3000 --seed 20240601
python -m ecommerce_analytics run --input data/synthetic_orders.csv --output artifacts/demo
python -m pytest
ruff check src tests
```

预期输出：`Pipeline passed`，`artifacts/demo/validation.md` 中 10 项全部 `[PASS]`，测试全绿。
