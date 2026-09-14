#!/usr/bin/env python3
"""Apply polished late-stage figures to the latest saved English report.

The edit is deliberately surgical: the user's saved DOCX is the source of
truth, Figures 1-6 and the surrounding prose are preserved, Figures 7-11 are
replaced in place, and the final Taylor-statistics table is converted to a
standard layer-resolved Taylor visualization.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "outputs/research_2026/reports"
FIGURE_DIR = ROOT / "outputs/research_2026/report_visual_revision"
SOURCE = REPORT_DIR / "enso_event_comparison_unified_1980_2014_jan_jun_2026_en.docx"
OUTPUT = REPORT_DIR / "enso_event_comparison_unified_1980_2014_jan_jun_2026_en_visual_revision.docx"

FIGURES = {
    7: FIGURE_DIR / "fig07_three_event_d20_geographic_sections_clean.png",
    10: FIGURE_DIR / "fig10_observed_expected_polished.png",
    11: FIGURE_DIR / "fig11_2026_coupling_sequence_polished.png",
}

ALT_TEXT = {
    7: "Three-event comparison of January-June equatorial Pacific ORAS5 20 degree Celsius isotherm displacement sections and ERA5 850 hPa zonal-wind anomalies for 2015, 2023, and 2026.",
    10: "Observed and Niño3-conditioned expected CWP 10 m zonal wind and central-Pacific precipitation for 2015, 2023, and 2026.",
    11: "January-June 2026 sequence of thermocline adjustment, Niño3 warming, near-surface wind response, and central-Pacific precipitation.",
}


def paragraph_with_caption(document: Document, figure_number: int):
    prefix = f"Figure {figure_number}."
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise ValueError(f"Could not find caption {prefix}")


def set_drawing_size(image_paragraph, image_path: Path, width_inches: float) -> None:
    with Image.open(image_path) as image:
        aspect = image.width / image.height
    width = int(width_inches * 914400)
    height = int(width / aspect)
    for extent in image_paragraph._p.xpath(".//wp:extent"):
        extent.set("cx", str(width))
        extent.set("cy", str(height))
    for extent in image_paragraph._p.xpath(".//a:xfrm/a:ext"):
        extent.set("cx", str(width))
        extent.set("cy", str(height))


def replace_figure(
    document: Document,
    figure_number: int,
    image_path: Path,
    display_number: int | None = None,
) -> None:
    caption = paragraph_with_caption(document, figure_number)
    image_element = caption._p.getprevious()
    if image_element is None or not image_element.xpath(".//w:drawing"):
        raise ValueError(f"Figure {figure_number} image paragraph was not found immediately before its caption")
    blips = image_element.xpath(".//a:blip")
    if len(blips) != 1:
        raise ValueError(f"Figure {figure_number} should contain exactly one embedded image")
    relationship_id = blips[0].get(qn("r:embed"))
    image_part = document.part.related_parts[relationship_id]
    image_part._blob = image_path.read_bytes()
    set_drawing_size(type("ImageParagraph", (), {"_p": image_element})(), image_path, 6.80)
    displayed = figure_number if display_number is None else display_number
    for doc_properties in image_element.xpath(".//wp:docPr"):
        doc_properties.set("descr", ALT_TEXT[figure_number])
        doc_properties.set("title", f"Figure {displayed}")


def set_caption(caption, text: str) -> None:
    caption.text = ""
    run = caption.add_run(text)
    run.italic = True


def remove_figure_and_caption(document: Document, figure_number: int) -> None:
    caption = paragraph_with_caption(document, figure_number)
    image_element = caption._p.getprevious()
    if image_element is None or not image_element.xpath(".//w:drawing"):
        raise ValueError(f"Figure {figure_number} image paragraph was not found immediately before its caption")
    remove_element(image_element)
    remove_element(caption._p)


def consolidate_d20_figures(document: Document) -> None:
    replace_figure(document, 7, FIGURES[7], display_number=7)
    set_caption(
        paragraph_with_caption(document, 7),
        "Figure 7. Equatorial Pacific D20 displacement and ERA5 u850 anomalies for the 2015/16, "
        "2023/24, and 2026 development periods. Solid curves add each detrended event anomaly to the "
        "1980-2014 ORAS5 calendar-month baseline; the locator map shows the equatorial section and "
        "5°S-5°N wind-averaging band.",
    )
    remove_figure_and_caption(document, 8)
    remove_figure_and_caption(document, 9)


def replace_and_renumber_late_figures(document: Document) -> None:
    replace_figure(document, 10, FIGURES[10], display_number=8)
    set_caption(
        paragraph_with_caption(document, 10),
        "Figure 8. Observed atmospheric responses and Niño3 SST-conditioned historical expectations "
        "for the three events; regression period: 1982-2014.",
    )
    replace_figure(document, 11, FIGURES[11], display_number=9)
    set_caption(
        paragraph_with_caption(document, 11),
        "Figure 9. January-June 2026 D20, Niño3 SST, Peng CWP u10, and CP precipitation, including "
        "SST-conditioned atmospheric expectations. Background colors separate process periods "
        "identified from the observed evolution.",
    )


def remove_element(element) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def remove_taylor_section(document: Document) -> None:
    section_heading = None
    heading = None
    note = None
    interpretation = None
    conclusion = None
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text.startswith("5. Historical Similarity and Evolution"):
            section_heading = paragraph
        elif text.startswith("Table 3. Layer-Resolved Similarity"):
            heading = paragraph
        elif text.startswith("Taylor statistics constrain pattern correlation"):
            note = paragraph
        elif text.startswith("Layer-resolved similarity yields"):
            interpretation = paragraph
        elif text.startswith("6. Conclusions"):
            conclusion = paragraph
    if any(item is None for item in [section_heading, heading, note, interpretation, conclusion]):
        raise ValueError("Could not locate the complete Taylor-analysis section")
    target_table = None
    for table in document.tables:
        if table.cell(0, 0).text.strip() == "Physical layer":
            target_table = table
            break
    if target_table is None:
        raise ValueError("Could not locate the layer-resolved similarity table")
    remove_element(section_heading._p)
    remove_element(heading._p)
    remove_element(target_table._tbl)
    remove_element(note._p)
    remove_element(interpretation._p)
    conclusion.text = "5. Conclusions"


def remove_taylor_method_text(document: Document) -> None:
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text.startswith("The 2023/24 event showed that a strong oceanic initial state"):
            paragraph.text = (
                "The 2023/24 event showed that a strong oceanic initial state need not produce an equally "
                "strong atmospheric response. The central question for 2026 is therefore whether the warming "
                "remains an eastern-Pacific surface development or has acquired a basin-scale positive feedback "
                "capable of sustaining itself. Peng et al. (2025) provide the Niño3-conditioned near-surface wind "
                "response used to test whether westerlies meet the historical SST-based expectation. Jiang et al. "
                "(2026) motivate the cross-event comparison of SST, wind, and precipitation centers."
            )
        elif text.startswith("Atmospheric conditional responses are obtained from 1982-2014"):
            paragraph.text = (
                "Atmospheric conditional responses are obtained from 1982-2014 calendar-month regressions on "
                "Niño3 SST, excluding 2015, 2023, and 2026. Monthly time series establish process order, while "
                "spatial fields test whether anomaly centers, signs, and basin-scale structures evolve coherently."
            )
        elif text.startswith("Peng et al. (2025), Nature Geoscience"):
            lines = [line for line in paragraph.text.splitlines() if not line.startswith("Taylor (2001)")]
            paragraph.text = "\n".join(lines)


def insert_taylor_figure(document: Document) -> None:
    target = None
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith("Layer-resolved similarity yields"):
            target = paragraph
            break
    if target is None:
        raise ValueError("Could not locate the historical-similarity interpretation paragraph")

    image_path = FIGURE_DIR / "fig12_layer_resolved_taylor_diagrams.png"
    image_paragraph = target.insert_paragraph_before()
    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_paragraph.paragraph_format.space_before = Pt(2)
    image_paragraph.paragraph_format.space_after = Pt(2)
    image_paragraph.paragraph_format.keep_with_next = True
    run = image_paragraph.add_run()
    shape = run.add_picture(str(image_path), width=Inches(6.55))
    doc_properties = shape._inline.docPr
    doc_properties.set("descr", ALT_TEXT[12])
    doc_properties.set("title", "Figure 10")

    caption = target.insert_paragraph_before()
    caption.style = "Caption"
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(1)
    caption.paragraph_format.space_after = Pt(6)
    caption.paragraph_format.keep_with_next = True
    caption_run = caption.add_run(
        "Figure 10. Layer-resolved Taylor diagrams comparing the January-June 2026 SST, u850, "
        "precipitation, and D20 fields with 2015/16 and 2023/24. Correlation, relative amplitude, "
        "and centered RMS difference are retained separately; no cross-variable score is constructed."
    )
    caption_run.italic = True

    target.text = (
        "The January-June 2026 SST field is modestly closer to 2023/24 in pattern correlation and "
        "centered RMSD, reflecting the shared eastern-leading onset and later westward expansion; "
        "its SST amplitude is nevertheless closer to 2015/16. In contrast, the u850 and equatorial "
        "D20 fields are more consistent with 2015/16, while precipitation does not map robustly onto "
        "either event. This field-by-field contrast identifies 2026 as a hybrid transition from "
        "eastern-leading warming toward basin-scale dynamical coupling without collapsing the "
        "diagnostics into one score."
    )


def main() -> int:
    document = Document(SOURCE)
    consolidate_d20_figures(document)
    replace_and_renumber_late_figures(document)
    remove_taylor_section(document)
    remove_taylor_method_text(document)
    document.core_properties.title = "Air-Sea Coupling Diagnosis of the 2026 ENSO Event"
    document.core_properties.subject = "January-June comparison with 2015/16 and 2023/24; visual revision"
    document.save(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
