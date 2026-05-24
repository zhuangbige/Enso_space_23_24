#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import monthly_anomalies, seasonal_mean_by_months  # noqa: E402


SEASONS = {
    "AMJ": (4, 5, 6),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
    "DJF": (12, 13, 14),
}

COMPARABLE_YEARS = (1982, 1997, 2015)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _monthly_records(path: Path, value_key: str) -> list[dict]:
    rows = read_rows(path)
    if "anomaly" in rows[0]:
        return [{"year": int(row["year"]), "month": int(row["month"]), "anomaly": float(row["anomaly"])} for row in rows]
    records = [{"year": int(row["year"]), "month": int(row["month"]), "value": float(row[value_key])} for row in rows]
    return monthly_anomalies(records, 1982, 2022)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build first seasonal comparison table for the research phase.")
    parser.add_argument("--oisst-monthly", type=Path, default=Path("data/interim/raw_validation/oisst_nino3_monthly.csv"))
    parser.add_argument("--ncep-seasonal", type=Path, default=Path("data/derived/raw_validation/ncep_atmosphere_jun_jan.csv"))
    parser.add_argument("--ncep-monthly", type=Path, default=Path("data/interim/raw_validation/ncep_atmosphere_monthly.csv"))
    parser.add_argument("--gpcp-summary", type=Path, default=Path("data/derived/raw_validation/gpcp_equatorial_summary.csv"))
    parser.add_argument("--external-basin-summary", type=Path, default=Path("data/derived/research/external_basin_seasonal_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/research/seasonal_decoupling_first_pass.csv"))
    args = parser.parse_args()

    oisst = _monthly_records(args.oisst_monthly, "value")
    ncep = read_rows(args.ncep_seasonal)
    ncep_monthly = read_rows(args.ncep_monthly) if args.ncep_monthly.exists() else []
    gpcp = read_rows(args.gpcp_summary)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "season", "value_2023", "value_comparable", "difference_2023_minus_comparable", "notes"])

        for season, months in SEASONS.items():
            value_2023 = seasonal_mean_by_months(oisst, 2023, months)
            comparable = mean([seasonal_mean_by_months(oisst, year, months) for year in COMPARABLE_YEARS])
            writer.writerow(["nino3_sst_oisst", season, value_2023, comparable, value_2023 - comparable, "Raw OISST Nino-3 seasonal anomaly"])

        # NCEP table currently has Jun-Jan seasonal values only; keep it in the
        # research table as an atmospheric annual-season anchor.
        ncep_lookup = {int(row["event_year"]): row for row in ncep}
        for metric, key in (("cwp_u_ncep_sig995", "cwp_u_sig995"), ("soi_like_ncep", "soi_like_tahiti_minus_darwin")):
            value_2023 = float(ncep_lookup[2023][key])
            comparable = mean([float(ncep_lookup[year][key]) for year in COMPARABLE_YEARS])
            writer.writerow([metric, "Jun-Jan", value_2023, comparable, value_2023 - comparable, "NCEP proxy; seasonal decomposition pending monthly atmospheric cache"])

        if ncep_monthly:
            ncep_records = {
                "cwp_u_ncep_sig995": [
                    {"year": int(row["year"]), "month": int(row["month"]), "anomaly": float(row["cwp_u_sig995"])}
                    for row in ncep_monthly
                ],
                "soi_like_ncep": [
                    {"year": int(row["year"]), "month": int(row["month"]), "anomaly": float(row["soi_like_tahiti_minus_darwin"])}
                    for row in ncep_monthly
                ],
            }
            for metric, records in ncep_records.items():
                for season, months in SEASONS.items():
                    value_2023 = seasonal_mean_by_months(records, 2023, months)
                    comparable = mean([seasonal_mean_by_months(records, year, months) for year in COMPARABLE_YEARS])
                    writer.writerow([metric, season, value_2023, comparable, value_2023 - comparable, "NCEP monthly proxy seasonal decomposition"])

        for region in ("central_pacific_180_140w", "eastern_pacific_140w_100w", "full_tropical_pacific_120e_80w"):
            for window in ("jun_dec", "jan_apr_next"):
                row_2023 = next(row for row in gpcp if row["case"] == "2023" and row["region"] == region and row["window"] == window)
                row_comp = next(row for row in gpcp if row["case"] == "comparable" and row["region"] == region and row["window"] == window)
                value_2023 = float(row_2023["precip_anomaly"])
                comparable = float(row_comp["precip_anomaly"])
                writer.writerow([f"gpcp_precip_{region}", window, value_2023, comparable, value_2023 - comparable, "Raw GPCP equatorial Pacific precipitation"])

        if args.external_basin_summary.exists():
            for row in read_rows(args.external_basin_summary):
                if not row.get("value_2023"):
                    continue
                writer.writerow(
                    [
                        f"oisst_sst_{row['region']}",
                        row["season"],
                        row["value_2023"],
                        row["value_comparable"],
                        row["difference_2023_minus_comparable"],
                        "Raw OISST external-basin SST anomaly",
                    ]
                )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
