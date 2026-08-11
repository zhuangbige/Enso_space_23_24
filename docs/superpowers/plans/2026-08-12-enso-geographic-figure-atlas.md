# ENSO Geographic Figure Atlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build five standalone, publication-oriented geographic climate figures for the ENSO three-question storyline without editing the existing PowerPoint.

**Architecture:** A small Python package loads and validates the audited event tables, prepares geographic encodings, and renders deterministic PNG/PDF figures. A separate fetcher obtains only the minimal SODA3 gridded fields needed for continuous OHC′ backgrounds; figures that rely only on existing trajectories and box budgets remain runnable without network access. Every figure writes an audit record containing source files, time windows, scales, and plotted headline values.

**Tech Stack:** Python 3.12, pandas, NumPy, xarray/netCDF4, Matplotlib, Cartopy, Pillow, unittest.

## Global Constraints

- Do not modify or re-export any PowerPoint file.
- All figure text must be English.
- Do not place a whole-figure title or decorative small print inside the figure.
- Use 1997, 2015, and 2023 as the highlighted events.
- Use 0–300 m OHC′ and complete fixed-depth enthalpy transport; do not use H20, D20, or a temperature threshold.
- Use the fixed boxes west 160°E–180°, central 180°–140°W, and east 140°W–80°W, all 10°S–5°N.
- Use development-year Jan–Jun for arrival and following Jan–May for fate.
- Use the current audited CSV values for box-integrated storage and boundary terms; do not infer those values from map pixels.
- Comparable event panels must use identical geographic extents, color limits, and arrow scales.
- Save each figure as a 300 dpi PNG and vector PDF under `outputs/research_2026/enso_geographic_figure_atlas_20260812/`.

---

## File Structure

- Create `scripts/enso_geographic_figures/__init__.py`: public package exports.
- Create `scripts/enso_geographic_figures/config.py`: immutable event, box, phase, palette, and output definitions.
- Create `scripts/enso_geographic_figures/data.py`: audited CSV loaders, longitude conversion, event extraction, and numeric validation.
- Create `scripts/enso_geographic_figures/plotting.py`: shared Cartopy axes, arrow scaling, color normalization, and export helpers.
- Create `scripts/enso_geographic_figures/figures.py`: the five figure builders.
- Create `scripts/fetch_soda3_geographic_figure_fields.py`: minimal OPeNDAP extraction and OHC′ map preparation.
- Create `scripts/build_enso_geographic_figure_atlas.py`: command-line orchestration, audit JSON, and montage creation.
- Create `tests/test_enso_geographic_figure_atlas.py`: data-contract, sign, scaling, and artifact tests.
- Create `outputs/research_2026/enso_geographic_figure_atlas_20260812/`: final PNG, PDF, audit JSON, and montage.

---

### Task 1: Lock the scientific data contract

**Files:**
- Create: `scripts/enso_geographic_figures/__init__.py`
- Create: `scripts/enso_geographic_figures/config.py`
- Create: `scripts/enso_geographic_figures/data.py`
- Create: `tests/test_enso_geographic_figure_atlas.py`

**Interfaces:**
- Produces: `load_trajectory_data() -> tuple[pd.DataFrame, pd.DataFrame]`.
- Produces: `load_budget_events() -> pd.DataFrame`.
- Produces: `load_hovmoller() -> pd.DataFrame`.
- Produces: `extract_event_budget(event: int, phase: str, box: str) -> dict[str, float]`.
- Produces: `to_display_longitude(lon_deg_e: np.ndarray) -> np.ndarray`.

- [ ] **Step 1: Write failing tests for the fixed domains and authoritative event values**

