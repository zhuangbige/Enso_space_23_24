#!/usr/bin/env python3
"""Build the curated figure package for the three warm-heat-fate questions."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/research_2026/three_questions_figure_package_20260805"

MAIN = [
    (
        "outputs/research_2026/soda3_ohc300_hovmoller_1997_2015_2023.png",
        "Fig01_eastward_OHC_arrival_hovmoller.png",
        "问题一",
        "主文",
        "展示1997、2015、2023暖量向东到达及盆地深层支撑差异。",
    ),
    (
        "outputs/research_2026/soda3_three_box_warm_heat_fate/soda3_three_box_warm_heat_fate.png",
        "Fig02_CT_CP_three_box_arrival_and_fate.png",
        "问题一/二",
        "主文",
        "证明CT与CP都能把暖量送到东部，但到达强度和衰减期分配不同。",
    ),
    (
        "outputs/research_2026/enso_1997_2015_2023_warm_heat_fate_bridge/enso_1997_2015_2023_warm_heat_fate_bridge.png",
        "Fig03_event_arrival_export_surface_loss.png",
        "问题二",
        "主文",
        "比较三个事件的暖量输入、5°N输出和海表散热。",
    ),
    (
        "outputs/research_2026/enso_1997_2015_2023_5n_geostrophic_fate/enso_1997_2015_2023_5n_geostrophic_fate.png",
        "Fig04_event_5N_dynamical_decomposition.png",
        "问题二/三",
        "主文",
        "将5°N出口差异分解为Ekman、地转和残差。",
    ),
    (
        "outputs/research_2026/soda3_fep_transition/jiang_fep_soda3_ohc_d20_1997_2015_2023.png",
        "Fig05_FEP_subsurface_preconditioning.png",
        "问题三",
        "主文",
        "说明相似FEP先暖对应不同OHC和D20背景。",
    ),
    (
        "outputs/research_2026/soda3_fep_transition/jiang_fep_soda3_u850_olr_1997_2015_2023.png",
        "Fig06_FEP_atmospheric_closure.png",
        "问题三",
        "主文",
        "定位FEP之后海洋转变和大气闭合的先后差异。",
    ),
    (
        "outputs/research_2026/compare_1997_2023_coupling/1997_2023_coupling_chain_comparison.png",
        "Fig07_1997_2023_coupled_mechanism_synthesis.png",
        "问题三",
        "主文",
        "综合比较1997和2023的海洋预置、对流接通和暖量出口。",
    ),
    (
        "outputs/research_2026/third_question_coupled_attribution/Fig08_third_question_coupled_attribution.png",
        "Fig08_third_question_coupled_attribution.png",
        "问题三",
        "主文",
        "用13事件统计和1997/2015/2023风应力替换定量归因第三个问题。",
    ),
]

SUPPLEMENT = [
    (
        "outputs/research_2026/soda3_three_box_warm_heat_fate/soda3_east_box_development_decay_fate.png",
        "FigS01_east_box_development_decay.png",
        "问题一/二",
        "补充",
        "CT/CP东部箱发展—衰减预算反转。",
    ),
    (
        "outputs/research_2026/soda3_warm_heat_budget_decomposition/soda3_warm_heat_budget_decomposition.png",
        "FigS02_full_budget_residual_decomposition.png",
        "问题二",
        "补充",
        "对暖量预算剩余项进行进一步过程拆解。",
    ),
    (
        "outputs/research_2026/soda3_5n_current_decomposition/soda3_5n_current_decomposition.png",
        "FigS03_CT_CP_5N_current_decomposition.png",
        "问题二/三",
        "补充",
        "CT/CP复合的5°N地转—Ekman分解。",
    ),
    (
        "outputs/research_2026/soda3_5n_coupled_timing/soda3_5n_coupled_timing.png",
        "FigS04_CT_CP_coupled_timing.png",
        "问题三",
        "补充",
        "CT/CP海温、降水、风应力与出口的逐月时序。",
    ),
    (
        "outputs/research_2026/soda3_air_sea_coupled_fate/soda3_air_sea_coupled_warm_heat_sequence.png",
        "FigS05_CT_CP_air_sea_sequence.png",
        "问题三",
        "补充",
        "CT/CP海气耦合复合序列。",
    ),
    (
        "outputs/research_2026/era5_full_stress_curl_warm_heat/era5_full_stress_curl_warm_heat.png",
        "FigS06_ERA5_full_stress_curl.png",
        "问题三",
        "补充",
        "ERA5全风应力旋度独立验证。",
    ),
    (
        "outputs/research_2026/soda3_5n_wind_stress_counterfactual/soda3_5n_wind_stress_counterfactual.png",
        "FigS07_wind_stress_counterfactual.png",
        "问题三",
        "补充",
        "固定温度结构下的风应力敏感性，不能替代正式模式因果试验。",
    ),
    (
        "outputs/research_2026/soda3_mixed_layer_budget/soda3_mixed_layer_budget_transition_evidence.png",
        "FigS08_mixed_layer_budget_transition.png",
        "问题二",
        "补充",
        "日界线输送与混合层预算的过渡证据。",
    ),
    (
        "outputs/research_2026/soda3_warm_heat_box_budget/soda3_warm_heat_box_budget.png",
        "FigS09_warm_heat_box_budget.png",
        "问题一/二",
        "补充",
        "160°E–180°暖量箱预算和脉冲依赖。",
    ),
]

EXPLORATORY = [
    ("outputs/research_2026/soda3_compensation_threshold/soda3_compensation_threshold_event_paths.png", "X01_compensation_event_paths.png"),
    ("outputs/research_2026/soda3_compensation_threshold/soda3_compensation_threshold_verification.png", "X02_compensation_verification.png"),
    ("outputs/research_2026/soda3_balance_transition_sequence/soda3_balance_transition_sequence.png", "X03_balance_transition_sequence.png"),
    ("outputs/research_2026/soda3_force_balance/soda3_force_balance_tendency_verification.png", "X04_force_balance_verification.png"),
    ("outputs/research_2026/soda3_force_balance_residual/soda3_force_balance_residual_attribution.png", "X05_force_balance_residual.png"),
    ("outputs/research_2026/soda3_high_frequency_wind_gate/soda3_high_frequency_wind_gate_skill.png", "X06_high_frequency_wind_gate.png"),
    ("outputs/research_2026/soda3_reservoir_release_coupling/soda3_reservoir_release_coupling.png", "X07_reservoir_release_coupling.png"),
    ("outputs/research_2026/soda3_5day_ohc_geometry_coupling/soda3_5day_ohc_geometry_mechanism_events.png", "X08_OHC_geometry_mechanism.png"),
    ("outputs/research_2026/soda3_5day_ohc_geometry_coupling/soda3_5day_ohc_geometry_skill_and_matches.png", "X09_OHC_geometry_skill.png"),
]


def copy_group(records, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for record in records:
        source, target = record[:2]
        shutil.copy2(ROOT / source, directory / target)


def make_contact_sheet(directory: Path, names: list[str], output: Path, columns: int) -> None:
    thumb_width = 620
    thumb_height = 440
    label_height = 48
    gap = 16
    cells = []
    for name in names:
        image = Image.open(directory / name).convert("RGB")
        image.thumbnail((thumb_width - 20, thumb_height - 20))
        cell = Image.new("RGB", (thumb_width, thumb_height + label_height), "white")
        x = (thumb_width - image.width) // 2
        y = label_height + (thumb_height - image.height) // 2
        cell.paste(image, (x, y))
        ImageDraw.Draw(cell).text((10, 10), name, fill="black")
        cells.append(cell)
    rows = (len(cells) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (
            columns * thumb_width + (columns - 1) * gap,
            rows * (thumb_height + label_height) + (rows - 1) * gap,
        ),
        (220, 220, 220),
    )
    for index, cell in enumerate(cells):
        x = (index % columns) * (thumb_width + gap)
        y = (index // columns) * (thumb_height + label_height + gap)
        sheet.paste(cell, (x, y))
    sheet.save(output)


def write_manifest() -> None:
    rows = []
    for category, records in (("主文", MAIN), ("补充", SUPPLEMENT)):
        for source, target, question, role, claim in records:
            rows.append([category, target, question, role, claim, source])
    for source, target in EXPLORATORY:
        rows.append(["探索", target, "后续", "暂不入稿", "需进一步独立验证或模式试验。", source])
    with (OUT / "figure_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["类别", "统一文件名", "对应问题", "论文角色", "核心用途/判断", "原始路径"])
        writer.writerows(rows)


def main() -> None:
    main_dir = OUT / "01_main_figures"
    supplement_dir = OUT / "02_supplementary_figures"
    exploratory_dir = OUT / "03_exploratory_not_for_manuscript"
    copy_group(MAIN, main_dir)
    copy_group(SUPPLEMENT, supplement_dir)
    copy_group(EXPLORATORY, exploratory_dir)
    make_contact_sheet(main_dir, [row[1] for row in MAIN], main_dir / "_main_contact_sheet.png", 2)
    make_contact_sheet(
        supplement_dir,
        [row[1] for row in SUPPLEMENT],
        supplement_dir / "_supplement_contact_sheet.png",
        3,
    )
    make_contact_sheet(
        exploratory_dir,
        [row[1] for row in EXPLORATORY],
        exploratory_dir / "_exploratory_contact_sheet.png",
        3,
    )
    source_pdf = ROOT / "outputs/research_2026/soda3_ohc300_hovmoller_1997_2015_2023.pdf"
    if source_pdf.exists():
        shutil.copy2(source_pdf, main_dir / "Fig01_eastward_OHC_arrival_hovmoller.pdf")
    write_manifest()
    print(OUT)


if __name__ == "__main__":
    main()
