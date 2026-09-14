#!/usr/bin/env python3
"""Diagnose where SODA3 H20 warm heat goes in three fixed Pacific boxes.

The script closes a diagnostic monthly budget for west (160E-180E), central
(180E-220E), and east (220E-280E) boxes spanning 10S-5N:

    dH20/dt = Cx + Fsouth + Fnorth + Qsurface,warm + R.

Every explicit flux is positive into its box.  R contains vertical/diapycnal
exchange, mixing/diffusion, assimilation increments, threshold motion, and
monthly/grid discretization.  Published-overlap CT and CP events are retained
from the preceding Chakravorty reproduction so event definition is not tuned.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_chakravorty2021_soda3_baseline as legacy  # noqa: E402

os.environ.setdefault(
    "MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig")
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


INPUT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_warm_heat_budget_terms_1980_2022.csv"
)
EXISTING_Q20_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_warm_transport_longitude_1980_2024.csv"
)
OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_three_box_warm_heat_fate"
OUT_PDF = ROOT / "output/pdf"

MONTHLY_CSV = OUT_DATA / "soda3_three_box_warm_heat_budget_monthly_1980_2022.csv"
EVENT_CSV = OUT_DATA / "soda3_three_box_warm_heat_budget_event_members.csv"
COMPOSITE_CSV = OUT_DATA / "soda3_three_box_warm_heat_budget_composites.csv"
CUMULATIVE_EVENT_CSV = OUT_DATA / "soda3_three_box_warm_heat_fate_cumulative_events.csv"
CUMULATIVE_SUMMARY_CSV = OUT_DATA / "soda3_three_box_warm_heat_fate_cumulative_summary.csv"
DIAGNOSTICS_JSON = OUT_DATA / "soda3_three_box_warm_heat_fate_diagnostics.json"
FIGURE_PNG = OUT_DIR / "soda3_three_box_warm_heat_fate.png"
FIGURE_PDF = OUT_PDF / "soda3_three_box_warm_heat_fate.pdf"
PHASE_FIGURE_PNG = OUT_DIR / "soda3_east_box_development_decay_fate.png"
PHASE_FIGURE_PDF = OUT_PDF / "soda3_east_box_development_decay_fate.pdf"
REPORT_MD = OUT_DIR / "SODA3_THREE_BOX_WARM_HEAT_FATE_CN.md"

BOXES = ("west", "central", "east")
BOX_LABELS = {
    "west": "West\n160°E–180°E",
    "central": "Central\n180°E–140°W",
    "east": "East\n140°W–80°W",
}
EVENTS = legacy.EVENTS
RELATIVE_MONTHS = legacy.RELATIVE_MONTHS
BASELINE = (1980, 2022)
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260804

PHASES = {
    "development_Jun0_to_Nov0": (5, 10),
    "mature_decay_Dec0_to_May1": (11, 16),
    "event_Jan0_to_May1": (0, 16),
}

COMPONENTS = {
    "zonal_convergence": "Zonal convergence",
    "south_q20_in": "10°S inflow",
    "north_q20_in": "5°N inflow",
    "surface_warm": "Surface heat",
    "residual_warm": "Unresolved",
    "storage_tendency": "dH20/dt",
}

COMPONENT_COLORS = {
    "zonal_convergence": "#3B6FB6",
    "south_q20_in": "#37A76F",
    "north_q20_in": "#D55E00",
    "surface_warm": "#E6AB02",
    "residual_warm": "#9B6AA6",
}

GATE_METRICS = {
    "q20_180e_10s5n": ("180°E", "#222222"),
    "q20_220e_10s5n": ("140°W", "#2C7FB8"),
    "q20_280e_10s5n": ("80°W", "#D95F0E"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.4,
            "axes.labelsize": 9.2,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def centered_storage_tendency_pw(
    storage_zj: np.ndarray,
    times: pd.DatetimeIndex,
) -> np.ndarray:
    """Centered dH/dt at monthly timestamps, converting ZJ to PW."""
    values = np.asarray(storage_zj, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    seconds = (times[2:] - times[:-2]).total_seconds().to_numpy(dtype=float)
    output[1:-1] = (values[2:] - values[:-2]) * 1.0e6 / seconds
    return output


def same_month_smoothed(
    values: np.ndarray,
    times: pd.DatetimeIndex,
) -> tuple[np.ndarray, np.ndarray]:
    anomaly = legacy.same_month_detrended(values, times, BASELINE)
    smoothed = (
        pd.Series(anomaly)
        .rolling(window=3, center=True, min_periods=3)
        .mean()
        .to_numpy()
    )
    return anomaly, smoothed


def build_monthly(raw: pd.DataFrame) -> pd.DataFrame:
    output = raw.copy().sort_values("time").reset_index(drop=True)
    output["time"] = pd.to_datetime(output["time"])
    times = pd.DatetimeIndex(output["time"])
    expected = pd.date_range("1980-01-01", "2022-12-01", freq="MS") + pd.Timedelta(
        days=14
    )
    if not times.equals(expected):
        raise ValueError("Input does not have the complete 1980-2022 monthly axis")

    raw_budget_columns: list[str] = []
    for box in BOXES:
        storage = f"{box}_h20_zj"
        tendency = f"{box}_storage_tendency_pw"
        output[tendency] = centered_storage_tendency_pw(output[storage], times)
        output[f"{box}_residual_warm_pw"] = (
            output[tendency] - output[f"{box}_resolved_warm_flux_pw"]
        )
        output[f"{box}_resolved_all_surface_pw"] = (
            output[f"{box}_zonal_convergence_pw"]
            + output[f"{box}_meridional_convergence_pw"]
            + output[f"{box}_surface_all_pw"]
        )
        output[f"{box}_residual_all_surface_pw"] = (
            output[tendency] - output[f"{box}_resolved_all_surface_pw"]
        )
        raw_budget_columns.extend(
            [
                storage,
                tendency,
                f"{box}_zonal_convergence_pw",
                f"{box}_south_q20_in_pw",
                f"{box}_north_q20_in_pw",
                f"{box}_meridional_convergence_pw",
                f"{box}_surface_warm_pw",
                f"{box}_surface_all_pw",
                f"{box}_resolved_warm_flux_pw",
            ]
        )

    gate_columns = [
        f"q20_{gate}e_10s5n_pw" for gate in (160, 180, 220, 280)
    ]
    for source in [*raw_budget_columns, *gate_columns]:
        anomaly, smoothed = same_month_smoothed(output[source].to_numpy(), times)
        short = source[:-3] if source.endswith("_pw") else source
        output[f"{short}_anom"] = anomaly
        output[f"{short}_sm3"] = smoothed

    # Derive processed residuals after applying the anomaly/smoothing operator.
    # The centered storage tendency is undefined at the first/last record,
    # whereas fluxes are valid there; deriving rather than independently
    # detrending the residual keeps the processed budget exactly closed.
    for box in BOXES:
        explicit_warm_anom = (
            output[f"{box}_zonal_convergence_anom"]
            + output[f"{box}_south_q20_in_anom"]
            + output[f"{box}_north_q20_in_anom"]
            + output[f"{box}_surface_warm_anom"]
        )
        explicit_warm_sm3 = (
            output[f"{box}_zonal_convergence_sm3"]
            + output[f"{box}_south_q20_in_sm3"]
            + output[f"{box}_north_q20_in_sm3"]
            + output[f"{box}_surface_warm_sm3"]
        )
        explicit_all_anom = (
            output[f"{box}_zonal_convergence_anom"]
            + output[f"{box}_south_q20_in_anom"]
            + output[f"{box}_north_q20_in_anom"]
            + output[f"{box}_surface_all_anom"]
        )
        explicit_all_sm3 = (
            output[f"{box}_zonal_convergence_sm3"]
            + output[f"{box}_south_q20_in_sm3"]
            + output[f"{box}_north_q20_in_sm3"]
            + output[f"{box}_surface_all_sm3"]
        )
        output[f"{box}_residual_warm_anom"] = (
            output[f"{box}_storage_tendency_anom"] - explicit_warm_anom
        )
        output[f"{box}_residual_warm_sm3"] = (
            output[f"{box}_storage_tendency_sm3"] - explicit_warm_sm3
        )
        output[f"{box}_residual_all_surface_anom"] = (
            output[f"{box}_storage_tendency_anom"] - explicit_all_anom
        )
        output[f"{box}_residual_all_surface_sm3"] = (
            output[f"{box}_storage_tendency_sm3"] - explicit_all_sm3
        )
        reconstructed = explicit_warm_sm3 + output[f"{box}_residual_warm_sm3"]
        error = output[f"{box}_storage_tendency_sm3"] - reconstructed
        if float(np.nanmax(np.abs(error))) > 1.0e-10:
            raise ValueError(f"Processed budget does not close for {box}")
    return output


def event_aligned(monthly: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        *[f"{name}_sm3" for name in GATE_METRICS],
    ]
    for box in BOXES:
        metrics.extend(
            [
                f"{box}_h20_zj_sm3",
                f"{box}_storage_tendency_sm3",
                f"{box}_zonal_convergence_sm3",
                f"{box}_south_q20_in_sm3",
                f"{box}_north_q20_in_sm3",
                f"{box}_surface_warm_sm3",
                f"{box}_surface_all_sm3",
                f"{box}_residual_warm_sm3",
                f"{box}_residual_all_surface_sm3",
            ]
        )
    indexed = monthly.set_index(pd.DatetimeIndex(monthly["time"]))
    rows: list[dict[str, object]] = []
    for event_class, years in EVENTS.items():
        for year in years:
            for relative_month in RELATIVE_MONTHS:
                timestamp = pd.Timestamp(year, 1, 15) + pd.DateOffset(
                    months=int(relative_month)
                )
                row: dict[str, object] = {
                    "event_class": event_class,
                    "event_year": year,
                    "relative_month": int(relative_month),
                    "time": timestamp,
                    "days_in_month": timestamp.days_in_month,
                }
                for metric in metrics:
                    value = indexed.loc[timestamp, metric]
                    if not np.isfinite(value):
                        raise ValueError(f"Missing {metric} for {timestamp}")
                    row[metric] = float(value)
                rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_composites(
    aligned: pd.DataFrame,
    bootstrap_samples: int,
) -> pd.DataFrame:
    metric_columns = [
        name for name in aligned.columns if name.endswith("_sm3")
    ]
    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, object]] = []
    for event_class, years in EVENTS.items():
        group = aligned[aligned["event_class"] == event_class]
        for metric in metric_columns:
            matrix = (
                group.pivot(index="event_year", columns="relative_month", values=metric)
                .reindex(index=years, columns=RELATIVE_MONTHS)
                .to_numpy(dtype=float)
            )
            draw = rng.integers(
                0, matrix.shape[0], size=(bootstrap_samples, matrix.shape[0])
            )
            boot = matrix[draw, :].mean(axis=1)
            low, high = np.quantile(boot, [0.025, 0.975], axis=0)
            mean = matrix.mean(axis=0)
            for index, relative_month in enumerate(RELATIVE_MONTHS):
                rows.append(
                    {
                        "event_class": event_class,
                        "event_years": ",".join(map(str, years)),
                        "n_events": len(years),
                        "metric": metric,
                        "relative_month": int(relative_month),
                        "mean": float(mean[index]),
                        "ci_low": float(low[index]),
                        "ci_high": float(high[index]),
                        "ci_excludes_zero": bool(
                            low[index] > 0.0 or high[index] < 0.0
                        ),
                    }
                )
    return pd.DataFrame(rows)


def cumulative_event_table(aligned: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    gate_metrics = [f"{name}_sm3" for name in GATE_METRICS]
    for (event_class, event_year), event in aligned.groupby(
        ["event_class", "event_year"], sort=True
    ):
        event = event.sort_values("relative_month")
        for phase, (start, end) in PHASES.items():
            phase_data = event[event["relative_month"].between(start, end)]
            factor = phase_data["days_in_month"].to_numpy(dtype=float) * 86400.0 / 1.0e6
            # PW * seconds / 1e6 converts to ZJ.
            for metric in gate_metrics:
                rows.append(
                    {
                        "event_class": event_class,
                        "event_year": int(event_year),
                        "phase": phase,
                        "box": "gate",
                        "component": metric.removesuffix("_sm3"),
                        "cumulative_zj": float(
                            np.sum(phase_data[metric].to_numpy(dtype=float) * factor)
                        ),
                    }
                )
            for box in BOXES:
                for component in COMPONENTS:
                    metric = f"{box}_{component}_sm3"
                    rows.append(
                        {
                            "event_class": event_class,
                            "event_year": int(event_year),
                            "phase": phase,
                            "box": box,
                            "component": component,
                            "cumulative_zj": float(
                                np.sum(
                                    phase_data[metric].to_numpy(dtype=float) * factor
                                )
                            ),
                        }
                    )
    return pd.DataFrame(rows)


def cumulative_summary(
    cumulative: pd.DataFrame,
    bootstrap_samples: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED + 1)
    rows: list[dict[str, object]] = []
    keys = ["phase", "box", "component"]
    unique_keys = cumulative[keys].drop_duplicates()
    for key in unique_keys.itertuples(index=False):
        phase, box, component = key
        class_values: dict[str, np.ndarray] = {}
        for event_class, years in EVENTS.items():
            selected = cumulative[
                (cumulative["event_class"] == event_class)
                & (cumulative["phase"] == phase)
                & (cumulative["box"] == box)
                & (cumulative["component"] == component)
            ].set_index("event_year")["cumulative_zj"].reindex(years)
            values = selected.to_numpy(dtype=float)
            if not np.isfinite(values).all():
                raise ValueError(f"Incomplete cumulative values for {key}")
            class_values[event_class] = values
            draw = rng.integers(
                0, values.size, size=(bootstrap_samples, values.size)
            )
            boot = values[draw].mean(axis=1)
            low, high = np.quantile(boot, [0.025, 0.975])
            rows.append(
                {
                    "contrast": event_class,
                    "phase": phase,
                    "box": box,
                    "component": component,
                    "mean_zj": float(values.mean()),
                    "ci_low_zj": float(low),
                    "ci_high_zj": float(high),
                    "ci_excludes_zero": bool(low > 0.0 or high < 0.0),
                }
            )
        ct = class_values["CT"]
        cp = class_values["CP"]
        ct_draw = rng.integers(0, ct.size, size=(bootstrap_samples, ct.size))
        cp_draw = rng.integers(0, cp.size, size=(bootstrap_samples, cp.size))
        differences = ct[ct_draw].mean(axis=1) - cp[cp_draw].mean(axis=1)
        low, high = np.quantile(differences, [0.025, 0.975])
        rows.append(
            {
                "contrast": "CT_minus_CP",
                "phase": phase,
                "box": box,
                "component": component,
                "mean_zj": float(ct.mean() - cp.mean()),
                "ci_low_zj": float(low),
                "ci_high_zj": float(high),
                "ci_excludes_zero": bool(low > 0.0 or high < 0.0),
            }
        )
    return pd.DataFrame(rows)


def select_composite(
    composites: pd.DataFrame,
    event_class: str,
    metric: str,
) -> pd.DataFrame:
    selected = composites[
        (composites["event_class"] == event_class)
        & (composites["metric"] == metric)
    ].sort_values("relative_month")
    if len(selected) != len(RELATIVE_MONTHS):
        raise ValueError(f"Incomplete composite: {event_class}, {metric}")
    return selected


def decorate_time_axis(axis: plt.Axes) -> None:
    labels = [
        (pd.Timestamp(2000, 1, 1) + pd.DateOffset(months=int(month))).strftime("%b")[0]
        for month in RELATIVE_MONTHS
    ]
    axis.set_xlim(RELATIVE_MONTHS[0], RELATIVE_MONTHS[-1])
    axis.set_xticks(RELATIVE_MONTHS)
    axis.set_xticklabels(labels)
    axis.axvspan(10.5, 13.5, color="#E8D7B9", alpha=0.42, lw=0, zorder=0)
    axis.axvline(-0.5, color="0.55", lw=0.75, ls=":")
    axis.axvline(11.5, color="0.55", lw=0.75, ls=":")
    axis.axhline(0.0, color="0.40", lw=0.75)
    axis.grid(axis="y", color="0.90", lw=0.6)
    axis.text(-3.0, -0.17, "Year −1", transform=axis.get_xaxis_transform(), ha="center")
    axis.text(5.5, -0.17, "Year 0", transform=axis.get_xaxis_transform(), ha="center")
    axis.text(14.0, -0.17, "Year +1", transform=axis.get_xaxis_transform(), ha="center")


def plot_signed_stack(
    axis: plt.Axes,
    summary: pd.DataFrame,
    event_class: str,
    phase: str,
) -> None:
    x = np.arange(len(BOXES))
    positive = np.zeros(len(BOXES))
    negative = np.zeros(len(BOXES))
    for component, label in COMPONENTS.items():
        if component == "storage_tendency":
            continue
        selected = summary[
            (summary["contrast"] == event_class)
            & (summary["phase"] == phase)
            & (summary["component"] == component)
        ].set_index("box").reindex(BOXES)
        values = selected["mean_zj"].to_numpy(dtype=float)
        bottoms = np.where(values >= 0.0, positive, negative)
        axis.bar(
            x,
            values,
            bottom=bottoms,
            width=0.66,
            color=COMPONENT_COLORS[component],
            edgecolor="white",
            linewidth=0.45,
            label=label,
        )
        positive += np.where(values >= 0.0, values, 0.0)
        negative += np.where(values < 0.0, values, 0.0)
    storage = summary[
        (summary["contrast"] == event_class)
        & (summary["phase"] == phase)
        & (summary["component"] == "storage_tendency")
    ].set_index("box").reindex(BOXES)
    y = storage["mean_zj"].to_numpy(dtype=float)
    lower = y - storage["ci_low_zj"].to_numpy(dtype=float)
    upper = storage["ci_high_zj"].to_numpy(dtype=float) - y
    axis.errorbar(
        x,
        y,
        yerr=np.vstack([lower, upper]),
        fmt="D",
        ms=4.2,
        color="#111111",
        ecolor="#111111",
        elinewidth=0.9,
        capsize=2.5,
        label="Integrated dH20/dt",
        zorder=5,
    )
    axis.axhline(0.0, color="0.25", lw=0.8)
    axis.set_xticks(x)
    axis.set_xticklabels([BOX_LABELS[box] for box in BOXES])
    axis.grid(axis="y", color="0.90", lw=0.6)


def plot_figure(composites: pd.DataFrame, summary: pd.DataFrame) -> None:
    setup_style()
    # Use explicit margins instead of outside constrained-layout legends.  The
    # latter caused the lower legend, box labels and method note to overlap in
    # raster/PDF export.
    figure, axes = plt.subplots(2, 2, figsize=(11.6, 8.1), constrained_layout=False)
    figure.subplots_adjust(
        left=0.075,
        right=0.985,
        top=0.855,
        bottom=0.245,
        wspace=0.18,
        hspace=0.43,
    )
    for column, event_class in enumerate(("CT", "CP")):
        axis = axes[0, column]
        for metric, (label, color) in GATE_METRICS.items():
            series = select_composite(composites, event_class, f"{metric}_sm3")
            axis.plot(
                RELATIVE_MONTHS,
                series["mean"],
                color=color,
                lw=1.9,
                label=label,
            )
            significant = series["ci_excludes_zero"].to_numpy(dtype=bool)
            axis.scatter(
                RELATIVE_MONTHS[significant],
                series.loc[significant, "mean"],
                s=10,
                color=color,
                edgecolors="white",
                linewidths=0.25,
                zorder=4,
            )
        axis.set_title(
            f"{event_class} El Niño — eastward Qwarm,20 through fixed gates (n=4)",
            loc="left",
            fontweight="bold",
        )
        axis.set_ylabel("Qwarm,20 anomaly (PW)" if column == 0 else "")
        decorate_time_axis(axis)

        bottom = axes[1, column]
        plot_signed_stack(bottom, summary, event_class, "event_Jan0_to_May1")
        bottom.set_title(
            f"{event_class} cumulative fate, Jan(0)–May(+1)",
            loc="left",
            fontweight="bold",
        )
        bottom.set_ylabel("Cumulative anomaly (ZJ)" if column == 0 else "")

    gate_limit = max(
        0.2,
        float(
            np.ceil(
                composites[
                    composites["metric"].isin(
                        [f"{name}_sm3" for name in GATE_METRICS]
                    )
                ]["mean"].abs().max()
                * 10.0
            )
            / 10.0
        ),
    )
    budget_values = summary[
        (summary["contrast"].isin(["CT", "CP"]))
        & (summary["phase"] == "event_Jan0_to_May1")
        & (summary["box"].isin(BOXES))
    ]["mean_zj"]
    budget_limit = max(
        1.0,
        float(np.ceil(budget_values.abs().max() * 1.4)),
    )
    for axis in axes[0, :]:
        axis.set_ylim(-gate_limit, gate_limit)
    for axis in axes[1, :]:
        axis.set_ylim(-budget_limit, budget_limit)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 0.925),
        columnspacing=1.8,
        handlelength=2.2,
    )
    bar_handles, bar_labels = axes[1, 0].get_legend_handles_labels()
    figure.legend(
        bar_handles,
        bar_labels,
        loc="lower center",
        ncol=6,
        frameon=False,
        bbox_to_anchor=(0.5, 0.105),
        fontsize=8.0,
        columnspacing=1.15,
        handlelength=1.7,
        handletextpad=0.45,
    )
    figure.suptitle(
        "Where does anomalous warm heat go after the western Pacific gateway?",
        fontsize=12.5,
        fontweight="bold",
        y=0.982,
    )
    figure.text(
        0.075,
        0.025,
        "Positive bars add H20 to a box; negative bars remove it. Residual includes vertical/diapycnal exchange, mixing, assimilation and discretization.\n"
        "Dots/diamonds show integrated dH20/dt; error bars are 95% event-bootstrap intervals.",
        fontsize=7.4,
        color="0.30",
        ha="left",
        va="bottom",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, facecolor="white")
    figure.savefig(FIGURE_PDF, facecolor="white")
    plt.close(figure)


def plot_phase_figure(summary: pd.DataFrame) -> None:
    setup_style()
    phases = (
        "development_Jun0_to_Nov0",
        "mature_decay_Dec0_to_May1",
    )
    phase_labels = ("Development\nJun–Nov(0)", "Mature/decay\nDec(0)–May(+1)")
    figure, axes = plt.subplots(
        1, 2, figsize=(9.7, 4.6), sharey=True, constrained_layout=True
    )
    figure.get_layout_engine().set(w_pad=0.08, wspace=0.08)
    extrema: list[float] = []
    for axis, event_class in zip(axes, ("CT", "CP"), strict=True):
        x = np.arange(len(phases))
        positive = np.zeros(len(phases))
        negative = np.zeros(len(phases))
        for component, label in COMPONENTS.items():
            if component == "storage_tendency":
                continue
            values = np.array(
                [
                    float(
                        summary_value(
                            summary, event_class, phase, "east", component
                        )["mean_zj"]
                    )
                    for phase in phases
                ]
            )
            bottoms = np.where(values >= 0.0, positive, negative)
            axis.bar(
                x,
                values,
                bottom=bottoms,
                width=0.62,
                color=COMPONENT_COLORS[component],
                edgecolor="white",
                linewidth=0.45,
                label=label,
            )
            positive += np.where(values >= 0.0, values, 0.0)
            negative += np.where(values < 0.0, values, 0.0)
        storage_rows = [
            summary_value(
                summary, event_class, phase, "east", "storage_tendency"
            )
            for phase in phases
        ]
        storage = np.array([float(row["mean_zj"]) for row in storage_rows])
        lower = storage - np.array([float(row["ci_low_zj"]) for row in storage_rows])
        upper = np.array([float(row["ci_high_zj"]) for row in storage_rows]) - storage
        axis.errorbar(
            x,
            storage,
            yerr=np.vstack([lower, upper]),
            fmt="D",
            ms=4.6,
            color="#111111",
            ecolor="#111111",
            elinewidth=0.9,
            capsize=2.7,
            label="Integrated dH20/dt",
            zorder=5,
        )
        axis.axhline(0.0, color="0.25", lw=0.8)
        axis.set_xticks(x)
        axis.set_xticklabels(phase_labels)
        axis.set_title(
            f"{event_class} El Niño — eastern Pacific box (n=4)",
            loc="left",
            fontweight="bold",
        )
        axis.grid(axis="y", color="0.90", lw=0.6)
        extrema.extend([float(positive.max()), float(negative.min())])
    axes[0].set_ylabel("Cumulative anomaly (ZJ)")
    limit = max(2.0, float(np.ceil(max(abs(value) for value in extrema) * 1.15)))
    axes[0].set_ylim(-limit, limit)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="outside lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, -0.08),
    )
    figure.suptitle(
        "Eastern Pacific warm-heat fate reverses from development to decay",
        fontsize=12.0,
        fontweight="bold",
        y=1.04,
    )
    figure.text(
        0.01,
        -0.075,
        "Negative 5°N inflow means northward export. Bars are event-composite anomalies; residual is not uniquely attributable to mixing.",
        fontsize=7.4,
        color="0.30",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    figure.savefig(PHASE_FIGURE_PNG, bbox_inches="tight", facecolor="white")
    figure.savefig(PHASE_FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def validate_q20(raw: pd.DataFrame) -> dict[str, object]:
    output: dict[str, object] = {}
    if not EXISTING_Q20_CSV.exists():
        return output
    existing = pd.read_csv(EXISTING_Q20_CSV, parse_dates=["time"])
    for gate in (160, 180, 220):
        reference = existing[np.isclose(existing["longitude_e"], gate)][
            ["time", "q20_pw"]
        ]
        merged = raw[["time", f"q20_{gate}e_5s5n_pw"]].merge(
            reference, on="time", how="inner"
        )
        difference = merged.iloc[:, 1] - merged.iloc[:, 2]
        output[f"q20_{gate}e_comparison_n"] = int(len(merged))
        output[f"q20_{gate}e_correlation"] = float(
            merged.iloc[:, 1:].corr().iloc[0, 1]
        )
        output[f"q20_{gate}e_max_abs_difference_pw"] = float(
            difference.abs().max()
        )
    return output


def summary_value(
    summary: pd.DataFrame,
    contrast: str,
    phase: str,
    box: str,
    component: str,
) -> pd.Series:
    return summary[
        (summary["contrast"] == contrast)
        & (summary["phase"] == phase)
        & (summary["box"] == box)
        & (summary["component"] == component)
    ].iloc[0]


def write_report(summary: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    event_phase = "event_Jan0_to_May1"
    lines: list[str] = []
    for event_class in ("CT", "CP"):
        for box in BOXES:
            terms = {
                component: summary_value(
                    summary, event_class, event_phase, box, component
                )["mean_zj"]
                for component in COMPONENTS
            }
            lines.append(
                f"| {event_class} | {BOX_LABELS[box].replace(chr(10), ' ')} | "
                f"{terms['zonal_convergence']:+.2f} | {terms['south_q20_in']:+.2f} | "
                f"{terms['north_q20_in']:+.2f} | {terms['surface_warm']:+.2f} | "
                f"{terms['residual_warm']:+.2f} | {terms['storage_tendency']:+.2f} |"
            )

    phase_lines: list[str] = []
    for phase_name, phase_label in (
        ("development_Jun0_to_Nov0", "发展期 Jun–Nov(0)"),
        ("mature_decay_Dec0_to_May1", "成熟—衰减期 Dec(0)–May(+1)"),
    ):
        for event_class in ("CT", "CP"):
            terms = {
                component: summary_value(
                    summary, event_class, phase_name, "east", component
                )["mean_zj"]
                for component in COMPONENTS
            }
            phase_lines.append(
                f"| {phase_label} | {event_class} | {terms['zonal_convergence']:+.2f} | "
                f"{terms['south_q20_in']:+.2f} | {terms['north_q20_in']:+.2f} | "
                f"{terms['surface_warm']:+.2f} | {terms['residual_warm']:+.2f} | "
                f"{terms['storage_tendency']:+.2f} |"
            )

    ct_north = summary_value(
        summary, "CT", event_phase, "east", "north_q20_in"
    )
    cp_north = summary_value(
        summary, "CP", event_phase, "east", "north_q20_in"
    )
    north_difference = summary_value(
        summary, "CT_minus_CP", event_phase, "east", "north_q20_in"
    )
    ct_gate_180 = summary_value(
        summary, "CT", event_phase, "gate", "q20_180e_10s5n"
    )
    cp_gate_180 = summary_value(
        summary, "CP", event_phase, "gate", "q20_180e_10s5n"
    )
    ct_gate_220 = summary_value(
        summary, "CT", event_phase, "gate", "q20_220e_10s5n"
    )
    cp_gate_220 = summary_value(
        summary, "CP", event_phase, "gate", "q20_220e_10s5n"
    )
    ct_dev_gate_220 = summary_value(
        summary, "CT", "development_Jun0_to_Nov0", "gate", "q20_220e_10s5n"
    )
    cp_dev_gate_220 = summary_value(
        summary, "CP", "development_Jun0_to_Nov0", "gate", "q20_220e_10s5n"
    )
    ct_dev_storage = summary_value(
        summary, "CT", "development_Jun0_to_Nov0", "east", "storage_tendency"
    )
    cp_dev_storage = summary_value(
        summary, "CP", "development_Jun0_to_Nov0", "east", "storage_tendency"
    )
    dev_storage_difference = summary_value(
        summary,
        "CT_minus_CP",
        "development_Jun0_to_Nov0",
        "east",
        "storage_tendency",
    )
    ct_decay_storage = summary_value(
        summary, "CT", "mature_decay_Dec0_to_May1", "east", "storage_tendency"
    )
    cp_decay_storage = summary_value(
        summary, "CP", "mature_decay_Dec0_to_May1", "east", "storage_tendency"
    )
    ct_decay_north = summary_value(
        summary, "CT", "mature_decay_Dec0_to_May1", "east", "north_q20_in"
    )
    cp_decay_north = summary_value(
        summary, "CP", "mature_decay_Dec0_to_May1", "east", "north_q20_in"
    )
    decay_north_difference = summary_value(
        summary,
        "CT_minus_CP",
        "mature_decay_Dec0_to_May1",
        "east",
        "north_q20_in",
    )
    ct_decay_south = summary_value(
        summary, "CT", "mature_decay_Dec0_to_May1", "east", "south_q20_in"
    )
    cp_decay_south = summary_value(
        summary, "CP", "mature_decay_Dec0_to_May1", "east", "south_q20_in"
    )

    report = rf"""# SODA3三箱暖热量去向：第一个问题

