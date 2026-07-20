#!/usr/bin/env python3
"""Build the English January-June ENSO event-comparison report."""

from __future__ import annotations

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from build_enso_event_comparison_docx import (
    EVENTS,
    ORDINARY_FIGURES,
    ROOT,
    add_figure,
    add_heading,
    add_paragraph,
    configure_styles,
    format_compact_table,
    keep_table_together,
    load_event_metrics,
    load_ordinary_analysis,
    set_cell_margins,
    set_cell_shading,
    set_run_font,
    set_table_width,
)


OUT = ROOT / "outputs/research_2026/reports/enso_event_comparison_unified_1980_2014_jan_jun_2026_en.docx"


def format_table(table) -> None:
    header_properties = table.rows[0]._tr.get_or_add_trPr()
    repeat_header = OxmlElement("w:tblHeader")
    repeat_header.set(qn("w:val"), "true")
    header_properties.append(repeat_header)
    set_table_width(table, [2.2, 1.43, 1.43, 1.43])
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            set_cell_shading(cell, "FFFFFF")
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.05
                for run in paragraph.runs:
                    set_run_font(run, size=8.6, bold=(row is table.rows[0]))


def add_metric_table(doc: Document, metrics: dict[str, dict[str, float]]) -> None:
    add_heading(doc, "Table 1. Key Regional Metrics", level=2)
    table_note = add_paragraph(
        doc,
        "Each cell gives the January-June mean / June value. Positive Peng CWP u10 denotes a near-surface westerly anomaly.",
        size=9.2,
    )
    table_note.paragraph_format.keep_with_next = True
    rows = [
        ("Niño3.4 SST (°C)", "sst_Nino3.4", "{:+.2f}"),
        ("Peng CWP u10 (m s⁻¹)", "u_CWP", "{:+.2f}"),
        ("CP precipitation (mm day⁻¹)", "pr_CP", "{:+.2f}"),
        ("Western D20 (m)", "d20_West", "{:+.1f}"),
        ("Eastern D20 (m)", "d20_East", "{:+.1f}"),
    ]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["Metric", "2015/16", "2023/24", "2026"]):
        cell.text = label
    for label, key, fmt in rows:
        cells = table.add_row().cells
        cells[0].text = label
        for index, event in enumerate(["2015/16", "2023/24", "2026"], start=1):
            cells[index].text = f"{fmt.format(metrics[event][key])} / {fmt.format(metrics[event][key + '_june'])}"
    format_table(table)
    keep_table_together(table)


def add_expected_response_table(doc: Document, ordinary) -> None:
    expected = ordinary["expected"]
    means = (
        expected.groupby(["target_label", "response"], as_index=False)[["observed", "expected", "residual"]]
        .mean(numeric_only=True)
        .set_index(["target_label", "response"])
    )
    add_heading(doc, "Table 2. Observed versus SST-Conditioned Response", level=2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["Response (Jan-Jun mean)", "2015/16", "2023/24", "2026 state"]):
        cell.text = label
    labels = {2015: "2015/16", 2023: "2023/24", 2026: "2026 developing state"}
    for metric_label, response in (("Peng CWP u10 (m/s)", "cwp_u10"), ("CP precipitation (mm/day)", "cp_precip")):
        cells = table.add_row().cells
        cells[0].text = metric_label
        for index, year in enumerate((2015, 2023, 2026), start=1):
            row = means.loc[(labels[year], response)]
            cells[index].text = f"{row.observed:+.2f} / {row.expected:+.2f} ({row.residual:+.2f})"
    format_compact_table(table, [2.05, 1.48, 1.48, 1.48])
    keep_table_together(table)
    add_paragraph(
        doc,
        "Each cell gives observed / historical expectation (residual). Calendar-month Niño3 regressions are fitted over "
        "1982-2014 with all three target years excluded.",
        size=9.2,
    )


