#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data/derived/research/seasonal_asynchrony_matrix.csv"
ERA5 = ROOT / "data/derived/research/era5_seasonal_summary.csv"
ERSST = ROOT / "data/derived/research/ersstv5_nino3_seasonal_summary.csv"
OUT = ROOT / "reports/当前数据证据链研究结论.md"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def lookup(rows: list[dict[str, str]], metric: str, season: str) -> dict[str, str]:
    return next(row for row in rows if row["metric"] == metric and row["season"] == season)


def lookup_region(rows: list[dict[str, str]], region: str, season: str) -> dict[str, str]:
    return next(row for row in rows if row["region"] == region and row["season"] == season)


def f(value: str | float) -> str:
    return f"{float(value):.2f}"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> int:
    matrix = read_rows(MATRIX)
    era5 = read_rows(ERA5)
    ersst = read_rows(ERSST)

    seasons = ["AMJ", "JJA"]
    sst_rows = []
    for season in seasons:
        oisst = lookup(matrix, "nino3_sst", season)
        ersst_row = next(row for row in ersst if row["season"] == season)
        sst_rows.append(
            [
                season,
                f(oisst["ratio_to_comparable"]),
                f(ersst_row["ratio_to_comparable"]),
                f(oisst["difference_2023_minus_comparable"]),
                f(ersst_row["difference_2023_minus_comparable"]),
            ]
        )

    atmosphere_rows = []
    for season in seasons:
        u10 = lookup(era5, "era5_u10_cwp_160e_140w", season)
        soi = lookup(era5, "era5_soi_like_tahiti_minus_darwin", season)
        precip = lookup(matrix, "precip_central_pacific_180_140w", season)
        olr = lookup(matrix, "olr_central_pacific_180_140w", season)
        atmosphere_rows.append(
            [
                season,
                f(u10["ratio_to_comparable"]),
                f(soi["ratio_to_comparable"]),
                f(precip["ratio_to_comparable"]),
                f(olr["ratio_to_comparable"]),
            ]
        )

    external_rows = []
    for season in seasons:
        for metric, label in (
            ("sst_tropical_north_atlantic", "Tropical North Atlantic"),
            ("sst_western_pacific_warm_pool", "Western Pacific warm pool"),
            ("sst_maritime_continent", "Maritime Continent"),
            ("sst_tropical_indian_ocean", "Tropical Indian Ocean"),
        ):
            row = lookup(matrix, metric, season)
            external_rows.append([season, label, f(row["difference_2023_minus_comparable"])])

    lines = [
        "# 当前数据证据链研究结论",
        "",
        "生成日期：2026-05-24。",
        "",
        "## 一句话结论",
        "",
        "在当前已经下载和处理的数据中，2023 年 AMJ/JJA 的 Nino-3 SST 强于历史强 El Nino 可比事件，但 ERA5 u10、ERA5 SOI-like SLP、GPCP 降水和 CPC Blended OLR 对流响应均明显偏弱。因此，当前资料已经可以支撑“发展期海温先强、大气风压和对流未同步响应”的主线。",
        "",
        "## 1. 海温信号：发展季已经足够强",
        "",
        md_table(
            ["季节", "OISST Nino-3 2023/可比", "ERSSTv5 Nino-3 2023/可比", "OISST 差值 (deg C)", "ERSSTv5 差值 (deg C)"],
            sst_rows,
        ),
        "",
        "OISST 主资料显示 AMJ/JJA Nino-3 分别为历史可比强事件的 1.41 和 1.22 倍。ERSSTv5 长记录产品也给出同号结论，说明发展季强海温不是 OISST 时段选择造成的假象。",
        "",
        "## 2. 大气响应：ERA5 确认风压响应弱",
        "",
        md_table(
            ["季节", "ERA5 CWP u10 2023/可比", "ERA5 SOI-like 2023/可比", "GPCP CP precip 2023/可比", "CPC OLR CP 2023/可比"],
            atmosphere_rows,
        ),
        "",
        "ERA5 single-level 已经替代 NCEP fallback 的核心风压结论：AMJ 的 CWP u10 响应为反相，JJA 近乎为零；SOI-like SLP 只有约 0.29 和 0.34 倍。GPCP 与 OLR 进一步说明，对流/降水也没有跟随强 SST 同步增强。注意 OLR 为负值代表增强对流，2023/可比比值越小，表示增强对流越弱。",
        "",
        "## 3. 外海盆背景：发展季暖背景异常强",
        "",
        md_table(["季节", "区域", "2023-可比 SST 差值 (deg C)"], external_rows),
        "",
        "AMJ/JJA 同时存在热带北大西洋、西太暖池、海陆热带区和热带印度洋偏暖。这些区域不是当前结果中的因果证明，但它们提供了后续机制分析的重点背景：外海盆和暖池加热可能改变 Walker circulation 背景态，削弱太平洋暖 SST 对中西太平洋风压和对流的典型响应。",
        "",
        "## 4. 相较 Peng et al. 2025 的新增点",
        "",
        "Peng et al. 2025 证明 2023/24 是海洋动力生成的强暖事件，并指出风场/SOI 响应偏弱。当前工作在其基础上新增三点：",
        "",
        "1. 把事件平均结论拆到 AMJ/JJA/SON/DJF，指出 AMJ/JJA 是最关键的发展期不同步窗口。",
        "2. 用 ERA5 u10/SLP、GPCP 和 OLR 组成独立观测链，证明弱响应不只出现在单一资料或复现图中。",
        "3. 把外海盆 SST 与太平洋耦合量放入同一季节矩阵，为后续机制分析准备可检验假设。",
        "",
        "## 5. 当前仍不能过度宣称的部分",
        "",
        "- ERA5 pressure-level u850、200 hPa divergence 和 500 hPa omega 还没有下载成功，因此 Walker circulation 只能作为待验证机制，不能作为已完成结论。",
        "- 外海盆暖异常目前是候选机制背景，不是因果归因。要做因果归因，需要 AGCM、pacemaker 实验或更严格的 partial regression / causal diagnostic design。",
        "- OLR 可比事件目前使用 1997/98 与 2015/16，不含 1982/83；正式图注需要说明这一点。",
        "",
        "## 6. 下一步工作建议",
        "",
        "短期先做两件事：第一，把 AMJ/JJA 的现有图和 ERA5 u10/SLP 结果整合成正式研究图；第二，围绕 July 2023 和 January 2024 做关键月份机制诊断。ERA5 pressure-level 可在 CDS 队列较空时继续补，但不应阻塞当前主线写作。",
        "",
        "## 数据来源索引",
        "",
        "- D2: NOAA OISST v2.1, https://www.ncei.noaa.gov/products/optimum-interpolation-sst",
        "- D3: GPCP monthly precipitation, https://psl.noaa.gov/data/gridded/data.gpcp.html",
        "- D5: ERA5 monthly averaged data on single levels, https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means",
        "- D8: CPC Blended OLR, https://psl.noaa.gov/data/gridded/data.cpc_blended_olr-1deg.html",
        "- D9: ERSSTv5, https://www.ncei.noaa.gov/products/extended-reconstructed-sst",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