```python
from scripts.enso_geographic_figures.config import BOXES, EVENTS
from scripts.enso_geographic_figures.data import extract_event_budget


def test_fixed_domains_and_events():
    assert EVENTS == (1997, 2015, 2023)
    assert BOXES["west"] == (160.0, 180.0, -10.0, 5.0)
    assert BOXES["central"] == (180.0, 220.0, -10.0, 5.0)
    assert BOXES["east"] == (220.0, 280.0, -10.0, 5.0)


def test_east_box_arrival_values_match_audited_csv():
    expected = {
        1997: (16.96, 17.32),
        2015: (8.49, 8.60),
        2023: (9.90, 11.12),
    }
    for event, (inflow, gain) in expected.items():
        row = extract_event_budget(event, "arrival_Jan_Jun", "east")
        assert round(row["west_theta_heat_in_zj"], 2) == inflow
        assert round(row["storage_change_zj"], 2) == gain


def test_east_box_fate_values_match_audited_csv():
    expected_loss = {1997: 21.76, 2015: 19.89, 2023: 15.95}
    for event, loss in expected_loss.items():
        row = extract_event_budget(event, "decay_Jan_May_next", "east")
        assert round(-row["storage_change_zj"], 2) == loss
```

- [ ] **Step 2: Run the focused tests and verify import failure**

Run: `.venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: FAIL because `scripts.enso_geographic_figures` does not exist.

- [ ] **Step 3: Implement immutable configuration and validated loaders**

```python
EVENTS = (1997, 2015, 2023)
BOXES = {
    "west": (160.0, 180.0, -10.0, 5.0),
    "central": (180.0, 220.0, -10.0, 5.0),
    "east": (220.0, 280.0, -10.0, 5.0),
}
PHASES = {
    "arrival": "arrival_Jan_Jun",
    "fate": "decay_Jan_May_next",
}


def extract_event_budget(event: int, phase: str, box: str) -> dict[str, float]:
    frame = load_budget_events()
    selected = frame.loc[
        (frame.event_year == event) & (frame.phase == phase) & (frame.box == box)
    ]
    if len(selected) != 1:
        raise ValueError(f"Expected one budget row, found {len(selected)}")
    return selected.iloc[0].to_dict()
```

The loader must reject missing columns, duplicate event/phase/box keys, non-finite headline values, trajectory positions outside 0–360° longitude or ±90° latitude, and Hovmöller data without all three events.

- [ ] **Step 4: Run tests and verify the data contract passes**

Run: `.venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: PASS for fixed domains, arrival values, fate values, trajectory ranges, and longitude conversion.

- [ ] **Step 5: Commit the data-contract unit**

```bash
git add scripts/enso_geographic_figures tests/test_enso_geographic_figure_atlas.py
git commit -m "feat: lock ENSO geographic figure data contract"
```

---

### Task 2: Build the shared geographic plotting system

**Files:**
- Create: `scripts/enso_geographic_figures/plotting.py`
- Modify: `tests/test_enso_geographic_figure_atlas.py`

**Interfaces:**
- Consumes: `BOXES`, `EVENTS`, and validated data frames from Task 1.
- Produces: `create_pacific_axes(fig, spec) -> np.ndarray`.
- Produces: `draw_box_boundaries(ax, emphasize_gate: float | None = None) -> None`.
- Produces: `arrow_width_zj(value: float, max_abs: float) -> float`.
- Produces: `save_figure_pair(fig, stem: str, output_dir: Path) -> tuple[Path, Path]`.

- [ ] **Step 1: Add failing tests for arrow scaling and deterministic exports**

```python
def test_arrow_scale_is_monotonic_and_sign_independent():
    assert arrow_width_zj(0.0, 20.0) == 0.0
    assert arrow_width_zj(10.0, 20.0) < arrow_width_zj(20.0, 20.0)
    assert arrow_width_zj(-10.0, 20.0) == arrow_width_zj(10.0, 20.0)


def test_export_creates_png_and_pdf(tmp_path):
    fig = plt.figure(figsize=(4, 2))
    png, pdf = save_figure_pair(fig, "probe", tmp_path)
    assert png.name == "probe.png" and pdf.name == "probe.pdf"
    assert png.stat().st_size > 5_000
    assert pdf.stat().st_size > 1_000
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `.venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: FAIL because plotting helpers are undefined.

- [ ] **Step 3: Implement shared map and export helpers**

Use `cartopy.crs.PlateCarree(central_longitude=180)` for map display and `ccrs.PlateCarree()` for data transforms. Use coastlines at 110 m resolution, land fill `#E7E4DE`, thin gray gridlines, and labeled meridians/parallels only on outer panels. Define a zero-centered `TwoSlopeNorm` for anomaly fields and a single arrow-width formula:

