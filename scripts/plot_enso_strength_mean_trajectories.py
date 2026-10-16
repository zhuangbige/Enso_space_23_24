#!/usr/bin/env python3
"""Event-weighted Niño3.4 mean plumes, preserving each February--June start.

Uses saved leave-one-event-out predictions only; does not fit or score models.
Run after analyze_enso_strength_pmm_skill.py to append this panel to its report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/maryland_enso_strength_mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "outputs/research_2026/enso_strength_ro_pmm_20261015"
STEM = "Fig4_strength_mean_Nino34_trajectories"
GROUPS = (("strong", "Strong", 7), ("moderate", "Moderate", 3), ("weak", "Weak", 3))
BLUE, ORANGE, BLACK = "#0075BE", "#E56A0A", "#252A30"


def make_composites(out):
    monthly = pd.read_csv(out / "monthly_forecasts.csv", parse_dates=["init", "target"])
    catalog = pd.read_csv(out / "event_catalog.csv", dtype={"development_years": str})
    raw = pd.read_csv(out / "inputs_absolute.csv", index_col="time", parse_dates=True)
    climate = pd.read_csv(out / "display_climatology.csv", index_col="month")
    assert not monthly.duplicated(["event", "init", "lead"]).any()
    monthly["relative_month"] = (monthly.target.dt.year-monthly.development_year)*12 + monthly.target.dt.month
    assert (monthly.relative_month == monthly.init_month + monthly.lead).all()
    keys = ["event", "strength", "init_month", "lead", "relative_month"]
    values = ["RO", "RO_PMM", "observed"]
    # Two development years inside a sustained event are averaged before events.
    event_forecasts = monthly.groupby(keys, as_index=False)[values].mean()
    counts = monthly.groupby(keys).size().rename("n_development_years").reset_index()
    event_forecasts = event_forecasts.merge(counts, on=keys, validate="one_to_one")
    group_keys = keys[1:]
    forecasts = event_forecasts.groupby(group_keys, as_index=False)[values].mean()
    forecast_counts = event_forecasts.groupby(group_keys).size().rename("n_events").reset_index()
    forecasts = forecasts.merge(forecast_counts, on=group_keys, validate="one_to_one")

    obs_rows = []
    for event in catalog.itertuples(index=False):
        for year in map(int, event.development_years.split(",")):
            dates = pd.date_range(f"{year}-01-01", periods=15, freq="MS")
            anomaly = raw.loc[dates, "sst"].to_numpy()-climate.loc[dates.month, "sst"].to_numpy()
            assert np.isfinite(anomaly).all()
            obs_rows.extend(dict(event=event.event, strength=event.strength,
                development_year=year, relative_month=i+1, time=date, observed=float(value))
                for i, (date, value) in enumerate(zip(dates, anomaly)))
    obs_members = pd.DataFrame(obs_rows)
    event_observations = obs_members.groupby(["event", "strength", "relative_month"], as_index=False)["observed"].mean()
    observations = event_observations.groupby(["strength", "relative_month"], as_index=False)["observed"].mean()
    obs_counts = event_observations.groupby(["strength", "relative_month"]).size().rename("n_events").reset_index()
    observations = observations.merge(obs_counts, on=["strength", "relative_month"], validate="one_to_one")
    assert len(event_forecasts) == 650 and len(forecasts) == 150
    assert len(event_observations) == 195 and len(observations) == 45
    for group, _, n in GROUPS:
        assert forecasts.loc[forecasts.strength.eq(group), "n_events"].eq(n).all()
        assert observations.loc[observations.strength.eq(group), "n_events"].eq(n).all()
    # Saved observations must agree with source observations at every forecast target.
    expected_obs = raw.loc[monthly.target, "sst"].to_numpy()-climate.loc[monthly.target.dt.month, "sst"].to_numpy()
    raw_obs_error = float(np.max(abs(monthly.observed.to_numpy()-expected_obs)))
    observed_match = forecasts.merge(observations, on=["strength", "relative_month"], suffixes=("", "_full"), validate="many_to_one")
    composite_obs_error = float(np.max(abs(observed_match.observed-observed_match.observed_full)))
    start = forecasts[forecasts.lead.eq(0)]
    start_error = float(np.max(abs(start[["RO", "RO_PMM"]].to_numpy()-start.observed.to_numpy()[:, None])))
    assert max(raw_obs_error, composite_obs_error, start_error) < 1e-10

    # Independent explicit event weights: a two-year event receives 1/2 per year.
    manual_error = 0.
    for row in forecasts.itertuples(index=False):
        part = monthly[monthly.strength.eq(row.strength) & monthly.init_month.eq(row.init_month) & monthly.lead.eq(row.lead)]
        event_ids = part.event.unique()
        weights = np.array([1/(len(event_ids)*(part.event == e).sum()) for e in part.event])
        assert abs(weights.sum()-1) < 1e-12
        manual = weights @ part[values].to_numpy()
        manual_error = max(manual_error, float(np.max(abs(manual-np.array([getattr(row, v) for v in values])))))
    assert manual_error < 1e-10
    event_forecasts.to_csv(out / "mean_trajectory_event_forecasts.csv", index=False)
    forecasts.to_csv(out / "mean_trajectory_group_forecasts.csv", index=False)
    obs_members.to_csv(out / "mean_trajectory_observation_members.csv", index=False)
    event_observations.to_csv(out / "mean_trajectory_event_observations.csv", index=False)
    observations.to_csv(out / "mean_trajectory_group_observations.csv", index=False)
    qa = dict(events=13, development_years=15, groups={g: n for g, _, n in GROUPS},
        starts=[2, 3, 4, 5, 6], monthly_leads=list(range(10)), group_forecast_rows=len(forecasts),
        group_observation_rows=len(observations), saved_vs_raw_observation_error=raw_obs_error,
        shared_observation_composite_error=composite_obs_error, initial_identity_error=start_error,
        independent_event_weight_error=manual_error, models_refit=False, temporal_smoothing=False)
    (out / "mean_trajectory_QA.json").write_text(json.dumps(qa, indent=2)+"\n")
    return forecasts, observations


def plot(forecasts, observations, out, caption=None):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 3, figsize=(16.8, 4.9), sharex=True, sharey=True)
    fig.subplots_adjust(left=.055, right=.985, top=.76, bottom=.34, wspace=.24)
    for ax, (group, label, n) in zip(axes, GROUPS):
        obs = observations[observations.strength.eq(group)].sort_values("relative_month")
        for init_month in range(2, 7):
            fc = forecasts[forecasts.strength.eq(group) & forecasts.init_month.eq(init_month)].sort_values("lead")
            assert fc.lead.to_list() == list(range(10))
            ax.plot(fc.relative_month, fc.RO, color=BLUE, lw=1.3, ls=(0, (5, 4)), zorder=2)
            ax.plot(fc.relative_month, fc.RO_PMM, color=ORANGE, lw=1.3, zorder=3)
        ax.plot(obs.relative_month, obs.observed, color=BLACK, lw=2.8, zorder=4)
        # One small marker locates each shared initial state on the observed line.
        starts = obs[obs.relative_month.between(2, 6)]
        ax.scatter(starts.relative_month, starts.observed, s=17, facecolor="white", edgecolor=BLACK, linewidth=.8, zorder=5)
        ax.set_title(f"{label}   Niño-3.4 SSTA (°C)", fontsize=18, color="#052D50", fontweight="bold", pad=28, loc="left")
        ax.text(.015, .94, f"Mean of {n} events", transform=ax.transAxes, fontsize=10.5, color="#5C6B78", va="top")
        ax.set(xlim=(1, 15), ylim=(-1, 2.5), xticks=[1, 5, 9, 13], yticks=[-1, 0, 1, 2])
        ax.tick_params(axis="both", colors="#1D3346", labelsize=12, length=0, pad=9, labelleft=True)
        ax.spines["left"].set_color("#BDCCD7")
        ax.spines["bottom"].set_color("#BDCCD7")
        ax.spines["left"].set_linewidth(.7)
        ax.spines["bottom"].set_linewidth(.7)
        ax.grid(axis="y", color="#D9E2E9", lw=.65)
        ax.axhline(0, color="#B2C6D5", lw=.7, zorder=1)
    handles = [Line2D([], [], color=BLACK, lw=2.8, label="Observed"),
        Line2D([], [], color=BLUE, lw=1.3, ls=(0, (5, 4)), label="RO"),
        Line2D([], [], color=ORANGE, lw=1.3, label="RO + PMM")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, .13), ncol=3, frameon=False, handlelength=3.1, columnspacing=3)
    fig.text(.5, .245, "Month of development year   (13 = January of the following year)", ha="center", fontsize=11, color="#4D606F")
    fig.text(.055, .055, caption or "Five starts per model: February–June; 9-month free forecasts. Monthly ERSST anomalies relative to 1982–2022.\n"
        "Events carry equal weight; two development years are averaged within 1986–88 and 2014–16. Leave-one-event-out sLIM; RO uses total WWV26.",
        fontsize=9.5, color="#62717D", linespacing=1.65)
    for extension in ("png", "pdf", "svg"):
        fig.savefig(out / f"{STEM}.{extension}", dpi=260, facecolor="white")
    plt.close(fig)


def add_to_report(out):
    note = (
        "强、中、弱三组的Niño3.4距平平均轨迹；组内事件等权。每个起报月份分别平均，保留2、3、4、5、6月五个起报，"
        "蓝色虚线为RO，橙色实线为RO＋PMM，黑色粗线为观测，空心点标出五个共同初态。"
        "每条预报包含起报月及后续9个月；横轴1为发展年1月，13为次年1月，绘至次年3月。"
        "1986—88和2014—16各先将两个发展年按相对月份平均，再与其他事件等权合成。"
        "图中为月平均ERSST Niño3.4距平，相对1982–2022同月气候态；未平滑、未改动或重新拟合模型。"
        "这张均值轨迹图用于展示平均演变；不能把平均曲线之间的误差当作前一轮逐事件计算再汇总的RMSE。"
    )
    (out / "mean_trajectory_notes_cn.txt").write_text(note+"\n\n复现：在Maryland目录运行\n"
        "  .venv/bin/python scripts/plot_enso_strength_mean_trajectories.py\n"
        "如重建原完整报告，随后重跑上述脚本即可重新插入均值轨迹图。\n", encoding="utf-8")
    path = out / "index.html"
    if path.exists():
        page = path.read_text()
        start, end = "<!-- mean-trajectories:start -->", "<!-- mean-trajectories:end -->"
        if start in page:
            before, rest = page.split(start, 1)
            _, after = rest.split(end, 1)
            page = before+after
        block = f'''{start}<section><h2>强、中、弱：Niño3.4平均预报轨迹</h2>
<img src="{STEM}.png" alt="强中弱事件平均Niño3.4观测与五个起报的预报曲线">
<p>{note}</p><p><a href="{STEM}.pdf">PDF</a> · <a href="{STEM}.svg">SVG</a> ·
<a href="mean_trajectory_group_forecasts.csv">分组预报数据</a> ·
<a href="mean_trajectory_group_observations.csv">分组观测数据</a> ·
<a href="mean_trajectory_QA.json">合成核验</a></p></section>{end}'''
        anchor = "<section><h2>全部事件逐一核对</h2>"
        assert anchor in page
        path.write_text(page.replace(anchor, block+anchor, 1), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    forecasts, observations = make_composites(args.output)
    plot(forecasts, observations, args.output)
    add_to_report(args.output)
    paths = [Path(__file__).resolve()] + [args.output/f for f in
        ("monthly_forecasts.csv", "event_catalog.csv", "inputs_absolute.csv", "display_climatology.csv")]
    manifest = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (args.output / "mean_trajectory_source_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(args.output / f"{STEM}.png")


if __name__ == "__main__":
    main()
