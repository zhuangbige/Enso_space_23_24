# Seasonal Asynchronous Coupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next research stage: a reproducible seasonal asynchronous-coupling analysis for the 2023/24 El Nino, with cited data sources, literature-derived method choices, figures, and a Chinese research report.

**Architecture:** Keep the existing Peng et al. reproduction untouched as the baseline. Add a new research layer that computes seasonal coupling metrics, external-basin context, and figure-ready tables from local derived data first, then adds optional ERA5/OLR/MJO products when access is configured.

**Tech Stack:** Python standard library, NumPy/Pandas/Xarray where already used, Matplotlib, existing `el_nino_decoupling` package modules, existing `unittest` test suite, Markdown reports.

---

## File Structure

- Modify: `docs/data_source_log.md`
  - Add Zhao, Li & Pan 2025 and Yang & Li 2025 to the citation table.
  - Add future OLR/MJO/ERA5 source rows only when a script actually reads or downloads them.
- Create: `docs/literature_method_notes.md`
  - Summarize methods learned from Peng, Zhang, Kim, Zhao, Yang, Hong, and Lin.
  - Convert each method into "what we will borrow" and "what we will not duplicate".
- Modify: `el_nino_decoupling/regions.py`
  - Add any missing region definitions for Nino-3.4, CWP wind box, central-Pacific rainfall box, TNA, tropical Indian Ocean, Maritime Continent, and west Pacific warm pool.
- Create: `el_nino_decoupling/seasonal_matrix.py`
  - Hold pure functions for seasonal ratios, response efficiency, and matrix assembly.
- Create: `tests/test_seasonal_matrix.py`
  - Unit-test the seasonal matrix functions with small in-memory records.
- Create: `scripts/build_seasonal_asynchrony_matrix.py`
  - Read existing derived CSVs and write the season-variable matrix.
- Create: `scripts/plot_seasonal_asynchrony_matrix.py`
  - Produce a heatmap and bar/line hybrid figure for the new article.
- Create: `scripts/write_seasonal_asynchrony_report.py`
  - Generate a Chinese Markdown report that explains reproduction status, new research start, findings, data sources, and missing data.
- Create: `reports/季节不等时响应研究报告.md`
  - Generated report from the script above.
- Create: `data/derived/research/seasonal_asynchrony_matrix.csv`
  - Main matrix for Figure 2.
- Create: `data/derived/research/seasonal_asynchrony_figure.png`
  - Heatmap/bar figure for the new article.

## Task 1: Literature Methods And Citation Log

**Files:**
- Modify: `docs/data_source_log.md`
- Create: `docs/literature_method_notes.md`

- [ ] **Step 1: Update citation table**

Insert these rows after L6 in `docs/data_source_log.md`:

```markdown
| L7 | Zhao, Li & Pan 2025, *Climate Dynamics*, "Why zonal wind anomalies were decoupled to El Nino in July 2023" | https://link.springer.com/article/10.1007/s00382-025-07625-8 | July 2023 wind-SST decoupling mechanism | Uses July-focused diagnosis; points to tropical North Atlantic SST and Indian summer monsoon / Maritime Continent heating as factors in anomalous equatorial Pacific winds. |
| L8 | Yang & Li 2025, *Journal of Climate*, "Easterly Anomalies during El Nino in January 2024: What Caused the Decoupling?" | https://journals.ametsoc.org/view/journals/clim/38/23/JCLI-D-24-0689.1.xml | January 2024 easterly anomaly and mature-season mechanism | Decomposes January 2024 easterlies into El Nino response, MJO, and interdecadal/global-trend-related components. |
```

- [ ] **Step 2: Create method note document**

Create `docs/literature_method_notes.md` with:

```markdown
# Literature Method Notes For Seasonal Asynchronous Coupling

Access date: 2026-05-23.

## Method Borrowing Table

| Source ID | Paper | Diagnostic Style To Borrow | What This Project Adds |
|---|---|---|---|
| L1 | Peng et al. 2025 | Strong-event comparison; Pacific versus external-basin forcing logic; wind-feedback framing | Converts event-mean weak coupling into AMJ/JJA/SON/DJF seasonal response efficiency. |
| L2 | Zhang et al. 2025 | Rainfall and teleconnection suppression; tropical Indian and Atlantic warming context | Places rainfall/OLR in the same seasonal matrix as SST, wind, and SOI-like pressure. |
| L3 | Kim et al. 2025 | Development-stage easterly anomalies and west-central Pacific SST gradient | Tests whether the development-season wind failure is already visible in AMJ/JJA. |
| L4 | Hong et al. 2024 | North Atlantic Tripole / North Pacific SST pathway and weak wind-burst development | Keeps North Pacific/NPMM as an optional branch if early-season maps support it. |
| L5 | Lin et al. 2025 | NPMM contrast with 1997/98 and 2015/16 | Uses NPMM only as robustness context after tropical-basin diagnostics are stable. |
| L7 | Zhao, Li & Pan 2025 | July 2023 month-specific wind-SST decoupling; TNA and ISM/MC heating mechanisms | Embeds July as a zoom-in inside a four-season matrix, instead of making July the whole paper. |
| L8 | Yang & Li 2025 | January 2024 easterly decomposition using MJO and background/trend signals | Uses January as the mature-season zoom-in after seasonal DJF metrics are established. |

## New Article Logic

The new analysis should make a seasonal argument: 2023/24 did not merely have weak event-mean atmospheric coupling. The oceanic warming and external-basin background evolved ahead of, and partly against, canonical Pacific atmospheric responses. The paper should therefore diagnose timing and variable-by-variable synchrony, not only amplitude.
```

