# Three-Box Wind–Heat-Fate Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible 13-event diagnostic that identifies which western, central, or eastern Pacific heat-loss pathway is most closely associated with physically matched wind anomalies, with 2015 and 2023 highlighted.

**Architecture:** A single focused analysis module will read the already-audited SODA3 three-box event budget, construct consistently detrended ERA5 wind indices, convert all heat-fate terms to a common positive-outward sign, and calculate pre-specified and discovery relationships. The same module will write deterministic CSV/JSON checkpoints, three English scientific figures, and a concise Chinese interpretation report. Existing budget-generation scripts and user-owned outputs remain unchanged.

**Tech Stack:** Python 3, pandas, NumPy, SciPy, xarray/netCDF4, Matplotlib, pytest; local SODA3 budget checkpoints and ERA5 NetCDF inputs.

## Global Constraints

- Boxes are fixed at 10°S–5°N and 0–300 m: west 160°E–180°, central 180°–140°W, east 140°W–80°W.
- Positive public heat-fate values always mean loss from the selected box.
- Phases are January–June year 0, July–December year 0, and January–May year +1.
- The primary sample is exactly 1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, and 2023.
- The budget residual remains an audit term and is never labeled as a physical loss mechanism.
- Main relationships must be pre-specified, physically interpretable, have matching Pearson/Spearman signs, and not be created solely by one highlighted event.
- No PowerPoint file is modified.
- Preserve all unrelated dirty-worktree files.

---

## File map

- Create `scripts/analyze_three_box_wind_heat_fate_relationships.py`: input discovery, heat-fate sign conversion, ERA5 wind indices, event aggregation, relationship statistics, figures, tables, JSON audit, and report orchestration.
- Create `tests/test_three_box_wind_heat_fate_relationships.py`: unit and integration checks for signs, phases, partial correlation, leverage diagnostics, audited event values, and deliverables.
- Create `outputs/research_2026/three_box_wind_heat_fate_relationships/THREE_BOX_WIND_HEAT_FATE_CN.md`: generated interpretation report.
- Generate ignored binary figures and derived checkpoints under `outputs/research_2026/three_box_wind_heat_fate_relationships/` and `data/derived/research_2026/`.
- Reuse without modification:
  - `data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`
  - `data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_monthly.csv`
  - `data/raw/era5/coupling_monthly_1deg/`
  - `data/raw/era5/coupling_meridional_stress_monthly_1deg/`
  - `data/raw/era5/era5_monthly_10m_wind_pmm_1deg_1982_2025.nc`
  - `data/derived/research_2026/jiang_ne_wind_h20_exit_event_table.csv`

---

### Task 1: Heat-fate event table and sign audit

**Files:**
- Create: `scripts/analyze_three_box_wind_heat_fate_relationships.py`
- Create: `tests/test_three_box_wind_heat_fate_relationships.py`

**Interfaces:**
- Consumes: `soda3_three_box_ohc_anomaly_budget_events.csv` with one row per event, phase, and box.
- Produces: `load_heat_fate_events(input_root: Path) -> pd.DataFrame`, `positive_outward_heat_fate(frame: pd.DataFrame) -> pd.DataFrame`, and `validate_heat_fate(frame: pd.DataFrame) -> dict[str, object]`.

- [ ] **Step 1: Write failing tests for positive-outward signs and exact phases**

