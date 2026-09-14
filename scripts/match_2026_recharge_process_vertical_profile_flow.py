#!/usr/bin/env python3
"""Match the 2026 equatorial-Pacific recharge process to historical El Nino events.

The matching deliberately keeps three pieces of evidence separate:

1. longitude-depth potential-temperature anomaly pattern;
2. west/central/east warm-water-volume (V20) evolution;
3. eastward warm-water-volume transport (M20) at 180E, 160W, and 140W.

The temperature profile identifies structural analogues.  Actual section
transport is then calculated from temperature and zonal velocity; it is not
inferred from temperature alone.  Each component receives equal weight in a
transparent rank aggregation, so the many profile grid cells do not dominate
the smaller storage and transport feature sets.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import pearsonr


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/compare_official_roni_vertical_profiles_and_flow_2026.py"
DATA_DIR = ROOT / "data/derived/research_2026/enso_vertical_flow_official_roni_2026"
OUT_DIR = ROOT / "outputs/research_2026/enso_recharge_event_matching_2026"
OUT_DATA = ROOT / "data/derived/research_2026/enso_recharge_event_matching_2026"


def load_base_module():
    spec = importlib.util.spec_from_file_location("vertical_flow_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base_module()
EVENT_YEARS = BASE.EVENTS["event_year"].astype(int).tolist()
EVENT_CLASS = BASE.EVENTS.set_index("event_year")["roni_class"].to_dict()
MONTHS = list(BASE.MONTHS)
SEASONS = {"JFM": [1, 2, 3], "AMJ": [4, 5, 6], "Jan-Jun": MONTHS}
REGIONS = ("west", "central", "east")
SECTIONS = tuple(BASE.SECTIONS)
SECTION_LABELS = BASE.SECTION_LABELS
MONTH_LABELS = BASE.MONTH_LABELS


def correlation_and_rmse(target: np.ndarray, reference: np.ndarray) -> tuple[float, float, float]:
    target = np.asarray(target, dtype=float).ravel()
    reference = np.asarray(reference, dtype=float).ravel()
    valid = np.isfinite(target) & np.isfinite(reference)
    if valid.sum() < 3:
        return np.nan, np.nan, np.nan
    target = target[valid]
    reference = reference[valid]
    correlation = float(pearsonr(target, reference).statistic)
    rmse = float(np.sqrt(np.mean((target - reference) ** 2)))
    rms_ratio = float(
        np.sqrt(np.mean(target**2)) / np.sqrt(np.mean(reference**2))
    )
    return correlation, rmse, rms_ratio


def build_event_profiles() -> tuple[xr.DataArray, xr.DataArray]:
    """Return historical event and 2026 monthly longitude-depth anomalies."""
    with BASE.open_dataset(BASE.SODA_TEMP) as dataset:
        latitude_mean = BASE.fixed_latitude_mean(dataset.temp, "depth")
    historical_anomaly = BASE.detrended_temperature_anomaly(latitude_mean)

    target_longitude = np.arange(121.0, 280.0, 1.0)
    target_depth = historical_anomaly.depth.where(
        historical_anomaly.depth < BASE.MAX_DEPTH, drop=True
    )
    historical_anomaly = historical_anomaly.sel(depth=target_depth).interp(
        lon=target_longitude
    )

    event_fields = []
    for year in EVENT_YEARS:
        selected = historical_anomaly.where(
            historical_anomaly.time.dt.year == year, drop=True
        )
        if selected.sizes["time"] != len(MONTHS):
            raise ValueError(f"Expected six months for {year}")
        selected = selected.assign_coords(time=MONTHS).rename(time="month")
        event_fields.append(selected.expand_dims(event_year=[year]))
    historical_events = xr.concat(event_fields, dim="event_year")

    monthly_groups, _, _ = BASE.build_vertical_profiles()
    target = monthly_groups.sel(category="2026", drop=True)
    return historical_events, target


def profile_metrics(events: xr.DataArray, target: xr.DataArray) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for year in EVENT_YEARS:
        reference = events.sel(event_year=year)
        row: dict[str, float | int] = {"year": year}
        for season, months in SEASONS.items():
            correlation, rmse, rms_ratio = correlation_and_rmse(
                target.sel(month=months).values,
                reference.sel(month=months).values,
            )
            row[f"{season}_profile_r"] = correlation
            row[f"{season}_profile_rmse_degC"] = rmse
            row[f"{season}_profile_rms_ratio_2026_to_event"] = rms_ratio
        rows.append(row)
    return pd.DataFrame(rows)


def harmonized_volume() -> tuple[pd.DataFrame, pd.DataFrame]:
    volume = pd.read_csv(DATA_DIR / "event_warm_water_volume.csv")
    validation = pd.read_csv(
        DATA_DIR / "soda3_godas_warm_volume_validation_summary.csv"
    ).set_index("region")
    historical = volume.loc[volume["year"].isin(EVENT_YEARS)].copy()
    target = volume.loc[volume["year"] == 2026].copy()
    for region in REGIONS:
        raw = f"v20_{region}_m3_anom"
        equivalent = f"v20_{region}_m3_anom_soda_equivalent"
        target[equivalent] = (
            validation.loc[region, "soda_on_godas_intercept_m3"]
            + validation.loc[region, "soda_on_godas_slope"] * target[raw]
        )
    return historical, target


def transport_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    historical = pd.read_csv(DATA_DIR / "historical_event_zonal_transport.csv")
    historical = historical.loc[historical["year"].isin(EVENT_YEARS)].copy()
    target = pd.read_csv(DATA_DIR / "2026_godas_zonal_transport.csv")
    return historical, target


def standardized_event_metrics(
    historical: pd.DataFrame,
    target: pd.DataFrame,
    value_pairs: list[tuple[str, str]],
    extra_dimensions: list[str],
    prefix: str,
) -> pd.DataFrame:
    """Calculate amplitude-sensitive standardized distance and pattern r.

    Each month-region or month-section feature is scaled by its inter-event
    standard deviation across the nine historical events.
    """
    rows: list[dict[str, float | int]] = []
    for year in EVENT_YEARS:
        row: dict[str, float | int] = {"year": year}
        for season, months in SEASONS.items():
            historical_stage = historical.loc[historical["month"].isin(months)]
            target_stage = target.loc[target["month"].isin(months)]
            target_vectors = []
            event_vectors = []
            scale_vectors = []
            for target_column, historical_column in value_pairs:
                columns = ["month"] + extra_dimensions
                historical_matrix = historical_stage.pivot(
                    index="year", columns=columns, values=historical_column
                ).sort_index(axis=1)
                target_matrix = target_stage.pivot_table(
                    index="year", columns=columns, values=target_column
                ).reindex(columns=historical_matrix.columns)
                target_vectors.append(target_matrix.iloc[0].to_numpy(dtype=float))
                event_vectors.append(
                    historical_matrix.loc[year].to_numpy(dtype=float)
                )
                scale_vectors.append(
                    historical_matrix.std(axis=0, ddof=1).to_numpy(dtype=float)
                )

            target_values = np.concatenate(target_vectors)
            event_values = np.concatenate(event_vectors)
            scales = np.concatenate(scale_vectors)
            valid = (
                np.isfinite(target_values)
                & np.isfinite(event_values)
                & np.isfinite(scales)
                & (scales > 1.0e-12)
            )
            row[f"{season}_{prefix}_standardized_distance"] = float(
                np.sqrt(
                    np.mean(
                        ((target_values[valid] - event_values[valid]) / scales[valid])
                        ** 2
                    )
                )
            )
            row[f"{season}_{prefix}_pattern_r"] = float(
                pearsonr(target_values[valid], event_values[valid]).statistic
            )
        rows.append(row)
    return pd.DataFrame(rows)


def build_matching_table(
    profile: pd.DataFrame,
    historical_volume: pd.DataFrame,
    target_volume: pd.DataFrame,
    historical_transport: pd.DataFrame,
    target_transport: pd.DataFrame,
) -> pd.DataFrame:
    volume_pairs = [
        (
            f"v20_{region}_m3_anom_soda_equivalent",
            f"v20_{region}_m3_anom",
        )
        for region in REGIONS
    ]
    volume_metrics = standardized_event_metrics(
        historical_volume,
        target_volume,
        volume_pairs,
        [],
        "storage",
    )
    transport_metrics = standardized_event_metrics(
        historical_transport,
        target_transport,
        [
            (
                "warm_volume_transport_sv_anom_soda_equivalent",
                "warm_volume_transport_sv_anom",
            )
        ],
        ["longitude_e"],
        "M20",
    )
    heat_metrics = standardized_event_metrics(
        historical_transport,
        target_transport,
        [("q20_pw_anom_soda_equivalent", "q20_pw_anom")],
        ["longitude_e"],
        "Q20",
    )

    result = (
        profile.merge(volume_metrics, on="year")
        .merge(transport_metrics, on="year")
        .merge(heat_metrics, on="year")
    )
    result["roni_class"] = result["year"].map(EVENT_CLASS)
    n_events = len(result)
    for season in SEASONS:
        result[f"{season}_profile_rank"] = result[
            f"{season}_profile_r"
        ].rank(ascending=False, method="average")
        result[f"{season}_storage_distance_rank"] = result[
            f"{season}_storage_standardized_distance"
        ].rank(ascending=True, method="average")
        result[f"{season}_storage_pattern_rank"] = result[
            f"{season}_storage_pattern_r"
        ].rank(ascending=False, method="average")
        result[f"{season}_storage_rank"] = result[
            [
                f"{season}_storage_distance_rank",
                f"{season}_storage_pattern_rank",
            ]
        ].mean(axis=1)
        result[f"{season}_M20_distance_rank"] = result[
            f"{season}_M20_standardized_distance"
        ].rank(ascending=True, method="average")
        result[f"{season}_M20_pattern_rank"] = result[
            f"{season}_M20_pattern_r"
        ].rank(ascending=False, method="average")
        result[f"{season}_M20_rank"] = result[
            [f"{season}_M20_distance_rank", f"{season}_M20_pattern_rank"]
        ].mean(axis=1)
        result[f"{season}_mean_rank"] = result[
            [
                f"{season}_profile_rank",
                f"{season}_storage_rank",
                f"{season}_M20_rank",
            ]
        ].mean(axis=1)
        result[f"{season}_combined_similarity"] = 1.0 - (
            result[f"{season}_mean_rank"] - 1.0
        ) / (n_events - 1.0)
    return result.sort_values("Jan-Jun_mean_rank").reset_index(drop=True)


def seasonal_mean(field: xr.DataArray, months: list[int]) -> xr.DataArray:
    return field.sel(month=months).mean("month")


def plot_profile_analogues(
    events: xr.DataArray,
    target: xr.DataArray,
    matching: pd.DataFrame,
) -> None:
    BASE.setup_style()
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    best_jfm_profile = int(
        matching.sort_values("JFM_profile_rank").iloc[0]["year"]
    )
    best_amj_process = int(matching.sort_values("AMJ_mean_rank").iloc[0]["year"])
    selections = [
        ("JFM", [1, 2, 3], best_jfm_profile),
        ("AMJ", [4, 5, 6], best_amj_process),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12.4, 6.3), sharex=True, sharey=True)
    norm = TwoSlopeNorm(vmin=-3.0, vcenter=0.0, vmax=3.0)
    mesh = None
    panel = 0
    for row, (season, months, analogue_year) in enumerate(selections):
        target_field = seasonal_mean(target, months)
        analogue_field = seasonal_mean(events.sel(event_year=analogue_year), months)
        fields = (
            (target_field, f"2026 {season}"),
            (analogue_field, f"{analogue_year} {season}"),
            (target_field - analogue_field, f"2026 minus {analogue_year}"),
        )
        for column, (field, title) in enumerate(fields):
            ax = axes[row, column]
            mesh = ax.pcolormesh(
                field.lon,
                field.depth,
                field,
                cmap="RdBu_r",
                norm=norm,
                shading="auto",
            )
            ax.contour(
                field.lon,
                field.depth,
                field,
                levels=[-1.0, 0.0, 1.0],
                colors=["#2166ac", "0.35", "#b2182b"],
                linewidths=[0.55, 0.45, 0.55],
            )
            ax.axvline(180.0, color="0.3", ls="--", lw=0.55)
            ax.axvline(200.0, color="0.3", ls="--", lw=0.55)
            ax.axvline(220.0, color="0.3", ls="--", lw=0.55)
            ax.set_ylim(BASE.MAX_DEPTH, 0.0)
            ax.set_title(f"({chr(97 + panel)}) {title}", loc="left")
            panel += 1
    for ax in axes[:, 0]:
        ax.set_ylabel("Depth (m)")
    for ax in axes[-1, :]:
        ax.set_xlabel("Longitude")
    for ax in axes.ravel():
        ax.set_xticks([140.0, 180.0, 220.0, 260.0])
        ax.set_xticklabels(["140°E", "180°", "140°W", "100°W"])
    colorbar = fig.colorbar(
        mesh,
        ax=axes,
        orientation="horizontal",
        fraction=0.06,
        pad=0.13,
        aspect=45,
    )
    colorbar.set_label("Potential-temperature anomaly (°C)")
    fig.subplots_adjust(left=0.065, right=0.99, top=0.96, bottom=0.18, wspace=0.08, hspace=0.18)
    fig.savefig(OUT_DIR / "2026_closest_analogue_vertical_profiles.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "2026_closest_analogue_vertical_profiles.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_matching_matrix(matching: pd.DataFrame) -> None:
    BASE.setup_style()
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 6.4))
    for ax, season, panel in zip(axes, ("JFM", "AMJ"), ("a", "b")):
        current = matching.sort_values(f"{season}_mean_rank").reset_index(drop=True)
        raw_columns = [
            f"{season}_profile_r",
            f"{season}_storage_standardized_distance",
            f"{season}_M20_standardized_distance",
            f"{season}_combined_similarity",
        ]
        rank_columns = [
            f"{season}_profile_rank",
            f"{season}_storage_rank",
            f"{season}_M20_rank",
        ]
        scores = []
        for column in rank_columns:
            scores.append(1.0 - (current[column].to_numpy() - 1.0) / (len(current) - 1.0))
        scores.append(current[f"{season}_combined_similarity"].to_numpy())
        score_matrix = np.column_stack(scores)
        image = ax.imshow(score_matrix, cmap="YlGnBu", norm=Normalize(0.0, 1.0), aspect="auto")
        for row in range(len(current)):
            values = [
                f"r={current.loc[row, raw_columns[0]]:.2f}",
                f"r={current.loc[row, f'{season}_storage_pattern_r']:.2f}\nd={current.loc[row, raw_columns[1]]:.2f}",
                f"r={current.loc[row, f'{season}_M20_pattern_r']:.2f}\nd={current.loc[row, raw_columns[2]]:.2f}",
                f"{current.loc[row, raw_columns[3]]:.2f}",
            ]
            for column, value in enumerate(values):
                color = "white" if score_matrix[row, column] > 0.62 else "black"
                ax.text(column, row, value, ha="center", va="center", fontsize=7.6, color=color)
        labels = [
            f"{int(row.year)}  ({str(row.roni_class).replace('_', ' ')})"
            for row in current.itertuples()
        ]
        ax.set_yticks(np.arange(len(current)), labels=labels)
        ax.set_xticks(
            np.arange(4),
            labels=["Vertical-profile\npattern", "V20 storage\nevolution", "M20 section\ntransport", "Combined\nsimilarity"],
        )
        ax.tick_params(axis="x", labelrotation=0)
        ax.set_title(f"({panel}) {season} event matching", loc="left")
        ax.set_xticks(np.arange(-0.5, 4, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(current), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.2)
        ax.tick_params(which="minor", bottom=False, left=False)
    colorbar = fig.colorbar(image, ax=axes, orientation="horizontal", fraction=0.055, pad=0.13, aspect=45)
    colorbar.set_label("Rank-based similarity (1 = closest; colors are comparable within each stage)")
    fig.subplots_adjust(left=0.15, right=0.99, top=0.94, bottom=0.2, wspace=0.34)
    fig.savefig(OUT_DIR / "2026_recharge_event_matching_matrix.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "2026_recharge_event_matching_matrix.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_event_processes(
    historical_volume: pd.DataFrame,
    target_volume: pd.DataFrame,
    historical_transport: pd.DataFrame,
    target_transport: pd.DataFrame,
    matching: pd.DataFrame,
) -> None:
    BASE.setup_style()
    import matplotlib.pyplot as plt

    # Retain the three full-period analogues plus the best early-profile analogue.
    selected = matching.nsmallest(3, "Jan-Jun_mean_rank")["year"].astype(int).tolist()
    early = int(matching.nsmallest(1, "JFM_profile_rank").iloc[0]["year"])
    if early not in selected:
        selected.append(early)
    colors = {
        selected[0]: "#b2182b",
        selected[1]: "#2166ac",
        selected[2]: "#ef8a0c",
        selected[3] if len(selected) > 3 else -1: "#1b9e77",
    }
    fig, axes = plt.subplots(2, 3, figsize=(12.4, 6.5), sharex=True)

    for column, longitude in enumerate(SECTIONS):
        ax = axes[0, column]
        for year in selected:
            current = historical_transport.loc[
                (historical_transport["year"] == year)
                & (historical_transport["longitude_e"] == longitude)
            ].sort_values("month")
            ax.plot(
                current["month"],
                current["warm_volume_transport_sv_anom"],
                color=colors[year],
                lw=1.25,
                marker="o",
                ms=2.5,
                label=str(year),
            )
        current = target_transport.loc[
            target_transport["longitude_e"] == longitude
        ].sort_values("month")
        ax.plot(
            current["month"],
            current["warm_volume_transport_sv_anom_soda_equivalent"],
            color="black",
            lw=2.3,
            marker="o",
            ms=3.6,
            label="2026",
        )
        ax.axhline(0.0, color="0.45", lw=0.65)
        ax.set_title(f"({chr(97 + column)}) M20 at {SECTION_LABELS[longitude]}", loc="left")
        if column == 0:
            ax.set_ylabel("Warm-water transport anomaly (Sv)")

    for column, region in enumerate(REGIONS):
        ax = axes[1, column]
        for year in selected:
            current = historical_volume.loc[historical_volume["year"] == year].sort_values("month")
            ax.plot(
                current["month"],
                current[f"v20_{region}_m3_anom"] / 1.0e13,
                color=colors[year],
                lw=1.25,
                marker="o",
                ms=2.5,
            )
        current = target_volume.sort_values("month")
        ax.plot(
            current["month"],
            current[f"v20_{region}_m3_anom_soda_equivalent"] / 1.0e13,
            color="black",
            lw=2.3,
            marker="o",
            ms=3.6,
        )
        ax.axhline(0.0, color="0.45", lw=0.65)
        ax.set_title(f"({chr(100 + column)}) {region.capitalize()} V20", loc="left")
        ax.set_xlabel("Development month")
        if column == 0:
            ax.set_ylabel("Warm-water-volume anomaly ($10^{13}$ m$^3$)")

    for ax in axes.ravel():
        ax.set_xticks(MONTHS, MONTH_LABELS)
        ax.grid(axis="y", color="0.88", lw=0.55)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False, bbox_to_anchor=(0.52, 1.01))
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.94))
    fig.savefig(OUT_DIR / "2026_recharge_analogue_flow_and_storage.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "2026_recharge_analogue_flow_and_storage.pdf", bbox_inches="tight")
    plt.close(fig)


def write_summary(matching: pd.DataFrame) -> None:
    jfm = matching.sort_values("JFM_mean_rank")
    amj = matching.sort_values("AMJ_mean_rank")
    full = matching.sort_values("Jan-Jun_mean_rank")
    best_jfm_profile = matching.sort_values("JFM_profile_rank").iloc[0]
    best_jfm_storage = matching.sort_values("JFM_storage_rank").iloc[0]
    best_jfm_flow_distance = matching.sort_values("JFM_M20_standardized_distance").iloc[0]
    best_jfm_flow_pattern = matching.sort_values("JFM_M20_pattern_r", ascending=False).iloc[0]
    best_amj = amj.iloc[0]
    best_full = full.iloc[0]
    lines = [
        "# 2026年充电过程的逐事件匹配",
        "",
        "## 方法",
        "",
        "历史事件使用SODA3；2026使用GODAS，并通过重叠事件回归换算为SODA等效V20和M20幅度。匹配包含三个等权分量：经度—深度温度异常型态、三分区V20演变、三个经度断面M20演变。V20与M20分量同时评价逐月型态相关和幅度标准化距离；Q20仅作为敏感性检验，不进入主排序。",
        "",
        "## JFM",
        "",
        f"垂向型态最接近{int(best_jfm_profile.year)}（r={best_jfm_profile['JFM_profile_r']:.3f}）；V20配置最接近{int(best_jfm_storage.year)}。M20没有唯一类比：{int(best_jfm_flow_distance.year)}的标准化幅度距离最小，而{int(best_jfm_flow_pattern.year)}的逐月—逐断面型态相关最高。综合排序前3为："
        + "、".join(str(int(year)) for year in jfm.head(3)["year"])
        + "。这说明早期没有唯一历史类比。",
        "",
        "## AMJ",
        "",
        f"{int(best_amj.year)}为最稳定类比：垂向型态r={best_amj['AMJ_profile_r']:.3f}，V20演变r={best_amj['AMJ_storage_pattern_r']:.3f}，M20演变r={best_amj['AMJ_M20_pattern_r']:.3f}。",
        "",
        "## 1—6月综合",
        "",
        f"最接近事件为{int(best_full.year)}（{str(best_full.roni_class).replace('_', ' ')}）：垂向型态r={best_full['Jan-Jun_profile_r']:.3f}，V20演变r={best_full['Jan-Jun_storage_pattern_r']:.3f}，M20演变r={best_full['Jan-Jun_M20_pattern_r']:.3f}。",
        "",
        "该结论表示2026由早期混合型结构转入与1997相似的快速东向再分配过程；它不表示2026最终ENSO强度必然达到1997水平。",
    ]
    (OUT_DIR / "RECHARGE_EVENT_MATCHING_2026_CN.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DATA.mkdir(parents=True, exist_ok=True)

    event_profiles, target_profile = build_event_profiles()
    profile = profile_metrics(event_profiles, target_profile)
    historical_volume, target_volume = harmonized_volume()
    historical_transport, target_transport = transport_tables()
    matching = build_matching_table(
        profile,
        historical_volume,
        target_volume,
        historical_transport,
        target_transport,
    )

    matching.to_csv(OUT_DATA / "2026_recharge_event_matching_metrics.csv", index=False)
    event_profiles.astype(np.float32).to_dataset(name="temperature_anomaly").to_netcdf(
        OUT_DATA / "historical_event_monthly_vertical_profiles.nc", engine="h5netcdf"
    )
    target_profile.astype(np.float32).to_dataset(name="temperature_anomaly").to_netcdf(
        OUT_DATA / "2026_monthly_vertical_profile.nc", engine="h5netcdf"
    )
    target_volume.to_csv(OUT_DATA / "2026_soda_equivalent_warm_water_volume.csv", index=False)

    plot_profile_analogues(event_profiles, target_profile, matching)
    plot_matching_matrix(matching)
    plot_event_processes(
        historical_volume,
        target_volume,
        historical_transport,
        target_transport,
        matching,
    )
    write_summary(matching)


if __name__ == "__main__":
    main()