```python
def arrow_width_zj(value: float, max_abs: float) -> float:
    if max_abs <= 0:
        raise ValueError("max_abs must be positive")
    if value == 0:
        return 0.0
    return 0.8 + 5.2 * np.sqrt(abs(value) / max_abs)
```

`save_figure_pair` must call `fig.savefig(..., dpi=300, bbox_inches="tight", facecolor="white")` for PNG and PDF and then close the figure.

- [ ] **Step 4: Run plotting helper tests**

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: PASS with both export files present.

- [ ] **Step 5: Commit the plotting system**

```bash
git add scripts/enso_geographic_figures/plotting.py tests/test_enso_geographic_figure_atlas.py
git commit -m "feat: add scientific Pacific map plotting system"
```

---

### Task 3: Render the three figures that need no new gridded download

**Files:**
- Create: `scripts/enso_geographic_figures/figures.py`
- Modify: `tests/test_enso_geographic_figure_atlas.py`

**Interfaces:**
- Consumes: trajectory and budget loaders from Task 1 and plotting helpers from Task 2.
- Produces: `build_trajectory_connectivity(output_dir: Path) -> dict`.
- Produces: `build_arrival_box_map(output_dir: Path, ohc_field: xr.Dataset | None = None) -> dict`.
- Produces: `build_fate_budget_map(output_dir: Path, surface_field: xr.Dataset | None = None) -> dict`.

- [ ] **Step 1: Add failing tests for plotted metadata and sign directions**

```python
def test_immediate_map_builders_return_audited_metadata(tmp_path):
    trajectory = build_trajectory_connectivity(tmp_path)
    arrival = build_arrival_box_map(tmp_path)
    fate = build_fate_budget_map(tmp_path)
    assert trajectory["particles"] == {1997: 467, 2015: 483, 2023: 410}
    assert arrival["east_inflow_zj"] == {1997: 16.96, 2015: 8.49, 2023: 9.90}
    assert fate["storage_loss_zj"] == {1997: 21.76, 2015: 19.89, 2023: 15.95}
    assert fate["westward_return_zj"][1997] > 0
```

- [ ] **Step 2: Run the focused tests and verify builder failure**

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: FAIL because the figure builders do not exist.

- [ ] **Step 3: Implement Figure 2, Figure 3, and Figure 4**

Figure 2 must use three equal map panels, weighted trajectory density on a common logarithmic scale, a time-progress colorbar, release box outlines, the 140°W gate, and compact annotations for weighted displacement and active fraction.

Figure 3 must fill all three boxes by Jan–Jun storage change and draw the 140°W eastward inflow arrow. The arrow label and east-box value must match the audited event table to two decimals.

Figure 4 must fill the east box by following Jan–May storage change, draw four boundary arrows using a single maximum absolute ZJ across all events, encode surface heat loss with five evenly spaced upward red arrows inside the east box, and put `R′ = value ZJ` in the panel corner. Negative southward output must reverse the arrow instead of drawing a negative-width arrow.

- [ ] **Step 4: Run tests and visually inspect the three PNG files**

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: PASS and PNG/PDF pairs for `fig02_trajectory_connectivity`, `fig03_arrival_box_map`, and `fig04_fate_budget_map`.

Inspect at full resolution for coastline clipping, label overlap, arrow direction, shared scales, and readable units.

- [ ] **Step 5: Commit the immediately available maps**

```bash
git add scripts/enso_geographic_figures/figures.py tests/test_enso_geographic_figure_atlas.py
git commit -m "feat: map ENSO trajectories arrival and heat fate"
```

---

### Task 4: Fetch and validate the minimal SODA3 geographic fields

**Files:**
- Create: `scripts/fetch_soda3_geographic_figure_fields.py`
- Modify: `tests/test_enso_geographic_figure_atlas.py`
- Create at runtime: `data/derived/research_2026/soda3_geographic_figure_fields_1997_2015_2023.nc`

