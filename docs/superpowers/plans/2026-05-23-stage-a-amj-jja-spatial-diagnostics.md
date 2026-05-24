# Stage A AMJ/JJA Spatial Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a NOAA fast-pass gridded AMJ/JJA spatial evidence layer comparing 2023 with 1982/1997/2015 strong El Nino events.

**Architecture:** Add pure compositing helpers first, then small OPeNDAP extraction scripts for OISST and GPCP. Save compact `.npz` grids and a CSV summary so spatial diagnostics can be verified against existing index/matrix values before plotting.

**Tech Stack:** Python standard library, NumPy, netCDF4 via Anaconda, existing `el_nino_decoupling` helpers, `unittest`.

---

## File Structure

- Create: `el_nino_decoupling/spatial.py`
  - Pure helpers for monthly climatology subtraction, seasonal grid means, comparable-event means, and region/grid means.
- Create: `tests/test_spatial.py`
  - Unit tests for AMJ/JJA and cross-year seasonal gridded compositing.
- Create: `scripts/extract_stage_a_oisst_spatial_opendap.py`
  - Extract OISST gridded AMJ/JJA 2023, comparable mean, and difference.
- Create: `scripts/extract_stage_a_gpcp_spatial_opendap.py`
  - Extract GPCP gridded AMJ/JJA 2023, comparable mean, and difference.
- Create: `scripts/build_stage_a_spatial_summary.py`
  - Read `.npz` products and write a summary CSV for key boxes.
- Create: `data/derived/research/stage_a_spatial_summary.csv`
  - Summary values by variable, season, case, and region.
- Update: `docs/data_source_log.md`
  - Log spatial OISST/GPCP products and caveats.
- Update: `reports/当前数据分析阶段总结.md`
  - Add Stage A spatial-data status after summary exists.

## Task 1: Pure Spatial Compositing Helpers

**Files:**
- Create: `tests/test_spatial.py`
- Create: `el_nino_decoupling/spatial.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_spatial.py` with:

```python
import unittest

from el_nino_decoupling.spatial import (
    difference_grid,
    grid_region_mean,
    seasonal_grid_mean,
)


class SpatialHelpersTest(unittest.TestCase):
    def test_seasonal_grid_mean_uses_event_year_months(self):
        records = [
            {"year": 2023, "month": 4, "values": [[1.0, 2.0], [3.0, 4.0]]},
            {"year": 2023, "month": 5, "values": [[2.0, 3.0], [4.0, 5.0]]},
            {"year": 2023, "month": 6, "values": [[3.0, 4.0], [5.0, 6.0]]},
        ]
        self.assertEqual(
            seasonal_grid_mean(records, 2023, (4, 5, 6)),
            [[2.0, 3.0], [4.0, 5.0]],
        )

    def test_seasonal_grid_mean_handles_cross_year_djf(self):
        records = [
            {"year": 2023, "month": 12, "values": [[1.0]]},
            {"year": 2024, "month": 1, "values": [[2.0]]},
            {"year": 2024, "month": 2, "values": [[3.0]]},
        ]
        self.assertEqual(seasonal_grid_mean(records, 2023, (12, 13, 14)), [[2.0]])

    def test_difference_grid_subtracts_cellwise(self):
        self.assertEqual(
            difference_grid([[3.0, 4.0]], [[1.0, 6.0]]),
            [[2.0, -2.0]],
        )

    def test_grid_region_mean_uses_lat_lon_bounds(self):
        values = [[1.0, 2.0], [3.0, 4.0]]
        lat = [-5.0, 5.0]
        lon = [180.0, 220.0]
        self.assertAlmostEqual(
            grid_region_mean(values, lat, lon, -6.0, 6.0, 170.0, 230.0),
            2.5,
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests/test_spatial.py
```

Expected:

```text
ModuleNotFoundError: No module named 'el_nino_decoupling.spatial'
```

- [ ] **Step 3: Implement helpers**

Create `el_nino_decoupling/spatial.py` with:

```python
from __future__ import annotations

import math


def seasonal_grid_mean(records: list[dict], event_year: int, months: tuple[int, ...]) -> list[list[float]]:
    lookup = {(int(row["year"]), int(row["month"])): row["values"] for row in records}
    selected = []
    for month in months:
        year = event_year
        actual_month = month
        if month > 12:
            year += 1
            actual_month = month - 12
        selected.append(lookup[(year, actual_month)])
    rows = len(selected[0])
    cols = len(selected[0][0])
    return [
        [
            sum(float(grid[row][col]) for grid in selected) / len(selected)
            for col in range(cols)
        ]
        for row in range(rows)
    ]


def difference_grid(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [float(left[row][col]) - float(right[row][col]) for col in range(len(left[0]))]
        for row in range(len(left))
    ]


def mean_grid(grids: list[list[list[float]]]) -> list[list[float]]:
    rows = len(grids[0])
    cols = len(grids[0][0])
    return [
        [
            sum(float(grid[row][col]) for grid in grids) / len(grids)
            for col in range(cols)
        ]
        for row in range(rows)
    ]


def grid_region_mean(
    values: list[list[float]],
    lat,
    lon,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> float:
    selected = []
    for lat_index, lat_value in enumerate(lat):
        if not (lat_min <= float(lat_value) <= lat_max):
            continue
        weight = math.cos(math.radians(float(lat_value)))
        for lon_index, lon_value in enumerate(lon):
            if lon_min <= float(lon_value) <= lon_max:
                value = float(values[lat_index][lon_index])
                if not math.isnan(value):
                    selected.append((value, weight))
    if not selected:
        return math.nan
    numerator = sum(value * weight for value, weight in selected)
    denominator = sum(weight for _, weight in selected)
    return numerator / denominator
```

