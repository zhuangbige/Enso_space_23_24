# 2015–2023 ENSO Coupling Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible paired-event diagnosis showing where the 2015 and 2023 development-year sequences separate between ocean heat arrival, SST expression, upward surface heat exchange, convection, and westerly stress.

**Architecture:** One focused analysis module will load existing SODA3 audit values and local OISST/ERA5/GPCP/CPC products, calculate sign-consistent monthly anomalies, assemble event and seasonal tables, and render a single English evidence-chain figure. Tests will exercise anomaly detrending, area weighting, ERA5 sign conversion, season windows, and the audited arrival inputs before the full pipeline runs.

**Tech Stack:** Python 3.12, pandas, NumPy, xarray with netCDF4 engine, Matplotlib, pytest.

## Global Constraints

- Do not edit the current PowerPoint.
- Use 1982–2014 same-calendar-month linear expectations for OISST, ERA5, and GPCP anomalies; retain CPC's published OLR anomaly.
- Use cosine-latitude weights for spatial means.
- Treat ERA5 surface heat fluxes as downward-positive raw inputs and convert ocean-to-atmosphere heat loss to positive values.
- Use the eastern heat-budget box 10°S–5°N, 140°W–80°W; eastern coupling SST box 5°S–5°N, 140°W–110°W; central-Pacific convection box 5°S–5°N, 180°–140°W; and central-western Pacific stress box 5°S–5°N, 160°E–140°W.
- Plot in English without a figure-level title or small-print footnotes, preserve natural aspect ratios, and use fixed colors for 2015 and 2023.
- Interpret the heat-flux/convection/wind sequence as coordinated coupling evidence, not proof that surface heat loss unidirectionally causes westerlies.

---

### Task 1: Scientific calculation core

**Files:**
- Create: `scripts/compare_2015_2023_coupling_exchange.py`
- Create: `tests/test_compare_2015_2023_coupling_exchange.py`

**Interfaces:**
- Produces: `same_month_linear_anomaly(frame, value_column, baseline=(1982, 2014)) -> pandas.Series`
- Produces: `weighted_box_mean(field, lat0, lat1, lon0, lon1) -> xarray.DataArray`
- Produces: `to_upward_loss(latent_down, sensible_down, shortwave_down, longwave_down) -> dict[str, numpy.ndarray]`
- Produces: `SEASON_MONTHS: dict[str, tuple[int, int, int]]`
- Produces: `audited_arrival_table() -> pandas.DataFrame`

- [ ] **Step 1: Write failing tests for anomaly construction and flux signs**

```python
def test_same_month_linear_anomaly_removes_month_specific_trend():
    frame = synthetic_monthly_frame(1982, 2016)
    result = module.same_month_linear_anomaly(frame, "value")
    assert np.allclose(result.loc[frame.year <= 2014], 0.0, atol=1e-10)

def test_to_upward_loss_reverses_era5_downward_sign():
    result = module.to_upward_loss(
        np.array([-100.0]), np.array([-10.0]),
        np.array([200.0]), np.array([-50.0]),
    )
    assert result["latent_loss"][0] == 100.0
    assert result["sensible_loss"][0] == 10.0
    assert result["turbulent_loss"][0] == 110.0
    assert result["net_ocean_loss"][0] == -40.0
```

- [ ] **Step 2: Run the targeted tests and verify they fail because the module does not exist**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/pytest tests/test_compare_2015_2023_coupling_exchange.py -v`

Expected: FAIL during import of `scripts.compare_2015_2023_coupling_exchange`.

- [ ] **Step 3: Implement anomaly, weighted-mean, sign, season, and arrival helpers**

```python
ARRIVAL_VALUES = {
    2015: {"transport_140w_zj": 8.49, "east_ohc_gain_zj": 8.60},
    2023: {"transport_140w_zj": 9.90, "east_ohc_gain_zj": 11.12},
}

def to_upward_loss(latent_down, sensible_down, shortwave_down, longwave_down):
    latent_loss = -np.asarray(latent_down, dtype=float)
    sensible_loss = -np.asarray(sensible_down, dtype=float)
    return {
        "latent_loss": latent_loss,
        "sensible_loss": sensible_loss,
        "turbulent_loss": latent_loss + sensible_loss,
        "net_ocean_loss": -(
            np.asarray(shortwave_down, dtype=float)
            + np.asarray(longwave_down, dtype=float)
            + np.asarray(latent_down, dtype=float)
            + np.asarray(sensible_down, dtype=float)
        ),
    }
