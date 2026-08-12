#!/usr/bin/env python3
"""Compare the development-year air-sea coupling of 2015 and 2023.

ERA5 surface fluxes are stored with downward-positive signs.  Every public
diagnostic from this module converts them to ocean-to-atmosphere heat loss,
positive upward.  OISST, ERA5, and GPCP anomalies use calendar-month linear
expectations fitted over 1982-2014.  CPC OLR retains its published anomaly.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
BASELINE = (1982, 2014)
EVENT_YEARS = (2015, 2023)
SEASON_MONTHS = {
    "MAM": (3, 4, 5),
    "MJJ": (5, 6, 7),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
}
ARRIVAL_VALUES = {
    2015: {"transport_140w_zj": 8.49, "east_ohc_gain_zj": 8.60},
    2023: {"transport_140w_zj": 9.90, "east_ohc_gain_zj": 11.12},
}
ERA5_DIR = Path("data/raw/era5/coupling_monthly_1deg")
ATMOSPHERE_TABLE = Path(
    "data/derived/research_2026/enso_full_year_coupling_monthly_1982_2024.csv"
)
OLR_TABLE = Path("data/interim/raw_validation/olr_monthly.csv")
DERIVED_DIR = Path("data/derived/research_2026")
MONTHLY_CSV_NAME = "enso_2015_2023_coupling_exchange_monthly.csv"
SEASONAL_CSV_NAME = "enso_2015_2023_coupling_exchange_seasonal.csv"
AUDIT_JSON_NAME = "enso_2015_2023_coupling_exchange_audit.json"
FIGURE_DIR = Path("outputs/research_2026/enso_2015_2023_coupling_exchange")
FIGURE_STEM = "enso_2015_2023_coupling_exchange"
REPORT_NAME = "ENSO_2015_2023_COUPLING_EXCHANGE_CN.md"
EVENT_COLORS = {2015: "#D97706", 2023: "#0F8F83"}

MONTHLY_OUTPUT_COLUMNS = (
    "date",
    "year",
    "month",
    "sst_east_raw_c",
    "sst_east_anom_c",
    "latent_loss_anom_wm2",
    "sensible_loss_anom_wm2",
    "turbulent_loss_anom_wm2",
    "shortwave_loss_anom_wm2",
    "longwave_loss_anom_wm2",
    "net_ocean_loss_anom_wm2",
    "minus_olr_ep_wm2",
    "minus_olr_cp_wm2",
    "precip_east_anom_mmday",
    "precip_central_anom_mmday",
    "tau_cwp_anom_nm2",
)
SEASONAL_METRICS = tuple(column for column in MONTHLY_OUTPUT_COLUMNS if column not in {"date", "year", "month"})


@dataclass(frozen=True)
class PipelineOutputs:
    monthly_csv: Path
    seasonal_csv: Path
    audit_json: Path
    png: Path
    pdf: Path
    report: Path


def same_month_linear_anomaly(
    frame: pd.DataFrame,
    value_column: str,
    baseline: tuple[int, int] = BASELINE,
) -> pd.Series:
    """Remove a calendar-month linear expectation while preserving row order."""

    required = {"year", "month", value_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns for anomaly calculation: {sorted(missing)}")

    output = pd.Series(np.nan, index=frame.index, dtype=float, name=f"{value_column}_anom")
    for month, group in frame.groupby("month", sort=False):
        baseline_rows = group.loc[group.year.between(*baseline), ["year", value_column]].dropna()
        if len(baseline_rows) < 3:
            raise ValueError(f"Month {month} has fewer than three baseline values")
        slope, intercept = np.polyfit(
            baseline_rows.year.to_numpy(dtype=float),
            baseline_rows[value_column].to_numpy(dtype=float),
            1,
        )
        expected = intercept + slope * group.year.to_numpy(dtype=float)
        output.loc[group.index] = group[value_column].to_numpy(dtype=float) - expected
    return output


def weighted_box_mean(
    field: xr.DataArray,
    lat0: float,
    lat1: float,
    lon0: float,
    lon1: float,
) -> xr.DataArray:
    """Return a cosine-latitude-weighted mean from a 0-360 longitude field."""

    rename = {}
    if "latitude" in field.coords:
        rename["latitude"] = "lat"
    if "longitude" in field.coords:
        rename["longitude"] = "lon"
    normalized = field.rename(rename)
    if "lat" not in normalized.coords or "lon" not in normalized.coords:
        raise ValueError("Field requires latitude and longitude coordinates")
    normalized = normalized.assign_coords(lon=normalized.lon % 360.0).sortby("lon").sortby("lat")
    selected = normalized.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if selected.sizes.get("lat", 0) == 0 or selected.sizes.get("lon", 0) == 0:
        raise ValueError(f"Empty box lat={lat0}:{lat1}, lon={lon0}:{lon1}")
    weights = np.cos(np.deg2rad(selected.lat))
    return selected.weighted(weights).mean(("lat", "lon"), skipna=True)


def to_upward_loss(
    latent_down: np.ndarray,
    sensible_down: np.ndarray,
    shortwave_down: np.ndarray,
    longwave_down: np.ndarray,
) -> dict[str, np.ndarray]:
    """Convert ERA5 downward-positive fluxes to positive ocean heat loss."""

    latent = np.asarray(latent_down, dtype=float)
    sensible = np.asarray(sensible_down, dtype=float)
    shortwave = np.asarray(shortwave_down, dtype=float)
    longwave = np.asarray(longwave_down, dtype=float)
    latent_loss = -latent
    sensible_loss = -sensible
    return {
        "latent_loss": latent_loss,
        "sensible_loss": sensible_loss,
        "turbulent_loss": latent_loss + sensible_loss,
        "shortwave_loss": -shortwave,
        "longwave_loss": -longwave,
        "net_ocean_loss": -(shortwave + longwave + latent + sensible),
    }


def audited_arrival_table() -> pd.DataFrame:
    """Return current-PPT arrival values from the mass-closed OHC analysis."""

    return pd.DataFrame(
        [
            {"year": year, **ARRIVAL_VALUES[year]}
            for year in EVENT_YEARS
        ]
    )


def discover_input_root() -> Path:
    """Find the data-bearing project root when execution occurs in a worktree."""

    candidates = []
    if os.environ.get("MARYLAND_INPUT_ROOT"):
        candidates.append(Path(os.environ["MARYLAND_INPUT_ROOT"]).expanduser())
    candidates.append(ROOT)
    if ROOT.parent.name == ".worktrees":
        candidates.append(ROOT.parents[1])
    for candidate in candidates:
        if (candidate / ERA5_DIR).exists() and (candidate / ATMOSPHERE_TABLE).exists():
            return candidate.resolve()
    rendered = ", ".join(str(item) for item in candidates)
    raise FileNotFoundError(f"Could not locate required local inputs under: {rendered}")


def _load_era5_indices(input_root: Path) -> pd.DataFrame:
    rows = []
    variable_names = [
        "avg_iews",
        "avg_snswrf",
        "avg_snlwrf",
        "avg_slhtf",
        "avg_ishf",
    ]
    for month in range(1, 13):
        pieces = []
        for part in ("part01", "part02"):
            path = (
                input_root
                / ERA5_DIR
                / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            )
            with xr.open_dataset(path, engine="netcdf4", chunks=None) as dataset:
                selected = dataset[variable_names].rename(
                    {"valid_time": "time", "latitude": "lat", "longitude": "lon"}
                )
                selected = selected.assign_coords(lon=selected.lon % 360.0).sortby("lon").sortby("lat")
                pieces.append(selected.load())
        fields = xr.concat(pieces, dim="lon").sortby("lon")
        _, unique = np.unique(fields.lon.values, return_index=True)
        fields = fields.isel(lon=np.sort(unique))
        times = pd.DatetimeIndex(pd.to_datetime(fields.time.values))

        latent = weighted_box_mean(fields.avg_slhtf, -10.0, 5.0, 220.0, 280.0).values
        sensible = weighted_box_mean(fields.avg_ishf, -10.0, 5.0, 220.0, 280.0).values
        shortwave = weighted_box_mean(fields.avg_snswrf, -10.0, 5.0, 220.0, 280.0).values
        longwave = weighted_box_mean(fields.avg_snlwrf, -10.0, 5.0, 220.0, 280.0).values
        losses = to_upward_loss(latent, sensible, shortwave, longwave)
        tau = weighted_box_mean(fields.avg_iews, -5.0, 5.0, 160.0, 220.0).values
        current = pd.DataFrame(
            {
                "year": times.year,
                "month": times.month,
                "latent_loss_raw_wm2": losses["latent_loss"],
                "sensible_loss_raw_wm2": losses["sensible_loss"],
                "turbulent_loss_raw_wm2": losses["turbulent_loss"],
                "shortwave_loss_raw_wm2": losses["shortwave_loss"],
                "longwave_loss_raw_wm2": losses["longwave_loss"],
                "net_ocean_loss_raw_wm2": losses["net_ocean_loss"],
                "tau_cwp_raw_nm2": tau,
            }
        )
        rows.append(current)
    output = pd.concat(rows, ignore_index=True).sort_values(["year", "month"]).reset_index(drop=True)
    if output.duplicated(["year", "month"]).any():
        raise ValueError("ERA5 index table contains duplicate months")
    return output


def _load_sst_precip_indices(input_root: Path) -> pd.DataFrame:
    path = input_root / ATMOSPHERE_TABLE
    source = pd.read_csv(path)
    columns = [
        "year",
        "month",
        "sst_east_raw_c",
        "precip_east_raw_mmday",
        "precip_central_raw_mmday",
    ]
    output = source[columns].copy()
    if output.duplicated(["year", "month"]).any():
        raise ValueError("OISST/GPCP source table contains duplicate months")
    return output


def _load_olr_indices(input_root: Path) -> pd.DataFrame:
    source = pd.read_csv(input_root / OLR_TABLE)
    regions = {
        "eastern_pacific_140w_100w": "olr_ep_native_anom_wm2",
        "central_pacific_180_140w": "olr_cp_native_anom_wm2",
    }
    pieces = []
    for region, name in regions.items():
        selected = source.loc[source.region.eq(region), ["year", "month", "olr_anomaly"]].copy()
        selected = selected.rename(columns={"olr_anomaly": name})
        pieces.append(selected)
    return pieces[0].merge(pieces[1], on=["year", "month"], validate="one_to_one")


def build_monthly_table(input_root: Path | None = None) -> pd.DataFrame:
    """Build monthly 2015/2023 diagnostics from complete historical inputs."""

    data_root = discover_input_root() if input_root is None else Path(input_root)
    full = _load_era5_indices(data_root)
    full = full.merge(_load_sst_precip_indices(data_root), on=["year", "month"], validate="one_to_one")
    full = full.merge(_load_olr_indices(data_root), on=["year", "month"], how="left", validate="one_to_one")

    anomaly_columns = {
        "sst_east_raw_c": "sst_east_anom_c",
        "precip_east_raw_mmday": "precip_east_anom_mmday",
        "precip_central_raw_mmday": "precip_central_anom_mmday",
        "latent_loss_raw_wm2": "latent_loss_anom_wm2",
        "sensible_loss_raw_wm2": "sensible_loss_anom_wm2",
        "turbulent_loss_raw_wm2": "turbulent_loss_anom_wm2",
        "shortwave_loss_raw_wm2": "shortwave_loss_anom_wm2",
        "longwave_loss_raw_wm2": "longwave_loss_anom_wm2",
        "net_ocean_loss_raw_wm2": "net_ocean_loss_anom_wm2",
        "tau_cwp_raw_nm2": "tau_cwp_anom_nm2",
    }
    for raw_name, anomaly_name in anomaly_columns.items():
        full[anomaly_name] = same_month_linear_anomaly(full, raw_name)
    full["minus_olr_ep_wm2"] = -full.olr_ep_native_anom_wm2
    full["minus_olr_cp_wm2"] = -full.olr_cp_native_anom_wm2
    full["date"] = pd.to_datetime(dict(year=full.year, month=full.month, day=1))

    events = full.loc[full.year.isin(EVENT_YEARS), MONTHLY_OUTPUT_COLUMNS].copy()
    events = events.sort_values(["year", "month"]).reset_index(drop=True)
    counts = events.groupby("year")["month"].nunique().to_dict()
    if counts != {2015: 12, 2023: 12}:
        raise ValueError(f"Incomplete event-month table: {counts}")
    return events


def build_seasonal_table(monthly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate overlapping development-season windows in physical units."""

    rows = []
    for season, months in SEASON_MONTHS.items():
        event_rows = []
        for year in EVENT_YEARS:
            selected = monthly.loc[monthly.year.eq(year) & monthly.month.isin(months)]
            if tuple(selected.month) != months:
                raise ValueError(f"{year} {season} has months {tuple(selected.month)}, expected {months}")
            row = {"season": season, "event": str(year), "year": year}
            row.update({metric: float(selected[metric].mean()) for metric in SEASONAL_METRICS})
            event_rows.append(row)
            rows.append(row)
        difference = {"season": season, "event": "2015_minus_2023", "year": np.nan}
        difference.update(
            {
                metric: event_rows[0][metric] - event_rows[1][metric]
                for metric in SEASONAL_METRICS
            }
        )
        rows.append(difference)
    return pd.DataFrame(rows)