- [ ] **Step 3: Verify documentation changes**

Run:

```bash
python -m unittest tests/test_catalog.py tests/test_report.py
```

Expected:

```text
OK
```

## Task 2: Seasonal Matrix Pure Functions

**Files:**
- Create: `el_nino_decoupling/seasonal_matrix.py`
- Create: `tests/test_seasonal_matrix.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_seasonal_matrix.py`:

```python
import unittest

from el_nino_decoupling.seasonal_matrix import (
    build_matrix_records,
    response_efficiency,
    ratio_to_comparable,
)


class SeasonalMatrixTests(unittest.TestCase):
    def test_ratio_to_comparable_handles_signed_response(self):
        self.assertAlmostEqual(ratio_to_comparable(2.0, 1.0), 2.0)
        self.assertAlmostEqual(ratio_to_comparable(-0.5, 1.0), -0.5)

    def test_response_efficiency_uses_sst_ratio_denominator(self):
        self.assertAlmostEqual(response_efficiency(-0.25, 1.25), -0.2)

    def test_response_efficiency_returns_none_for_zero_sst_ratio(self):
        self.assertIsNone(response_efficiency(1.0, 0.0))

    def test_build_matrix_records_preserves_sources(self):
        rows = [
            {"season": "AMJ", "metric": "nino3_sst", "value_2023": 1.4, "value_comparable": 1.0, "source_ids": "D2"},
            {"season": "AMJ", "metric": "cwp_u", "value_2023": -0.2, "value_comparable": 1.0, "source_ids": "D4"},
        ]
        records = build_matrix_records(rows, sst_metric="nino3_sst")
        by_metric = {row["metric"]: row for row in records}
        self.assertAlmostEqual(by_metric["nino3_sst"]["ratio_to_comparable"], 1.4)
        self.assertAlmostEqual(by_metric["cwp_u"]["response_efficiency"], -0.14285714285714288)
        self.assertEqual(by_metric["cwp_u"]["source_ids"], "D4")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests/test_seasonal_matrix.py
```

Expected:

```text
ModuleNotFoundError: No module named 'el_nino_decoupling.seasonal_matrix'
```

- [ ] **Step 3: Implement pure functions**

Create `el_nino_decoupling/seasonal_matrix.py`:

```python
"""Seasonal coupling matrix utilities for the 2023/24 El Nino analysis."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def ratio_to_comparable(value_2023: float, value_comparable: float) -> float | None:
    """Return 2023/comparable ratio, preserving sign for atmospheric variables."""
    if value_comparable == 0:
        return None
    return value_2023 / value_comparable


def response_efficiency(response_ratio: float | None, sst_ratio: float | None) -> float | None:
    """Normalize an atmospheric response ratio by same-season Pacific SST strength."""
    if response_ratio is None or sst_ratio in (None, 0):
        return None
    return response_ratio / sst_ratio


def build_matrix_records(
    rows: Iterable[dict[str, Any]],
    *,
    sst_metric: str = "nino3_sst",
) -> list[dict[str, Any]]:
    """Build season-variable matrix records with ratios and response efficiency."""
    base_rows = list(rows)
    sst_ratio_by_season: dict[str, float | None] = {}
    records: list[dict[str, Any]] = []

    for row in base_rows:
        ratio = ratio_to_comparable(float(row["value_2023"]), float(row["value_comparable"]))
        if row["metric"] == sst_metric:
            sst_ratio_by_season[str(row["season"])] = ratio

    for row in base_rows:
        season = str(row["season"])
        metric = str(row["metric"])
        ratio = ratio_to_comparable(float(row["value_2023"]), float(row["value_comparable"]))
        sst_ratio = sst_ratio_by_season.get(season)
        records.append(
            {
                "season": season,
                "metric": metric,
                "value_2023": float(row["value_2023"]),
                "value_comparable": float(row["value_comparable"]),
                "ratio_to_comparable": ratio,
                "response_efficiency": 1.0 if metric == sst_metric else response_efficiency(ratio, sst_ratio),
                "source_ids": str(row.get("source_ids", "")),
            }
        )
    return records
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m unittest tests/test_seasonal_matrix.py
```

