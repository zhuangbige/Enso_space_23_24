#!/usr/bin/env python3
"""Translate the finalized ENSO report to English without rebuilding its layout."""

from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path

from lxml import etree


SOURCE = Path(
    "/Users/daiyue/Documents/Maryland/outputs/research_2026/reports/"
    "ENSO发展期_SSTA-OHC不同步_阶段性汇报_赤道带与纬向剖面修正版_"
    "统一1982_2024基准_暖核公式与完整符号说明版_20260818.docx"
)
OUTPUT = Path(
    "/Users/daiyue/Documents/Maryland/outputs/research_2026/reports/"
    "ENSO_Development_Phase_SSTA_OHC_Desynchronization_Final_English_"
    "Times_New_Roman_20260818.docx"
)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
W = f"{{{NS['w']}}}"
M = f"{{{NS['m']}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


TRANSLATIONS: dict[int, str] = {
    0: "Data and Core Formulations Used in This Report",
    1: (
        "This report compares the January-June evolution of sea surface temperature, "
        "upper-ocean heat storage, and wind fields in 1997, 2015, and 2023, and extends "
        "the meridional-vertical structures identified in these three case studies to "
        "13 ENSO warm events."
    ),
    2: "Data",
    3: (
        "Sea surface temperature and SST indices. Monthly NOAA OISST is used to construct "
        "SSTA maps and calculate the Niño3, Niño3.4, and Niño4 indices. OISST anomalies are "
        "defined relative to same-calendar-month linear detrending over 1982-2024."
    ),
    4: (
        "Three-dimensional ocean temperature and OHC. Monthly SODA3.15.2 temperature is "
        "used, retaining the native depth levels in the upper 300 m. Temperature, "
        "heat-content density, and 0-300 m OHC all use same-calendar-month linear detrending "
        "over 1982-2024."
    ),
    5: (
        "Wind fields and atmospheric coupling metrics. Spatial maps are overlaid with ERA5 "
        "850-hPa wind anomalies, defined using same-calendar-month linear detrending over "
        "1982-2024. The cross-event coupling response uses GPCP precipitation, ERA5 sea level "
        "pressure, and ERA5 zonal wind stress. Historical expected relationships are trained "
        "over 1982-2014 using leave-one-year-out fits for each calendar month."
    ),
    6: (
        "Events and time windows. The case studies are 1997, 2015, and 2023. The cross-event "
        "analysis includes 1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, "
        "2019, and 2023. JFM is the oceanic predictor window and JJA is the atmospheric "
        "response window."
    ),
    7: "Same-Calendar-Month Linearly Detrended Anomalies",
    9: (
        "Here, X(y,m) is the original monthly value of variable X in year y and month m; "
        "X′(y,m) is the anomaly after removing the same-calendar-month mean and linear trend; "
        "y denotes year and m denotes calendar month; ⟨X⟩m is the 1982-2024 mean of all samples "
        "for calendar month m; bm is the linear trend slope fitted using only month-m samples, "
        "with units of X per year; ȳ is the mean year of the reference period and equals 2003 "
        "for 1982-2024; bm(y−ȳ) is the trend term relative to the mean year; angle brackets "
        "⟨·⟩ denote averaging."
    ),
    10: "Heat-Content Density and OHC per Unit Area",
    12: (
        "Here, {EQ0} is the volumetric heat-content-density anomaly, with SI units of J m⁻³ "
        "and plotted in MJ m⁻³; {EQ1}=1025 kg m⁻³ is the reference seawater density; "
        "{EQ2}=3990 J kg⁻¹ K⁻¹ is the specific heat capacity of seawater at constant pressure; "
        "{EQ3} is the same-calendar-month linearly detrended temperature anomaly and has the "
        "same numerical value in K and °C; {EQ4} is the OHC anomaly per unit horizontal area at "
        "time t within latitude band B and depth layer L, with SI units of J {EQ5} and reported "
        "here in GJ {EQ6}; {EQ7} is longitude, and z is depth positive downward; {EQ8} is the "
        "cosine-latitude-weighted temperature anomaly within band B; {EQ9} denotes averaging "
        "over the selected longitude window."
    ),
    13: "Cross-Event Spreading Metric and JJA Coupling Residual",
    14: "Domain Definitions",
    15: (
        "Maps cover 30°S-30°N, 120°E-80°W; FEP is defined as 5°S-5°N, 90°W-80°W. "
        "Longitude-depth sections are cosine-weighted averages over 5°S-5°N, whereas "
        "latitude-depth sections are averaged over the fixed full-longitude range "
        "120°E-80°W. Cross-event calculations follow the centroid longitude λc of the positive "
        "equatorial OHC warm core for each event, use a λc±10° window, and divide the domain "
        "into equatorial, southern, and northern bands: 5°S-5°N, 15°S-5°S, and 5°N-15°N."
    ),
    16: (
        "Warm-Core Centroid and Moving Window. Based on the cosine-weighted 5°S-5°N section, "
        "positive heat-content-density anomalies are weighted by grid-cell area; j and k "
        "denote depth and longitude, respectively, and no additional peak threshold is imposed."
    ),
    19: (
        "Here, q′j,k is the heat-content-density anomaly at depth layer j and longitude grid "
        "point k after cosine-weighted averaging over 5°S-5°N; {EQ0}= {EQ1} is its positive "
        "part, so cold anomalies receive zero weight; j indexes depth layers and k indexes "
        "longitude grid points; {EQ2} is the thickness of layer j, and {EQ3} is the zonal width "
        "represented by longitude grid point k; {EQ4} is the centroid weight. If q′ is in MJ "
        "{EQ5} and a is in {EQ6}, W has units of MJ {EQ7}, although only relative weights are "
        "used in the centroid calculation; λk and zj are the longitude-grid and depth-layer "
        "centers; {EQ8} and {EQ9} are the weighted centroid longitude and depth of the warm core; "
        "{EQ10} denotes summation over all j,k cells within 120°E-80°W and 0-300 m; {EQ11} is "
        "the warm-core-following moving window used for the subsequent three-band OHC calculation."
    ),
    20: "Off-Equatorial Heat Content and the Three-Band Area-Weighted Mean OHC",
    24: (
        "Here, {EQ0}, {EQ1}, and {EQ2} are the JFM-mean 0-300 m OHC anomalies per unit area in "
        "the 5°S-5°N equatorial band, 15°S-5°S southern band, and 5°N-15°N northern band, "
        "respectively, within the event-specific warm-core window centered on {EQ3}±10°; their "
        "units are GJ {EQ4}. {EQ5} is the arithmetic mean OHC of the southern and northern "
        "bands; {EQ6} is the area-weighted mean OHC of the three bands, not the "
        "volume-integrated total heat content of the full ocean domain; {EQ7},B is the relative "
        "spherical-area weight of band B, and {EQ8} and {EQ9} are its southern and northern "
        "latitude boundaries; i indexes the 13 ENSO warm events; α is the intercept and β is "
        "the coefficient multiplying {EQ10} in the linear regression of {EQ11}; {EQ12} is the "
        "off-equatorial OHC residual for event i after removing the linear influence of the "
        "three-band mean OHC, with units of GJ {EQ13}."
    ),
    25: (
        "The x axis uses residual {EQ0}. {EQ1}>0 indicates that, for the same three-band "
        "area-weighted mean OHC, relatively more 0-300 m heat is located on the two sides of "
        "the equator; {EQ2}<0 indicates that heat is relatively concentrated in the equatorial "
        "band. This metric describes the relative allocation between equatorial and "
        "off-equatorial regions and cannot separately identify an off-equatorial increase from "
        "an equatorial decrease."
    ),
    26: "JJA Pattern-Adjusted Composite Coupling Residual",
    27: (
        "The three atmospheric components are GPCP precipitation over 5°S-5°N, 180°E-250°E; "
        "the ERA5 zonal sea level pressure gradient, defined as 130°E-160°E minus "
        "220°E-250°E; and ERA5 zonal wind stress over 5°S-5°N, 160°E-220°E. The expected "
        "atmospheric response for each calendar month is"
    ),
    31: (
        "Here, A is one atmospheric response variable for a given calendar month: GPCP "
        "equatorial-Pacific precipitation, the ERA5 zonal sea level pressure gradient, or ERA5 "
        "central-western Pacific zonal wind stress; {EQ0} is the regression intercept; {EQ1} is "
        "the coefficient of long-term linear change; year is the sample year, and year−1998 is "
        "the time term centered on 1998, the midpoint of the 1982-2014 training period; {EQ2} "
        "and {EQ3} are the regression coefficients of A on SST amplitude and the EP-CP pattern, "
        "respectively; ε is the unexplained model residual."
    ),
    32: (
        "Here, {EQ0} is the predicted value of A obtained from same-calendar-month "
        "leave-one-year-out training over 1982-2014; {EQ1} is the standard deviation of the "
        "corresponding training-sample regression residual ε; {EQ2} is the cross-validated "
        "standardized residual of atmospheric variable A; {EQ3}, {EQ4}, and {EQ5} are the "
        "standardized residuals of precipitation, the sea level pressure gradient, and zonal "
        "wind stress, respectively; {EQ6} denotes averaging over June-August; {EQ7} is the "
        "equally weighted three-component JJA composite coupling residual for event i, in z "
        "units; {EQ8} is the JJA coupling residual for event i after further removing the "
        "linear influence of JFM three-band mean OHC; {EQ9} or {EQ10}>0 indicates an atmospheric "
        "response stronger than the historical expectation for the same SST amplitude and "
        "pattern, whereas <0 indicates a weaker response."
    ),
    33: (
        "{EQ0} and {EQ1} are both obtained from same-calendar-month leave-one-year-out training "
        "over 1982-2014, so {EQ2} is a cross-validated standardized residual. {EQ3} is the JJA "
        "coupling residual after further controlling for the JFM three-band area-weighted mean "
        "OHC. Thus, the final correlation compares early meridional heat allocation with the "
        "strength of the subsequent JJA coupling response under the same three-band mean heat "
        "content."
    ),
    34: "1997: Full-Depth Warming Leads, Followed by a Surface Surge",
    35: (
        "In the FEP, OHC had already become positive in February, whereas SSTA did not turn "
        "positive until March; both then strengthened rapidly and synchronously from March "
        "through June. Spatially, warm OHC expanded eastward along the equator from the central "
        "Pacific, followed by a pronounced increase in far-eastern SSTA in May-June."
    ),
    37: (
        "Fig. 1(a): January-June 1997 OISST sea surface temperature anomalies (shading) and "
        "ERA5 850-hPa wind anomalies (vectors). The domain is 30°S-30°N, 120°E-80°W. OISST and "
        "ERA5 winds are same-calendar-month linearly detrended anomalies over 1982-2024. The "
        "wind-vector scale is 4 m s⁻¹ in each panel; dashed boxes mark the Niño3, Niño3.4, EP, "
        "and FEP diagnostic regions."
    ),
    39: (
        "Fig. 1(b): January-June 1997 SODA3 0-300 m OHC anomalies per unit area (shading) and "
        "ERA5 850-hPa wind anomalies (vectors). The domain is the same as in Fig. 1(a). OHC and "
        "wind are same-calendar-month linearly detrended anomalies over 1982-2024. A common "
        "±3 GJ m⁻² color scale is used for all three events, and the wind-vector scale is "
        "4 m s⁻¹ in each panel."
    ),
    40: (
        "Figure 1 shows that full-depth warming in 1997 preceded sustained surface warming in "
        "the eastern Pacific, after which the two intensified rapidly and synchronously."
    ),
    42: "2015: Persistent Subsurface Warming, Brief Surface Cooling",
    43: (
        "In January 2015, both the surface and OHC anomalies were positive, but FEP SSTA "
        "returned to negative values in February-March while OHC remained weakly positive. "
        "Both strengthened again after April. This event shows that full-depth heat storage can "
        "persist while the surface fluctuates under short-term heat-flux or advective influences."
    ),
    45: (
        "Fig. 2(a): January-June 2015 OISST sea surface temperature anomalies and ERA5 850-hPa "
        "wind anomalies. Shading, vectors, diagnostic boxes, spatial domain, anomaly baseline, "
        "and wind-vector scale are the same as in Fig. 1(a)."
    ),
    47: (
        "Fig. 2(b): January-June 2015 SODA3 0-300 m OHC anomalies per unit area and ERA5 850-hPa "
        "wind anomalies. The spatial domain, anomaly baseline, wind-vector scale, and common "
        "color scale are the same as in Fig. 1(b)."
    ),
    48: (
        "Figure 2 shows that the brief surface cooling in 2015 did not eliminate upper-ocean "
        "heat storage; the subsurface warm tongue continued to support subsequent development."
    ),
    50: (
        "2023: Far-Eastern Surface Warming Leads, with Full-Depth Warming Catching Up About One "
        "Month Later"
    ),
    51: (
        "In January 2023, both the eastern-Pacific surface and 0-300 m OHC displayed interleaved "
        "positive and negative anomalies. In February, a local surface warm anomaly first "
        "emerged in the far-eastern equatorial Pacific, especially near 90°W; at similar "
        "longitudes, however, the full-depth OHC warm anomaly was still weak, and some areas "
        "remained near zero or were anomalously cold. After March, warm OHC gradually expanded "
        "eastward, increasing the spatial overlap between surface and full-depth warming, which "
        "was broadly maintained over the following months."
    ),
    53: (
        "Fig. 3(a): January-June 2023 OISST sea surface temperature anomalies and ERA5 850-hPa "
        "wind anomalies. A local warm anomaly had already appeared in the far-eastern FEP in "
        "February; shading, vectors, diagnostic boxes, spatial domain, anomaly baseline, and "
        "wind-vector scale are the same as in Fig. 1(a)."
    ),
    55: (
        "Fig. 3(b): January-June 2023 SODA3 0-300 m OHC anomalies per unit area and ERA5 850-hPa "
        "wind anomalies. The spatial domain, anomaly baseline, wind-vector scale, and common "
        "color scale are the same as in Fig. 1(b)."
    ),
    56: (
        "Figure 3 shows that far-eastern surface warming led in 2023, and the surface and "
        "full-depth fields did not enter coherent development until after March."
    ),
    58: (
        "Continuous Section Structure: Eastward Migration and Meridional Spreading of "
        "Equatorial Warm Anomalies"
    ),
    59: (
        "The longitude-depth sections retain the original 5°S-5°N equatorial band to track the "
        "warm tongue from west to east and from depth toward the surface. The subsequent "
        "latitude-depth sections are averaged over the fixed full-longitude range 120°E-80°W "
        "to compare the meridional structures of the three events."
    ),
    61: (
        "Fig. 4: Longitude-depth sections of equatorial-Pacific heat-content-density anomalies, "
        "q′=ρ₀cₚT′, for January-June 1997, 2015, and 2023. Rows correspond to 1997, 2015, and "
        "2023, and columns to January-June. The sections use cosine-latitude weighting over "
        "5°S-5°N, native SODA3 levels in the upper 300 m, and a longitude range of 120°E-80°W. "
        "Anomalies are same-calendar-month linearly detrended over 1982-2024. All panels use a "
        "common color scale in MJ m⁻³."
    ),
    62: (
        "In early 1997, a pronounced warm core occupied approximately 100-200 m in the central "
        "Pacific; it shoaled and propagated eastward in spring, producing a deep eastern-Pacific "
        "warm anomaly. In 2015, the subsurface warm tongue continuously linked the central and "
        "eastern Pacific from the beginning of the year; even during the brief surface cooling, "
        "the deeper warm anomaly persisted, indicating strong ocean memory. In early 2023, the "
        "warm water was farther west and deeper, while the far-eastern surface warmed first and "
        "the warm tongue subsequently shoaled and propagated eastward; by early summer, the "
        "deep-ocean support remained weaker than in 1997 and 2015."
    ),
    64: "Latitude-Depth Sections Averaged over the Fixed Full-Longitude Range",
    65: (
        "Each monthly panel below is averaged over the same 120°E-80°W range. This diagnostic "
        "compares basin-mean meridional and vertical structures; because the zonal signal is "
        "averaged out, the eastward migration of the warm core should still be interpreted "
        "together with Fig. 4."
    ),
    66: "1997 Full-Longitude Mean",
    68: (
        "Fig. 5: January-June 1997 latitude-depth heat-content-density anomalies averaged over "
        "the fixed 120°E-80°W range. The domain is 30°S-30°N and 0-300 m. SODA3 temperature and "
        "same-calendar-month linearly detrended anomalies over 1982-2024 are used. All six "
        "months share a ±6 MJ m⁻³ color scale."
    ),
    69: (
        "Fig. 6: January-June 2015 latitude-depth heat-content-density anomalies averaged over "
        "the fixed 120°E-80°W range. The spatial domain, anomaly definition, and common color "
        "scale are the same as in Fig. 5."
    ),
    71: (
        "Fig. 7: January-June 2023 latitude-depth heat-content-density anomalies averaged over "
        "the fixed 120°E-80°W range. The spatial domain, anomaly definition, and common color "
        "scale are the same as in Fig. 5."
    ),
    72: (
        "All three events show equatorial warm anomalies gradually shoaling, but their "
        "meridional structures differ markedly. In 1997, warming was concentrated near the "
        "equator at 100-200 m, with stronger cold anomalies at 5°-15°N, forming a clear "
        "“equatorial warm-northern cold” structure. In 2015, warming was shallower and more "
        "tightly concentrated near the equator; northern cold anomalies were also pronounced, "
        "whereas southern warm anomalies were weaker and discontinuous. By contrast, the "
        "northern cold anomalies in 2023 occupied a smaller area, and warm anomalies remained "
        "just north of the equator. More importantly, broad and deep warm anomalies were "
        "already present over 0°-20°S at the beginning of the year and persisted through spring "
        "and summer without turning into a coherent cold anomaly. Local cold anomalies were "
        "still present at 10°-15°N in 2023; therefore, the more accurate characterization is not "
        "“no anomalous cooling at all,” but persistent and pronounced excessive spreading of "
        "southern warm anomalies."
    ),
    73: (
        "Thus, the distinctive feature of 2023 was not merely a southward displacement of "
        "heat. Rather, heat was not concentrated near the equatorial warm core but spread to "
        "both sides of the equator, especially southward, producing a broader and deeper heat "
        "distribution. This configuration may reduce the fraction of heat in the equatorial "
        "surface layer that can directly participate in the SST-convection-wind feedback. This "
        "observation motivates the following cross-event test: for similar three-band mean OHC, "
        "does placing more early-season heat off the equator lead to a weaker JJA air-sea "
        "coupling response?"
    ),
    74: (
        "From Case Studies to Cross-Event Evidence: Does Heat Spreading Affect Development-Phase "
        "Coupling?"
    ),
    75: (
        "The central clue from the 2023 sections is not merely a southward displacement of heat. "
        "Early warm anomalies were distributed across the equatorial band and both flanks and "
        "were stored more strongly below the surface, producing a broader and deeper oceanic "
        "heat configuration. To test whether this structure is meaningful across events, we "
        "extend the analysis by asking: when the three-band area-weighted mean OHC is similar, "
        "does greater heat allocation to the two sides of the equator weaken the subsequent "
        "conversion of ocean heat storage into the equatorial surface-convection-wind feedback?"
    ),
    76: (
        "For 13 ENSO warm events, we calculate JFM 0-300 m OHC in three latitude bands—5°S-5°N, "
        "5°-15°S, and 5°-15°N—using a ±10° longitude window that follows the centroid of the "
        "positive equatorial OHC warm core. Off-equatorial heat content is defined as the mean "
        "OHC of the southern and northern bands, with the linear influence of the three-band "
        "area-weighted mean OHC removed. This metric is then compared with the JJA "
        "pattern-adjusted composite air-sea coupling residual, which controls for Niño3.4 "
        "amplitude, the Niño3-Niño4 spatial pattern, and long-term linear change."
    ),
    78: (
        "Fig. 8: Relationship between meridional OHC configuration near the JFM warm core and "
        "the subsequent JJA development-phase air-sea response across 13 ENSO warm events. The "
        "x axis is the residual of off-equatorial 0-300 m OHC after controlling for the "
        "three-band area-weighted mean OHC; the y axis is the JJA pattern-adjusted coupling "
        "residual after controlling for the same oceanic quantity. Ocean data are from "
        "SODA3.15.2; the longitude window follows the warm-core centroid ±10°, the latitude "
        "range is 15°S-15°N, and anomalies are same-calendar-month linearly detrended over "
        "1982-2024. The coupling residual controls for SST amplitude and the EP-CP pattern; gray "
        "shading shows the 95% interval of regression lines from event resampling."
    ),
    79: (
        "Across the 13 warm events, greater JFM off-equatorial heat content is followed by a "
        "weaker JJA pattern-adjusted air-sea coupling response (partial r=−0.79, permutation "
        "p=0.002, FDR q=0.006). Leave-one-event-out correlations remain between −0.83 and −0.73, "
        "showing that the relationship is not determined by any single 1997, 2015, or 2023 "
        "event. The result indicates that, beyond the three-band mean heat content, the "
        "concentration of heat near the equator is related to the relative strength of the "
        "subsequent air-sea coupling response and is consistent with reduced coupling-conversion "
        "efficiency."
    ),
    81: "The analysis supports three conclusions:",
    82: (
        "Conclusion 1. The ocean did not lack heat in 2023, but during the early development "
        "phase the heat was located mainly in the western basin, below the surface, and south "
        "of the equator. It did not overlap promptly with surface warming in the eastern "
        "equatorial Pacific, indicating slower establishment of development-phase air-sea "
        "coupling rather than persistent decoupling during the mature phase."
    ),
    83: (
        "Conclusion 2. Compared with 1997 and 2015, warm anomalies in 2023 were broader and "
        "deeper. As heat spread to both sides of the equator and into the subsurface, the "
        "fraction of heat in the equatorial surface layer that could directly participate in "
        "the convection-wind feedback may have declined."
    ),
    84: (
        "Conclusion 3. Across 13 warm events, after controlling for the three-band area-weighted "
        "mean OHC, greater JFM off-equatorial heat content was followed by a weaker JJA air-sea "
        "coupling response (r=−0.79, p=0.002)."
    ),
}


