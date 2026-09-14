# ENSO PPT Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a data-verified, approximately 15-slide Chinese research presentation that preserves one formula slide immediately before every result figure and removes redundant literature, robustness, and repeated-summary content.

**Architecture:** A Python data/figure builder will read the authoritative CSV files, validate the displayed values, and export five English scientific figures plus a JSON audit ledger. A JavaScript ES module using `@oai/artifact-tool` will duplicate selected slides from the current 38-slide deck, edit inherited objects in place, insert the regenerated figures, and export the final PPTX and QA artifacts.

**Tech Stack:** Python 3, pandas, NumPy, SciPy, Matplotlib, Node.js ES modules, `@oai/artifact-tool`, presentation template-following helpers.

## Global Constraints

- Preserve the current deck's master, layout, PingFang SC typography, blue/orange/teal palette, margins, and title hierarchy.
- Keep all H20 and Q20 threshold material out of the deck.
- Use no more than 15 main slides.
- Place one matching formula/data slide immediately before every local result figure.
- Keep result-figure axes, legends, panel labels, and units in English; use Chinese for slide titles, formulas, and interpretation.
- Do not show bootstrap intervals, event-deletion tests, LOEO results, or sensitivity matrices in the main deck.
- Treat the three Q3 relationships as parallel statistical constraints, not a completed intermediate mechanism.
- Read every displayed numeric value from the authoritative CSVs or from calculations made from those CSVs.
- Preserve `[Sources]` blocks in speaker notes for external claims and assets.
- Leave the original 38-slide PPTX unchanged and export a new file.

---

### Task 1: Build the authoritative data audit and scientific figures

**Files:**
- Create: `scripts/build_simplified_enso_ppt_assets_20260811.py`
- Create: `tests/test_simplified_enso_ppt_assets_20260811.py`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/data-audit.json`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/fig-q1-hovmoller-en.png`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/fig-q1-trajectory-en.png`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/fig-q1-arrival-en.png`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/fig-q2-partition-en.png`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/fig-q3-independent-constraints-en.png`

**Interfaces:**
- Consumes: `data/derived/research_2026/soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv`.
- Consumes: `data/derived/research_2026/soda3_temp_anomaly_lagrangian_pilot_summary.csv`.
- Consumes: `data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`.
- Consumes: `data/derived/research_2026/nonh20_early_north_to_jiang_event_table.csv` and `nonh20_early_north_to_jiang_relationships.csv`.
- Consumes: `data/derived/research_2026/nonh20_third_question_event_table.csv` and `nonh20_third_question_relationships.csv`.
- Produces: `build_assets(output_dir: Path) -> dict`, returning the same structure written to `data-audit.json`.
- Produces JSON keys: `arrival`, `trajectory`, `partition`, `q3`, `residual_summary`, and `source_files`.

- [ ] **Step 1: Write validation tests for source-derived values**

```python
def test_highlight_values_match_authoritative_csvs(tmp_path):
    audit = build_assets(tmp_path)
    assert audit["arrival"]["1997"] == {"inflow_zj": 16.95640595, "ohc_gain_zj": 17.31754541}
    assert audit["arrival"]["2015"] == {"inflow_zj": 8.48760368, "ohc_gain_zj": 8.604799183}
    assert audit["arrival"]["2023"] == {"inflow_zj": 9.903187024, "ohc_gain_zj": 11.11554695}
    assert audit["partition"]["2023"]["surface_loss_zj"] == 0.4654415672
    assert audit["partition"]["2015"]["residual_zj"] == -6.385269096
```

- [ ] **Step 2: Run the focused test and confirm it fails before implementation**

Run: `python -m pytest tests/test_simplified_enso_ppt_assets_20260811.py -q`

Expected: import or function failure because the asset builder does not yet exist.

- [ ] **Step 3: Implement CSV loading, residualization, correlations, and exact-value assertions**

The implementation must:

```python
HIGHLIGHT_EVENTS = (1997, 2015, 2023)

def residualize(values: np.ndarray, control: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(control.size), control])
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    return values - design @ coefficients
```

It must select `arrival_Jan_Jun/east` and `decay_Jan_May_next/east` rows, calculate signed residuals, include eastward and southward small terms in the Q2 figure, and assert the three Q3 Pearson correlations round to 0.68, 0.74, and 0.65.

- [ ] **Step 4: Generate five figures with deterministic English labels**

Use fixed event colors: 1997 `#E87500`, 2015 `#2E86C1`, 2023 `#148F88`, other events `#93A4AF`. Do not place a figure-level title inside any PNG. Use panel labels `(a)`, `(b)`, `(c)`, explicit units, shared scales for comparable event panels, and 300 dpi output.

- [ ] **Step 5: Run the tests and inspect image dimensions**

Run: `python -m pytest tests/test_simplified_enso_ppt_assets_20260811.py -q`

Expected: all tests pass and each output PNG exists with width at least 1800 pixels.

---

### Task 2: Inspect the source deck and create the 15-slide template map

