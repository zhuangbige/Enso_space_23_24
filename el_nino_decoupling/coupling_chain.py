"""Minimal monthly air--sea coupling closure for ENSO event diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd


BASELINE_START = 1982
BASELINE_END = 2022
EVENT_MONTHS = ((4, 12), (1, 2))


@dataclass(frozen=True)
class LinkSpec:
    name: str
    label: str
    predictor: str
    target: str
    state: str | None
    lag: int
    predictor_units: str
    target_units: str


LINK_SPECS = (
    LinkSpec(
        "atmospheric",
        "SST -> zonal wind stress",
        "nino3_sst_anom",
        "tau_x_era5_anom",
        None,
        0,
        "degC",
        "N m-2",
    ),
    LinkSpec(
        "ocean_adjustment",
        "zonal wind stress -> D20 slope",
        "tau_x_era5_anom",
        "d20_slope_anom",
        "d20_slope_anom",
        1,
        "N m-2",
        "m",
    ),
    LinkSpec(
        "thermocline_feedback",
        "eastern D20 -> Nino3 SST",
        "d20_east_anom",
        "nino3_sst_anom",
        "nino3_sst_anom",
        1,
        "m",
        "degC",
    ),
    LinkSpec(
        "thermal_damping",
        "Nino3 SST -> net surface heat flux",
        "nino3_sst_anom",
        "qnet_nino3_anom",
        None,
        0,
        "degC",
        "W m-2",
    ),
)


ERA5_ALIASES = {
    "tau_x": (
        "avg_iews",
        "metss",
        "mean_eastward_turbulent_surface_stress",
        "ewssra",
    ),
    "shortwave": (
        "avg_snswrf",
        "msnswrf",
        "mean_surface_net_short_wave_radiation_flux",
        "msnswrfcs",
    ),
    "longwave": (
        "avg_snlwrf",
        "msnlwrf",
        "mean_surface_net_long_wave_radiation_flux",
    ),
    "latent": ("avg_slhtf", "mslhf", "mean_surface_latent_heat_flux"),
    "sensible": ("avg_ishf", "msshf", "mean_surface_sensible_heat_flux"),
}


def _time_index(year: pd.Series, month: pd.Series) -> pd.DatetimeIndex:
    values = pd.to_datetime(
        {"year": year.astype(int), "month": month.astype(int), "day": 1}
    )
    if isinstance(values, pd.Series):
        values = values.dt.to_period("M").dt.to_timestamp()
    else:
        values = values.to_period("M").to_timestamp()
    return pd.DatetimeIndex(values)


def _series_from_csv(path: Path, value_column: str = "value") -> pd.Series:
    frame = pd.read_csv(path)
    if not {"year", "month", value_column}.issubset(frame.columns):
        raise ValueError(f"{path} lacks year/month/{value_column}: {list(frame.columns)}")
    index = _time_index(frame["year"], frame["month"])
    series = pd.Series(frame[value_column].astype(float).to_numpy(), index=index, name=value_column)
    if series.index.has_duplicates:
        raise ValueError(f"duplicate monthly rows in {path}")
    return series.sort_index()


def preprocess_monthly_series(
    raw: pd.Series,
    *,
    baseline_start: int = BASELINE_START,
    baseline_end: int = BASELINE_END,
) -> pd.DataFrame:
    """Compute same-month anomalies and remove the baseline same-month trend."""

    series = raw.copy().astype(float).sort_index()
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("raw series must use a DatetimeIndex")
    if series.index.has_duplicates:
        raise ValueError("raw series contains duplicate months")
    full = pd.date_range(series.index.min(), series.index.max(), freq="MS")
    series = series.reindex(full)

    anomaly = pd.Series(np.nan, index=full, dtype=float)
    trend = pd.Series(np.nan, index=full, dtype=float)
    detrended = pd.Series(np.nan, index=full, dtype=float)
    slope = pd.Series(np.nan, index=full, dtype=float)

    decimal_year = full.year.astype(float) + (full.month.astype(float) - 0.5) / 12.0
    for month in range(1, 13):
        month_mask = full.month == month
        base_mask = month_mask & (full.year >= baseline_start) & (full.year <= baseline_end)
        valid_base = base_mask & np.isfinite(series.to_numpy())
        if valid_base.sum() < 20:
            raise ValueError(
                f"month {month} has only {valid_base.sum()} valid baseline values; at least 20 required"
            )
        climatology = float(series.to_numpy()[valid_base].mean())
        month_anomaly = series.to_numpy()[month_mask] - climatology
        anomaly.loc[month_mask] = month_anomaly
        x = decimal_year[valid_base]
        y = anomaly.to_numpy()[valid_base]
        fit_slope, fit_intercept = np.polyfit(x, y, 1)
        fitted = fit_slope * decimal_year[month_mask] + fit_intercept
        trend.loc[month_mask] = fitted
        detrended.loc[month_mask] = month_anomaly - fitted
        slope.loc[month_mask] = fit_slope

    return pd.DataFrame(
        {
            "raw": series,
            "anomaly_before_detrend": anomaly,
            "trend": trend,
            "anomaly": detrended,
            "trend_slope_per_year": slope,
        },
        index=full,
    )


def area_weighted_mean(da, *, lat_bounds: tuple[float, float], lon_bounds: tuple[float, float]):
    """Return a cosine-latitude weighted mean from a standardized DataArray."""

    lat0, lat1 = sorted(lat_bounds)
    lon0, lon1 = sorted(lon_bounds)
    sub = da.where(
        (da["lat"] >= lat0)
        & (da["lat"] <= lat1)
        & (da["lon"] >= lon0)
        & (da["lon"] <= lon1),
        drop=True,
    )
    if sub.sizes.get("lat", 0) == 0 or sub.sizes.get("lon", 0) == 0:
        raise ValueError(f"empty area selection lat={lat_bounds} lon={lon_bounds}")
    weights = np.cos(np.deg2rad(sub["lat"]))
    return sub.weighted(weights).mean(("lat", "lon"), skipna=True)


def _open_dataset(path: Path):
    import xarray as xr

    try:
        return xr.open_dataset(path, engine="h5netcdf")
    except Exception:
        return xr.open_dataset(path, engine="scipy")


def _standardize_dataset(ds):
    rename: dict[str, str] = {}
    for old, new in (
        ("valid_time", "time"),
        ("latitude", "lat"),
        ("longitude", "lon"),
    ):
        if old in ds.coords or old in ds.dims:
            rename[old] = new
    ds = ds.rename(rename)
    required = {"time", "lat", "lon"}
    if not required.issubset(ds.coords):
        raise ValueError(f"ERA5 file lacks standardized coordinates: {list(ds.coords)}")
    ds = ds.assign_coords(lon=(ds["lon"] % 360)).sortby("lon").sortby("lat")
    ds = ds.assign_coords(time=pd.to_datetime(ds["time"].values).to_period("M").to_timestamp())
    return ds


def _find_variable(ds, aliases: Iterable[str], role: str):
    for name in aliases:
        if name in ds.data_vars:
            return ds[name]
    raise ValueError(f"ERA5 coupling file lacks {role}; found {list(ds.data_vars)}")


def _validate_era5_units(array, role: str) -> None:
    """Reject ERA5 fields whose declared units do not match the diagnostic."""

    units = str(array.attrs.get("units", "")).replace(" ", "").lower()
    if not units:
        raise ValueError(f"ERA5 {role} lacks units metadata")
    expected_prefix = "nm" if role == "tau_x" else "wm"
    if not units.startswith(expected_prefix) or "-2" not in units:
        expected = "N m-2" if role == "tau_x" else "W m-2"
        raise ValueError(f"ERA5 {role} units are {array.attrs.get('units')!r}; expected {expected}")


_ERA5_FILE_RE = re.compile(
    r"era5_coupling_(?P<part>[^_]+)_m(?P<month>\d{2})_(?P<start>\d{4})_(?P<end>\d{4})_(?P<grid>[^.]+)deg\.nc$"
)


def load_era5_coupling_indices(input_dir: Path) -> pd.DataFrame:
    """Load ERA5 shards and return CWP stress and Nino3 net heat flux."""

    import xarray as xr

    groups: dict[tuple[str, str, str, str], list[Path]] = {}
    for path in sorted(input_dir.glob("era5_coupling_*.nc")):
        match = _ERA5_FILE_RE.match(path.name)
        if not match:
            continue
        key = (match["month"], match["start"], match["end"], match["grid"])
        groups.setdefault(key, []).append(path)
    if not groups:
        raise FileNotFoundError(f"no ERA5 coupling shards in {input_dir}")

    frames: list[pd.DataFrame] = []
    for key, paths in sorted(groups.items()):
        pieces = []
        for path in paths:
            ds = _standardize_dataset(_open_dataset(path))
            selected_fields = {}
            for role, aliases in ERA5_ALIASES.items():
                field = _find_variable(ds, aliases, role)
                _validate_era5_units(field, role)
                selected_fields[role] = field
            selected = xr.Dataset(selected_fields).load()
            ds.close()
            pieces.append(selected)
        merged = xr.concat(pieces, dim="lon").sortby("lon")
        _, unique_index = np.unique(merged["lon"].values, return_index=True)
        merged = merged.isel(lon=np.sort(unique_index))

        tau = area_weighted_mean(
            merged["tau_x"], lat_bounds=(-5, 5), lon_bounds=(160, 220)
        )
        qnet_field = (
            merged["shortwave"]
            + merged["longwave"]
            + merged["latent"]
            + merged["sensible"]
        )
        qnet = area_weighted_mean(
            qnet_field, lat_bounds=(-5, 5), lon_bounds=(210, 270)
        )
        frame = pd.DataFrame(
            {
                "time": pd.to_datetime(tau["time"].values),
                "tau_x_era5": tau.to_numpy().astype(float),
                "qnet_nino3": qnet.to_numpy().astype(float),
            }
        ).set_index("time")
        frames.append(frame)
        merged.close()

    result = pd.concat(frames).sort_index()
    result = result[~result.index.duplicated(keep="last")]
    if result["tau_x_era5"].abs().max() > 5:
        raise ValueError("ERA5 zonal stress exceeds 5 N m-2; check units")
    if result["qnet_nino3"].abs().max() > 2000:
        raise ValueError("ERA5 net surface heat flux exceeds 2000 W m-2; check units")
    return result


def load_oras5_d20(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"year", "month", "requested_lon", "d20_m"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path} lacks ORAS5 D20 fields")
    frame["time"] = _time_index(frame["year"], frame["month"])
    frame["requested_lon"] = frame["requested_lon"].astype(float) % 360
    east = frame[frame["requested_lon"].between(210, 260)].groupby("time")["d20_m"].mean()
    # 140E--170W crosses the date line; in 0--360 notation it is 140--190E.
    west = frame[frame["requested_lon"].between(140, 190)].groupby("time")["d20_m"].mean()
    result = pd.concat({"d20_east": east, "d20_west": west}, axis=1)
    result["d20_slope"] = result["d20_east"] - result["d20_west"]
    return result.sort_index()


def load_oras5_stress(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    required = {"year", "month", "requested_lon", "tau_x_n_m2"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path} lacks ORAS5 stress fields")
    frame["time"] = _time_index(frame["year"], frame["month"])
    frame["requested_lon"] = frame["requested_lon"].astype(float) % 360
    selected = frame[frame["requested_lon"].between(160, 220)]
    return selected.groupby("time")["tau_x_n_m2"].mean().sort_index().rename("tau_x_oras5")


def load_gpcp_cwp(path: Path) -> pd.Series:
    ds = _standardize_dataset(_open_dataset(path))
    if "precip" not in ds:
        raise ValueError(f"GPCP file lacks precip: {path}")
    mean = area_weighted_mean(ds["precip"], lat_bounds=(-5, 5), lon_bounds=(160, 220)).load()
    ds.close()
    return pd.Series(mean.to_numpy(), index=pd.to_datetime(mean["time"].values), name="gpcp_cwp")


def load_olr_cp(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    region = frame[frame["region"] == "central_pacific_180_140w"].copy()
    index = _time_index(region["year"], region["month"])
    return pd.Series(region["olr_anomaly"].astype(float).to_numpy(), index=index, name="olr_cp")


def build_monthly_table(
    *,
    oisst_path: Path,
    ersst_path: Path,
    d20_path: Path,
    oras5_stress_path: Path,
    era5_dir: Path,
    gpcp_path: Path | None = None,
    olr_path: Path | None = None,
    baseline_start: int = BASELINE_START,
    baseline_end: int = BASELINE_END,
) -> pd.DataFrame:
    raw = pd.DataFrame(
        {
            "nino3_sst": _series_from_csv(oisst_path),
            "nino3_sst_ersst": _series_from_csv(ersst_path),
        }
    )
    raw = raw.join(load_oras5_d20(d20_path), how="outer")
    raw = raw.join(load_oras5_stress(oras5_stress_path), how="outer")
    raw = raw.join(load_era5_coupling_indices(era5_dir), how="outer")
    if gpcp_path is not None and gpcp_path.exists():
        raw = raw.join(load_gpcp_cwp(gpcp_path), how="outer")
    if olr_path is not None and olr_path.exists():
        raw = raw.join(load_olr_cp(olr_path), how="outer")
    raw = raw.sort_index()

    output = pd.DataFrame(index=raw.index)
    for column in raw.columns:
        series = raw[column].dropna()
        if series.empty:
            continue
        local_start = baseline_start
        if column == "olr_cp" and series.index.min().year > baseline_start:
            local_start = int(series.index.min().year)
        processed = preprocess_monthly_series(
            series, baseline_start=local_start, baseline_end=baseline_end
        )
        output[f"{column}_raw"] = processed["raw"].reindex(output.index)
        output[f"{column}_anom"] = processed["anomaly"].reindex(output.index)
        output[f"{column}_trend_per_year"] = processed["trend_slope_per_year"].reindex(output.index)
    output.index.name = "time"
    return output


def validate_monthly_table(
    table: pd.DataFrame,
    *,
    baseline_start: int = BASELINE_START,
    baseline_end: int = BASELINE_END,
) -> dict[str, object]:
    required = {
        "nino3_sst_anom",
        "tau_x_era5_anom",
        "d20_east_anom",
        "d20_west_anom",
        "d20_slope_anom",
        "qnet_nino3_anom",
    }
    missing = required - set(table.columns)
    if missing:
        raise ValueError(f"monthly table lacks required fields: {sorted(missing)}")
    if table.index.has_duplicates or not table.index.is_monotonic_increasing:
        raise ValueError("monthly table time must be unique and increasing")
    expected_full_index = pd.date_range(table.index.min(), table.index.max(), freq="MS")
    if not table.index.equals(expected_full_index):
        missing_months = expected_full_index.difference(table.index)
        raise ValueError(f"monthly table has discontinuous months: {missing_months[:12].tolist()}")
    baseline = table[(table.index.year >= baseline_start) & (table.index.year <= baseline_end)]
    counts = baseline[list(required)].notna().groupby(baseline.index.month).sum()
    if int(counts.min().min()) < 35:
        raise ValueError(f"baseline monthly coverage is insufficient:\n{counts}")
    required_windows = {
        "baseline": pd.date_range(f"{baseline_start}-01-01", f"{baseline_end}-12-01", freq="MS"),
        "2023/24 event plus lag target": pd.date_range("2023-04-01", "2024-03-01", freq="MS"),
        "2026 frozen-model validation": pd.date_range("2026-01-01", "2026-05-01", freq="MS"),
    }
    coverage: dict[str, dict[str, object]] = {}
    for label, expected_index in required_windows.items():
        selected = table.reindex(expected_index)[sorted(required)]
        missing_counts = selected.isna().sum()
        if int(missing_counts.sum()) > 0:
            missing_detail = {key: int(value) for key, value in missing_counts.items() if value}
            raise ValueError(f"{label} has missing required monthly data: {missing_detail}")
        coverage[label] = {
            "start": str(expected_index.min().date()),
            "end": str(expected_index.max().date()),
            "months": int(len(expected_index)),
        }
    return {
        "start": str(table.index.min().date()),
        "end": str(table.index.max().date()),
        "rows": int(len(table)),
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
        "minimum_monthly_baseline_count": int(counts.min().min()),
        "complete_required_windows": coverage,
        "missing_by_variable": {key: int(value) for key, value in table.isna().sum().items()},
    }


def event_window(event_year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    return pd.Timestamp(event_year, 4, 1), pd.Timestamp(event_year + 1, 2, 1)


def _link_arrays(table: pd.DataFrame, spec: LinkSpec) -> pd.DataFrame:
    frame = pd.DataFrame(index=table.index)
    frame["predictor"] = table[spec.predictor]
    frame["state"] = table[spec.state] if spec.state else 0.0
    frame["target"] = table[spec.target].shift(-spec.lag) if spec.lag else table[spec.target]
    frame["target_time"] = frame.index + pd.offsets.MonthBegin(spec.lag)
    frame["month"] = frame.index.month
    return frame


def fit_monthly_models(
    table: pd.DataFrame,
    *,
    baseline_start: int = BASELINE_START,
    baseline_end: int = BASELINE_END,
    exclude_windows: tuple[tuple[pd.Timestamp, pd.Timestamp], ...] = (),
    sample_positions: np.ndarray | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in LINK_SPECS:
        frame = _link_arrays(table, spec)
        base_mask = (frame.index.year >= baseline_start) & (frame.index.year <= baseline_end)
        base_mask &= frame["target_time"].dt.year <= baseline_end
        for start, end in exclude_windows:
            base_mask &= ~((frame.index >= start) & (frame.index <= end))
            base_mask &= ~((frame["target_time"] >= start) & (frame["target_time"] <= end))
        if sample_positions is None:
            sampled = frame.loc[base_mask].copy()
        else:
            allowed = np.flatnonzero(base_mask.to_numpy())
            selected = sample_positions[np.isin(sample_positions, allowed)]
            sampled = frame.iloc[selected].copy()

        for month in range(1, 13):
            month_frame = sampled[sampled["month"] == month].dropna(
                subset=["predictor", "state", "target"]
            )
            if len(month_frame) < 20:
                raise ValueError(f"{spec.name} month {month} has only {len(month_frame)} training rows")
            if spec.state is None:
                design = np.column_stack(
                    [np.ones(len(month_frame)), month_frame["predictor"].to_numpy()]
                )
            else:
                design = np.column_stack(
                    [
                        np.ones(len(month_frame)),
                        month_frame["state"].to_numpy(),
                        month_frame["predictor"].to_numpy(),
                    ]
                )
            target = month_frame["target"].to_numpy()
            coefficients, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
            fitted = design @ coefficients
            residual = target - fitted
            ss_total = float(np.sum((target - target.mean()) ** 2))
            r2 = np.nan if ss_total == 0 else 1 - float(np.sum(residual**2)) / ss_total
            if spec.state is None:
                intercept, beta = coefficients
                persistence = 0.0
            else:
                intercept, persistence, beta = coefficients
            rows.append(
                {
                    "link": spec.name,
                    "link_label": spec.label,
                    "month": month,
                    "intercept": float(intercept),
                    "persistence": float(persistence),
                    "feedback_beta": float(beta),
                    "n": int(len(month_frame)),
                    "r2": float(r2),
                    "residual_std": float(np.std(residual, ddof=design.shape[1])),
                    "predictor_units": spec.predictor_units,
                    "target_units": spec.target_units,
                    "baseline_start": baseline_start,
                    "baseline_end": baseline_end,
                }
            )
    return pd.DataFrame(rows)


def event_diagnostics(
    table: pd.DataFrame,
    coefficients: pd.DataFrame,
    *,
    event_label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    product_combo: str = "OISST+ERA5",
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in LINK_SPECS:
        frame = _link_arrays(table, spec)
        selected = frame[(frame.index >= start) & (frame.index <= end)]
        coeff = coefficients[coefficients["link"] == spec.name].set_index("month")
        for time, record in selected.iterrows():
            if not np.isfinite(record[["predictor", "state", "target"]].to_numpy(float)).all():
                continue
            params = coeff.loc[int(record["month"])]
            intercept = float(params["intercept"])
            persistence = float(params["persistence"])
            beta = float(params["feedback_beta"])
            memory = persistence * float(record["state"])
            y_star = float(record["target"]) - intercept - memory
            expected = beta * float(record["predictor"])
            rows.append(
                {
                    "event": event_label,
                    "product_combo": product_combo,
                    "link": spec.name,
                    "link_label": spec.label,
                    "time": time,
                    "target_time": record["target_time"],
                    "predictor": float(record["predictor"]),
                    "state": float(record["state"]),
                    "actual_target": float(record["target"]),
                    "intercept": intercept,
                    "persistence": persistence,
                    "feedback_beta": beta,
                    "memory_contribution": memory,
                    "observed_innovation": y_star,
                    "expected_feedback": expected,
                    "residual": y_star - expected,
                    "predicted_target": intercept + memory + expected,
                    "predictor_units": spec.predictor_units,
                    "target_units": spec.target_units,
                }
            )
    return pd.DataFrame(rows)


def eta_from_diagnostics(diagnostics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (event, product, link, label), group in diagnostics.groupby(
        ["event", "product_combo", "link", "link_label"], sort=False
    ):
        expected = group["expected_feedback"].to_numpy(float)
        observed = group["observed_innovation"].to_numpy(float)
        denominator = float(np.sum(expected**2))
        eta = np.nan if denominator == 0 else float(np.sum(observed * expected) / denominator)
        rows.append(
            {
                "event": event,
                "product_combo": product,
                "link": link,
                "link_label": label,
                "eta": eta,
                "n_months": int(len(group)),
                "start": group["time"].min(),
                "end": group["time"].max(),
            }
        )
    return pd.DataFrame(rows)


def _eligible_bootstrap_blocks(
    table: pd.DataFrame,
    *,
    baseline_start: int,
    baseline_end: int,
    block_months: int,
    exclude_windows: tuple[tuple[pd.Timestamp, pd.Timestamp], ...],
) -> tuple[np.ndarray, list[np.ndarray]]:
    positions = np.arange(len(table))
    eligible = (table.index.year >= baseline_start) & (table.index.year <= baseline_end)
    for start, end in exclude_windows:
        eligible &= ~((table.index >= start) & (table.index <= end))
    eligible_positions = positions[eligible]
    eligible_set = set(eligible_positions.tolist())
    blocks = []
    for start_position in eligible_positions:
        block = np.arange(start_position, start_position + block_months)
        if block[-1] >= len(table):
            continue
        if all(int(position) in eligible_set for position in block):
            blocks.append(block)
    if not blocks:
        raise ValueError("no complete bootstrap blocks are available")
    return eligible_positions, blocks


def bootstrap_event_eta(
    table: pd.DataFrame,
    *,
    event_label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    exclude_windows: tuple[tuple[pd.Timestamp, pd.Timestamp], ...],
    n_bootstrap: int = 10_000,
    block_months: int = 24,
    seed: int = 20260716,
    baseline_start: int = BASELINE_START,
    baseline_end: int = BASELINE_END,
) -> pd.DataFrame:
    """Return block-bootstrap uncertainty using batched weighted least squares.

    A direct pandas refit for every draw is prohibitively slow at 10,000
    replicates.  The block samples are therefore represented as row-count
    weights and all OLS systems for a given link/month are solved in one
    batched NumPy operation.  This is algebraically identical to fitting the
    explicitly repeated bootstrap rows.
    """

    rng = np.random.default_rng(seed)
    eligible_positions, blocks = _eligible_bootstrap_blocks(
        table,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        block_months=block_months,
        exclude_windows=exclude_windows,
    )
    block_count = int(np.ceil(len(eligible_positions) / block_months))
    block_matrix = np.stack(blocks)
    chosen = rng.integers(0, len(blocks), size=(n_bootstrap, block_count))
    samples = block_matrix[chosen].reshape(n_bootstrap, -1)[:, : len(eligible_positions)]
    counts = np.zeros((n_bootstrap, len(table)), dtype=np.int16)
    np.add.at(
        counts,
        (np.repeat(np.arange(n_bootstrap), samples.shape[1]), samples.reshape(-1)),
        1,
    )

    coefficient_draws: dict[str, np.ndarray] = {}
    for spec in LINK_SPECS:
        frame = _link_arrays(table, spec)
        base_mask = (frame.index.year >= baseline_start) & (frame.index.year <= baseline_end)
        base_mask &= frame["target_time"].dt.year <= baseline_end
        for exclude_start, exclude_end in exclude_windows:
            base_mask &= ~((frame.index >= exclude_start) & (frame.index <= exclude_end))
            base_mask &= ~(
                (frame["target_time"] >= exclude_start) & (frame["target_time"] <= exclude_end)
            )
        parameter_count = 2 if spec.state is None else 3
        draws = np.full((n_bootstrap, 12, parameter_count), np.nan, dtype=float)
        for month in range(1, 13):
            valid = (
                base_mask
                & (frame["month"] == month)
                & frame[["predictor", "state", "target"]].notna().all(axis=1)
            )
            positions = np.flatnonzero(valid.to_numpy())
            if len(positions) < 20:
                raise ValueError(f"{spec.name} month {month} has only {len(positions)} bootstrap rows")
            selected = frame.iloc[positions]
            if spec.state is None:
                design = np.column_stack(
                    [np.ones(len(selected)), selected["predictor"].to_numpy(float)]
                )
            else:
                design = np.column_stack(
                    [
                        np.ones(len(selected)),
                        selected["state"].to_numpy(float),
                        selected["predictor"].to_numpy(float),
                    ]
                )
            target_values = selected["target"].to_numpy(float)
            weights = counts[:, positions].astype(float, copy=False)
            xtwx = np.einsum("bn,ni,nj->bij", weights, design, design, optimize=True)
            xtwy = np.einsum("bn,ni,n->bi", weights, design, target_values, optimize=True)
            try:
                solved = np.linalg.solve(xtwx, xtwy)
            except np.linalg.LinAlgError:
                ridge = np.eye(parameter_count)[None, :, :] * 1e-10
                solved = np.linalg.solve(xtwx + ridge, xtwy)
            draws[:, month - 1, :] = solved
        coefficient_draws[spec.name] = draws

    eta_draws: dict[str, np.ndarray] = {}
    for spec in LINK_SPECS:
        frame = _link_arrays(table, spec)
        selected = frame[(frame.index >= start) & (frame.index <= end)].dropna(
            subset=["predictor", "state", "target"]
        )
        numerator = np.zeros(n_bootstrap, dtype=float)
        denominator = np.zeros(n_bootstrap, dtype=float)
        draws = coefficient_draws[spec.name]
        for _, record in selected.iterrows():
            params = draws[:, int(record["month"]) - 1, :]
            if spec.state is None:
                intercept = params[:, 0]
                persistence = 0.0
                beta = params[:, 1]
            else:
                intercept = params[:, 0]
                persistence = params[:, 1]
                beta = params[:, 2]
            observed = float(record["target"]) - intercept - persistence * float(record["state"])
            expected = beta * float(record["predictor"])
            numerator += observed * expected
            denominator += expected**2
        eta_draws[spec.name] = np.divide(
            numerator,
            denominator,
            out=np.full_like(numerator, np.nan),
            where=denominator > 0,
        )
    rows = []
    for spec in LINK_SPECS:
        values = eta_draws[spec.name]
        rows.append(
            {
                "event": event_label,
                "link": spec.name,
                "ci_low": float(np.nanquantile(values, 0.025)),
                "ci_high": float(np.nanquantile(values, 0.975)),
                "bootstrap_median": float(np.nanmedian(values)),
                "n_bootstrap": int(n_bootstrap),
                "block_months": int(block_months),
                "seed": int(seed),
            }
        )
    return pd.DataFrame(rows)


def pseudo_event_distribution(
    table: pd.DataFrame,
    *,
    first_year: int = BASELINE_START,
    last_year: int = BASELINE_END - 1,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for year in range(first_year, last_year + 1):
        start, end = event_window(year)
        coefficients = fit_monthly_models(table, exclude_windows=((start, end),))
        diagnostics = event_diagnostics(
            table,
            coefficients,
            event_label=str(year),
            start=start,
            end=end,
        )
        score = eta_from_diagnostics(diagnostics)
        score["event_year"] = year
        rows.append(score)
    return pd.concat(rows, ignore_index=True)


def replace_product(
    table: pd.DataFrame,
    *,
    sst_column: str | None = None,
    stress_column: str | None = None,
) -> pd.DataFrame:
    output = table.copy()
    if sst_column is not None:
        output["nino3_sst_anom"] = output[sst_column]
    if stress_column is not None:
        output["tau_x_era5_anom"] = output[stress_column]
    return output
