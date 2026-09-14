from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/Users/daiyue/Documents/Maryland")
DATA = ROOT / "data/derived/research_2026"
N_PERMUTATIONS = 20_000
N_BOOTSTRAP = 20_000
SEED = 20260811


def residualize(values: np.ndarray, controls: np.ndarray | None) -> np.ndarray:
    y = np.asarray(values, dtype=float)
    if controls is None:
        return y - y.mean()
    c = np.asarray(controls, dtype=float)
    if c.ndim == 1:
        c = c[:, None]
    design = np.column_stack([np.ones(len(y)), c])
    return y - design @ np.linalg.lstsq(design, y, rcond=None)[0]


def summarize(
    table: pd.DataFrame,
    label: str,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...],
    seed: int,
) -> dict[str, float | str]:
    x = table[x_name].to_numpy(float)
    y = table[y_name].to_numpy(float)
    c = table[list(controls)].to_numpy(float) if controls else None

    def fit(indices: np.ndarray) -> tuple[float, float, float]:
        ci = c[indices] if c is not None else None
        xr = residualize(x[indices], ci)
        yr = residualize(y[indices], ci)
        pearson = float(np.corrcoef(xr, yr)[0, 1])
        spearman = float(
            np.corrcoef(pd.Series(xr).rank(), pd.Series(yr).rank())[0, 1]
        )
        slope = float(
            np.linalg.lstsq(
                np.column_stack([np.ones(len(xr)), xr]), yr, rcond=None
            )[0][1]
        )
        return pearson, spearman, slope

    all_indices = np.arange(len(table))
    pearson, spearman, slope = fit(all_indices)
    rng = np.random.default_rng(seed)
    xr = residualize(x, c)
    yr = residualize(y, c)
    permutations = np.array(
        [np.corrcoef(xr, rng.permutation(yr))[0, 1] for _ in range(N_PERMUTATIONS)]
    )
    permutation_p = float(
        (np.sum(np.abs(permutations) >= abs(pearson)) + 1)
        / (N_PERMUTATIONS + 1)
    )
    bootstrap = []
    for _ in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(table), len(table))
        try:
            value = fit(sample)[0]
        except np.linalg.LinAlgError:
            value = np.nan
        bootstrap.append(value)
    bootstrap = np.asarray(bootstrap)
    bootstrap = bootstrap[np.isfinite(bootstrap)]
    ci_low, ci_high = np.percentile(bootstrap, [2.5, 97.5])

    loeo_r: list[float] = []
    loeo_slope: list[float] = []
    r_without: dict[int, float] = {}
    slope_without: dict[int, float] = {}
    years = table["event_year"].to_numpy(int)
    for index, year in enumerate(years):
        keep = all_indices[all_indices != index]
        r_i, _, b_i = fit(keep)
        loeo_r.append(r_i)
        loeo_slope.append(b_i)
        r_without[int(year)] = r_i
        slope_without[int(year)] = b_i

    return {
        "link": label,
        "pearson": pearson,
        "spearman": spearman,
        "permutation_p": permutation_p,
        "bootstrap_low": float(ci_low),
        "bootstrap_high": float(ci_high),
        "r_without_1997": r_without[1997],
        "r_without_2015": r_without[2015],
        "r_without_2023": r_without[2023],
        "loeo_r_min": float(np.min(loeo_r)),
        "loeo_r_max": float(np.max(loeo_r)),
        "slope_full": slope,
        "slope_without_1997": slope_without[1997],
        "slope_without_2015": slope_without[2015],
        "slope_without_2023": slope_without[2023],
        "loeo_slope_min": float(np.min(loeo_slope)),
        "loeo_slope_max": float(np.max(loeo_slope)),
    }


def main() -> None:
    early = pd.read_csv(DATA / "nonh20_early_north_to_jiang_event_table.csv").rename(
        columns={"year": "event_year"}
    )
    main_table = pd.read_csv(DATA / "nonh20_third_question_event_table.csv")
    specifications = [
        (
            early,
            "JFM north export -> MJJ NE925 | arrival",
            "north_output_jfm_zj",
            "ne925_mjj_ms",
            ("arrival_140w_jfm_zj",),
        ),
        (
            early,
            "MJJ NE850 -> central stress | JFM arrival",
            "ne850_mjj_z",
            "tau_response_mjj_z",
            ("arrival_140w_jfm_zj",),
        ),
        (
            main_table,
            "MJJ U850 -> following 5N stress",
            "u850_cwp_mj_ms",
            "decay_tau5n_westward_nm2",
            (),
        ),
        (
            main_table,
            "5N stress -> late north export | arrival",
            "decay_tau5n_westward_nm2",
            "decay_northward_output_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            main_table,
            "east SST -> surface loss | arrival",
            "decay_east_sst_anom_c",
            "decay_surface_loss_zj",
            ("arrival_140w_heat_in_zj",),
        ),
    ]
    rows = [
        summarize(table, label, x_name, y_name, controls, SEED + 101 * index)
        for index, (table, label, x_name, y_name, controls) in enumerate(
            specifications
        )
    ]
    output = pd.DataFrame(rows)
    print(output.to_csv(index=False, float_format="%.6f"))


if __name__ == "__main__":
    main()