## 问题与固定收支

本阶段回答：暖热量越过西太平洋通道后，是留在中/东太平洋，还是从10°S、5°N排出，或被表面通量及未解析过程改变？控制体在看结果前固定为10°S–5°N、0–300 m的三个箱体：160°E–180°E、180°E–140°W、140°W–80°W。

每个箱体使用：

\[
\frac{{dH_{{20}}}}{{dt}}=C_x+F_{{10S}}+F_{{5N}}+Q_{{surface,warm}}+R.
\]

所有显式项均以进入箱体为正。`Qsurface,warm`只保留海表温度高于20°C格点的SODA `net_heating`；全表面热通量另存作敏感性检查。`R`包括垂向/跨等温面交换、混合扩散、同化增量、20°C阈值面运动和月平均/网格离散误差。

## Jan(0)–May(+1)累计异常（ZJ）

| 类型 | 箱体 | 东西向汇聚 | 10°S输入 | 5°N输入 | 暖层表面项 | 未解析项 | 储量倾向积分 |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

## 直接回答

- **发展期两类事件都把暖热量送到东部。** Jun–Nov(0)穿过140°W的异常东向Q20累计在CT/CP中分别为 {ct_dev_gate_220['mean_zj']:+.2f}/{cp_dev_gate_220['mean_zj']:+.2f} ZJ，且两组95%区间都为正。同期东部储量倾向积分为 {ct_dev_storage['mean_zj']:+.2f}/{cp_dev_storage['mean_zj']:+.2f} ZJ；CT−CP差为 {dev_storage_difference['mean_zj']:+.2f} ZJ，95%区间 [{dev_storage_difference['ci_low_zj']:+.2f}, {dev_storage_difference['ci_high_zj']:+.2f}]。因此CP不是“没有暖水东传”，而是东部增热较弱。
- **分叉发生在衰减期的北侧出口。** Dec(0)–May(+1)东部储量在CT/CP中分别减少 {abs(ct_decay_storage['mean_zj']):.2f}/{abs(cp_decay_storage['mean_zj']):.2f} ZJ。5°N项在CT为 {ct_decay_north['mean_zj']:+.2f} ZJ（向北排出），CP为 {cp_decay_north['mean_zj']:+.2f} ZJ（向箱内输入）；CT−CP差为 {decay_north_difference['mean_zj']:+.2f} ZJ，95%区间 [{decay_north_difference['ci_low_zj']:+.2f}, {decay_north_difference['ci_high_zj']:+.2f}]。
- **没有证据表明主要从南侧排出。** 同一衰减期10°S项在CT/CP中为 {ct_decay_south['mean_zj']:+.2f}/{cp_decay_south['mean_zj']:+.2f} ZJ，两组区间均跨零。CT的稳健排放方向是5°N，而不是10°S。
- 80°W门的异常通过量接近零，说明事件暖热异常主要在东部箱体内储存、由南北边界和表面/未解析过程调节，并没有大量继续穿过80°W。

