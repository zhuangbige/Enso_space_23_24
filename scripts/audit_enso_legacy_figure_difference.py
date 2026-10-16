#!/usr/bin/env python3
"""Explain the legacy slide versus current event plots without fitting new models."""
from pathlib import Path
import hashlib
import json
import os
import sys

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/maryland_enso_strength_mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

import paper_ro_slim as slim

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "outputs/research_2026/enso_strength_fullperiod_D20_20261015"
OLD = ROOT / "outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014"
SLIDE = ROOT / "outputs/interview_redesign_20261014/source_data"
OUT = NEW / "comparison_with_legacy"
YEARS = [1997, 2015, 2023]
COLORS = dict(RO="#0075BE", RO_PMM="#E56A0A", observed="#252A30")


def main():
    OUT.mkdir(exist_ok=True)
    f = pd.read_csv(NEW / "monthly_forecasts.csv", parse_dates=["init", "target"])
    f = f[f.development_year.isin(YEARS)].copy()
    old = pd.read_csv(SLIDE / "RO_PMM_three_event_trajectories.csv", parse_dates=["init", "center"])
    old_scores = pd.read_csv(SLIDE / "RO_PMM_three_event_metrics.csv")
    raw = pd.read_csv(NEW / "inputs_absolute.csv", index_col="time", parse_dates=True)
    climate = pd.read_csv(NEW / "display_climatology.csv", index_col="month")
    obs_monthly = raw.sst-climate.loc[raw.index.month, "sst"].to_numpy()
    obs_seasonal = obs_monthly.rolling(3, center=True, min_periods=3).mean()
    old_observations = pd.read_csv(OLD / "observations.csv", index_col=0, parse_dates=True)
    old_states = pd.read_csv(OLD / "processed_states_official_PMM.csv", index_col=0, parse_dates=True)
    old_archive = json.loads((OLD / "frozen_models_and_preprocessing.json").read_text())
    meta = old_archive["preprocessing"]
    old_model_max_error = 0.
    # Replay exactly the archived 2002--2024 operators: no refitting.
    for name in ["RO", "RO_SST"]:
        model = old_archive["fits"][name]
        model["coef"], model["scale"] = np.array(model["coef"]), np.array(model["scale"])
        for (year, init), part in old[old.method.eq(name)].groupby(["year", "init"]):
            dates = pd.date_range(init, periods=10, freq="MS")
            p = slim.predict(model, old_states.loc[init, model["columns"]], init.month, months=9)
            bg = np.array(meta["clim"])[dates.month-1]+np.column_stack(
                [np.ones(10), slim.decimal_time(dates)-meta["center"]])@np.array(meta["beta"])
            restored = p[:, 0]+bg[:, 0]-climate.loc[dates.month, "sst"].to_numpy()
            seasonal = pd.Series(restored, index=dates).rolling(3, center=True).mean()
            error = float(abs(seasonal.loc[part.center].to_numpy()-part.value.to_numpy()).max())
            old_model_max_error = max(old_model_max_error, error)
    assert old_model_max_error < 1e-10

    seasonal_rows = []
    for init, part in f.groupby("init"):
        g = part.sort_values("lead").set_index("lead")
        means = g[["observed", "RO", "RO_PMM"]].rolling(3, center=True, min_periods=3).mean()
        for lead in range(1, 9):
            seasonal_rows.append(dict(year=init.year, init=init, init_month=init.month,
                center=g.loc[lead, "target"], lead_center=lead, **means.loc[lead].to_dict()))
    new = pd.DataFrame(seasonal_rows)
    rows, differences, obs_error = [], [], 0.
    for year in YEARS:
        dates = pd.date_range(f"{year}-01-01", periods=15, freq="MS")
        obs_error = max(obs_error, float(abs(obs_seasonal.loc[dates]-old_observations.loc[dates, "seasonal_1991_2020"]).max()))
        o = old[old.year.eq(year)].copy()
        n = new[new.year.eq(year)].copy()
        for model, method in [("RO", "RO"), ("RO_PMM", "RO_SST")]:
            pair = n.merge(o[o.method.eq(method)], on=["year", "init", "center", "lead_center"], suffixes=("_new", "_old"), validate="one_to_one")
            assert len(pair) == 40
            np.testing.assert_allclose(pair.observed_new, pair.observed_old, atol=1e-10, rtol=0)
            delta = pair[model]-pair.value
            differences.append(dict(year=year, model=model, n_pairs=len(pair),
                mean_new_minus_old=float(delta.mean()), max_abs_new_minus_old=float(abs(delta).max()),
                rms_new_minus_old=float(np.sqrt(np.mean(delta**2)))))
        legacy = o.pivot(index=["year", "init", "center", "lead_center", "observed"], columns="method", values="value").reset_index().rename(columns={"RO_SST": "RO_PMM"})
        for label, sample in [("legacy_2002_2024_seasonal_L1_5", legacy.query("lead_center<=5")),
                               ("current_1982_2024_seasonal_L1_5", n.query("lead_center<=5")),
                               ("current_1982_2024_monthly_L1_9", f.query("development_year==@year and lead>0"))]:
            err = sample[["RO", "RO_PMM"]].to_numpy()-sample.observed.to_numpy()[:, None]
            rmse = np.sqrt(np.mean(err**2, axis=0))
            if label.startswith("legacy"):
                reference = old_scores[old_scores.year.eq(year)].set_index("model")
                np.testing.assert_allclose(rmse, reference.loc[["RO", "RO_SST"], "RMSE"], atol=1e-10, rtol=0)
            rows.append(dict(year=year, protocol=label, n_pairs=len(sample), RMSE_RO=rmse[0], RMSE_RO_PMM=rmse[1],
                improvement_percent=100*(1-rmse[1]/rmse[0])))
    assert obs_error < 1e-10
    scores = pd.DataFrame(rows)
    diff = pd.DataFrame(differences)
    new.to_csv(OUT / "current_seasonal_full_trajectories.csv", index=False)
    diff.to_csv(OUT / "same_coordinate_forecast_differences.csv", index=False)
    scores.to_csv(OUT / "score_definition_comparison.csv", index=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), sharex=True, sharey=True)
    fig.subplots_adjust(left=.065, right=.985, top=.865, bottom=.15, wspace=.17, hspace=.44)
    labels = ["Old fit · 3-month means", "New fit · 3-month means", "New fit · monthly values"]
    for j, year in enumerate(YEARS):
        dates = pd.date_range(f"{year}-01-01", periods=15, freq="MS")
        for i in range(3):
            ax = axes[i, j]
            for month in range(2, 7):
                if i == 0:
                    part = old[old.year.eq(year) & old.issue_month.eq(month)]
                    for name, method in [("RO", "RO"), ("RO_PMM", "RO_SST")]:
                        p = part[part.method.eq(method)].sort_values("center")
                        x = (p.center.dt.year-year)*12+p.center.dt.month
                        ax.plot(x, p.value, color=COLORS[name], lw=1.25, ls="--" if name == "RO" else "-")
                else:
                    p = new[new.year.eq(year) & new.init_month.eq(month)].sort_values("lead_center") if i == 1 else f[f.development_year.eq(year) & f.init_month.eq(month)].sort_values("lead")
                    times = p.center if i == 1 else p.target
                    x = (times.dt.year-year)*12+times.dt.month
                    for name in ("RO", "RO_PMM"):
                        ax.plot(x, p[name], color=COLORS[name], lw=1.25, ls="--" if name == "RO" else "-")
            truth = obs_monthly.loc[dates] if i == 2 else obs_seasonal.loc[dates]
            ax.plot(range(1, 16), truth, color=COLORS["observed"], lw=2.7)
            ax.set_title(f"{year}  |  {labels[i]}", loc="left", fontsize=12, color="#052D50", fontweight="bold", pad=12)
            ax.set(xlim=(1, 15), ylim=(-1.15, 3.15), xticks=[1, 5, 9, 13], yticks=[-1, 0, 1, 2, 3])
            ax.tick_params(length=0, labelbottom=True, labelleft=True)
            ax.grid(axis="y", color="#DBE4EB", lw=.7)
            for spine in ("left", "bottom"):
                ax.spines[spine].set_color("#BDCCD7")
            if j == 0:
                ax.set_ylabel("Niño-3.4 SSTA (°C)")
    fig.suptitle("Why the new curves differ from the earlier slide", fontsize=22, color="#052D50", fontweight="bold", y=.985)
    fig.text(.5, .94, "Top → middle: fitted period / preprocessing changes. Middle → bottom: three-month averaging only.", ha="center", fontsize=12, color="#4D606F")
    handles = [Line2D([], [], color=COLORS[n], lw=2.7 if n == "observed" else 1.5, ls="--" if n == "RO" else "-",
                       label={"observed": "Observed", "RO": "RO", "RO_PMM": "RO + PMM"}[n]) for n in ("observed", "RO", "RO_PMM")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, .92), ncol=3, frameon=False)
    fig.text(.5, .093, "Month of development year  (13 = January of following year)", ha="center", fontsize=11)
    fig.text(.065, .025, "Old fit: 2002–2024; new fit: 1982–2024. Same D20 state, seasonal sLIM estimator, February–June starts, and 1991–2020 reference.\n"
        "Three-month forecast centers use leads 1–8 (valid windows only); monthly forecasts include lead 0–9. No new parameter fitting in this audit.",
        fontsize=9.5, color="#5C6B78", linespacing=1.6)
    for extension in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"legacy_vs_current_comparison.{extension}", dpi=220, facecolor="white")
    plt.close(fig)
    qa = dict(legacy_frozen_model_replay_max_error=old_model_max_error,
        three_month_observation_match_max_error=obs_error, new_models_fitted=False,
        old_forecast_rows=len(old), new_seasonal_forecast_rows=len(new),
        model_state_definition_same=True, initialization_months_same=True,
        climatology_same=True, training_period_same=False, detrending_period_same=False)
    (OUT / "audit_QA.json").write_text(json.dumps(qa, indent=2)+"\n")
    explanation = (
        "旧图与新图差异核验\n\n"
        "1. 旧图是三个月中心滑动平均；新逐事件图是未经时间平滑的月值。"
        f"新观测取同样三个月平均后与旧图观测最大差{obs_error:.2e}°C，观测数据/气候态没有换。\n"
        "2. 旧图用冻结2002—2024模型，趋势拟合到2025年4月；新图用1982—2024模型，趋势拟合到2024年12月。"
        "两者都用D20、同一sLIM核心和2—6月初态，但重新估计的系数、尺度、趋势及PMM均值不同。"
        "这使统一三个月平均后的预报仍有真实差异，不能只归因于绘图。\n"
        "3. 旧表按三个月平均中心提前1—5月评分，新主表按月值提前1—9月评分；二者RMSE不能直接比较。"
        "下表另列统一旧评分定义的结果。2015仅比较2015起报，不混入2014。\n"
        "4. 旧图有效季节曲线从起报后第1个月到第8个月；新月值曲线包含起报月到第9个月，端点自然不同。\n\n"
        "比较图上排=旧模型/三个月平均，中排=新模型/三个月平均，下排=新模型/月值。\n\n"
    )
    (OUT / "difference_explanation_cn.txt").write_text(explanation+scores.to_string(index=False)+"\n\n"+diff.to_string(index=False)+"\n", encoding="utf-8")
    sources = [NEW / "monthly_forecasts.csv", NEW / "display_climatology.csv", NEW / "models_and_preprocessing.json",
        OLD / "frozen_models_and_preprocessing.json", OLD / "processed_states_official_PMM.csv",
        SLIDE / "RO_PMM_three_event_trajectories.csv", SLIDE / "RO_PMM_three_event_metrics.csv", Path(__file__).resolve()]
    (OUT / "source_manifest.json").write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2)+"\n")
    print(json.dumps(qa, indent=2), flush=True)
    print(scores.to_string(index=False), flush=True)
    print(OUT / "legacy_vs_current_comparison.png", flush=True)


if __name__ == "__main__":
    main()
