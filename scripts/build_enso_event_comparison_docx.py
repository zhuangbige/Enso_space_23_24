#!/usr/bin/env python3
"""Build a plain DOCX report for the 2015/16, 2023/24, and 2026 event comparison."""

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
OUT = ROOT / "outputs/research_2026/reports/enso_event_comparison_unified_1980_2014.docx"

EVENTS = {
    "2015/16": {
        "npz": ROOT / "data/interim/research_2026/monthly_panel_inputs/monthly_2015_detrended_fields_1980_2014.npz",
        "label": "2015/16 development year",
        "ssta": ROOT
        / "outputs/research_2026/event_2015_16_monthly_panels_1980_2025_detrended/fig_2015_monthly_ssta_u850_detrended_1980_2014.png",
        "precip": ROOT
        / "outputs/research_2026/event_2015_16_monthly_panels_1980_2025_detrended/fig_2015_monthly_era5_precip_u850_detrended_1980_2014.png",
        "d20": ROOT
        / "outputs/research_2026/event_2015_16_monthly_panels_1980_2025_detrended/fig_2015_monthly_d20_u850_detrended_1980_2014.png",
    },
    "2023/24": {
        "npz": ROOT / "data/interim/research_2026/monthly_panel_inputs/monthly_2023_detrended_fields_1980_2014.npz",
        "label": "2023/24 development year",
        "ssta": ROOT
        / "outputs/research_2026/event_2024_monthly_panels_1980_2023_detrended/fig_2023_monthly_ssta_u850_detrended_1980_2014.png",
        "precip": ROOT
        / "outputs/research_2026/event_2024_monthly_panels_1980_2023_detrended/fig_2023_monthly_era5_precip_u850_detrended_1980_2014.png",
        "d20": ROOT
        / "outputs/research_2026/event_2024_monthly_panels_1980_2023_detrended/fig_2023_monthly_d20_u850_detrended_1980_2014.png",
    },
    "2026": {
        "npz": ROOT / "data/interim/research_2026/monthly_panel_inputs/monthly_2026_detrended_fields_1980_2014.npz",
        "label": "2026 January-May",
        "ssta": ROOT / "outputs/research_2026/monthly_panels_1980_2025_detrended/fig_2026_monthly_ssta_u850_detrended_1980_2014.png",
        "precip": ROOT
        / "outputs/research_2026/monthly_panels_1980_2025_detrended/fig_2026_monthly_era5_precip_u850_detrended_1980_2014.png",
        "d20": ROOT / "outputs/research_2026/monthly_panels_1980_2025_detrended/fig_2026_monthly_d20_u850_detrended_1980_2014.png",
    },
}

PMM_FIG = ROOT / "outputs/research_2026/pmm_index/fig_pmm_like_eof_patterns_and_index.png"
PMM_FOCUS = ROOT / "outputs/research_2026/pmm_index/fig_pmm_like_index_2026_jan_may.png"
PMM_CSV = ROOT / "data/derived/research_2026/pmm_like_index_oisst_era5_1982_2026.csv"

REGIONS = {
    "Nino3.4": (-5, 5, 190, 240),
    "CWP": (-5, 5, 160, 220),
    "CP": (-5, 5, 180, 220),
    "EP": (-5, 5, 220, 260),
    "FEP": (-5, 5, 270, 280),
}
D20_REGIONS = {"West": (130, 180), "Central": (180, 220), "East": (220, 275)}


