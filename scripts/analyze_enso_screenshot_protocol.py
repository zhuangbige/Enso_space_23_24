#!/usr/bin/env python3
"""Use the legacy screenshot protocol for a fixed 1982 or 2002 start year."""
from pathlib import Path
import argparse
import hashlib
import json

import numpy as np
import pandas as pd

import analyze_enso_strength_fullperiod_d20 as core
import analyze_enso_strength_pmm_skill as scoring
import paper_ro_slim as slim
import run_paper_ro_pmm as original

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/research_2026/enso_strength_screenshot_D20_20261015"
OLD = ROOT / "outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014"
SLIDE = ROOT / "outputs/interview_redesign_20261014/source_data"
TREND_END = "2025-04-01"
PROTOCOL = """Screenshot-matched protocol, user instruction 2026-10-15.
{period_rule} All fitting uses continuous data.
Operator fitting: {start_year}Jan--2024Dec ({fit_months} months); detrending:
{start_year}Jan--2025Apr ({trend_months} months). Original end dates are retained.
Climate: the complete fixed 1991--2020 monthly reference, regardless of fit start.
RO=[ERSSTv5 Nino3.4, GODAS mean D20], RO+PMM adds official PMM-SST. PMM is
centered over {start_year}--2024. Standard deviations use the same operator-fitting
period and ddof=0. D20=area-weighted 5S--5N,120E--80W mean, meters.
Reuse original prepare(), perturb2 annual/semiannual sLIM, 6x monthly linear
interpolation, covariance lags6/1, and RK4 24 substeps/month. No new estimator.
Exactly two primary models, fitted once for all events. Feb--Jun observed
monthly initial states; 9-month free integration, no later observed forcing.
Restore trend/background; subtract fixed 1991--2020 SST monthly climatology.
Both observation and prediction curves use centered 3-month arithmetic means.
Forecast means use ONLY the corresponding free trajectory: first center lead1
averages leads0,1,2; last center lead8 averages leads7,8,9. No partial windows,
observed forecast padding, or additional filtering. Plot all center leads1--8.
Observation curves: Jan of development year through next Mar; use actual
neighboring months at both ends. The Jan{start_year} observation uses Dec{previous_year}.
Primary scores: center leads1--5, five starts, 25 pairs/one-year case. Report
event-pooled Pearson r, RMSE and bias. r is not multi-year fixed-lead ACC.
Screenshot RMSE change=100*(RMSE_PMM/RMSE_RO-1); NEGATIVE means improvement.
For continuity also save improvement_percent=-RMSE_change_percent.
Select complete ONI events in {start_year}--2024 from the frozen original catalog:
{event_counts}. {development_years} development years, {n_starts} starts.
Sustained episodes retain separate development-year panels but each counts once
in group metrics. Average MSE/bias by event before grouping.
For composite curves average development years within each event first, then
give all events equal weight. Group curve errors are NOT used as skill scores.
5000 paired-event bootstrap draws, fixed seed20261015+group offset, no refits.
Primary plot range: x1--15 (Jan to next Mar), ticks1/5/9/13; y-1--3.5 degreesC.
Black observed, blue dashed RO, orange RO+PMM, no synthetic initial anchors.
This is an in-sample retrospective initialization comparison. Preserve older
monthly and leave-one-event-out outputs in their existing directories.
"""


def period_protocol(start_year):
    events = scoring.detect_events(scoring.read_oni(), start_year=start_year)
    counts = events.strength.value_counts()
    n_years = int(events.n_development_years.sum())
    return PROTOCOL.format(
        period_rule=("The ONLY protocol change is fit start 2002 -> 1982." if start_year == 1982
            else "Restore the original 2002--2024 fit and restrict comparisons to events in 2002--2024. No other settings change."),
        start_year=start_year, previous_year=start_year-1, fit_months=(2025-start_year)*12,
        trend_months=(2025-start_year)*12+4, development_years=n_years, n_starts=n_years*5,
        event_counts=f"{len(events)} events, strong{counts.strong}/moderate{counts.moderate}/weak{counts.weak}")


