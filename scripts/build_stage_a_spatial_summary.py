#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.spatial import grid_region_mean  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
OISST = ROOT / "data/interim/raw_validation/oisst_spatial_amj_jja.npz"
GPCP = ROOT / "data/interim/raw_validation/gpcp_spatial_amj_jja.npz"
NCEP = ROOT / "data/interim/raw_validation/ncep_spatial_amj_jja.npz"
OUT = ROOT / "data/derived/research/stage_a_spatial_summary.csv"
SEASONS = ("AMJ", "JJA")
CASES = ("2023", "comparable", "difference")
OISST_REGIONS = {
    "nino3": (-5, 5, 210, 270),
    "tropical_indian_ocean": (-20, 20, 40, 110),
    "maritime_continent": (-10, 10, 95, 150),
    "western_pacific_warm_pool": (-10, 10, 120, 160),
    "tropical_north_atlantic": (0, 20, 300, 340),
}
GPCP_REGIONS = {
    "central_pacific_180_140w": (-5, 5, 180, 220),
    "eastern_pacific_140w_100w": (-5, 5, 220, 260),
    "full_tropical_pacific_120e_80w": (-5, 5, 120, 280),
    "western_central_pacific_140e_180": (-5, 5, 140, 180),
}
NCEP_UWND_REGIONS = {
    "cwp_u_160e_140w": (-5, 5, 160, 220),
}
NCEP_SLP_REGIONS = {
    "tahiti_slp_proxy": (-25, -10, 200, 220),
    "darwin_slp_proxy": (-20, -5, 120, 140),
}


def rows_from_npz(path: Path, dataset: str, variable: str, source_ids: str, regions: dict[str, tuple[float, float, float, float]]):
    import numpy as np

    if not path.exists():
        return []
    data = np.load(path)
    lat = data["lat"]
    lon = data["lon"]
    rows = []
    for season in SEASONS:
        for case in CASES:
            values = data[f"{season}_{case}"].tolist()
            for region, (lat_min, lat_max, lon_min, lon_max) in regions.items():
                rows.append(
                    {
                        "dataset": dataset,
                        "variable": variable,
                        "season": season,
                        "region": region,
                        "case": case,
                        "value": grid_region_mean(values, lat, lon, lat_min, lat_max, lon_min, lon_max),
                        "source_ids": source_ids,
                    }
                )
    return rows


def rows_from_ncep_npz(path: Path):
    import numpy as np

    if not path.exists():
        return []
    data = np.load(path)
    lat = data["lat"]
    lon = data["lon"]
    rows = []
    for season in SEASONS:
        for case in CASES:
            uwnd_values = data[f"uwnd_{season}_{case}"].tolist()
            slp_values = data[f"slp_{season}_{case}"].tolist()
            for region, (lat_min, lat_max, lon_min, lon_max) in NCEP_UWND_REGIONS.items():
                rows.append(
                    {
                        "dataset": "NCEP/NCAR Reanalysis 1 fallback",
                        "variable": "uwnd_sig995",
                        "season": season,
                        "region": region,
                        "case": case,
                        "value": grid_region_mean(
                            uwnd_values, lat, lon, lat_min, lat_max, lon_min, lon_max
                        ),
                        "source_ids": "D4",
                    }
                )
            slp_region_values = {}
            for region, (lat_min, lat_max, lon_min, lon_max) in NCEP_SLP_REGIONS.items():
                value = grid_region_mean(slp_values, lat, lon, lat_min, lat_max, lon_min, lon_max)
                slp_region_values[region] = value
                rows.append(
                    {
                        "dataset": "NCEP/NCAR Reanalysis 1 fallback",
                        "variable": "slp",
                        "season": season,
                        "region": region,
                        "case": case,
                        "value": value,
                        "source_ids": "D4",
                    }
                )
            rows.append(
                {
                    "dataset": "NCEP/NCAR Reanalysis 1 fallback",
                    "variable": "soi_like_slp",
                    "season": season,
                    "region": "tahiti_minus_darwin",
                    "case": case,
                    "value": slp_region_values["tahiti_slp_proxy"]
                    - slp_region_values["darwin_slp_proxy"],
                    "source_ids": "D4",
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Stage A spatial summary CSV from gridded NPZ products.")
    parser.add_argument("--oisst", type=Path, default=OISST)
    parser.add_argument("--gpcp", type=Path, default=GPCP)
    parser.add_argument("--ncep", type=Path, default=NCEP)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = []
    rows.extend(rows_from_npz(args.oisst, "NOAA OISST v2.1", "sst", "D2", OISST_REGIONS))
    rows.extend(rows_from_npz(args.gpcp, "GPCP monthly precipitation", "precip", "D3", GPCP_REGIONS))
    rows.extend(rows_from_ncep_npz(args.ncep))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dataset", "variable", "season", "region", "case", "value", "source_ids"])
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
