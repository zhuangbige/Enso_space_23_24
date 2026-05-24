#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _corr(a: list[float], b: list[float]) -> float:
    amean = sum(a) / len(a)
    bmean = sum(b) / len(b)
    numerator = sum((x - amean) * (y - bmean) for x, y in zip(a, b))
    denominator = math.sqrt(sum((x - amean) ** 2 for x in a) * sum((y - bmean) ** 2 for y in b))
    return numerator / denominator


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare NCEP atmospheric proxy indices against Fig. 1 u10/SOI data.")
    parser.add_argument("--fig1", type=Path, default=Path("data/derived/peng2025_repro/tables/fig1_event_coupling.csv"))
    parser.add_argument("--ncep", type=Path, default=Path("data/derived/raw_validation/ncep_atmosphere_jun_jan.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/raw_validation/ncep_vs_fig1_atmosphere.csv"))
    args = parser.parse_args()

    fig1 = {int(row["year"]): row for row in read_rows(args.fig1)}
    ncep = read_rows(args.ncep)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["year", "fig1_uwind", "ncep_cwp_u", "fig1_soi", "ncep_soi_like"])
        for row in ncep:
            year = int(row["event_year"])
            if year not in fig1:
                continue
            writer.writerow(
                [
                    year,
                    fig1[year]["uwind"],
                    row["cwp_u_sig995"],
                    fig1[year]["soi"],
                    row["soi_like_tahiti_minus_darwin"],
                ]
            )
    rows = read_rows(args.output)
    fig1_u = [float(row["fig1_uwind"]) for row in rows]
    ncep_u = [float(row["ncep_cwp_u"]) for row in rows]
    fig1_soi = [float(row["fig1_soi"]) for row in rows]
    ncep_soi = [float(row["ncep_soi_like"]) for row in rows]
    print(args.output)
    print(f"u_correlation={_corr(fig1_u, ncep_u):.4f}")
    print(f"soi_correlation={_corr(fig1_soi, ncep_soi):.4f}")
    for row in rows:
        if int(row["year"]) in {1982, 1997, 2015, 2023}:
            print(
                f"{row['year']}: fig1_u={float(row['fig1_uwind']):.3f}, ncep_u={float(row['ncep_cwp_u']):.3f}, "
                f"fig1_soi={float(row['fig1_soi']):.3f}, ncep_soi_like={float(row['ncep_soi_like']):.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