```python
def test_positive_outward_conversion() -> None:
    source = pd.DataFrame({
        "west_theta_heat_in_zj": [2.0],
        "east_theta_heat_in_zj": [-3.0],
        "south_theta_heat_in_zj": [-4.0],
        "north_theta_heat_in_zj": [5.0],
        "surface_zj": [-6.0],
        "storage_change_zj": [-7.0],
    })
    result = analysis.positive_outward_heat_fate(source)
    assert result.loc[0, "west_face_loss_zj"] == -2.0
    assert result.loc[0, "east_face_loss_zj"] == 3.0
    assert result.loc[0, "southward_loss_zj"] == 4.0
    assert result.loc[0, "northward_loss_zj"] == -5.0
    assert result.loc[0, "surface_loss_zj"] == 6.0
    assert result.loc[0, "storage_loss_zj"] == 7.0

def test_phase_months_are_fixed() -> None:
    assert analysis.PHASE_MONTHS == {
        "arrival_Jan_Jun": (0, 1, 6),
        "redistribution_Jul_Dec": (0, 7, 12),
        "decay_Jan_May_next": (1, 1, 5),
    }
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: FAIL because `analyze_three_box_wind_heat_fate_relationships` does not exist.

- [ ] **Step 3: Implement constants, input discovery, and sign conversion**

```python
EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
BOXES = {"west": (160.0, 180.0), "central": (180.0, 220.0), "east": (220.0, 280.0)}
PHASE_MONTHS = {
    "arrival_Jan_Jun": (0, 1, 6),
    "redistribution_Jul_Dec": (0, 7, 12),
    "decay_Jan_May_next": (1, 1, 5),
}

