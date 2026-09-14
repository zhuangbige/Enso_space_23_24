# Jiang-Style Forward Lagrangian Heat-Fate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track the positive anomalous heat entering the eastern tropical Pacific across 140°W during January–June 2015 and 2023 forward to the following May, then compare its heat-weighted destinations with the existing three-box Eulerian budget.

**Architecture:** A new script reuses the validated SODA3 remote snapshot reader without modifying the existing backward pilot. It seeds particles on the 140°W gate where eastward velocity and detrended temperature anomaly are both positive, attaches an anomaly-heat-flux weight, integrates three-dimensional trajectories forward, and diagnoses first exits plus retained temperature anomaly. The existing three-box budget remains an independent closure product.

**Tech Stack:** Python 3, NumPy, pandas, SciPy, xarray/h5netcdf, Matplotlib, SODA3.15.2 five-day `temp/u/v/wt`, pytest.

## Global Constraints

- Do not use H20 or a 20°C threshold.
- Compare 2015 and 2023; release during development-year January–June at 140°W, 10°S–5°N, 0–300 m; track through following May.
- Seed weight is `ρ₀cₚ max(u,0) max(T′,0) dA dt`, reported in ZJ.
- Distinguish particle destination from thermodynamic anomaly loss.
- First exits are west across 140°W, north across 5°N, south across 10°S, below 300 m, or east/domain failure. Surface contact is exposure, not an exit.
- Temperature expectation is leave-event-out, same-calendar-month linear 1980–2024.
- State that missing SODA3 native diffusion/external-heating tendencies prevent full replication of every Jiang budget term.
- Preserve user-owned existing pilot files and outputs.

---

### Task 1: Gate Heat-Flux Seeding and Forward Integrator

**Files:**
- Create: `scripts/analyze_soda3_jiang_forward_heat_fate.py`
- Create: `tests/test_soda3_jiang_forward_heat_fate.py`

**Interfaces:**
- Consumes: `pilot_soda3_lagrangian_connectivity.Snapshot` and its interpolator.
- Produces: `centered_release_intervals_seconds`, `seed_gate_particles`, `integrate_interval_forward`, and `classify_first_exit`.

- [ ] **Step 1: Write failing seed tests**

```python
def test_gate_seed_weight_is_anomalous_heat_flux():
    seeds = fate.seed_gate_particles(snapshot(u=0.5, temp=19.0), expected(18.0), 86400.0, 2015)
    assert (seeds.gate_u_ms > 0).all()
    assert seeds.heat_weight_zj.sum() == pytest.approx(
        fate.RHO0 * fate.CP0 * 0.5 * seeds.section_area_m2.sum() * 86400.0 / 1e21
    )

def test_gate_seed_rejects_westward_and_nonpositive_anomaly():
    seeds = fate.seed_gate_particles(mixed_snapshot(), expected(18.0), 86400.0, 2023)
    assert (seeds.gate_u_ms > 0).all()
    assert (seeds.release_temp_anomaly_c > fate.MINIMUM_ANOMALY_C).all()
```

- [ ] **Step 2: Verify RED**

Run: `/opt/anaconda3/bin/python -m pytest tests/test_soda3_jiang_forward_heat_fate.py -k gate_seed -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement gate geometry and seeding**

Use tracer depth-cell thickness and meridional arc length for `dA`; interpolate `temp` and `u` to 220°E; require `u>0` and `T′>0.05°C`; calculate `heat_weight_zj=ρ₀cₚuT′dAΔt/10²¹`.

- [ ] **Step 4: Write failing forward-exit tests**

```python
@pytest.mark.parametrize("velocity, expected", [
    ((-2.0, 0.0, 0.0), "returned_west_140w"),
    ((0.0, 2.0, 0.0), "north_of_5n"),
    ((0.0, -2.0, 0.0), "south_of_10s"),
    ((0.0, 0.0, -1e-3), "below_300m"),
])
def test_forward_first_exit(velocity, expected):
    assert run_synthetic_forward_case(velocity).destination.iloc[0] == expected
```

- [ ] **Step 5: Verify RED, implement RK2/exit bookkeeping, verify GREEN**

Run before and after implementation: `/opt/anaconda3/bin/python -m pytest tests/test_soda3_jiang_forward_heat_fate.py -k forward -q`

Use 12-hour time-interpolated RK2; map upward-positive `wt` to `dz/dt=-w`; retain failed/exited particles in the denominator.

- [ ] **Step 6: Commit Task 1**

Run: `/opt/anaconda3/bin/python -m pytest tests/test_soda3_jiang_forward_heat_fate.py -q`

Commit: `git add scripts/analyze_soda3_jiang_forward_heat_fate.py tests/test_soda3_jiang_forward_heat_fate.py && git commit -m "feat: add heat-weighted forward SODA trajectories"`

### Task 2: Two-Year Event Assembly and Calculation

**Files:**
- Modify: `scripts/analyze_soda3_jiang_forward_heat_fate.py`
- Modify: `tests/test_soda3_jiang_forward_heat_fate.py`

**Interfaces:**
- Consumes: Task 1 APIs and `fetch_soda3_5day_event_transport.list_event_files`.
- Produces: `filter_tracking_calendar`, `track_event_cohorts`, endpoint/trajectory/summary CSVs, and audit JSON.

- [ ] **Step 1: Write failing calendar tests**

```python
def test_tracking_calendar_runs_january_to_following_may():
    files = fate.filter_tracking_calendar(two_year_files(), 2015)
    assert files[0][0] == pd.Timestamp("2015-01-01")
    assert files[-1][0].year == 2016 and files[-1][0].month == 5

