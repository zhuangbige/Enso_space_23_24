#!/usr/bin/env python3
"""Apply the simplified primary statistical model to the finalized ENSO report."""

from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path

from lxml import etree


SOURCE = Path(
    "/Users/daiyue/Library/Containers/com.tencent.xinWeChat/Data/Library/Caches/"
    "com.tencent.xinWeChat/2.0b4.0.9/7666f44fdf715bc28336d1e11a523974/"
    "SaveTemp/ed4aea7a069a85737477e58cae7a9b32/"
    "ENSO_Development_Phase_SSTA_OHC_Desynchronization.docx"
)
OUTPUT = Path(
    "/Users/daiyue/Documents/Maryland/outputs/research_2026/reports/"
    "ENSO_Development_Phase_SSTA_OHC_Desynchronization_"
    "Simplified_Primary_Model.docx"
)
FIGURE = Path("/private/tmp/enso_stat_revision/figure8_primary_model.png")

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
W = f"{{{NS['w']}}}"
M = f"{{{NS['m']}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def set_text(node: etree._Element, value: str) -> None:
    node.text = value
    if value.startswith(" ") or value.endswith(" "):
        node.set(XML_SPACE, "preserve")
    else:
        node.attrib.pop(XML_SPACE, None)


def replace_plain_paragraph(paragraph: etree._Element, text: str) -> None:
    text_nodes = paragraph.xpath(".//w:t[not(ancestor::m:oMath)]", namespaces=NS)
    if not text_nodes:
        raise ValueError("Paragraph has no writable text node")
    set_text(text_nodes[0], text)
    for node in text_nodes[1:]:
        set_text(node, "")


def first_prose_run_properties(paragraph: etree._Element) -> etree._Element | None:
    for run in paragraph.xpath(".//w:r[.//w:t]", namespaces=NS):
        properties = run.find(f"{W}rPr")
        if properties is not None:
            return copy.deepcopy(properties)
    return None


def prose_run(text: str, run_properties: etree._Element | None) -> etree._Element:
    run = etree.Element(f"{W}r")
    if run_properties is not None:
        run.append(copy.deepcopy(run_properties))
    else:
        properties = etree.SubElement(run, f"{W}rPr")
        fonts = etree.SubElement(properties, f"{W}rFonts")
        for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(f"{W}{attribute}", "Times New Roman")
    text_node = etree.SubElement(run, f"{W}t")
    set_text(text_node, text)
    return run


def replace_mixed_paragraph(
    paragraph: etree._Element,
    segments: list[str],
    equations: list[etree._Element],
) -> None:
    if len(segments) != len(equations) + 1:
        raise ValueError("Mixed paragraph segment/equation mismatch")
    run_properties = first_prose_run_properties(paragraph)
    paragraph_properties = paragraph.find(f"{W}pPr")
    for child in list(paragraph):
        if child is not paragraph_properties:
            paragraph.remove(child)
    for index, segment in enumerate(segments):
        if segment:
            paragraph.append(prose_run(segment, run_properties))
        if index < len(equations):
            paragraph.append(copy.deepcopy(equations[index]))


def equation_text(element: etree._Element) -> str:
    return "".join(element.xpath(".//m:t/text()", namespaces=NS))


def find_math_child(equation: etree._Element, text: str) -> etree._Element:
    for child in equation:
        if equation_text(child) == text:
            return copy.deepcopy(child)
    raise ValueError(f"Could not find equation component: {text}")


def sample_math_run(root: etree._Element) -> etree._Element:
    sample = root.xpath(".//m:r[m:t]", namespaces=NS)[0]
    return copy.deepcopy(sample)