ALT_TEXTS = {
    1: "January-June 1997 OISST anomalies and ERA5 850-hPa wind anomalies",
    2: "January-June 1997 SODA3 upper-300-m OHC anomalies and ERA5 850-hPa wind anomalies",
    3: "January-June 2015 OISST anomalies and ERA5 850-hPa wind anomalies",
    4: "January-June 2015 SODA3 upper-300-m OHC anomalies and ERA5 850-hPa wind anomalies",
    5: "January-June 2023 OISST anomalies and ERA5 850-hPa wind anomalies",
    6: "January-June 2023 SODA3 upper-300-m OHC anomalies and ERA5 850-hPa wind anomalies",
    7: "Longitude-depth heat-content-density anomaly sections for 1997, 2015, and 2023",
    8: "January-June 1997 latitude-depth heat-content-density anomaly sections",
    9: "January-June 2015 latitude-depth heat-content-density anomaly sections",
    10: "January-June 2023 latitude-depth heat-content-density anomaly sections",
    11: "Cross-event relationship between meridional OHC spreading and JJA coupling response",
}


def outside_math(node: etree._Element) -> bool:
    parent = node.getparent()
    while parent is not None:
        if parent.tag == f"{M}oMath":
            return False
        parent = parent.getparent()
    return True


def set_text(node: etree._Element, value: str) -> None:
    node.text = value
    if value.startswith(" ") or value.endswith(" "):
        node.set(XML_SPACE, "preserve")
    else:
        node.attrib.pop(XML_SPACE, None)