def validate_monthly_table(monthly: pd.DataFrame, seasonal: pd.DataFrame) -> dict[str, object]:
    target = [column for column in MONTHLY_OUTPUT_COLUMNS if column not in {"date", "year", "month"}]
    mjj = seasonal.loc[
        seasonal.season.eq("MJJ") & seasonal.event.isin(["2015", "2023"])
    ].set_index("event")
    return {
        "baseline": "1982-2014 calendar-month linear expectation; CPC OLR native anomaly",
        "flux_sign": "positive means ocean-to-atmosphere heat loss",
        "month_counts": {
            str(year): int(count)
            for year, count in monthly.groupby("year")["month"].nunique().items()
        },
        "missing_target_values": int(monthly[target].isna().sum().sum()),
        "arrival_values": audited_arrival_table().to_dict(orient="records"),
        "mjj_key_values": {
            event: {
                metric: float(mjj.loc[event, metric])
                for metric in (
                    "sst_east_raw_c",
                    "sst_east_anom_c",
                    "latent_loss_anom_wm2",
                    "net_ocean_loss_anom_wm2",
                    "minus_olr_cp_wm2",
                    "precip_central_anom_mmday",
                    "tau_cwp_anom_nm2",
                )
            }
            for event in ("2015", "2023")
        },
    }


