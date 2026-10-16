#!/usr/bin/env python3
"""Frozen 13-event, leave-one-event-out sLIM RO / RO+PMM comparison.

Only the existing Chen--Jin estimator is used. No observed forcing is supplied
after initialization. Event strength is a verification label, never a feature.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

import paper_ro_slim as original
import three_event_segmented_slim as slim

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "outputs/research_2026/enso_strength_ro_pmm_20261015"
ONI = ROOT / "data/raw/noaa_cpc/oni_as_of_2026-07-30.txt"
INPUT = ROOT / "outputs/research_2026/three_event_slim_baseline_20261014/inputs_absolute.csv"
PMM = ROOT / "outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014/official_PMM.csv"
SEASONS = "DJF JFM FMA MAM AMJ MJJ JJA JAS ASO SON OND NDJ".split()
MODELS = {"RO": ["sst", "wwv26"], "RO_PMM": ["sst", "wwv26", "pmm"]}
SEED = 20261015
N_BOOT = 5000
EXPECTED = {
    "1982-1983": "strong", "1986-1988": "strong", "1991-1992": "strong",
    "1994-1995": "moderate", "1997-1998": "strong", "2002-2003": "moderate",
    "2004-2005": "weak", "2006-2007": "weak", "2009-2010": "strong",
    "2014-2016": "strong", "2018-2019": "moderate", "2019-2020": "weak",
    "2023-2024": "strong",
}
PROTOCOL = """Frozen protocol: 2026-10-15, approved before all-event results.
Inputs: ERSSTv5 monthly absolute Nino3.4 SST; SODA3 total WWV26 (1e14 m3,
9S--9N, 120E--80W, volume above instantaneous sigma_theta=26); official PMM-SST.
Common span: 1982-01 through 2024-12. WWV26 is not D20 or a heat budget.
RO=[SST,WWV26]; RO_PMM=[SST,WWV26,PMM]. No other model or tuning.
ONI vintage: local oni_as_of_2026-07-30.txt, rounded to published tenths using
decimal ROUND_HALF_UP. Runs >=5 overlapping seasons at ONI>=0.5 define events;
peak <1.0 weak, <1.5 moderate, otherwise strong (including very strong).
Event seasons are mapped to center months (DJF -> January of the listed year).
Exclusion: first season's first month through last season's last month, plus
12 months on EACH side, inclusive, clipped to input coverage. All climatology,
trend, scale and operator fitting excludes this interval. Disjoint segments
are never joined for interpolation, differentiation or lagged covariance.
Training includes all remaining ENSO phases, with no strength-specific fit.
SST/WWV: training monthly means then one training linear trend; PMM: training
mean only, no second detrending/ENSO removal. Existing sLIM perturb2, order=2,
72 steps/year interpolation, mean lag6/seasonal lag1; RK4 24 steps/month.
Development years: onset calendar year through the July--June year containing
the peak season center (first maximum if tied; never before the onset year).
Thus 1986/1987 and 2014/2015
both contribute starts, each pair of years remains ONE statistical event.
Five complete-month initial states Feb--Jun each development year; nine-month
deterministic free forecasts, no future observed SST, WWV or PMM forcing.
Display: fixed ERSST 1982--2022 monthly climatology; restore fitted background.
Main scores: monthly leads1--9 (lead0 excluded). Supplemental: centered 3-month
means at center leads1--5, including lead0 at the first seasonal center.
Compute each event's MSE and bias first, then equal-weight events and sqrt(MSE).
Skill percent = 100*(1-RMSE_RO_PMM/RMSE_RO); positive means improvement.
Paired event bootstrap: 5000 draws, seed20261015 (+ fixed group offsets), 95%
pointwise percentile intervals; no refitting during bootstrap. Not predictive
intervals, not independent monthly samples; n=3 groups are descriptive.
Current-vintage retrospective parameter-heldout assessment: future NON-target
training data and the published fixed PMM spatial pattern remain available.
Not a real-time forecast reconstruction or proof of PMM causality. Report both
positive and negative skills. No process attribution, no added model variants.
"""


def dump(path: Path, obj):
    def convert(x):
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, np.generic):
            return x.item()
        if isinstance(x, (pd.Timestamp, Path)):
            return str(x)
        raise TypeError(type(x))
    path.write_text(json.dumps(obj, default=convert, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def rounded_oni(value: str) -> float:
    return float(Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def classify(peak: float) -> str:
    if peak < .5:
        raise ValueError("Not a warm event")
    return "weak" if peak < 1 else ("moderate" if peak < 1.5 else "strong")


def detect_events(oni: pd.DataFrame, start_year=1982, end_year=2024) -> pd.DataFrame:
    """Identify complete contiguous warm episodes, not individual warm winters."""
    assert oni.index.is_unique
    assert oni.index.equals(pd.date_range(oni.index[0], oni.index[-1], freq="MS"))
    above = oni.oni >= .5
    run_id = above.ne(above.shift(fill_value=False)).cumsum()
    records = []
    for _, run in oni.loc[above].groupby(run_id[above]):
        if len(run) < 5:
            continue
        first, last = run.index[0], run.index[-1]
        if first.year < start_year or last.year > end_year or last == oni.index[-1]:
            continue
        peak_center = run.oni.idxmax()
        peak_year = max(first.year, peak_center.year - int(peak_center.month <= 6))
        development_years = list(range(first.year, peak_year + 1))
        assert development_years, "Inspect an event peaking before its onset year"
        coverage_start = first - pd.DateOffset(months=1)
        coverage_end = last + pd.DateOffset(months=1)
        holdout_start = max(coverage_start - pd.DateOffset(months=12), pd.Timestamp(start_year, 1, 1))
        holdout_end = min(coverage_end + pd.DateOffset(months=12), pd.Timestamp(end_year, 12, 1))
        records.append(dict(
            event=f"{first.year}-{last.year}", strength=classify(run.oni.max()),
            peak_oni=float(run.oni.max()), peak_center=peak_center,
            start_center=first, end_center=last,
            start_season=SEASONS[first.month-1], end_season=SEASONS[last.month-1],
            n_seasons=len(run), coverage_start=coverage_start, coverage_end=coverage_end,
            holdout_start=holdout_start, holdout_end=holdout_end,
            development_years=",".join(map(str, development_years)),
            n_development_years=len(development_years),
        ))
    return pd.DataFrame(records)


def read_oni(path=ONI):
    records = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] in SEASONS:
            records.append(dict(time=pd.Timestamp(int(parts[1]), SEASONS.index(parts[0])+1, 1),
                                season=parts[0], oni_raw=float(parts[3]), oni=rounded_oni(parts[3])))
    return pd.DataFrame(records).set_index("time")


def load_inputs():
    data = pd.read_csv(INPUT, index_col="time", parse_dates=True)
    pmm = pd.read_csv(PMM, index_col="time", parse_dates=True)
    assert data.index.equals(pd.date_range("1982-01-01", "2024-12-01", freq="MS"))
    assert pmm.index.is_unique
    np.testing.assert_allclose(data.basin_wwv,
        data[["west_wwv", "central_wwv", "east_wwv"]].sum(axis=1), atol=1e-10, rtol=0)
    raw = data[["ersst", "basin_wwv"]].rename(columns={"ersst": "sst", "basin_wwv": "wwv26"})
    raw["pmm"] = pmm.SST.reindex(raw.index)
    assert np.isfinite(raw.to_numpy()).all()
    return raw


def prepare(raw, mask):
    anomalies, meta = slim.preprocess(raw, np.asarray(mask, float), detrend=True)
    j = raw.columns.get_loc("pmm")
    mean = float(raw.loc[mask, "pmm"].mean())
    anomalies["pmm"] = raw.pmm - mean
    meta["clim"][:, j] = mean
    meta["trend"][:, j] = 0
    return anomalies, meta


def submeta(meta, indices):
    return {k: (v[:, indices] if k in ("clim", "trend") else v) for k, v in meta.items()}


def predict_from_initial(model, meta, raw_initial, dates, display):
    """No full observation series is accepted by the forecast interface."""
    background = slim.background_at(meta, dates)
    initial = np.asarray(raw_initial) - background[0]
    trajectory = original.predict(model, initial, dates[0].month, months=len(dates)-1)
    return trajectory + background - display.loc[dates.month, model["columns"]].to_numpy(), trajectory


def fit_forecasts(raw, events, out):
    display = raw.loc["1982":"2022"].groupby(raw.loc["1982":"2022"].index.month).mean()
    display.to_csv(out / "display_climatology.csv", index_label="month")
    models, audit, rows, masks, failures = {}, [], [], [], []
    qa = dict(max_heldout_coef_error=0., max_heldout_preprocessing_error=0.,
              max_heldout_scale_error=0., max_future_observation_error=0.,
              max_initial_error=0., max_rk4_error=0., max_unit_scaling_error=0.,
              max_propagator_error=0.)
    for event in events.itertuples(index=False):
        mask = np.asarray(~((raw.index >= event.holdout_start) & (raw.index <= event.holdout_end)))
        masks.extend(dict(event=event.event, time=t, training=bool(v)) for t, v in zip(raw.index, mask))
        anomalies, meta = prepare(raw, mask)
        changed = raw.copy()
        changed.loc[~mask] += np.array([123., 456., 789.])
        changed_a, changed_meta = prepare(changed, mask)
        for key in ("clim", "trend"):
            qa["max_heldout_preprocessing_error"] = max(qa["max_heldout_preprocessing_error"],
                float(np.max(abs(changed_meta[key] - meta[key]))))
        # Changing future HELD-OUT observations cannot affect the fitted model.
        first_init = pd.Timestamp(int(event.development_years.split(",")[0]), 2, 1)
        future_changed = raw.copy()
        future_changed.loc[(raw.index > first_init) & ~mask] -= np.array([57., 34., 89.])
        future_a, future_meta = prepare(future_changed, mask)
        event_models = {}
        for name, columns in MODELS.items():
            try:
                model = slim.fit(anomalies[columns], mask, method="perturb2", order=2)
                assert np.isfinite(model["coef"]).all()
                indices = [raw.columns.get_loc(c) for c in columns]
                mm = submeta(meta, indices)
                event_models[name] = model, mm
                models[f"{event.event}/{name}"] = dict(model=model, preprocessing=mm)
                radius = float(max(abs(np.linalg.eigvals(slim.propagators(model)[-1]))))
                audit.append(dict(event=event.event, model=name, training_months=int(mask.sum()),
                    annual_radius=radius, stable_annual=radius < 1,
                    **{k: v for k, v in model["diag"].items() if k != "segments"}))
                refit = slim.fit(changed_a[columns], mask, method="perturb2", order=2)
                qa["max_heldout_coef_error"] = max(qa["max_heldout_coef_error"],
                    float(np.max(abs(refit["coef"] - model["coef"]))))
                qa["max_heldout_scale_error"] = max(qa["max_heldout_scale_error"],
                    float(np.max(abs(refit["scale"] - model["scale"]))))
                future_fit = slim.fit(future_a[columns], mask, method="perturb2", order=2)
                dates = pd.date_range(first_init, periods=10, freq="MS")
                pred, native = predict_from_initial(model, mm, raw.loc[first_init, columns], dates, display)
                pred_changed, _ = predict_from_initial(future_fit, submeta(future_meta, indices),
                    future_changed.loc[first_init, columns], dates, display)
                qa["max_future_observation_error"] = max(qa["max_future_observation_error"],
                    float(np.max(abs(pred - pred_changed))))
                # Apply both integration and coordinate-change tests to every fold/model/start month.
                factors = np.array([3., 100.] + ([.2] if name == "RO_PMM" else []))
                scaled = slim.fit(anomalies[columns] * factors, mask, method="perturb2", order=2)
                for year in map(int, event.development_years.split(",")):
                    for month in range(2, 7):
                        ini = pd.Timestamp(year, month, 1)
                        initial = anomalies.loc[ini, columns].to_numpy()
                        native = original.predict(model, initial, month, months=9)
                        fine = original.predict(model, initial, month, months=9, steps=48)
                        converted = original.predict(scaled, initial*factors, month, months=9)/factors
                        propagated = slim.forecast(model, initial, month=month, months=9)
                        qa["max_rk4_error"] = max(qa["max_rk4_error"], float(np.max(abs(native-fine))))
                        qa["max_unit_scaling_error"] = max(qa["max_unit_scaling_error"], float(np.max(abs(native-converted))))
                        qa["max_propagator_error"] = max(qa["max_propagator_error"], float(np.max(abs(native-propagated))))
            except Exception as exc:
                failures.append(dict(event=event.event, model=name, error=repr(exc)))
                dump(out / "failures.json", failures)
                continue
        if len(event_models) == 2 and not any(f["event"] == event.event for f in failures):
            for year in map(int, event.development_years.split(",")):
                for month in range(2, 7):
                    ini = pd.Timestamp(year, month, 1)
                    dates = pd.date_range(ini, periods=10, freq="MS")
                    assert ((dates >= event.holdout_start) & (dates <= event.holdout_end)).all()
                    obs = raw.loc[dates, "sst"].to_numpy() - display.loc[dates.month, "sst"].to_numpy()
                    predictions = {}
                    for name, (model, mm) in event_models.items():
                        pred, native = predict_from_initial(model, mm, raw.loc[ini, MODELS[name]], dates, display)
                        assert np.isfinite(pred).all()
                        qa["max_initial_error"] = max(qa["max_initial_error"], abs(float(pred[0, 0]-obs[0])))
                        predictions[name] = pred[:, 0]
                    for lead, target in enumerate(dates):
                        rows.append(dict(event=event.event, strength=event.strength,
                            development_year=year, init=ini, init_month=month, lead=lead,
                            target=target, observed=float(obs[lead]),
                            **{name: float(v[lead]) for name, v in predictions.items()}))
        print(f"{event.event} ({event.strength}): {mask.sum()} training months; completed", flush=True)
    pd.DataFrame(masks).to_csv(out / "training_masks.csv", index=False)
    pd.DataFrame(audit).to_csv(out / "fit_diagnostics.csv", index=False)
    dump(out / "models_and_preprocessing.json", models)
    dump(out / "failures.json", failures)
    if failures:
        raise RuntimeError("Some fits failed; see failures.json. No incomplete group comparison is published.")
    assert qa["max_heldout_coef_error"] < 1e-9
    assert qa["max_heldout_preprocessing_error"] < 1e-10
    assert qa["max_heldout_scale_error"] < 1e-10
    assert qa["max_future_observation_error"] < 1e-9
    assert qa["max_initial_error"] < 1e-10
    assert qa["max_rk4_error"] < 1e-5
    assert qa["max_unit_scaling_error"] < 1e-8
    assert qa["max_propagator_error"] < 1e-8
    qa.update(fits=len(models), unstable_fits=sum(not a["stable_annual"] for a in audit),
              annual_radius_min=min(a["annual_radius"] for a in audit),
              annual_radius_max=max(a["annual_radius"] for a in audit))
    return pd.DataFrame(rows), qa


def seasonal_forecasts(monthly):
    records = []
    for (_, _), series in monthly.groupby(["event", "init"], sort=False):
        series = series.sort_values("lead").set_index("lead")
        assert series.index.tolist() == list(range(10))
        for center in range(1, 6):
            row = series.loc[center].to_dict()
            row["lead"] = center
            for column in ("observed", *MODELS):
                row[column] = float(series.loc[center-1:center+1, column].mean())
            records.append(row)
    return pd.DataFrame(records)


def event_metrics(frame):
    records = []
    for event, part in frame.groupby("event", sort=True):
        row = dict(event=event, strength=part.strength.iloc[0], n_pairs=len(part),
                   n_unique_targets=part.target.nunique(), n_starts=part.init.nunique())
        for model in MODELS:
            errors = part[model].to_numpy()-part.observed.to_numpy()
            assert np.isfinite(errors).all()
            row[f"MSE_{model}"] = float(np.mean(errors**2))
            row[f"RMSE_{model}"] = float(np.sqrt(row[f"MSE_{model}"]))
            row[f"bias_{model}"] = float(np.mean(errors))
        row["improvement_percent"] = improvement(row["MSE_RO"], row["MSE_RO_PMM"])
        row["delta_MSE"] = row["MSE_RO_PMM"]-row["MSE_RO"]
        records.append(row)
    return pd.DataFrame(records)


def improvement(mse_ro, mse_pmm):
    a, b = np.asarray(mse_ro), np.asarray(mse_pmm)
    with np.errstate(divide="ignore", invalid="ignore"):
        value = np.where(a > 0, 100*(1-np.sqrt(b/a)), np.nan)
    return float(value) if value.ndim == 0 else value


def aggregate(events, group, n_boot=N_BOOT):
    """MSE averages give every episode one vote, regardless of its duration."""
    assert events.event.is_unique and len(events) > 0
    a, b = events.MSE_RO.to_numpy(), events.MSE_RO_PMM.to_numpy()
    offset = {"all": 0, "strong": 1, "moderate": 2, "weak": 3}[group]
    rng = np.random.default_rng(SEED+offset)
    draws = rng.integers(0, len(events), size=(n_boot, len(events)))
    gain = improvement(a[draws].mean(axis=1), b[draws].mean(axis=1))
    lo, hi = np.percentile(gain, [2.5, 97.5]) if np.isfinite(gain).all() else (np.nan, np.nan)
    return dict(group=group, n_events=len(events), n_pairs=int(events.n_pairs.sum()),
        RMSE_RO=float(np.sqrt(a.mean())), RMSE_RO_PMM=float(np.sqrt(b.mean())),
        bias_RO=float(events.bias_RO.mean()), bias_RO_PMM=float(events.bias_RO_PMM.mean()),
        improvement_percent=improvement(a.mean(), b.mean()), ci_low=float(lo), ci_high=float(hi),
        improved_events=int((b < a-1e-12).sum()), worsened_events=int((b > a+1e-12).sum()),
        tied_events=int((abs(b-a) <= 1e-12).sum()), small_sample=len(events) < 5,
        bootstrap_replicates=n_boot, undefined_bootstrap_replicates=int((~np.isfinite(gain)).sum()))


def score_tables(monthly, seasonal):
    event_rows, group_rows = [], []
    for target_type, frame in [("monthly", monthly[monthly.lead.between(1, 9)]),
                               ("seasonal", seasonal)]:
        views = [("overall", 0, 0, frame)]
        views += [("lead", int(lead), 0, part) for lead, part in frame.groupby("lead")]
        views += [("init", 0, int(month), part) for month, part in frame.groupby("init_month")]
        views += [("init_lead", int(lead), int(month), part)
                  for (month, lead), part in frame.groupby(["init_month", "lead"])]
        for view, lead, month, part in views:
            coordinates = dict(target_type=target_type, view=view, lead=lead, init_month=month)
            scores = event_metrics(part)
            event_rows.extend({**coordinates, **row} for row in scores.to_dict("records"))
            for name in ("all", "strong", "moderate", "weak"):
                selected = scores if name == "all" else scores[scores.strength.eq(name)]
                group_rows.append({**coordinates, **aggregate(selected, name)})
    return pd.DataFrame(event_rows), pd.DataFrame(group_rows)


def validate_saved(out, expected_events=None):
    """Reconstruct scores directly from persisted pairs, independent of scoring helpers."""
    monthly = pd.read_csv(out / "monthly_forecasts.csv", parse_dates=["init", "target"])
    seasonal = pd.read_csv(out / "seasonal_forecasts.csv", parse_dates=["init", "target"])
    events = pd.read_csv(out / "event_catalog.csv")
    groups = pd.read_csv(out / "group_scores.csv")
    detailed = pd.read_csv(out / "event_scores.csv")
    assert monthly.groupby(["event", "init"]).size().eq(10).all()
    assert not monthly.duplicated(["event", "init", "lead"]).any()
    expected_events = EXPECTED if expected_events is None else expected_events
    n_years = int(events.n_development_years.sum())
    assert len(monthly) == n_years*50 and len(seasonal) == n_years*25
    assert monthly.event.nunique() == len(expected_events)
    assert events.set_index("event").strength.to_dict() == expected_events
    for event in events.itertuples(index=False):
        years = [int(y) for y in str(event.development_years).split(",")]
        expected_starts = {pd.Timestamp(year, month, 1) for year in years for month in range(2, 7)}
        assert set(monthly.loc[monthly.event.eq(event.event), "init"]) == expected_starts
    assert monthly[["observed", "RO", "RO_PMM"]].notna().all().all()
    assert (monthly.target.dt.to_period("M").astype(int)-monthly.init.dt.to_period("M").astype(int)).equals(monthly.lead)
    for row in seasonal.itertuples(index=False):
        match = monthly[monthly.event.eq(row.event) & monthly.init.eq(row.init)
                        & monthly.lead.between(row.lead-1, row.lead+1)]
        assert len(match) == 3
        for column in ("observed", *MODELS):
            assert abs(match[column].mean()-getattr(row, column)) < 1e-10
    max_score_error = 0.
    for saved in groups.itertuples(index=False):
        frame = monthly[monthly.lead.gt(0)] if saved.target_type == "monthly" else seasonal
        if saved.group != "all":
            frame = frame[frame.strength.eq(saved.group)]
        if saved.lead:
            frame = frame[frame.lead.eq(saved.lead)]
        if saved.init_month:
            frame = frame[frame.init_month.eq(saved.init_month)]
        means, biases = [], []
        for _, part in frame.groupby("event", sort=True):
            err = part[["RO", "RO_PMM"]].to_numpy()-part.observed.to_numpy()[:, None]
            means.append(np.mean(err**2, axis=0))
            biases.append(np.mean(err, axis=0))
        means, biases = np.array(means), np.array(biases)
        rmse = np.sqrt(means.mean(axis=0))
        expected = [rmse[0], rmse[1], *biases.mean(axis=0), 100*(1-rmse[1]/rmse[0])]
        actual = [saved.RMSE_RO, saved.RMSE_RO_PMM, saved.bias_RO, saved.bias_RO_PMM, saved.improvement_percent]
        max_score_error = max(max_score_error, float(np.max(abs(np.array(expected)-actual))))
        assert saved.n_events == len(means) and saved.n_pairs == len(frame)
        assert saved.improved_events == (means[:, 1] < means[:, 0]-1e-12).sum()
        # Independently reproduce the percentile interval from event-level paired errors.
        offset = {"all": 0, "strong": 1, "moderate": 2, "weak": 3}[saved.group]
        draws = np.random.default_rng(SEED+offset).integers(0, len(means), (N_BOOT, len(means)))
        mse = means[draws].mean(axis=1)
        ci = np.percentile(100*(1-np.sqrt(mse[:, 1]/mse[:, 0])), [2.5, 97.5])
        np.testing.assert_allclose(ci, [saved.ci_low, saved.ci_high], atol=1e-9, rtol=0)
    for saved in detailed.itertuples(index=False):
        frame = monthly[monthly.lead.gt(0)] if saved.target_type == "monthly" else seasonal
        frame = frame[frame.event.eq(saved.event)]
        if saved.lead:
            frame = frame[frame.lead.eq(saved.lead)]
        if saved.init_month:
            frame = frame[frame.init_month.eq(saved.init_month)]
        for model in MODELS:
            errors = frame[model]-frame.observed
            assert abs(np.mean(errors**2)-getattr(saved, "MSE_"+model)) < 1e-10
            assert abs(errors.mean()-getattr(saved, "bias_"+model)) < 1e-10
    assert max_score_error < 1e-9
    return dict(saved_score_max_error=max_score_error, saved_monthly_rows=len(monthly),
                saved_seasonal_rows=len(seasonal), group_score_rows=len(groups),
                event_score_rows=len(detailed), saved_score_and_bootstrap_reconstruction="passed")


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "protocol_before_run.txt").write_text(PROTOCOL, encoding="utf-8")
    raw, oni = load_inputs(), read_oni()
    events = detect_events(oni)
    assert events.set_index("event").strength.to_dict() == EXPECTED
    assert events.n_development_years.sum() == 15
    raw.to_csv(out / "inputs_absolute.csv", index_label="time")
    oni.to_csv(out / "oni_frozen.csv", index_label="center")
    events.to_csv(out / "event_catalog.csv", index=False)
    files = [ONI, INPUT, PMM, Path(__file__).resolve(), Path(original.__file__).resolve(), Path(slim.__file__).resolve(),
             Path(__file__).resolve().with_name("report_enso_strength_pmm_skill.py")]
    dump(out / "source_manifest.json", dict(
        sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        python=sys.version, executable=sys.executable, platform=platform.platform(),
        numpy=np.__version__, pandas=pd.__version__, seed=SEED, bootstrap_replicates=N_BOOT,
        oni_source="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v5/"))
    monthly, qa = fit_forecasts(raw, events, out)
    seasonal = seasonal_forecasts(monthly)
    monthly.to_csv(out / "monthly_forecasts.csv", index=False)
    seasonal.to_csv(out / "seasonal_forecasts.csv", index=False)
    detailed, groups = score_tables(monthly, seasonal)
    detailed.to_csv(out / "event_scores.csv", index=False)
    groups.to_csv(out / "group_scores.csv", index=False)
    detailed.query("view == 'overall'").to_csv(out / "event_summary.csv", index=False)
    groups.query("view == 'overall'").to_csv(out / "group_summary.csv", index=False)
    qa.update(validate_saved(out))
    dump(out / "numerical_QA.json", qa)
    print(groups.query("target_type == 'monthly' and view == 'overall'").to_string(index=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate_saved(args.output), indent=2))
        return
    if not args.report_only:
        run(args.output)
    if not args.no_report:
        from report_enso_strength_pmm_skill import report
        report(args.output)


if __name__ == "__main__":
    main()
