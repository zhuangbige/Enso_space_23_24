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
    PMM_FIG,
    PMM_FOCUS,
    ROOT,
    add_figure,
    add_heading,
    add_paragraph,
    configure_styles,
    format_compact_table,
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
    add_heading(doc, "Key Regional Metrics under the Unified Climatology", level=2)
    add_paragraph(
        doc,
        "The table reports January-June means. SST is in deg C, u850 is in m/s, precipitation is in mm/day, "
        "and D20 is in m. Positive u850 denotes a westerly anomaly and negative u850 an easterly anomaly. "
        "Because the 10 m wind input has not been extended through June, the PMM values remain January-May means "
        "and are labeled separately.",
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
    for cell, label in zip(table.rows[0].cells, ["Metric", "2015/16", "2023/24", "2026"]):
        cell.text = label
    for label, key, fmt in rows:
        cells = table.add_row().cells
        cells[0].text = label
        for index, event in enumerate(["2015/16", "2023/24", "2026"], start=1):
            if key is None:
                values = (
                    metrics[event]["d20_West"],
                    metrics[event]["d20_Central"],
                    metrics[event]["d20_East"],
                )
                cells[index].text = fmt.format(*values)
            else:
                cells[index].text = fmt.format(metrics[event][key])
    format_table(table)


def add_june_metric_table(doc: Document, metrics: dict[str, dict[str, float]]) -> None:
    add_heading(doc, "New Evidence from June 2026", level=2)
    add_paragraph(
        doc,
        "June is the critical addition in this update because it tests whether the previously observed sequence of "
        "ocean warming, wind recovery, and delayed precipitation persisted. Under the same detrending and climatology "
        "framework, June 2026 exhibits strong central-eastern Pacific warming, pronounced equatorial westerlies, "
        "positive central-Pacific precipitation anomalies, and a clear shallow-west/deep-east thermocline structure.",
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
    for cell, label in zip(table.rows[0].cells, ["June metric", "2015", "2023", "2026"]):
        cell.text = label
    for label, key, fmt in rows:
        cells = table.add_row().cells
        cells[0].text = label
        for index, event in enumerate(["2015/16", "2023/24", "2026"], start=1):
            if key is None:
                values = (
                    metrics[event]["d20_West_june"],
                    metrics[event]["d20_Central_june"],
                    metrics[event]["d20_East_june"],
                )
                cells[index].text = fmt.format(*values)
            else:
                cells[index].text = fmt.format(metrics[event][key])
    format_table(table)


def add_ordinary_event_table(doc: Document, ordinary) -> None:
    add_heading(doc, "Ordinary Non-Extreme El Niño Event List", level=2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["Developing event", "Peak ONI", "Peak season", "EP/CP"]):
        cell.text = label
    for row in ordinary["manifest"].itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = str(row.event_label)
        cells[1].text = f"{row.peak_oni:.2f}"
        cells[2].text = str(row.peak_season)
        cells[3].text = str(row.ep_cp_type)
    format_compact_table(table, [2.05, 1.35, 1.75, 1.35])
    add_paragraph(
        doc,
        "Events are identified automatically from NOAA ERSSTv5 ONI: ONI >= 0.5 deg C for at least five consecutive "
        "overlapping seasons, a developing year within 1982-2014, and peak ONI < 2.0 deg C. The 1982/83, 1997/98, "
        "2015/16, 2023/24, and 2026 cases are excluded. Composite uncertainty uses 10,000 event-resampling bootstrap "
        "replicates. EP/CP types use the published Cold Tongue/Warm Pool categories in Beniche et al. (2024), "
        "Supplementary Fig. S4.",
        size=9.2,
    )


def add_expected_response_table(doc: Document, ordinary) -> None:
    expected = ordinary["expected"]
    means = (
        expected.groupby(["target_label", "response"], as_index=False)[["observed", "expected", "residual"]]
        .mean(numeric_only=True)
        .set_index(["target_label", "response"])
    )
    add_heading(doc, "Observed versus Historical SST-Conditioned Response", level=2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["Response (Jan-Jun mean)", "2015/16", "2023/24", "2026 state"]):
        cell.text = label
    labels = {2015: "2015/16", 2023: "2023/24", 2026: "2026 developing state"}
    for metric_label, response in (("CWP u850 (m/s)", "cwp_u850"), ("CP precipitation (mm/day)", "cp_precip")):
        cells = table.add_row().cells
        cells[0].text = metric_label
        for index, year in enumerate((2015, 2023, 2026), start=1):
            row = means.loc[(labels[year], response)]
            cells[index].text = f"{row.observed:+.2f} / {row.expected:+.2f} ({row.residual:+.2f})"
    format_compact_table(table, [2.05, 1.48, 1.48, 1.48])
    add_paragraph(
        doc,
        "Each cell gives observed / SST-conditioned historical expectation (residual). Expectations are calendar-month "
        "regressions on Niño3 SST fitted over 1982-2014; 2015, 2023, and 2026 are excluded. The January-June 2023 "
        "residual is -0.86 m/s for CWP u850 and -1.88 mm/day for CP precipitation. Its weak atmospheric response is "
        "therefore not merely weak relative to a super El Niño; it is weak for the contemporaneous SST forcing.",
        size=9.2,
    )


def build_doc() -> None:
    metrics = load_event_metrics()
    ordinary = load_ordinary_analysis()
    doc = Document()
    configure_styles(doc)
    doc.core_properties.title = "Comparison of the 2015/16, 2023/24, and 2026 ENSO Development Phases"
    doc.core_properties.subject = "January-June air-sea coupling diagnostics"

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run("Comparison of the 2015/16, 2023/24, and 2026 ENSO Development Phases")
    set_run_font(run, size=20, bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(10)
    run = subtitle.add_run(
        "January-June SST-Wind, Precipitation-Wind, and D20-Wind Diagnostics under a Unified Climatology and Detrending Framework"
    )
    set_run_font(run, size=10.5)

    add_heading(doc, "Analytical Framework", level=1)
    add_paragraph(
        doc,
        "This report examines the newly redrawn January-June panels for three developing ENSO events. SST is from "
        "NOAA OISST, 850 hPa winds and precipitation are from ERA5, and D20 is from ORAS5. Monthly anomalies are "
        "calculated relative to the corresponding calendar-month climatology and linearly detrended. ERA5 and ORAS5 "
        "use a common 1980-2014 baseline, whereas OISST uses 1982-2014 because the record begins in late 1981. "
        "The PMM-like EOF is trained independently over 1982-2025. The 2026 PMM values still use January-May data only, "
        "are projected onto the fixed EOF pattern, and are not used to diagnose the June atmospheric feedback.",
    )
    add_paragraph(
        doc,
        "The spatial comparison emphasizes central-Pacific, eastern-Pacific, and far-eastern-Pacific SST anomalies. "
        "The temporal comparison asks whether the warming center, low-level winds, precipitation, and D20 evolve together "
        "from January through June. Air-sea coupling is therefore assessed from the co-evolution of SST, u850, precipitation, "
        "and D20 in similar regions and months rather than from any single variable.",
    )

    add_metric_table(doc, metrics)
    add_june_metric_table(doc, metrics)

    add_heading(doc, "Integrated Assessment", level=1)
    add_paragraph(
        doc,
        "Under the unified climatology, 2026 is not merely a surface warming event confined to the eastern Pacific. "
        "In June, Niño3.4, CP, and EP SST anomalies reach approximately 1.54, 1.63, and 1.62 deg C, respectively; "
        "CWP u850 reaches about 6.37 m/s, and eastern-Pacific D20 deepens by about 46.6 m. SST, low-level westerlies, "
        "and thermocline adjustment therefore show a clear, mutually reinforcing evolution.",
    )
    add_paragraph(
        doc,
        "The primary difference among the three events remains the timing at which coupling becomes established. "
        "In 2015, westerlies, D20, SST, and central-Pacific precipitation strengthened together relatively early. "
        "The 2023 event began with pronounced far-eastern-Pacific warming and a weaker atmospheric response. "
        "The 2026 event instead underwent a staged transition: convection remained weak during January-April, began to "
        "recover in May, and central-Pacific precipitation reached about +2.40 mm/day in June. Thus, 2026 can no longer "
        "be described as persistently decoupled; it transitioned rapidly from early asynchrony to strong coupling.",
    )

    add_heading(doc, "SST Anomalies and 850 hPa Winds: Spatial Evolution of Warming and Zonal Winds", level=1)
    add_paragraph(
        doc,
        "The early-2015 signal was concentrated from the central to central-eastern Pacific and was accompanied by "
        "persistent westerly anomalies. In 2023, the warming center was initially displaced toward the far eastern Pacific "
        "and subsequently expanded westward. The 2026 event also showed early eastern-Pacific warming, but central-Pacific "
        "SST and westerlies became increasingly involved during April-May. By June, the warm anomaly extended across the "
        "central-eastern Pacific together with the strongest CWP/CP westerly anomalies, indicating that the Bjerknes "
        "positive feedback had become well established.",
    )
    add_figure(doc, EVENTS["2015/16"]["ssta"], "Figure 1. 2015/16 development year: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2023/24"]["ssta"], "Figure 2. 2023/24 development year: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2026"]["ssta"], "Figure 3. January-June 2026: monthly OISST SSTA with ERA5 850 hPa wind anomalies.")

    add_heading(doc, "Precipitation and 850 hPa Winds: Did the Atmospheric Response Catch Up?", level=1)
    add_paragraph(
        doc,
        "The precipitation panels show that the central-Pacific convective response was earliest and most coherent in "
        "2015. During the far-eastern-Pacific warming of 2023, central-Pacific precipitation remained comparatively weak, "
        "indicating delayed atmospheric coupling. In 2026, central-Pacific precipitation was still suppressed during "
        "January-April, recovered locally in May, and became clearly positive in June in the same region as strong westerlies "
        "and warm SST. Deep-convective feedback had therefore caught up by June rather than remaining in its springtime lagged state.",
    )
    add_figure(doc, EVENTS["2015/16"]["precip"], "Figure 4. 2015/16 development year: ERA5 precipitation with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2023/24"]["precip"], "Figure 5. 2023/24 development year: ERA5 precipitation with ERA5 850 hPa wind anomalies.")
    add_figure(doc, EVENTS["2026"]["precip"], "Figure 6. January-June 2026: ERA5 precipitation with ERA5 850 hPa wind anomalies.")

    add_heading(doc, "D20 and Equatorial u850: Subsurface Dynamical Structure", level=1)
    add_paragraph(
        doc,
        "D20 provides the clearest evidence for the dynamical similarity between 2015 and 2026. In June, both events "
        "exhibited a shallower thermocline in the western Pacific and pronounced deepening in the central-eastern Pacific, "
        "consistent with an eastward displacement of warm water and an enhanced thermocline tilt. In June 2026, western "
        "D20 was about -12.1 m and eastern D20 about +46.6 m; western D20 in June 2023 was only about -2.7 m. The basin-scale "
        "dynamical adjustment in 2026 was therefore substantially closer to that of 2015.",
    )
    add_figure(doc, EVENTS["2015/16"]["d20"], "Figure 7. 2015/16 development year: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")
    add_figure(doc, EVENTS["2023/24"]["d20"], "Figure 8. 2023/24 development year: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")
    add_figure(doc, EVENTS["2026"]["d20"], "Figure 9. January-June 2026: ORAS5 equatorial D20 anomalies with ERA5 equatorial u850.")

    add_heading(doc, "PMM: Did the Subtropical North Pacific Background Contribute?", level=1)
    add_paragraph(
        doc,
        "The PMM-like EOF represents the leading coupled mode of subtropical North Pacific SST and near-surface winds "
        "after removing the linear influence of Niño3.4. Its positive phase corresponds to northeastern-Pacific warming, "
        "weakened trade winds, and reduced evaporative cooling. The joint SST-plus-wind PMM index was clearly positive "
        "during January-May in both 2015 and 2026, but weak or negative in 2023, suggesting that the subtropical background "
        "in 2026 more closely resembled 2015. Because the 10 m wind input has not been extended through June, this section "
        "is treated only as preconditioning context and is not used to determine whether the June feedback loop closed.",
    )
    add_figure(doc, PMM_FIG, "Figure 10. PMM-like EOF diagnostics from OISST SST and ERA5 10 m wind. EOF training period: 1982-2025.")
    add_figure(doc, PMM_FOCUS, "Figure 11. 2026 January-May PMM-like joint SST+wind and SST-only indices.")

    add_heading(doc, "Ordinary El Niño Benchmark: Was 2023/24 Weak Even for Its SST Forcing?", level=1)
    add_paragraph(
        doc,
        "The ordinary-El Niño comparison serves two distinct purposes. First, the equal-event composite provides the "
        "spatial background of non-extreme events at the same calendar stage. Second, a Peng et al. (2025)-style historical "
        "regression controls SST amplitude by comparing the observed atmosphere with the calendar-month response expected "
        "from Niño3 SST. The former asks where ordinary events usually progress by a given month; only the latter directly "
        "tests whether the atmosphere under-responded to the SST forcing. They are deliberately not collapsed into a new index.",
    )
    add_ordinary_event_table(doc, ordinary)
    add_paragraph(
        doc,
        "The January-June composite Niño3 SST of the seven ordinary events is about -0.06 deg C because many ordinary "
        "events do not enter their growth phase until late spring or early summer. The raw composite is therefore a calendar-"
        "stage benchmark, not a same-amplitude counterfactual for 2023/24. Figures 12-14 show its SST-wind, precipitation-wind, "
        "and D20-wind evolution. All wind maps use a common vector scale, with a separate white-backed, unit-labeled key in "
        "the lower-right corner of every panel.",
    )
    add_figure(doc, ORDINARY_FIGURES["sst"], "Figure 12. Ordinary non-extreme El Niño composite: January-June OISST SSTA and ERA5 850 hPa wind anomalies (n=7).")
    add_figure(doc, ORDINARY_FIGURES["precip"], "Figure 13. Ordinary non-extreme El Niño composite: January-June ERA5 precipitation and 850 hPa wind anomalies (n=7).")
    add_figure(doc, ORDINARY_FIGURES["d20"], "Figure 14. Ordinary non-extreme El Niño composite: January-June ORAS5 equatorial D20 anomalies and ERA5 u850 (n=7).")
    add_paragraph(
        doc,
        "In the 2023-minus-ordinary fields, eastern-Pacific surface and subsurface warming remains pronounced, whereas "
        "western-central Pacific low-level winds and central-Pacific precipitation do not strengthen proportionally. This "
        "is a spatial residual pattern of a strong ocean signal with limited atmospheric follow-through. Because onset timing "
        "varies among ordinary events, Figure 15 is used to locate the response gap rather than to provide amplitude control.",
    )
    add_figure(doc, ORDINARY_FIGURES["difference"], "Figure 15. January-June 2023 minus the ordinary non-extreme El Niño composite: SST, precipitation/u850, and equatorial D20/u850 differences.")
    add_expected_response_table(doc, ordinary)
    add_figure(doc, ORDINARY_FIGURES["expected"], "Figure 16. Observed and SST-conditioned historical atmospheric responses in 2015, 2023, and the 2026 developing state. Calendar-month regressions are fitted over 1982-2014.")
    add_heading(doc, "EP/CP Robustness Check", level=2)
    add_paragraph(
        doc,
        "Using published event categories, the EP subset contains 1986, 1991, and 2006 (n=3), whereas the CP subset "
        "contains 1994, 2002, 2004, and 2009 (n=4). Their precipitation-wind patterns differ, confirming that a pooled "
        "composite can blur response-center differences. The samples are too small for a new primary conclusion, so this "
        "remains a qualitative sensitivity test. Yan et al. (2025) supplies the physical motivation for distinct EP/CP "
        "rainfall responses; discrete event assignments follow Beniche et al. (2024).",
    )
    add_figure(doc, ORDINARY_FIGURES["ep_cp"], "Figure 17. EP and CP sensitivity of January-June precipitation and u850 within the ordinary-event sample; qualitative because n=3 and n=4.")

    add_heading(doc, "Similarities and Differences among the Three Events", level=1)
    add_paragraph(
        doc,
        "The 2015/16 event is the clearest example of strong coupling during development. Central and central-eastern "
        "Pacific SST anomalies became positive relatively early, westerly anomalies were strong, central-Pacific "
        "precipitation turned positive early, and D20 showed a clear shallow-west/deep-east structure. Ocean dynamics, "
        "low-level winds, and convection strengthened in a coordinated manner.",
    )
    add_paragraph(
        doc,
        "The 2023/24 development phase was more strongly led by the far eastern Pacific. FEP SST was relatively the most "
        "prominent of the three events, while CP SST and PMM support were weaker and the precipitation and low-level-wind "
        "responses to SST were less synchronous than in 2015. It therefore resembled an eastern-initiation event that "
        "subsequently connected westward.",
    )
    add_paragraph(
        doc,
        "The 2026 event shows a distinct staged transition. During January-April, eastern-Pacific SST still led while "
        "convection lagged. By June, however, CP/EP warming, strong westerlies, positive precipitation anomalies, and the "
        "shallow-west/deep-east D20 structure appeared together, shifting the event toward a 2015-like strong-coupling "
        "framework. It is not a simple repetition of 2015, but the evidence through June no longer supports persistent "
        "air-sea decoupling.",
    )

    add_heading(doc, "Conclusion", level=1)
    add_paragraph(
        doc,
        "With the ordinary-event benchmark and SST-conditioned expectation added, the most robust conclusion is that the "
        "weak 2023/24 atmospheric response was not merely weak relative to a super El Niño such as 2015/16. After controlling "
        "calendar-month Niño3 SST amplitude, CWP u850 and central-Pacific precipitation still fell below their historical "
        "expectations by about 0.86 m/s and 1.88 mm/day, respectively. This supports a mechanism in which strong initial ocean "
        "memory promoted eastern-Pacific warming while the atmospheric positive feedback was not fully realized. The record "
        "through June 2026 is retained only as an out-of-sample developing state: SST, westerlies, precipitation, and thermocline "
        "adjustment strengthened together in June, but the available months do not justify declaring a completed El Niño event.",
    )

    add_heading(doc, "Method References", level=1)
    add_paragraph(
        doc,
        "Peng et al. (2025), Nature Geoscience, doi:10.1038/s41561-025-01700-9: ocean initial conditions and wind-stress effects in 2023/24 versus strong events.\n"
        "Beniche et al. (2024), Scientific Reports, doi:10.1038/s41598-024-52580-9: moderate/extreme event grouping, composites, bootstrap, and CT/WP event categories.\n"
        "Kim et al. (2025), npj Climate and Atmospheric Science, doi:10.1038/s41612-024-00890-0: persistent easterlies limiting 2023/24 development.\n"
        "Yan et al. (2025), npj Climate and Atmospheric Science, doi:10.1038/s41612-025-00933-0: contrasting EP/CP rainfall and Walker-circulation responses.\n"
        "Srinivas et al. (2024), Scientific Reports, doi:10.1038/s41598-024-58803-3: structural and nonlinear response differences between all-event and extreme-event composites.",
        size=9.2,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build_doc()