def paragraph_groups(paragraph: etree._Element) -> tuple[list[list[etree._Element]], int]:
    events = paragraph.xpath(".//w:t[not(ancestor::m:oMath)] | .//m:oMath", namespaces=NS)
    groups: list[list[etree._Element]] = [[]]
    equation_count = 0
    for event in events:
        if event.tag == f"{M}oMath":
            equation_count += 1
            groups.append([])
        else:
            groups[-1].append(event)
    return groups, equation_count


def replace_paragraph(paragraph: etree._Element, template: str, paragraph_index: int) -> None:
    groups, equation_count = paragraph_groups(paragraph)
    marker_numbers = [int(number) for number in re.findall(r"\{EQ(\d+)\}", template)]
    if marker_numbers != list(range(equation_count)):
        raise ValueError(
            f"Paragraph {paragraph_index}: equation markers {marker_numbers} do not match "
            f"the {equation_count} source equations"
        )
    segments = re.split(r"\{EQ\d+\}", template)
    if len(segments) != len(groups):
        raise ValueError(f"Paragraph {paragraph_index}: text/equation group mismatch")
    for group_index, (nodes, segment) in enumerate(zip(groups, segments)):
        if not nodes and segment:
            raise ValueError(
                f"Paragraph {paragraph_index}, group {group_index}: no source text node "
                "available for translated prose"
            )
        if nodes:
            set_text(nodes[0], segment)
            for node in nodes[1:]:
                set_text(node, "")