def legacy_check():
    """Returning the start to 2002 must reproduce both archived screenshot models."""
    raw, pmm, climate = original.load()
    raw, pmm = raw.loc[:TREND_END], pmm.loc[:TREND_END]
    a, meta = original.prepare(raw, pmm, "2002-01-01", core.END, paper=True, trend_end=TREND_END)
    archive = json.loads((OLD / "frozen_models_and_preprocessing.json").read_text())
    truth = pd.read_csv(SLIDE / "RO_PMM_three_event_trajectories.csv", parse_dates=["init", "center"])
    max_coef, max_scale, max_curve = 0., 0., 0.
    for name, columns in {"RO": original.V, "RO_SST": original.V+["PMM_SST"]}.items():
        model = slim.fit(a.loc["2002":core.END, columns])
        saved = archive["fits"][name]
        max_coef = max(max_coef, float(abs(model["coef"]-np.array(saved["coef"])).max()))
        max_scale = max(max_scale, float(abs(model["scale"]-np.array(saved["scale"])).max()))
        for init, part in truth[truth.method.eq(name)].groupby("init"):
            dates = pd.date_range(init, periods=10, freq="MS")
            pred = slim.predict(model, a.loc[init, columns], init.month, months=9)
            anomaly = original.restore(pred, dates, meta)[:, 0]-climate.loc[dates.month, "Nino34"].to_numpy()
            means = pd.Series(anomaly, index=dates).rolling(3, center=True, min_periods=3).mean()
            max_curve = max(max_curve, float(abs(means.loc[part.center].to_numpy()-part.value.to_numpy()).max()))
    assert max(max_coef, max_scale, max_curve) < 1e-10
    return dict(old_two_model_coefficient_max_error=max_coef, old_scale_max_error=max_scale,
                old_240_seasonal_values_max_error=max_curve, both_legacy_models_reproduced=True)


def seasonal_products(out):
    monthly = pd.read_csv(out / "monthly_forecasts.csv", parse_dates=["init", "target"])
    catalog = pd.read_csv(out / "event_catalog.csv", dtype={"development_years": str})
    development_years = [int(year) for years in catalog.development_years for year in years.split(",")]
    records = []
    for init, part in monthly.groupby("init"):
        g = part.sort_values("lead").set_index("lead")
        means = g[["observed", "RO", "RO_PMM"]].rolling(3, center=True, min_periods=3).mean()
        for lead in range(1, 9):
            row = g.loc[lead].to_dict()
            row.update(lead=lead, relative_month=init.month+lead, **means.loc[lead].to_dict())
            records.append(row)
    f = pd.DataFrame(records)
    assert len(f) == len(development_years)*40 and f.groupby("init").size().eq(8).all()
    f.to_csv(out / "seasonal_plot_forecasts.csv", index=False)
    raw, _, _ = original.load()
    raw = raw.loc[f"{min(development_years)-1}-12-01":f"{max(development_years)+1}-04-01", ["Nino34"]].rename(columns={"Nino34": "sst"})
    climate = pd.read_csv(out / "display_climatology.csv", index_col="month")
    obs = raw.sst-climate.loc[raw.index.month, "sst"].to_numpy()
    smoothed = obs.rolling(3, center=True, min_periods=3).mean()
    raw.to_csv(out / "observation_inputs.csv", index_label="time")
    pd.DataFrame(dict(monthly=obs, seasonal=smoothed)).to_csv(out / "observation_series.csv", index_label="time")
    obsrows = []
    for event in catalog.itertuples(index=False):
        for year in map(int, event.development_years.split(",")):
            dates = pd.date_range(f"{year}-01-01", periods=15, freq="MS")
            assert smoothed.loc[dates].notna().all()
            obsrows.extend(dict(event=event.event, strength=event.strength, development_year=year,
                time=t, relative_month=i+1, observed=float(smoothed.loc[t])) for i, t in enumerate(dates))
    observations = pd.DataFrame(obsrows)
    observations.to_csv(out / "seasonal_plot_observations.csv", index=False)
    event_keys = ["event", "strength", "init_month", "lead", "relative_month"]
    event_means = f.groupby(event_keys, as_index=False)[["observed", "RO", "RO_PMM"]].mean()
    means = event_means.groupby(event_keys[1:], as_index=False)[["observed", "RO", "RO_PMM"]].mean()
    event_obs = observations.groupby(["event", "strength", "relative_month"], as_index=False)["observed"].mean()
    mean_obs = event_obs.groupby(["strength", "relative_month"], as_index=False)["observed"].mean()
    assert len(event_means) == len(catalog)*40 and len(means) == 120 and len(mean_obs) == 45
    event_means.to_csv(out / "seasonal_event_mean_forecasts.csv", index=False)
    means.to_csv(out / "seasonal_group_mean_forecasts.csv", index=False)
    mean_obs.to_csv(out / "seasonal_group_mean_observations.csv", index=False)
    score_data = f[f.lead.le(5)]
    event_scores = pd.read_csv(out / "event_scores.csv").query("target_type == 'seasonal' and view == 'overall'").copy()
    for name in ("RO", "RO_PMM"):
        correlations = {event: np.corrcoef(part[name], part.observed)[0, 1] for event, part in score_data.groupby("event")}
        event_scores["r_"+name] = event_scores.event.map(correlations)
    event_scores["rmse_change_percent"] = -event_scores.improvement_percent
    event_scores.to_csv(out / "primary_event_summary.csv", index=False)
    groups = pd.read_csv(out / "group_scores.csv").query("target_type == 'seasonal'").copy()
    groups["rmse_change_percent"] = -groups.improvement_percent
    groups["change_ci_low"], groups["change_ci_high"] = -groups.ci_high, -groups.ci_low
    groups.to_csv(out / "primary_group_scores.csv", index=False)
    groups.query("view == 'overall'").to_csv(out / "primary_group_summary.csv", index=False)
    years = []
    for year, part in score_data.groupby("development_year"):
        row = dict(development_year=int(year), event=part.event.iloc[0], strength=part.strength.iloc[0], n_pairs=len(part))
        for name in ("RO", "RO_PMM"):
            row["RMSE_"+name] = float(np.sqrt(np.mean((part[name]-part.observed)**2)))
            row["r_"+name] = float(np.corrcoef(part[name], part.observed)[0, 1])
        row["rmse_change_percent"] = 100*(row["RMSE_RO_PMM"]/row["RMSE_RO"]-1)
        years.append(row)
    pd.DataFrame(years).to_csv(out / "development_year_summary.csv", index=False)


