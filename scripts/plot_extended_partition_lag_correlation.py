#!/usr/bin/env python3
"""Plot an extended lead-lag spectrum for H20 partition and wind response.

For each warm event, the source variable is the north-box H20 change from
January to March, April, or May.  The matching equator+north H20 change is
held fixed, so the source coefficient measures meridional partition rather
than total warm-heat amount.  The target is a rolling three-month mean of the
central-Pacific zonal wind-stress pattern residual.  Lag is the offset, in
months, between the source-window endpoint and the centre of the atmospheric
response window.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_partition_lag_mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp/codex_partition_lag_cache")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


DATA = ROOT / "data/derived/research_2026"
EVENT_FILE = DATA / "warm_heat_partition_coupling_event_table.csv"
ATM_FILE = DATA / "enso_full_year_coupling_monthly_1982_2024.csv"
OUT_DIR = ROOT / "outputs/research_2026/warm_heat_partition_coupling"
OUT_CSV = DATA / "warm_heat_partition_extended_lag_spectrum.csv"

EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
LAGS = tuple(range(-6, 13))
N_PERMUTATIONS = 50_000
RANDOM_SEED = 20260809

WINDOWS = (
    {
        "label_en": "Jan-Mar partition",
        "label_cn": "Jan-Mar配置",
        "end_month": 3,
        "north": "delta_h20_north_jan_mar_zj",
        "total": "delta_h20_total_jan_mar_zj",
        "color": "#2B83BA",
    },
    {
        "label_en": "Jan-Apr partition",
        "label_cn": "Jan-Apr配置",
        "end_month": 4,
        "north": "delta_h20_north_jan_apr_zj",
        "total": "delta_h20_total_jan_apr_zj",
        "color": "#D95F02",
    },
    {
        "label_en": "Jan-May partition",
        "label_cn": "Jan-May配置",
        "end_month": 5,
        "north": "delta_h20_north_jan_may_zj",
        "total": "delta_h20_total_jan_may_zj",
        "color": "#1B9E77",
    },
)


def shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    serial = year * 12 + (month - 1) + offset
    return serial // 12, serial % 12 + 1


def residualize(values: np.ndarray, controls: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    controls = np.asarray(controls, dtype=float)
    if controls.ndim == 1:
        controls = controls[:, None]
    design = np.column_stack([np.ones(len(values)), controls])
    return values - design @ np.linalg.lstsq(design, values, rcond=None)[0]


def partial_correlation(
    x: np.ndarray,
    y: np.ndarray,
    control: np.ndarray,
    rng: np.random.Generator,
) -> tuple[float, float]:
    xr = residualize(x, control)
    yr = residualize(y, control)
    r = float(np.corrcoef(xr, yr)[0, 1])

    # Two-sided event permutation test.  Work in batches to keep memory small.
    xr0 = xr - xr.mean()
    yr0 = yr - yr.mean()
    denominator = np.sqrt(np.sum(xr0**2) * np.sum(yr0**2))
    exceed = 0
    remaining = N_PERMUTATIONS
    while remaining:
        batch = min(5_000, remaining)
        permutations = np.vstack([rng.permutation(len(yr0)) for _ in range(batch)])
        current = (yr0[permutations] @ xr0) / denominator
        exceed += int(np.count_nonzero(np.abs(current) >= abs(r)))
        remaining -= batch
    permutation_p = (exceed + 1.0) / (N_PERMUTATIONS + 1.0)
    return r, float(permutation_p)


def bh_fdr(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.clip(adjusted, 0.0, 1.0)
    return output


def response_value(
    lookup: dict[tuple[int, int], float],
    event_year: int,
    endpoint_month: int,
    lag: int,
) -> float:
    center_year, center_month = shift_month(event_year, endpoint_month, lag)
    values: list[float] = []
    for relative_month in (-1, 0, 1):
        year, month = shift_month(center_year, center_month, relative_month)
        values.append(lookup.get((year, month), np.nan))
    return float(np.mean(values)) if np.all(np.isfinite(values)) else np.nan


def build_spectrum() -> pd.DataFrame:
    events = pd.read_csv(EVENT_FILE).set_index("year")
    atmosphere = pd.read_csv(ATM_FILE)
    lookup = {
        (int(row.year), int(row.month)): float(row.tau_pattern_residual_z)
        for row in atmosphere.itertuples(index=False)
    }

    # A common sample is used at every lag.  The 1982 event is omitted because
    # the atmospheric residual file begins in Jan 1982 and cannot support the
    # negative-lag windows.  Keeping N fixed prevents sample changes from
    # masquerading as temporal evolution.
    candidate_years = [year for year in EVENT_YEARS if year != 1982]
    valid_years = []
    for year in candidate_years:
        complete = True
        for window in WINDOWS:
            for lag in LAGS:
                current = response_value(lookup, year, int(window["end_month"]), lag)
                if not np.isfinite(current):
                    complete = False
        if complete:
            valid_years.append(year)
    if len(valid_years) != 12:
        raise ValueError(f"Expected a 12-event common sample, got {valid_years}")

    rows: list[dict[str, float | int | str]] = []
    for window_index, window in enumerate(WINDOWS):
        x = events.loc[valid_years, str(window["north"])].to_numpy(dtype=float)
        control = events.loc[valid_years, str(window["total"])].to_numpy(dtype=float)
        for lag in LAGS:
            y = np.array(
                [
                    response_value(lookup, year, int(window["end_month"]), lag)
                    for year in valid_years
                ],
                dtype=float,
            )
            rng = np.random.default_rng(RANDOM_SEED + window_index * 100 + lag + 20)
            r, permutation_p = partial_correlation(x, y, control, rng)
            center_example = shift_month(2000, int(window["end_month"]), lag)[1]
            month_names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
            centered_window = []
            for offset in (-1, 0, 1):
                _, month = shift_month(2000, center_example, offset)
                centered_window.append(month_names[month - 1])
            rows.append(
                {
                    "partition_window_en": window["label_en"],
                    "partition_window_cn": window["label_cn"],
                    "partition_end_month": window["end_month"],
                    "lag_months": lag,
                    "response_window": "-".join(centered_window),
                    "n_events": len(valid_years),
                    "partial_r": r,
                    "permutation_p": permutation_p,
                }
            )
    result = pd.DataFrame(rows)
    result["fdr_q_all"] = bh_fdr(result["permutation_p"].to_numpy())
    result["fdr_q_within_partition"] = np.nan
    for name, indices in result.groupby("partition_window_en").groups.items():
        result.loc[indices, "fdr_q_within_partition"] = bh_fdr(
            result.loc[indices, "permutation_p"].to_numpy()
        )
    return result


def apply_style() -> None:
    cjk_font = Path("/Library/Fonts/Arial Unicode.ttf")
    if not cjk_font.exists():
        cjk_font = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    if cjk_font.exists():
        font_manager.fontManager.addfont(cjk_font)
        primary_font = font_manager.FontProperties(fname=cjk_font).get_name()
    else:
        primary_font = "DejaVu Sans"
    preferred_fonts = [primary_font, "Arial", "Helvetica", "DejaVu Sans"]
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": preferred_fonts,
            "axes.unicode_minus": False,
            "figure.dpi": 160,
            "savefig.dpi": 300,
            "font.size": 15,
            "axes.titlesize": 23,
            "axes.labelsize": 17,
            "xtick.labelsize": 13,
            "ytick.labelsize": 13,
            "legend.fontsize": 14,
            "axes.linewidth": 1.2,
            "lines.linewidth": 2.6,
        }
    )


def plot_spectrum(data: pd.DataFrame, language: str) -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(14.2, 7.4))

    # Lag +2 is the first fully non-overlapping three-month response window:
    # Jan-Mar -> AMJ, Jan-Apr -> MJJ, and Jan-May -> JJA.
    ax.axvspan(LAGS[0] - 0.5, 1.5, color="#EEF1F4", zorder=0)
    ax.axvspan(1.5, LAGS[-1] + 0.5, color="#F3FAF6", zorder=0)
    ax.axhline(0.0, color="#34495E", linewidth=1.2, zorder=1)
    ax.axvline(2.0, color="#8A5A00", linewidth=1.5, linestyle="--", zorder=1)

    for window in WINDOWS:
        label_column = "partition_window_cn" if language == "cn" else "partition_window_en"
        label = str(window["label_cn"] if language == "cn" else window["label_en"])
        subset = data.loc[data[label_column].eq(label)].sort_values("lag_months")
        x = subset["lag_months"].to_numpy(dtype=float)
        y = subset["partial_r"].to_numpy(dtype=float)
        color = str(window["color"])
        ax.plot(x, y, color=color, marker="o", markersize=6.5, label=label, zorder=3)

        significant = subset["permutation_p"].to_numpy(dtype=float) < 0.05
        ax.scatter(
            x[significant],
            y[significant],
            s=105,
            facecolor=color,
            edgecolor="white",
            linewidth=1.4,
            zorder=5,
        )
        ax.scatter(
            x[~significant],
            y[~significant],
            s=70,
            facecolor="white",
            edgecolor=color,
            linewidth=1.7,
            zorder=4,
        )

    ax.set_xlim(LAGS[0] - 0.35, LAGS[-1] + 0.35)
    ax.set_ylim(-1.0, 1.0)
    ax.set_xticks(LAGS)
    ax.set_yticks(np.arange(-1.0, 1.01, 0.2))
    ax.grid(axis="y", color="#CFD8E3", linewidth=0.8, alpha=0.8)
    ax.spines[["top", "right"]].set_visible(False)

    if language == "cn":
        title = "春季暖量配置与后续风应力：扩展滞后相关谱"
        subtitle = "三个月滑动风应力窗口；控制同期赤道+北侧总暖量（12个共同暖事件）"
        xlabel = "相对暖量配置终点的滞后（月）"
        ylabel = "暖量偏北分配与风应力响应的偏相关 r"
        left_zone = "大气领先或窗口重叠"
        right_zone = "完全滞后于暖量配置"
        significance = "实心点：置换检验 p < 0.05"
    else:
        title = "Spring warm-heat partition and wind-stress response: extended lag spectrum"
        subtitle = "Three-month rolling wind-stress windows; equator+north total H20 held fixed (12 common warm events)"
        xlabel = "Lag from the endpoint of the H20-partition window (months)"
        ylabel = "Partial correlation with wind-stress response, r"
        left_zone = "Atmosphere leads or windows overlap"
        right_zone = "Response fully follows partition"
        significance = "Filled markers: permutation p < 0.05"

    ax.set_title(title, weight="bold", color="#102A43", pad=30)
    ax.text(0.5, 1.025, subtitle, transform=ax.transAxes, ha="center", va="bottom", color="#334E68", fontsize=14)
    ax.set_xlabel(xlabel, weight="bold", color="#243B53", labelpad=12)
    ax.set_ylabel(ylabel, weight="bold", color="#243B53", labelpad=12)
    ax.text(-2.2, 0.88, left_zone, ha="center", va="center", color="#607080", fontsize=13, weight="bold")
    ax.text(7.0, 0.88, right_zone, ha="center", va="center", color="#287A54", fontsize=13, weight="bold")
    ax.text(0.02, 0.035, significance, transform=ax.transAxes, ha="left", va="bottom", color="#334E68", fontsize=13)

    legend = ax.legend(loc="lower right", frameon=True, ncol=1)
    legend.get_frame().set_facecolor("white")
    legend.get_frame().set_edgecolor("#AAB7C4")
    legend.get_frame().set_alpha(0.96)

    fig.subplots_adjust(left=0.105, right=0.985, top=0.84, bottom=0.15)
    suffix = "cn" if language == "cn" else "en"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"extended_partition_lag_correlation_{suffix}.png", dpi=300, facecolor="white")
    fig.savefig(OUT_DIR / f"extended_partition_lag_correlation_{suffix}.pdf", facecolor="white")
    plt.close(fig)


def main() -> None:
    spectrum = build_spectrum()
    spectrum.to_csv(OUT_CSV, index=False, float_format="%.9g")
    plot_spectrum(spectrum, "cn")
    plot_spectrum(spectrum, "en")
    print(f"Saved {OUT_CSV}")
    print(f"Saved figures under {OUT_DIR}")


if __name__ == "__main__":
    main()