def write_tables(output_root: Path | None = None, input_root: Path | None = None) -> tuple[Path, Path, Path]:
    root = ROOT if output_root is None else Path(output_root)
    monthly = build_monthly_table(input_root=input_root)
    seasonal = build_seasonal_table(monthly)
    audit = validate_monthly_table(monthly, seasonal)
    target_dir = root / DERIVED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    monthly_path = target_dir / MONTHLY_CSV_NAME
    seasonal_path = target_dir / SEASONAL_CSV_NAME
    audit_path = target_dir / AUDIT_JSON_NAME
    monthly.to_csv(monthly_path, index=False, float_format="%.8g")
    seasonal.to_csv(seasonal_path, index=False, float_format="%.8g")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return monthly_path, seasonal_path, audit_path


def _style_axis(axis: plt.Axes, panel: str, *, zero_line: bool = True) -> None:
    axis.text(
        0.01,
        0.98,
        f"({panel})",
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        fontweight="bold",
    )
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#D8E0E6", linewidth=0.7, alpha=0.75)
    axis.tick_params(labelsize=9, length=3.5, width=0.8)
    if zero_line:
        axis.axhline(0.0, color="#52616B", linewidth=0.8, zorder=0)


def _plot_monthly_pair(
    axis: plt.Axes,
    monthly: pd.DataFrame,
    column: str,
    ylabel: str,
    panel: str,
    *,
    zero_line: bool = True,
    legend: bool = False,
) -> None:
    axis.axvspan(4.5, 7.5, color="#DCE9F2", alpha=0.55, linewidth=0, zorder=0)
    for year in EVENT_YEARS:
        selected = monthly.loc[monthly.year.eq(year)].sort_values("month")
        axis.plot(
            selected.month,
            selected[column],
            color=EVENT_COLORS[year],
            marker="o",
            markersize=4.2,
            markeredgecolor="white",
            markeredgewidth=0.6,
            linewidth=2.15,
            label=str(year),
            zorder=3,
        )
    axis.set_xlim(0.7, 12.3)
    axis.set_xticks(range(1, 13))
    axis.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    axis.set_ylabel(ylabel, fontsize=10)
    _style_axis(axis, panel, zero_line=zero_line)
    if legend:
        axis.legend(
            loc="best",
            frameon=False,
            fontsize=9,
            handlelength=2.0,
            ncol=2,
            columnspacing=1.2,
        )