def validate(out):
    qa = core.validate_saved(out)
    f = pd.read_csv(out / "seasonal_plot_forecasts.csv", parse_dates=["init", "target"])
    m = pd.read_csv(out / "monthly_forecasts.csv", parse_dates=["init", "target"])
    obs = pd.read_csv(out / "seasonal_plot_observations.csv", parse_dates=["time"])
    raw = pd.read_csv(out / "observation_inputs.csv", index_col="time", parse_dates=True)
    clim = pd.read_csv(out / "display_climatology.csv", index_col="month")
    anomaly = raw.sst-clim.loc[raw.index.month, "sst"].to_numpy()
    maximum = 0.
    for row in f.itertuples(index=False):
        triplet = m[m.init.eq(row.init) & m.lead.between(row.lead-1, row.lead+1)]
        assert len(triplet) == 3 and row.lead in range(1, 9)
        for name in ("observed", "RO", "RO_PMM"):
            maximum = max(maximum, abs(float(triplet[name].mean()-getattr(row, name))))
        dates = pd.date_range(row.target-pd.DateOffset(months=1), periods=3, freq="MS")
        assert abs(row.observed-anomaly.loc[dates].mean()) < 1e-10
    for row in obs.itertuples(index=False):
        dates = pd.date_range(row.time-pd.DateOffset(months=1), periods=3, freq="MS")
        assert abs(row.observed-anomaly.loc[dates].mean()) < 1e-10
    assert len(obs) == m.development_year.nunique()*15 and maximum < 1e-10
    # Direct event weights independently validate the plotted class composites.
    composite = pd.read_csv(out / "seasonal_group_mean_forecasts.csv")
    weight_error = 0.
    for row in composite.itertuples(index=False):
        part = f[f.strength.eq(row.strength) & f.init_month.eq(row.init_month) & f.lead.eq(row.lead)]
        weights = np.array([1/(part.event.nunique()*part.event.eq(e).sum()) for e in part.event])
        actual = weights@part[["observed", "RO", "RO_PMM"]].to_numpy()
        weight_error = max(weight_error, float(abs(actual-np.array([row.observed, row.RO, row.RO_PMM])).max()))
    assert weight_error < 1e-10
    legacy_obs = pd.read_csv(OLD / "observations.csv", index_col=0, parse_dates=True)
    legacy_error = float(abs(obs.observed.to_numpy()-legacy_obs.loc[obs.time, "seasonal_1991_2020"].to_numpy()).max())
    assert legacy_error < 1e-10
    primary = pd.read_csv(out / "primary_event_summary.csv")
    for row in primary.itertuples(index=False):
        part = f[f.event.eq(row.event) & f.lead.le(5)]
        for name in ("RO", "RO_PMM"):
            assert abs(np.corrcoef(part[name], part.observed)[0, 1]-getattr(row, "r_"+name)) < 1e-10
        assert abs(row.rmse_change_percent+row.improvement_percent) < 1e-10
    qa.update(seasonal_forecast_rows=len(f), scored_seasonal_pairs=int(f.lead.le(5).sum()), observation_plot_rows=len(obs),
        rolling_mean_max_error=maximum, event_weighting_max_error=weight_error,
        old_observation_match_max_error=legacy_error, first_observation_has_previous_December=True,
        plotted_center_leads=list(range(1, 9)), scored_center_leads=list(range(1, 6)))
    protocol = json.loads((out / "analysis_protocol.json").read_text())
    if protocol["start"] == "2002-01-01":
        saved = json.loads((out / "models_and_preprocessing.json").read_text())
        archive = json.loads((OLD / "frozen_models_and_preprocessing.json").read_text())
        errors = []
        for new_name, old_name in [("RO", "RO"), ("RO_PMM", "RO_SST")]:
            for key in ("coef", "scale"):
                errors.append(float(abs(np.array(saved["models"][new_name][key])-np.array(archive["fits"][old_name][key])).max()))
        truth = pd.read_csv(SLIDE / "RO_PMM_three_event_trajectories.csv", parse_dates=["init", "center"])
        curve_errors = []
        for row in truth[truth.init.dt.year.isin(m.development_year.unique())].itertuples(index=False):
            match = f[f.init.eq(row.init) & f.target.eq(row.center)]
            assert len(match) == 1
            name = "RO" if row.method == "RO" else "RO_PMM"
            curve_errors.append(abs(float(match[name].iloc[0])-row.value))
        assert len(curve_errors) == 160 and max(errors+curve_errors) < 1e-10
        qa.update(current_models_equal_legacy_max_error=max(errors),
            current_2015_2023_curves_equal_legacy_max_error=max(curve_errors),
            current_legacy_overlap_values=len(curve_errors))
    return qa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, choices=[1982, 2002], default=1982)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.output is None:
        args.output = OUT if args.start_year == 1982 else ROOT / "outputs/research_2026/enso_strength_screenshot_D20_2002_2024_20261015"
    if args.validate_only:
        print(json.dumps(validate(args.output), indent=2)); return
    if not args.report_only:
        try:
            check = legacy_check()
            core.run(args.output, trend_end=TREND_END, protocol_text=period_protocol(args.start_year),
                start=f"{args.start_year}-01-01")
            protocol = json.loads((args.output / "analysis_protocol.json").read_text())
            protocol.update(reference="legacy screenshot", only_protocol_change=("fit start 2002 -> 1982" if args.start_year == 1982 else "none; only compare 2002--2024 events"),
                plotted_center_leads=list(range(1, 9)), primary_scored_center_leads=list(range(1, 6)),
                curve_average="centered 3-month", rmse_change_sign="negative means improvement")
            scoring.dump(args.output / "analysis_protocol.json", protocol)
            seasonal_products(args.output)
            scoring.dump(args.output / "screenshot_QA.json", {**check, **validate(args.output)})
        except Exception as exc:
            args.output.mkdir(parents=True, exist_ok=True)
            scoring.dump(args.output / "failures.json", [dict(error=repr(exc))]); raise
    from report_enso_screenshot_protocol import report
    report(args.output)
    core.save_manifest(args.output)
    path = args.output / "source_manifest.json"
    manifest = json.loads(path.read_text())
    files = [Path(__file__).resolve(), ROOT / "scripts/report_enso_screenshot_protocol.py",
        OLD / "frozen_models_and_preprocessing.json", SLIDE / "RO_PMM_three_event_trajectories.csv"]
    manifest["sha256"].update({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    scoring.dump(path, manifest)


if __name__ == "__main__":
    main()