def positive_outward_heat_fate(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["west_face_loss_zj"] = -output["west_theta_heat_in_zj"]
    output["east_face_loss_zj"] = -output["east_theta_heat_in_zj"]
    output["southward_loss_zj"] = -output["south_theta_heat_in_zj"]
    output["northward_loss_zj"] = -output["north_theta_heat_in_zj"]
    output["surface_loss_zj"] = -output["surface_zj"]
    output["storage_loss_zj"] = -output["storage_change_zj"]
    output["residual_audit_zj"] = output["residual_zj"]
    return output
```

`load_heat_fate_events` must rename `post_Jul_Dec` to `redistribution_Jul_Dec`, restrict to the 13 events and three boxes, enforce 117 rows, and preserve the audited dynamic-reference face transports.

- [ ] **Step 4: Add integration tests for audited 2015/2023 storage changes**

```python
def test_audited_arrival_storage_changes() -> None:
    table = analysis.load_heat_fate_events(analysis.discover_input_root())
    arrival = table.loc[table.phase.eq("arrival_Jan_Jun")].set_index(["event_year", "box"])
    assert arrival.loc[(2015, "central"), "storage_change_zj"] == pytest.approx(2.6285, abs=0.005)
    assert arrival.loc[(2023, "central"), "storage_change_zj"] == pytest.approx(0.8720, abs=0.005)
    assert arrival.loc[(2015, "east"), "storage_change_zj"] == pytest.approx(8.6048, abs=0.005)
    assert arrival.loc[(2023, "east"), "storage_change_zj"] == pytest.approx(11.1155, abs=0.005)
```

- [ ] **Step 5: Run Task 1 tests**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: PASS for sign, phase, row-count, and audited-value tests.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/analyze_three_box_wind_heat_fate_relationships.py tests/test_three_box_wind_heat_fate_relationships.py
git commit -m "feat: assemble three-box heat-fate events"
```

---

### Task 2: ERA5 wind indices for boxes, boundaries, and coupling regions

**Files:**
- Modify: `scripts/analyze_three_box_wind_heat_fate_relationships.py`
- Modify: `tests/test_three_box_wind_heat_fate_relationships.py`

**Interfaces:**
- Consumes: ERA5 monthly u10/v10, eastward stress, northward stress, and the established Jiang event index.
- Produces: `same_month_linear_anomaly`, `cosine_box_mean`, `load_monthly_wind_indices`, and `build_event_wind_table`.

- [ ] **Step 1: Write failing tests for calendar-month detrending and cosine weighting**

```python
def test_same_month_detrending_removes_monthly_linear_signal() -> None:
    frame = analysis.synthetic_monthly_signal(1982, 2024)
    anomaly = analysis.same_month_linear_anomaly(frame, "value", (1982, 2014))
    assert np.allclose(anomaly, 0.0, atol=1e-10)

def test_cosine_box_mean_weights_latitude() -> None:
    field = xr.DataArray([[0.0], [10.0]], dims=("lat", "lon"), coords={"lat": [0.0, 60.0], "lon": [220.0]})
    assert float(analysis.cosine_box_mean(field, 0, 60, 220, 220)) == pytest.approx(10.0 / 3.0)
```

- [ ] **Step 2: Run the two tests and verify they fail**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: FAIL because the wind helper functions are missing.

- [ ] **Step 3: Implement monthly wind indices**

Construct, for every month from 1982 through 2024:

- box-mean u10, v10, and scalar wind speed over each control volume;
- box-mean eastward stress;
- eastward stress at the 5°N and 10°S boundary bands for each box;
- `-∂τx/∂y` over northern and southern flanks;
- full stress curl where both stress components exist;
- central-western-Pacific u10/stress over 5°S–5°N, 140°E–160°W;
- the existing Jiang-region MJJ northeasterly index.

All ERA5 grid fields must be longitude-normalized to 0–360, latitude-sorted, cosine-weighted, and converted to 1982–2014 same-calendar-month linearly detrended anomalies.

- [ ] **Step 4: Extend missing 2023–2024 meridional stress only if the input audit reports absent months**

Run the existing CDS downloader with the exact variable and domain:

```bash
python3 scripts/fetch_era5_coupling_fields.py \
  --start-year 2023 --end-year 2024 \
  --months 01 02 03 04 05 06 07 08 09 10 11 12 \
  --area 10 120 -10 280 --grid 1.0 \
  --variables mean_northward_turbulent_surface_stress \
  --output-dir data/raw/era5/coupling_meridional_stress_monthly_1deg
```

Validate each file has two monthly records, the expected variable, the full split Pacific domain, and units of N m⁻² before it is used. If CDS access is unavailable, retain the all-event `-∂τx/∂y` predictor as primary and label full curl as a through-2022 sensitivity; do not impute 2023 full curl.

- [ ] **Step 5: Aggregate wind windows and test event completeness**

`build_event_wind_table` must emit one row per event and window for `MAM`, `MJJ`, `arrival_Jan_Jun`, `redistribution_Jul_Dec`, and `decay_Jan_May_next`. A test must assert 65 rows and no missing primary u10/eastward-stress predictors.

- [ ] **Step 6: Run Task 2 tests**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: PASS with 13 events × 5 windows and complete primary predictors.

- [ ] **Step 7: Commit Task 2**

```bash
git add scripts/analyze_three_box_wind_heat_fate_relationships.py tests/test_three_box_wind_heat_fate_relationships.py
git commit -m "feat: build three-box ERA5 wind indices"
```

---

### Task 3: Pre-specified wind–loss relationships and discovery matrix

**Files:**
- Modify: `scripts/analyze_three_box_wind_heat_fate_relationships.py`
- Modify: `tests/test_three_box_wind_heat_fate_relationships.py`

**Interfaces:**
- Consumes: positive-outward event heat-fate table and event wind-window table.
- Produces: `partial_correlation`, `relationship_statistics`, `build_prespecified_relationships`, and `build_discovery_matrix`.

- [ ] **Step 1: Write failing synthetic tests for partial correlation and leave-one-event range**

```python
def test_partial_correlation_removes_shared_control() -> None:
    control = np.arange(13, dtype=float)
    x = control + np.array([0, 1, -1, 1, -1, 0, 1, -1, 0, 1, -1, 0, 0], dtype=float)
    y = control - np.array([0, 1, -1, 1, -1, 0, 1, -1, 0, 1, -1, 0, 0], dtype=float)
    raw = np.corrcoef(x, y)[0, 1]
    adjusted = analysis.partial_correlation(x, y, control)
    assert raw > 0.8
    assert adjusted < -0.9

def test_relationship_statistics_reports_loeo_range() -> None:
    x = np.arange(13, dtype=float)
    result = analysis.relationship_statistics(x, 2.0 * x, np.zeros_like(x))
    assert result["pearson_r"] == pytest.approx(1.0)
    assert result["spearman_r"] == pytest.approx(1.0)
    assert result["loeo_r_min"] == pytest.approx(1.0)
    assert result["loeo_r_max"] == pytest.approx(1.0)
```

- [ ] **Step 2: Run the statistics tests and verify they fail**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: FAIL because relationship functions are missing.

- [ ] **Step 3: Implement the exact pre-specified pairing registry**

The registry must include, for all three boxes and both contemporaneous and MJJ-leading windows:

```python
PAIRINGS = {
    "zonal_faces": (["west_face_loss_zj", "east_face_loss_zj"], ["box_tau_x_anom_nm2", "cwp_u10_anom_ms"]),
    "north_boundary": (["northward_loss_zj"], ["tau_x_5n_anom_nm2", "north_curl_tx_anom_1e8_nm3", "jiang_ne925_mjj_ms"]),
    "south_boundary": (["southward_loss_zj"], ["tau_x_10s_anom_nm2", "south_curl_tx_anom_1e8_nm3"]),
    "surface": (["surface_loss_zj"], ["box_wind_speed_anom_ms", "box_tau_x_anom_nm2"]),
    "storage": (["storage_loss_zj"], ["box_tau_x_anom_nm2", "cwp_u10_anom_ms", "box_wind_speed_anom_ms"]),
}
```

Every response uses arrival-phase box storage change or the relevant western-face input as its single control. The output must include the predictor window, response phase, box, response, predictor, control, Pearson r/p, Spearman r/p, partial r, standardized slope, LOEO minimum/maximum, and the values for 1997/2015/2023.

- [ ] **Step 4: Build the complete discovery matrix without using it to redefine the primary registry**

Calculate every available wind predictor against every positive-outward heat-fate response for audit. Add a Benjamini–Hochberg q value, but preserve a `prespecified` Boolean so primary and discovery-only results cannot be confused.

- [ ] **Step 5: Add tests for relationship row uniqueness and highlighted-event values**

Assert no duplicate `(box, predictor_window, response_phase, response, predictor)` keys; each main relationship has `n=13`; and 2015/2023 values exactly match the joined source tables.

- [ ] **Step 6: Run Task 3 tests**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: PASS for synthetic statistics, registry uniqueness, 13-event completeness, and highlighted values.

- [ ] **Step 7: Commit Task 3**

```bash
git add scripts/analyze_three_box_wind_heat_fate_relationships.py tests/test_three_box_wind_heat_fate_relationships.py
git commit -m "feat: relate box heat losses to wind anomalies"
```

---

### Task 4: Scientific figures, audit, and Chinese result report

**Files:**
- Modify: `scripts/analyze_three_box_wind_heat_fate_relationships.py`
- Modify: `tests/test_three_box_wind_heat_fate_relationships.py`
- Create: `outputs/research_2026/three_box_wind_heat_fate_relationships/THREE_BOX_WIND_HEAT_FATE_CN.md`

**Interfaces:**
- Consumes: all tables from Tasks 1–3.
- Produces: `PipelineOutputs`, `make_fate_figure`, `make_relationship_matrix`, `make_scatter_figure`, `write_report`, and `run_pipeline`.

- [ ] **Step 1: Write a failing pipeline-output test**

```python
def test_pipeline_writes_tables_figures_audit_and_report(tmp_path: Path) -> None:
    result = analysis.run_pipeline(output_dir=tmp_path, input_root=analysis.discover_input_root())
    assert result.event_heat_csv.stat().st_size > 5_000
    assert result.relationship_csv.stat().st_size > 5_000
    assert result.fate_png.stat().st_size > 100_000
    assert result.matrix_png.stat().st_size > 100_000
    assert result.scatter_png.stat().st_size > 100_000
    text = result.report_md.read_text(encoding="utf-8")
    assert "2015" in text and "2023" in text
    assert "不能证明单向因果" in text
```

- [ ] **Step 2: Run the pipeline test and verify it fails**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py::test_pipeline_writes_tables_figures_audit_and_report -q`

Expected: FAIL because `run_pipeline` and output writers are missing.

- [ ] **Step 3: Implement a three-box fate figure**

Create an English, title-free, non-compressed figure with:

- a geographic locator strip showing the three boxes;
- three phase rows and three box columns;
- paired 2015/2023 bars for west/east face loss, north/south loss, surface loss, and storage loss;
- consistent 2015 orange `#D97706` and 2023 teal `#0F8F83`;
- a zero line, physical units, panel labels, and no small footnotes inside the plot.

- [ ] **Step 4: Implement the relationship matrix and scatter figure**

The matrix shows partial r only for pre-specified relationships, grouped by box and loss pathway. The scatter figure shows at most four relationships that satisfy the promotion rule; every panel highlights 1997, 2015, and 2023 and states n, Pearson r, Spearman r, and partial r without a figure-level title.

- [ ] **Step 5: Implement deterministic outputs and report**

Write:

- `three_box_wind_heat_fate_events.csv`;
- `three_box_wind_indices.csv`;
- `three_box_wind_heat_prespecified_relationships.csv`;
- `three_box_wind_heat_discovery_matrix.csv`;
- `three_box_wind_heat_fate_audit.json`;
- PNG/PDF versions of all three figures;
- `THREE_BOX_WIND_HEAT_FATE_CN.md`.

The report must lead with the 2015/2023 central-versus-east storage contrast, then state which heat-loss pathway has the strongest physically defensible wind relationship in each box, and explicitly separate association from causation.

- [ ] **Step 6: Run Task 4 tests and visually inspect all PNGs at original resolution**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: PASS. Open each PNG with the image viewer; reject clipped labels, compressed map panels, inconsistent axes, or unreadable annotations.

- [ ] **Step 7: Commit Task 4**

```bash
git add scripts/analyze_three_box_wind_heat_fate_relationships.py tests/test_three_box_wind_heat_fate_relationships.py outputs/research_2026/three_box_wind_heat_fate_relationships/THREE_BOX_WIND_HEAT_FATE_CN.md
git commit -m "feat: publish three-box wind heat-fate diagnostic"
```

---

### Task 5: Full verification and handoff

**Files:**
- Verify all files from Tasks 1–4.

**Interfaces:**
- Consumes: final implementation and generated outputs.
- Produces: verified branch ready for the user's integration choice.

- [ ] **Step 1: Run syntax and whitespace checks**

```bash
git diff --check
/Users/daiyue/Documents/Maryland/.venv/bin/python -m py_compile scripts/analyze_three_box_wind_heat_fate_relationships.py
```

- [ ] **Step 2: Run focused tests**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest tests/test_three_box_wind_heat_fate_relationships.py -q`

Expected: all focused tests pass.

- [ ] **Step 3: Run the full project suite**

Run: `/Users/daiyue/Documents/Maryland/.venv/bin/python -m pytest -q`

Expected: all tests pass with no new failures.

- [ ] **Step 4: Run the pipeline from a clean output target and audit results**

```bash
/Users/daiyue/Documents/Maryland/.venv/bin/python scripts/analyze_three_box_wind_heat_fate_relationships.py
```

Confirm 13 events, 117 heat-fate rows, 65 wind-window rows, no missing primary pairs, exact audited 2015/2023 storage checkpoints, valid JSON, and non-empty PNG/PDF/report files.

- [ ] **Step 5: Review the final diff and report exact evidence**

Run: `git status --short && git log --oneline -5`

Report the strongest defensible relationships, the 2015/2023 box-fate differences, test counts, output paths, limitations, and the branch integration choices. Do not modify the PPT.