**Interfaces:**
- Consumes: SODA3 URLs, coordinate helpers, and depth bounds already used by `fetch_soda3_three_box_enthalpy_boundary_terms.py`.
- Produces: required NetCDF variable `ohc300_anom_gjm2(event, phase, lat, lon)`. A `surface_flux_anom_wm2` variable is included only when the source file exposes a spatially complete, unit-validated field; no figure test depends on it.
- Produces: `open_geographic_fields(path: Path) -> xr.Dataset` in `data.py`.

- [ ] **Step 1: Add a failing schema test for the NetCDF output**

```python
def test_geographic_field_schema(geographic_field_dataset):
    ds = geographic_field_dataset
    assert ds.event.values.tolist() == [1997, 2015, 2023]
    assert "ohc300_anom_gjm2" in ds
    assert ds.ohc300_anom_gjm2.dims == ("event", "phase", "lat", "lon")
    assert ds.attrs["baseline"] == "1980-2022 same-calendar-month linear expectation"
    assert float(ds.lon.min()) >= 130.0 and float(ds.lon.max()) <= 280.0
    assert float(ds.lat.min()) >= -10.0 and float(ds.lat.max()) <= 5.0
```

- [ ] **Step 2: Run the schema test against a missing output and verify failure**

Run: `.venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas.GeographicFieldTests -v`

Expected: FAIL because the NetCDF file has not been created.

- [ ] **Step 3: Implement the minimal fetch and anomaly calculation**

The fetcher must request only 130°E–80°W, 10°S–5°N, 0–300 m and the months needed for the selected event phases plus 1980–2022 baseline months. It must compute layer-thickness-weighted OHC, fit the same-calendar-month intercept and linear trend over 1980–2022 at every wet grid cell, subtract the expectation, and then average the required phase months.

Use resumable year/event cache files under `data/interim/research_2026/soda3_geographic_figure_fields/`; never overwrite a valid cache unless `--force` is passed. Preserve `units`, `baseline`, `depth_range`, `phase_definition`, and SODA source URL as NetCDF attributes.

- [ ] **Step 4: Run the fetcher and validation tests**

Run: `.venv/bin/python scripts/fetch_soda3_geographic_figure_fields.py`

Run: `.venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas.GeographicFieldTests -v`

Expected: PASS, finite wet-ocean values, zero-centered anomaly distributions, strictly increasing longitudes, and strictly increasing latitudes.

- [ ] **Step 5: Commit the field fetcher and schema tests**

```bash
git add scripts/fetch_soda3_geographic_figure_fields.py scripts/enso_geographic_figures/data.py tests/test_enso_geographic_figure_atlas.py
git commit -m "feat: prepare minimal SODA3 OHC map fields"
```

---

### Task 5: Render propagation and third-question map–statistics figures

**Files:**
- Modify: `scripts/enso_geographic_figures/figures.py`
- Modify: `tests/test_enso_geographic_figure_atlas.py`

**Interfaces:**
- Consumes: Hovmöller table, minimal geographic NetCDF, `nonh20_early_north_to_jiang_event_table.csv`, `nonh20_early_north_to_jiang_relationships.csv`, `nonh20_third_question_event_table.csv`, and `nonh20_third_question_relationships.csv`.
- Produces: `build_propagation_atlas(output_dir: Path, fields: xr.Dataset) -> dict`.
- Produces: `build_q3_state_map(output_dir: Path, fields: xr.Dataset | None = None) -> dict`.

- [ ] **Step 1: Add failing tests for shared scales and reported correlations**

```python
def test_propagation_panels_share_one_color_limit(tmp_path, geographic_field_dataset):
    metadata = build_propagation_atlas(tmp_path, geographic_field_dataset)
    assert metadata["color_limits"][0] == -metadata["color_limits"][1]
    assert metadata["events"] == [1997, 2015, 2023]
    assert metadata["gate_longitude_deg_e"] == 220.0


def test_q3_metadata_matches_current_residual_relations(tmp_path):
    metadata = build_q3_state_map(tmp_path)
    assert metadata["n_events"] == 13
    assert round(metadata["relations"]["route_to_ne925"]["r"], 2) == 0.68
    assert round(metadata["relations"]["stress_to_export"]["r"], 2) == 0.74
    assert round(metadata["relations"]["sst_to_surface_loss"]["r"], 2) == 0.65
```

