#!/usr/bin/env python3
"""Create a sign-safe scientific summary of the completed Isca P0 screen.

The script refuses partial model output.  It translates every diagnostic into
one common physical orientation (positive means a more favorable atmospheric
connection), while retaining the original model units and contrasts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


METRIC_LABELS = {
    "precip_tp_mm_day": "Tropical-Pacific precipitation",
    "precip_cp_mm_day": "Central-Pacific precipitation",
    "olr_cp_w_m2": "Central-Pacific -OLR",
    "peng_cwp_u10_m_s": "Peng CWP zonal wind",
    "tau_cwp_ocean_n_m2": "Eastward ocean stress",
    "slp_drive_w_minus_e_hpa": "West-minus-east SLP drive",
}
METRIC_UNITS = {
    "precip_tp_mm_day": "mm day-1",
    "precip_cp_mm_day": "mm day-1",
    "olr_cp_w_m2": "W m-2",
    "peng_cwp_u10_m_s": "m s-1",
    "tau_cwp_ocean_n_m2": "N m-2",
    "slp_drive_w_minus_e_hpa": "hPa",
}
CONTRASTS = (
    "FEP_at_IA0",
    "FEP_at_IA1",
    "IA_at_FEP0",
    "IA_at_FEP1",
    "IA_x_FEP",
)
EXPECTED_ROWS = len(METRIC_LABELS) * len(CONTRASTS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_verified(result_dir: Path) -> pd.DataFrame:
    audit_path = result_dir / "p0_verification.json"
    summary_path = result_dir / "p0_mjj_factorial_summary.csv"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    required_audit = (
        audit.get("complete") is True
        and audit.get("expected_files") == 240
        and audit.get("valid_files") == 240
        and audit.get("invalid_files") == 0
        and audit.get("errors") == []
    )
    if not required_audit:
        raise SystemExit(f"P0 audit is not complete: {audit_path}")

    frame = pd.read_csv(summary_path)
    required_columns = {
        "season",
        "metric",
        "contrast",
        "n_members",
        "mean",
        "sd",
        "ci95_low",
        "ci95_high",
        "same_sign_fraction",
    }
    if set(frame.columns) < required_columns:
        raise SystemExit(f"Missing summary columns: {required_columns - set(frame.columns)}")
    if len(frame) != EXPECTED_ROWS:
        raise SystemExit(f"Expected {EXPECTED_ROWS} summary rows, found {len(frame)}")
    if set(frame["metric"]) != set(METRIC_LABELS):
        raise SystemExit(f"Unexpected metrics: {sorted(set(frame['metric']))}")
    if set(frame["contrast"]) != set(CONTRASTS):
        raise SystemExit(f"Unexpected contrasts: {sorted(set(frame['contrast']))}")
    if not frame["season"].eq("MJJ").all() or not frame["n_members"].eq(10).all():
        raise SystemExit("Expected MJJ and n_members=10 for every row")
    numeric = frame[["mean", "sd", "ci95_low", "ci95_high", "same_sign_fraction"]]
    if not np.isfinite(numeric.to_numpy(float)).all():
        raise SystemExit("Non-finite values in factorial summary")
    if not ((frame["ci95_low"] <= frame["mean"]) & (frame["mean"] <= frame["ci95_high"])).all():
        raise SystemExit("A mean lies outside its bootstrap interval")
    return frame


def orient(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["orientation"] = np.where(result["metric"].eq("olr_cp_w_m2"), -1.0, 1.0)
    result["metric_label"] = result["metric"].map(METRIC_LABELS)
    result["unit"] = result["metric"].map(METRIC_UNITS)
    result["oriented_mean"] = result["orientation"] * result["mean"]
    low = result["orientation"] * result["ci95_low"]
    high = result["orientation"] * result["ci95_high"]
    result["oriented_ci95_low"] = np.minimum(low, high)
    result["oriented_ci95_high"] = np.maximum(low, high)
    result["physical_direction"] = np.select(
        [
            result["oriented_ci95_low"] > 0,
            result["oriented_ci95_high"] < 0,
            result["oriented_mean"] > 0,
            result["oriented_mean"] < 0,
        ],
        [
            "robust_favorable",
            "robust_adverse",
            "uncertain_favorable_mean",
            "uncertain_adverse_mean",
        ],
        default="zero_or_undetermined",
    )
    result["member_consistency"] = np.select(
        [result["same_sign_fraction"] >= 0.8, result["same_sign_fraction"] >= 0.7],
        ["high", "moderate"],
        default="low",
    )
    return result


def interaction_audit(oriented: pd.DataFrame) -> dict[str, object]:
    interaction = oriented.loc[oriented["contrast"].eq("IA_x_FEP")].copy()
    rows = []
    for row in interaction.itertuples(index=False):
        suppressive_mean = row.oriented_mean < 0
        ci_excludes_zero = row.oriented_ci95_high < 0
        same_sign_high = row.same_sign_fraction >= 0.8
        if suppressive_mean and ci_excludes_zero and same_sign_high:
            grade = "strong_suppressive"
        elif suppressive_mean and (ci_excludes_zero or same_sign_high):
            grade = "suggestive_suppressive"
        elif suppressive_mean:
            grade = "weak_suppressive_mean_only"
        elif row.oriented_ci95_low > 0 and same_sign_high:
            grade = "strong_amplifying"
        elif row.oriented_mean > 0:
            grade = "amplifying_or_uncertain"
        else:
            grade = "undetermined"
        rows.append(
            {
                "metric": row.metric,
                "metric_label": row.metric_label,
                "oriented_mean": float(row.oriented_mean),
                "oriented_ci95": [
                    float(row.oriented_ci95_low),
                    float(row.oriented_ci95_high),
                ],
                "same_sign_fraction": float(row.same_sign_fraction),
                "grade": grade,
            }
        )
    return {
        "definition": (
            "Negative oriented IA_x_FEP means the IA background weakens the "
            "FEP-induced atmospheric connection. Strong evidence additionally "
            "requires a 95% interval below zero and >=0.8 same-sign members."
        ),
        "metrics": rows,
        "strong_suppressive_count": sum(r["grade"] == "strong_suppressive" for r in rows),
        "suggestive_or_strong_suppressive_count": sum(
            r["grade"] in {"strong_suppressive", "suggestive_suppressive"} for r in rows
        ),
    }


def write_markdown(oriented: pd.DataFrame, audit: dict[str, object], path: Path) -> None:
    view = oriented.loc[
        oriented["contrast"].isin(("FEP_at_IA0", "FEP_at_IA1", "IA_x_FEP"))
    ].copy()
    lines = [
        "# Isca P0 MJJ结果符号安全摘要",
        "",
        "物理方向已统一为正值表示更有利于热带太平洋大气接通；OLR使用负号后再判读。",
        "",
        "| 响应量 | 对比 | 有利方向均值 | 95% bootstrap | 同号成员 | 判读 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in view.itertuples(index=False):
        lines.append(
            f"| {row.metric_label} | {row.contrast} | {row.oriented_mean:+.4g} {row.unit} "
            f"| [{row.oriented_ci95_low:+.4g}, {row.oriented_ci95_high:+.4g}] "
            f"| {row.same_sign_fraction:.0%} | {row.physical_direction} |"
        )
    lines.extend(
        [
            "",
            "## IA×FEP抑制证据门槛",
            "",
            audit["definition"],
            "",
            f"- 强抑制指标数：{audit['strong_suppressive_count']}/6",
            "- 提示性或强抑制指标数："
            f"{audit['suggestive_or_strong_suppressive_count']}/6",
            "",
            "注：这些等级只是防止符号和不确定性被误读的审计标签，不替代对降水—气压—风应力完整链条的科学判断。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output = args.output or args.input
    output.mkdir(parents=True, exist_ok=True)
    oriented = orient(load_verified(args.input))
    audit = interaction_audit(oriented)
    oriented.to_csv(output / "p0_mjj_factorial_summary_oriented.csv", index=False)
    (output / "p0_scientific_interpretation.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(oriented, audit, output / "p0_scientific_interpretation.md")
    print(
        "P0_SCIENTIFIC_SUMMARY_COMPLETE "
        f"strong_suppressive={audit['strong_suppressive_count']}/6"
    )


if __name__ == "__main__":
    main()
