#!/usr/bin/env python3
"""Link the SODA3 force-balance surface to SST growth and air-sea coupling.

The force-balance model is trained in leave-one-event-out mode.  Its zero
crossing is compared with the directly observed onset of sustained Date-Line
warm-volume transport acceleration, eastern-Pacific SST entry into a growing
warm state, and persistent central-Pacific westerly/coupled convection onsets.

The analysis deliberately separates a physical onset date from the date on
which a persistent run can be confirmed in real time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_soda3_balance_sequence")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest

sys.path.insert(0, str(ROOT / "scripts"))
import verify_soda3_force_balance_tendency as balance  # noqa: E402


EVENTS = balance.EVENTS
HIGHLIGHTS = (1997, 2015, 2023)
EAST_SST_LONS = tuple(np.arange(220.0, 241.0, 5.0))  # 140W-120W
RUN_LENGTH = 3
RNG_SEED = 20260803
N_BOOTSTRAP = 10000

RAW_TRANSPORT_DIR = ROOT / "data/interim/research_2026/soda3_5day_event_transport"
MONTHLY_REFERENCE = ROOT / "data/derived/research_2026/soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
WIND_ONSETS = ROOT / "data/derived/research_2026/soda3_5day_ohc_geometry_event_onsets.csv"
MONTHLY_COUPLING = ROOT / "data/derived/research_2026/enso_type_coupling_monthly_1982_2023.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_balance_transition_sequence"
PDF_DIR = ROOT / "output/pdf"
EVENT_CSV = DERIVED / "soda3_balance_transition_event_sequence.csv"
SENSITIVITY_CSV = DERIVED / "soda3_balance_transition_run_sensitivity.csv"
BOOTSTRAP_CSV = DERIVED / "soda3_balance_transition_lead_bootstrap.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_balance_transition_diagnostics.json"
FIGURE_PNG = OUT / "soda3_balance_transition_sequence.png"
FIGURE_PDF = PDF_DIR / "soda3_balance_transition_sequence.pdf"
REPORT_MD = OUT / "SODA3_BALANCE_TRANSITION_SEQUENCE_CN.md"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.4,
            "axes.titlesize": 9.8,
            "axes.labelsize": 8.8,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def build_balance_frame() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    base = pd.read_csv(balance.BASE_PENTADS, parse_dates=["time"])
    sections, anchor_qa = balance.read_and_anchor_sections()
    frame = base.merge(sections, on="time", how="left", validate="one_to_one")
    frame, time_qa = balance.add_tendencies(frame)
    predictions, _ = balance.loeo_linear(frame, "m180_tendency_future5")
    loeo = predictions.loc[
        predictions["model"].eq("d20_balance"),
        ["time", "year", "observed", "prediction"],
    ].rename(
        columns={
            "observed": "observed_transport_tendency_sv_day",
            "prediction": "loeo_balance_signal_sv_day",
        }
    )
    output = frame.merge(loeo, on=["time", "year"], how="left", validate="one_to_one")
    return output.sort_values(["year", "time"]), loeo, {**anchor_qa, **time_qa}


def build_east_sst() -> tuple[pd.DataFrame, dict[str, float]]:
    pieces = []
    for year in EVENTS:
        path = RAW_TRANSPORT_DIR / f"soda3_5day_transport_{year}_jan_jun.csv"
        current = pd.read_csv(path, parse_dates=["time"])
        pieces.append(current)
    raw = pd.concat(pieces, ignore_index=True)
    reference = pd.read_csv(MONTHLY_REFERENCE)
    within = raw.groupby(["year", "month", "longitude_e"])["sst_c"].transform("mean")
    raw = raw.merge(
        reference[["year", "month", "longitude_e", "sst_c_anom"]].rename(
            columns={"sst_c_anom": "_monthly_sst_anom"}
        ),
        on=["year", "month", "longitude_e"],
        how="left",
        validate="many_to_one",
    )
    if raw["_monthly_sst_anom"].isna().any():
        raise ValueError("Missing monthly SST anomaly anchor")
    raw["sst_anom_c"] = raw["sst_c"] - within + raw["_monthly_sst_anom"]

    reconstruction = raw.groupby(["year", "month", "longitude_e"])["sst_anom_c"].mean()
    target = (
        reference.loc[reference["year"].isin(EVENTS)]
        .set_index(["year", "month", "longitude_e"])["sst_c_anom"]
        .reindex(reconstruction.index)
    )
    error = float(np.nanmax(np.abs(reconstruction.to_numpy() - target.to_numpy())))

    east = (
        raw.loc[raw["longitude_e"].isin(EAST_SST_LONS)]
        .groupby(["time", "year"], as_index=False)["sst_anom_c"]
        .mean()
        .rename(columns={"sst_anom_c": "east_sst_anom_c"})
        .sort_values(["year", "time"])
    )
    pieces = []
    intervals = []
    for _, event in east.groupby("year", sort=True):
        event = event.copy().sort_values("time")
        dt = event["time"].shift(-1) - event["time"]
        days = dt.dt.total_seconds() / 86400.0
        intervals.extend(days.dropna().tolist())
        event["east_sst_tendency_future5_c_day"] = (
            event["east_sst_anom_c"].shift(-1) - event["east_sst_anom_c"]
        ) / days
        pieces.append(event)
    east = pd.concat(pieces, ignore_index=True)
    interval_array = np.asarray(intervals, dtype=float)
    if not np.all((interval_array >= 4.0) & (interval_array <= 6.0)):
        raise ValueError("Unexpected SST pentad interval")
    return east, {
        "sst_monthly_reconstruction_max_abs_error_c": error,
        "sst_pentad_interval_median_days": float(np.median(interval_array)),
    }


def first_positive_run(
    event: pd.DataFrame,
    column: str,
    run_length: int,
    *,
    start_month: int = 1,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Return run onset and the date the run itself is observable."""
    current = event.loc[event["time"].dt.month >= start_month].sort_values("time")
    values = current[column].to_numpy(dtype=float)
    times = pd.DatetimeIndex(current["time"])
    for index in range(len(values) - run_length + 1):
        window = values[index : index + run_length]
        previous = values[index - 1] if index > 0 else np.nan
        if (
            np.isfinite(window).all()
            and np.all(window > 0.0)
            and (index == 0 or not np.isfinite(previous) or previous <= 0.0)
        ):
            return pd.Timestamp(times[index]), pd.Timestamp(times[index + run_length - 1])
    return None, None