**Files:**
- Create: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/template-audit.txt`
- Create: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/template-frame-map.json`
- Create: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/deviation-log.txt`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/template-starter.pptx`

**Interfaces:**
- Consumes: `outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_第三问精简版_20260811.pptx`.
- Produces: a 15-slide starter deck and stable inherited object IDs/names for Task 3.

- [ ] **Step 1: Inspect and render every source slide**

Run the presentation skill's `inspect_template_deck.mjs` against the 38-slide source deck and review all generated slide PNGs and layout JSON files.

- [ ] **Step 2: Write the source-to-output frame map**

Map output slides to source slides as follows:

```text
1<-1, 2<-2, 3<-10, 4<-11, 5<-12, 6<-13, 7<-14, 8<-15,
9<-16, 10<-19, 11<-20, 12<-26, 13<-20, 14<-32, 15<-9
```

The source deck was saved by the user as a 32-slide current version after the plan was drafted, so these source numbers supersede the earlier 38-slide mapping while preserving the same narrative roles.

Declare every rewritten text box and replaced image as an explicit edit target. Record all omitted source slides and the reason `redundant literature detail, robustness detail, repeated summary, or superseded figure`.

- [ ] **Step 3: Build and validate the starter deck**

Run `prepare_template_starter_deck.mjs`, requiring exactly 15 slides, no unresolved source element IDs, and no empty inherited placeholders.

---

### Task 3: Author the simplified presentation from the starter deck

**Files:**
- Create: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/build_simplified_deck.mjs`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/final-preview/slide-*.png`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/final-layout/slide-*.layout.json`
- Create: `outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_精简核对版_20260811.pptx`

**Interfaces:**
- Consumes: the starter PPTX and `assets/data-audit.json` from Tasks 1–2.
- Produces: the final 15-slide PPTX, renders, layouts, montage, and inspect NDJSON.

- [ ] **Step 1: Import the starter deck and bind source element IDs to copied shapes**

Use `PresentationFile.importPptx`, the source inspect NDJSON, and inherited shape names. Fail if the starter deck does not contain exactly 15 slides.

- [ ] **Step 2: Rewrite the literature and question framing slides**

Slide 2 must use only one sentence per paper and one bottom synthesis line. Slide 3 must show the three questions and the three non-overlapping time windows. Remove source-paper figures, original-paper formula pages, and all audience-facing robustness language.

- [ ] **Step 3: Rewrite the five formula pages**

Each formula page must include only the equation, variable definitions, domain/time window, unit, and how to read the immediately following figure. Use mathematical subscripts instead of underscores in visible text.

- [ ] **Step 4: Replace all five result figures and populate numeric callouts from JSON**

Do not hard-code result values in the `.mjs` file. Read and format values from `data-audit.json`. Q2 must show the signed residuals `−0.52`, `−6.39`, and `−4.43 ZJ`; its explanatory line must state that residual magnitudes are 2%, 32%, and 28% of eastern-box loss. Q3 must label the first relationship as NE925 in `m s⁻¹` and must not mix it with NE850 standardized values.

- [ ] **Step 5: Rewrite the final synthesis and backup data-window slide**

Slide 14 resolves all three questions without claiming an intermediate mechanism. Slide 15 is labeled as backup/reference and lists SODA3.15.2, ERA5, the 13 event years, analysis regions, and time windows.

- [ ] **Step 6: Export the PPTX, previews, layouts, montage, and inspect file**

Use `PresentationFile.exportPptx`. Fail if the output deck has a slide count other than 15.

---

### Task 4: Verify scientific values and presentation layout

**Files:**
- Create: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/qa-ledger.txt`
- Create at runtime: `outputs/research_2026/ppt/.tmp_simplified_verified_20260811/final-contact-sheet.png`

**Interfaces:**
- Consumes: final PPTX, inspect NDJSON, layout JSON, source CSVs, and `data-audit.json`.
- Produces: a pass/fail QA ledger with one record per slide.

- [ ] **Step 1: Run programmatic slide and placeholder checks**

Run `slides_test.py`, the template fidelity checker, and a ZIP/XML scan that fails on empty `<p:ph>` placeholders, `H20`, `Q20`, visible underscores, unresolved `Slide Number`, `Date`, or `Footer` prompts, and any slide count other than 15.

- [ ] **Step 2: Cross-check every displayed number**

Extract text from the final inspect NDJSON and compare the arrival, trajectory, Q2, and Q3 values against `data-audit.json`. The check must specifically reject the prior incorrect surface-loss sequence `4.89 / 1.49 / 0.54`.

- [ ] **Step 3: Review every slide render at full size**

Inspect all 15 slide PNGs individually for clipping, overlap, unexpected wrapping, figure legibility, panel-label consistency, formula readability, and English-only figure labels.

- [ ] **Step 4: Run a final reopen/export verification**

Re-import the final PPTX with artifact-tool, export slide 1 and slide 15, and confirm there is no parse or render failure.

- [ ] **Step 5: Record final evidence**

Write the exact test commands, exit codes, slide count, corrected values, and any intentionally retained limitations to `qa-ledger.txt` before delivery.