```

- [ ] **Step 4: Add tests for box weighting, season membership, and audited arrival values**

```python
def test_overlapping_season_windows_are_exact():
    assert module.SEASON_MONTHS["MAM"] == (3, 4, 5)
    assert module.SEASON_MONTHS["MJJ"] == (5, 6, 7)
    assert module.SEASON_MONTHS["JJA"] == (6, 7, 8)
    assert module.SEASON_MONTHS["SON"] == (9, 10, 11)

def test_audited_arrival_values_match_current_ppt():
    table = module.audited_arrival_table().set_index("year")
    assert table.loc[2015, "transport_140w_zj"] == 8.49
    assert table.loc[2023, "transport_140w_zj"] == 9.90
```

- [ ] **Step 5: Run Task 1 tests**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/pytest tests/test_compare_2015_2023_coupling_exchange.py -v`

Expected: all Task 1 tests PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/compare_2015_2023_coupling_exchange.py tests/test_compare_2015_2023_coupling_exchange.py
git commit -m "feat: add 2015 2023 coupling calculation core"
```

### Task 2: Local data assembly and seasonal diagnostics

**Files:**
- Modify: `scripts/compare_2015_2023_coupling_exchange.py`
- Modify: `tests/test_compare_2015_2023_coupling_exchange.py`
- Create at runtime: `data/derived/research_2026/enso_2015_2023_coupling_exchange_monthly.csv`
- Create at runtime: `data/derived/research_2026/enso_2015_2023_coupling_exchange_seasonal.csv`
- Create at runtime: `data/derived/research_2026/enso_2015_2023_coupling_exchange_audit.json`

**Interfaces:**
- Consumes: Task 1 helper functions.
- Produces: `build_monthly_table() -> pandas.DataFrame`
- Produces: `build_seasonal_table(monthly: pandas.DataFrame) -> pandas.DataFrame`
- Produces: `validate_monthly_table(monthly: pandas.DataFrame) -> dict[str, object]`

- [ ] **Step 1: Write a failing schema and sign-audit test**

```python
def test_build_monthly_table_has_two_complete_event_years():
    table = module.build_monthly_table()
    assert table.groupby("year")["month"].nunique().to_dict() == {2015: 12, 2023: 12}
    assert set(module.MONTHLY_OUTPUT_COLUMNS).issubset(table.columns)
    assert table[["sst_east_anom_c", "latent_loss_anom_wm2",
                  "minus_olr_cp_wm2", "tau_cwp_anom_nm2"]].notna().all().all()
```

- [ ] **Step 2: Run the schema test and verify it fails because the loaders are absent**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/pytest tests/test_compare_2015_2023_coupling_exchange.py::test_build_monthly_table_has_two_complete_event_years -v`

Expected: FAIL with missing `build_monthly_table`.

- [ ] **Step 3: Implement local loaders and monthly merge**

Load all 12 ERA5 coupling files for each of the two longitude pieces with `engine="netcdf4", chunks=None`, normalize longitudes to 0–360°, remove the duplicate 180° meridian, and compute the heat-budget and stress boxes. Merge those indices with the existing full-year OISST/GPCP table and CPC OLR monthly table by year and month. Calculate anomalies after merging raw indices, never after selecting only the two events.

- [ ] **Step 4: Implement seasonal aggregation with overlapping windows**

```python
SEASON_MONTHS = {
    "MAM": (3, 4, 5),
    "MJJ": (5, 6, 7),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
}
```

For every metric, save rows for 2015, 2023, and `2015_minus_2023`. Retain physical units rather than standardizing the outputs.

- [ ] **Step 5: Add numerical regression tests for the approved first-pass findings**

```python
def test_mjj_paired_diagnosis_matches_audited_first_pass():
    seasonal = module.build_seasonal_table(module.build_monthly_table())
    mjj = seasonal.query("season == 'MJJ'").set_index("year")
    assert mjj.loc[2015, "sst_east_raw_c"] == pytest.approx(27.88, abs=0.03)
    assert mjj.loc[2023, "sst_east_raw_c"] == pytest.approx(27.90, abs=0.03)
    assert mjj.loc[2015, "latent_loss_anom_wm2"] == pytest.approx(5.96, abs=0.08)
    assert mjj.loc[2023, "latent_loss_anom_wm2"] == pytest.approx(0.09, abs=0.08)
    assert mjj.loc[2015, "minus_olr_cp_wm2"] == pytest.approx(17.75, abs=0.08)
    assert mjj.loc[2023, "minus_olr_cp_wm2"] == pytest.approx(4.75, abs=0.08)
```

- [ ] **Step 6: Run the full test file**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/pytest tests/test_compare_2015_2023_coupling_exchange.py -v`

Expected: all tests PASS.

- [ ] **Step 7: Run the table pipeline and inspect outputs**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/python scripts/compare_2015_2023_coupling_exchange.py --tables-only`

