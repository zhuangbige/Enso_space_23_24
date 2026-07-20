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

ORDINARY_DIR = ROOT / "outputs/research_2026/revised_event_figures"
ORDINARY_EXPECTED_CSV = ORDINARY_DIR / "ordinary_el_nino_expected_response.csv"
SIMILARITY_CSV = ORDINARY_DIR / "event_2026_taylor_similarity_to_2015_2023.csv"
ORDINARY_FIGURES = {
    "expected": ORDINARY_DIR / "fig_targets_observed_expected_atmospheric_response_1982_2014.png",
    "staged": ORDINARY_DIR / "fig_2026_staged_air_sea_coupling_jan_jun_1980_2014.png",
}

REGIONS = {
    "Nino3.4": (-5, 5, 190, 240),
    "CP": (-5, 5, 180, 220),
}
D20_REGIONS = {"West": (130, 180), "Central": (180, 220), "East": (220, 275)}


def set_run_font(run, size: float | None = None, bold: bool = False, italic: bool = False) -> None:
    has_cjk = any(0x2E80 <= ord(char) <= 0x9FFF for char in run.text)
    # STSong is exposed to both Word on macOS and the headless LibreOffice
    # renderer used for report QA.
    font_name = "STSong" if has_cjk else "Times New Roman"
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


def mark_table_header(table) -> None:
    """Mark the first row as a repeating semantic table header."""

    properties = table.rows[0]._tr.get_or_add_trPr()
    if properties.find(qn("w:tblHeader")) is None:
        repeat_header = OxmlElement("w:tblHeader")
        repeat_header.set(qn("w:val"), "true")
        properties.append(repeat_header)


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
            pr_values = area_mean(z["precip"], lat, lon, box)
            out[f"sst_{region}"] = float(np.nanmean(sst_values))
            out[f"pr_{region}"] = float(np.nanmean(pr_values))
            out[f"sst_{region}_june"] = float(sst_values[-1])
            out[f"pr_{region}_june"] = float(pr_values[-1])
        for region, bounds in D20_REGIONS.items():
            d20_values = d20_mean(z["d20"], dlon, bounds)
            out[f"d20_{region}"] = float(np.nanmean(d20_values))
            out[f"d20_{region}_june"] = float(d20_values[-1])
        out["sst_baseline_start"] = 1982.0
        metrics[event] = out

    expected = pd.read_csv(ORDINARY_EXPECTED_CSV)
    labels = {"2015/16": "2015/16", "2023/24": "2023/24", "2026": "2026 developing state"}
    for event, target_label in labels.items():
        wind = expected.loc[
            expected["target_label"].eq(target_label) & expected["response"].eq("cwp_u10")
        ].sort_values("month")
        if wind["month"].astype(int).tolist() != list(range(1, 7)):
            raise ValueError(f"Incomplete Peng CWP u10 response rows for {target_label}")
        metrics[event]["u_CWP"] = float(wind["observed"].mean())
        metrics[event]["u_CWP_june"] = float(wind.iloc[-1]["observed"])
    return metrics


def load_ordinary_analysis() -> dict[str, pd.DataFrame]:
    return {
        "expected": pd.read_csv(ORDINARY_EXPECTED_CSV),
        "similarity": pd.read_csv(SIMILARITY_CSV),
    }


def add_paragraph(doc: Document, text: str = "", style: str | None = None, size: float = 10.5):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.1
    run = p.add_run(text)
    set_run_font(run, size=size)
    return p


def keep_table_together(table) -> None:
    """Keep a compact table on one page when it fits."""
    for row_index, row in enumerate(table.rows):
        tr_properties = row._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        tr_properties.append(cant_split)
        if row_index < len(table.rows) - 1:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.keep_with_next = True


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
    picture = p.add_run().add_picture(str(image), width=Inches(width))
    picture._inline.docPr.set("title", caption)
    picture._inline.docPr.set("descr", caption)
    add_caption(doc, caption)


