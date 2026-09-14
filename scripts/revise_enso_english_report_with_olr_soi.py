#!/usr/bin/env python3
"""Add unified-baseline ERA5 OLR and CPC SOI diagnostics to the English report."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "outputs/research_2026/reports"
FIGURE_DIR = (
    ROOT / "outputs/research_2026/report_era5_olr_soi_unified_climatology"
)
SOURCE = (
    REPORT_DIR
    / "enso_event_comparison_unified_1980_2014_jan_jun_2026_en_d20_anomaly_revision.docx"
)
OUTPUT = (
    REPORT_DIR
    / "enso_event_comparison_unified_1980_2014_jan_jun_2026_en_era5_olr_soi_revision.docx"
)

OLR_MAP = FIGURE_DIR / "fig07_2026_monthly_era5_olr_anomalies.png"
OLR_INDICES = FIGURE_DIR / "fig08_three_event_era5_olr_soi_indices.png"


def find_paragraph(document: Document, prefix: str) -> Paragraph:
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise ValueError(f"Could not find paragraph beginning with {prefix!r}")


def replace_text(paragraph: Paragraph, text: str, italic: bool = False) -> None:
    paragraph.text = ""
    run = paragraph.add_run(text)
    run.italic = italic


def insert_paragraph_after(
    anchor: Paragraph,
    text: str = "",
    style: str | None = None,
) -> Paragraph:
    element = OxmlElement("w:p")
    anchor._p.addnext(element)
    paragraph = Paragraph(element, anchor._parent)
    if style is not None:
        paragraph.style = style
    if text:
        paragraph.add_run(text)
    return paragraph


def insert_picture_after(
    anchor: Paragraph,
    image_path: Path,
    width_inches: float,
    title: str,
    alt_text: str,
) -> Paragraph:
    paragraph = insert_paragraph_after(anchor)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run()
    shape = run.add_picture(str(image_path), width=Inches(width_inches))
    shape._inline.docPr.set("title", title)
    shape._inline.docPr.set("descr", alt_text)
    return paragraph


def insert_caption_after(anchor: Paragraph, text: str) -> Paragraph:
    paragraph = insert_paragraph_after(anchor, style="Caption")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(1)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.keep_together = True
    run = paragraph.add_run(text)
    run.italic = True
    return paragraph


def renumber_existing_figure(document: Document, old_number: int, new_number: int) -> None:
    caption = find_paragraph(document, f"Figure {old_number}.")
    text = caption.text.strip()
    replace_text(caption, text.replace(f"Figure {old_number}.", f"Figure {new_number}.", 1), True)
    image_element = caption._p.getprevious()
    if image_element is None or not image_element.xpath(".//w:drawing"):
        raise ValueError(f"Image for Figure {old_number} was not found immediately before caption")
    for properties in image_element.xpath(".//wp:docPr"):
        properties.set("title", f"Figure {new_number}")


def revise_existing_text(document: Document) -> None:
    replace_text(
        find_paragraph(document, "This report uses the strongly coupled"),
        "This report uses the strongly coupled 2015/16 event and the atmosphere-limited "
        "2023/24 event to diagnose the January-June 2026 tropical Pacific state. Alongside "
        "OISST, ERA5, and ORAS5, the analysis adds ERA5 outgoing longwave radiation (OLR) "
        "anomalies and monthly traditional and equatorial Southern Oscillation indices (SOI). "
        "All ERA5 OLR fields use the same 1980–2014 calendar-month climatology and same-month "
        "linear detrending as the report's other ERA5 diagnostics. Early warming retained an "
        "eastern-Pacific lead and strong subsurface recharge, but central-Pacific convection "
        "was near neutral in January and suppressed from February through April, while the "
        "traditional SOI remained positive through March. The pressure gradient changed sign "
        "in April, "
        "central-Pacific OLR became negative in May, and the atmospheric branch organized "
        "rapidly in June: central-Pacific OLR reached −18.4 W m−2, the central-Pacific-minus-"
        "Indonesia OLR contrast reached −23.7 W m−2, and both SOI measures reached −1.4. "
        "Compared with 2015, the 2026 coupling transition was delayed; compared with 2023, its "
        "June atmospheric response was much more complete. The 2026 event is therefore best "
        "interpreted as an eastern-leading oceanic transition whose convective link closed late "
        "in the development period.",
    )

    region_paragraph = find_paragraph(document, "Peng CWP wind is")
    replace_text(
        region_paragraph,
        "Peng CWP wind is the area-mean 10 m zonal wind over 5°S–5°N, 140°E–160°W. "
        "Central-Pacific precipitation follows the 5°S–5°N, 180°–140°W diagnostic region of "
        "Sun et al. (2016). For the OLR diagnostics, Indonesia is 5°S–5°N, 120°E–170°E; the "
        "central Pacific is 5°S–5°N, 170°E–140°W; and the east-central Pacific is 5°S–5°N, "
        "140°W–110°W. Regional precipitation and wind anomalies, and the Niño3 SST index, are "
        "calculated after removing the 1980–2014 linear trend and calendar-month climatology.",
    )

    methods = find_paragraph(document, "SST is from NOAA OISST")
    replace_text(
        methods,
        "SST is from NOAA OISST; 10 m wind, 850 hPa wind, and precipitation are from ERA5; "
        "and 20°C isotherm depth (D20) is from ORAS5. OLR is defined as the negative of ERA5 "
        "mean top net long-wave radiation flux because ERA5 vertical fluxes are positive "
        "downward. ERA5 OLR is downloaded as monthly means on a 1° grid. For each calendar "
        "month, the 1980–2014 climatology is removed and a grid-cell linear trend fitted over "
        "the same 35 years is subtracted, exactly matching the ERA5 wind and precipitation "
        "processing. Monthly traditional SOI and equatorial SOI are from NOAA Climate "
        "Prediction Center. June 2026 u10 is aggregated from hourly fields in the local ERA5 "
        "archive. OISST and Peng CWP u10 use their effective 1982–2014 baseline.",
    )

    precipitation = find_paragraph(document, "In 2015, central-Pacific positive precipitation")
    replace_text(
        precipitation,
        "In 2015, central-Pacific positive precipitation anomalies developed with the westerly "
        "center, indicating that deep convective heating had joined the Walker-circulation "
        "adjustment. In 2023, rainfall remained displaced and intermittent relative to the SST "
        "signal, consistent with a weak atmospheric return flow. During January–March 2026, "
        "ERA5 precipitation was still noisy. ERA5 OLR was near neutral over the central Pacific "
        "in January and positive from February through April, showing that deep convection had "
        "not yet organized despite the growing oceanic anomaly. The OLR transition began in May "
        "and became spatially coherent in June, when enhanced high-cloud and deep-"
        "convection signals extended across the central and east-central equatorial Pacific and "
        "suppressed convection appeared over Indonesia. This late reorganization is the clearest "
        "evidence that the atmospheric branch finally joined the oceanic transition.",
    )

    response = find_paragraph(document, "The SST-conditioned regressions convert")
    replace_text(
        response,
        "The SST-conditioned regressions convert event SST amplitude into a calendar-month "
        "historical atmospheric benchmark. The 2015 near-surface westerlies exceeded this "
        "benchmark, consistent with rapid positive feedback. The 2023 response remained weak "
        "and spatially displaced. In 2026, the wind response became increasingly consistent "
        "with the oceanic state, while precipitation lagged the SST-conditioned expectation "
        "through much of the period. The independent OLR and SOI diagnostics show that this "
        "gap closed sharply in May–June rather than persisting through the end of June.",
    )

    replace_text(
        find_paragraph(document, "The 2026 event began with eastern-Pacific"),
        "The 2026 event began with eastern-Pacific surface and subsurface warming, then "
        "developed a basin-scale thermocline tilt together with persistent central-western "
        "Pacific westerlies. OLR and SOI establish a clear atmospheric lag: central-Pacific "
        "convection remained suppressed and the traditional SOI stayed positive through March; "
        "the pressure gradient changed sign in April; and organized convection appeared in "
        "May–June. By June, central-Pacific OLR was −18.4 W m−2, the central-Pacific-minus-"
        "Indonesia contrast was −23.7 W m−2, and both traditional and equatorial SOI were −1.4. "
        "Thus, deep convection was not simply an incomplete link at the end of the analysis; it "
        "was the last link to close. The 2026 transition was later than the 2015 sequence but "
        "substantially more complete by June than the 2023 sequence. Continued monitoring should "
        "test whether this June atmospheric organization persists and reinforces the basin-scale "
        "ocean adjustment.",
    )

    references = find_paragraph(document, "Peng et al. (2025)")
    replace_text(
        references,
        references.text.rstrip()
        + "\nCopernicus Climate Change Service / ECMWF, ERA5 monthly averaged data on single "
        "levels: mean top net long-wave radiation flux, converted to OLR by sign reversal; "
        "https://cds.climate.copernicus.eu/datasets/"
        "reanalysis-era5-single-levels-monthly-means"
        + "\nECMWF ERA5 data documentation, mean top net long-wave radiation flux and flux "
        "sign convention: https://confluence.ecmwf.int/display/CKB/ERA5%3A+data+documentation"
        + "\nNOAA Climate Prediction Center (2026), monthly standardized traditional SOI and "
        "equatorial SOI: https://www.cpc.ncep.noaa.gov/data/indices/"
        + "\nNOAA Climate Prediction Center, Atmospheric and Equatorial SOI methodology: "
        "https://www.cpc.ncep.noaa.gov/data/indices/Readme.index.shtml",
    )


def add_olr_soi_section(document: Document) -> None:
    anchor = find_paragraph(document, "Figure 6.")
    heading = insert_paragraph_after(anchor, "2.3 OLR and Southern Oscillation", "Heading 2")

    interpretation = insert_paragraph_after(
        heading,
        "OLR and pressure indices confirm that the atmospheric branch lagged the oceanic "
        "transition but closed rapidly late in the period. January 2026 central-Pacific OLR was "
        "near neutral (+0.1 W m−2), while Indonesia OLR was strongly positive (+12.6 W m−2); "
        "this indicates Maritime Continent suppression without established central-Pacific "
        "enhancement. In February–March, central-Pacific OLR remained positive (+8.8 and "
        "+3.8 W m−2), while the traditional SOI remained positive (+1.4 and +1.2). The "
        "equatorial SOI first crossed slightly negative in March, but the central-Pacific "
        "convective response still lagged. April marked the pressure transition: traditional "
        "and equatorial SOI changed to −0.6 and −0.3 and Indonesia OLR rose to +18.7 W m−2, "
        "yet central-Pacific OLR remained +4.2 W m−2. The pressure gradient and western-Pacific "
        "suppression therefore led the full convective reorganization. By May and June, "
        "central-Pacific OLR fell to −8.3 and −18.4 W m−2; in June both SOI measures reached "
        "−1.4 and the OLR contrast reached −23.7 W m−2.",
    )

    figure = insert_picture_after(
        interpretation,
        OLR_MAP,
        6.55,
        "Figure 7",
        "Six monthly maps of January through June 2026 ERA5 OLR anomalies, with "
        "Indonesia, central-Pacific, and east-central-Pacific diagnostic boxes.",
    )
    caption = insert_caption_after(
        figure,
        "Figure 7. Monthly ERA5 OLR anomalies for January–June 2026. OLR is the negative "
        "of ERA5 mean top net long-wave radiation flux. Negative OLR "
        "denotes enhanced high-cloud/deep-convection signal and positive OLR denotes "
        "suppression; anomalies use the 1980–2014 same-calendar-month climatology and linear "
        "trend. Boxes "
        "mark Indonesia (120°E–170°E), the central Pacific (170°E–140°W), and the east-central "
        "Pacific (140°W–110°W), all averaged over 5°S–5°N.",
    )

    comparison = insert_paragraph_after(
        caption,
        "The cross-event comparison shows both the timing and completeness of the transition. "
        "In 2015, equatorial SOI was negative throughout January–June and central-Pacific OLR "
        "became strongly negative in March. In 2023, central-Pacific OLR weakened only modestly "
        "in May–June (−9.1 and −4.1 W m−2), and the June central-Pacific-minus-Indonesia "
        "contrast was only −2.8 W m−2, so the Walker-circulation shift remained weak. The 2026 response "
        "was later than 2015, but by June its traditional/equatorial SOI (−1.4/−1.4) and OLR "
        "contrast (−23.7 W m−2) had moved much more decisively toward a coupled El Niño-like "
        "atmospheric state than in 2023.",
    )

    figure = insert_picture_after(
        comparison,
        OLR_INDICES,
        6.55,
        "Figure 8",
        "Traditional SOI, equatorial SOI, ERA5 central-Pacific OLR, and central-Pacific-minus-"
        "Indonesia OLR contrast for the 2015, 2023, and 2026 development periods.",
    )
    insert_caption_after(
        figure,
        "Figure 8. January–June traditional SOI, equatorial SOI, ERA5 central-Pacific OLR anomaly, "
        "and central-Pacific-minus-Indonesia OLR contrast for the 2015/16, 2023/24, and 2026 "
        "development periods. OLR anomalies use the 1980–2014 same-calendar-month climatology "
        "and linear trend. Negative SOI and negative central-Pacific OLR denote an El Niño-like "
        "pressure and convection response, respectively.",
    )

    d20_heading = find_paragraph(document, "2.3 D20 and Equatorial u850")
    replace_text(d20_heading, "2.4 D20 and Equatorial u850")


def add_sequence_interpretation(document: Document) -> None:
    heading = find_paragraph(document, "4. Coupling Sequence in 2026")
    insert_paragraph_after(
        heading,
        "The independent OLR and SOI diagnostics refine the stage boundaries. January–February "
        "were dominated by ocean warming and thermocline adjustment while central-Pacific "
        "convection remained neutral or suppressed. March–April marked a pressure and wind transition "
        "without a fully organized convective center. May–June completed the sequence as both "
        "SOI measures became negative and enhanced convection expanded across the central and "
        "east-central Pacific. The coupled feedback therefore emerged progressively rather than "
        "as a simultaneous basin-wide switch.",
    )


def normalize_figure_properties(document: Document) -> None:
    """Keep all embedded-image metadata English and aligned with displayed numbers."""
    figure_2_alt = (
        "OISST sea-surface temperature anomalies and ERA5 850 hPa wind anomalies "
        "during the 2023/24 development year."
    )
    for figure_number, shape in enumerate(document.inline_shapes, start=1):
        shape._inline.docPr.set("title", f"Figure {figure_number}")
        if figure_number == 2:
            shape._inline.docPr.set("descr", figure_2_alt)


def main() -> int:
    for path in (SOURCE, OLR_MAP, OLR_INDICES):
        if not path.exists():
            raise FileNotFoundError(path)

    document = Document(SOURCE)
    revise_existing_text(document)
    renumber_existing_figure(document, 9, 11)
    renumber_existing_figure(document, 8, 10)
    renumber_existing_figure(document, 7, 9)
    add_olr_soi_section(document)
    add_sequence_interpretation(document)
    normalize_figure_properties(document)

    document.core_properties.title = "Air-Sea Coupling Diagnosis of the 2026 ENSO Event"
    document.core_properties.subject = (
        "January-June 2026 comparison with 2015/16 and 2023/24; ERA5 OLR and CPC SOI revision"
    )
    document.core_properties.comments = (
        "Updated with unified-baseline ERA5 OLR, traditional SOI, and equatorial SOI through June 2026."
    )
    document.save(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