def set_run_font(run, size: float | None = None, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run._element.rPr.rFonts.set(qn("w:cs"), "Times New Roman")
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
            out[f"sst_{region}"] = float(np.nanmean(area_mean(z["sst"], slat, slon, box)))
            out[f"u_{region}"] = float(np.nanmean(area_mean(z["u850"], lat, lon, box)))
            out[f"pr_{region}"] = float(np.nanmean(area_mean(z["precip"], lat, lon, box)))
        for region, bounds in D20_REGIONS.items():
            out[f"d20_{region}"] = float(np.nanmean(d20_mean(z["d20"], dlon, bounds)))
        out["sst_baseline_start"] = 1982.0
        metrics[event] = out
    pmm = pd.read_csv(PMM_CSV)
    for event, year in [("2015/16", 2015), ("2023/24", 2023), ("2026", 2026)]:
        subset = pmm[(pmm["year"] == year) & (pmm["month"].between(1, 5))]
        metrics[event]["pmm_joint"] = float(subset["pmm_joint_sst_wind"].mean())
        metrics[event]["pmm_sst"] = float(subset["pmm_sst_only"].mean())
    return metrics


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
    p.add_run().add_picture(str(image), width=Inches(width))
    add_caption(doc, caption)


def add_metric_table(doc: Document, metrics: dict[str, dict[str, float]]) -> None:
    add_heading(doc, "统一气候态后的关键区域指标", level=2)
    add_paragraph(
        doc,
        "下表均为 1-5 月平均。SST 单位为 degC，u850 单位为 m/s，降水单位为 mm/day，D20 单位为 m。"
        "u850 为正代表西风异常，为负代表东风异常。",
    )
    rows = [
        ("Niño3.4 SST", "sst_Nino3.4", "{:.2f}"),
        ("CP SST (180E-140W)", "sst_CP", "{:.2f}"),
        ("EP SST (140W-100W)", "sst_EP", "{:.2f}"),
        ("FEP SST (90W-80W)", "sst_FEP", "{:.2f}"),
        ("CWP u850", "u_CWP", "{:.2f}"),
        ("CP precipitation", "pr_CP", "{:.2f}"),
        ("D20 west / central / east", None, "{:.1f} / {:.1f} / {:.1f}"),
        ("PMM joint index", "pmm_joint", "{:.2f}"),
        ("PMM SST-only index", "pmm_sst", "{:.2f}"),
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
        for key in ("ascii", "hAnsi", "eastAsia", "cs"):
            rfonts.set(qn(f"w:{key}"), "Times New Roman")


def build_doc() -> None:
    metrics = load_event_metrics()
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
    run = subtitle.add_run("统一气候态和去趋势基准下的 1-5 月 SST-Wind、Precipitation-Wind、D20-Wind 与 PMM 诊断")
    set_run_font(run, size=10.5)

    add_heading(doc, "分析口径", level=1)
    add_paragraph(
        doc,
        "本报告只讨论最新重画的三组 1-5 月事件图。SST 使用 NOAA OISST，850 hPa 风和降水使用 ERA5，D20 使用 ORAS5。"
        "SST、风、降水和 D20 均按同月气候态计算异常，并移除线性趋势；ERA5/ORAS5 共同基准为 1980-2014，"
        "OISST 因资料起点限制使用 1982-2014。PMM 图为独立的 PMM-like EOF 诊断，EOF 训练期为 1982-2025，"
        "2026 年 1-5 月只投影到该 EOF 模态上，不参与 EOF 训练。",
    )
    add_paragraph(
        doc,
        "空间上重点比较中太平洋、东太平洋和远东太平洋的 SST 异常；时间上重点看 1 月到 5 月暖中心、低层风、"
        "降水和 D20 是否同步推进。海气耦合的判据不是单一变量，而是 SST、u850、降水和 D20 是否在相近区域、相近月份共同增强。",
    )

    add_metric_table(doc, metrics)

    add_heading(doc, "综合判断", level=1)
    add_paragraph(
        doc,
        "统一气候态后，2026 不再只是一个表层偏弱的东太平洋暖事件。它的 Niño3.4、CP 和 EP SST 均比原先不统一基准时更高，"
        "同时 CWP/CP 低层西风和东太平洋 D20 也更强。因此，2026 在动力结构上更接近 2015，而不是 2023。"
    )
    add_paragraph(
        doc,
        "三者最主要的差异是海气耦合的成熟度。2015 的西风、D20、SST 和中太平洋降水较早协同增强；2023 则以远东太平洋暖异常先行，"
        "中太平洋和 PMM 支持都较弱；2026 的 D20 和低层风已经接近 2015 式结构，但降水仍滞后，说明深对流耦合尚未完全跟上。"
    )

    add_heading(doc, "SST 异常与 850 hPa 风：暖中心和东西风的空间传播", level=1)
    add_paragraph(
        doc,
        "2015 的早春信号更偏中太平洋到中东太平洋，并伴随持续西风异常。2023 的暖中心明显偏远东太平洋，随后逐步向中东太平洋扩展。"
        "2026 早期也有东部增强，但 4-5 月中太平洋 SST 与西风都开始接入，使它不像 2023 那样纯粹偏东。"
    )
    add_figure(doc, EVENTS["2015/16"]["ssta"], "Figure 1. 2015/16 development year: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2023/24"]["ssta"], "Figure 2. 2023/24 development year: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2026"]["ssta"], "Figure 3. 2026 January-May: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")

    add_heading(doc, "降水与 850 hPa 风：大气响应是否跟上海温和风场", level=1)
    add_paragraph(
        doc,
        "降水图显示 2015 的中太平洋对流响应最早、最一致；2023 在远东太平洋 SST 增暖期间，中太平洋降水仍偏弱，说明大气耦合偏晚。"
        "2026 的关键点是：西风异常已经比较像 2015，但中太平洋降水 1-4 月仍偏抑制，5 月才局部恢复。"
    )
    add_figure(doc, EVENTS["2015/16"]["precip"], "Figure 4. 2015/16 development year: ERA5 precipitation with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2023/24"]["precip"], "Figure 5. 2023/24 development year: ERA5 precipitation with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2026"]["precip"], "Figure 6. 2026 January-May: ERA5 precipitation with ERA5 850 hPa wind anomalies.")

    add_heading(doc, "D20 与赤道 u850：次表层动力结构", level=1)
    add_paragraph(
        doc,
        "D20 是解释导师为什么会觉得 2015 和 2026 相像的核心证据。2015 和 2026 都表现出西太平洋相对浅化、中东太平洋加深的结构，"
        "对应暖水体向中东太平洋倾斜或输送。2023 虽然东太平洋 D20 也加深，但西太平洋并未呈现同样清楚的浅化，因此动力结构不如 2015/2026 相似。"
    )
    add_figure(doc, EVENTS["2015/16"]["d20"], "Figure 7. 2015/16 development year: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")
    add_figure(doc, EVENTS["2023/24"]["d20"], "Figure 8. 2023/24 development year: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")
    add_figure(doc, EVENTS["2026"]["d20"], "Figure 9. 2026 January-May: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")

    add_heading(doc, "PMM：北太平洋副热带背景是否参与", level=1)
    add_paragraph(
        doc,
        "PMM-like EOF 表示扣除 Niño3.4 线性影响以后，北太平洋副热带 SST 与近地面风场的主要耦合模态。"
        "正位相对应东北太平洋偏暖、信风减弱和较弱蒸发冷却的背景。2015 和 2026 的 joint SST+wind PMM 指数在 1-5 月均明显为正，"
        "而 2023 较弱甚至偏负，说明 2026 的副热带海气背景更像 2015。"
    )
    add_figure(doc, PMM_FIG, "Figure 10. PMM-like EOF diagnostics from OISST SST and ERA5 10 m wind. EOF training period: 1982-2025.")
    add_figure(doc, PMM_FOCUS, "Figure 11. 2026 January-May PMM-like joint SST+wind and SST-only indices.")

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
        "2026 的综合特征介于两者之间，但更靠近 2015 的动力框架。表层 SST 的早期暖中心带有东部先行特征，"
        "但统一基准后 CP/EP SST、西风异常、D20 西浅东深结构和 PMM 正位相都使 2026 更接近 2015。"
        "它目前与 2015 的主要差别是降水和深对流滞后，即海洋和低层风已经先行，大气深对流尚未完全闭合反馈。"
    )

    add_heading(doc, "结论", level=1)
    add_paragraph(
        doc,
        "如果只看 1-5 月表层 SST 暖中心，2026 会显得有一部分 2023 式的东太平洋先行特征；但如果把 D20、u850 和 PMM 一起看，"
        "2026 与 2015 的相似性更强。更准确的表述是：2026 不是 2015 的简单复刻，而是一个东部启动明显、"
        "但动力背景逐渐转向 2015 式中东太平洋耦合框架的事件。后续判断是否真正接近 2015，还需要观察夏季以后中太平洋降水和 Walker circulation 是否持续响应。"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build_doc()