def set_times_new_roman(root: etree._Element) -> int:
    count = 0
    for run in root.xpath(".//w:r", namespaces=NS):
        if not outside_math(run):
            continue
        if not run.xpath(".//w:t | .//w:instrText", namespaces=NS):
            continue
        run_properties = run.find(f"{W}rPr")
        if run_properties is None:
            run_properties = etree.Element(f"{W}rPr")
            run.insert(0, run_properties)
        fonts = run_properties.find(f"{W}rFonts")
        if fonts is None:
            fonts = etree.Element(f"{W}rFonts")
            run_properties.insert(0, fonts)
        for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(f"{W}{attribute}", "Times New Roman")
        count += 1
    return count


def patch_document_xml(data: bytes) -> tuple[bytes, dict[str, int]]:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(data, parser)
    paragraphs = root.xpath("/w:document/w:body/w:p", namespaces=NS)
    if len(paragraphs) != 85:
        raise ValueError(f"Expected 85 body paragraphs, found {len(paragraphs)}")

    required = {
        index
        for index, paragraph in enumerate(paragraphs)
        if any((node.text or "") for node in paragraph.xpath(
            ".//w:t[not(ancestor::m:oMath)]", namespaces=NS
        ))
    }
    if required != set(TRANSLATIONS):
        missing = sorted(required - set(TRANSLATIONS))
        extra = sorted(set(TRANSLATIONS) - required)
        raise ValueError(f"Translation index mismatch; missing={missing}, extra={extra}")

    for index in sorted(TRANSLATIONS):
        replace_paragraph(paragraphs[index], TRANSLATIONS[index], index)

    doc_properties = root.xpath(".//wp:docPr", namespaces=NS)
    if len(doc_properties) != 11:
        raise ValueError(f"Expected 11 image properties, found {len(doc_properties)}")
    for image_index, properties in enumerate(doc_properties, start=1):
        properties.set("descr", ALT_TEXTS[image_index])
        if "title" in properties.attrib:
            properties.set("title", ALT_TEXTS[image_index])

    formatted_runs = set_times_new_roman(root)
    cjk_nodes = [
        node
        for node in root.xpath(".//w:t", namespaces=NS)
        if re.search(r"[\u3400-\u9fff]", node.text or "")
    ]
    if cjk_nodes:
        examples = [node.text for node in cjk_nodes[:5]]
        raise ValueError(f"Chinese text remains in document.xml: {examples}")

    return (
        etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes"),
        {
            "paragraphs": len(paragraphs),
            "translated_paragraphs": len(TRANSLATIONS),
            "equations": len(root.xpath(".//m:oMath", namespaces=NS)),
            "images": len(doc_properties),
            "formatted_runs": formatted_runs,
        },
    )