- [ ] **Step 2: Run the focused tests and verify builder failure**

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: FAIL because the two builders are not implemented.

- [ ] **Step 3: Implement Figure 1 and Figure 5**

Figure 1 must use one shared Hovmöller colorbar, one shared OHC′ map colorbar, the same 140°W gate styling in all panels, and no duplicate numeric callout boxes.

Figure 5 must place the JFM route, MJJ NE925 region, 5°N stress gate, eastern SST box, and surface heat-loss box on a single Pacific map. Three narrow residual-slope panels sit below the map, using gray for the other ten events and fixed orange/blue/teal highlights. Do not add an untested intermediate causal arrow.

- [ ] **Step 4: Run the full test file and visually inspect Figure 1 and Figure 5**

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: PASS and PNG/PDF pairs for `fig01_propagation_atlas` and `fig05_q3_state_map`.

- [ ] **Step 5: Commit the remaining figures**

```bash
git add scripts/enso_geographic_figures/figures.py tests/test_enso_geographic_figure_atlas.py
git commit -m "feat: add ENSO propagation and state-constraint maps"
```

---

### Task 6: Build the atlas, audit, and final visual QA

**Files:**
- Create: `scripts/build_enso_geographic_figure_atlas.py`
- Modify: `tests/test_enso_geographic_figure_atlas.py`
- Create at runtime: `outputs/research_2026/enso_geographic_figure_atlas_20260812/figure-audit.json`
- Create at runtime: `outputs/research_2026/enso_geographic_figure_atlas_20260812/atlas-montage.png`

**Interfaces:**
- Consumes: all five builder functions.
- Produces: `main(argv: list[str] | None = None) -> int`.
- Produces: ten final figure files, one audit JSON, and one montage.

- [ ] **Step 1: Add a failing end-to-end artifact test**

```python
def test_complete_atlas_artifacts(atlas_output_dir):
    stems = [
        "fig01_propagation_atlas",
        "fig02_trajectory_connectivity",
        "fig03_arrival_box_map",
        "fig04_fate_budget_map",
        "fig05_q3_state_map",
    ]
    for stem in stems:
        assert (atlas_output_dir / f"{stem}.png").stat().st_size > 100_000
        assert (atlas_output_dir / f"{stem}.pdf").stat().st_size > 10_000
    audit = json.loads((atlas_output_dir / "figure-audit.json").read_text())
    assert set(audit["figures"]) == set(stems)
    assert (atlas_output_dir / "atlas-montage.png").stat().st_size > 100_000
```

- [ ] **Step 2: Run the end-to-end test and verify failure**

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: FAIL because the CLI and final audit do not exist.

- [ ] **Step 3: Implement the CLI, audit JSON, and montage**

The CLI must support `--output-dir`, `--fields`, `--skip-grid-fields`, and `--force`. It must call each builder once, merge returned metadata under deterministic figure stems, write sorted UTF-8 JSON, and create a two-column montage from the PNG files using Pillow without resampling the scientific originals.

- [ ] **Step 4: Run the complete build and verification suite**

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python scripts/build_enso_geographic_figure_atlas.py`

Run: `MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl_enso_geo .venv/bin/python -m unittest tests.test_enso_geographic_figure_atlas -v`

Expected: all tests PASS; five PNG/PDF pairs, audit JSON, and montage exist.

- [ ] **Step 5: Perform full-size visual inspection**

Inspect each PNG individually at full resolution and verify:

- no titles or labels are clipped;
- no text overlaps coastlines, arrows, colorbars, or panel labels;
- event panels use shared scales;
- arrow directions match the sign convention;
- negative terms are visually unambiguous;
- maps show the correct 140°W gate and three fixed boxes;
- all labels and units are English;
- no H20 or D20 notation appears.

- [ ] **Step 6: Commit the atlas builder and tests**

```bash
git add scripts/build_enso_geographic_figure_atlas.py tests/test_enso_geographic_figure_atlas.py
git commit -m "feat: deliver audited ENSO geographic figure atlas"
```
