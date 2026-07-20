"""Reusable methods for ordinary-El-Nino composites and response diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


SEASONS = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")
MEAN_FIELD_KEYS = ("sst", "u850", "v850", "precip", "d20")


@dataclass(frozen=True)
class WarmEpisode:
    """One NOAA ONI warm episode represented by consecutive threshold seasons."""

    event_year: int
    event_label: str
    first_year: int
    first_season: str
    last_year: int
    last_season: str
    n_consecutive_seasons: int
    peak_oni: float
    peak_season: str
    mature_djf_year: int
    mature_djf_oni: float
    is_extreme: bool


def read_oni_ascii(path: str | Path) -> pd.DataFrame:
    """Read the official NOAA CPC ``oni.ascii.txt`` whitespace table."""

    frame = pd.read_csv(path, sep=r"\s+")
    required = {"SEAS", "YR", "ANOM"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"ONI table is missing columns: {sorted(missing)}")
    frame = frame.rename(columns={"SEAS": "season", "YR": "year", "ANOM": "oni"})
    frame = frame.loc[frame["season"].isin(SEASONS), ["year", "season", "oni"]].copy()
    frame["year"] = frame["year"].astype(int)
    frame["oni"] = frame["oni"].astype(float)
    order = {season: index for index, season in enumerate(SEASONS)}
    frame["season_order"] = frame["season"].map(order).astype(int)
    frame = frame.sort_values(["year", "season_order"]).reset_index(drop=True)
    return frame


def identify_warm_episodes(
    oni: pd.DataFrame,
    *,
    threshold: float = 0.5,
    minimum_seasons: int = 5,
    extreme_threshold: float = 2.0,
) -> list[WarmEpisode]:
    """Identify NOAA-style warm episodes from consecutive overlapping seasons.

    The developing year is the year before the strongest DJF season in a run.
    This maps the prolonged 1986-1988 warm run to the 1986/87 developing event
    and the prolonged 2014-2016 run to the 2015/16 extreme event.
    """

    required = {"year", "season", "oni"}
    missing = required.difference(oni.columns)
    if missing:
        raise ValueError(f"ONI frame is missing columns: {sorted(missing)}")

    warm = oni["oni"].to_numpy(dtype=float) >= threshold
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, active in enumerate(warm):
        if active and start is None:
            start = index
        if start is not None and (not active or index == len(warm) - 1):
            stop = index if active and index == len(warm) - 1 else index - 1
            if stop - start + 1 >= minimum_seasons:
                runs.append((start, stop))
            start = None

    episodes: list[WarmEpisode] = []
    for start, stop in runs:
        run = oni.iloc[start : stop + 1]
        djf = run.loc[run["season"].eq("DJF")]
        if djf.empty:
            peak_row = run.loc[run["oni"].idxmax()]
            mature_djf_year = int(peak_row["year"])
            mature_djf_oni = float(peak_row["oni"])
        else:
            mature = djf.loc[djf["oni"].idxmax()]
            mature_djf_year = int(mature["year"])
            mature_djf_oni = float(mature["oni"])
        event_year = mature_djf_year - 1
        peak = run.loc[run["oni"].idxmax()]
        first = run.iloc[0]
        last = run.iloc[-1]
        episodes.append(
            WarmEpisode(
                event_year=event_year,
                event_label=f"{event_year}/{str(event_year + 1)[-2:]}",
                first_year=int(first["year"]),
                first_season=str(first["season"]),
                last_year=int(last["year"]),
                last_season=str(last["season"]),
                n_consecutive_seasons=int(len(run)),
                peak_oni=float(peak["oni"]),
                peak_season=f"{peak['season']} {int(peak['year'])}",
                mature_djf_year=mature_djf_year,
                mature_djf_oni=mature_djf_oni,
                is_extreme=bool(float(peak["oni"]) >= extreme_threshold),
            )
        )
    return episodes


def ordinary_event_manifest(
    episodes: Iterable[WarmEpisode],
    *,
    start_year: int = 1982,
    end_year: int = 2014,
    excluded_years: Sequence[int] = (1982, 1997, 2015, 2023, 2026),
) -> pd.DataFrame:
    """Return the deterministic ordinary-event selection table."""

    excluded = set(int(year) for year in excluded_years)
    selected = [
        episode
        for episode in episodes
        if start_year <= episode.event_year <= end_year
        and episode.event_year not in excluded
        and not episode.is_extreme
    ]
    rows = [asdict(episode) for episode in selected]
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No ordinary El Nino events satisfy the requested rules")
    frame.insert(2, "comparison_window", frame["event_year"].map(lambda year: f"Jan-Jun {year}"))
    frame.insert(3, "phase", "development")
    frame.insert(4, "group", "ordinary_non_extreme_composite")
    frame.insert(5, "role", "reference")
    return frame.sort_values("event_year").reset_index(drop=True)


def composite_fields(
    fields_by_year: Mapping[int, Mapping[str, object]],
    years: Sequence[int],
    *,
    method: str,
) -> dict[str, object]:
    """Compute an equal-event composite while validating coordinates."""

    if not years:
        raise ValueError("At least one event year is required")
    missing_years = [year for year in years if year not in fields_by_year]
    if missing_years:
        raise ValueError(f"Missing event fields for years: {missing_years}")

    template = fields_by_year[int(years[0])]
    coordinate_keys = ("lat", "lon", "sst_lat", "sst_lon", "d20_lon", "month_numbers")
    for year in years[1:]:
        candidate = fields_by_year[int(year)]
        for key in coordinate_keys:
            if not np.array_equal(np.asarray(template[key]), np.asarray(candidate[key])):
                raise ValueError(f"Coordinate mismatch for {key} in event year {year}")

    output: dict[str, object] = {}
    for key, value in template.items():
        if key in MEAN_FIELD_KEYS:
            stacked = np.stack([np.asarray(fields_by_year[int(year)][key], dtype=float) for year in years], axis=0)
            output[key] = np.nanmean(stacked, axis=0).astype(np.float32)
        else:
            output[key] = np.asarray(value).copy() if isinstance(value, np.ndarray) else value
    output["composite_years"] = np.asarray(years, dtype=np.int16)
    output["method"] = np.asarray(method)
    return output


def difference_fields(
    target: Mapping[str, object],
    reference: Mapping[str, object],
    *,
    method: str,
) -> dict[str, object]:
    """Return target-minus-reference fields in physical units."""

    output: dict[str, object] = {}
    for key, value in target.items():
        if key in MEAN_FIELD_KEYS:
            target_values = np.asarray(value, dtype=float)
            reference_values = np.asarray(reference[key], dtype=float)
            if target_values.shape != reference_values.shape:
                raise ValueError(f"Shape mismatch for difference field {key}")
            output[key] = (target_values - reference_values).astype(np.float32)
        else:
            output[key] = np.asarray(value).copy() if isinstance(value, np.ndarray) else value
    output["method"] = np.asarray(method)
    return output


def bootstrap_mean_ci(
    values: np.ndarray,
    *,
    n_bootstrap: int = 10_000,
    seed: int = 20260719,
    lower_percentile: float = 2.5,
    upper_percentile: float = 97.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Event-resampling confidence interval for one or more physical fields."""

    array = np.asarray(values, dtype=float)
    if array.ndim < 1 or array.shape[0] < 1:
        raise ValueError("values must contain at least one event along axis 0")
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, array.shape[0], size=(n_bootstrap, array.shape[0]))
    means = np.nanmean(array[samples], axis=1)
    center = np.nanmean(array, axis=0)
    lower = np.nanpercentile(means, lower_percentile, axis=0)
    upper = np.nanpercentile(means, upper_percentile, axis=0)
    return center, lower, upper


