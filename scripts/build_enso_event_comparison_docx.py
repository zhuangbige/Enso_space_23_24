#!/usr/bin/env python3
"""Build the January-June DOCX report for the 2015/16, 2023/24, and 2026 comparison."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/research_2026/reports/enso_event_comparison_unified_1980_2014_jan_jun_2026.docx"

EVENTS = {
    "2015/16": {
        "npz": ROOT / "data/interim/research_2026/monthly_panel_inputs/monthly_2015_detrended_fields_1980_2014.npz",
        "label": "2015/16 development year",
        "ssta": ROOT
        / "outputs/research_2026/revised_event_figures/fig_2015_revised_ssta_u850_detrended_1980_2014.png",
        "precip": ROOT
        / "outputs/research_2026/revised_event_figures/fig_2015_paperstyle_era5_precip_u850_strip_detrended_1980_2014.png",
        "d20": ROOT
        / "outputs/research_2026/revised_event_figures/fig_2015_revised_d20_u850_detrended_1980_2014.png",
    },
    "2023/24": {
        "npz": ROOT / "data/interim/research_2026/monthly_panel_inputs/monthly_2023_detrended_fields_1980_2014.npz",
        "label": "2023/24 development year",
        "ssta": ROOT
        / "outputs/research_2026/revised_event_figures/fig_2023_revised_ssta_u850_detrended_1980_2014.png",
        "precip": ROOT
        / "outputs/research_2026/revised_event_figures/fig_2023_paperstyle_era5_precip_u850_strip_detrended_1980_2014.png",
        "d20": ROOT
        / "outputs/research_2026/revised_event_figures/fig_2023_revised_d20_u850_detrended_1980_2014.png",
    },
    "2026": {
        "npz": ROOT / "data/interim/research_2026/monthly_panel_inputs/monthly_2026_detrended_fields_1980_2014.npz",
        "label": "2026 January-June",
        "ssta": ROOT / "outputs/research_2026/revised_event_figures/fig_2026_revised_ssta_u850_detrended_1980_2014.png",
        "precip": ROOT
        / "outputs/research_2026/revised_event_figures/fig_2026_paperstyle_era5_precip_u850_strip_detrended_1980_2014.png",
        "d20": ROOT / "outputs/research_2026/revised_event_figures/fig_2026_revised_d20_u850_detrended_1980_2014.png",
    },
}

PMM_FIG = ROOT / "outputs/research_2026/pmm_index/fig_pmm_like_eof_patterns_and_index.png"
PMM_FOCUS = ROOT / "outputs/research_2026/pmm_index/fig_pmm_like_index_2026_jan_may.png"
PMM_CSV = ROOT / "data/derived/research_2026/pmm_like_index_oisst_era5_1982_2026.csv"

ORDINARY_DIR = ROOT / "outputs/research_2026/revised_event_figures"
ORDINARY_MANIFEST_CSV = ORDINARY_DIR / "ordinary_el_nino_event_manifest.csv"
ORDINARY_BOOTSTRAP_CSV = ORDINARY_DIR / "ordinary_el_nino_bootstrap_summary.csv"
ORDINARY_EXPECTED_CSV = ORDINARY_DIR / "ordinary_el_nino_expected_response.csv"
ORDINARY_EP_CP_CSV = ORDINARY_DIR / "ordinary_el_nino_ep_cp_sensitivity.csv"
ORDINARY_FIGURES = {
    "sst": ORDINARY_DIR / "fig_ordinary_el_nino_composite_ssta_u850_detrended_1980_2014.png",
    "precip": ORDINARY_DIR / "fig_ordinary_el_nino_composite_precip_u850_detrended_1980_2014.png",
    "d20": ORDINARY_DIR / "fig_ordinary_el_nino_composite_d20_u850_detrended_1980_2014.png",
    "difference": ORDINARY_DIR / "fig_2023_minus_ordinary_el_nino_hovmoller_detrended_1980_2014.png",
    "expected": ORDINARY_DIR / "fig_targets_observed_expected_atmospheric_response_1982_2014.png",
    "ep_cp": ORDINARY_DIR / "fig_ordinary_el_nino_ep_cp_sensitivity_precip_u850.png",
}

REGIONS = {
    "Nino3.4": (-5, 5, 190, 240),
    "CWP": (-5, 5, 160, 220),
    "CP": (-5, 5, 180, 220),
    "EP": (-5, 5, 220, 260),
    "FEP": (-5, 5, 270, 280),
}
D20_REGIONS = {"West": (130, 180), "Central": (180, 220), "East": (220, 275)}


def set_run_font(run, size: float | None = None, bold: bool = False, italic: bool = False) -> None:
    has_cjk = any(0x2E80 <= ord(char) <= 0x9FFF for char in run.text)
    # Hiragino Sans GB is available to both Word on macOS and the LibreOffice
    # renderer used for report QA; Songti SC was dropped during headless export.
    font_name = "Hiragino Sans GB" if has_cjk else "Times New Roman"
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn("w:ascii"), font_name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), font_name)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    run._element.rPr.rFonts.set(qn("w:cs"), font_name)
    if size is not None:
        run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def set_cell_shading(cell, fill: str = "FFFFFF") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 80, start: int = 120, bottom: int = 80, end: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in [("top", top), ("start", start), ("bottom", bottom), ("end", end)]:
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_table_width(table, widths_in: list[float]) -> None:
    table.autofit = False
    for row in table.rows:
        for cell, width in zip(row.cells, widths_in):
            cell.width = Inches(width)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(int(width * 1440)))
            tc_w.set(qn("w:type"), "dxa")


def area_mean(field: np.ndarray, lat: np.ndarray, lon: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray:
    lat0, lat1, lon0, lon1 = box
    lm = (lat >= lat0) & (lat <= lat1)
    om = (lon >= lon0) & (lon <= lon1)
    sub = field[:, lm, :][:, :, om]
    weights = np.cos(np.deg2rad(lat[lm]))
    return np.nansum(sub * weights[None, :, None], axis=(1, 2)) / (np.sum(weights) * om.sum())


def d20_mean(field: np.ndarray, lon: np.ndarray, bounds: tuple[float, float]) -> np.ndarray:
    m = (lon >= bounds[0]) & (lon <= bounds[1])
    return np.nanmean(field[:, m], axis=1)


def load_event_metrics() -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for event, info in EVENTS.items():
        z = np.load(info["npz"])
        lat = z["lat"].astype(float)
        lon = z["lon"].astype(float)
        slat = z["sst_lat"].astype(float)
        slon = z["sst_lon"].astype(float)
        dlon = z["d20_lon"].astype(float)
        out: dict[str, float] = {}
        for region, box in REGIONS.items():
            sst_values = area_mean(z["sst"], slat, slon, box)
            u_values = area_mean(z["u850"], lat, lon, box)
            pr_values = area_mean(z["precip"], lat, lon, box)
            out[f"sst_{region}"] = float(np.nanmean(sst_values))
            out[f"u_{region}"] = float(np.nanmean(u_values))
            out[f"pr_{region}"] = float(np.nanmean(pr_values))
            out[f"sst_{region}_june"] = float(sst_values[-1])
            out[f"u_{region}_june"] = float(u_values[-1])
            out[f"pr_{region}_june"] = float(pr_values[-1])
        for region, bounds in D20_REGIONS.items():
            d20_values = d20_mean(z["d20"], dlon, bounds)
            out[f"d20_{region}"] = float(np.nanmean(d20_values))
            out[f"d20_{region}_june"] = float(d20_values[-1])
        out["sst_baseline_start"] = 1982.0
        metrics[event] = out
    pmm = pd.read_csv(PMM_CSV)
    for event, year in [("2015/16", 2015), ("2023/24", 2023), ("2026", 2026)]:
        subset = pmm[(pmm["year"] == year) & (pmm["month"].between(1, 5))]
        metrics[event]["pmm_joint"] = float(subset["pmm_joint_sst_wind"].mean())
        metrics[event]["pmm_sst"] = float(subset["pmm_sst_only"].mean())
    return metrics


def load_ordinary_analysis() -> dict[str, pd.DataFrame]:
    return {
        "manifest": pd.read_csv(ORDINARY_MANIFEST_CSV),
        "bootstrap": pd.read_csv(ORDINARY_BOOTSTRAP_CSV),
        "expected": pd.read_csv(ORDINARY_EXPECTED_CSV),
        "ep_cp": pd.read_csv(ORDINARY_EP_CP_CSV),
    }


def add_paragraph(doc: Document, text: str = "", style: str | None = None, size: float = 10.5) -> None:
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.1
    run = p.add_run(text)
    set_run_font(run, size=size)


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph(style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, size={1: 15, 2: 13, 3: 11.5}.get(level, 11.5), bold=True)


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(7)
    run = p.add_run(text)
    set_run_font(run, size=8.7, italic=True)


def add_figure(doc: Document, image: Path, caption: str, width: float = 6.35) -> None:
    if not image.exists():
        raise FileNotFoundError(image)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(image), width=Inches(width))
    add_caption(doc, caption)


def add_metric_table(doc: Document, metrics: dict[str, dict[str, float]]) -> None:
    add_heading(doc, "统一气候态后的关键区域指标", level=2)
    add_paragraph(
        doc,
        "下表均为 1-6 月平均。SST 单位为 degC，u850 单位为 m/s，降水单位为 mm/day，D20 单位为 m。"
        "u850 为正代表西风异常，为负代表东风异常。PMM 因 10 m 风资料尚未补到 6 月，仍为 1-5 月平均，并单独标注。",
    )
    rows = [
        ("Niño3.4 SST", "sst_Nino3.4", "{:.2f}"),
        ("CP SST (180E-140W)", "sst_CP", "{:.2f}"),
        ("EP SST (140W-100W)", "sst_EP", "{:.2f}"),
        ("FEP SST (90W-80W)", "sst_FEP", "{:.2f}"),
        ("CWP u850", "u_CWP", "{:.2f}"),
        ("CP precipitation", "pr_CP", "{:.2f}"),
        ("D20 west / central / east", None, "{:.1f} / {:.1f} / {:.1f}"),
        ("PMM joint index (Jan-May)", "pmm_joint", "{:.2f}"),
        ("PMM SST-only index (Jan-May)", "pmm_sst", "{:.2f}"),
    ]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for cell, text in zip(hdr, ["Metric", "2015/16", "2023/24", "2026"]):
        cell.text = text
    for label, key, fmt in rows:
        cells = table.add_row().cells
        cells[0].text = label
        for i, event in enumerate(["2015/16", "2023/24", "2026"], start=1):
            if key is None:
                vals = (metrics[event]["d20_West"], metrics[event]["d20_Central"], metrics[event]["d20_East"])
                cells[i].text = fmt.format(*vals)
            else:
                cells[i].text = fmt.format(metrics[event][key])
    set_table_width(table, [2.2, 1.43, 1.43, 1.43])
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            set_cell_shading(cell, "FFFFFF")
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                para.paragraph_format.line_spacing = 1.05
                for run in para.runs:
                    set_run_font(run, size=8.6, bold=(row is table.rows[0]))


def add_june_metric_table(doc: Document, metrics: dict[str, dict[str, float]]) -> None:
    add_heading(doc, "2026 年 6 月新增证据", level=2)
    add_paragraph(
        doc,
        "六月单月是本次更新的关键。它检验了此前观测到的海温先行、风场恢复和降水滞后是否继续存在。"
        "同一去趋势和气候态口径下，2026 年六月已经出现强中东太平洋增暖、显著赤道西风、正的中太平洋降水异常和清楚的西浅东深温跃层结构。",
    )
    rows = [
        ("Niño3.4 SST", "sst_Nino3.4_june", "{:.2f}"),
        ("CP SST (180E-140W)", "sst_CP_june", "{:.2f}"),
        ("EP SST (140W-100W)", "sst_EP_june", "{:.2f}"),
        ("FEP SST (90W-80W)", "sst_FEP_june", "{:.2f}"),
        ("CWP u850", "u_CWP_june", "{:.2f}"),
        ("CP precipitation", "pr_CP_june", "{:.2f}"),
        ("D20 west / central / east", None, "{:.1f} / {:.1f} / {:.1f}"),
    ]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, ["June metric", "2015", "2023", "2026"]):
        cell.text = text
    for label, key, fmt in rows:
        cells = table.add_row().cells
        cells[0].text = label
        for i, event in enumerate(["2015/16", "2023/24", "2026"], start=1):
            if key is None:
                vals = (
                    metrics[event]["d20_West_june"],
                    metrics[event]["d20_Central_june"],
                    metrics[event]["d20_East_june"],
                )
                cells[i].text = fmt.format(*vals)
            else:
                cells[i].text = fmt.format(metrics[event][key])
    set_table_width(table, [2.2, 1.43, 1.43, 1.43])
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            set_cell_shading(cell, "FFFFFF")
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                para.paragraph_format.line_spacing = 1.05
                for run in para.runs:
                    set_run_font(run, size=8.6, bold=(row is table.rows[0]))


def format_compact_table(table, widths: list[float]) -> None:
    set_table_width(table, widths)
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell, top=65, start=90, bottom=65, end=90)
            set_cell_shading(cell, "FFFFFF")
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                para.paragraph_format.line_spacing = 1.0
                for run in para.runs:
                    set_run_font(run, size=8.1, bold=(row is table.rows[0]))


def add_ordinary_event_table(doc: Document, ordinary: dict[str, pd.DataFrame]) -> None:
    add_heading(doc, "一般非极端 El Niño 事件清单", level=2)
    manifest = ordinary["manifest"]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["发展年事件", "峰值 ONI", "峰值季节", "EP/CP"]):
        cell.text = label
    for row in manifest.itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = str(row.event_label)
        cells[1].text = f"{row.peak_oni:.2f}"
        cells[2].text = str(row.peak_season)
        cells[3].text = str(row.ep_cp_type)
    format_compact_table(table, [2.05, 1.35, 1.75, 1.35])
    add_paragraph(
        doc,
        "事件由 NOAA ERSSTv5 ONI 自动识别：ONI ≥ 0.5°C 持续至少 5 个重叠季节，发展年位于 1982-2014，"
        "且事件峰值 ONI < 2.0°C。1982/83、1997/98、2015/16、2023/24 和 2026 均不进入合成。"
        "合成不确定性采用 10,000 次事件重采样 bootstrap。EP/CP 类型采用 Beniche et al. (2024) 补充图 S4 的 "
        "Cold Tongue/Warm Pool 事件分类。",
        size=9.2,
    )


def add_expected_response_table(doc: Document, ordinary: dict[str, pd.DataFrame]) -> None:
    expected = ordinary["expected"]
    means = (
        expected.groupby(["target_label", "response"], as_index=False)[["observed", "expected", "residual"]]
        .mean(numeric_only=True)
        .set_index(["target_label", "response"])
    )
    add_heading(doc, "SST 条件下的观测—历史预期响应", level=2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["响应（1-6 月平均）", "2015/16", "2023/24", "2026 发展状态"]):
        cell.text = label
    rows = [
        ("CWP u850 (m/s)", "cwp_u850"),
        ("CP precipitation (mm/day)", "cp_precip"),
    ]
    labels = {2015: "2015/16", 2023: "2023/24", 2026: "2026 developing state"}
    for metric_label, response in rows:
        cells = table.add_row().cells
        cells[0].text = metric_label
        for index, year in enumerate((2015, 2023, 2026), start=1):
            row = means.loc[(labels[year], response)]
            cells[index].text = f"{row.observed:+.2f} / {row.expected:+.2f} ({row.residual:+.2f})"
    format_compact_table(table, [2.05, 1.48, 1.48, 1.48])
    add_paragraph(
        doc,
        "单元格依次为观测值 / SST 条件历史预期值（残差）。预期值由 1982-2014 各日历月 Niño3 SST 回归得到；"
        "2015、2023 和 2026 均未进入拟合。2023 年 1-6 月 CWP u850 残差为 -0.86 m/s，CP 降水残差为 "
        "-1.88 mm/day，说明大气响应偏弱并不只是因为它弱于超级 El Niño，而是相对于同期 SST 强迫也偏弱。",
        size=9.2,
    )


def configure_styles(doc: Document) -> None:
    section = doc.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.78)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.82)
    section.right_margin = Inches(0.82)
    section.header_distance = Inches(0.49)
    section.footer_distance = Inches(0.49)

    styles = doc.styles
    for style_name, size, bold, before, after in [
        ("Normal", 10.5, False, 0, 5),
        ("Heading 1", 15, True, 14, 6),
        ("Heading 2", 13, True, 10, 5),
        ("Heading 3", 11.5, True, 8, 4),
        ("Caption", 8.7, False, 1, 6),
    ]:
        style = styles[style_name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = None
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.1
        rpr = style._element.get_or_add_rPr()
        rfonts = rpr.rFonts
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        for key in ("ascii", "hAnsi", "cs"):
            rfonts.set(qn(f"w:{key}"), "Times New Roman")
        rfonts.set(qn("w:eastAsia"), "Hiragino Sans GB")


def build_doc() -> None:
    metrics = load_event_metrics()
    ordinary = load_ordinary_analysis()
    doc = Document()
    configure_styles(doc)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run("2015/16、2023/24 与 2026 ENSO 发展期对比分析")
    set_run_font(run, size=20, bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(10)
    run = subtitle.add_run("统一气候态和去趋势基准下的 1-6 月 SST-Wind、Precipitation-Wind 与 D20-Wind 诊断")
    set_run_font(run, size=10.5)

    add_heading(doc, "分析口径", level=1)
    add_paragraph(
        doc,
        "本报告讨论最新重画的三组 1-6 月事件图。SST 使用 NOAA OISST，850 hPa 风和降水使用 ERA5，D20 使用 ORAS5。"
        "SST、风、降水和 D20 均按同月气候态计算异常，并移除线性趋势；ERA5/ORAS5 共同基准为 1980-2014，"
        "OISST 因资料起点限制使用 1982-2014。PMM 图为独立的 PMM-like EOF 诊断，EOF 训练期为 1982-2025，"
        "2026 年 PMM 仍只使用 1-5 月资料投影到该 EOF 模态上，不参与 EOF 训练；它不用于判断六月的大气反馈。",
    )
    add_paragraph(
        doc,
        "空间上重点比较中太平洋、东太平洋和远东太平洋的 SST 异常；时间上重点看 1 月到 6 月暖中心、低层风、"
        "降水和 D20 是否同步推进。海气耦合的判据不是单一变量，而是 SST、u850、降水和 D20 是否在相近区域、相近月份共同增强。",
    )

    add_metric_table(doc, metrics)
    add_june_metric_table(doc, metrics)

    add_heading(doc, "综合判断", level=1)
    add_paragraph(
        doc,
        "统一气候态后，2026 不只是一个表层偏东的暖事件。六月 Niño3.4、CP 和 EP SST 分别达到约 1.54、1.63 和 1.62 degC，"
        "CWP u850 达到约 6.37 m/s，东部 D20 加深约 46.6 m。海温、低层西风和温跃层调整已经形成清楚的协同增强。"
    )
    add_paragraph(
        doc,
        "三者最主要的差异仍是海气耦合建立的时间。2015 的西风、D20、SST 和中太平洋降水较早协同增强；2023 以远东太平洋暖异常先行，"
        "大气响应相对偏弱；2026 则表现出阶段性转换：1-4 月对流偏弱，5 月开始恢复，6 月中太平洋降水转为约 +2.40 mm/day。"
        "因此，2026 已不能再概括为持续脱耦，而应描述为从早期不同步向强耦合快速过渡。"
    )

    add_heading(doc, "SST 异常与 850 hPa 风：暖中心和东西风的空间传播", level=1)
    add_paragraph(
        doc,
        "2015 的早春信号更偏中太平洋到中东太平洋，并伴随持续西风异常。2023 的暖中心明显偏远东太平洋，随后逐步向中东太平洋扩展。"
        "2026 早期也有东部增强，但 4-5 月中太平洋 SST 与西风开始接入；到六月，暖异常已经覆盖中东太平洋并伴随最强的 CWP/CP 西风异常，"
        "显示Bjerknes正反馈已经明显建立。"
    )
    add_figure(doc, EVENTS["2015/16"]["ssta"], "Figure 1. 2015/16 development year: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2023/24"]["ssta"], "Figure 2. 2023/24 development year: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2026"]["ssta"], "Figure 3. January-June 2026: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")

    add_heading(doc, "降水与 850 hPa 风：大气响应是否跟上海温和风场", level=1)
    add_paragraph(
        doc,
        "降水图显示 2015 的中太平洋对流响应最早、最一致；2023 在远东太平洋 SST 增暖期间，中太平洋降水仍偏弱，说明大气耦合偏晚。"
        "2026 的关键点是：中太平洋降水在 1-4 月仍偏抑制，5 月局部恢复，6 月则转为明显正异常，并与强西风和暖 SST 同区出现。"
        "这意味着大气深对流反馈在六月已经跟上，而不是继续维持春季的响应滞后。"
    )
    add_figure(doc, EVENTS["2015/16"]["precip"], "Figure 4. 2015/16 development year: ERA5 precipitation with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2023/24"]["precip"], "Figure 5. 2023/24 development year: ERA5 precipitation with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2026"]["precip"], "Figure 6. January-June 2026: ERA5 precipitation with ERA5 850 hPa wind anomalies.")

    add_heading(doc, "D20 与赤道 u850：次表层动力结构", level=1)
    add_paragraph(
        doc,
        "D20 是解释 2015 和 2026 相似性的核心证据。六月 2015 和 2026 都表现出西太平洋浅化、中东太平洋显著加深的结构，"
        "对应暖水体东移和温跃层倾斜增强。2026 年六月西部 D20 约 -12.1 m、东部约 +46.6 m；2023 年同期西部仅约 -2.7 m，"
        "因此 2026 的盆尺度动力调整明显更接近 2015。"
    )
    add_figure(doc, EVENTS["2015/16"]["d20"], "Figure 7. 2015/16 development year: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")
    add_figure(doc, EVENTS["2023/24"]["d20"], "Figure 8. 2023/24 development year: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")
    add_figure(doc, EVENTS["2026"]["d20"], "Figure 9. January-June 2026: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")

    add_heading(doc, "PMM：北太平洋副热带背景是否参与", level=1)
    add_paragraph(
        doc,
        "PMM-like EOF 表示扣除 Niño3.4 线性影响以后，北太平洋副热带 SST 与近地面风场的主要耦合模态。"
        "正位相对应东北太平洋偏暖、信风减弱和较弱蒸发冷却的背景。2015 和 2026 的 joint SST+wind PMM 指数在 1-5 月均明显为正，"
        "而 2023 较弱甚至偏负，说明 2026 的副热带海气背景更像 2015。"
        "由于 PMM 的 10 m 风输入尚未补到六月，本节只作为前期背景，不参与六月反馈是否闭合的判断。"
    )
    add_figure(doc, PMM_FIG, "Figure 10. PMM-like EOF diagnostics from OISST SST and ERA5 10 m wind. EOF training period: 1982-2025.")
    add_figure(doc, PMM_FOCUS, "Figure 11. 2026 January-May PMM-like joint SST+wind and SST-only indices.")

    add_heading(doc, "一般 El Niño 对照：2023/24 是否相对同等 SST 强迫也偏弱", level=1)
    add_paragraph(
        doc,
        "老师建议的“一般 El Niño”对照在这里承担两个不同任务。第一，等权事件合成给出普通非极端事件在相同日历阶段的空间背景；"
        "第二，Peng et al. (2025) 式的历史回归控制 SST 振幅，比较实际大气响应与同月 Niño3 SST 所对应的历史预期。"
        "前者回答“普通事件通常在几月推进到哪里”，后者才直接回答“给定 SST 强迫，大气响应是否不足”。本报告不再把两者混为一个综合指标。",
    )
    add_ordinary_event_table(doc, ordinary)
    add_paragraph(
        doc,
        "七个一般事件的 1-6 月 Niño3 SST 合成均值约为 -0.06°C，反映许多普通事件直到春末或初夏才进入发展阶段。"
        "因此，普通事件合成是“日历阶段基准”，不能单独当作与 2023/24 等振幅的反事实预期。图 12-14 展示其 SST—风、降水—风和 D20—风演变；"
        "所有风场子图使用一致矢量尺度，并在每个面板右下角单独给出带单位的白底风矢量标识。",
    )
    add_figure(doc, ORDINARY_FIGURES["sst"], "Figure 12. Ordinary non-extreme El Niño composite: January-June OISST SSTA and ERA5 850 hPa wind anomalies (n=7).")
    add_figure(doc, ORDINARY_FIGURES["precip"], "Figure 13. Ordinary non-extreme El Niño composite: January-June ERA5 precipitation and 850 hPa wind anomalies (n=7).")
    add_figure(doc, ORDINARY_FIGURES["d20"], "Figure 14. Ordinary non-extreme El Niño composite: January-June ORAS5 equatorial D20 anomalies and ERA5 u850 (n=7).")
    add_paragraph(
        doc,
        "2023 减去一般事件合成后，东太平洋表层与次表层暖信号仍然显著，而中西太平洋低层风和中太平洋降水并未出现等比例增强。"
        "这是一种“强海洋信号—有限大气跟随”的空间残差结构；但因普通事件的发展起始月份不同，图 15 只作为空间定位证据。",
    )
    add_figure(doc, ORDINARY_FIGURES["difference"], "Figure 15. January-June 2023 minus the ordinary non-extreme El Niño composite: SST, precipitation/u850, and equatorial D20/u850 differences.")
    add_expected_response_table(doc, ordinary)
    add_figure(doc, ORDINARY_FIGURES["expected"], "Figure 16. Observed and SST-conditioned historical atmospheric responses in 2015, 2023, and the 2026 developing state. Calendar-month regressions are fitted over 1982-2014.")
    add_heading(doc, "EP/CP 分型稳健性", level=2)
    add_paragraph(
        doc,
        "按已发表事件类别复算后，EP 子样本为 1986、1991、2006（n=3），CP 子样本为 1994、2002、2004、2009（n=4）。"
        "两类降水—风空间结构确有差异，说明统一合成会掩盖部分经向位置和响应中心差别；但样本很小，本文仅将其作为定性敏感性检查，"
        "不据此建立新的主结论。Yan et al. (2025) 提供了 EP/CP 降水响应差异的物理依据，具体离散事件归类则来自 Beniche et al. (2024)。",
    )
    add_figure(doc, ORDINARY_FIGURES["ep_cp"], "Figure 17. EP and CP sensitivity of January-June precipitation and u850 within the ordinary-event sample; qualitative because n=3 and n=4.")

    add_heading(doc, "三次事件的异同点", level=1)
    add_paragraph(
        doc,
        "2015/16 是最典型的强耦合发展型事件：中太平洋和中东太平洋 SST 较早为正，西风异常强，中太平洋降水也较早转正，"
        "D20 呈现清楚的西浅东深结构。它代表了 ocean dynamics、low-level winds 和 convection 的同步增强。"
    )
    add_paragraph(
        doc,
        "2023/24 的发展期更偏远东太平洋先行。FEP SST 是三者中相对最突出的，CP SST 和 PMM 支持较弱，"
        "降水和低层风对 SST 的响应也不如 2015 同步。因此它更像东部启动、随后向西连接的事件。"
    )
    add_paragraph(
        doc,
        "2026 的综合特征呈现清楚的阶段转换。1-4 月仍带有东部海温先行和对流滞后的特征，但到六月，CP/EP SST、强西风、"
        "正降水异常和 D20 西浅东深结构同时出现，使其明显转向 2015 式强耦合框架。它不是 2015 的简单复刻，"
        "但截至六月已不再支持持续海气脱耦的表述。"
    )

    add_heading(doc, "结论", level=1)
    add_paragraph(
        doc,
        "新增一般 El Niño 对照和 SST 条件历史预期后，最稳健的主结论是：2023/24 的大气响应偏弱并不只是相对于 2015/16 这类超级事件而言；"
        "在控制同月 Niño3 SST 振幅后，其中西太平洋 u850 和中太平洋降水仍分别低于历史预期约 0.86 m/s 和 1.88 mm/day。"
        "这支持“较强海洋初始记忆推动东太平洋增暖，但大气正反馈未同步充分实现”的机制表述。更新到六月的 2026 仅被视为样本外发展状态："
        "其六月 SST、西风、降水和温跃层已协同增强，但不能据此提前认定为一个完整 El Niño 事件。下一步应检验这种耦合是否在 JJA/SON 持续。"
    )

    add_heading(doc, "方法参考", level=1)
    add_paragraph(
        doc,
        "Peng et al. (2025), Nature Geoscience, doi:10.1038/s41561-025-01700-9：2023/24 与典型强事件的海洋初始状态和风应力作用比较。\n"
        "Beniche et al. (2024), Scientific Reports, doi:10.1038/s41598-024-52580-9：中等/极端事件分组、合成、bootstrap 及 CT/WP 事件类别。\n"
        "Kim et al. (2025), npj Climate and Atmospheric Science, doi:10.1038/s41612-024-00890-0：持续东风限制 2023/24 发展。\n"
        "Yan et al. (2025), npj Climate and Atmospheric Science, doi:10.1038/s41612-025-00933-0：EP/CP El Niño 的降水与 Walker 环流响应差异。\n"
        "Srinivas et al. (2024), Scientific Reports, doi:10.1038/s41598-024-58803-3：一般与极端事件合成的结构和非线性响应差异。",
        size=9.2,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build_doc()