def add_similarity_table(doc: Document, ordinary) -> None:
    similarity = ordinary["similarity"]
    add_heading(doc, "Table 3. Layer-Resolved Similarity of 2026 to 2015 and 2023", level=2)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    for cell, label in zip(
        table.rows[0].cells,
        ["Physical layer", "Candidate", "Correlation r", "Centered RMSD", "Std. ratio"],
    ):
        cell.text = label
    layer_labels = {
        "Tropical-Pacific SST": "SST",
        "850 hPa zonal wind": "u850",
        "Precipitation": "Precipitation",
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
    format_compact_table(table, [1.25, 1.35, 1.1, 1.55, 1.15])
    keep_table_together(table)
    add_paragraph(
        doc,
        "Taylor statistics constrain pattern correlation, centered error, and relative amplitude separately; no aggregate "
        "similarity score is constructed.",
        size=9.2,
    )


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
    doc.core_properties.title = "Air-Sea Coupling Diagnosis of the 2026 ENSO Event"
    doc.core_properties.subject = "January-June comparison with 2015/16 and 2023/24"

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run("Air-Sea Coupling Diagnosis of the 2026 ENSO Event")
    set_run_font(run, size=20, bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(10)
    run = subtitle.add_run("Comparison with 2015/16 and 2023/24; observations through June 2026")
    set_run_font(run, size=10.5)

    add_heading(doc, "Abstract", level=1)
    add_paragraph(
        doc,
        "This report uses the strongly coupled 2015/16 event and the atmosphere-limited 2023/24 event to diagnose the January-June "
        "2026 tropical Pacific state. Early warming retained the eastern-leading geometry of 2023, but the equatorial thermocline "
        "subsequently developed a basin-scale shallow-west/deep-east structure and central-western Pacific near-surface westerlies "
        "became persistent. Deep convection lagged these oceanic and dynamical adjustments and joined the coupled pattern only late "
        "in the period. The 2026 evolution is therefore a transition from an eastern surface signal toward a 2015-like dynamical "
        "coupling regime; its subsequent strength depends on whether central-Pacific convection can sustain the wind-thermocline feedback.",
    )

    add_heading(doc, "Research Question and Methodological Basis", level=1)
    add_paragraph(
        doc,
        "The 2023/24 event showed that a strong oceanic initial state need not produce an equally strong atmospheric response. The "
        "central question for 2026 is therefore whether the warming remains an eastern-Pacific surface development or has acquired a "
        "basin-scale positive feedback capable of sustaining itself. Peng et al. (2025) provide the Niño3-conditioned near-surface "
        "wind response used to test whether westerlies meet the historical SST-based expectation. Jiang et al. (2026) motivate the "
        "cross-event comparison of SST, wind, and precipitation centers, and Li et al. (2024) provide the process chain linking "
        "thermocline adjustment, surface warming, low-level wind, and convective heating. Taylor statistics identify the historical "
        "analogue separately in each physical field.",
    )
    add_paragraph(
        doc,
        "Peng CWP wind is the area-mean 10 m zonal wind over 5°S–5°N, 140°E–160°W. Central-Pacific precipitation follows the "
        "5°S–5°N, 180°–140°W diagnostic region of Sun et al. (2016). Regional time series quantify observed-versus-expected "
        "responses, while 850 hPa vectors describe the spatial organization of the lower-tropospheric circulation. These diagnostics "
        "separate near-surface momentum response from the broader low-level wind pattern.",
    )

    add_heading(doc, "1. Data and Methods", level=1)
    add_paragraph(
        doc,
        "SST is from NOAA OISST; 10 m wind, 850 hPa wind, and precipitation are from ERA5; and 20°C isotherm depth (D20) is "
        "from ORAS5. June 2026 u10 is aggregated from hourly fields in the public ARCO-ERA5T mirror; the remaining u10 "
        "values use ERA5 monthly means. ERA5 850 hPa wind, precipitation, and ORAS5 anomalies use 1980-2014, whereas OISST and Peng CWP u10 use "
        "1982-2014. Calendar-month climatologies and linear trends are removed. "
        "All events are compared over January-June of the developing year.",
    )
    add_paragraph(
        doc,
        "Atmospheric conditional responses are obtained from 1982-2014 calendar-month regressions on Niño3 SST, excluding "
        "2015, 2023, and 2026. Historical similarity is evaluated with the area-weighted pattern correlation, centered RMSD, and "
        "standard-deviation ratio of Taylor (2001), separately for SST, u850, precipitation, and D20. Monthly time series establish "
        "process order, while spatial fields test whether anomaly centers, signs, and basin-scale structures evolve coherently.",
    )
    add_metric_table(doc, metrics)

    add_heading(doc, "2. Evolution of the Three Events", level=1)
    add_heading(doc, "2.1 SST and 850 hPa Wind", level=2)
    add_paragraph(
        doc,
        "In 2015, warm anomalies formed a connected central-eastern Pacific pattern, while westerlies intensified on the western flank "
        "of the warm region and favored eastward warm-water displacement. In 2023, warming remained more confined to the east and the "
        "central-western Pacific westerly response was weak and spatially incoherent. Early 2026 resembled the eastern-leading 2023 "
        "geometry, but the warm region expanded westward during spring and the low-level westerly band became organized across the "
        "central-western Pacific. The surface onset was 2023-like; the later circulation configuration moved toward the coupled 2015 state.",
    )
    add_figure(doc, EVENTS["2015/16"]["ssta"], "Figure 1. OISST SSTA and ERA5 850 hPa wind anomalies during the 2015/16 development year.")
    add_figure(doc, EVENTS["2023/24"]["ssta"], "Figure 2. OISST SSTA and ERA5 850 hPa wind anomalies during the 2023/24 development year.")
    add_figure(doc, EVENTS["2026"]["ssta"], "Figure 3. OISST SSTA and ERA5 850 hPa wind anomalies, January-June 2026.")

    add_heading(doc, "2.2 Precipitation and 850 hPa Wind", level=2)
    add_paragraph(
        doc,
        "In 2015, central-Pacific positive precipitation anomalies developed with the westerly center, indicating that deep convective "
        "heating had joined the Walker-circulation adjustment. In 2023, convection did not expand sufficiently into the central Pacific, "
        "and the wind-precipitation pattern remained poorly aligned. During early 2026, central-Pacific convection was still suppressed "
        "even as near-surface and 850 hPa westerlies began to develop. Positive precipitation anomalies entered the central Pacific only "
        "later and then overlapped the westerly region. This wind-before-rain sequence places deep-convective organization after the "
        "oceanic and boundary-layer dynamical response.",
    )
    add_figure(doc, EVENTS["2015/16"]["precip"], "Figure 4. ERA5 precipitation and 850 hPa wind anomalies during the 2015/16 development year.")
    add_figure(doc, EVENTS["2023/24"]["precip"], "Figure 5. ERA5 precipitation and 850 hPa wind anomalies during the 2023/24 development year.")
    add_figure(doc, EVENTS["2026"]["precip"], "Figure 6. ERA5 precipitation and 850 hPa wind anomalies, January-June 2026.")

    add_heading(doc, "2.3 D20 and Equatorial u850", level=2)
    add_paragraph(
        doc,
        "The 2015 thermocline showed sustained western shoaling and eastern deepening, consistent with eastward warm-water redistribution "
        "and strong subsurface support for eastern-Pacific warming. In 2023, eastern deepening occurred without comparable western "
        "shoaling, leaving the basin-scale tilt and dynamical feedback weaker. In 2026, eastern deepening appeared first and western "
        "shoaling followed, producing a coherent shallow-west/deep-east structure late in the period. The ocean evolved from a localized "
        "eastern signal into a basin-scale adjustment and is therefore dynamically closer to 2015 than to 2023.",
    )
    add_figure(doc, EVENTS["2015/16"]["d20"], "Figure 7. ORAS5 equatorial D20 anomalies and ERA5 equatorial u850 during the 2015/16 development year.")
    add_figure(doc, EVENTS["2023/24"]["d20"], "Figure 8. ORAS5 equatorial D20 anomalies and ERA5 equatorial u850 during the 2023/24 development year.")
    add_figure(doc, EVENTS["2026"]["d20"], "Figure 9. ORAS5 equatorial D20 anomalies and ERA5 equatorial u850, January-June 2026.")

    add_heading(doc, "3. SST-Conditioned Atmospheric Response", level=1)
    add_expected_response_table(doc, analysis)
    add_figure(
        doc,
        ORDINARY_FIGURES["expected"],
        "Figure 10. Observed atmospheric responses and Niño3 SST-conditioned historical expectations for the three events; regression period: 1982-2014.",
    )
    response_paragraph = add_paragraph(
        doc,
        "The SST-conditioned regressions convert event SST amplitude into a calendar-month historical atmospheric benchmark. The 2015 "
        "near-surface westerlies exceeded this benchmark, consistent with atmospheric amplification in a strongly coupled event. In "
        "2023, both wind and precipitation fell below expectation, showing that the SST anomaly failed to organize an adequate "
        "central-western Pacific response. The 2026 response is process-separated: near-surface westerlies remained above expectation "
        "after spring, while central-Pacific precipitation stayed below expectation for most of the period. The limiting link has shifted "
        "from near-surface wind response to the migration and persistence of deep convective heating.",
    )
    response_paragraph.paragraph_format.keep_together = True

    add_heading(doc, "4. Coupling Sequence in 2026", level=1)
    add_figure(
        doc,
        ORDINARY_FIGURES["staged"],
        "Figure 11. January-June 2026 D20, Niño3 SST, Peng CWP u10, and CP precipitation, including SST-conditioned atmospheric expectations. Background colors separate process periods identified from the observed evolution.",
    )
    add_heading(doc, "4.1 Thermocline Adjustment (Figure 11a)", level=2)
    add_paragraph(
        doc,
        "The eastern thermocline deepened before a comparable western response, indicating localized subsurface warmth rather than a "
        "basin-wide tilt. Western shoaling emerged during spring and completed a shallow-west/deep-east structure. This redistribution "
        "limits cold-water supply to the eastern mixed layer and converts initial ocean memory into dynamical support for surface warming.",
    )
    add_heading(doc, "4.2 Eastern-Pacific Surface Warming (Figure 11b)", level=2)
    add_paragraph(
        doc,
        "Niño3 warming developed in two steps: a rapid early increase, a spring pause, and renewed acceleration after the thermocline "
        "tilt strengthened. This phase relationship links the surface warming to ocean dynamics. Eastern thermocline deepening reduces "
        "entrainment and upwelling of cold water into the mixed layer, while western shoaling accompanies the eastward displacement of "
        "warm water. The later surface acceleration is thus the expression of basin-scale thermocline adjustment at the sea surface, not "
        "an isolated local heat anomaly.",
    )
    add_heading(doc, "4.3 Low-Level Zonal-Wind Response (Figure 11c)", level=2)
    add_paragraph(
        doc,
        "Near-surface zonal wind alternated in sign early in the year, indicating that the atmosphere had not yet established a stable "
        "response to eastern-Pacific warming. From spring onward, CWP westerlies became persistent and increasingly exceeded the "
        "Niño3-conditioned historical expectation, while the 850 hPa westerly band organized spatially into the central Pacific. These "
        "westerlies weaken the equatorial trades, promote eastward warm-water displacement, and reinforce the emerging thermocline tilt. "
        "Unlike the persistently weak wind response of 2023, near-surface wind in 2026 changed from a limiting link into active support for "
        "ocean adjustment; its strength also cannot be explained by contemporaneous Niño3 amplitude alone.",
    )
    add_heading(doc, "4.4 Deep-Convective Response (Figure 11d)", level=2)
    convection_paragraph = add_paragraph(
        doc,
        "Central-Pacific precipitation was the last of the four components to respond. Eastern SST and the thermocline had already changed "
        "while convection remained suppressed, showing that the surface thermal anomaly had not yet produced an effective deep-heating "
        "response in the central Pacific. Later, precipitation became positive and moved toward its SST-conditioned expectation, and the "
        "positive anomaly began to overlap the westerly region. Latent heating from organized deep convection can strengthen the zonal "
        "pressure gradient and anomalous Walker circulation, helping maintain the central-western Pacific westerlies. Convection therefore "
        "determines whether the established wind-ocean link can continue to amplify. The observed order is eastern subsurface and surface "
        "warming first, basin-scale thermocline and westerly adjustment second, and convective recovery last. The principal feedback geometry "
        "is present, but its persistence depends on central-Pacific convection through boreal summer and autumn.",
    )
    convection_paragraph.paragraph_format.keep_together = True

    add_heading(doc, "5. Historical Similarity and Evolution", level=1)
    add_similarity_table(doc, analysis)
    similarity_paragraph = add_paragraph(
        doc,
        "Layer-resolved similarity yields a coherent physical interpretation. The 2026 surface-SST pattern is closer to 2023, whereas "
        "low-level zonal wind and equatorial D20 are closer to 2015; precipitation does not yet map robustly onto either reference event. "
        "SST alone would therefore overstate similarity to 2023, while ocean dynamics alone would overlook the delayed convective response. "
        "Taken together without collapsing the fields into one score, 2026 is a hybrid transition from eastern-leading warming toward "
        "basin-scale dynamical coupling.",
    )
    similarity_paragraph.paragraph_format.keep_together = True
    outlook_paragraph = add_paragraph(
        doc,
        "If central-Pacific positive precipitation persists and remains collocated with the westerly band, the existing thermocline tilt "
        "and eastward warm-water displacement are likely to continue, moving the event further toward a 2015-like basin-scale coupled state. "
        "If deep convection weakens again, the westerlies may lose large-scale heating support and the event may retain a strong eastern "
        "surface expression without sustaining equally strong positive feedback. Contemporary CPC and WMO outlooks also favor continued "
        "strengthening, but the eventual amplitude should be assessed from the continued coherence of convection, wind, and ocean adjustment.",
    )
    outlook_paragraph.paragraph_format.keep_together = True

    add_heading(doc, "6. Conclusions", level=1)
    add_paragraph(
        doc,
        "The 2026 event began with eastern-Pacific surface and subsurface warming, then developed a basin-scale thermocline tilt together "
        "with persistent central-western Pacific westerlies at the surface and 850 hPa. This dynamical structure differs from the limited "
        "wind response of 2023/24 and is moving toward the strongly coupled 2015/16 configuration. Central-Pacific deep convection developed "
        "later and remains the least complete link. The next phase should therefore be judged not by SST increase alone, but by whether "
        "convective heating sustains the westerlies and keeps the wind-thermocline-SST feedback coherent across the basin.",
    )

    add_heading(doc, "Method and Data References", level=1)
    references_paragraph = add_paragraph(
        doc,
        "Peng et al. (2025), Nature Geoscience, doi:10.1038/s41561-025-01700-9: CWP (5°S–5°N, 140°E–160°W) u10, Niño3-conditioned regression, and actual-versus-expected response.\n"
        "Jiang et al. (2026), Geophysical Research Letters, doi:10.1029/2026GL123227: eastern-Pacific-leading warming, central-Pacific wind-precipitation response, and cross-event regression comparison.\n"
        "Li et al. (2024), Geophysical Research Letters, doi:10.1029/2024GL109874: process-separated atmospheric Bjerknes feedback from SST through precipitation heating and pressure to wind stress.\n"
        "Sun et al. (2016), Advances in Atmospheric Sciences, doi:10.1007/s00376-015-5018-6: central-Pacific precipitation and wind-stress responses to Niño3 SST and the 5°S–5°N, 180°–140°W diagnostic box.\n"
        "Kim, Tian & Yu (2025), npj Climate and Atmospheric Science, doi:10.1038/s41612-024-00890-0: D20, western-Pacific warm water, and western-central Pacific zonal-wind evolution across events.\n"
        "Taylor (2001), Journal of Geophysical Research, doi:10.1029/2000JD900719: pattern correlation, centered RMSD, and standard-deviation ratio.\n"
        "Zuo et al. (2019), Ocean Science, doi:10.5194/os-15-779-2019: the ORAS5 system, data assimilation, and ocean-state reconstruction.\n"
        "NOAA CPC ENSO Diagnostic Discussion, 9 July 2026; WMO El Niño Update, 3 July 2026.",
        size=9.2,
    )
    references_paragraph.paragraph_format.keep_together = True

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build_doc()