def fit_expected_response(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_target: float,
    y_target: float,
) -> dict[str, float]:
    """Fit a Peng-style historical response line and evaluate one target."""

    x = np.asarray(x_train, dtype=float)
    y = np.asarray(y_train, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 10:
        raise ValueError("At least 10 finite historical samples are required")
    slope, intercept = np.polyfit(x[valid], y[valid], 1)
    expected = float(slope * float(x_target) + intercept)
    observed = float(y_target)
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "correlation": float(np.corrcoef(x[valid], y[valid])[0, 1]),
        "predictor": float(x_target),
        "observed": observed,
        "expected": expected,
        "residual": observed - expected,
        "n_train": int(valid.sum()),
    }


def weighted_taylor_statistics(
    reference: np.ndarray,
    candidate: np.ndarray,
    weights: np.ndarray,
) -> dict[str, float]:
    """Return the standard Taylor (2001) pattern-comparison statistics.

    The function deliberately returns the component statistics rather than a
    synthesized similarity score.  Correlation measures pattern agreement,
    centered RMS difference measures pattern error in the variable's physical
    units, and the standard-deviation ratio measures relative amplitude.
    """

    reference_values = np.asarray(reference, dtype=float)
    candidate_values = np.asarray(candidate, dtype=float)
    weight_values = np.broadcast_to(np.asarray(weights, dtype=float), reference_values.shape)
    if reference_values.shape != candidate_values.shape:
        raise ValueError("reference and candidate must have the same shape")
    valid = (
        np.isfinite(reference_values)
        & np.isfinite(candidate_values)
        & np.isfinite(weight_values)
        & (weight_values > 0)
    )
    if int(valid.sum()) < 3:
        raise ValueError("At least three finite, positively weighted samples are required")

    reference_values = reference_values[valid]
    candidate_values = candidate_values[valid]
    weight_values = weight_values[valid]
    weight_values = weight_values / weight_values.sum()

    reference_mean = float(np.sum(weight_values * reference_values))
    candidate_mean = float(np.sum(weight_values * candidate_values))
    reference_centered = reference_values - reference_mean
    candidate_centered = candidate_values - candidate_mean
    reference_std = float(np.sqrt(np.sum(weight_values * reference_centered**2)))
    candidate_std = float(np.sqrt(np.sum(weight_values * candidate_centered**2)))
    if reference_std == 0 or candidate_std == 0:
        raise ValueError("Taylor statistics require non-zero reference and candidate variance")

    correlation = float(
        np.sum(weight_values * reference_centered * candidate_centered) / (reference_std * candidate_std)
    )
    centered_rmsd = float(
        np.sqrt(np.sum(weight_values * (candidate_centered - reference_centered) ** 2))
    )
    rmsd = float(np.sqrt(np.sum(weight_values * (candidate_values - reference_values) ** 2)))
    return {
        "pattern_correlation": correlation,
        "centered_rmsd": centered_rmsd,
        "standard_deviation_ratio": candidate_std / reference_std,
        "mean_bias": candidate_mean - reference_mean,
        "rmsd": rmsd,
        "n_samples": int(valid.sum()),
    }


def classify_ep_cp(ep_index: float, cp_index: float) -> str:
    """Assign the dominant Yan-style EOF index for a warm event."""

    if not np.isfinite(ep_index) or not np.isfinite(cp_index):
        return "unclassified"
    return "EP" if ep_index >= cp_index else "CP"
