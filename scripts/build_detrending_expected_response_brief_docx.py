#!/usr/bin/env python3
"""Build concise bilingual DOCX reports on detrending and expectation lines."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path("/Users/daiyue/Documents/Maryland")
OUT_DIR = ROOT / "outputs/research_2026/reports"

FIG = {
    "expectation": ROOT / "outputs/research_2026/figures/fig4_2026_era5_expected_response_lines.png",
    "fep_raw": ROOT / "outputs/research_2026/figures/fig1_2026_sst_fep_residual.png",
    "fep_detrended": ROOT / "outputs/research_2026/figures_detrended/fig1_2026_sst_fep_residual.png",
    "spatial_raw": ROOT / "outputs/research_2026/spatial_meteorology/fig4_2026_sst_precip_spatial.png",
    "spatial_detrended": ROOT / "outputs/research_2026/spatial_meteorology_detrended/fig4_2026_sst_precip_spatial.png",
    "event_sst": ROOT / "outputs/research_2026/figures/fig5_2026_event_aligned_sst_trajectory.png",
    "event_atm": ROOT / "outputs/research_2026/figures/fig6_2026_event_aligned_atmosphere_trajectory.png",
    "event_matrix": ROOT / "outputs/research_2026/figures/fig7_2026_event_apr_may_summary_matrix.png",
    "event_spatial_sst_precip": ROOT / "outputs/research_2026/figures/fig13_event_aligned_sst_precip_spatial_apr_may.png",
    "event_spatial_era5": ROOT / "outputs/research_2026/figures/fig14_event_aligned_era5_u10_mslp_spatial_apr_may.png",
    "jiang_fig4": ROOT / "outputs/research_2026/figures/fig12_grl_fig4_same_sources_extended_to_2026.png",
}

DATA = {
    "monthly_raw": ROOT / "data/interim/research_2026/current_2026_monthly_indices.csv",
    "monthly_detrended": ROOT / "data/interim/research_2026/current_2026_monthly_indices_detrended.csv",
    "fep_raw": ROOT / "data/derived/research_2026/current_2026_fep_residual.csv",
    "fep_detrended": ROOT / "data/derived/research_2026/current_2026_fep_residual_detrended.csv",
    "expected_line": ROOT / "data/derived/peng2025_repro/tables/fig1_event_coupling.csv",
    "era5_raw": ROOT / "data/derived/research_2026/current_2026_era5_region_summary.csv",
    "era5_detrended": ROOT / "data/derived/research_2026/current_2026_era5_region_summary_detrended.csv",
    "event_comparison": ROOT / "data/derived/research_2026/event_aligned_2026_comparison.csv",
    "event_spatial_summary": ROOT / "data/derived/research_2026/event_aligned_spatial_apr_may_summary.csv",
    "oisst_spatial_apr": ROOT / "data/interim/research_2026/oisst_event_spatial_tropics_apr_1982_2026_1deg.nc",
    "oisst_spatial_may": ROOT / "data/interim/research_2026/oisst_event_spatial_tropics_may_1982_2026_1deg.nc",
    "gpcp_spatial": ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc",
    "oras5_d20": ROOT / "data/derived/research_2026/oras5_d20_annual_mean_removed_10yr.csv",
    "jiang_corr": ROOT / "data/derived/research_2026/grl_fig4_same_source_leadlag_corr_ersstv5_trailing15.csv",
}

COLORS = {
    "ink": "1C1B18",
    "blue": "2E74B5",
    "dark_blue": "1F4D78",
    "muted": "5B5A55",
    "line": "D8D1C2",
    "light_blue": "E8EEF5",
    "light_teal": "E7F1EF",
    "table_header": "F2F4F7",
    "soft": "F8F6F0",
}


def ensure_inputs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    missing = [path for path in [*FIG.values(), *DATA.values()] if not path.exists()]
    if missing:
        raise FileNotFoundError("\n".join(str(path) for path in missing))


def set_run_font(run, lang: str, size: float | None = None, bold: bool | None = None, color: str | None = None) -> None:
    font = "PingFang SC" if lang == "cn" else "Calibri"
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def set_style_font(style, lang: str, size: float, color: str = COLORS["ink"], bold: bool = False) -> None:
    font = "PingFang SC" if lang == "cn" else "Calibri"
    style.font.name = font
    style._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor.from_string(color)
    style.font.bold = bold


def style_document(doc: Document, lang: str) -> None:
    section = doc.sections[0]
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    styles = doc.styles
    set_style_font(styles["Normal"], lang, 11)
    styles["Normal"].paragraph_format.space_after = Pt(6)
    styles["Normal"].paragraph_format.line_spacing = 1.10
    set_style_font(styles["Heading 1"], lang, 16, COLORS["blue"], True)
    styles["Heading 1"].paragraph_format.space_before = Pt(14)
    styles["Heading 1"].paragraph_format.space_after = Pt(7)
    set_style_font(styles["Heading 2"], lang, 13, COLORS["blue"], True)
    styles["Heading 2"].paragraph_format.space_before = Pt(10)
    styles["Heading 2"].paragraph_format.space_after = Pt(5)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("Detrending and expected-response brief | Yue Dai | 2026-06-25")
    set_run_font(run, lang, 8.5, color=COLORS["muted"])


def add_horizontal_rule(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), COLORS["line"])
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def add_title(doc: Document, title: str, subtitle: str, lang: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(title)
    set_run_font(run, lang, 21, True, COLORS["ink"])
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(subtitle)
    set_run_font(run, lang, 11.5, False, COLORS["muted"])
    add_horizontal_rule(doc)


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_width(cell, width_dxa: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def set_table_fixed(table, widths: list[int]) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_pr = table._tbl.tblPr
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_grid = table._tbl.tblGrid
    if tbl_grid is None:
        tbl_grid = OxmlElement("w:tblGrid")
        table._tbl.insert(0, tbl_grid)
    for child in list(tbl_grid):
        tbl_grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        tbl_grid.append(col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            set_cell_width(cell, widths[idx])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def set_cell_margins(table, top=80, bottom=80, start=120, end=120) -> None:
    tbl_pr = table._tbl.tblPr
    margins = tbl_pr.find(qn("w:tblCellMar"))
    if margins is None:
        margins = OxmlElement("w:tblCellMar")
        tbl_pr.append(margins)
    for key, value in {"top": top, "bottom": bottom, "start": start, "end": end}.items():
        node = margins.find(qn(f"w:{key}"))
        if node is None:
            node = OxmlElement(f"w:{key}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def add_table(doc: Document, rows: list[list[str]], widths: list[int], lang: str) -> None:
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    set_table_fixed(table, widths)
    set_cell_margins(table)
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            cell = table.cell(r, c)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(text)
            set_run_font(run, lang, 9.3 if len(text) > 70 else 10, bold=(r == 0), color=COLORS["ink"])
            if r == 0:
                shade_cell(cell, COLORS["table_header"])
            elif r % 2 == 1:
                shade_cell(cell, COLORS["soft"])
    doc.add_paragraph()


def add_bullet(doc: Document, text: str, lang: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(5)
    run = p.add_run(text)
    set_run_font(run, lang, 10.8)


def add_body(doc: Document, text: str, lang: str, size: float = 10.5, color: str = COLORS["ink"]) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    run = p.add_run(text)
    set_run_font(run, lang, size, False, color)


def add_callout(doc: Document, title: str, body: str, lang: str, fill: str = COLORS["light_teal"]) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    set_table_fixed(table, [9360])
    set_cell_margins(table, top=110, bottom=110, start=170, end=170)
    cell = table.cell(0, 0)
    shade_cell(cell, fill)
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(title)
    set_run_font(r, lang, 11.2, True, COLORS["dark_blue"])
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    r2 = p2.add_run(body)
    set_run_font(r2, lang, 10.3, False, COLORS["ink"])
    doc.add_paragraph()


def add_figure(doc: Document, path: Path, caption: str, interpretation: str, lang: str, width: float = 6.25) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width))

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(caption)
    set_run_font(r, lang, 9.4, True, COLORS["muted"])

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(interpretation)
    set_run_font(r, lang, 9.6, False, COLORS["muted"])


def seasonal_value(df: pd.DataFrame, metric: str, region: str, months: list[int]) -> float:
    subset = df[
        (df["metric"] == metric)
        & (df["region"] == region)
        & (df["year"] == 2026)
        & (df["month"].isin(months))
    ]
    return float(subset["anomaly"].mean())


def era5_value(df: pd.DataFrame, metric: str, region: str, period: str) -> float:
    row = df[(df["metric"] == metric) & (df["region"] == region) & (df["period"] == period)]
    return float(row["anomaly"].iloc[0])


def build_summary_rows(lang: str) -> list[list[str]]:
    monthly_raw = pd.read_csv(DATA["monthly_raw"])
    monthly_det = pd.read_csv(DATA["monthly_detrended"])
    fep_raw = pd.read_csv(DATA["fep_raw"])
    fep_det = pd.read_csv(DATA["fep_detrended"])
    era5_raw = pd.read_csv(DATA["era5_raw"])
    era5_det = pd.read_csv(DATA["era5_detrended"])

    records = [
        (
            "MAM Niño-3 SST" if lang == "en" else "MAM Niño-3 海温",
            seasonal_value(monthly_raw, "ersstv5_sst", "nino3", [3, 4, 5]),
            seasonal_value(monthly_det, "ersstv5_sst", "nino3", [3, 4, 5]),
            "°C",
            "SST becomes slightly stronger after detrending." if lang == "en" else "去趋势后 Niño-3 暖异常略增强。",
        ),
        (
            "MAM FEP residual" if lang == "en" else "MAM FEP residual",
            float(fep_raw.loc[fep_raw["period"].eq("MAM"), "fep_residual"].iloc[0]),
            float(fep_det.loc[fep_det["period"].eq("MAM"), "fep_residual"].iloc[0]),
            "°C",
            "Positive residual remains robust." if lang == "en" else "FEP 相对 Niño-3.4 的额外偏暖仍然存在。",
        ),
        (
            "JFM CP GPCP rainfall" if lang == "en" else "JFM 中太平洋 GPCP 降水",
            seasonal_value(monthly_raw, "gpcp_precip", "central_pacific_180_140w", [1, 2, 3]),
            seasonal_value(monthly_det, "gpcp_precip", "central_pacific_180_140w", [1, 2, 3]),
            "mm/day",
            "Negative rainfall anomaly weakens but remains below normal." if lang == "en" else "负降水异常减弱，但仍低于气候态。",
        ),
        (
            "Apr-May CWP ERA5 u10" if lang == "en" else "Apr-May 中西太平洋 ERA5 u10",
            era5_value(era5_raw, "era5_u10", "cwp_160e_140w", "AM_to_date"),
            era5_value(era5_det, "era5_u10", "cwp_160e_140w", "AM_to_date"),
            "m/s",
            "Near-surface westerlies become close to expectation after detrending." if lang == "en" else "近地面西风去趋势后接近历史预期。",
        ),
        (
            "Apr-May SOI-like MSLP" if lang == "en" else "Apr-May SOI-like 海平面气压差",
            era5_value(era5_raw, "era5_soi_like_mslp", "tahiti_minus_darwin", "AM_to_date"),
            era5_value(era5_det, "era5_soi_like_mslp", "tahiti_minus_darwin", "AM_to_date"),
            "hPa",
            "Pressure-gradient signal strengthens after detrending." if lang == "en" else "去趋势后气压梯度信号更强。",
        ),
    ]

    header = ["Metric", "No detrend", "Detrended", "Change", "Reading"] if lang == "en" else [
        "指标",
        "未去趋势",
        "去趋势后",
        "差值",
        "解读",
    ]
    rows = [header]
    for name, raw, det, unit, note in records:
        rows.append([name, f"{raw:.2f} {unit}", f"{det:.2f} {unit}", f"{det - raw:+.2f} {unit}", note])
    return rows


def add_methods_cn(doc: Document) -> None:
    doc.add_heading("一、数据与方法", level=1)
    add_body(
        doc,
        "本报告以 1982-2022 年为气候态和线性趋势拟合基准，当前 2026 年诊断截至 2026 年 5 月。"
        "所有海温、降水、风场和气压量均先计算月异常，再按区域和季节平均；区域平均采用 cos(latitude) 加权。",
        "cn",
    )
    doc.add_heading("1.1 数据来源", level=2)
    add_table(
        doc,
        [
            ["资料", "用途", "来源网址"],
            [
                "NOAA ERSSTv5 monthly SST",
                "Niño-3、Niño-3.4 和 FEP 月指数；FEP residual 的历史回归。",
                "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc",
            ],
            [
                "NOAA OISST v2.1 monthly SST",
                "2026 空间 SST 异常图、Niño-3 交叉检查，以及 2015/2023/2026 Apr-May 经纬度对比。",
                "https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc",
            ],
            [
                "GPCP monthly precipitation",
                "2026 热带太平洋降水异常和 2015/2023/2026 Apr-May 降水空间对比。",
                "https://psl.noaa.gov/thredds/ncss/grid/Datasets/gpcp/precip.mon.mean.nc",
            ],
            [
                "ERA5 monthly means",
                "u850、海平面气压和 SOI-like 气压梯度指标。",
                "https://cds.climate.copernicus.eu/",
            ],
            [
                "Peng et al. (2025)",
                "expected response 历史回归方法来源。",
                "https://www.nature.com/articles/s41561-025-01700-9",
            ],
            [
                "ORAS5 time-series D20",
                "Jiang et al. (2026) 图 4 风格的赤道太平洋 20°C 等温面深度背景。",
                "https://cds.climate.copernicus.eu/datasets/reanalysis-oras5-timeseries",
            ],
        ],
        [1750, 3450, 4160],
        "cn",
    )
    doc.add_heading("1.2 计算公式", level=2)
    add_table(
        doc,
        [
            ["步骤", "公式", "含义"],
            [
                "月异常",
                "X′(y,m) = X(y,m) - C_m",
                "X 为 SST、降水、u850 或海平面气压；m 为月份；C_m 是 1982-2022 年同月气候态。",
            ],
            [
                "区域/季节平均",
                "X′S(y) = mean over m in S of area-mean_A[X′(y,m)]",
                "area-mean_A 表示 cos(latitude) 加权区域平均；S 可为 JFM、MAM、Apr-May 等时段。",
            ],
            [
                "去趋势异常",
                "X′det(t) = X′(t) - (αt + β)",
                "alpha 和 beta 由 1982-2022 月异常序列线性拟合得到；对每个指标/区域或格点分别处理。",
            ],
            [
                "FEP residual",
                "FEPres = FEP′ - (a + b × Niño-3.4′)",
                "a、b 由 1982-2022 年 FEP 与 Niño-3.4 的历史线性关系估计；正值表示 FEP 比 Niño-3.4 可解释的部分更暖。",
            ],
            [
                "大气预期响应",
                "Rexp = aR + bR × Niño-3′;  ratio = Robs / Rexp",
                "沿用 Peng et al. (2025) 思路；本报告中 R 为 ERA5 u10 或 SOI-like 海平面气压梯度。ratio 小于 1 表示响应弱于历史 SST-大气耦合预期。",
            ],
            [
                "事件对齐空间异常",
                "X′AM(y,lat,lon) = mean[X(y,Apr)-CApr, X(y,May)-CMay]",
                "用于 2015/16、2023/24、2026 的经纬度图；C 为 1982-2022 同月气候态，确保比较的是同一发展季 Apr-May。",
            ],
            [
                "Jiang-style D20",
                "D20* = D20 - mean1960-2024(D20); then 10-yr trailing mean",
                "沿 Jiang et al. (2026) 图 4 逻辑，使用 ORAS5 `depth_of_20_c_isotherm`，赤道 130°E-85°W 点列；2026 年只含 Jan-May，应视为当前更新而非全年平均。",
            ],
        ],
        [1650, 3400, 4310],
        "cn",
    )
    add_body(
        doc,
        "因此，普通异常图回答“相对气候态偏多少”，去趋势图回答“扣除长期线性背景后还偏多少”，"
        "而 expected response 预期线回答“按历史海温-大气关系本该响应多强”。",
        "cn",
        10.0,
        COLORS["muted"],
    )


def add_methods_en(doc: Document) -> None:
    doc.add_heading("1. Data and Methods", level=1)
    add_body(
        doc,
        "The 1982-2022 period is used as both the climatological baseline and the linear-trend fitting period. "
        "The current 2026 diagnosis is available through May 2026. Monthly anomalies are computed first and then averaged by region and season; regional means are weighted by cos(latitude).",
        "en",
    )
    doc.add_heading("1.1 Data", level=2)
    add_table(
        doc,
        [
            ["Dataset", "Use in this report", "Source URL"],
            [
                "NOAA ERSSTv5 monthly SST",
                "Niño-3, Niño-3.4 and FEP monthly indices; historical regression for FEP residual.",
                "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc",
            ],
            [
                "NOAA OISST v2.1 monthly SST",
                "2026 spatial SST anomaly maps, Niño-3 cross-check, and Apr-May maps for 2015/2023/2026.",
                "https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc",
            ],
            [
                "GPCP monthly precipitation",
                "2026 tropical-Pacific rainfall anomalies and Apr-May rainfall maps for 2015/2023/2026.",
                "https://psl.noaa.gov/thredds/ncss/grid/Datasets/gpcp/precip.mon.mean.nc",
            ],
            [
                "ERA5 monthly means",
                "u850, mean sea level pressure, and SOI-like pressure-gradient diagnostics.",
                "https://cds.climate.copernicus.eu/",
            ],
            [
                "Peng et al. (2025)",
                "Method source for the expected-response regression.",
                "https://www.nature.com/articles/s41561-025-01700-9",
            ],
            [
                "ORAS5 time-series D20",
                "Equatorial-Pacific 20°C isotherm-depth background following the Jiang et al. (2026) Fig. 4 logic.",
                "https://cds.climate.copernicus.eu/datasets/reanalysis-oras5-timeseries",
            ],
        ],
        [1750, 3450, 4160],
        "en",
    )
    doc.add_heading("1.2 Formulae", level=2)
    add_table(
        doc,
        [
            ["Step", "Formula", "Meaning"],
            [
                "Monthly anomaly",
                "X′(y,m) = X(y,m) - C_m",
                "X denotes SST, rainfall, u850, or mean sea level pressure; C_m is the 1982-2022 climatology for calendar month m.",
            ],
            [
                "Regional/seasonal mean",
                "X′S(y) = mean over m in S of area-mean_A[X′(y,m)]",
                "area-mean_A is the cos(latitude)-weighted regional mean; S may be JFM, MAM, Apr-May, etc.",
            ],
            [
                "Detrended anomaly",
                "X′det(t) = X′(t) - (αt + β)",
                "alpha and beta are fitted from the 1982-2022 monthly anomaly series for each variable/region or grid point.",
            ],
            [
                "FEP residual",
                "FEPres = FEP′ - (a + b × Niño-3.4′)",
                "a and b are estimated from the 1982-2022 FEP-Niño-3.4 relationship; positive values mean FEP is warmer than expected from Niño-3.4.",
            ],
            [
                "Expected atmospheric response",
                "Rexp = aR + bR × Niño-3′;  ratio = Robs / Rexp",
                "Following Peng et al. (2025), R is ERA5 u10 or the SOI-like sea-level-pressure gradient in this report. A ratio below one indicates a response weaker than historical SST-atmosphere coupling would suggest.",
            ],
            [
                "Event-aligned spatial anomaly",
                "X′AM(y,lat,lon) = mean[X(y,Apr)-CApr, X(y,May)-CMay]",
                "Used for 2015/16, 2023/24, and 2026 latitude-longitude maps. C is the 1982-2022 same-month climatology, so all events are compared in the same Apr-May developing-season window.",
            ],
            [
                "Jiang-style D20",
                "D20* = D20 - mean1960-2024(D20); then 10-yr trailing mean",
                "Following Jiang et al. (2026) Fig. 4, this uses ORAS5 `depth_of_20_c_isotherm` along the equator from 130°E to 85°W. The 2026 value contains Jan-May only and should be read as a current update, not a full-year mean.",
            ],
        ],
        [1650, 3400, 4310],
        "en",
    )
    add_body(
        doc,
        "Thus, an anomaly measures departure from climatology, a detrended anomaly measures the remaining departure after removing the linear background trend, and an expected-response line measures the atmospheric response implied by historical SST-atmosphere coupling.",
        "en",
        10.0,
        COLORS["muted"],
    )


def add_result_figures_cn(doc: Document) -> None:
    doc.add_heading("二、结果", level=1)
    add_callout(
        doc,
        "核心结果",
        "与 1982/83、1997/98、2015/16 和 2023/24 的同月份发展阶段相比，2026 年 Apr-May Niño-3 已进入强事件发展季范围，FEP residual 为正；但未去趋势 u10 只有历史预期的约 0.55 倍，GPCP 中太平洋降水仍为负响应。去趋势前后，FEP/东太平洋偏暖仍然存在；低层风和气压梯度对去趋势处理更敏感。因此后续机制讨论应同时报告未去趋势图和去趋势图。",
        "cn",
    )
    add_table(doc, build_summary_rows("cn"), [1900, 1350, 1350, 1350, 3410], "cn")
    doc.add_page_break()

    add_figure(
        doc,
        FIG["expectation"],
        "图 1. 2026 年 expected response 预期线图，沿用 Peng et al. (2025) 的历史回归逻辑。",
        "灰点为 1982-2022 年 Apr-May 历史关系；红实心点为 2026 观测响应，红空心圈为同一 Niño-3 海温强度下的历史回归预期。未去趋势时 ERA5 u10 约为预期的 0.56 倍，去趋势后约为 1.06 倍；SOI-like 气压梯度则强于预期。",
        "cn",
        6.3,
    )
    doc.add_page_break()
    doc.add_heading("2.1 与历史强 El Niño 的月份对齐比较", level=2)
    add_body(
        doc,
        "历史对照选用 Peng et al. (2025) 中的强事件 1982/83、1997/98、2015/16，并加入 2023/24 与当前 2026。"
        "所有曲线都取事件发展年的 Jan-May；量化矩阵取同一发展年 Apr-May，因此没有把 2026 春季与历史冬季峰值混合比较。",
        "cn",
        10.0,
    )
    add_figure(
        doc,
        FIG["event_sst"],
        "图 2. 月份对齐的海温发展：2026 与历史强 El Niño 事件。",
        "2026 年 Niño-3 在 May 已接近 2023/24 和 2015/16 的发展季强度；FEP residual 为正，说明远东太平洋偏暖超过 Niño-3.4 可解释部分，但幅度低于 2023/24 的极端 FEP residual。",
        "cn",
        6.3,
    )
    add_figure(
        doc,
        FIG["event_atm"],
        "图 3. 月份对齐的大气与降水响应。",
        "2026 年 u10 在 Jan-Feb 偏东风/偏弱，Mar-May 转为弱西风，但远弱于 1997/98 和 2015/16；GPCP 中太平洋降水到 Apr 仍为负，May 才转为小幅正值，显示降水响应滞后于 SST。",
        "cn",
        6.3,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["event_matrix"],
        "图 4. Apr-May 同月份窗口下的事件对比矩阵。",
        "2026 的 Apr-May Niño-3 强度接近 2015/16 和 2023/24；FEP residual 为 +0.50 °C，低于 2023/24 但高于 2015/16。未去趋势 u10 只有历史预期的 0.55 倍，GPCP 中太平洋降水为预期的 -0.33 倍，说明海温已强但风场/降水响应仍不同步。",
        "cn",
        6.3,
    )
    doc.add_page_break()
    doc.add_heading("2.2 Apr-May 经纬度空间对比", level=2)
    add_body(
        doc,
        "为了避免把 2026 春季与历史事件冬季峰值混合比较，空间图也统一使用事件发展年的 Apr-May。"
        "这组图回答的问题是：同样在春季发展阶段，2026 的海温、降水、低层风和气压场更像 2015/16 的经典强响应，还是更像 2023/24 的不同步响应。",
        "cn",
        10.0,
    )
    add_figure(
        doc,
        FIG["event_spatial_sst_precip"],
        "图 5. Apr-May 经纬度图：OISST SST 与 GPCP 降水，2015/16、2023/24、2026 对比。",
        "2015/16 在中东太平洋 SST 暖异常上方已有连续的中太平洋降水增强；2023/24 的 FEP 暖异常最强，但降水响应更破碎；2026 的 Niño-3 与 FEP 都明显偏暖，但中太平洋降水区域均值约为 -0.56 mm/day，显示 SST 与降水仍不同步。",
        "cn",
        6.25,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["event_spatial_era5"],
        "图 6. Apr-May 经纬度图：ERA5 u10 与海平面气压，2015/16、2023/24、2026 对比。",
        "2015/16 的中西太平洋 u10 西风异常带连续且区域均值约 +1.82 m/s；2023/24 同区域约 -0.41 m/s，表现为发展季风场反相；2026 约 +0.52 m/s，已转为西风但远弱于 2015/16。SOI-like 气压梯度在 2026 并不弱，说明当前更突出的不同步来自风场/降水空间响应，而不是气压梯度完全缺失。",
        "cn",
        6.25,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["fep_raw"],
        "图 7. 未去趋势：2026 SST 指数与 FEP residual。",
        "未去趋势图表示当前真实气候背景下的异常，包含长期背景变化。FEP 自 2 月以后快速转暖，并保持正 residual。",
        "cn",
        6.3,
    )
    add_figure(
        doc,
        FIG["fep_detrended"],
        "图 8. 去趋势后：2026 SST 指数与 FEP residual。",
        "去趋势后 FEP residual 仍为正，说明远东太平洋额外偏暖不是单纯由线性背景增暖造成；但 residual 幅度略小于未去趋势版本。",
        "cn",
        6.3,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["spatial_raw"],
        "图 9. 未去趋势：OISST SST 与 GPCP 降水空间异常。",
        "未去趋势空间图更接近“当前实际状态”：热带海盆大范围偏暖，同时中东太平洋降水响应并不连续增强。",
        "cn",
        6.3,
    )
    add_figure(
        doc,
        FIG["spatial_detrended"],
        "图 10. 去趋势后：OISST SST 与 GPCP 降水空间异常。",
        "去趋势后，大范围背景暖信号被削弱，东太平洋/FEP 暖异常仍突出；降水负异常减弱但仍显示海温和降水响应之间存在不同步。",
        "cn",
        6.3,
    )
    doc.add_page_break()
    doc.add_heading("2.3 Jiang et al. 图 4 风格的温跃层背景", level=2)
    add_figure(
        doc,
        FIG["jiang_fig4"],
        "图 11. Jiang et al. (2026) 图 4 同源数据延伸：ERSSTv5 FEP residual 与 ORAS5 D20。",
        "这张图使用与 Jiang et al. (2026) 方法一致的数据家族：左图用 ERSSTv5 计算去趋势 Niño-3.4 与 FEP residual 的 15 年滑动 lead-lag 相关；右图用 ORAS5 `depth_of_20_c_isotherm` 计算赤道太平洋 D20，每个经度扣除 1960-2024 平均后做 10 年 trailing mean。2026 年 D20 只包含 Jan-May，不能当作全年平均，但可作为当前温跃层背景的初步延伸。",
        "cn",
        6.25,
    )


def add_result_figures_en(doc: Document) -> None:
    doc.add_heading("2. Results", level=1)
    add_callout(
        doc,
        "Main result",
        "Compared with the same developing-season months of 1982/83, 1997/98, 2015/16, and 2023/24, Apr-May 2026 Niño-3 is already within the strong-event developing range and the FEP residual is positive; however, non-detrended u10 is only about 0.55 of the historical expectation and central-Pacific GPCP rainfall remains opposite to expectation. With or without detrending, FEP/eastern-Pacific warming remains evident. Low-level wind and pressure-gradient diagnostics are more sensitive to detrending, so both versions should be reported.",
        "en",
    )
    add_table(doc, build_summary_rows("en"), [1900, 1350, 1350, 1350, 3410], "en")
    doc.add_page_break()

    add_figure(
        doc,
        FIG["expectation"],
        "Figure 1. 2026 expected-response lines following the Peng et al. (2025) regression logic.",
        "Gray dots show the 1982-2022 Apr-May historical relationship; filled red dots are the 2026 observed responses, and open red circles are the expected responses for the same Niño-3 SST anomaly. Without detrending, ERA5 u10 is about 0.56 of expectation; after detrending, u10 is close to expectation at about 1.06. The SOI-like pressure gradient is stronger than expected.",
        "en",
        6.3,
    )
    doc.add_page_break()
    doc.add_heading("2.1 Calendar-Aligned Comparison With Strong El Niño Events", level=2)
    add_body(
        doc,
        "The historical reference cases follow Peng et al. (2025): 1982/83, 1997/98, and 2015/16, with 2023/24 and the current 2026 case added. "
        "All trajectories use Jan-May of the event developing year, and the summary matrix uses the same Apr-May window, so the 2026 spring state is not compared with historical winter peaks.",
        "en",
        10.0,
    )
    add_figure(
        doc,
        FIG["event_sst"],
        "Figure 2. Calendar-aligned SST development: 2026 versus historical strong El Niño events.",
        "By May, 2026 Niño-3 SST is close to the developing-season strength of 2023/24 and 2015/16. The FEP residual is positive, meaning far-eastern Pacific warming exceeds the component expected from Niño-3.4, but it is less extreme than 2023/24.",
        "en",
        6.3,
    )
    add_figure(
        doc,
        FIG["event_atm"],
        "Figure 3. Calendar-aligned atmospheric and rainfall response.",
        "In 2026, u10 is weak/easterly in January-February and turns only modestly westerly by March-May, much weaker than 1997/98 and 2015/16. Central-Pacific GPCP rainfall remains negative through April and becomes only weakly positive in May, indicating a lagged rainfall response.",
        "en",
        6.3,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["event_matrix"],
        "Figure 4. Apr-May event comparison using the same developing-season window.",
        "Apr-May 2026 Niño-3 is close to 2015/16 and 2023/24. Its FEP residual is +0.50 °C, lower than 2023/24 but higher than 2015/16. Non-detrended u10 is only 0.55 of the historical expectation, and central-Pacific GPCP rainfall is -0.33 of expectation, showing strong SST but asynchronous wind/rainfall response.",
        "en",
        6.3,
    )
    doc.add_page_break()
    doc.add_heading("2.2 Apr-May Latitude-Longitude Comparison", level=2)
    add_body(
        doc,
        "To avoid comparing 2026 spring with historical winter peaks, the spatial maps also use Apr-May of each event developing year. "
        "The question is whether 2026 spring resembles the canonical strong-response case in 2015/16 or the asynchronous response seen in 2023/24.",
        "en",
        10.0,
    )
    add_figure(
        doc,
        FIG["event_spatial_sst_precip"],
        "Figure 5. Apr-May latitude-longitude maps: OISST SST and GPCP rainfall for 2015/16, 2023/24, and 2026.",
        "In 2015/16, central-eastern Pacific SST warming was accompanied by a continuous central-Pacific rainfall increase. In 2023/24, FEP warming was strongest but rainfall was spatially fragmented. In 2026, Niño-3 and FEP are both warm, yet central-Pacific rainfall averages about -0.56 mm/day, indicating persistent SST-rainfall asynchrony.",
        "en",
        6.25,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["event_spatial_era5"],
        "Figure 6. Apr-May latitude-longitude maps: ERA5 u10 and mean sea-level pressure for 2015/16, 2023/24, and 2026.",
        "The 2015/16 CWP u10 westerly anomaly is broad and strong, averaging about +1.82 m/s; 2023/24 is about -0.41 m/s, a developing-season wind reversal. In 2026 the same region is about +0.52 m/s, so westerlies have returned but remain far weaker than in 2015/16. The SOI-like pressure gradient is not weak in 2026, so the main asynchrony lies in wind/rainfall spatial response rather than a fully absent pressure-gradient signal.",
        "en",
        6.25,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["fep_raw"],
        "Figure 7. No detrending: 2026 SST indices and FEP residual.",
        "The non-detrended version describes the actual current climate state, including long-term background change. FEP warms rapidly after February and keeps a positive residual.",
        "en",
        6.3,
    )
    add_figure(
        doc,
        FIG["fep_detrended"],
        "Figure 8. Detrended: 2026 SST indices and FEP residual.",
        "After detrending, the FEP residual remains positive, so the far-eastern Pacific excess warming cannot be explained only by linear background warming. The residual is slightly smaller than in the non-detrended version.",
        "en",
        6.3,
    )
    doc.add_page_break()
    add_figure(
        doc,
        FIG["spatial_raw"],
        "Figure 9. No detrending: OISST SST and GPCP rainfall spatial anomalies.",
        "The non-detrended spatial map shows the actual state under the current climate background: broad tropical-ocean warmth and a rainfall response that does not form a continuous positive equatorial central-eastern Pacific band.",
        "en",
        6.3,
    )
    add_figure(
        doc,
        FIG["spatial_detrended"],
        "Figure 10. Detrended: OISST SST and GPCP rainfall spatial anomalies.",
        "After detrending, broad background warmth is reduced, but eastern-Pacific/FEP warming remains visible. Rainfall deficits weaken but still indicate asynchronous SST-rainfall response.",
        "en",
        6.3,
    )
    doc.add_page_break()
    doc.add_heading("2.3 Jiang et al. Fig. 4-Style Thermocline Background", level=2)
    add_figure(
        doc,
        FIG["jiang_fig4"],
        "Figure 11. Jiang et al. (2026) Fig. 4 same-source extension: ERSSTv5 FEP residual and ORAS5 D20.",
        "This figure uses the same source family as Jiang et al. (2026): ERSSTv5 for detrended Niño-3.4 and FEP residual lead-lag correlation, and ORAS5 `depth_of_20_c_isotherm` for equatorial-Pacific D20. D20 is mean-removed at each longitude relative to 1960-2024 and smoothed with a 10-year trailing mean. The 2026 D20 row includes Jan-May only, so it should be read as a current update rather than a completed annual mean.",
        "en",
        6.25,
    )


def add_conclusion_cn(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("三、简短结论", level=1)
    for item in [
        "与历史强事件同月份比较后，2026 更像“海温先行、风场/降水滞后”的发展季事件，而不像 1997/98 和 2015/16 那种春季西风和中太平洋降水已经明显同步增强的情形。",
        "经纬度图进一步说明：2026 Apr-May 的 FEP 和 Niño-3 暖异常不弱，但中太平洋降水为负，CWP u10 仅弱西风；同时 SOI-like 气压梯度并不弱，说明不同步重点在风场/降水空间响应。",
        "2026 expected-response 图说明：未去趋势时 u10 响应弱于历史预期，但去趋势后 u10 接近预期；SOI-like 气压梯度反而强于预期。",
        "Jiang et al. 图 4 风格温跃层图已改用同源 ORAS5 D20，而不是 GODAS 替代；2026 D20 只包含 Jan-May，适合作为当前背景监测，不适合当作全年结论。",
        "2026 SST 图说明：去趋势前后，东太平洋/FEP 暖异常仍然存在；因此 FEP 偏暖信号不是完全由长期趋势造成。",
        "降水响应对去趋势有一定敏感性，但即使去趋势后，中太平洋降水仍未与 SST 增暖完全同步。",
        "后续汇报中应把“未去趋势图”作为当前真实背景，把“去趋势图”作为机制归因和历史对比的主图。",
    ]:
        add_bullet(doc, item, "cn")
    add_body(
        doc,
        "注：具体数据来源和公式已并入“数据与方法”部分；本地中间表包括 current_2026_era5_expected_response_lines.csv、event_aligned_2026_comparison.csv、event_aligned_spatial_apr_may_summary.csv、grl_fig4_same_source_*、oras5_d20_annual_mean_removed_10yr.csv 与 current_2026_fep_residual*.csv。",
        "cn",
        9.4,
        COLORS["muted"],
    )


def add_conclusion_en(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("3. Brief Conclusions", level=1)
    for item in [
        "Calendar-aligned comparison with strong historical events suggests that 2026 looks more like a developing-season case with SST leading wind/rainfall, rather than a 1997/98- or 2015/16-like case where springtime westerlies and central-Pacific rainfall were already strongly synchronized.",
        "Latitude-longitude maps sharpen this point: Apr-May 2026 FEP and Niño-3 warming are not weak, but central-Pacific rainfall is negative and CWP u10 is only weakly westerly. The SOI-like pressure gradient is not weak, so the main mismatch is in wind/rainfall spatial response.",
        "The 2026 expected-response figure shows that u10 is weaker than expected without detrending but close to expectation after detrending; the SOI-like pressure gradient is stronger than expected.",
        "The Jiang et al. Fig. 4-style thermocline panel now uses same-source ORAS5 D20 rather than the earlier GODAS substitute. The 2026 D20 value includes Jan-May only and should be used as a current background monitor, not as a full-year conclusion.",
        "Eastern-Pacific/FEP warming remains visible with and without detrending, so the FEP signal is not purely a linear-trend artifact.",
        "Rainfall is somewhat sensitive to detrending, but even after detrending, central-Pacific rainfall does not fully synchronize with SST warming.",
        "For future presentations, the non-detrended map should be used to describe the actual current climate state, while the detrended map should be the main figure for mechanism attribution and historical comparison.",
    ]:
        add_bullet(doc, item, "en")
    add_body(
        doc,
        "Note: data sources and formulae are listed in Data and Methods. Local intermediate tables include current_2026_era5_expected_response_lines.csv, event_aligned_2026_comparison.csv, event_aligned_spatial_apr_may_summary.csv, grl_fig4_same_source_*, oras5_d20_annual_mean_removed_10yr.csv, and current_2026_fep_residual*.csv.",
        "en",
        9.4,
        COLORS["muted"],
    )


def build_cn() -> Path:
    doc = Document()
    style_document(doc, "cn")
    add_title(
        doc,
        "去趋势与 expected response 预期线：2026 ENSO/FEP 简短汇报",
        "方法与阶段性结果 | 中文版 | 2026-06-25",
        "cn",
    )
    add_methods_cn(doc)
    doc.add_page_break()
    add_result_figures_cn(doc)
    add_conclusion_cn(doc)
    out = OUT_DIR / "2026_Detrending_and_Expected_Response_Brief_CN.docx"
    doc.save(out)
    return out


def build_en() -> Path:
    doc = Document()
    style_document(doc, "en")
    add_title(
        doc,
        "Detrending and Expected-Response Lines: A Brief 2026 ENSO/FEP Report",
        "Methods and preliminary results | English version | 25 June 2026",
        "en",
    )
    add_methods_en(doc)
    doc.add_page_break()
    add_result_figures_en(doc)
    add_conclusion_en(doc)
    out = OUT_DIR / "2026_Detrending_and_Expected_Response_Brief_EN.docx"
    doc.save(out)
    return out


def main() -> None:
    ensure_inputs()
    print(build_cn())
    print(build_en())


if __name__ == "__main__":
    main()