def add_metric_table(doc: Document, metrics: dict[str, dict[str, float]]) -> None:
    add_heading(doc, "表1  三次事件的关键区域指标", level=2)
    table_note = add_paragraph(
        doc,
        "每格为1-6月平均 / 6月单月；Peng CWP u10为正表示近地面西风异常。",
        size=9.2,
    )
    table_note.paragraph_format.keep_with_next = True
    rows = [
        ("Niño3.4 SST (°C)", "sst_Nino3.4", "{:+.2f}"),
        ("Peng CWP u10 (m s⁻¹)", "u_CWP", "{:+.2f}"),
        ("CP降水 (mm day⁻¹)", "pr_CP", "{:+.2f}"),
        ("西部D20 (m)", "d20_West", "{:+.1f}"),
        ("东部D20 (m)", "d20_East", "{:+.1f}"),
    ]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    mark_table_header(table)
    hdr = table.rows[0].cells
    for cell, text in zip(hdr, ["指标", "2015/16", "2023/24", "2026"]):
        cell.text = text
    for label, key, fmt in rows:
        cells = table.add_row().cells
        cells[0].text = label
        for i, event in enumerate(["2015/16", "2023/24", "2026"], start=1):
            cells[i].text = f"{fmt.format(metrics[event][key])} / {fmt.format(metrics[event][key + '_june'])}"
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
    keep_table_together(table)


def format_compact_table(table, widths: list[float]) -> None:
    mark_table_header(table)
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


