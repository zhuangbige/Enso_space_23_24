#!/usr/bin/env python3
"""One continuous 1982--2024 manuscript-style D20 sLIM fit per model.

This is the user's corrected in-sample retrospective experiment. Event labels
select forecast starts and scoring groups only; they never select fit samples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

import paper_ro_slim as slim
import run_paper_ro_pmm as manuscript
import three_event_segmented_slim as segmented
import analyze_enso_strength_pmm_skill as scoring

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "outputs/research_2026/enso_strength_fullperiod_D20_20261015"
EXACT = ROOT / "outputs/research_2026/manuscript_RO_exact_period_20261014"
START, END = "1982-01-01", "2024-12-01"
MODELS = {"RO": ["sst", "d20"], "RO_PMM": ["sst", "d20", "pmm"]}
RENAME = {"Nino34": "sst", "WWV": "d20", "PMM_SST": "pmm"}
PROTOCOL = """User correction, 2026-10-15: continuous full-period manuscript-style fitting.
Fit interval: 1982-01 through 2024-12, 516 consecutive months, all ENSO phases.
Exactly ONE RO and ONE RO+PMM operator are used for all events and start months.
No event exclusions, moving training windows, or strength-specific operators.
RO=[ERSSTv5 Nino3.4, GODAS mean D20]; RO_PMM additionally uses official PMM-SST.
D20: 20-degree-C isotherm depth, area-weighted 5S--5N,120E--80W mean, meters.
The historical raw_indices.csv column WWV contains this mean D20, not WWV26.
Reuse original manuscript preprocessing and paper_ro_slim.py: 1991--2020
monthly climatology; one linear trend over 1982--2024; PMM full-fit mean only;
standard deviation ddof=0; annual/semiannual harmonics; perturb2; linear 6x
monthly interpolation, mean lag6/seasonal lag1; RK4 24 steps/month. No tuning.
Original local 2002--2024 replication (trend to Apr2025) is checked separately
against its saved coefficients. The new main analysis ends its trend at Dec2024
to keep the entire fitting protocol inside the requested common interval.
Classification: frozen local traditional ONI vintage 2026-07-30, decimal
round-half-up to tenths, >=5 seasons >=0.5; strong >=1.5, moderate >=1, weak >=.5.
13 events: 7 strong,3 moderate,3 weak. Sustained 1986--88 and 2014--16 each
include two development years but count once in event-weighted statistics.
75 starts: Feb--Jun in 15 development years. Each model takes its observed
initial state and integrates freely for nine months with fixed fitted dynamics.
PMM enters as an initial third state; it is not supplied as future observations.
Adding PMM entails a separately estimated 3-state operator, not a coefficient
switch during a pre-existing trajectory. No event-specific retraining.
Restore the fitted trend; score/display in common 1991--2020 SST anomalies.
Main: monthly leads1--9; supplement: centered 3-month means at center leads1--5.
Score each event's MSE/bias first; average events equally, then sqrt for RMSE.
Gain=100*(1-RMSE_RO_PMM/RMSE_RO); positive improves, negative worsens.
5000 paired-event bootstrap draws, seed20261015+fixed group offsets; n=3 groups
are small-sample summaries. Intervals condition on the two fixed fitted models.
This is full-period in-sample retrospective initialization comparison, not
parameter-out-of-sample verification or historical real-time prediction.
Keep all outcomes, positive or negative. No process attribution or new variants.
"""


def load_and_prepare(trend_end=END, start=START):
    raw_source, pmm, _ = manuscript.load()
    assert pd.Timestamp(trend_end) >= pd.Timestamp(END)
    # Keep the entire fixed 1991--2020 reference even when fitting starts in 2002.
    raw_source = raw_source.loc[:trend_end].copy()
    pmm = pmm.loc[:trend_end].copy()
    index = pd.date_range(start, trend_end, freq="MS")
    assert raw_source.loc[start:trend_end].index.equals(index) and pmm.loc[start:trend_end].index.equals(index)
    assert np.isfinite(raw_source.loc[index].to_numpy()).all() and np.isfinite(pmm.loc[index].to_numpy()).all()
    reference = raw_source.loc["1991":"2020"].rename(columns=RENAME)
    assert reference.index.equals(pd.date_range("1991-01-01", "2020-12-01", freq="MS"))
    prepared, meta = manuscript.prepare(raw_source, pmm, start, END, paper=True, trend_end=trend_end)
    raw = raw_source.loc[start:END].rename(columns=RENAME)
    raw["pmm"] = pmm.PMM_SST
    a = prepared.loc[start:END].rename(columns=RENAME)[MODELS["RO_PMM"]]
    # Remove unused PMM-wind bookkeeping; it is never a fitted state here.
    meta["pmm_sst_mean"] = float(meta.pop("pmm_mean")[0])
    meta.update(trend_start=start, trend_end=trend_end, climatology="1991-2020",
                physical_columns=["sst", "d20"], ocean_unit="m")
    reference["pmm"] = pmm.PMM_SST
    display = reference.groupby(reference.index.month).mean()
    assert raw.d20.between(0, 500).all() and raw.sst.between(15, 35).all()
    return raw, a, meta, display


def audit_original_replication():
    """Confirm the unchanged core reproduces our saved manuscript implementation."""
    raw, pmm, _ = manuscript.load()
    raw, pmm = raw.loc[:"2025-04-01"], pmm.loc[:"2025-04-01"]
    a, _ = manuscript.prepare(raw, pmm, "2002-01-01", END, paper=True,
                              trend_end="2025-04-01")
    old_a = pd.read_csv(EXACT / "observations_detrended_2002Jan_2025Apr.csv", index_col=0, parse_dates=True)
    old = json.loads((EXACT / "models_exact_period.json").read_text())
    model = slim.fit(a.loc["2002":END, manuscript.V])
    pre_error = float(abs(a.loc[old_a.index, manuscript.V].to_numpy()-old_a.to_numpy()).max())
    coef_error = float(abs(model["coef"]-np.array(old["models"]["monthly_states"]["model"]["coef"])).max())
    assert max(pre_error, coef_error) < 1e-10
    return dict(saved_2002_2024_preprocessing_max_error=pre_error,
                saved_2002_2024_coefficient_max_error=coef_error,
                audit_only=True, main_period=START+"/"+END,
                original_trend_end="2025-04-01", main_trend_end=END)


def forecast(model, initial, dates, meta, display, steps=24):
    """Only fixed coefficients and an initial state enter the free integration."""
    native = slim.predict(model, initial, dates[0].month, months=len(dates)-1, steps=steps)
    restored = manuscript.restore(native, dates, meta)
    anomaly = restored-display.loc[dates.month, ["sst", "d20"]].to_numpy()
    return anomaly, native


def validate_saved(out):
    """Reload both operators and recover every forecast from the full-period inputs."""
    saved = json.loads((out / "models_and_preprocessing.json").read_text())
    assert set(saved["models"]) == set(MODELS)
    meta = saved["preprocessing"]
    start, end = meta["start"], meta["end"]
    expected_events = {event: strength for event, strength in scoring.EXPECTED.items()
        if int(event[:4]) >= pd.Timestamp(start).year and int(event[-4:]) <= pd.Timestamp(end).year}
    result = scoring.validate_saved(out, expected_events=expected_events)
    for key in ("clim", "beta"):
        meta[key] = np.array(meta[key])
    raw = pd.read_csv(out / "inputs_absolute.csv", index_col="time", parse_dates=True)
    states = pd.read_csv(out / "fitted_period_states.csv", index_col="time", parse_dates=True)
    training = pd.read_csv(out / "training_period.csv", parse_dates=["time"])
    assert raw.index.equals(pd.date_range(start, end, freq="MS"))
    assert len(training) == len(raw) and training.training.eq(True).all()
    assert pd.DatetimeIndex(training.time).equals(raw.index)
    # Independently recover the preprocessing using saved raw SST and D20.
    climate_path = out / "climatology_inputs.csv"
    reference = pd.read_csv(climate_path, index_col="time", parse_dates=True) if climate_path.exists() else raw.loc["1991":"2020"]
    assert reference.index.equals(pd.date_range("1991-01-01", "2020-12-01", freq="MS"))
    climate = reference.groupby(reference.index.month).mean()
    np.testing.assert_allclose(climate[["sst", "d20"]], meta["clim"], atol=1e-11, rtol=0)
    trend_path = out / "trend_fit_inputs.csv"
    trend_raw = pd.read_csv(trend_path, index_col="time", parse_dates=True) if trend_path.exists() else raw[["sst", "d20"]]
    assert trend_raw.index.equals(pd.date_range(start, meta["trend_end"], freq="MS"))
    trend_anomaly = trend_raw[["sst", "d20"]].to_numpy()-climate.loc[trend_raw.index.month, ["sst", "d20"]].to_numpy()
    trend_time = slim.decimal_time(trend_raw.index)
    trend_design = np.column_stack([np.ones(len(trend_time)), trend_time-trend_time.mean()])
    beta = np.linalg.lstsq(trend_design, trend_anomaly, rcond=None)[0]
    anomaly = raw[["sst", "d20"]].to_numpy()-climate.loc[raw.index.month, ["sst", "d20"]].to_numpy()
    time = slim.decimal_time(raw.index)
    design = np.column_stack([np.ones(len(time)), time-trend_time.mean()])
    recomputed = pd.DataFrame(anomaly-design@beta, index=raw.index, columns=["sst", "d20"])
    recomputed["pmm"] = raw.pmm-raw.pmm.mean()
    prep_error = float(abs(recomputed.to_numpy()-states.to_numpy()).max())
    np.testing.assert_allclose(beta, meta["beta"], atol=1e-11, rtol=0)
    assert prep_error < 1e-10 and abs(meta["center"]-trend_time.mean()) < 1e-10
    monthly = pd.read_csv(out / "monthly_forecasts.csv", parse_dates=["init", "target"])
    maximum = 0.
    for name, columns in MODELS.items():
        model = saved["models"][name]
        for key in ("coef", "scale"):
            model[key] = np.array(model[key])
        assert model["columns"] == columns and model["order"] == 2 and model["method"] == "perturb2"
        np.testing.assert_allclose(model["scale"], recomputed[columns].std(ddof=0), atol=1e-10, rtol=0)
        for init, part in monthly.groupby("init"):
            part = part.sort_values("lead")
            dates = pd.DatetimeIndex(part.target)
            pred, _ = forecast(model, recomputed.loc[init, columns], dates, meta, climate)
            maximum = max(maximum, float(abs(pred[:, 0]-part[name].to_numpy()).max()))
    assert maximum < 1e-10
    result.update(saved_operator_forecast_max_error=maximum,
                  saved_preprocessing_max_error=prep_error,
                  saved_models_count=2, full_training_period_verified=True,
                  verified_training_months=len(raw), fixed_360_month_climatology_verified=True)
    return result


def run(out, trend_end=END, protocol_text=None, start=START):
    out.mkdir(parents=True, exist_ok=True)
    if trend_end != END or start != START:
        assert protocol_text is not None, "A different preprocessing window needs an explicit protocol."
    (out / "protocol_before_run.txt").write_text(protocol_text or PROTOCOL, encoding="utf-8")
    scoring.dump(out / "failures.json", [])
    scoring.dump(out / "analysis_protocol.json", dict(
        design="full_period_in_sample", start=start, end=END, training_months=len(pd.date_range(start, END, freq="MS")),
        climatology="1991-2020", trend_start=start, trend_end=trend_end,
        ocean_state="GODAS mean D20 (m)", model_count=2, event_exclusion=False))
    qa = dict(original_replication=audit_original_replication(),
        max_initial_error=0., max_rk4_error=0., max_unit_scaling_error=0.,
        max_fixed_model_future_observation_error=0., max_propagator_error=0.,
        max_continuous_segmented_coefficient_error=0., max_restored_error_difference=0.)
    qa["original_replication"]["main_trend_end"] = trend_end
    qa["original_replication"]["main_period"] = start+"/"+END
    raw, a, meta, display = load_and_prepare(trend_end, start)
    source = manuscript.load()[0].rename(columns=RENAME)
    source.loc["1991":"2020"].to_csv(out / "climatology_inputs.csv", index_label="time")
    trend_raw = source.loc[start:trend_end]
    trend_raw.to_csv(out / "trend_fit_inputs.csv", index_label="time")
    oni = scoring.read_oni()
    events = scoring.detect_events(oni, start_year=pd.Timestamp(start).year,
        end_year=pd.Timestamp(END).year).drop(columns=["holdout_start", "holdout_end"])
    expected_events = {event: strength for event, strength in scoring.EXPECTED.items()
        if int(event[:4]) >= pd.Timestamp(start).year and int(event[-4:]) <= pd.Timestamp(END).year}
    assert events.set_index("event").strength.to_dict() == expected_events
    raw.to_csv(out / "inputs_absolute.csv", index_label="time")
    a.to_csv(out / "fitted_period_states.csv", index_label="time")
    display.to_csv(out / "display_climatology.csv", index_label="month")
    oni.to_csv(out / "oni_frozen.csv", index_label="center")
    events.to_csv(out / "event_catalog.csv", index=False)
    pd.DataFrame(dict(time=raw.index, training=True)).to_csv(out / "training_period.csv", index=False)
    fits, audit = {}, []
    for name, columns in MODELS.items():
        model = slim.fit(a[columns])
        fits[name] = model
        equivalent = segmented.fit(a[columns], np.ones(len(a), bool))
        err = float(abs(model["coef"]-equivalent["coef"]).max())
        qa["max_continuous_segmented_coefficient_error"] = max(qa["max_continuous_segmented_coefficient_error"], err)
        assert err < 1e-10
        radii = [float(max(abs(np.linalg.eigvals(segmented.propagators(model, month=m)[-1])))) for m in range(1, 13)]
        audit.append(dict(model=name, training_start=start, training_end=END, training_months=len(a),
            fitted_once_for_all_events=True, n_states=len(columns), annual_radius=min(radii),
            annual_radius_max=max(radii), stable_annual=max(radii)<1, **model["diag"]))
        factors = np.array([3., 100., .2])[:len(columns)]
        scaled = slim.fit(a[columns]*factors)
        init = pd.Timestamp("2015-03-01")
        y = slim.predict(model, a.loc[init, columns], 3, months=9)
        ys = slim.predict(scaled, a.loc[init, columns]*factors, 3, months=9)/factors
        qa["max_unit_scaling_error"] = max(qa["max_unit_scaling_error"], float(abs(y-ys).max()))
    np.testing.assert_allclose(fits["RO"]["scale"], fits["RO_PMM"]["scale"][:2], atol=1e-12)
    scoring.dump(out / "models_and_preprocessing.json", dict(models=fits, preprocessing=meta))
    pd.DataFrame(audit).to_csv(out / "fit_diagnostics.csv", index=False)
    rows, state_rows = [], []
    for event in events.itertuples(index=False):
        for year in map(int, event.development_years.split(",")):
            for month in range(2, 7):
                init = pd.Timestamp(year, month, 1)
                dates = pd.date_range(init, periods=10, freq="MS")
                obs = raw.loc[dates, ["sst", "d20"]].to_numpy()-display.loc[dates.month, ["sst", "d20"]].to_numpy()
                predictions = {}
                for name, columns in MODELS.items():
                    model = fits[name]
                    initial = a.loc[init, columns].to_numpy()
                    pred, native = forecast(model, initial, dates, meta, display)
                    assert np.isfinite(pred).all() and np.isfinite(native).all()
                    qa["max_initial_error"] = max(qa["max_initial_error"], float(abs(pred[0]-obs[0]).max()))
                    refined, _ = forecast(model, initial, dates, meta, display, steps=48)
                    qa["max_rk4_error"] = max(qa["max_rk4_error"], float(abs(pred-refined).max()))
                    # Coefficients/preprocessing are deliberately frozen here;
                    # refitting on perturbed future data is NOT invariant in-sample.
                    changed = a.copy()
                    changed.loc[changed.index > init] += 999
                    check, _ = forecast(model, changed.loc[init, columns], dates, meta, display)
                    qa["max_fixed_model_future_observation_error"] = max(
                        qa["max_fixed_model_future_observation_error"], float(abs(pred-check).max()))
                    propagated = segmented.forecast(model, initial, month=month, months=9)
                    qa["max_propagator_error"] = max(qa["max_propagator_error"], float(abs(native-propagated).max()))
                    diff = (native[:, :2]-a.loc[dates, ["sst", "d20"]].to_numpy())-(pred-obs)
                    qa["max_restored_error_difference"] = max(qa["max_restored_error_difference"], float(abs(diff).max()))
                    predictions[name] = pred[:, 0]
                    for lead, target in enumerate(dates):
                        for j, variable in enumerate(columns):
                            state_rows.append(dict(event=event.event, model=name, init=init, target=target,
                                lead=lead, variable=variable, predicted_model_state=float(native[lead, j]),
                                initial_model_state=float(initial[j])))
                for lead, target in enumerate(dates):
                    rows.append(dict(event=event.event, strength=event.strength, development_year=year,
                        init=init, init_month=month, lead=lead, target=target, observed=float(obs[lead, 0]),
                        **{name: float(pred[lead]) for name, pred in predictions.items()}))
        print(f"Completed {event.event}: shared full-period D20 operators", flush=True)
    monthly = pd.DataFrame(rows)
    seasonal = scoring.seasonal_forecasts(monthly)
    monthly.to_csv(out / "monthly_forecasts.csv", index=False)
    seasonal.to_csv(out / "seasonal_forecasts.csv", index=False)
    pd.DataFrame(state_rows).to_csv(out / "forecast_model_states.csv", index=False)
    detailed, groups = scoring.score_tables(monthly, seasonal)
    detailed.to_csv(out / "event_scores.csv", index=False)
    groups.to_csv(out / "group_scores.csv", index=False)
    detailed.query("view == 'overall'").to_csv(out / "event_summary.csv", index=False)
    groups.query("view == 'overall'").to_csv(out / "group_summary.csv", index=False)
    assert qa["max_initial_error"] < 1e-10
    assert qa["max_rk4_error"] < 1e-5
    assert qa["max_unit_scaling_error"] < 1e-8
    assert qa["max_propagator_error"] < 1e-8
    assert qa["max_restored_error_difference"] < 1e-10
    assert qa["max_fixed_model_future_observation_error"] == 0
    qa.update(fits=len(fits), training_months_per_model=len(a), no_event_exclusions=True,
        unstable_fits=sum(not v["stable_annual"] for v in audit),
        annual_radius_min=min(v["annual_radius"] for v in audit),
        annual_radius_max=max(v["annual_radius_max"] for v in audit), **validate_saved(out))
    scoring.dump(out / "numerical_QA.json", qa)
    print(groups.query("target_type == 'monthly' and view == 'overall'").to_string(index=False), flush=True)


def save_manifest(out):
    paths = [scoring.ONI, manuscript.SOURCE / "raw_indices.csv", manuscript.PMM,
        EXACT / "models_exact_period.json", EXACT / "observations_detrended_2002Jan_2025Apr.csv"]
    paths += [ROOT / "scripts" / (name+".py") for name in (
        "analyze_enso_strength_fullperiod_d20", "report_enso_strength_fullperiod_d20",
        "analyze_enso_strength_pmm_skill", "report_enso_strength_pmm_skill",
        "plot_enso_strength_mean_trajectories", "paper_ro_slim", "three_event_segmented_slim", "run_paper_ro_pmm")]
    scoring.dump(out / "source_manifest.json", dict(
        sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        python=sys.version, platform=platform.platform(), numpy=np.__version__, pandas=pd.__version__,
        seed=scoring.SEED, bootstrap_replicates=scoring.N_BOOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate_saved(args.output), indent=2))
        return
    if not args.report_only:
        try:
            run(args.output)
        except Exception as exc:
            args.output.mkdir(parents=True, exist_ok=True)
            scoring.dump(args.output / "failures.json", [dict(error=repr(exc))])
            raise
    from report_enso_strength_fullperiod_d20 import report
    report(args.output)
    save_manifest(args.output)


if __name__ == "__main__":
    main()