Expected:

```text
OK
```

## Task 3: Build Seasonal Asynchrony Matrix From Existing Data

**Files:**
- Create: `scripts/build_seasonal_asynchrony_matrix.py`
- Create: `data/derived/research/seasonal_asynchrony_matrix.csv`

- [ ] **Step 1: Inspect current input columns**

Run:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd
for path in [
    Path("data/derived/research/asynchronous_coupling_efficiency.csv"),
    Path("data/derived/research/external_basin_seasonal_summary.csv"),
]:
    print(path)
    df = pd.read_csv(path)
    print(df.columns.tolist())
    print(df.head(3).to_string(index=False))
PY
```

Expected:

```text
data/derived/research/asynchronous_coupling_efficiency.csv
...
data/derived/research/external_basin_seasonal_summary.csv
...
```

- [ ] **Step 2: Create matrix builder script**

Create `scripts/build_seasonal_asynchrony_matrix.py` with a conservative adapter that accepts the existing column names and fails clearly if required columns are missing:

```python
"""Build the seasonal asynchronous-coupling matrix from derived diagnostics."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from el_nino_decoupling.seasonal_matrix import build_matrix_records


ROOT = Path(__file__).resolve().parents[1]
ASYNC = ROOT / "data/derived/research/asynchronous_coupling_efficiency.csv"
EXTERNAL = ROOT / "data/derived/research/external_basin_seasonal_summary.csv"
OUT = ROOT / "data/derived/research/seasonal_asynchrony_matrix.csv"


def _require_columns(df: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = columns - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")


def load_rows() -> list[dict[str, object]]:
    async_df = pd.read_csv(ASYNC)
    external_df = pd.read_csv(EXTERNAL)
    _require_columns(async_df, {"season", "metric", "value_2023", "value_comparable"}, ASYNC)
    _require_columns(external_df, {"season", "region", "value_2023", "value_comparable"}, EXTERNAL)

    rows: list[dict[str, object]] = []
    for row in async_df.to_dict("records"):
        rows.append(
            {
                "season": row["season"],
                "metric": row["metric"],
                "value_2023": row["value_2023"],
                "value_comparable": row["value_comparable"],
                "source_ids": row.get("source_ids", "D2/D3/D4"),
            }
        )

    for row in external_df.to_dict("records"):
        rows.append(
            {
                "season": row["season"],
                "metric": f"sst_{row['region']}",
                "value_2023": row["value_2023"],
                "value_comparable": row["value_comparable"],
                "source_ids": "D2",
            }
        )
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records = build_matrix_records(load_rows(), sst_metric="nino3_sst")
    fieldnames = [
        "season",
        "metric",
        "value_2023",
        "value_comparable",
        "ratio_to_comparable",
        "response_efficiency",
        "source_ids",
    ]
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run script**

Run:

```bash
python scripts/build_seasonal_asynchrony_matrix.py
```

Expected:

```text
Wrote /Users/daiyue/Documents/Maryland/data/derived/research/seasonal_asynchrony_matrix.csv
```

## Task 4: Plot Seasonal Matrix Figure

**Files:**
- Create: `scripts/plot_seasonal_asynchrony_matrix.py`
- Create: `data/derived/research/seasonal_asynchrony_figure.png`

- [ ] **Step 1: Create plotting script**

Create `scripts/plot_seasonal_asynchrony_matrix.py`:

```python
"""Plot the seasonal asynchronous-coupling matrix."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data/derived/research/seasonal_asynchrony_matrix.csv"
OUT = ROOT / "data/derived/research/seasonal_asynchrony_figure.png"
SEASONS = ["AMJ", "JJA", "SON", "DJF"]


def main() -> None:
    df = pd.read_csv(MATRIX)
    pivot = df.pivot_table(index="metric", columns="season", values="ratio_to_comparable", aggfunc="mean")
    pivot = pivot.reindex(columns=SEASONS)
    fig_height = max(5, 0.35 * len(pivot.index))
    fig, ax = plt.subplots(figsize=(8.5, fig_height), constrained_layout=True)
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(data, cmap="RdBu_r", vmin=-2.5, vmax=2.5, aspect="auto")
    ax.set_xticks(np.arange(len(SEASONS)), SEASONS)
    ax.set_yticks(np.arange(len(pivot.index)), pivot.index)
    ax.set_title("Seasonal asynchronous coupling ratios: 2023/24 versus comparable strong El Nino events")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, label="2023/comparable ratio")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=220)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run plotting script**

