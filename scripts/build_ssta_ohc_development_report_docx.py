#!/usr/bin/env python3
"""Build the Chinese SSTA--OHC development-stage report from Design Report.

The retained Design Report DOCX is the visual authority.  The script edits a
clone, then re-packages the result so preserve-only template parts (styles,
fonts, numbering, theme, footers, and cover art) stay byte-for-byte identical
to the retained reference.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(
    "/Users/daiyue/.codex/plugins/cache/openai-curated-remote/"
    "openai-templates/0.1.1/skills/artifact-template-design-report/"
    "assets/reference.docx"
)
REFERENCE_SHA256 = "ba1e11258ff52659318a321462a5e598c7bed33cf991329eb91150788fcd1a7b"
WORK_DIR = Path("/private/tmp/maryland_ohc_report.eU6nlr")
SCRATCH_DOCX = WORK_DIR / "ssta_ohc_report_scratch.docx"
OUTPUT = (
    ROOT
    / "outputs/research_2026/reports/ENSO发展期_SSTA-OHC不同步_阶段性汇报_修订版_20260815.docx"
)
DOCUMENT_SKILL_SCRIPTS = Path(
    "/Users/daiyue/.codex/plugins/cache/openai-primary-runtime/"
    "documents/26.813.12317/skills/documents/scripts"
)
sys.path.insert(0, str(DOCUMENT_SKILL_SCRIPTS))
from table_geometry import apply_table_geometry  # noqa: E402


FIGURES = {
    "1997_ssta": ROOT
    / "outputs/research_2026/event_1997_monthly_panels_1980_2024_detrended/"
    "fig_1997_jan_jun_oisst_ssta_era5_850_windA_1980_2024.png",
    "1997_ohc": ROOT
    / "outputs/research_2026/soda3_ohc300_monthly_wind_panels_1980_2024_detrended/"
    "fig_1997_jan_jun_soda3_ohc300_era5_850_windA_1980_2024.png",
    "2015_ssta": ROOT
    / "outputs/research_2026/event_2015_monthly_panels_1980_2024_detrended/"
    "fig_2015_jan_jun_oisst_ssta_era5_850_windA_1980_2024.png",
    "2015_ohc": ROOT
    / "outputs/research_2026/soda3_ohc300_monthly_wind_panels_1980_2024_detrended/"
    "fig_2015_jan_jun_soda3_ohc300_era5_850_windA_1980_2024.png",
    "2023_ssta": ROOT
    / "outputs/research_2026/event_2023_monthly_panels_1980_2024_detrended/"
    "fig_2023_jan_jun_oisst_ssta_era5_850_windA_1980_2024.png",
    "2023_ohc": ROOT
    / "outputs/research_2026/soda3_ohc300_monthly_wind_panels_1980_2024_detrended/"
    "fig_2023_jan_jun_soda3_ohc300_era5_850_windA_1980_2024.png",
    "vertical": ROOT
    / "outputs/research_2026/soda3_ohc_vertical_sections_1980_2024_detrended/"
    "fig_1997_2015_2023_jan_jun_soda3_ohc_vertical_sections_1980_2024_detrended.png",
    "census": ROOT
    / "outputs/research_2026/soda3_all_warm_event_ssta_ohc_mismatch/"
    "fig_13_soda3_warm_events_fep_ssta_ohc_jan_jun_1982_2024.png",
    "trajectory": ROOT
    / "outputs/research_2026/soda3_ssta_ohc_pattern_analysis/"
    "fig_fep_mismatch_event_phase_trajectories.png",
    "persistence": ROOT
    / "outputs/research_2026/soda3_ssta_ohc_pattern_analysis/"
    "fig_fep_joint_warming_persistence_vs_mature_nino34.png",
}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
CJK_FONT = "Noto Sans CJK SC"
CJK_FONT_FILE = ROOT / "outputs/research_2026/report_fonts/NotoSansCJKsc-Regular.otf"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def set_run_font(
    run,
    *,
    size: float | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    color: str | None = None,
    latin: str | None = None,
    east_asia: str = CJK_FONT,
) -> None:
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    contains_cjk = any("\u3400" <= char <= "\u9fff" for char in run.text)
    resolved_font = CJK_FONT if contains_cjk else latin
    if resolved_font is not None:
        run.font.name = resolved_font
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    if resolved_font is not None:
        r_fonts.set(qn("w:ascii"), resolved_font)
        r_fonts.set(qn("w:hAnsi"), resolved_font)
        r_fonts.set(qn("w:cs"), resolved_font)
    r_fonts.set(qn("w:eastAsia"), CJK_FONT if contains_cjk else east_asia)


def clear_paragraph(paragraph: Paragraph) -> None:
    p = paragraph._p
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)


def replace_paragraph(
    paragraph: Paragraph,
    text: str,
    *,
    size: float | None = None,
    bold: bool | None = None,
    color: str | None = None,
    latin: str | None = None,
) -> None:
    clear_paragraph(paragraph)
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color, latin=latin)


def format_all_runs(paragraph: Paragraph) -> None:
    for run in paragraph.runs:
        set_run_font(run)


def add_body(doc: Document, text: str, *, after: float = 6.0) -> Paragraph:
    paragraph = doc.add_paragraph(style="normal")
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = 1.15
    paragraph.paragraph_format.widow_control = False
    run = paragraph.add_run(text)
    set_run_font(run, size=11.0, latin="Helvetica Neue")
    return paragraph


def add_labeled_body(doc: Document, label: str, text: str) -> Paragraph:
    paragraph = doc.add_paragraph(style="normal")
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.15
    first = paragraph.add_run(label)
    set_run_font(first, size=11.0, bold=True, latin="Helvetica Neue")
    second = paragraph.add_run(text)
    set_run_font(second, size=11.0, latin="Helvetica Neue")
    return paragraph


def add_heading(doc: Document, text: str, level: int, *, page_break: bool = False) -> Paragraph:
    if page_break:
        doc.add_page_break()
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    paragraph.paragraph_format.keep_with_next = False
    paragraph.paragraph_format.keep_together = False
    paragraph.paragraph_format.page_break_before = False
    paragraph.paragraph_format.widow_control = False
    run = paragraph.add_run(text)
    set_run_font(run)
    return paragraph


def add_list_paragraph(
    doc: Document,
    prototype_xml,
    lead: str,
    text: str,
) -> Paragraph:
    paragraph = doc.add_paragraph(style="normal")
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.15
    paragraph.paragraph_format.keep_with_next = False
    paragraph.paragraph_format.keep_together = False
    paragraph.paragraph_format.page_break_before = False
    paragraph.paragraph_format.widow_control = False
    first = paragraph.add_run(lead)
    set_run_font(first, size=11.0, bold=bool(lead), latin="Helvetica Neue")
    second = paragraph.add_run(text)
    set_run_font(second, size=11.0, latin="Helvetica Neue")
    return paragraph


def add_callout(doc: Document, prototype_xml, label: str, text: str) -> Paragraph:
    clone = deepcopy(prototype_xml)
    doc._body._element.insert(-1, clone)
    paragraph = Paragraph(clone, doc._body)
    clear_paragraph(paragraph)
    first = paragraph.add_run(label)
    set_run_font(first, size=11.0, bold=True, latin="Helvetica Neue")
    second = paragraph.add_run(text)
    set_run_font(second, size=11.0, latin="Helvetica Neue")
    return paragraph


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_comparison_table(doc: Document, prototype_xml) -> Table:
    clone = deepcopy(prototype_xml)
    doc._body._element.insert(-1, clone)
    table = Table(clone, doc._body)
    values = [
        ["事件", "表层—整层时序", "连续垂向结构与过程含义"],
        [
            "1997",
            "FEP OHC 2月转正，SSTA 3月转正：整层领先约1个月。",
            "1—3月中太平洋约100—200 m暖核强，随后明显向东、向上扩展；属于次表层预置后表层响应。",
        ],
        [
            "2015",
            "1月二者同为正；2—3月SSTA转负而OHC保持弱正，随后4月重新同步增强。",
            "中东太平洋次表层暖舌持续存在，说明短期表面冷却没有消除海洋热储备。",
        ],
        [
            "2023",
            "2月SSTA +0.230°C，而0—300 m OHC −0.040 GJ m⁻²；3月起共同转正。",
            "远东表层先响应，整层热含量约一个月内追上；暖异常更浅、更偏东，深层支撑弱于1997/2015。",
        ],
    ]
    for row_index, row in enumerate(table.rows):
        for col_index, cell in enumerate(row.cells):
            cell.text = values[row_index][col_index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cell.paragraphs:
                paragraph.alignment = (
                    WD_ALIGN_PARAGRAPH.CENTER if col_index == 0 else WD_ALIGN_PARAGRAPH.LEFT
                )
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.05
                for run in paragraph.runs:
                    set_run_font(
                        run,
                        size=9.2 if row_index else 9.5,
                        bold=row_index == 0,
                        latin="Helvetica Neue",
                    )
    set_repeat_table_header(table.rows[0])
    apply_table_geometry(
        table,
        [1080, 3150, 5130],
        table_width_dxa=9360,
        indent_dxa=120,
        cell_margins_dxa={"top": 100, "bottom": 100, "start": 120, "end": 120},
    )
    return table


def add_figure(
    doc: Document,
    path: Path,
    caption: str,
    *,
    width: float = 6.35,
    alt_text: str,
) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    paragraph = doc.add_paragraph(style="normal")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(2)
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.keep_with_next = False
    paragraph.paragraph_format.keep_together = False
    paragraph.paragraph_format.widow_control = False
    run = paragraph.add_run()
    run.add_picture(str(path), width=Inches(width))
    doc_pr = paragraph._p.find(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr")
    if doc_pr is not None:
        doc_pr.set("descr", alt_text)

    caption_paragraph = doc.add_paragraph(style="normal")
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_paragraph.paragraph_format.space_before = Pt(0)
    caption_paragraph.paragraph_format.space_after = Pt(6)
    caption_paragraph.paragraph_format.keep_with_next = False
    caption_paragraph.paragraph_format.keep_together = False
    caption_paragraph.paragraph_format.widow_control = False
    caption_run = caption_paragraph.add_run(caption)
    set_run_font(
        caption_run,
        size=8.0,
        color="666666",
        latin="Helvetica Neue",
    )


def set_cell_text(cell, text: str, *, align: WD_ALIGN_PARAGRAPH) -> None:
    paragraph = cell.paragraphs[0]
    for extra in cell.paragraphs[1:]:
        cell._tc.remove(extra._p)
    clear_paragraph(paragraph)
    paragraph.alignment = align
    paragraph.paragraph_format.space_after = Pt(0)
    for index, line in enumerate(text.split("\n")):
        if index:
            paragraph.add_run().add_break()
        run = paragraph.add_run(line)
        set_run_font(run, size=12.0, color="666666", latin="Helvetica Neue")


def edit_cover(doc: Document) -> None:
    title = next(paragraph for paragraph in doc.paragraphs if paragraph.style.name == "Title")
    replace_paragraph(
        title,
        "ENSO发展期\nSSTA—OHC不同步",
        size=32.0,
        bold=True,
        latin="Helvetica Neue",
    )
    cover_table = doc.tables[0]
    set_cell_text(
        cover_table.cell(0, 0),
        "1997、2015与2023对比：\n从平面异常、连续垂向结构到13次暖事件普查",
        align=WD_ALIGN_PARAGRAPH.LEFT,
    )
    set_cell_text(
        cover_table.cell(0, 2),
        "阶段性研究汇报\n2026年8月15日",
        align=WD_ALIGN_PARAGRAPH.LEFT,
    )


def add_report_content(doc: Document, bullet_xml, numbered_xml, callout_xml) -> None:
    add_heading(doc, "执行摘要", 1, page_break=True)
    add_body(
        doc,
        "本阶段工作的出发点是一个简单但关键的问题：发展期海表温度异常（SSTA）是否能够代表0—300 m上层海洋热含量异常（OHC）的演变？对1997、2015和2023的逐月比较显示，答案是否定的。三次强暖事件都存在表层与整层不同步，但不同步方向、垂向构型和后续命运并不相同。",
    )
    add_callout(
        doc,
        callout_xml,
        "核心判断。",
        "“出现异号”本身不是强事件的充分特征；异号后一个月能否转入并维持表层—整层共同增暖，才是当前13事件样本中更稳定的过程信号。2023是唯一一次早期、经同基准核验、次月完成转换并持续到6月的案例。",
    )
    add_heading(doc, "一页结论", 2)
    add_list_paragraph(
        doc,
        bullet_xml,
        "1997：",
        "OHC先转正，随后SSTA快速增强；典型的次表层暖量预置—向东上翻过程。",
    )
    add_list_paragraph(
        doc,
        bullet_xml,
        "2015：",
        "表层在2—3月短暂偏冷，但OHC维持正异常；表面波动没有消除次表层支撑。",
    )
    add_list_paragraph(
        doc,
        bullet_xml,
        "2023：",
        "2月远东SSTA已转暖而OHC仍略冷，3月OHC迅速追上；属于表层先行—整层追赶。",
    )
    add_list_paragraph(
        doc,
        bullet_xml,
        "跨事件：",
        "13次暖事件中有5次出现过FEP表暖、OHC冷，但只有1982和2023次月转为共同正异常；1982发生在5月且OHC几乎等于零。",
    )

    add_heading(doc, "研究设计与可比性", 1, page_break=True)
    add_body(
        doc,
        "平面图比较OISST SSTA与SODA3.15.2的0—300 m OHC异常，并叠加ERA5 850 hPa风异常。三例图的经度统一为120°E—80°W；连续垂向图采用5°S—5°N余弦加权平均和SODA原生深度层，不再进行分箱。",
    )
    add_labeled_body(
        doc,
        "异常定义。",
        "早期平面图与剖面沿用各自绘图口径：OISST为1982—2024逐月去趋势异常，SODA OHC/垂向结构为1980—2024逐月去趋势异常。随后13事件普查重新把OISST与SODA统一到1982—2024同月线性基准，并限制在具有完整0—300 m资料的共同海洋格点，用于严格判断正负号。",
    )
    add_labeled_body(
        doc,
        "量的含义。",
        "OHC′ = ρ₀Cp∫₀³⁰⁰ᵐT′dz，单位GJ m⁻²；垂向图展示的是ρ₀CpT′热含量密度异常，单位MJ m⁻³，因此能够定位不同深度的正负补偿，而不是再次进行垂向积分。",
    )
    add_callout(
        doc,
        callout_xml,
        "核验结果。",
        "2023年2月FEP共同覆盖区内，OISST与SODA表层温度异常均已转暖，而0—300 m OHC仍为微弱冷异常。独立重算及0—80 m、80—300 m分层闭合均复现这一符号差异，因此它不是积分代码错误。",
    )

    add_heading(doc, "关键发现", 1, page_break=True)
    add_heading(doc, "三种不同步路径", 2)
    add_body(
        doc,
        "若只看成熟期海温，三次事件都可归入强暖事件；若把表层与整层热状态放在同一时间轴上，则出现三条不同路径。",
    )
    add_heading(doc, "1997：整层领先", 2)
    add_body(
        doc,
        "FEP整层热含量先于海表转暖。年初中太平洋次表层暖核已经建立，随后暖异常向东、向上扩展，海表才进入快速增暖阶段。这是一条典型的“次表层预置—表层响应”路径。",
    )
    add_heading(doc, "2015：次表层支撑下的表面回冷", 2)
    add_body(
        doc,
        "年初表层与整层已共同偏暖，但海表在晚冬至早春短暂回冷，整层热含量仍维持暖异常。该路径说明表面受短期通量或平流扰动时，次表层储热可以继续支撑后续发展。",
    )
    add_heading(doc, "2023：表层先行与整层追赶", 2)
    add_body(
        doc,
        "远东太平洋海表在2月率先转暖，整层热含量仍略冷，随后约一个月内追上并转入共同增暖。与前两例相比，暖异常更浅、更偏东，早期深层支撑也更弱。",
    )
    add_labeled_body(
        doc,
        "解释边界。",
        "2015的“同月转正”仅指首次正值；2—3月SSTA重新转负，说明首次过零点不是稳定阈值。1997、2015、2023的先后顺序各不相同，不能把“表层先暖”当作强东部型事件的必要条件。",
    )

    event_pages = [
        (
            "1997：整层先行、随后表层爆发",
            "FEP中OHC在2月已转正，而SSTA到3月才转正；3—6月二者同步快速增强。空间上，暖OHC沿赤道从中太平洋向东扩展，5—6月远东SSTA随之显著升高。",
            "1997_ssta",
            "图1（a）  1997年1—6月OISST海温异常及ERA5 850 hPa风异常。填色表示SSTA，箭头表示风异常；SSTA采用1982—2024年同月线性去趋势基准。",
            "1997年逐月SSTA与850百帕风异常地图",
            "1997_ohc",
            "图1（b）  1997年1—6月SODA3 0—300 m OHC异常及ERA5 850 hPa风异常。填色表示整层热含量异常，箭头表示风异常；OHC采用1980—2024年同月线性去趋势基准。",
            "1997年逐月0至300米OHC与850百帕风异常地图",
        ),
        (
            "2015：次表层持续暖、表层短暂回冷",
            "2015年1月表层与OHC均为正，但2—3月FEP SSTA回到负值，OHC仍保持弱正。4月以后两者重新共同增强。该事件说明表面受短期通量或平流影响而波动时，整层热储备可以继续存在。",
            "2015_ssta",
            "图2（a）  2015年1—6月OISST海温异常及ERA5 850 hPa风异常。填色和箭头定义同图1（a）。",
            "2015年逐月SSTA与850百帕风异常地图",
            "2015_ohc",
            "图2（b）  2015年1—6月SODA3 0—300 m OHC异常及ERA5 850 hPa风异常。填色和箭头定义同图1（b）。",
            "2015年逐月0至300米OHC与850百帕风异常地图",
        ),
        (
            "2023：远东表层先暖、整层约一个月追上",
            "2023年1月FEP表层与OHC均偏冷；2月SSTA首先转正，而0—300 m OHC仍略低于零；3月两者共同转正并持续增强到6月。更宽的140°W—80°W平均会稀释这一信号，说明最早不同步集中在远东FEP。",
            "2023_ssta",
            "图3（a）  2023年1—6月OISST海温异常及ERA5 850 hPa风异常。2月远东FEP已出现局地暖异常；填色和箭头定义同图1（a）。",
            "2023年逐月SSTA与850百帕风异常地图",
            "2023_ohc",
            "图3（b）  2023年1—6月SODA3 0—300 m OHC异常及ERA5 850 hPa风异常。2月远东整层异常仍接近零或略冷；填色和箭头定义同图1（b）。",
            "2023年逐月0至300米OHC与850百帕风异常地图",
        ),
    ]
    for title, text, ssta_key, ssta_caption, ssta_alt, ohc_key, ohc_caption, ohc_alt in event_pages:
        add_heading(doc, title, 1, page_break=True)
        add_body(doc, text, after=4)
        add_figure(doc, FIGURES[ssta_key], ssta_caption, width=5.95, alt_text=ssta_alt)
        add_figure(doc, FIGURES[ohc_key], ohc_caption, width=5.95, alt_text=ohc_alt)
        add_body(
            doc,
            {
                "1997_ssta": "图1表明，1997年整层增暖先于东部海表持续转暖，随后二者同步快速增强。",
                "2015_ssta": "图2表明，2015年海表短暂回冷并未消除上层海洋热储备，次表层暖舌持续支撑后续发展。",
                "2023_ssta": "图3表明，2023年远东海表先行增暖，3月以后表层与整层才进入一致发展。",
            }[ssta_key],
        )

    add_heading(doc, "连续垂向结构：不同步来自哪里", 1, page_break=True)
    add_body(
        doc,
        "无分箱剖面把平面平均重新展开到深度—经度空间。它显示，SSTA与OHC不同步不是简单的数据冲突，而是上层海洋中暖异常的位置、深度和向东上翻速度不同。",
        after=4,
    )
    add_figure(
        doc,
        FIGURES["vertical"],
        "图4  1997、2015和2023年1—6月赤道太平洋热含量密度异常的连续垂向剖面。5°S—5°N余弦加权；SODA原生深度层；经度120°E—80°W；未分箱。",
        width=6.45,
        alt_text="三次事件一月至六月连续深度经度热含量密度异常剖面",
    )
    add_heading(doc, "剖面解释", 2)
    add_labeled_body(doc, "1997。", "年初中太平洋约100—200 m存在显著暖核，春季向东上翻并形成深厚的东部暖异常，支持整层领先于表层的判断。")
    add_labeled_body(doc, "2015。", "次表层暖舌从年初持续连接中、东太平洋；即使海表短暂偏冷，深层暖异常仍然延续，显示出较强的海洋记忆。")
    add_labeled_body(doc, "2023。", "年初暖量更偏西、偏深，远东海表先变暖，暖舌随后向东上翻；到初夏，深层支撑仍弱于1997和2015。")

    add_heading(doc, "1980年后暖事件普查", 1, page_break=True)
    add_body(
        doc,
        "为判断2023是否只是常见过零波动，我们把同一FEP定义推广到13次暖事件：1982、1986、1991、1994、1997、2002、2004、2006、2009、2015、2018、2019和2023，并统一基准、共同覆盖区和面积权重。",
        after=4,
    )
    add_figure(
        doc,
        FIGURES["census"],
        "图5  13次暖事件1—6月FEP OISST SSTA、SODA3 0—300 m OHC及首次转正月差。黑框表示SSTA>0且OHC<0；紫色为2023。",
        width=6.35,
        alt_text="十三次暖事件的FEP SSTA和OHC月份矩阵与首次转正月差",
    )
    add_heading(doc, "普查结果", 2)
    add_body(
        doc,
        "普查显示，发展期出现“表层已暖、整层仍冷”并非2023独有；但多数事件的异号只是短暂过零或随后重新冷却。若进一步要求异号发生较早、次月完成表层—整层共同转暖并持续发展，2023成为样本中唯一稳健保留的案例。1982也出现了先表层、后整层的顺序，但发生更晚且整层异常接近零线。",
    )

    add_heading(doc, "异号之后：转换还是失败", 1, page_break=True)
    add_body(
        doc,
        "五次异号事件的相空间轨迹揭示真正的分水岭。1982和2023在异号后的下个月进入表层与OHC共同为正的象限；2002、2004和2006则向冷却方向返回。",
        after=4,
    )
    add_figure(
        doc,
        FIGURES["trajectory"],
        "图6  五次FEP异号事件的1—6月相空间轨迹。横轴为0—300 m OHC异常，纵轴为OISST SSTA；数字1—6表示月份。",
        width=6.35,
        alt_text="五次SSTA正OHC负事件一月至六月相空间轨迹",
    )
    add_labeled_body(
        doc,
        "最强反例。",
        "2006年的表暖—整层冷差异比2023更强，但随后表层与整层同时转向冷却；2023则在下一月完成共同增暖。异号幅度本身因此不能预示事件能否继续发展。",
    )

    add_heading(doc, "共同增暖与成熟期强度", 1, page_break=True)
    add_body(
        doc,
        "把13次事件放在同一统计框架中，持续共同为正比首次转正先后更能组织样本；到6月形成的表层—整层一致暖态与随后成熟期强度联系最强。",
        after=4,
    )
    add_figure(
        doc,
        FIGURES["persistence"],
        "图7  共同正异常持续性及6月联合暖度与成熟期DJF Niño-3.4异常的关系。置换检验10万次；结果为探索性且未作多重比较校正。",
        width=6.35,
        alt_text="共同正异常持续月数和六月联合暖度对成熟期尼诺三点四强度散点图",
    )
    add_heading(doc, "研究含义", 2)
    add_body(
        doc,
        "结果显示，共同正异常维持越久，事件成熟期通常越强；与首次转正时序相比，晚春表层—整层联合暖度能够更清楚地区分事件后续强度。该关系在扩展到更宽的东太平洋区域后仍然成立。",
    )
    add_body(
        doc,
        "物理上，SSTA描述海气界面的即时状态，OHC表示上层海洋记忆。两者短期不同步并不矛盾，关键在于随后是否合流并维持。",
    )

    add_heading(doc, "建议", 1, page_break=True)
    add_body(
        doc,
        "下一阶段应从“描述不同步”转向“解释2023为何完成整层追赶，而2006没有”。优先级如下。",
    )
    add_list_paragraph(
        doc,
        numbered_xml,
        "锁定2023与2006的2—3月热收支。",
        "统一计算水平热平流、垂向交换/混合、表面净热通量与剩余项，判断OHC追赶的直接来源。",
    )
    add_list_paragraph(
        doc,
        numbered_xml,
        "把连续垂向结构与传播代理配对。",
        "同时比较D20、SSH和Kelvin波到达时间，检验暖舌东移与上翻是否先于FEP整层转正。",
    )
    add_list_paragraph(
        doc,
        numbered_xml,
        "做独立资料敏感性。",
        "用TAO关键经线和ORAS5复核2023年2月的表层—整层符号与3月转换，避免结论依赖单一再分析。",
    )
    add_list_paragraph(
        doc,
        numbered_xml,
        "预先固定判据并扩展样本。",
        "冻结FEP范围、共同覆盖区和转换判据；将13事件结果作为探索样本，不据此拟合普适硬阈值。",
    )
    add_heading(doc, "结论", 2)
    add_body(
        doc,
        "当前证据支持把2023描述为一次“远东表层先响应—上层海洋约一个月追赶—随后持续共同增暖”的事件，而不是简单的SSTA/OHC永久脱耦。1997展示整层领先，2015展示次表层支撑下的表层回冷，2023展示表层先行；三者共同说明，发展期ENSO需要同时观察界面状态、垂向热结构和后续持续性。",
    )
    add_callout(
        doc,
        callout_xml,
        "适合写入论文的谨慎表述。",
        "2023的早期FEP表层—整层不同步在13事件样本中具有独特性，但目前只能作为机制线索；是否由水平热输送、Kelvin波上翻或局地表面通量主导，仍需热预算和独立资料闭合。",
    )

    add_heading(doc, "附录", 1, page_break=True)
    add_heading(doc, "样本与区域", 2)
    add_body(
        doc,
        "主样本为13次发展年暖事件：1982、1986、1991、1994、1997、2002、2004、2006、2009、2015、2018、2019、2023。主区域FEP=5°S—5°N、90°W—80°W；宽区域为5°S—5°N、140°W—80°W。1987/88作为连续事件敏感性样本，不进入主统计。",
    )
    add_heading(doc, "数据与计算", 2)
    add_labeled_body(
        doc,
        "海表：",
        "NOAA OISST月平均SST；同月线性去趋势异常；严格比较时插值到SODA网格并使用共同完整0—300 m海洋覆盖区。",
    )
    add_labeled_body(
        doc,
        "海洋：",
        "SODA3.15.2月平均温度；OHC按ρ₀Cp对0—300 m分层积分；连续垂向图使用原生深度层热含量密度异常。",
    )
    add_labeled_body(
        doc,
        "权重：",
        "区域平均采用cos(latitude)面积权重；正负号比较和统计均在相同月份、相同区域和相同完整柱网格上进行。",
    )
    add_heading(doc, "文档边界", 2)
    add_body(
        doc,
        "本报告仅呈现经质量控制后的研究图件、方法说明与结果解释，不附原始数据、派生数据表或本地数据文件路径。图中数值仅用于展示异常演变与跨事件关系。",
    )
    add_heading(doc, "限制", 2)
    add_body(
        doc,
        "13事件统计属于小样本探索，相关检验未作多重比较校正；1982与2023的异号OHC都接近零线，必须结合空间图、SODA表层温度和独立资料判断。所有结果描述演变与关联，不单独证明因果。",
    )


def patch_header(header_xml: bytes) -> bytes:
    root = etree.fromstring(header_xml)
    for child in list(root):
        root.remove(child)
    etree.SubElement(root, qn("w:p"))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def patch_styles(styles_xml: bytes) -> bytes:
    root = etree.fromstring(styles_xml)
    for tag in ("keepNext", "keepLines", "pageBreakBefore", "widowControl", "suppressLineNumbers"):
        for node in root.xpath(f"//w:pPr/w:{tag}", namespaces=NS):
            node.getparent().remove(node)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def patch_settings(settings_xml: bytes) -> bytes:
    root = etree.fromstring(settings_xml)
    update = root.find(qn("w:updateFields"))
    if update is None:
        update = etree.Element(qn("w:updateFields"))
        root.append(update)
    update.set(qn("w:val"), "true")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def patch_document(document_xml: bytes) -> bytes:
    root = etree.fromstring(document_xml)
    content_nodes = root.xpath("//w:sdt/w:sdtContent", namespaces=NS)
    if not content_nodes:
        return document_xml
    content = content_nodes[0]
    existing = content.findall(qn("w:p"))
    if len(existing) < 2:
        return document_xml

    entries = [
        ("执行摘要", "2", 1),
        ("一页结论", "2", 2),
        ("研究设计与可比性", "3", 1),
        ("关键发现", "4", 1),
        ("三种不同步路径", "4", 2),
        ("1997：整层先行、随后表层爆发", "5", 1),
        ("2015：次表层持续暖、表层短暂回冷", "6", 1),
        ("2023：远东表层先暖、整层约一个月追上", "7", 1),
        ("连续垂向结构：不同步来自哪里", "8", 1),
        ("1980年后暖事件普查", "9", 1),
        ("异号之后：转换还是失败", "10", 1),
        ("共同增暖与成熟期强度", "11", 1),
        ("建议", "12", 1),
        ("结论", "12", 2),
        ("附录", "13", 1),
    ]
    level_one_ppr = deepcopy(existing[0].find(qn("w:pPr")))
    level_two_ppr = deepcopy(existing[1].find(qn("w:pPr")))
    for child in list(content):
        content.remove(child)

    for index, (label, page, level) in enumerate(entries):
        paragraph = etree.SubElement(content, qn("w:p"))
        p_pr = deepcopy(level_one_ppr if level == 1 else level_two_ppr)
        for tab_stop in p_pr.xpath(".//w:tab", namespaces=NS):
            tab_stop.set(qn("w:pos"), "9000")
        paragraph.append(p_pr)
        run = etree.SubElement(paragraph, qn("w:r"))
        if index == 0:
            begin = etree.SubElement(run, qn("w:fldChar"))
            begin.set(qn("w:fldCharType"), "begin")
            instruction = etree.SubElement(run, qn("w:instrText"))
            instruction.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            instruction.text = ' TOC \\h \\u \\z \\t "Heading 1,1,Heading 2,2"'
            separate = etree.SubElement(run, qn("w:fldChar"))
            separate.set(qn("w:fldCharType"), "separate")
        r_pr = etree.SubElement(run, qn("w:rPr"))
        fonts = etree.SubElement(r_pr, qn("w:rFonts"))
        for slot in ("ascii", "hAnsi", "cs", "eastAsia"):
            fonts.set(qn(f"w:{slot}"), CJK_FONT)
        etree.SubElement(r_pr, qn("w:sz")).set(qn("w:val"), "22")
        etree.SubElement(r_pr, qn("w:szCs")).set(qn("w:val"), "22")
        label_node = etree.SubElement(run, qn("w:t"))
        label_node.text = label
        etree.SubElement(run, qn("w:tab"))
        page_node = etree.SubElement(run, qn("w:t"))
        page_node.text = page
        if index == len(entries) - 1:
            end_run = etree.SubElement(paragraph, qn("w:r"))
            end = etree.SubElement(end_run, qn("w:fldChar"))
            end.set(qn("w:fldCharType"), "end")

    for tag in ("keepNext", "keepLines", "pageBreakBefore", "widowControl", "suppressLineNumbers"):
        for node in root.xpath(f"//w:pPr/w:{tag}", namespaces=NS):
            node.getparent().remove(node)
    for node in root.xpath("//w:pPr/w:numPr", namespaces=NS):
        node.getparent().remove(node)

    title_paragraphs = root.xpath(
        "//w:body/w:p[w:pPr/w:pStyle[@w:val='Title']]",
        namespaces=NS,
    )
    if title_paragraphs:
        title = title_paragraphs[0]
        page_break = etree.Element(qn("w:p"))
        run = etree.SubElement(page_break, qn("w:r"))
        br = etree.SubElement(run, qn("w:br"))
        br.set(qn("w:type"), "page")
        title.getparent().insert(title.getparent().index(title), page_break)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def patch_font_table(font_table_xml: bytes) -> bytes:
    root = etree.fromstring(font_table_xml)
    existing = root.xpath("//w:font[@w:name=$name]", namespaces=NS, name=CJK_FONT)
    if not existing:
        font = etree.SubElement(root, qn("w:font"))
        font.set(qn("w:name"), CJK_FONT)
        embed = etree.SubElement(font, qn("w:embedRegular"))
        embed.set(qn("w:fontKey"), "{00000000-0000-0000-0000-000000000000}")
        embed.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "rId5")
        embed.set(qn("w:subsetted"), "0")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def patch_font_rels(font_rels_xml: bytes) -> bytes:
    root = etree.fromstring(font_rels_xml)
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    if root.find(f"{{{rel_ns}}}Relationship[@Id='rId5']") is None:
        relation = etree.SubElement(root, f"{{{rel_ns}}}Relationship")
        relation.set("Id", "rId5")
        relation.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font")
        relation.set("Target", "fonts/NotoSansCJKsc-Regular.ttf")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def build_final_package(scratch: Path, output: Path) -> None:
    editable_from_scratch = {
        "word/document.xml",
        "word/_rels/document.xml.rels",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.docx")
    with ZipFile(REFERENCE) as source, ZipFile(scratch) as changed, ZipFile(
        temporary, "w", ZIP_DEFLATED
    ) as target:
        original_names = set(source.namelist())
        changed_names = set(changed.namelist())
        for name in source.namelist():
            if name == "word/document.xml":
                data = patch_document(changed.read(name))
            elif name in editable_from_scratch:
                data = changed.read(name)
            elif name == "word/header1.xml":
                data = patch_header(source.read(name))
            elif name == "word/settings.xml":
                data = patch_settings(source.read(name))
            elif name == "word/fontTable.xml":
                data = patch_font_table(source.read(name))
            elif name == "word/_rels/fontTable.xml.rels":
                data = patch_font_rels(source.read(name))
            elif name == "word/styles.xml":
                data = patch_styles(source.read(name))
            else:
                data = source.read(name)
            target.writestr(name, data)
        for name in sorted(changed_names - original_names):
            if name.startswith("word/media/"):
                target.writestr(name, changed.read(name))
        target.writestr("word/fonts/NotoSansCJKsc-Regular.ttf", CJK_FONT_FILE.read_bytes())
    temporary.replace(output)


def main() -> None:
    if sha256(REFERENCE) != REFERENCE_SHA256:
        raise RuntimeError("Retained Design Report reference changed; re-distill before authoring")
    for figure in FIGURES.values():
        if not figure.exists():
            raise FileNotFoundError(figure)
    if not CJK_FONT_FILE.exists():
        raise FileNotFoundError(CJK_FONT_FILE)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REFERENCE, SCRATCH_DOCX)
    doc = Document(SCRATCH_DOCX)

    # Capture source-derived components before replacing the template body.
    bullet_xml = deepcopy(doc.paragraphs[10]._p)
    callout_xml = deepcopy(doc.paragraphs[23]._p)
    numbered_xml = deepcopy(doc.paragraphs[29]._p)
    comparison_table_xml = deepcopy(doc.tables[1]._tbl)

    edit_cover(doc)
    body = doc._body._element
    body_children = list(body)
    first_section_break_index = next(
        index
        for index, child in enumerate(body_children)
        if child.tag == qn("w:p") and child.find(".//" + qn("w:sectPr")) is not None
    )
    # Preserve cover, contents title, blank line, TOC content control and its bookmarks.
    keep_through = first_section_break_index + 6
    for child in list(body)[keep_through:-1]:
        body.remove(child)

    # Localize retained Contents heading without altering its page pattern.
    contents = next(paragraph for paragraph in doc.paragraphs if paragraph.text == "Contents")
    replace_paragraph(contents, "目录", size=24.0, bold=False, latin="Helvetica Neue")

    add_report_content(doc, bullet_xml, numbered_xml, callout_xml)
    doc.save(SCRATCH_DOCX)
    build_final_package(SCRATCH_DOCX, OUTPUT)

    if sha256(REFERENCE) != REFERENCE_SHA256:
        raise RuntimeError("Retained reference was modified during authoring")
    print(OUTPUT)


if __name__ == "__main__":
    main()