def math_run(root: etree._Element, text: str) -> etree._Element:
    run = sample_math_run(root)
    text_nodes = run.xpath("./m:t", namespaces=NS)
    if not text_nodes:
        raise ValueError("Math run lacks m:t")
    text_nodes[0].text = text
    for node in text_nodes[1:]:
        run.remove(node)
    if text.startswith(" ") or text.endswith(" "):
        text_nodes[0].set(XML_SPACE, "preserve")
    else:
        text_nodes[0].attrib.pop(XML_SPACE, None)
    return run


def subscript(
    root: etree._Element,
    base: str,
    subscript_parts: list[str],
    template_subscript: etree._Element,
) -> etree._Element:
    structure = etree.Element(f"{M}sSub")
    template_properties = template_subscript.find(f"{M}sSubPr")
    if template_properties is not None:
        structure.append(copy.deepcopy(template_properties))
    base_element = etree.SubElement(structure, f"{M}e")
    base_element.append(math_run(root, base))
    sub_element = etree.SubElement(structure, f"{M}sub")
    for part in subscript_parts:
        sub_element.append(math_run(root, part))
    return structure


def make_inline_equation(children: list[etree._Element]) -> etree._Element:
    equation = etree.Element(f"{M}oMath")
    for child in children:
        equation.append(copy.deepcopy(child))
    return equation


def replace_display_equation(
    paragraph: etree._Element, children: list[etree._Element]
) -> None:
    equations = paragraph.xpath(".//m:oMath", namespaces=NS)
    if len(equations) != 1:
        raise ValueError("Expected one display equation")
    equation = equations[0]
    for child in list(equation):
        equation.remove(child)
    for child in children:
        equation.append(copy.deepcopy(child))