def add_expected_response_table(doc: Document, ordinary: dict[str, pd.DataFrame]) -> None:
    expected = ordinary["expected"]
    means = (
        expected.groupby(["target_label", "response"], as_index=False)[["observed", "expected", "residual"]]
        .mean(numeric_only=True)
        .set_index(["target_label", "response"])
    )
    add_heading(doc, "表2  SST条件下的观测—历史预期响应", level=2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["响应（1-6 月平均）", "2015/16", "2023/24", "2026 发展状态"]):
        cell.text = label
    rows = [
        ("Peng CWP u10 (m/s)", "cwp_u10"),
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
    keep_table_together(table)
    add_paragraph(
        doc,
        "每格为观测 / 历史预期（残差）。预期由1982-2014各日历月Niño3 SST回归得到；三个目标年份均排除在拟合之外。",
        size=9.2,
    )


def add_similarity_table(doc: Document, ordinary: dict[str, pd.DataFrame]) -> None:
    similarity = ordinary["similarity"]
    add_heading(doc, "表3  2026与2015、2023的分层相似性", level=2)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    headers = ["物理层", "参照事件", "相关 r", "中心化 RMSD", "标准差比"]
    for cell, label in zip(table.rows[0].cells, headers):
        cell.text = label
    layer_labels = {
        "Tropical-Pacific SST": "SST",
        "850 hPa zonal wind": "u850",
        "Precipitation": "降水",
        "Equatorial D20": "D20",
    }
    for layer in ("Tropical-Pacific SST", "850 hPa zonal wind", "Precipitation", "Equatorial D20"):
        subset = similarity.loc[similarity["layer"].eq(layer)].sort_values("candidate_year")
        for row in subset.itertuples(index=False):
            cells = table.add_row().cells
            cells[0].text = layer_labels[layer]
            cells[1].text = str(row.candidate_label)
            cells[2].text = f"{row.pattern_correlation:.3f}"
            cells[3].text = f"{row.centered_rmsd:.2f} {row.unit}"
            cells[4].text = f"{row.standard_deviation_ratio:.3f}"
    format_compact_table(table, [1.05, 1.35, 1.0, 1.65, 1.2])
    keep_table_together(table)
    add_paragraph(
        doc,
        "Taylor统计量分别约束形态相关、中心化误差和相对振幅；各变量独立评价，不合成总分。",
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
    analysis = load_ordinary_analysis()
    expected = analysis["expected"]
    wind_2026 = expected.loc[
        expected["target_year"].eq(2026) & expected["response"].eq("cwp_u10")
    ].sort_values("month")
    if wind_2026["month"].astype(int).tolist() != list(range(1, 7)):
        raise ValueError("Incomplete January-June 2026 Peng CWP u10 response")
    doc = Document()
    configure_styles(doc)
    doc.core_properties.title = "2026 ENSO海气耦合诊断"
    doc.core_properties.subject = "2015/16、2023/24与2026年1-6月观测对比"

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run("2026 ENSO 海气耦合诊断")
    set_run_font(run, size=20, bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(10)
    run = subtitle.add_run("2015/16与2023/24参照；观测截至2026年6月")
    set_run_font(run, size=10.5)

    add_heading(doc, "摘要", level=1)
    add_paragraph(
        doc,
        "本报告以2015/16的强耦合过程和2023/24的受限大气响应为参照，判断2026年1-6月热带太平洋海气耦合所处阶段。"
        "2026年初的表层增暖具有2023式东部先行特征，随后赤道温跃层形成盆尺度西浅东深结构，中西太平洋近地面西风也由间歇响应转为持续增强；"
        "中太平洋深对流则明显滞后，至后期才开始与海温和西风异常同位发展。"
        "因此，2026并非前两次事件的简单复刻，而是由东部表层信号向2015式动力耦合过渡的混合型演变；后续强度主要取决于深对流能否持续组织并维持风—温跃层反馈。",
    )

    add_heading(doc, "研究问题与方法依据", level=1)
    add_paragraph(
        doc,
        "2023/24表明较强海洋初始状态并不必然转化为同等强度的大气响应，因此2026需要回答的关键问题是："
        "当前增暖仍停留在东太平洋局地发展，还是已经建立能够自我维持的盆尺度海气正反馈。"
        "分析采用Peng et al.（2025）的Niño3 SST条件风响应，检验近地面西风相对历史预期是否充分；采用Jiang et al.（2026）的跨事件空间比较，识别SST、风和降水中心是否协同东移；"
        "并依据Li et al.（2024）的Bjerknes反馈链，将温跃层调整、表层增暖、低层风和深对流按物理过程逐环解释。"
        "Taylor统计用于分变量判断2026与历史事件的结构相似性。",
    )
    add_paragraph(
        doc,
        "Peng CWP风定义为5°S–5°N、140°E–160°W区域平均10 m纬向风；中太平洋降水采用Sun et al.（2016）的5°S–5°N、180°–140°W诊断区。"
        "区域时间序列用于实际—预期响应比较，850 hPa风用于刻画低层环流的空间组织，二者分别对应近地面动量响应和对流层低层结构。",
    )

    add_heading(doc, "1  资料与方法", level=1)
    add_paragraph(
        doc,
        "SST取自NOAA OISST；10 m风、850 hPa风和降水取自ERA5；20°C等温面深度（D20）取自ORAS5。"
        "2026年6月u10由ARCO-ERA5T逐小时场聚合为月平均，其余u10使用ERA5月平均资料。"
        "ERA5 850 hPa风、降水及ORAS5异常基准为1980-2014，OISST和Peng CWP u10为1982-2014；各变量逐日历月去气候态并去线性趋势。"
        "三次事件均比较发展年1-6月。",
    )
    add_paragraph(
        doc,
        "大气条件响应由1982-2014各日历月Niño3 SST回归给出，三个目标年份均排除在拟合之外。"
        "历史相似性采用Taylor（2001）的面积加权相关、中心化RMSD和标准差比，分别评价SST、u850、降水和D20。"
        "月度序列用于确定各过程的先后关系，空间场用于检验异常中心、符号和盆尺度结构是否一致。",
    )
    add_metric_table(doc, metrics)

    add_heading(doc, "2  三次事件的海气演变", level=1)
    add_heading(doc, "2.1  SST与850 hPa风", level=2)
    add_paragraph(
        doc,
        "2015年暖异常从东太平洋向中太平洋连成一体，西风异常位于暖区西侧并随增暖同步加强，构成有利于暖水东移的盆尺度结构。"
        "2023年的暖中心更局限于东部，中西太平洋西风既弱且缺乏持续的空间组织，大气响应未能与海温异常充分配合。"
        "2026年初同样由东部先行，但春季以后暖区向西扩展，低层西风在中西太平洋成带增强；这表明其表层形态虽然起始于2023式配置，后期环流组织已转向2015式耦合。",
    )
    add_figure(doc, EVENTS["2015/16"]["ssta"], "图1  2015/16发展年OISST海温异常与ERA5 850 hPa风异常。")
    add_figure(doc, EVENTS["2023/24"]["ssta"], "图2  2023/24发展年OISST海温异常与ERA5 850 hPa风异常。")
    add_figure(doc, EVENTS["2026"]["ssta"], "图3  2026年1-6月OISST海温异常与ERA5 850 hPa风异常。")

    add_heading(doc, "2.2  降水与850 hPa风", level=2)
    add_paragraph(
        doc,
        "2015年中太平洋正降水异常与西风中心协同发展，说明深对流加热已参与Walker环流调整，并可反过来维持低层西风。"
        "2023年对流中心未能随东部增暖充分向中太平洋扩展，风—降水之间的空间配合较弱。"
        "2026年前期中太平洋仍以对流受抑为主，即使近地面和850 hPa西风已经开始建立；后期正降水异常才进入中太平洋并与西风区重叠。"
        "这种先风后雨的次序说明动力响应早于深对流组织，完整的大气反馈建立晚于海洋和近地面风场调整。",
    )
    add_figure(doc, EVENTS["2015/16"]["precip"], "图4  2015/16发展年ERA5降水与850 hPa风异常。")
    add_figure(doc, EVENTS["2023/24"]["precip"], "图5  2023/24发展年ERA5降水与850 hPa风异常。")
    add_figure(doc, EVENTS["2026"]["precip"], "图6  2026年1-6月ERA5降水与850 hPa风异常。")

    add_heading(doc, "2.3  D20与赤道u850", level=2)
    add_paragraph(
        doc,
        "2015年的赤道温跃层表现为西部持续变浅、东部持续加深，反映暖水体向东再分配并为东太平洋增暖提供次表层支撑。"
        "2023年虽有东部加深，但西部浅化较弱，盆尺度倾斜和相应的动力反馈均受到限制。"
        "2026年先出现东部加深，随后西部浅化明显发展，至后期形成连贯的西浅东深结构。"
        "因此，2026的海洋动力演变已由局地东部信号转为盆尺度调整，这一层面更接近2015而非2023。",
    )
    add_figure(doc, EVENTS["2015/16"]["d20"], "图7  2015/16发展年ORAS5赤道D20异常与ERA5赤道u850。")
    add_figure(doc, EVENTS["2023/24"]["d20"], "图8  2023/24发展年ORAS5赤道D20异常与ERA5赤道u850。")
    add_figure(doc, EVENTS["2026"]["d20"], "图9  2026年1-6月ORAS5赤道D20异常与ERA5赤道u850。")

    add_heading(doc, "3  SST条件下的大气响应", level=1)
    add_expected_response_table(doc, analysis)
    add_figure(
        doc,
        ORDINARY_FIGURES["expected"],
        "图10  三次事件的观测大气响应及Niño3 SST条件历史预期；回归期为1982-2014。",
    )
    response_paragraph = add_paragraph(
        doc,
        "SST条件回归把事件的海温振幅转换为同月份的历史大气响应基准。2015年的近地面西风普遍高于该基准，体现了强事件中的大气放大；"
        "2023年的风和降水则同时低于预期，表明海温异常未能有效组织中西太平洋大气响应。"
        "2026呈现不同的过程分离：近地面西风在春季以后持续高于SST条件预期，而中太平洋降水在大部分月份仍低于预期。"
        "这说明2026当前的限制环节已不是海面附近的西风响应，而是深对流加热向中太平洋迁移并维持的速度。",
    )
    response_paragraph.paragraph_format.keep_together = True

    add_heading(doc, "4  2026年耦合建立次序", level=1)
    add_figure(
        doc,
        ORDINARY_FIGURES["staged"],
        "图11  2026年1-6月D20、Niño3 SST、Peng CWP u10及CP降水的观测与历史条件响应；背景色表示依据观测演变划分的过程段。",
    )
    add_heading(doc, "4.1  温跃层调整（图11a）", level=2)
    add_paragraph(
        doc,
        "东部温跃层先于西部出现显著变化，说明初始信号是局地次表层暖水，而非完整的盆尺度倾斜。"
        "春季西部浅化随后建立西浅东深结构；暖水由此向东再分配并削弱东部混合层的冷水补给，使海洋初始记忆转化为表层增暖的动力支撑。",
    )
    add_heading(doc, "4.2  东太平洋表层增暖（图11b）", level=2)
    add_paragraph(
        doc,
        "Niño3增暖并非匀速发展：年初快速建立，春季短暂停滞，随后在温跃层倾斜明显加强后再次加速。"
        "这一相位关系把表层升温与海洋动力过程联系起来。东部温跃层加深削弱冷水夹卷和上翻对混合层的冷却，西部浅化则对应暖水向东输送；"
        "两者共同使已有的东部暖异常更容易维持和扩展。表层增暖的后期加速因而不是孤立的热力异常，而是盆尺度温跃层调整在海表的响应。",
    )
    add_heading(doc, "4.3  低层纬向风响应（图11c）", level=2)
    add_paragraph(
        doc,
        "近地面纬向风在年初仍有月际反转，显示大气尚未对东部增暖形成稳定响应。春季以后，CWP西风转为持续并逐步高于Niño3 SST所对应的历史预期，"
        "同时850 hPa西风带在空间上向中太平洋组织。西风异常有利于削弱赤道信风、推动暖水向东传播，并加强已出现的温跃层倾斜。"
        "与2023年持续偏弱的风响应不同，2026的近地面风场已经从反馈的限制环节转变为海洋调整的支持环节；其增强也不能仅由同期Niño3振幅解释。",
    )
    add_heading(doc, "4.4  深对流响应（图11d）", level=2)
    convection_paragraph = add_paragraph(
        doc,
        "中太平洋降水是四个环节中响应最晚的一项。前期东部海温已转暖、温跃层已开始调整，但中太平洋仍受对流抑制，说明海表热力异常尚未有效转化为该区域的深对流加热。"
        "后期降水异常转正并接近SST条件响应，正降水中心开始与西风异常重叠。深对流释放的潜热可加强东西向气压梯度和Walker环流异常，从而帮助维持中西太平洋西风；"
        "因此它决定了已经建立的风—海洋动力联系能否继续自我强化。"
        "截至6月，观测顺序为东部次表层和表层异常先出现，盆尺度温跃层与西风随后强化，深对流最后追赶。反馈链已具备主要空间结构，但其持续性仍取决于中太平洋对流在夏秋季的维持。",
    )
    convection_paragraph.paragraph_format.keep_together = True

    add_heading(doc, "5  历史相似性与演变判断", level=1)
    add_similarity_table(doc, analysis)
    similarity_paragraph = add_paragraph(
        doc,
        "分层相似性给出一致的物理图景：2026的表层SST空间形态更接近2023，而低层纬向风和赤道D20更接近2015；降水场尚未稳定归入任一参照事件。"
        "这意味着单看海温会高估2026与2023的相似程度，单看海洋动力场又会忽略深对流尚未完全跟上的事实。"
        "综合各层但不压缩为单一分数，2026可判断为从东部先行增暖向盆尺度动力耦合过渡的混合型过程。",
    )
    similarity_paragraph.paragraph_format.keep_together = True
    outlook_paragraph = add_paragraph(
        doc,
        "若中太平洋正降水异常持续并与西风带保持同位，现有温跃层倾斜和暖水东移将更可能延续，演变方向将进一步接近2015式盆尺度耦合。"
        "若深对流再次减弱，西风异常可能失去大尺度加热支撑，事件则可能保留较强的东部表层特征而难以维持同等强度的正反馈。"
        "CPC和WMO同期业务展望均支持继续增强，但最终振幅仍应由后续对流—风—海洋三者的协同演变判断。",
    )
    outlook_paragraph.paragraph_format.keep_together = True

    add_heading(doc, "6  结论", level=1)
    add_paragraph(
        doc,
        "2026年初由东太平洋表层和次表层异常启动，随后形成盆尺度温跃层倾斜，并伴随中西太平洋近地面及850 hPa西风的持续加强。"
        "这一动力结构已明显区别于2023/24的受限风响应，并向2015/16的强耦合配置靠近；但中太平洋深对流建立较晚，仍是当前反馈链中最不充分的一环。"
        "因此，2026下一阶段的关键不是海温是否继续单独升高，而是深对流能否持续维持西风，并使风—温跃层—SST反馈保持盆尺度协同。",
    )

    add_heading(doc, "参考方法与资料", level=1)
    references_paragraph = add_paragraph(
        doc,
        "Peng et al. (2025), Nature Geoscience, doi:10.1038/s41561-025-01700-9：CWP（5°S–5°N、140°E–160°W）u10、Niño3条件回归及实际—预期响应。\n"
        "Jiang et al. (2026), Geophysical Research Letters, doi:10.1029/2026GL123227：东太平洋先行增暖、中太平洋风—降水响应及跨事件回归比较。\n"
        "Li et al. (2024), Geophysical Research Letters, doi:10.1029/2024GL109874：SST—降水加热—气压—风应力的大气Bjerknes反馈分环诊断。\n"
        "Sun et al. (2016), Advances in Atmospheric Sciences, doi:10.1007/s00376-015-5018-6：Niño3 SST对应的中太平洋降水和风应力响应，以及5°S–5°N、180°–140°W诊断区。\n"
        "Kim, Tian & Yu (2025), npj Climate and Atmospheric Science, doi:10.1038/s41612-024-00890-0：D20、西太平洋暖水体和西—中太平洋纬向风的事件演变与跨事件对比。\n"
        "Taylor (2001), Journal of Geophysical Research, doi:10.1029/2000JD900719：相关、中心化RMSD和标准差比。\n"
        "Zuo et al. (2019), Ocean Science, doi:10.5194/os-15-779-2019：ORAS5系统、资料同化与海洋状态重建。\n"
        "NOAA CPC ENSO Diagnostic Discussion, 9 July 2026；WMO El Niño Update, 3 July 2026。",
        size=9.2,
    )
    references_paragraph.paragraph_format.keep_together = True

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build_doc()