- [ ] **Step 4: Verify helper tests**

Run:

```bash
python -m unittest tests/test_spatial.py
```

Expected:

```text
OK
```

## Task 2: Extract OISST Stage A Spatial Product

**Files:**
- Create: `scripts/extract_stage_a_oisst_spatial_opendap.py`
- Create: `data/interim/raw_validation/oisst_spatial_amj_jja.npz`

- [ ] **Step 1: Create extraction script**

Create a script that:

- Reads NOAA OISST monthly SST from D2.
- Region window: 30S-30N, 40E-340E.
- Time range: Jan 1982-Feb 2024.
- Climatology: 1982-2022.
- Seasons: AMJ and JJA.
- Events: 2023 and comparable years 1982, 1997, 2015.
- Saves `lat`, `lon`, and arrays named like `AMJ_2023`, `AMJ_comparable`, `AMJ_difference`, `JJA_2023`, `JJA_comparable`, `JJA_difference`.

- [ ] **Step 2: Run extraction**

Run with Anaconda netCDF4 library path:

```bash
DYLD_LIBRARY_PATH=/opt/anaconda3/pkgs/libjpeg-turbo-2.0.0-h1a28f6b_0/lib python scripts/extract_stage_a_oisst_spatial_opendap.py
```

Expected:

```text
data/interim/raw_validation/oisst_spatial_amj_jja.npz
```

## Task 3: Extract GPCP Stage A Spatial Product

**Files:**
- Create: `scripts/extract_stage_a_gpcp_spatial_opendap.py`
- Create: `data/interim/raw_validation/gpcp_spatial_amj_jja.npz`

- [ ] **Step 1: Create extraction script**

Create a script equivalent to the OISST extractor but for D3 GPCP precipitation:

- Region window: 30S-30N, 120E-80W.
- Variable: `precip`.
- Time range: Jan 1982-Feb 2024.
- Climatology: 1982-2022.
- Save the same AMJ/JJA 2023, comparable, and difference arrays.

- [ ] **Step 2: Run extraction**

Run:

```bash
DYLD_LIBRARY_PATH=/opt/anaconda3/pkgs/libjpeg-turbo-2.0.0-h1a28f6b_0/lib python scripts/extract_stage_a_gpcp_spatial_opendap.py
```

Expected:

```text
data/interim/raw_validation/gpcp_spatial_amj_jja.npz
```

## Task 4: Build Stage A Spatial Summary CSV

**Files:**
- Create: `scripts/build_stage_a_spatial_summary.py`
- Create: `data/derived/research/stage_a_spatial_summary.csv`

- [ ] **Step 1: Create summary script**

The script should read both `.npz` files and write region means for:

- OISST: Nino-3, TNA, TIO, Maritime Continent, W. Pacific warm pool.
- GPCP: central Pacific, eastern Pacific, full tropical Pacific, western-central Pacific.

Rows:

```text
dataset,variable,season,region,case,value,source_ids
```

where `case` is `2023`, `comparable`, or `difference`.

- [ ] **Step 2: Run summary**

Run:

```bash
python scripts/build_stage_a_spatial_summary.py
```

Expected:

```text
data/derived/research/stage_a_spatial_summary.csv
```

## Task 5: Update Reports And Data Log

**Files:**
- Modify: `docs/data_source_log.md`
- Modify: `reports/当前数据分析阶段总结.md`

- [ ] **Step 1: Add derived products to data log**

Add rows for Stage A OISST and GPCP spatial products, citing D2 and D3.

- [ ] **Step 2: Add Stage A paragraph to report**

Add a short section explaining whether spatial summaries support the matrix conclusion.

## Task 6: Verification

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m unittest tests/test_spatial.py tests/test_gpcp_seasonal_summary.py
```

Expected: `OK`

- [ ] **Step 2: Run full tests**

Run:

```bash
python -m unittest discover -s tests
```

Expected: `OK`

- [ ] **Step 3: Check outputs**

Run:

```bash
python -c "from pathlib import Path; [print(p, Path(p).exists(), Path(p).stat().st_size if Path(p).exists() else 0) for p in ['data/interim/raw_validation/oisst_spatial_amj_jja.npz','data/interim/raw_validation/gpcp_spatial_amj_jja.npz','data/derived/research/stage_a_spatial_summary.csv']]"
```

Expected: all paths exist and have non-zero size.