def test_release_calendar_ends_in_development_june():
    assert fate.is_release_time(pd.Timestamp("2015-06-28"), 2015)
    assert not fate.is_release_time(pd.Timestamp("2015-07-03"), 2015)
```

- [ ] **Step 2: Verify RED, implement calendar assembly, verify GREEN**

Run before and after: `/opt/anaconda3/bin/python -m pytest tests/test_soda3_jiang_forward_heat_fate.py -k calendar -q`

- [ ] **Step 3: Implement cohort tracking and endpoint anomaly**

Release at every retained January–June snapshot; track to following May or first exit. For active particles sample final temperature and following-May leave-year-out expectation. Record endpoint anomaly, anomaly-retention ratio, surface exposure, destination, and initial heat weight.

- [ ] **Step 4: Run the coarse calculation**

Run: `/opt/anaconda3/bin/python scripts/analyze_soda3_jiang_forward_heat_fate.py --years 2015 2023 --stride 6 --step-hours 12`

Write `soda3_jiang_forward_heat_fate_{endpoints,trajectories,summary}.csv` and `soda3_jiang_forward_heat_fate_audit.json` under `data/derived/research_2026/`.

- [ ] **Step 5: Audit and commit Task 2**

Require heat-weight destination fractions to sum to one, positive integrated gate heat, January–June releases only, and terminal dates no later than following May.

Commit: `git add scripts/analyze_soda3_jiang_forward_heat_fate.py tests/test_soda3_jiang_forward_heat_fate.py && git commit -m "feat: calculate 2015 and 2023 forward warm-water fate"`

### Task 3: Scientific Figures and Eulerian Cross-Check

**Files:**
- Modify: `scripts/analyze_soda3_jiang_forward_heat_fate.py`
- Modify: `tests/test_soda3_jiang_forward_heat_fate.py`
- Create: `outputs/research_2026/soda3_jiang_forward_heat_fate/SODA3_JIANG_FORWARD_HEAT_FATE_CN.md`

**Interfaces:**
- Consumes: Task 2 outputs and `soda3_three_box_ohc_anomaly_budget_events.csv`.
- Produces: English PNG/PDF destination figure, Lagrangian–Eulerian comparison, and Chinese interpretation.

- [ ] **Step 1: Write a failing product test**

```python
def test_products_write_figures_report_and_audit(tmp_path):
    outputs = fate.write_products(synthetic_endpoints(), synthetic_trajectories(), tmp_path)
    assert outputs.destination_png.stat().st_size > 50_000
    assert "拉格朗日" in outputs.report_md.read_text(encoding="utf-8")
    assert "不是完整复现" in outputs.report_md.read_text(encoding="utf-8")
```

- [ ] **Step 2: Verify RED, implement product writers, verify GREEN**

Run before and after: `/opt/anaconda3/bin/python -m pytest tests/test_soda3_jiang_forward_heat_fate.py -k products -q`

- [ ] **Step 3: Generate and visually inspect both figures**

Use separate 2015/2023 geographic panels with natural aspect and no figure-level title, plus a heat-weighted destination panel. Compare Lagrangian first-exit fractions with Eulerian boundary losses but label them as different diagnostics rather than forcing equality.

- [ ] **Step 4: Write conclusion and limitations**

Report westward return, north/south/deep exit, retained east-box heat, and endpoint anomaly retention. Retain three-box closure and state why missing native diffusion/external-heating diagnostics prevent a complete Jiang process decomposition.

- [ ] **Step 5: Full verification and commit**

Run `/opt/anaconda3/bin/python -m pytest tests/test_soda3_jiang_forward_heat_fate.py -q`, `/opt/anaconda3/bin/python -m pytest -q`, and `git diff --check`.

Commit: `git add scripts/analyze_soda3_jiang_forward_heat_fate.py tests/test_soda3_jiang_forward_heat_fate.py outputs/research_2026/soda3_jiang_forward_heat_fate/SODA3_JIANG_FORWARD_HEAT_FATE_CN.md && git commit -m "feat: report Jiang-style warm-water destinations"`
