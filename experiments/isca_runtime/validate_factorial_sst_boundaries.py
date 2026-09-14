"""Audit the four Isca SST boundary files used by the primary P0 factorial."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import xarray as xr


CASES = ("ia0_fep0", "ia0_fep1", "ia1_fep0", "ia1_fep1")
# The converted boundary follows Isca's bundled 1-degree AMIP file. Isca then
# interpolates it internally to the T42 atmospheric grid (64 x 128).
EXPECTED_SHAPE = (12, 180, 360)
FORCED_MONTHS = np.arange(2, 8)  # March--August in a zero-based annual file.
CLIM_MONTHS = np.array([0, 1, 8, 9, 10, 11])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forcing-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def summary(field: np.ndarray) -> dict[str, float]:
    return {
        "min": float(np.min(field)),
        "max": float(np.max(field)),
        "mean": float(np.mean(field)),
        "rms": float(np.sqrt(np.mean(np.square(field)))),
    }


def main() -> None:
    args = parse_args()
    fields: dict[str, np.ndarray] = {}
    records: dict[str, object] = {}
    errors: list[str] = []

    for case in CASES:
        stem = f"sst_ag_{case}_isca"
        path = args.forcing_dir / f"{stem}.nc"
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty forcing: {path}")
            continue
        with xr.open_dataset(path, decode_times=False) as dataset:
            if stem not in dataset:
                errors.append(f"{path.name}: missing variable {stem}")
                continue
            values = np.asarray(dataset[stem].values, dtype=np.float64)
        if values.shape != EXPECTED_SHAPE:
            errors.append(
                f"{path.name}: expected shape {EXPECTED_SHAPE}, found {values.shape}"
            )
            continue
        if not np.isfinite(values).all():
            errors.append(f"{path.name}: contains NaN or infinity")
            continue
        fields[case] = values
        records[case] = {
            "bytes": path.stat().st_size,
            "kelvin": summary(values),
        }

    contrasts: dict[str, object] = {}
    if len(fields) == len(CASES):
        base = fields["ia0_fep0"]
        offseason_max = max(
            float(np.max(np.abs(fields[case][CLIM_MONTHS] - base[CLIM_MONTHS])))
            for case in CASES[1:]
        )
        if offseason_max != 0.0:
            errors.append(
                f"the four cases differ outside March-August; max={offseason_max} K"
            )

        contrast_fields = {
            "FEP_at_IA0": fields["ia0_fep1"] - fields["ia0_fep0"],
            "FEP_at_IA1": fields["ia1_fep1"] - fields["ia1_fep0"],
            "IA_at_FEP0": fields["ia1_fep0"] - fields["ia0_fep0"],
            "IA_at_FEP1": fields["ia1_fep1"] - fields["ia0_fep1"],
            "IA_x_FEP": (
                fields["ia1_fep1"]
                - fields["ia1_fep0"]
                - fields["ia0_fep1"]
                + fields["ia0_fep0"]
            ),
        }
        for name, field in contrast_fields.items():
            forced = field[FORCED_MONTHS]
            contrasts[name] = {
                "march_august_kelvin": summary(forced),
                "outside_march_august_max_abs_kelvin": float(
                    np.max(np.abs(field[CLIM_MONTHS]))
                ),
            }
            if name != "IA_x_FEP" and float(np.sqrt(np.mean(forced**2))) <= 1e-4:
                errors.append(f"{name} is effectively zero in March-August")

        # A non-zero interaction is allowed and is the quantity being tested;
        # the gate only requires the two main forcing contrasts to be present.
        records["outside_march_august_case_difference_max_abs_kelvin"] = offseason_max

    complete = not errors and len(fields) == len(CASES)
    audit = {
        "complete": complete,
        "expected_shape": EXPECTED_SHAPE,
        "forced_months": "March-August",
        "errors": errors,
        "cases": records,
        "contrasts": contrasts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if not complete:
        raise SystemExit(f"FACTORIAL_SST_VALIDATION_FAILED see={args.output}")
    print(f"FACTORIAL_SST_VALIDATION_COMPLETE output={args.output}")


if __name__ == "__main__":
    main()