def make_figure(monthly: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Render the paired evidence chain without a figure-level title."""

    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.edgecolor": "#263746",
            "axes.labelcolor": "#102A3A",
            "xtick.color": "#263746",
            "ytick.color": "#263746",
            "text.color": "#102A3A",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    figure, axes = plt.subplots(3, 3, figsize=(15.2, 10.8), constrained_layout=True)
    axes = axes.ravel()

    arrival = audited_arrival_table().set_index("year")
    x = np.arange(2)
    width = 0.34
    for index, year in enumerate(EVENT_YEARS):
        values = [arrival.loc[year, "transport_140w_zj"], arrival.loc[year, "east_ohc_gain_zj"]]
        bars = axes[0].bar(
            x + (index - 0.5) * width,
            values,
            width=width,
            color=EVENT_COLORS[year],
            edgecolor="white",
            linewidth=0.7,
            label=str(year),
            zorder=3,
        )
        axes[0].bar_label(bars, fmt="%.2f", padding=3, fontsize=8.5, color="#263746")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["140°W input", "East-box OHC gain"])
    axes[0].set_ylabel("Jan–Jun heat content (ZJ)", fontsize=10)
    axes[0].set_ylim(0, 12.8)
    axes[0].legend(frameon=False, fontsize=9, ncol=2, loc="upper left", bbox_to_anchor=(0.12, 1.0))
    _style_axis(axes[0], "a", zero_line=False)

    specifications = [
        ("sst_east_raw_c", "Eastern SST (°C)", "b", False, True),
        ("sst_east_anom_c", "Eastern SST anomaly (°C)", "c", True, False),
        ("latent_loss_anom_wm2", "Upward latent heat flux\nanomaly (W m⁻²)", "d", True, False),
        ("sensible_loss_anom_wm2", "Upward sensible heat flux\nanomaly (W m⁻²)", "e", True, False),
        ("net_ocean_loss_anom_wm2", "Net ocean heat-loss\nanomaly (W m⁻²)", "f", True, False),
        ("minus_olr_cp_wm2", "Central −OLR (W m⁻²)", "g", True, False),
        ("precip_central_anom_mmday", "Central precipitation\nanomaly (mm day⁻¹)", "h", True, False),
        ("tau_cwp_anom_nm2", "Central-western eastward stress\nanomaly (N m⁻²)", "i", True, False),
    ]
    for axis, (column, ylabel, panel, zero_line, legend) in zip(axes[1:], specifications):
        _plot_monthly_pair(
            axis,
            monthly,
            column,
            ylabel,
            panel,
            zero_line=zero_line,
            legend=legend,
        )

    png_path = output_dir / f"{FIGURE_STEM}.png"
    pdf_path = output_dir / f"{FIGURE_STEM}.pdf"
    figure.savefig(png_path, dpi=340, bbox_inches="tight", facecolor="white")
    figure.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return png_path, pdf_path


def _seasonal_markdown_table(seasonal: pd.DataFrame) -> str:
    columns = [
        ("sst_east_raw_c", "SST (°C)"),
        ("sst_east_anom_c", "SST′ (°C)"),
        ("latent_loss_anom_wm2", "潜热损失′ (W m⁻²)"),
        ("net_ocean_loss_anom_wm2", "净散热′ (W m⁻²)"),
        ("minus_olr_cp_wm2", "−OLR (W m⁻²)"),
        ("precip_central_anom_mmday", "降水′ (mm d⁻¹)"),
        ("tau_cwp_anom_nm2", "东向应力′ (N m⁻²)"),
    ]
    lines = [
        "| 季节 | 事件 | " + " | ".join(label for _, label in columns) + " |",
        "|---|---:" + "|---:" * len(columns) + "|",
    ]
    selected = seasonal.loc[seasonal.event.isin(["2015", "2023"])]
    for row in selected.itertuples(index=False):
        values = []
        for key, _ in columns:
            value = float(getattr(row, key))
            digits = 3 if key == "tau_cwp_anom_nm2" else 2
            values.append(f"{value:.{digits}f}")
        lines.append(f"| {row.season} | {row.event} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(monthly: pd.DataFrame, seasonal: pd.DataFrame, output_dir: Path) -> Path:
    """Write a concise Chinese interpretation anchored to audited values."""

    output_dir.mkdir(parents=True, exist_ok=True)
    mjj = seasonal.loc[
        seasonal.season.eq("MJJ") & seasonal.event.isin(["2015", "2023"])
    ].set_index("event")
    report = f"""# 2015与2023年厄尔尼诺发展期海气耦合对比

## 比较目的

2015和2023年1—6月均有大量异常暖量到达东赤道太平洋。140°W累计输入分别为8.49和9.90 ZJ，东箱海洋热含量增量分别为8.60和11.12 ZJ。因此，两次事件的差异不能简单归结为2023年暖量没有到达。本比较检验的是：在相近的暖量到达和东部海温背景下，2015年是否建立了更有效的海洋向大气能量释放—深对流—西风异常协同变化。

## 数据与计算

海表温度采用OISST，地表热通量和纬向风应力采用ERA5，降水采用GPCP，OLR采用CPC月资料。除CPC OLR沿用资料自带异常外，其余异常均相对于1982—2014年逐月线性气候期望计算。ERA5热通量由向下为正统一转换为向上为正，因此正值表示海洋向大气散热增强。东部海洋热收支箱为10°S—5°N、140°W—80°W；东部SST箱为5°S—5°N、140°W—110°W；中太平洋对流和降水箱为5°S—5°N、180°—140°W；中西太平洋风应力箱为5°S—5°N、160°E—140°W。

下表的MAM、MJJ、JJA和SON为重叠的三个月窗口，用于识别两次事件何时开始分化，而不是四个相互独立的样本。

{_seasonal_markdown_table(seasonal)}

## 结果

两次事件在东部海温达到相近水平时，大气响应强度已经明显不同。MJJ东部绝对SST在2015年和2023年分别为{mjj.loc['2015', 'sst_east_raw_c']:.2f}和{mjj.loc['2023', 'sst_east_raw_c']:.2f} °C，SST异常分别为{mjj.loc['2015', 'sst_east_anom_c']:.2f}和{mjj.loc['2023', 'sst_east_anom_c']:.2f} °C。也就是说，MJJ期间2023年并不缺少维持海气相互作用所需的东部暖海温背景。

真正突出的差异出现在海气交换及其大气响应。MJJ向上潜热通量异常在2015年为{mjj.loc['2015', 'latent_loss_anom_wm2']:.2f} W m⁻²，在2023年仅为{mjj.loc['2023', 'latent_loss_anom_wm2']:.2f} W m⁻²；同期净海洋散热异常分别为{mjj.loc['2015', 'net_ocean_loss_anom_wm2']:.2f}和{mjj.loc['2023', 'net_ocean_loss_anom_wm2']:.2f} W m⁻²。差异主要由潜热通量贡献，表明2015年暖海面向大气提供水汽和能量的交换更强，而2023年的东部暖海温没有转化为同等强度的表面能量释放。

与热通量差异一致，2015年MJJ中太平洋−OLR和降水异常分别为{mjj.loc['2015', 'minus_olr_cp_wm2']:.2f} W m⁻²和{mjj.loc['2015', 'precip_central_anom_mmday']:.2f} mm d⁻¹，明显强于2023年的{mjj.loc['2023', 'minus_olr_cp_wm2']:.2f} W m⁻²和{mjj.loc['2023', 'precip_central_anom_mmday']:.2f} mm d⁻¹。中西太平洋东向风应力异常也由2015年的{mjj.loc['2015', 'tau_cwp_anom_nm2']:.3f} N m⁻²降至2023年的{mjj.loc['2023', 'tau_cwp_anom_nm2']:.3f} N m⁻²。分化在MAM已经出现，并在MJJ—JJA保持：2015年呈现较完整的散热增强、对流增强、降水增强和西风应力增强的协同演变，2023年则明显较弱。

## 判断边界

这些结果支持“2015年建立了更有效的海气耦合，而2023年暖量到达后未产生同等强度的大气响应”这一判断。海表散热可以理解为海洋向大气输送显热和潜热，其中潜热通过增加水汽并在凝结时释放能量，有利于深对流和环流响应；但不能把净散热直接等同于局地空气温度升高。

月尺度共演变不能据此证明“散热增强单向造成西风异常”。西风本身也会改变蒸发和潜热通量，对流、风和热通量属于相互反馈的耦合系统。因此，当前最稳妥的结论是：在近似的东部海温和暖量到达条件下，2015年的海气交换—对流—西风响应更协调、更强，2023年的耦合效率较低；中间触发机制仍需通过滞后关系、垂直结构或模式试验进一步检验。
"""
    path = output_dir / REPORT_NAME
    path.write_text(report, encoding="utf-8")
    return path


def run_pipeline(
    output_dir: Path | None = None,
    input_root: Path | None = None,
    output_root: Path | None = None,
) -> PipelineOutputs:
    """Run calculations once and write tables, audit, figure, and report."""

    data_root = discover_input_root() if input_root is None else Path(input_root)
    root = ROOT if output_root is None else Path(output_root)
    target = root / FIGURE_DIR if output_dir is None else Path(output_dir)
    monthly = build_monthly_table(input_root=data_root)
    seasonal = build_seasonal_table(monthly)
    audit = validate_monthly_table(monthly, seasonal)

    derived = root / DERIVED_DIR
    derived.mkdir(parents=True, exist_ok=True)
    monthly_path = derived / MONTHLY_CSV_NAME
    seasonal_path = derived / SEASONAL_CSV_NAME
    audit_path = derived / AUDIT_JSON_NAME
    monthly.to_csv(monthly_path, index=False, float_format="%.8g")
    seasonal.to_csv(seasonal_path, index=False, float_format="%.8g")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    png_path, pdf_path = make_figure(monthly, target)
    report_path = write_report(monthly, seasonal, target)
    return PipelineOutputs(
        monthly_csv=monthly_path,
        seasonal_csv=seasonal_path,
        audit_json=audit_path,
        png=png_path,
        pdf=pdf_path,
        report=report_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables-only", action="store_true")
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.tables_only:
        paths = write_tables(output_root=args.output_root, input_root=args.input_root)
    else:
        outputs = run_pipeline(output_root=args.output_root, input_root=args.input_root)
        paths = (
            outputs.monthly_csv,
            outputs.seasonal_csv,
            outputs.audit_json,
            outputs.png,
            outputs.pdf,
            outputs.report,
        )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
