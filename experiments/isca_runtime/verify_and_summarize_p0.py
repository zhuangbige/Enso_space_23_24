"""Verify the Isca P0 matrix and summarize its paired factorial effects.

The script is intentionally read-only with respect to model output.  It checks
all four prescribed-SST cases and all ensemble members, extracts monthly
coupling diagnostics, and writes machine-readable screening tables.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


CASES = ("ia0_fep0", "ia0_fep1", "ia1_fep0", "ia1_fep1")
MONTH_NAMES = {1: "Mar", 2: "Apr", 3: "May", 4: "Jun", 5: "Jul", 6: "Aug"}
REQUIRED_VARIABLES = (
    "t_surf",
    "precipitation",
    "olr",
    "u_10m",
    "v_10m",
    "flux_u",
    "ps",
    "slp",
)
METRICS = (
    "precip_tp_mm_day",
    "precip_cp_mm_day",
    "olr_cp_w_m2",
    "peng_cwp_u10_m_s",
    "tau_cwp_ocean_n_m2",
    "slp_drive_w_minus_e_hpa",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--members", type=int, default=10)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--bootstrap", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260801)
    return parser.parse_args()


def normalize_grid(field: xr.DataArray) -> xr.DataArray:
    result = field
    if "time" in result.dims:
        if result.sizes["time"] != 1:
            raise ValueError(f"expected one time sample, got {result.sizes['time']}")
        result = result.isel(time=0, drop=True)
    lon = np.mod(result.lon.astype(float), 360.0)
    result = result.assign_coords(lon=lon).sortby("lon")
    _, unique = np.unique(result.lon.values, return_index=True)
    return result.isel(lon=np.sort(unique)).sortby("lat")


def weighted_box(
    field: xr.DataArray, lon0: float, lon1: float, lat0: float = -5.0, lat1: float = 5.0
) -> float:
    normalized = normalize_grid(field)
    subset = normalized.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(f"empty box lat={lat0}:{lat1}, lon={lon0}:{lon1}")
    weights = np.cos(np.deg2rad(subset.lat))
    return float(subset.weighted(weights).mean(("lat", "lon")))


def experiment_path(root: Path, case: str, member: int, run: int) -> Path:
    return (
        root
        / f"isca_2023_{case}_m{member:02d}_t42"
        / f"run{run:04d}"
        / "atmos_monthly.nc"
    )


def inspect_file(path: Path) -> tuple[dict[str, float], dict[str, object]]:
    with xr.open_dataset(path, decode_times=False) as dataset:
        missing = sorted(set(REQUIRED_VARIABLES) - set(dataset.data_vars))
        if missing:
            raise ValueError(f"missing variables: {missing}")
        expected_dims = {"lon": 128, "lat": 64, "pfull": 40}
        wrong_dims = {
            name: {"expected": size, "found": dataset.sizes.get(name)}
            for name, size in expected_dims.items()
            if dataset.sizes.get(name) != size
        }
        if wrong_dims:
            raise ValueError(f"unexpected dimensions: {wrong_dims}")

        ranges: dict[str, list[float]] = {}
        for variable in REQUIRED_VARIABLES:
            values = dataset[variable]
            if not bool(np.isfinite(values).all()):
                raise ValueError(f"{variable} contains NaN or infinity")
            ranges[variable] = [float(values.min()), float(values.max())]

        precipitation = dataset["precipitation"] * 86_400.0
        metrics = {
            "precip_tp_mm_day": weighted_box(precipitation, 180.0, 250.0),
            "precip_cp_mm_day": weighted_box(precipitation, 180.0, 220.0),
            "olr_cp_w_m2": weighted_box(dataset["olr"], 180.0, 220.0),
            "peng_cwp_u10_m_s": weighted_box(dataset["u_10m"], 140.0, 200.0),
            # Isca flux_u is the surface momentum flux into the atmosphere.
            # Negating it gives eastward stress exerted by air on the ocean,
            # matching the sign of ERA5 instantaneous eastward turbulent stress.
            "tau_cwp_ocean_n_m2": -weighted_box(dataset["flux_u"], 160.0, 220.0),
            "slp_drive_w_minus_e_hpa": (
                weighted_box(dataset["slp"], 130.0, 160.0)
                - weighted_box(dataset["slp"], 220.0, 250.0)
            )
            / 100.0,
        }
        metadata = {
            "sizes": {key: int(value) for key, value in dataset.sizes.items()},
            "ranges": ranges,
        }
    return metrics, metadata


def paired_effects(monthly: pd.DataFrame) -> pd.DataFrame:
    index = ["member", "run", "month", "month_name"]
    wide = monthly.pivot(index=index, columns="case", values=list(METRICS))
    rows: list[dict[str, object]] = []
    for metric in METRICS:
        current = wide[metric]
        contrasts = {
            "FEP_at_IA0": current["ia0_fep1"] - current["ia0_fep0"],
            "FEP_at_IA1": current["ia1_fep1"] - current["ia1_fep0"],
            "IA_at_FEP0": current["ia1_fep0"] - current["ia0_fep0"],
            "IA_at_FEP1": current["ia1_fep1"] - current["ia0_fep1"],
            "IA_x_FEP": (
                current["ia1_fep1"]
                - current["ia1_fep0"]
                - current["ia0_fep1"]
                + current["ia0_fep0"]
            ),
        }
        for contrast, values in contrasts.items():
            frame = values.rename("value").reset_index()
            frame["metric"] = metric
            frame["contrast"] = contrast
            rows.extend(frame.to_dict("records"))
    return pd.DataFrame(rows)


def bootstrap_summary(
    effects: pd.DataFrame, samples: int, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for (metric, contrast), group in effects.groupby(["metric", "contrast"]):
        # MJJ is model runs 3--5 because run 1 starts on 1 March.
        member_values = group.loc[group["run"].isin((3, 4, 5))].groupby("member")[
            "value"
        ].mean()
        values = member_values.to_numpy(float)
        resampled = values[rng.integers(0, len(values), size=(samples, len(values)))]
        boot_means = resampled.mean(axis=1)
        mean = float(values.mean())
        rows.append(
            {
                "season": "MJJ",
                "metric": metric,
                "contrast": contrast,
                "n_members": int(len(values)),
                "mean": mean,
                "sd": float(values.std(ddof=1)),
                "ci95_low": float(np.quantile(boot_means, 0.025)),
                "ci95_high": float(np.quantile(boot_means, 0.975)),
                "same_sign_fraction": float(
                    np.mean(np.sign(values) == np.sign(mean)) if mean != 0 else np.nan
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["metric", "contrast"])


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    file_checks: dict[str, object] = {}
    errors: list[dict[str, object]] = []

    for member in range(1, args.members + 1):
        for case in CASES:
            for run in range(1, args.months + 1):
                path = experiment_path(args.data, case, member, run)
                key = str(path.relative_to(args.data))
                if not path.is_file() or path.stat().st_size == 0:
                    errors.append({"file": key, "error": "missing or empty"})
                    continue
                try:
                    metrics, metadata = inspect_file(path)
                except Exception as error:  # preserve every failed path in the audit
                    errors.append({"file": key, "error": str(error)})
                    continue
                file_checks[key] = metadata
                rows.append(
                    {
                        "case": case,
                        "member": member,
                        "run": run,
                        "month": run + 2,
                        "month_name": MONTH_NAMES[run],
                        **metrics,
                    }
                )

    expected_files = len(CASES) * args.members * args.months
    monthly = pd.DataFrame(rows)
    complete = len(rows) == expected_files and not errors
    audit = {
        "complete": complete,
        "expected_files": expected_files,
        "valid_files": len(rows),
        "invalid_files": len(errors),
        "cases": list(CASES),
        "members": args.members,
        "months": args.months,
        "errors": errors,
        "files": file_checks,
    }
    (args.output / "p0_verification.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if rows:
        monthly.sort_values(["member", "case", "run"]).to_csv(
            args.output / "p0_monthly_metrics.csv", index=False
        )
    if not complete:
        raise SystemExit(
            f"P0 verification failed: {len(rows)}/{expected_files} valid files; "
            f"see {args.output / 'p0_verification.json'}"
        )

    effects = paired_effects(monthly)
    effects.to_csv(args.output / "p0_paired_monthly_effects.csv", index=False)
    summary = bootstrap_summary(effects, args.bootstrap, args.seed)
    summary.to_csv(args.output / "p0_mjj_factorial_summary.csv", index=False)
    print(
        f"P0_VERIFICATION_COMPLETE files={len(rows)} members={args.members} "
        f"months={args.months}"
    )


if __name__ == "__main__":
    main()