def patch_footer_xml(data: bytes) -> tuple[bytes, int]:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(data, parser)
    count = set_times_new_roman(root)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes"), count


def copy_zipinfo(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    copied = copy.copy(info)
    copied.CRC = 0
    copied.file_size = 0
    copied.compress_size = 0
    return copied


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    stats: dict[str, int] = {}
    with zipfile.ZipFile(SOURCE, "r") as source_zip, zipfile.ZipFile(OUTPUT, "w") as output_zip:
        for info in source_zip.infolist():
            payload = source_zip.read(info.filename)
            if info.filename == "word/document.xml":
                payload, stats = patch_document_xml(payload)
            elif info.filename.startswith("word/footer") and info.filename.endswith(".xml"):
                payload, footer_runs = patch_footer_xml(payload)
                stats["footer_formatted_runs"] = stats.get("footer_formatted_runs", 0) + footer_runs
            output_zip.writestr(copy_zipinfo(info), payload, compress_type=info.compress_type)

    with zipfile.ZipFile(OUTPUT, "r") as check_zip:
        bad = check_zip.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP member: {bad}")
        if "word/document.xml" not in check_zip.namelist():
            raise RuntimeError("Output is missing word/document.xml")

    print(f"Created: {OUTPUT}")
    print(f"Paragraphs: {stats['paragraphs']}")
    print(f"Translated paragraphs: {stats['translated_paragraphs']}")
    print(f"Native equations preserved: {stats['equations']}")
    print(f"Images preserved: {stats['images']}")
    print(f"Times New Roman text runs: {stats['formatted_runs']}")
    print(f"Times New Roman footer runs: {stats.get('footer_formatted_runs', 0)}")


if __name__ == "__main__":
    main()
