"""Write a Chinese report for the seasonal asynchronous-coupling stage."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data/derived/research/seasonal_asynchrony_matrix.csv"
FIGURE = ROOT / "data/derived/research/seasonal_asynchrony_figure.png"
OUT = ROOT / "reports/季节不等时响应研究报告.md"
SEASONS = ["AMJ", "JJA", "SON", "DJF"]


def _markdown_table(df: pd.DataFrame) -> str:
    columns = list(df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in df.to_dict("records"):
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.3f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    df = pd.read_csv(MATRIX)
    df = df[df["season"].isin(SEASONS)].copy()
    df["metric"] = df["metric"].replace(
        {
            "nino3_sst": "Nino-3 SST",
            "cwp_u": "CWP low-level u",
            "soi_like": "SOI-like SLP",
            "sst_maritime_continent": "Maritime Continent SST",
            "sst_tropical_indian_ocean": "Tropical Indian Ocean SST",
            "sst_tropical_north_atlantic": "Tropical North Atlantic SST",
            "sst_western_pacific_warm_pool": "W. Pacific warm pool SST",
        }
    )
    compact = df[
        [
            "season",
            "metric",
            "value_2023",
            "value_comparable",
            "difference_2023_minus_comparable",
            "ratio_to_comparable",
            "response_efficiency",
            "source_ids",
        ]
    ]

    lines = [
        "# 2023/24 强厄尔尼诺季节不等时响应研究报告",
        "",
        "生成日期：2026-05-23。",
        "",
        "## 目前是否仍在复现",
        "",
        "目前已经不只是复现。复现 Peng et al. 2025 的 Fig. 1-4 和关键数值仍然是基线，但当前工作已经进入新研究的第一层：把 2023/24 事件拆成 AMJ、JJA、SON、DJF 四个季节，比较海温、低层风、SOI-like 气压梯度与外海盆 SST 是否同步响应。",
        "",
        "## 今天新增了什么",
        "",
        "- 将 Zhao, Li & Pan 2025 的 July 2023 wind-SST decoupling 和 Yang & Li 2025 的 January 2024 easterly decoupling 纳入引用与方法记录。",
        "- 建立 `seasonal_asynchrony_matrix.csv`，把 Nino-3 SST、CWP 低层纬向风、SOI-like SLP 和外海盆 SST 放进同一个 AMJ/JJA/SON/DJF 框架。",
        "- 生成新图 `seasonal_asynchrony_figure.png`，左图显示太平洋耦合量的 2023/可比强事件比值，右图显示外海盆 SST 的 2023-可比强事件差值。",
        "- 明确降水资料目前已有 Jun-Dec 和 Jan-Apr(next) 证据，但还没有完全拆成 AMJ/JJA/SON/DJF；下一步应补季节化降水/OLR。",
        "",
        f"![Seasonal asynchrony figure]({FIGURE})",
        "",
        "## 初步科学判断",
        "",
        "AMJ 和 JJA 是最值得作为文章突破口的季节。Nino-3 SST 在 AMJ/JJA 相对历史强事件分别达到 1.41 和 1.22 倍，但 CWP 低层风响应分别为 -0.43 和 -0.14 倍，说明早期不是简单的“响应偏弱”，而是局地风场对暖海温信号出现了反相或近乎失效的同步响应。",
        "",
        "SOI-like SLP 的同步效率也偏低，AMJ/JJA 只有约 0.22 和 0.28。与此同时，Tropical North Atlantic SST 在 AMJ/JJA 比可比强事件高出 1.11 和 1.35 deg C，Maritime Continent 与 western Pacific warm pool 也明显偏暖。这支持一个更具体的假设：2023 年发展季外海盆和暖池背景加热削弱或抵消了太平洋暖 SST 本应触发的 Walker/Bjerknes 风压响应。",
        "",
        "## 季节矩阵",
        "",
        _markdown_table(compact),
        "",
        "## 数据与文献来源",
        "",
        "- L1: Peng et al. 2025, Nature Geoscience, https://www.nature.com/articles/s41561-025-01700-9",
        "- L7: Zhao, Li & Pan 2025, Climate Dynamics, https://link.springer.com/article/10.1007/s00382-025-07625-8",
        "- L8: Yang & Li 2025, Journal of Climate, https://journals.ametsoc.org/view/journals/clim/38/23/JCLI-D-24-0689.1.xml",
        "- D2: NOAA OISST v2.1, https://www.ncei.noaa.gov/products/optimum-interpolation-sst",
        "- D3: GPCP monthly precipitation, https://psl.noaa.gov/data/gridded/data.gpcp.html",
        "- D4: NCEP/NCAR Reanalysis 1, https://www.psl.noaa.gov/data/reanalysis/",
        "",
        "## 下一步",
        "",
        "1. 将 GPCP 降水拆成 AMJ/JJA/SON/DJF，并并入矩阵。",
        "2. 下载或接入 2023/24 可用 OLR，独立验证对流响应。",
        "3. 获取 ERA5 u850、SLP 和 200 hPa velocity potential，替换当前 NCEP fallback 风压诊断。",
        "4. 做 July 2023 与 January 2024 关键月份机制图，分别对应 Zhao et al. 和 Yang & Li 的方法，但服务于本项目的四季不等时主线。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