def observed_transport_episode(
    event: pd.DataFrame,
    run_length: int,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Positive future tendencies need one additional state to be confirmed."""
    onset, _ = first_positive_run(event, "m180_tendency_future5", run_length)
    if onset is None:
        return None, None
    current = event.sort_values("time").reset_index(drop=True)
    index = int(current.index[current["time"].eq(onset)][0])
    confirmation_index = index + run_length
    confirmation = (
        pd.Timestamp(current.loc[confirmation_index, "time"])
        if confirmation_index < len(current)
        else onset + pd.Timedelta(days=5 * run_length)
    )
    return onset, confirmation


def east_sst_warm_entry(event: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """First post-January growing warm state in the 140W-120W SODA3 SST."""
    current = event.loc[event["time"].dt.month >= 2].sort_values("time").reset_index(drop=True)
    sst = current["east_sst_anom_c"].to_numpy(dtype=float)
    tendency = current["east_sst_tendency_future5_c_day"].to_numpy(dtype=float)
    for index in range(len(current) - RUN_LENGTH + 1):
        warm = sst[index : index + RUN_LENGTH] > 0.0
        growing = tendency[index : index + RUN_LENGTH] > 0.0
        if np.all(warm) and int(np.sum(growing)) >= 2:
            onset = pd.Timestamp(current.loc[index, "time"])
            confirm_index = min(index + RUN_LENGTH, len(current) - 1)
            return onset, pd.Timestamp(current.loc[confirm_index, "time"])
    return None, None


def load_atmospheric_onsets() -> tuple[dict[int, pd.Timestamp | None], dict[int, pd.Timestamp | None]]:
    wind = pd.read_csv(WIND_ONSETS)
    wind_lookup = {
        int(row.year): (
            None if pd.isna(row.coupling_onset_date) else pd.Timestamp(row.coupling_onset_date)
        )
        for row in wind.itertuples()
    }
    monthly = pd.read_csv(MONTHLY_COUPLING, parse_dates=["time"])
    atmosphere_lookup: dict[int, pd.Timestamp | None] = {}
    for year in EVENTS:
        current = monthly.loc[
            monthly["year"].eq(year) & monthly["month"].between(3, 6)
        ].sort_values("month")
        coupled = current.loc[
            current["u850_cwp_anom_ms"].gt(0.0)
            & current["olr_cp_anom_wm2"].lt(0.0)
        ]
        atmosphere_lookup[int(year)] = (
            None
            if coupled.empty
            else pd.Timestamp(year=int(year), month=int(coupled.iloc[0]["month"]), day=15)
        )
    return wind_lookup, atmosphere_lookup


def date_or_nat(value: pd.Timestamp | None) -> pd.Timestamp:
    return pd.NaT if value is None else pd.Timestamp(value)


def build_event_table(
    frame: pd.DataFrame,
    east_sst: pd.DataFrame,
    run_length: int = RUN_LENGTH,
) -> pd.DataFrame:
    wind_lookup, atmosphere_lookup = load_atmospheric_onsets()
    rows = []
    for year in EVENTS:
        ocean = frame.loc[frame["year"].eq(year)].copy()
        sst = east_sst.loc[east_sst["year"].eq(year)].copy()
        balance_onset, balance_available = first_positive_run(
            ocean, "loeo_balance_signal_sv_day", run_length
        )
        transport_onset, transport_available = observed_transport_episode(ocean, run_length)
        sst_onset, sst_available = east_sst_warm_entry(sst)
        wind_onset = wind_lookup[int(year)]
        atmosphere_onset = atmosphere_lookup[int(year)]
        row = {
            "year": int(year),
            "loeo_balance_crossing_date": date_or_nat(balance_onset),
            "loeo_balance_available_date": date_or_nat(balance_available),
            "transport_acceleration_onset_date": date_or_nat(transport_onset),
            "transport_acceleration_available_date": date_or_nat(transport_available),
            "east_sst_warm_entry_date": date_or_nat(sst_onset),
            "east_sst_warm_entry_available_date": date_or_nat(sst_available),
            "soda3_westerly_onset_date": date_or_nat(wind_onset),
            "era5_olr_coupled_month_midpoint": date_or_nat(atmosphere_onset),
        }
        for prefix, start in (
            ("balance_candidate", balance_onset),
            ("balance_available", balance_available),
            ("transport_candidate", transport_onset),
            ("transport_available", transport_available),
        ):
            for target, end in (
                ("sst", sst_onset),
                ("wind", wind_onset),
                ("atmos", atmosphere_onset),
            ):
                row[f"{prefix}_lead_to_{target}_days"] = (
                    np.nan if start is None or end is None else float((end - start).days)
                )
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_leads(event_table: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for source in (
        "balance_candidate",
        "balance_available",
        "transport_candidate",
        "transport_available",
    ):
        for target in ("sst", "wind", "atmos"):
            column = f"{source}_lead_to_{target}_days"
            values = event_table[column].dropna().to_numpy(dtype=float)
            if len(values) == 0:
                continue
            samples = np.empty(N_BOOTSTRAP)
            for index in range(N_BOOTSTRAP):
                selected = rng.integers(0, len(values), len(values))
                samples[index] = np.median(values[selected])
            positive = int(np.sum(values > 0.0))
            rows.append(
                {
                    "source": source,
                    "target": target,
                    "n_events": len(values),
                    "median_lead_days": float(np.median(values)),
                    "ci_low": float(np.quantile(samples, 0.025)),
                    "ci_high": float(np.quantile(samples, 0.975)),
                    "positive_lead_events": positive,
                    "positive_lead_fraction": float(positive / len(values)),
                    "sign_test_one_sided_p": float(
                        binomtest(positive, len(values), 0.5, alternative="greater").pvalue
                    ),
                }
            )
    return pd.DataFrame(rows)


def run_sensitivity(frame: pd.DataFrame, east_sst: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run_length in (2, 3, 4):
        table = build_event_table(frame, east_sst, run_length=run_length)
        for source in ("balance_candidate", "balance_available", "transport_candidate", "transport_available"):
            values = table[f"{source}_lead_to_wind_days"].dropna().to_numpy(dtype=float)
            positive = int(np.sum(values > 0.0))
            rows.append(
                {
                    "run_length": run_length,
                    "source": source,
                    "n_events": len(values),
                    "median_lead_to_wind_days": float(np.median(values)),
                    "positive_lead_events": positive,
                    "positive_lead_fraction": float(positive / len(values)),
                    "sign_test_one_sided_p": float(
                        binomtest(positive, len(values), 0.5, alternative="greater").pvalue
                    ),
                }
            )
    return pd.DataFrame(rows)


def day_of_year(series: pd.Series) -> np.ndarray:
    return pd.to_datetime(series).dt.dayofyear.to_numpy(dtype=float)


def plot_result(
    frame: pd.DataFrame,
    event_table: pd.DataFrame,
    bootstrap: pd.DataFrame,
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.7, 8.3))
    figure.subplots_adjust(left=0.085, right=0.975, bottom=0.11, top=0.91, wspace=0.24, hspace=0.32)

    # (a) Event timeline.
    ax = axes[0, 0]
    timeline = event_table.sort_values("year").reset_index(drop=True)
    y = np.arange(len(timeline))
    date_columns = {
        "transport_acceleration_onset_date": ("Transport acceleration", ">", "#2C7FB8"),
        "east_sst_warm_entry_date": ("East SST warm entry", "s", "#F28E2B"),
        "soda3_westerly_onset_date": ("Persistent westerlies", "D", "#B7352D"),
        "era5_olr_coupled_month_midpoint": ("ERA5 wind + OLR", "*", "#6A3D9A"),
    }
    for column, (label, marker, color) in date_columns.items():
        values = day_of_year(timeline[column])
        valid = np.isfinite(values)
        ax.scatter(values[valid], y[valid], marker=marker, s=31 if marker != "*" else 48,
                   color=color, edgecolor="white", linewidth=0.45, label=label, zorder=4)
    for index, row in timeline.iterrows():
        start = row["transport_acceleration_available_date"]
        end = row["soda3_westerly_onset_date"]
        if pd.notna(start) and pd.notna(end):
            x0, x1 = pd.Timestamp(start).dayofyear, pd.Timestamp(end).dayofyear
            ax.plot([x0, x1], [index, index], color="#B8B8B8", lw=1.0, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels(timeline["year"].astype(str))
    for label in ax.get_yticklabels():
        if int(label.get_text()) in HIGHLIGHTS:
            label.set_fontweight("bold")
    ax.set_xlim(1, 245)
    ax.set_xticks([1, 32, 61, 92, 122, 153, 183, 214, 245])
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"])
    ax.grid(axis="x", color="#E4E4E4", lw=0.6)
    ax.set_title("(a) Ocean acceleration usually precedes atmospheric establishment", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=2, loc="lower right")

    # (b) Event-by-event lead to the persistent-westerly onset.
    ax = axes[0, 1]
    years = event_table["year"].to_numpy(dtype=int)
    x = np.arange(len(years))
    direct = event_table["transport_available_lead_to_wind_days"].to_numpy(dtype=float)
    plane = event_table["balance_available_lead_to_wind_days"].to_numpy(dtype=float)
    ax.axhline(0.0, color="#333333", lw=0.8)
    ax.scatter(x - 0.12, direct, color="#2C7FB8", s=25, marker="o", label="Observed transport signal available")
    ax.scatter(x + 0.12, plane, color="#8C6BB1", s=25, marker="s", label="LOEO balance crossing available")
    for index, year in enumerate(years):
        if year in HIGHLIGHTS:
            ax.axvspan(index - 0.42, index + 0.42, color="#F4EBD8", alpha=0.65, zorder=0)
    ax.set_xticks(x)
    ax.set_xticklabels(years.astype(str), rotation=45, ha="right")
    ax.set_ylabel("Lead to persistent westerlies (days)")
    ax.set_title("(b) Direct transport change is the more stable timing marker", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    # (c) Highlighted event signals aligned to persistent-westerly onset.
    ax = axes[1, 0]
    colors = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}
    onset_lookup = event_table.set_index("year")["soda3_westerly_onset_date"]
    for year in HIGHLIGHTS:
        current = frame.loc[frame["year"].eq(year)].dropna(
            subset=["m180_tendency_future5", "loeo_balance_signal_sv_day"]
        ).copy()
        onset = pd.Timestamp(onset_lookup.loc[year])
        current["relative_days"] = (current["time"] - onset).dt.days
        selected = current.loc[current["relative_days"].between(-125, 45)]
        ax.plot(selected["relative_days"], selected["m180_tendency_future5"],
                color=colors[year], lw=1.45, label=f"{year} observed")
        ax.plot(selected["relative_days"], selected["loeo_balance_signal_sv_day"],
                color=colors[year], lw=1.05, ls="--", alpha=0.78, label=f"{year} balance")
    ax.axhline(0.0, color="#444444", lw=0.7)
    ax.axvline(0.0, color="#111111", lw=0.9, ls=":")
    ax.set_xlim(-125, 45)
    ax.set_xlabel("Days relative to persistent-westerly onset")
    ax.set_ylabel("Warm-volume transport tendency (Sv day⁻¹)")
    ax.set_title("(c) The reduced balance misses important event-specific pulses", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    ax.grid(axis="x", color="#E5E5E5", lw=0.5)

    # (d) Candidate versus operationally available lead summaries.
    ax = axes[1, 1]
    target_labels = {"sst": "East SST warm entry", "wind": "Persistent westerlies", "atmos": "ERA5 wind + OLR"}
    target_x = {"sst": 0.0, "wind": 1.0, "atmos": 2.0}
    styles = {
        "transport_candidate": ("Physical onset estimate", "#2C7FB8", "o", -0.10),
        "transport_available": ("Signal available in real time", "#0B4F6C", "s", 0.10),
    }
    for source, (label, color, marker, offset) in styles.items():
        current = bootstrap.loc[bootstrap["source"].eq(source)]
        for row in current.itertuples():
            xpos = target_x[row.target] + offset
            ax.errorbar(
                xpos,
                row.median_lead_days,
                yerr=[[row.median_lead_days - row.ci_low], [row.ci_high - row.median_lead_days]],
                color=color,
                marker=marker,
                ms=5.0,
                capsize=3,
                lw=1.2,
            )
            ax.text(xpos, row.ci_high + 7, f"{row.positive_lead_events}/{row.n_events}",
                    ha="center", va="bottom", fontsize=6.8, color=color)
        ax.plot([], [], color=color, marker=marker, ls="none", label=label)
    ax.axhline(0.0, color="#333333", lw=0.8)
    ax.set_xticks(list(target_x.values()))
    ax.set_xticklabels([target_labels[key] for key in target_x], rotation=12, ha="right")
    ax.set_ylabel("Median lead (days; event-bootstrap 95% CI)")
    ax.set_title("(d) Transport acceleration is an ocean-first indicator", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    figure.suptitle(
        "From force balance to transition timing: a 13-event SODA3 sequence test",
        fontsize=13.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "Five-day SODA3, detrended 1980-2024 monthly anchor. Balance signal is strictly leave-one-event-out. "
        "ERA5+OLR timing is monthly (mid-month marker, about +/-15-day uncertainty).",
        ha="center",
        fontsize=7.0,
        color="#555555",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def selected_summary(bootstrap: pd.DataFrame, source: str, target: str) -> pd.Series:
    return bootstrap.loc[
        bootstrap["source"].eq(source) & bootstrap["target"].eq(target)
    ].iloc[0]


def main() -> int:
    frame, _, balance_qa = build_balance_frame()
    east_sst, sst_qa = build_east_sst()
    event_table = build_event_table(frame, east_sst)
    bootstrap = bootstrap_leads(event_table)
    sensitivity = run_sensitivity(frame, east_sst)

    direct_sst = selected_summary(bootstrap, "transport_candidate", "sst")
    direct_wind = selected_summary(bootstrap, "transport_candidate", "wind")
    available_wind = selected_summary(bootstrap, "transport_available", "wind")
    direct_atmos = selected_summary(bootstrap, "transport_candidate", "atmos")
    balance_wind = selected_summary(bootstrap, "balance_candidate", "wind")
    sensitivity_available = {
        int(row.run_length): row
        for row in sensitivity.loc[
            sensitivity["source"].eq("transport_available")
        ].itertuples()
    }

    diagnostics = {
        "events": list(EVENTS),
        "primary_run_length_pentads": RUN_LENGTH,
        "transport_candidate_definition": "first three consecutive positive future-five-day Date-Line warm-volume transport tendencies",
        "transport_available_definition": "fourth transport state, 15 days after candidate onset",
        "east_sst_definition": "SODA3 140W-120W anomaly positive for three pentads with at least two positive five-day tendencies",
        "westerly_onset_definition": "post-February SODA3 central stress: first two pentads positive and at least four of six positive",
        "independent_atmosphere_definition": "first Mar-Jun month with ERA5 u850 anomaly >0 and OLR anomaly <0; plotted at month midpoint",
        "quality_control": {**balance_qa, **sst_qa},
        "caveats": [
            "The reduced D20-wind-transport balance is a proxy, not a closed momentum budget.",
            "Monthly ERA5+OLR onset has approximately plus/minus 15-day timing uncertainty.",
            "Onset rules are diagnostic; only the transport-available date is interpreted operationally.",
        ],
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    event_table.to_csv(EVENT_CSV, index=False, date_format="%Y-%m-%d")
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)
    bootstrap.to_csv(BOOTSTRAP_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    plot_result(frame, event_table, bootstrap)

    report = f"""# SODA3受力平衡面到海气耦合转折的事件序列检验

## 问题

受力平衡面确实存在，但它是否能够给出一个可操作的ENSO转折时刻？本阶段把13次暖事件依次拆成四个节点：

1. 留一事件估计的D20压力—风—已有输送平衡面穿越；
2. 日界线暖水体积输送连续三个五日加速；
3. SODA3东部140°W—120°W进入持续增长的正SST异常；
4. 中太平洋持续西风建立，以及ERA5西风与负OLR同时出现。

## 结果

### 直接输送变化是目前最稳定的先行节点

- 暖水输送加速起点领先东部SST暖态进入：中位 `{direct_sst['median_lead_days']:.0f}` 天，`{int(direct_sst['positive_lead_events'])}/{int(direct_sst['n_events'])}` 次事件方向一致，单侧符号检验 `p={direct_sst['sign_test_one_sided_p']:.3f}`。
- 领先SODA3持续西风建立：中位 `{direct_wind['median_lead_days']:.0f}` 天，`{int(direct_wind['positive_lead_events'])}/{int(direct_wind['n_events'])}` 次，`p={direct_wind['sign_test_one_sided_p']:.4f}`。
- 连续三个五日加速需要15天才能被实时确认；即使从确认日计算，仍领先持续西风中位 `{available_wind['median_lead_days']:.0f}` 天，`{int(available_wind['positive_lead_events'])}/{int(available_wind['n_events'])}` 次，`p={available_wind['sign_test_one_sided_p']:.3f}`。
- 对ERA5西风与负OLR共同出现的独立月尺度检查，候选起点领先中位 `{direct_atmos['median_lead_days']:.0f}` 天，`{int(direct_atmos['positive_lead_events'])}/{int(direct_atmos['n_events'])}` 个可判定事件方向一致；但月资料存在约±15天时间不确定性。

### 先行信号表现为短脉冲，而不是连续一个月的平滑加速

- 要求连续2个五日加速时，实时可用信号领先西风中位 `{sensitivity_available[2].median_lead_to_wind_days:.0f}` 天，`{int(sensitivity_available[2].positive_lead_events)}/{int(sensitivity_available[2].n_events)}` 次方向一致。
- 主定义连续3个五日时为 `{sensitivity_available[3].median_lead_to_wind_days:.0f}` 天和 `{int(sensitivity_available[3].positive_lead_events)}/{int(sensitivity_available[3].n_events)}` 次。
- 强制连续4个五日时降为 `{sensitivity_available[4].median_lead_to_wind_days:.0f}` 天和 `{int(sensitivity_available[4].positive_lead_events)}/{int(sensitivity_available[4].n_events)}` 次，不再稳定。这表明有效前兆更像10—15天的暖水输送脉冲；不能把它表述成持续整月、单调增强的背景流。

### 现有平衡面只能解释倾向，暂时不能精确报出转折日

- 留一事件平衡面穿越领先持续西风的中位数为 `{balance_wind['median_lead_days']:.0f}` 天，但只有 `{int(balance_wind['positive_lead_events'])}/{int(balance_wind['n_events'])}` 次方向一致，单侧 `p={balance_wind['sign_test_one_sided_p']:.3f}`。
- 1997年平衡面代理直到5月底才形成稳定正值，明显晚于2月的实际输送加速和3月的大气响应；2015年三五日稳定穿越没有被该简化模型识别。
- 因而，D20坡度、风应力和已有输送构成的经验平衡面在总体上能解释 `dM/dt`，但缺失Kelvin波相位、脉冲式西风、非线性平流和经向收支后，事件级穿越日期仍不可靠。

## 对“临界点”的修正表述

可以把转变写成两层：

1. **物理临界面**：完整动量和热量收支满足 `dM/dt=0`；
2. **可观测转折指标**：日界线暖水体积输送由减速转为持续加速。

目前资料对第二层的支持强于用简化受力代理直接定位第一层。也就是说，受力平衡点很可能真实存在，但现阶段最接近可预测量的是“持续暖水输送加速是否已经出现”，而不是一个固定的西部OHC阈值。

## 2023年的含义

2023年暖水输送加速候选起点为 `{event_table.loc[event_table['year'].eq(2023), 'transport_acceleration_onset_date'].iloc[0].date()}`，实时确认日为 `{event_table.loc[event_table['year'].eq(2023), 'transport_acceleration_available_date'].iloc[0].date()}`，SODA3持续西风直到 `{event_table.loc[event_table['year'].eq(2023), 'soda3_westerly_onset_date'].iloc[0].date()}` 才建立。确认后仍有 `{event_table.loc[event_table['year'].eq(2023), 'transport_available_lead_to_wind_days'].iloc[0]:.0f}` 天海洋先行窗口，明显长于1997和2015，正是“海洋已向东释放、但大气迟迟未接上”的量化表现。

## 输出

- 图：`{FIGURE_PDF}`
- 逐事件时间表：`{EVENT_CSV}`
- 持续长度敏感性：`{SENSITIVITY_CSV}`
- 事件自助区间：`{BOOTSTRAP_CSV}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
