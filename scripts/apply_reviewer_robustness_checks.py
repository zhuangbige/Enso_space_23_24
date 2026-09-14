"""Targeted robustness checks requested in the 14-page manuscript review.

The script deliberately avoids adding another fitted gate index.  It tests the
two claims that can be evaluated without new model integrations:

1. stability of the rain-dipole/atmospheric-response relationship after every
   possible pair of warm events is removed; and
2. whether the May-June coupling update beats spring type persistence and a
   spring Nino3.4-only benchmark, in addition to calibrated NMME.

All inputs are existing project-derived CSV files.  Outputs are deterministic
CSV/JSON diagnostics and one manuscript-ready robustness figure.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/paper_cn"

EVENTS = DERIVED / "enso_perturbation_event_indices_1982_2023.csv"
NMME = DERIVED / "nmme_enso_type_hindcast_indices_1991_2020.csv"
MONTHLY = DERIVED / "enso_full_year_coupling_monthly_1982_2024.csv"
UPDATE_PRED = DERIVED / "nmme_son_coupling_update_predictions.csv"

L2O_CSV = DERIVED / "reviewer_leave_two_events_out.csv"
BASELINE_CSV = DERIVED / "reviewer_nmme_baseline_comparison.csv"
SUMMARY_JSON = DERIVED / "reviewer_robustness_diagnostics.json"
FIGURE = OUT / "fig11_reviewer_robustness"

CONTROLS = (
    "east_ocean_state_z_z",
    "early_ec_apr_z",
    "fep_residual_mjj_z",
)
RESPONSES = {
    "coupling_mjj_z": "Composite coupling",
    "precip_response_mjj_z": "Rainfall branch",
    "slp_response_mjj_z": "SLP branch",
    "tau_response_mjj_z": "Wind-stress branch",
}
VALIDATIONS = ("leave-one-year-out", "expanding-window")
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260731


def partial_r(frame: pd.DataFrame, predictor: str, response: str) -> float:
    required = [predictor, response, *CONTROLS]
    data = frame.dropna(subset=required)
    design = np.column_stack(
        [np.ones(len(data)), *[data[name].to_numpy(float) for name in CONTROLS]]
    )
    x = data[predictor].to_numpy(float)
    y = data[response].to_numpy(float)
    x -= design @ np.linalg.lstsq(design, x, rcond=None)[0]
    y -= design @ np.linalg.lstsq(design, y, rcond=None)[0]
    return float(np.corrcoef(x, y)[0, 1])


def leave_two_out_table(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for response, label in RESPONSES.items():
        full = partial_r(events, "precip_dipole_mjj_z", response)
        for first, second in combinations(events["year"].astype(int), 2):
            reduced = events.loc[~events["year"].isin([first, second])]
            rows.append(
                {
                    "response": response,
                    "response_label": label,
                    "removed_event_1": first,
                    "removed_event_2": second,
                    "n_events": len(reduced),
                    "full_sample_partial_r": full,
                    "leave_two_out_partial_r": partial_r(
                        reduced,
                        "precip_dipole_mjj_z",
                        response,
                    ),
                }
            )
    return pd.DataFrame(rows)


def linear_residual(
    train_years: np.ndarray,
    train_values: np.ndarray,
    test_year: float,
    test_value: float,
) -> tuple[np.ndarray, float]:
    design = np.column_stack([np.ones(len(train_years)), train_years])
    coefficients = np.linalg.lstsq(design, train_values, rcond=None)[0]
    return (
        train_values - design @ coefficients,
        float(test_value - np.asarray([1.0, test_year]) @ coefficients),
    )


def ridge_one_feature(
    train: pd.DataFrame,
    test: pd.Series,
    feature: str,
) -> tuple[float, float]:
    years = train["year"].to_numpy(float)
    target, observed = linear_residual(
        years,
        train["target_son_type_raw"].to_numpy(float),
        float(test["year"]),
        float(test["target_son_type_raw"]),
    )
    predictor, test_predictor = linear_residual(
        years,
        train[feature].to_numpy(float),
        float(test["year"]),
        float(test[feature]),
    )
    scale = float(predictor.std(ddof=1))
    predictor /= scale
    test_predictor /= scale
    coefficient = float(
        (predictor @ target) / (predictor @ predictor + 1.0)
    )
    return test_predictor * coefficient, observed


def build_annual_table() -> pd.DataFrame:
    nmme = pd.read_csv(NMME)
    selected = nmme.loc[
        nmme["model"].eq("nmme")
        & nmme["target_season"].eq("SON")
        & nmme["init_month"].isin([3, 4])
    ].copy()
    selected["target_son_type_raw"] = (
        selected["observed_nino3_raw_c"] - selected["observed_nino4_raw_c"]
    )
    annual = (
        selected.groupby("event_year", as_index=False)
        .agg(target_son_type_raw=("target_son_type_raw", "mean"))
        .rename(columns={"event_year": "year"})
    )
    monthly = pd.read_csv(MONTHLY)
    spring = (
        monthly.loc[monthly["month"].isin([3, 4])]
        .groupby("year", as_index=False)
        .agg(
            spring_type_raw=("sst_type_raw_c", "mean"),
            spring_nino34_raw=("nino34_raw_c", "mean"),
        )
    )
    return annual.merge(spring, on="year", validate="one_to_one")


def baseline_predictions() -> pd.DataFrame:
    annual = build_annual_table()
    existing = pd.read_csv(UPDATE_PRED)
    rows: list[dict[str, object]] = []
    for validation in VALIDATIONS:
        for year in annual["year"].astype(int):
            if validation == "leave-one-year-out":
                train = annual.loc[annual["year"].ne(year)]
            else:
                train = annual.loc[annual["year"].lt(year)]
            if len(train) < 12:
                continue
            test = annual.loc[annual["year"].eq(year)].iloc[0]
            years = train["year"].to_numpy(float)
            _, observed = linear_residual(
                years,
                train["target_son_type_raw"].to_numpy(float),
                float(year),
                float(test["target_son_type_raw"]),
            )
            _, persistence = linear_residual(
                years,
                train["spring_type_raw"].to_numpy(float),
                float(year),
                float(test["spring_type_raw"]),
            )
            nino34, _ = ridge_one_feature(train, test, "spring_nino34_raw")
            rows.extend(
                [
                    {
                        "validation": validation,
                        "year": year,
                        "model": "Spring type persistence",
                        "prediction": persistence,
                        "observed": observed,
                    },
                    {
                        "validation": validation,
                        "year": year,
                        "model": "Spring Nino3.4 only",
                        "prediction": nino34,
                        "observed": observed,
                    },
                ]
            )
    additions = pd.DataFrame(rows)
    retained = existing.loc[
        existing["model"].isin(["NMME", "NMME + May-Jun coupling"]),
        ["validation", "year", "model", "prediction", "observed"],
    ]
    return pd.concat([additions, retained], ignore_index=True)


def rmse_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, object]] = []
    for (validation, model), current in predictions.groupby(
        ["validation", "model"], sort=False
    ):
        current = current.dropna(subset=["prediction", "observed"])
        errors = (
            current["prediction"].to_numpy(float)
            - current["observed"].to_numpy(float)
        )
        rmse = float(np.sqrt(np.mean(errors**2)))
        samples = rng.integers(0, len(errors), (BOOTSTRAP_SAMPLES, len(errors)))
        boot = np.sqrt(np.mean(errors[samples] ** 2, axis=1))
        low, high = np.percentile(boot, [2.5, 97.5])
        rows.append(
            {
                "validation": validation,
                "model": model,
                "n_test": len(errors),
                "rmse": rmse,
                "rmse_ci_low": float(low),
                "rmse_ci_high": float(high),
                "prediction_observation_r": float(
                    np.corrcoef(
                        current["prediction"].to_numpy(float),
                        current["observed"].to_numpy(float),
                    )[0, 1]
                ),
            }
        )
    output = pd.DataFrame(rows)
    for validation, indices in output.groupby("validation").groups.items():
        update = float(
            output.loc[
                (output["validation"].eq(validation))
                & (output["model"].eq("NMME + May-Jun coupling")),
                "rmse",
            ].iloc[0]
        )
        output.loc[indices, "update_skill_relative_to_model"] = (
            1.0 - update / output.loc[indices, "rmse"]
        )
    return output


def make_figure(l2o: pd.DataFrame, baseline: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 160,
            "savefig.dpi": 300,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), constrained_layout=True)

    order = list(RESPONSES.values())
    values = [
        l2o.loc[l2o["response_label"].eq(label), "leave_two_out_partial_r"]
        .to_numpy(float)
        for label in order
    ]
    colors = ["#355F8A", "#2A9D8F", "#E9A03B", "#D05A4A"]
    bp = axes[0].boxplot(
        values,
        tick_labels=["Composite", "Rainfall", "SLP", "Wind stress"],
        patch_artist=True,
        widths=0.58,
        showfliers=False,
        medianprops={"color": "white", "linewidth": 1.5},
        whiskerprops={"color": "#555555"},
        capprops={"color": "#555555"},
    )
    for patch, color in zip(bp["boxes"], colors, strict=True):
        patch.set_facecolor(color)
        patch.set_alpha(0.86)
    rng = np.random.default_rng(RANDOM_SEED)
    for index, current in enumerate(values, 1):
        jitter = rng.normal(index, 0.045, len(current))
        axes[0].scatter(jitter, current, s=9, color="#202020", alpha=0.20, linewidth=0)
    axes[0].axhline(0, color="#777777", linewidth=0.8)
    axes[0].axhline(0.5, color="#777777", linewidth=0.8, linestyle="--")
    axes[0].set_ylim(-0.35, 1.0)
    axes[0].set_ylabel("Partial correlation after removing two events")
    axes[0].set_title("a  Rain-dipole link: all 78 leave-two-out samples", loc="left", fontweight="bold")
    axes[0].grid(axis="y", color="#E5E5E5", linewidth=0.7)

    current = baseline.loc[baseline["validation"].eq("expanding-window")].copy()
    model_order = [
        "Spring type persistence",
        "Spring Nino3.4 only",
        "NMME",
        "NMME + May-Jun coupling",
    ]
    current["model"] = pd.Categorical(current["model"], model_order, ordered=True)
    current = current.sort_values("model")
    x = np.arange(len(current))
    y = current["rmse"].to_numpy(float)
    yerr = np.vstack(
        [
            y - current["rmse_ci_low"].to_numpy(float),
            current["rmse_ci_high"].to_numpy(float) - y,
        ]
    )
    bar_colors = ["#A7A9AC", "#7B8DA6", "#355F8A", "#D05A4A"]
    axes[1].bar(x, y, color=bar_colors, width=0.67, edgecolor="white", linewidth=0.8)
    axes[1].errorbar(x, y, yerr=yerr, fmt="none", ecolor="#303030", capsize=3, linewidth=1)
    axes[1].set_xticks(x, ["Spring type\npersistence", "Spring Niño3.4\nonly", "Calibrated\nNMME", "NMME +\nMay–Jun coupling"], rotation=0)
    axes[1].set_ylabel("SON type RMSE (°C)")
    axes[1].set_title("b  Chronological forecast-update comparison", loc="left", fontweight="bold")
    axes[1].grid(axis="y", color="#E5E5E5", linewidth=0.7)
    axes[1].set_axisbelow(True)
    for xpos, value in zip(x, y, strict=True):
        axes[1].text(xpos, value + 0.035, f"{value:.2f}", ha="center", va="bottom", fontsize=8.5)

    fig.suptitle(
        "Robustness of the atmospheric branch and the late-spring forecast update",
        fontsize=12,
        fontweight="bold",
    )
    fig.text(
        0.01,
        -0.025,
        "Event sample: 13 warm events (1982–2023). Forecast panel: 18 chronological targets (1991–2020); error bars are year-bootstrap 95% intervals.",
        fontsize=7.5,
        color="#555555",
    )
    fig.savefig(FIGURE.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(FIGURE.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(EVENTS)
    l2o = leave_two_out_table(events)
    l2o.to_csv(L2O_CSV, index=False)

    predictions = baseline_predictions()
    baseline = rmse_summary(predictions)
    baseline.to_csv(BASELINE_CSV, index=False)

    composite = l2o.loc[l2o["response"].eq("coupling_mjj_z")]
    update = baseline.loc[
        (baseline["validation"].eq("expanding-window"))
        & (baseline["model"].eq("NMME + May-Jun coupling"))
    ].iloc[0]
    diagnostic = {
        "leave_two_out": {
            "pairs": int(len(composite)),
            "minimum_partial_r": float(composite["leave_two_out_partial_r"].min()),
            "fifth_percentile": float(composite["leave_two_out_partial_r"].quantile(0.05)),
            "median": float(composite["leave_two_out_partial_r"].median()),
            "fraction_positive": float((composite["leave_two_out_partial_r"] > 0).mean()),
            "fraction_above_0p5": float((composite["leave_two_out_partial_r"] > 0.5).mean()),
            "lowest_pairs": composite.nsmallest(4, "leave_two_out_partial_r")[[
                "removed_event_1", "removed_event_2", "leave_two_out_partial_r"
            ]].to_dict("records"),
        },
        "expanding_window": {
            "n_test": int(update["n_test"]),
            "models": baseline.loc[
                baseline["validation"].eq("expanding-window"),
                ["model", "rmse", "prediction_observation_r", "update_skill_relative_to_model"],
            ].to_dict("records"),
        },
        "interpretation": (
            "The rain-dipole link is sign-stable but not uniformly above 0.5; "
            "the weakest deletion removes 1997 and 2015. The forecast update "
            "beats persistence and Nino3.4-only, but remains a May-June "
            "observational update rather than a pure March forecast."
        ),
    }
    SUMMARY_JSON.write_text(
        json.dumps(diagnostic, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    make_figure(l2o, baseline)
    print(L2O_CSV)
    print(BASELINE_CSV)
    print(SUMMARY_JSON)
    print(FIGURE.with_suffix(".png"))


if __name__ == "__main__":
    main()
