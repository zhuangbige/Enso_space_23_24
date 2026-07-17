#!/usr/bin/env python3
"""Build the minimal monthly ENSO air--sea coupling closure diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from el_nino_decoupling.coupling_chain import (  # noqa: E402
    BASELINE_END,
    BASELINE_START,
    LINK_SPECS,
    bootstrap_event_eta,
    build_monthly_table,
    eta_from_diagnostics,
    event_diagnostics,
    event_window,
    fit_monthly_models,
    pseudo_event_distribution,
    replace_product,
    validate_monthly_table,
)


DEFAULT_OUTPUT_DIR = ROOT / "outputs/research_2026/air_sea_coupling_minimal"
DEFAULT_ERA5_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"
INPUTS = {
    "oisst": ROOT / "data/interim/research_2026/oisst_nino3_monthly_1982_2026m05.csv",
    "ersst": ROOT / "data/interim/raw_validation/ersstv5_nino3_monthly.csv",
    "d20": ROOT / "data/interim/research_2026/oras5_d20_timeseries_equatorial_1960_202605.csv",
    "oras5_stress": ROOT
    / "data/interim/research_2026/oras5_windstress_timeseries_equatorial_1980_202605.csv",
    "gpcp": ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc",
    "olr": ROOT / "data/interim/raw_validation/olr_monthly.csv",
}
EVENTS = {
    "1997/98": (pd.Timestamp(1997, 4, 1), pd.Timestamp(1998, 2, 1), 1997),
    "2015/16": (pd.Timestamp(2015, 4, 1), pd.Timestamp(2016, 2, 1), 2015),
    "2023/24": (pd.Timestamp(2023, 4, 1), pd.Timestamp(2024, 2, 1), 2023),
}


def _metadata_path(path: Path) -> str:
    """Prefer repository-relative source paths while preserving external inputs."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT.resolve()))
    except ValueError:
        return str(resolved)


LINK_LABELS_CN = {
    "atmospheric": "Niño3 SST → 中西太平洋纬向风应力",
    "ocean_adjustment": "纬向风应力 → D20 倾斜",
    "thermocline_feedback": "东部 D20 → Niño3 SST 增长",
    "thermal_damping": "Niño3 SST → 净表面热通量阻尼",
}