Expected: monthly CSV has 24 rows; seasonal CSV has 12 rows; audit JSON reports no missing values, expected month counts, correct flux sign convention, and the four audited arrival values.

- [ ] **Step 8: Commit Task 2**

```bash
git add scripts/compare_2015_2023_coupling_exchange.py tests/test_compare_2015_2023_coupling_exchange.py data/derived/research_2026/enso_2015_2023_coupling_exchange_*.csv data/derived/research_2026/enso_2015_2023_coupling_exchange_audit.json
git commit -m "feat: assemble paired ENSO coupling diagnostics"
```

### Task 3: Evidence-chain figure and Chinese interpretation

**Files:**
- Modify: `scripts/compare_2015_2023_coupling_exchange.py`
- Create at runtime: `outputs/research_2026/enso_2015_2023_coupling_exchange/enso_2015_2023_coupling_exchange.png`
- Create at runtime: `outputs/research_2026/enso_2015_2023_coupling_exchange/enso_2015_2023_coupling_exchange.pdf`
- Create at runtime: `outputs/research_2026/enso_2015_2023_coupling_exchange/ENSO_2015_2023_COUPLING_EXCHANGE_CN.md`

**Interfaces:**
- Consumes: `build_monthly_table`, `build_seasonal_table`, and `audited_arrival_table`.
- Produces: `plot_evidence_chain(monthly, seasonal, arrival, output_png, output_pdf) -> None`
- Produces: `write_chinese_report(monthly, seasonal, arrival, output_path) -> None`

- [ ] **Step 1: Write a failing smoke test for plot and report outputs**

```python
def test_pipeline_writes_nonempty_figure_and_report(tmp_path):
    result = module.run_pipeline(output_dir=tmp_path)
    assert result.png.stat().st_size > 100_000
    assert result.pdf.stat().st_size > 20_000
    text = result.report.read_text(encoding="utf-8")
    assert "27.88" in text and "27.90" in text
    assert "不能据此证明" in text
```

- [ ] **Step 2: Run the smoke test and verify it fails before plotting is implemented**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/pytest tests/test_compare_2015_2023_coupling_exchange.py::test_pipeline_writes_nonempty_figure_and_report -v`

Expected: FAIL with missing `run_pipeline` or missing output files.

- [ ] **Step 3: Implement the English figure**

Create a 3-column by 3-row GridSpec with arrival bars spanning the first row left column, SST and heat-flux panels in the remaining first/second rows, and convection/precipitation/stress panels in the final row. Use `#D97706` for 2015 and `#0F8F83` for 2023. Use panel letters, physical units, direct endpoint labels, restrained horizontal grids, and no super-title. Keep the canvas at least 13.5 by 9.0 inches and never use an aspect setting that compresses the axes vertically.

- [ ] **Step 4: Implement the Chinese interpretation**

State the MJJ and SON paired values, identify the first sustained separation, distinguish latent from sensible heat exchange, and state explicitly that monthly co-evolution cannot establish the causal arrow because wind and evaporation are mutually coupled.

- [ ] **Step 5: Run all tests and the complete pipeline**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/pytest tests/test_compare_2015_2023_coupling_exchange.py -v`

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/python scripts/compare_2015_2023_coupling_exchange.py`

Expected: tests PASS and all five output artifacts are written.

- [ ] **Step 6: Validate generated CSV and image properties**

Run: `MPLCONFIGDIR=.matplotlib-cache .venv/bin/python /Users/daiyue/.codex/skills/weather-data-processing/scripts/validate_met_output.py data/derived/research_2026/enso_2015_2023_coupling_exchange_monthly.csv`

Run: `sips -g pixelWidth -g pixelHeight outputs/research_2026/enso_2015_2023_coupling_exchange/enso_2015_2023_coupling_exchange.png`

Expected: no missing target metrics; PNG width at least 4000 px and height at least 2700 px.

- [ ] **Step 7: Visually inspect the PNG at original detail**

Open the generated PNG and check every panel for clipped labels, misleading scales, compressed axes, inconsistent event colors, illegible units, and title/footnote violations. Revise and rerun until clean.

- [ ] **Step 8: Commit Task 3**

```bash
git add scripts/compare_2015_2023_coupling_exchange.py tests/test_compare_2015_2023_coupling_exchange.py data/derived/research_2026/enso_2015_2023_coupling_exchange_* outputs/research_2026/enso_2015_2023_coupling_exchange
git commit -m "feat: compare 2015 and 2023 coupling exchange"
```
