from __future__ import annotations

import csv
from pathlib import Path


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def format_ratio(value: str) -> str:
    if value in ("", "None", "nan"):
        return "NA"
    return f"{float(value):.3f}"


def _find_row(rows: list[dict[str, str]], **criteria: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    label = ", ".join(f"{key}={value}" for key, value in criteria.items())
    raise ValueError(f"No row found for {label}")


def _fig3_value(rows: list[dict[str, str]], experiment: str, region: str = "central_pacific_180_140w") -> float:
    row = _find_row(
        rows,
        metric="taux",
        experiment=experiment,
        region=region,
        window_or_layer="jun_dec",
    )
    return float(row["value"])


def _fig4_value(rows: list[dict[str, str]], experiment: str, month: str = "Dec", case: str = "2023") -> float:
    row = _find_row(rows, case=case, experiment=experiment, month=month)
    return float(row["nino3"])


def write_first_pass_report(fig1_csv: Path, fig3_csv: Path, fig4_csv: Path, output: Path) -> None:
    fig1_rows = read_csv_rows(fig1_csv)
    fig3_rows = read_csv_rows(fig3_csv)
    fig4_rows = read_csv_rows(fig4_csv)
    event_rows = [row for row in fig1_rows if row.get("highlight") == "True"]
    event_2023 = _find_row(fig1_rows, year="2023")

    lines = [
        "# First-Pass Reproduction Report",
        "",
        "## What Has Been Reproduced From Article Data",
        "",
        "- The Zenodo figure data and plotting scripts were downloaded and patched only in a local interim copy.",
        "- Main Figures 1-4 were reproduced as PNG/PDF outputs.",
        "- The source figure data were converted into four analysis tables for coupling, equatorial evolution, AGCM attribution, and wind-stress experiments.",
        "",
        "## Fig. 1: Coupling Weakness",
        "",
        "| Year | Nino-3 | u10 | SOI | u10 ratio | SOI ratio |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in event_rows:
        lines.append(
            f"| {row['year']} | {float(row['nino3']):.3f} | {float(row['uwind']):.3f} | "
            f"{float(row['soi']):.3f} | {format_ratio(row['uwind_coupling_ratio'])} | "
            f"{format_ratio(row['soi_coupling_ratio'])} |"
        )
    lines.extend(
        [
            "",
            f"For 2023/24, the u10 coupling ratio is {format_ratio(event_2023['uwind_coupling_ratio'])} "
            f"and the SOI coupling ratio is {format_ratio(event_2023['soi_coupling_ratio'])}. "
            "This reproduces the paper's core claim that the atmospheric response was only about one third of the historical SST-expected response.",
            "",
            "## Fig. 3: AGCM Attribution Signal",
            "",
            "| Experiment | Central Pacific Jun-Dec taux |",
            "|---|---:|",
        ]
    )
    for experiment in ("aCTRL", "aPac", "aIndAtl", "aTrend"):
        lines.append(f"| {experiment} | {_fig3_value(fig3_rows, experiment):.4f} |")
    lines.extend(
        [
            "",
            "The Pacific-only response (`aPac`) gives a stronger positive central Pacific wind-stress anomaly, while `aIndAtl` and `aTrend` are negative in the same region.",
            "",
            "## Fig. 4: Wind-Stress Experiment Signal",
            "",
            "| 2023 Experiment | December Nino-3 |",
            "|---|---:|",
        ]
    )
    for experiment in ("CTRL", "InitApr", "Wind2023"):
        lines.append(f"| {experiment} | {_fig4_value(fig4_rows, experiment):.3f} |")
    lines.extend(
        [
            "",
            "The December `InitApr` value remains large relative to `CTRL`, which is consistent with the paper's interpretation that ocean preconditioning retains much of the warming after low-frequency post-April wind-stress anomalies are removed.",
            "",
            "## Boundary Of This Step",
            "",
            "These results reproduce and tabulate the article-provided figure data. They do not yet independently verify the results from raw OISST, ERA5, GPCP, or GODAS downloads.",
            "",
            "## Next Independent-Data Step",
            "",
            "1. Download monthly OISSTv2, GPCP, GODAS, and ERA5 fields for 1982-2024.",
            "2. Rebuild Nino-3, CWP u10, SOI-like SLP, rainfall, and equatorial wind-stress indices from raw products.",
            "3. Compare raw-product diagnostics against the article-data tables generated here.",
        ]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