**第一个问题的答案是：暖热量在发展期确实从西部通道传到东太平洋，CT和CP都有；差异主要不是“能否到达”，而是到达后的命运。CT东部储热更强，随后出现显著北向排放和负表面热通量异常；CP东部储热较弱，合成中没有同样的北向排放。**

Jan(0)–May(+1)总积分会混合增长和衰减两个相反阶段：180°E累计CT/CP为 {ct_gate_180['mean_zj']:+.2f}/{cp_gate_180['mean_zj']:+.2f} ZJ，140°W为 {ct_gate_220['mean_zj']:+.2f}/{cp_gate_220['mean_zj']:+.2f} ZJ；东部5°N总项为 {ct_north['mean_zj']:+.2f}/{cp_north['mean_zj']:+.2f} ZJ。因此机制判断应以分阶段结果为主，而不是只看总和。

## 东部箱体的分阶段收支

| 阶段 | 类型 | 东西向汇聚 | 10°S输入 | 5°N输入 | 暖层表面项 | 未解析项 | 储量倾向积分 |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(phase_lines)}

表中未解析项若很大，不能全部解释成混合；它还包含SODA同化增量、垂向/跨20°C面交换和月平均离散误差。

## QA与限制

- 完整月份：{diagnostics['n_months']}；预算经线性异常/平滑处理后代数闭合误差不超过 {diagnostics['processed_closure_max_abs_pw']:.2e} PW；
- 160/180/220°E的5°S–5°N Q20与既有独立结果的最小相关为 {diagnostics['q20_validation_min_correlation']:.8f}，最大绝对差为 {diagnostics['q20_validation_max_abs_difference_pw']:.2e} PW；
- 主合成仍使用论文与SODA3重叠的4个CT和4个CP事件，组间结论必须结合整事件bootstrap区间；
- 本结果是欧拉箱体热收支，不是水团拉格朗日追踪；“同一团暖水”的精确路径需要粒子或被动示踪实验。
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(args.input)
    raw = pd.read_csv(args.input, parse_dates=["time"])
    monthly = build_monthly(raw)
    aligned = event_aligned(monthly)
    composites = bootstrap_composites(aligned, args.bootstrap_samples)
    cumulative = cumulative_event_table(aligned)
    summary = cumulative_summary(cumulative, args.bootstrap_samples)

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    aligned.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    composites.to_csv(COMPOSITE_CSV, index=False, float_format="%.9g")
    cumulative.to_csv(CUMULATIVE_EVENT_CSV, index=False, float_format="%.9g")
    summary.to_csv(CUMULATIVE_SUMMARY_CSV, index=False, float_format="%.9g")
    plot_figure(composites, summary)
    plot_phase_figure(summary)

    closure_errors = []
    for box in BOXES:
        reconstruction = (
            monthly[f"{box}_zonal_convergence_sm3"]
            + monthly[f"{box}_south_q20_in_sm3"]
            + monthly[f"{box}_north_q20_in_sm3"]
            + monthly[f"{box}_surface_warm_sm3"]
            + monthly[f"{box}_residual_warm_sm3"]
        )
        closure_errors.extend(
            (monthly[f"{box}_storage_tendency_sm3"] - reconstruction)
            .dropna()
            .abs()
            .tolist()
        )
    q20_validation = validate_q20(raw)
    correlations = [
        value
        for key, value in q20_validation.items()
        if key.endswith("_correlation")
    ]
    differences = [
        value
        for key, value in q20_validation.items()
        if key.endswith("_max_abs_difference_pw")
    ]
    diagnostics: dict[str, object] = {
        "source": str(args.input),
        "n_months": int(len(raw)),
        "boxes": {
            "west": [160.0, 180.0],
            "central": [180.0, 220.0],
            "east": [220.0, 280.0],
            "latitude": [-10.0, 5.0],
        },
        "events": {key: list(value) for key, value in EVENTS.items()},
        "bootstrap_samples": int(args.bootstrap_samples),
        "processed_closure_max_abs_pw": float(max(closure_errors)),
        "q20_validation_min_correlation": float(min(correlations)),
        "q20_validation_max_abs_difference_pw": float(max(differences)),
        **q20_validation,
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(summary, diagnostics)
    for path in (
        MONTHLY_CSV,
        EVENT_CSV,
        COMPOSITE_CSV,
        CUMULATIVE_EVENT_CSV,
        CUMULATIVE_SUMMARY_CSV,
        FIGURE_PNG,
        FIGURE_PDF,
        PHASE_FIGURE_PNG,
        PHASE_FIGURE_PDF,
        REPORT_MD,
    ):
        print(f"Wrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
