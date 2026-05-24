#!/usr/bin/env python3
"""Build a traceable inventory for the current El Nino data chain."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ChainItem:
    step: str
    layer: str
    product: str
    local_path: str
    source_ids: str
    upstream_scripts: str
    role: str
    status_if_missing: str


CHAIN_ITEMS = (
    ChainItem(
        "01",
        "source-paper reproduction",
        "Peng et al. 2025 raw Zenodo/source archive manifest",
        "data/raw/peng2025_zenodo/manifest.csv",
        "D1,L1",
        "scripts/fetch_peng2025_zenodo.py",
        "Documents the source-paper files used to reproduce Fig. 1-4.",
        "missing raw source archive; rerun manifest/download step",
    ),
    ChainItem(
        "02",
        "source-paper reproduction",
        "Reproduced Peng et al. 2025 Fig. 1-4",
        "data/derived/peng2025_repro/figures/Fig1.png",
        "D1,L1",
        "scripts/run_peng2025_reproduction.py",
        "Visual baseline for the published claim: strong Nino-3 warming with weak atmospheric coupling.",
        "missing figure reproduction; rerun reproduction scripts",
    ),
    ChainItem(
        "03",
        "source-paper reproduction",
        "Source-paper Fig. 1 coupling table",
        "data/derived/peng2025_repro/tables/fig1_event_coupling.csv",
        "D1,L1",
        "scripts/extract_fig1_event_table.py",
        "Extracted Nino-3, wind, SOI, and coupling-ratio values from the reproduced paper figure.",
        "missing extracted table; rerun table extraction",
    ),
    ChainItem(
        "04",
        "independent validation",
        "OISST monthly Nino-3 index",
        "data/interim/raw_validation/oisst_nino3_monthly.csv",
        "D2",
        "scripts/extract_oisst_nino3_opendap.py",
        "Independent monthly SST backbone for seasonal Nino-3 anomalies.",
        "missing OISST cache; rerun OPeNDAP extraction when network is available",
    ),
    ChainItem(
        "05",
        "independent validation",
        "GPCP monthly equatorial precipitation anomalies",
        "data/interim/raw_validation/gpcp_equatorial_monthly.csv",
        "D3",
        "scripts/extract_gpcp_equatorial_monthly_opendap.py",
        "Independent precipitation/convection response check, split into Pacific longitude bands.",
        "missing GPCP monthly cache; rerun OPeNDAP extraction when network is available",
    ),
    ChainItem(
        "06",
        "independent validation",
        "NCEP monthly low-level wind and SOI-like pressure proxy",
        "data/interim/raw_validation/ncep_atmosphere_monthly.csv",
        "D4",
        "scripts/extract_ncep_atmosphere_opendap.py",
        "Fallback atmospheric backbone for CWP low-level wind and Tahiti-minus-Darwin SLP proxy.",
        "missing NCEP cache; rerun OPeNDAP extraction or replace with ERA5",
    ),
    ChainItem(
        "07",
        "seasonal diagnosis",
        "Seasonal SST-wind-SLP first-pass table",
        "data/derived/research/seasonal_decoupling_first_pass.csv",
        "D2,D3,D4",
        "scripts/build_seasonal_research_table.py",
        "AMJ/JJA/SON/DJF comparison of 2023/24 with 1982/83, 1997/98, and 2015/16.",
        "missing seasonal table; rebuild after monthly caches exist",
    ),
    ChainItem(
        "08",
        "seasonal diagnosis",
        "Seasonal GPCP precipitation summary",
        "data/derived/research/gpcp_precip_seasonal_summary.csv",
        "D3",
        "scripts/build_gpcp_seasonal_summary.py",
        "Adds AMJ/JJA/SON/DJF precipitation response to the coupling matrix.",
        "missing GPCP seasonal table; rebuild after GPCP monthly cache exists",
    ),
    ChainItem(
        "09",
        "seasonal diagnosis",
        "External-basin OISST seasonal summary",
        "data/derived/research/external_basin_seasonal_summary.csv",
        "D2",
        "scripts/extract_oisst_external_basin_indices.py; scripts/build_external_basin_summary.py",
        "Quantifies TNA, tropical Indian Ocean, Maritime Continent, and western Pacific warm-pool background SST.",
        "missing external-basin table; rerun OISST external-basin scripts",
    ),
    ChainItem(
        "10",
        "seasonal diagnosis",
        "Asynchronous coupling efficiency table",
        "data/derived/research/asynchronous_coupling_efficiency.csv",
        "D2,D3,D4",
        "scripts/build_asynchronous_coupling_table.py",
        "Normalizes atmospheric response ratios by Nino-3 SST strength ratios.",
        "missing efficiency table; rebuild after seasonal first-pass table exists",
    ),
    ChainItem(
        "11",
        "seasonal diagnosis",
        "Seasonal asynchrony matrix",
        "data/derived/research/seasonal_asynchrony_matrix.csv",
        "D2,D3,D4",
        "scripts/build_seasonal_asynchrony_matrix.py",
        "Single table joining SST, wind, SLP, precipitation, and external-basin diagnostics.",
        "missing matrix; rebuild after seasonal component tables exist",
    ),
    ChainItem(
        "12",
        "spatial diagnosis",
        "AMJ/JJA OISST spatial anomaly cache",
        "data/interim/raw_validation/oisst_spatial_amj_jja.npz",
        "D2",
        "scripts/extract_stage_a_oisst_spatial_opendap.py",
        "Gridded SST evidence for Pacific and external-basin anomaly placement.",
        "missing OISST spatial cache; rerun spatial extraction",
    ),
    ChainItem(
        "13",
        "spatial diagnosis",
        "AMJ/JJA GPCP spatial anomaly cache",
        "data/interim/raw_validation/gpcp_spatial_amj_jja.npz",
        "D3",
        "scripts/extract_stage_a_gpcp_spatial_opendap.py",
        "Gridded precipitation evidence for suppressed tropical Pacific rainfall response.",
        "missing GPCP spatial cache; rerun spatial extraction",
    ),
    ChainItem(
        "14",
        "spatial diagnosis",
        "AMJ/JJA NCEP wind/SLP spatial anomaly cache",
        "data/interim/raw_validation/ncep_spatial_amj_jja.npz",
        "D4",
        "scripts/extract_stage_a_ncep_spatial_opendap.py",
        "Fallback gridded wind/pressure evidence before ERA5 is available.",
        "missing NCEP spatial cache; rerun spatial extraction or replace with ERA5",
    ),
    ChainItem(
        "15",
        "spatial diagnosis",
        "Stage A spatial regional summary",
        "data/derived/research/stage_a_spatial_summary.csv",
        "D2,D3,D4",
        "scripts/build_stage_a_spatial_summary.py",
        "Regional means from AMJ/JJA spatial caches for direct comparison with the index chain.",
        "missing spatial summary; rebuild after spatial caches exist",
    ),
    ChainItem(
        "16",
        "spatial diagnosis",
        "Stage A SST and precipitation quick-look map",
        "data/derived/research/stage_a_amj_jja_sst_precip.png",
        "D2,D3",
        "scripts/plot_stage_a_spatial_diagnostics.py",
        "Current spatial figure for strong SST but weak rainfall response.",
        "missing quick-look map; rerun plotting script",
    ),
    ChainItem(
        "17",
        "spatial diagnosis",
        "Stage A NCEP wind and SLP quick-look map",
        "data/derived/research/stage_a_amj_jja_ncep_wind_slp.png",
        "D4",
        "scripts/plot_stage_a_ncep_spatial_diagnostics.py",
        "Current fallback spatial figure for weak low-level wind and pressure-gradient response.",
        "missing quick-look map; rerun plotting script",
    ),
    ChainItem(
        "18",
        "reporting",
        "Current Chinese stage summary",
        "reports/当前数据分析阶段总结.md",
        "D1,D2,D3,D4,L1,L2,L3,L7,L8",
        "manual synthesis from derived products",
        "Explains what is reproduced, what is original, and what remains pending.",
        "missing report; regenerate stage summary",
    ),
    ChainItem(
        "19",
        "paper-grade replacement",
        "ERA5 single-level u10 and SLP diagnostics",
        "data/derived/research/era5_seasonal_summary.csv",
        "D5",
        "scripts/fetch_era5_monthly_cds.py; scripts/build_era5_seasonal_summary.py",
        "Replaces NCEP fallback for near-surface wind and SOI-like SLP diagnostics.",
        "pending: needs Copernicus CDS credentials or ERA5 single-level download",
    ),
    ChainItem(
        "22",
        "paper-grade replacement",
        "ERA5 pressure-level u850 and Walker-circulation diagnostics",
        "data/raw/era5/era5_monthly_u850_tropics_1982_2024.nc",
        "D6",
        "scripts/fetch_era5_monthly_cds.py --request u850; scripts/fetch_era5_monthly_cds.py --request walker; scripts/build_era5_seasonal_summary.py",
        "Adds u850, 200 hPa divergence, and 500 hPa omega for final Walker-circulation diagnosis.",
        "pending: CDS pressure-level queue was slow; rerun smaller u850 and walker requests later",
    ),
    ChainItem(
        "20",
        "paper-grade replacement",
        "Recent OLR convection diagnostics",
        "data/interim/raw_validation/olr_monthly.csv",
        "D8",
        "scripts/extract_cpc_olr_monthly_opendap.py",
        "Independent convection proxy for 2023/24 beyond GPCP precipitation.",
        "pending: open-data extraction still to be added/run",
    ),
    ChainItem(
        "21",
        "long-record robustness",
        "ERSSTv5 long-record Nino indices",
        "data/interim/raw_validation/ersstv5_nino3_monthly.csv",
        "D9",
        "scripts/extract_ersstv5_nino3_opendap.py",
        "Tests whether the OISST post-1981 sample changes the historical comparison.",
        "pending: open-data extraction still to be added/run",
    ),
)


def _file_metadata(path: Path) -> tuple[str, str, str]:
    if path.is_dir():
        files = [child for child in path.rglob("*") if child.is_file()]
        return ("present" if files else "missing", str(len(files)), "files")
    if not path.exists():
        return "missing", "", ""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            rows = sum(1 for _ in reader)
        return "present", str(rows), ",".join(header)
    if suffix == ".npz":
        import numpy as np

        data = np.load(path)
        return "present", str(len(data.files)), ",".join(data.files[:10])
    size_kb = path.stat().st_size / 1024
    return "present", f"{size_kb:.1f}", "KB"


def build_inventory(root: Path = ROOT) -> list[dict[str, str]]:
    rows = []
    for item in CHAIN_ITEMS:
        path = root / item.local_path
        status, count, fields = _file_metadata(path)
        rows.append(
            {
                "step": item.step,
                "layer": item.layer,
                "product": item.product,
                "status": status,
                "local_path": item.local_path,
                "count_or_size": count,
                "fields_or_keys": fields,
                "source_ids": item.source_ids,
                "upstream_scripts": item.upstream_scripts,
                "role": item.role,
                "next_action_if_missing": "" if status == "present" else item.status_if_missing,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "step",
        "layer",
        "product",
        "status",
        "local_path",
        "count_or_size",
        "fields_or_keys",
        "source_ids",
        "upstream_scripts",
        "role",
        "next_action_if_missing",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _md_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[column]).replace("\n", " ") for column in columns) + " |")
    return "\n".join(lines)


def write_report(path: Path, rows: list[dict[str, str]], csv_path: Path) -> None:
    present = [row for row in rows if row["status"] == "present"]
    missing = [row for row in rows if row["status"] != "present"]
    completed_layers = sorted({row["layer"] for row in present})
    pending_layers = sorted({row["layer"] for row in missing})
    pending_products = "、".join(row["product"] for row in missing) if missing else "无"
    lines = [
        "# 2023/24 El Nino 数据链总账",
        "",
        "生成日期：2026-05-24。",
        "",
        "## 当前结论",
        "",
        f"当前链条已完成 {len(present)}/{len(rows)} 个节点。原文复现、独立 SST/降水/风压验证、AMJ/JJA 空间诊断、季节不等时矩阵、ERA5 u10/SLP、OLR 对流代理、ERSSTv5 长记录稳健性和中文阶段报告已经闭合；仍待补的节点是：{pending_products}。",
        "",
        "这意味着现在已经可以支撑一个阶段性研究汇报：2023 年发展季 Nino-3 SST 强于历史可比强事件，但 ERA5 u10、ERA5 SOI-like SLP、GPCP 降水和 CPC Blended OLR 对流代理都没有同步增强。最终论文写作前，还应继续补 ERA5 pressure-level 的 u850 与 Walker circulation 诊断。",
        "",
        "## 已闭合层级",
        "",
        ", ".join(completed_layers),
        "",
        "## 待补层级",
        "",
        ", ".join(pending_layers) if pending_layers else "无。",
        "",
        "## 数据链节点",
        "",
        _md_table(rows, ["step", "layer", "product", "status", "source_ids", "local_path"]),
        "",
        "## 待补动作",
        "",
    ]
    if missing:
        lines.append(_md_table(missing, ["step", "product", "source_ids", "next_action_if_missing"]))
    else:
        lines.append("所有节点均已存在。")
    lines.extend(
        [
            "",
            "## 使用方式",
            "",
            f"机器可读总账见 `{csv_path}`。报告或 PPT 中每个图表应引用该表中的 `source_ids`，并到 `docs/data_source_log.md` 查对应文献和数据网址。",
            "",
            "## 当前论文级缺口解释",
            "",
            "- ERA5：single-level u10/SLP 已接入并替代 NCEP fallback 的核心风压结论；pressure-level u850、200 hPa divergence 和 500 hPa omega 仍需在 CDS 队列较空时继续下载。",
            "- OLR：CPC Blended OLR 已接入。需要注意该产品用于本文比较时只覆盖 1997/98、2015/16 与 2023/24，不能包含 1982/83。",
            "- ERSSTv5：长记录 Nino-3 稳健性已接入。结果用于检查 OISST 1981 年以后样本是否限制历史强事件比较。",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a traceable inventory for the current data chain.")
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=ROOT / "data/derived/research/data_chain_inventory.csv",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=ROOT / "reports/数据链总账.md",
    )
    args = parser.parse_args()
    rows = build_inventory()
    write_csv(args.csv_output, rows)
    write_report(args.report_output, rows, args.csv_output.relative_to(ROOT))
    print(args.csv_output)
    print(args.report_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