def patch_document_xml(data: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(data, parser)
    paragraphs = root.xpath("/w:document/w:body/w:p", namespaces=NS)
    if len(paragraphs) != 85:
        raise ValueError(f"Expected 85 body paragraphs, found {len(paragraphs)}")

    source_p23_equation = paragraphs[23].xpath(".//m:oMath", namespaces=NS)[0]
    source_p30_equation = paragraphs[30].xpath(".//m:oMath", namespaces=NS)[0]
    source_p24_equations = paragraphs[24].xpath(".//m:oMath", namespaces=NS)
    source_p32_equations = paragraphs[32].xpath(".//m:oMath", namespaces=NS)
    template_subscript = source_p23_equation.find(f"{M}sSub")
    if template_subscript is None:
        raise ValueError("Could not locate a subscript template")

    h_off_i = find_math_child(source_p23_equation, "Hoff,i")
    hbar_i = find_math_child(source_p30_equation, "H3band,i")
    c_jja_i = find_math_child(source_p30_equation, "CJJA,i")
    d_i = subscript(root, "D", ["i"], template_subscript)
    h_e_i = subscript(root, "H", ["E", ",", "i"], template_subscript)
    beta_0 = subscript(root, "β", ["0"], template_subscript)
    beta_1 = subscript(root, "β", ["1"], template_subscript)
    beta_2 = subscript(root, "β", ["2"], template_subscript)
    epsilon_i = subscript(root, "ε", ["i"], template_subscript)

    replace_plain_paragraph(
        paragraphs[13],
        "Cross-Event Meridional Configuration Metric and Primary JJA Coupling Model",
    )
    replace_plain_paragraph(
        paragraphs[20],
        "Off-Equatorial Heat Content, Three-Band Mean OHC, and Meridional Contrast",
    )
    replace_display_equation(
        paragraphs[23],
        [
            d_i,
            math_run(root, "="),
            h_off_i,
            math_run(root, "−"),
            h_e_i,
        ],
    )

    p24_equations = [copy.deepcopy(eq) for eq in source_p24_equations[:10]]
    p24_equations.append(make_inline_equation([d_i]))
    replace_mixed_paragraph(
        paragraphs[24],
        [
            "Here, ",
            ", ",
            ", and ",
            " are the JFM-mean 0-300 m OHC anomalies per unit area in the 5°S-5°N equatorial band, 15°S-5°S southern band, and 5°N-15°N northern band, respectively, within the event-specific warm-core window centered on ",
            "±10°; their units are GJ ",
            ". ",
            " is the arithmetic mean OHC of the southern and northern bands; ",
            " is the area-weighted mean OHC of the three bands, not the volume-integrated heat content of the full ocean domain; ",
            " is the relative spherical-area weight of band B, and ",
            " and ",
            " are its southern and northern latitude boundaries. The index i identifies the 13 ENSO warm events. ",
            " is the meridional heat-configuration contrast: positive values indicate relatively more heat off the equator, whereas negative values indicate relatively greater concentration in the equatorial band.",
        ],
        p24_equations,
    )
    replace_mixed_paragraph(
        paragraphs[25],
        [
            "This parameterization separates overall ocean heat amount from meridional allocation. The primary analysis therefore enters both predictors in one multiple linear model. The residual-residual scatter in Fig. 8 is only a partial-regression visualization of that model, not an additional analytical stage."
        ],
        [],
    )

    replace_plain_paragraph(
        paragraphs[26],
        "Pattern-Adjusted JJA Coupling Index and Primary Regression",
    )
    replace_plain_paragraph(
        paragraphs[27],
        "Step 1 defines the atmospheric coupling anomaly. The three atmospheric components are GPCP precipitation over 5°S-5°N, 180°E-250°E; the ERA5 zonal sea level pressure gradient, defined as 130°E-160°E minus 220°E-250°E; and ERA5 zonal wind stress over 5°S-5°N, 160°E-220°E. The expected atmospheric response for each calendar month is",
    )
    replace_display_equation(
        paragraphs[30],
        [
            c_jja_i,
            math_run(root, "="),
            beta_0,
            math_run(root, "+"),
            beta_1,
            hbar_i,
            math_run(root, "+"),
            beta_2,
            d_i,
            math_run(root, "+"),
            epsilon_i,
        ],
    )

    p32_equations = [
        copy.deepcopy(source_p32_equations[index])
        for index in [0, 1, 2, 3, 4, 5, 6, 7, 9]
    ]
    replace_mixed_paragraph(
        paragraphs[32],
        [
            "Here, ",
            " is the predicted value of A obtained from same-calendar-month leave-one-year-out training over 1982-2014; ",
            " is the standard deviation of the corresponding training-sample regression residual; ",
            " is the cross-validated standardized residual of atmospheric variable A; ",
            ", ",
            ", and ",
            " are the standardized residuals of precipitation, the sea level pressure gradient, and zonal wind stress, respectively; ",
            " denotes averaging over June-August; ",
            " is the equally weighted three-component JJA composite coupling index for event i, in z units. A positive ",
            " indicates an atmospheric response stronger than the historical expectation for the same SST amplitude and pattern; a negative value indicates a weaker response.",
        ],
        p32_equations,
    )
    replace_mixed_paragraph(
        paragraphs[33],
        [
            "Step 2 tests oceanic configuration with the single OLS model shown above. The response is the JJA coupling index, the three-band mean OHC controls overall heat amount, and ",
            " is the primary predictor of meridional allocation. The coefficient ",
            " is tested against zero with a two-sided t test. By the Frisch-Waugh-Lovell result, the residual-residual scatter in Fig. 8 is an equivalent partial-regression visualization, not an additional analysis. A 100,000-draw Freedman-Lane permutation test and leave-one-event-out analysis are retained as robustness checks.",
        ],
        [make_inline_equation([d_i]), make_inline_equation([beta_2])],
    )

    replace_plain_paragraph(
        paragraphs[76],
        "For 13 ENSO warm events, we calculate JFM 0-300 m OHC in three latitude bands—5°S-5°N, 5°-15°S, and 5°-15°N—using a ±10° longitude window that follows the centroid of the positive equatorial OHC warm core. The meridional configuration contrast is defined as mean off-equatorial OHC minus equatorial OHC. The primary OLS model relates the JJA coupling index to the three-band area-weighted mean OHC, which controls overall heat amount, and the meridional contrast, which represents spatial allocation. The coupling index has already been adjusted for Niño3.4 amplitude, the Niño3-Niño4 pattern, and long-term linear change.",
    )
    replace_plain_paragraph(
        paragraphs[78],
        "Fig. 8: Partial-regression visualization of the primary multiple linear model across 13 ENSO warm events. The x axis is the residual of the JFM meridional heat-configuration contrast, defined as off-equatorial 0-300 m OHC minus equatorial OHC, after controlling for the three-band area-weighted mean OHC. The y axis is the residual of the JJA pattern-adjusted coupling index after controlling for the same mean OHC. Ocean data are from SODA3.15.2; the longitude window follows the warm-core centroid ±10°, the latitude range is 15°S-15°N, and anomalies are same-calendar-month linearly detrended over 1982-2024. The gray envelope is the 95% interval of event-resampled regression lines. The main inference uses the two-sided analytic test; Freedman-Lane permutation and leave-one-event-out results are robustness checks.",
    )
    replace_plain_paragraph(
        paragraphs[79],
        "In the primary model, a larger JFM off-equatorial-minus-equatorial heat contrast is associated with a weaker subsequent JJA coupling response after controlling for three-band mean OHC. The estimated contrast coefficient is −3.09 z per GJ m⁻² (95% CI: −4.76 to −1.41), with partial r=−0.79 (Fisher 95% CI: −0.94 to −0.40), t(10)=−4.11, and two-sided p=0.002. Significance is also supported by a 100,000-draw Freedman-Lane permutation test (p=0.003), while leave-one-event-out partial correlations remain between −0.83 and −0.73. The result is therefore presented as one primary amount-plus-configuration regression, with the resampling analyses serving only as robustness checks.",
    )
    replace_plain_paragraph(
        paragraphs[84],
        "Conclusion 3. Across 13 warm events, the primary multiple regression shows that a larger JFM off-equatorial-minus-equatorial heat contrast is followed by a weaker JJA air-sea coupling response after controlling for three-band area-weighted mean OHC (partial r=−0.79, 95% CI: −0.94 to −0.40, p=0.002).",
    )

    image_properties = root.xpath(".//wp:docPr", namespaces=NS)
    if len(image_properties) != 11:
        raise ValueError(f"Expected 11 images, found {len(image_properties)}")
    image_properties[10].set(
        "descr",
        "Partial-regression relationship between the JFM meridional heat-configuration contrast and the JJA coupling response across 13 ENSO warm events",
    )

    stale_terms = ["FDR q", "Residual rank", "corr(X", "off-equatorial OHC residual"]
    visible_text = "".join(root.xpath(".//w:t/text()", namespaces=NS))
    for term in stale_terms:
        if term in visible_text:
            raise ValueError(f"Stale statistical term remains: {term}")

    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone="yes"
    )


def copy_zipinfo(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    copied = copy.copy(info)
    copied.CRC = 0
    copied.file_size = 0
    copied.compress_size = 0
    return copied


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    if not FIGURE.exists():
        raise FileNotFoundError(FIGURE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    with zipfile.ZipFile(SOURCE, "r") as source_zip, zipfile.ZipFile(OUTPUT, "w") as output_zip:
        for info in source_zip.infolist():
            payload = source_zip.read(info.filename)
            if info.filename == "word/document.xml":
                payload = patch_document_xml(payload)
            elif info.filename == "word/media/image11.png":
                payload = FIGURE.read_bytes()
            output_zip.writestr(copy_zipinfo(info), payload, compress_type=info.compress_type)

    with zipfile.ZipFile(OUTPUT, "r") as check_zip:
        corrupt_member = check_zip.testzip()
        if corrupt_member:
            raise RuntimeError(f"Corrupt DOCX member: {corrupt_member}")
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