def _event_coefficients(table: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if start.year <= BASELINE_END:
        return fit_monthly_models(table, exclude_windows=((start, end),))
    return fit_monthly_models(table)


def _score_events(
    table: pd.DataFrame,
    *,
    product_combo: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    coefficients = []
    diagnostics = []
    scores = []
    for label, (start, end, _) in EVENTS.items():
        model = _event_coefficients(table, start, end).copy()
        model["fit_for_event"] = label
        model["product_combo"] = product_combo
        coefficients.append(model)
        monthly = event_diagnostics(
            table,
            model,
            event_label=label,
            start=start,
            end=end,
            product_combo=product_combo,
        )
        diagnostics.append(monthly)
        scores.append(eta_from_diagnostics(monthly))
    return (
        pd.concat(coefficients, ignore_index=True),
        pd.concat(diagnostics, ignore_index=True),
        pd.concat(scores, ignore_index=True),
    )


def _attach_inference(
    scores: pd.DataFrame,
    bootstrap: pd.DataFrame,
    pseudo: pd.DataFrame,
) -> pd.DataFrame:
    output = scores.merge(bootstrap, on=["event", "link"], how="left")
    event_year_lookup = {label: year for label, (_, _, year) in EVENTS.items()}
    rows = []
    for _, row in output.iterrows():
        distribution = pseudo[pseudo["link"] == row["link"]]
        event_year = event_year_lookup.get(str(row["event"]))
        if event_year is not None:
            distribution = distribution[distribution["event_year"] != event_year]
        values = distribution["eta"].dropna().to_numpy(float)
        p05 = float(np.quantile(values, 0.05))
        p95 = float(np.quantile(values, 0.95))
        eta = float(row["eta"])
        percentile = float(100 * np.mean(values <= eta))
        record = row.to_dict()
        record.update(
            {
                "historical_p05": p05,
                "historical_p95": p95,
                "historical_percentile": percentile,
                "significantly_weakened": bool(
                    eta < p05 and np.isfinite(row.get("ci_high", np.nan)) and float(row["ci_high"]) < 1
                ),
                "inference_rule": "eta < historical p05 and bootstrap 95% CI upper < 1",
                "status": "complete_event",
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)


def _partial_2026(table: pd.DataFrame, coefficients: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(2026, 1, 1)
    end = pd.Timestamp(2026, 5, 1)
    monthly = event_diagnostics(
        table,
        coefficients,
        event_label="2026 Jan-May",
        start=start,
        end=end,
        product_combo="OISST+ERA5",
    )
    score = eta_from_diagnostics(monthly)
    score["ci_low"] = np.nan
    score["ci_high"] = np.nan
    score["bootstrap_median"] = np.nan
    score["n_bootstrap"] = 0
    score["block_months"] = 24
    score["seed"] = np.nan
    score["historical_p05"] = np.nan
    score["historical_p95"] = np.nan
    score["historical_percentile"] = np.nan
    score["significantly_weakened"] = False
    score["inference_rule"] = "not applied to incomplete validation window"
    score["status"] = "partial_validation_not_event_comparable"
    return monthly, score


def _convection_validation(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    baseline = table[(table.index.year >= BASELINE_START) & (table.index.year <= BASELINE_END)]
    for response, label in (
        ("gpcp_cwp_anom", "CWP GPCP precipitation"),
        ("olr_cp_anom", "CP CPC OLR"),
    ):
        if response not in table:
            continue
        pair = baseline[["tau_x_era5_anom", response]].dropna()
        corr = float(pair.corr().iloc[0, 1])
        target = table.loc[pd.Timestamp(2023, 4, 1) : pd.Timestamp(2024, 2, 1)]
        rows.append(
            {
                "response": response,
                "response_label": label,
                "historical_tau_correlation": corr,
                "historical_n_months": int(len(pair)),
                "event_2023_24_response_mean": float(target[response].mean()),
                "event_2023_24_tau_mean": float(target["tau_x_era5_anom"].mean()),
                "role": "supporting validation; not a fifth feedback link",
            }
        )
    return pd.DataFrame(rows)


def _write_summary(
    output: Path,
    scores: pd.DataFrame,
    sensitivity: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    target = scores[(scores["event"] == "2023/24") & (scores["status"] == "complete_event")].copy()
    target = target.sort_values(["historical_percentile", "eta"])
    minimum_percentile = float(target["historical_percentile"].min())
    lowest_history = target[np.isclose(target["historical_percentile"], minimum_percentile)]
    weakest_eta = target.loc[target["eta"].idxmin()]
    significant = target[target["significantly_weakened"]]
    if significant.empty:
        low_names = "、".join(LINK_LABELS_CN[str(link)] for link in lowest_history["link"])
        history_phrase = (
            f"{low_names}（均为第 {minimum_percentile:.1f} 百分位）"
            if len(lowest_history) > 1
            else f"{low_names}（第 {minimum_percentile:.1f} 百分位）"
        )
        conclusion = (
            f"2023/24 历史相对位置最低的是 {history_phrase}；"
            f"其中 {LINK_LABELS_CN[str(weakest_eta['link'])]} 的实现率最低（eta={weakest_eta['eta']:.2f}）。"
            "但没有反馈链同时满足预设的双重显著性标准。"
        )
    else:
        names = "、".join(LINK_LABELS_CN[str(link)] for link in significant["link"])
        conclusion = f"2023/24 显著减弱的反馈链为：{names}。"

    lines = [
        "# 2023/24 厄尔尼诺海气耦合最小闭环：结果摘要",
        "",
        conclusion,
        "",
        "## 2023/24 四条反馈链",
        "",
        "| 反馈链 | eta | 95% CI | 历史百分位 | 显著减弱 |",
        "|---|---:|---:|---:|:---:|",
    ]
    for _, row in target.iterrows():
        lines.append(
            f"| {LINK_LABELS_CN[str(row['link'])]} | {row['eta']:.2f} | "
            f"[{row['ci_low']:.2f}, {row['ci_high']:.2f}] | "
            f"{row['historical_percentile']:.1f} | {'是' if row['significantly_weakened'] else '否'} |"
        )
    lines.extend(
        [
            "",
            "## 判据",
            "",
            "只有当 eta 低于历史 April-February 伪事件分布第 5 百分位，且 24 个月块自助法的 95% CI 上限低于 1，才称为显著减弱。",
            "",
            "## 稳健性",
            "",
            "ERSST 与 ORAS5 风应力只作为产品敏感性试验；若反馈链排序变化，最终报告标记为资料依赖。",
            "",
            "## 对流验证",
            "",
        ]
    )
    for _, row in validation.iterrows():
        lines.append(
            f"- {row['response_label']} 与 ERA5 纬向风应力的历史月相关为 "
            f"{row['historical_tau_correlation']:.2f}（n={int(row['historical_n_months'])}）。"
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    output_dir = args.output_dir
    table_dir = output_dir / "tables"
    figure_dir = output_dir / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    monthly = build_monthly_table(
        oisst_path=args.oisst,
        ersst_path=args.ersst,
        d20_path=args.d20,
        oras5_stress_path=args.oras5_stress,
        era5_dir=args.era5_dir,
        gpcp_path=args.gpcp,
        olr_path=args.olr,
    )
    validation_meta = validate_monthly_table(monthly)
    monthly.reset_index().to_csv(table_dir / "coupling_link_monthly.csv", index=False, float_format="%.8g")

    primary_models, primary_monthly, primary_scores = _score_events(
        monthly, product_combo="OISST+ERA5"
    )
    base_model = fit_monthly_models(monthly)
    base_model["fit_for_event"] = "1982-2022 frozen baseline / 2026"
    base_model["product_combo"] = "OISST+ERA5"
    all_models = pd.concat([base_model, primary_models], ignore_index=True)

    pseudo = pseudo_event_distribution(monthly)
    bootstrap_rows = []
    if args.n_bootstrap > 0:
        for index, (label, (start, end, _)) in enumerate(EVENTS.items()):
            excluded = ((start, end),) if start.year <= BASELINE_END else ()
            bootstrap_rows.append(
                bootstrap_event_eta(
                    monthly,
                    event_label=label,
                    start=start,
                    end=end,
                    exclude_windows=excluded,
                    n_bootstrap=args.n_bootstrap,
                    block_months=args.block_months,
                    seed=args.seed + index,
                )
            )
    bootstrap = (
        pd.concat(bootstrap_rows, ignore_index=True)
        if bootstrap_rows
        else pd.DataFrame(columns=["event", "link", "ci_low", "ci_high"])
    )
    inferred = _attach_inference(primary_scores, bootstrap, pseudo)
    partial_monthly, partial_score = _partial_2026(monthly, base_model)
    event_scores = pd.concat([inferred, partial_score], ignore_index=True, sort=False)
    event_monthly = pd.concat([primary_monthly, partial_monthly], ignore_index=True)

    sensitivity_parts = [primary_scores.assign(sensitivity_role="primary")]
    for product_combo, variant in (
        ("ERSST+ERA5", replace_product(monthly, sst_column="nino3_sst_ersst_anom")),
        ("OISST+ORAS5", replace_product(monthly, stress_column="tau_x_oras5_anom")),
    ):
        _, _, score = _score_events(variant, product_combo=product_combo)
        score["sensitivity_role"] = "product_sensitivity"
        sensitivity_parts.append(score)
    sensitivity = pd.concat(sensitivity_parts, ignore_index=True)
    validation = _convection_validation(monthly)

    memory = event_monthly[
        event_monthly["link"].isin(["ocean_adjustment", "thermocline_feedback"])
    ].copy()
    memory = memory[
        [
            "event",
            "link",
            "time",
            "target_time",
            "actual_target",
            "intercept",
            "memory_contribution",
            "expected_feedback",
            "predicted_target",
            "residual",
            "target_units",
        ]
    ]

    all_models.to_csv(table_dir / "coupling_model_coefficients.csv", index=False, float_format="%.8g")
    event_monthly.to_csv(
        table_dir / "coupling_event_monthly_diagnostics.csv", index=False, float_format="%.8g"
    )
    event_scores.to_csv(table_dir / "coupling_event_scores.csv", index=False, float_format="%.8g")
    memory.to_csv(table_dir / "coupling_memory_forcing.csv", index=False, float_format="%.8g")
    sensitivity.to_csv(table_dir / "coupling_sensitivity.csv", index=False, float_format="%.8g")
    validation.to_csv(table_dir / "coupling_convection_validation.csv", index=False, float_format="%.8g")
    pseudo.to_csv(table_dir / "historical_pseudo_event_eta.csv", index=False, float_format="%.8g")
    bootstrap.to_csv(table_dir / "coupling_bootstrap_summary.csv", index=False, float_format="%.8g")

    metadata = {
        "analysis": "minimal monthly ENSO air-sea coupling closure",
        "baseline": [BASELINE_START, BASELINE_END],
        "events": {label: [str(start.date()), str(end.date())] for label, (start, end, _) in EVENTS.items()},
        "regions": {
            "Nino3": "5S-5N, 150W-90W",
            "CWP_stress": "5S-5N, 160E-140W",
            "D20_east": "equator, 150W-100W",
            "D20_west": "equator, 140E-170W",
        },
        "qnet_sign": "positive downward; sum of net SW, net LW, latent and sensible heat flux",
        "bootstrap": {
            "n": args.n_bootstrap,
            "block_months": args.block_months,
            "seed": args.seed,
        },
        "inference": "eta < historical p05 and bootstrap 95% CI upper < 1",
        "validation": validation_meta,
        "sources": {
            "oisst": _metadata_path(args.oisst),
            "ersst": _metadata_path(args.ersst),
            "d20": _metadata_path(args.d20),
            "oras5_stress": _metadata_path(args.oras5_stress),
            "gpcp": _metadata_path(args.gpcp),
            "olr": _metadata_path(args.olr),
            "era5": _metadata_path(args.era5_dir),
        },
        "links": [spec.__dict__ for spec in LINK_SPECS],
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    _write_summary(output_dir / "analysis_summary_cn.md", event_scores, sensitivity, validation)
    print(output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--era5-dir", type=Path, default=DEFAULT_ERA5_DIR)
    parser.add_argument("--oisst", type=Path, default=INPUTS["oisst"])
    parser.add_argument("--ersst", type=Path, default=INPUTS["ersst"])
    parser.add_argument("--d20", type=Path, default=INPUTS["d20"])
    parser.add_argument("--oras5-stress", type=Path, default=INPUTS["oras5_stress"])
    parser.add_argument("--gpcp", type=Path, default=INPUTS["gpcp"])
    parser.add_argument("--olr", type=Path, default=INPUTS["olr"])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--n-bootstrap", type=int, default=10_000)
    parser.add_argument("--block-months", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260716)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