Run:

```bash
python scripts/plot_seasonal_asynchrony_matrix.py
```

Expected:

```text
Wrote /Users/daiyue/Documents/Maryland/data/derived/research/seasonal_asynchrony_figure.png
```

## Task 5: Chinese Research Report

**Files:**
- Create: `scripts/write_seasonal_asynchrony_report.py`
- Create: `reports/季节不等时响应研究报告.md`

- [ ] **Step 1: Create report script**

Create `scripts/write_seasonal_asynchrony_report.py`:

```python
"""Write a Chinese report for the seasonal asynchronous-coupling stage."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data/derived/research/seasonal_asynchrony_matrix.csv"
OUT = ROOT / "reports/季节不等时响应研究报告.md"


def main() -> None:
    df = pd.read_csv(MATRIX)
    selected = df[df["season"].isin(["AMJ", "JJA", "SON", "DJF"])].copy()
    lines = [
        "# 2023/24 强厄尔尼诺季节不等时响应研究报告",
        "",
        "## 当前阶段判断",
        "",
        "目前工作已经从单纯复现进入新研究的第一层诊断。复现仍作为可信基线保留，但新的主线是比较 AMJ、JJA、SON、DJF 中 SST、风、气压、降水和外海盆 SST 是否同步响应。",
        "",
        "## 已完成内容",
        "",
        "- 已复现 Peng et al. 2025 的关键事实：2023/24 海洋增暖强，但风场和 SOI 响应弱。",
        "- 已用 OISST、GPCP 和 NCEP/NCAR fallback 做独立资料验证。",
        "- 已建立季节响应效率指标，用 2023/24 与 1982/83、1997/98、2015/16 等强事件对比。",
        "- 已把外海盆 SST 放入同一个季节框架，初步显示 AMJ/JJA 的 TNA、印度洋、海陆热带区偏暖显著。",
        "",
        "## 新研究核心表",
        "",
        selected.to_markdown(index=False),
        "",
        "## 数据来源",
        "",
        "- D1: Peng et al. 2025 source archive / Nature Geoscience article.",
        "- D2: NOAA OISST v2.1 via NOAA PSL OPeNDAP.",
        "- D3: GPCP monthly precipitation via NOAA PSL.",
        "- D4: NCEP/NCAR Reanalysis 1 via NOAA PSL fallback.",
        "",
        "## 下一步数据需求",
        "",
        "- ERA5 single levels and pressure levels: 用于论文级 u850、SLP、Walker circulation。",
        "- CPC Blended OLR: 用于 2023/24 对流独立约束。",
        "- RMM/MJO index 或日资料: 用于 January 2024 机制拆解。",
        "- ERSSTv5: 用于长记录 SST 稳健性检验。",
        "",
        "## 下一步图件",
        "",
        "- 图 1: 原文复现结果加季节响应效率。",
        "- 图 2: AMJ/JJA/SON/DJF 季节不等时响应矩阵。",
        "- 图 3: AMJ/JJA SST、风、SLP、降水/OLR 空间图。",
        "- 图 4: July 2023 与 January 2024 的机制放大图。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run report script**

Run:

```bash
python scripts/write_seasonal_asynchrony_report.py
```

Expected:

```text
Wrote /Users/daiyue/Documents/Maryland/reports/季节不等时响应研究报告.md
```

## Task 6: Verification

**Files:**
- Existing test suite and generated outputs.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m unittest tests/test_seasonal_matrix.py tests/test_asynchronous_coupling.py tests/test_external_basin_summary.py
```

Expected:

```text
OK
```

- [ ] **Step 2: Run full tests**

Run:

```bash
python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 3: Confirm generated outputs exist**

Run:

```bash
python - <<'PY'
from pathlib import Path
for path in [
    "data/derived/research/seasonal_asynchrony_matrix.csv",
    "data/derived/research/seasonal_asynchrony_figure.png",
    "reports/季节不等时响应研究报告.md",
]:
    p = Path(path)
    print(p, p.exists(), p.stat().st_size if p.exists() else 0)
PY
```

Expected:

```text
data/derived/research/seasonal_asynchrony_matrix.csv True <non-zero size>
data/derived/research/seasonal_asynchrony_figure.png True <non-zero size>
reports/季节不等时响应研究报告.md True <non-zero size>
```

## Self-Review

- Spec coverage: The plan covers literature learning, citation tracking, seasonal matrix construction, figure generation, Chinese reporting, and verification.
- Placeholder scan: No placeholder tasks are left; each task names exact files, commands, and expected outputs.
- Type consistency: `ratio_to_comparable`, `response_efficiency`, and `build_matrix_records` are introduced before scripts import them.
