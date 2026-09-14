#!/usr/bin/env python3
"""Plot SODA3 cumulative ocean-heat-content anomaly sections.

The shaded quantity is not temperature anomaly.  At every longitude and
displayed depth z it is the heat-content anomaly accumulated from the sea
surface to z:

    Q'(x, z) = rho0 * Cp0 * integral_0^z T'(x, zeta) d zeta.

This preserves a depth coordinate without imposing arbitrary depth bins.  The
value at 300 m is therefore exactly the conventional 0--300 m OHC anomaly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
import numpy as np
import xarray as xr

import plot_soda3_peng2025_profile_comparison as base


OUT_DIR = base.ROOT / "outputs/research_2026/soda3_cumulative_ohca_profiles"
DEFAULT_VLIM = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=base.TEMP_FILE)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--vlim",
        type=float,
        default=DEFAULT_VLIM,
        help="Symmetric cumulative-OHCA colour limit in GJ m-2.",
    )
    return parser.parse_args()


def open_dataset(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(path)
    for engine in ("h5netcdf", "netcdf4", "scipy"):
        try:
            return xr.open_dataset(path, engine=engine)
        except (OSError, ImportError, ValueError, TypeError):
            continue
    raise OSError(f"No available xarray backend could open {path}")


def cumulative_ohca(temperature_anomaly: xr.DataArray) -> xr.DataArray:
    """Return surface-to-depth cumulative OHCA in GJ m-2."""
    dz = base.depth_cell_thickness(temperature_anomaly.depth)
    layer_ohca = temperature_anomaly * dz * base.RHO0 * base.CP0 / 1.0e9
    cumulative = layer_ohca.cumsum("depth", skipna=False)

    lower_edges = np.cumsum(dz.values.astype(float))
    cumulative = cumulative.assign_coords(depth=lower_edges)
    surface = xr.zeros_like(cumulative.isel(depth=0, drop=True)).expand_dims(depth=[0.0])
    result = xr.concat((surface, cumulative), dim="depth")
    result = result.transpose(*temperature_anomaly.dims)
    result.name = "cumulative_ohca"
    result.attrs.update(
        units="GJ m-2",
        long_name="surface-to-depth cumulative ocean-heat-content anomaly",
        definition="rho0*Cp0*integral(surface,z) temperature_anomaly dz",
        rho0_kg_m3=base.RHO0,
        cp0_J_kg_K=base.CP0,
    )
    return result


def draw_section(
    ax: plt.Axes,
    field: xr.DataArray,
    *,
    norm: TwoSlopeNorm,
    actual_temperature: xr.DataArray | None,
    climatological_temperature: xr.DataArray | None,
) -> plt.collections.QuadMesh:
    mesh = ax.pcolormesh(
        field.lon,
        field.depth,
        field,
        cmap="RdBu_r",
        norm=norm,
        shading="auto",
        rasterized=True,
        zorder=1,
    )
    ax.axvspan(
        base.FEP_BOUNDS[0],
        base.FEP_BOUNDS[1],
        facecolor="none",
        edgecolor="0.20",
        linewidth=0.75,
        linestyle=(0, (2, 2)),
        zorder=4,
    )
    if actual_temperature is not None and climatological_temperature is not None:
        actual = ax.contour(
            actual_temperature.lon,
            actual_temperature.depth,
            actual_temperature,
            levels=[20.0],
            colors=["k"],
            linewidths=1.25,
            zorder=5,
        )
        actual.set_path_effects(
            [path_effects.Stroke(linewidth=2.0, foreground="white"), path_effects.Normal()]
        )
        # Draw the climatological curve last so that its dashes remain visible
        # even when it closely follows the actual 20 degC isotherm.
        climatological = ax.contour(
            climatological_temperature.lon,
            climatological_temperature.depth,
            climatological_temperature,
            levels=[20.0],
            colors=["0.42"],
            linewidths=1.20,
            linestyles="--",
            zorder=6,
        )
        climatological.set_path_effects(
            [path_effects.Stroke(linewidth=2.2, foreground="white"), path_effects.Normal()]
        )
    return mesh


def add_isotherm_legend(fig: plt.Figure, *, x: float, y: float) -> None:
    handles = (
        Line2D([0], [0], color="k", linewidth=1.25, label="Actual 20°C isotherm"),
        Line2D(
            [0],
            [0],
            color="0.42",
            linewidth=1.20,
            linestyle="--",
            label="1982–2022 climatological 20°C isotherm",
        ),
    )
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(x, y),
        ncol=2,
        frameon=False,
        fontsize=8.0,
        handlelength=2.6,
        columnspacing=1.8,
    )


def format_axis(ax: plt.Axes, *, show_xlabel: bool, show_ylabel: bool) -> None:
    base.format_axis(ax, show_xlabel=show_xlabel, show_ylabel=show_ylabel)


def figure_note() -> str:
    return (
        "2°S–2°N cosine-weighted SODA3.15.2; Q′(x,z)=ρ₀Cₚ∫₀ᶻT′dz, referenced to "
        "the 1982–2022 calendar-month climatology (no detrending). Units: GJ m⁻²; "
        "the value at 300 m equals 0–300 m OHCA. Black: actual 20°C isotherm; grey "
        "dashed: climatological 20°C isotherm; outlined strip: FEP (90°W–80°W)."
    )


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    return base.save_figure(fig, output_dir, stem)


def plot_three_stage(
    temperature: xr.DataArray,
    ohca: xr.DataArray,
    climatology: xr.DataArray,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(3, 3, figsize=(12.8, 8.7), sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.078,
        right=0.985,
        top=0.86,
        bottom=0.15,
        wspace=0.07,
        hspace=0.12,
    )
    fig.suptitle(
        "Surface-to-depth cumulative OHC anomaly: 2023/24 versus strong-event composite",
        fontsize=13.8,
        fontweight="bold",
        y=0.965,
    )
    titles = ("2023/24", "1982/83, 1997/98, 2015/16 composite", "2023/24 minus composite")
    for col, title in enumerate(titles):
        axes[0, col].set_title(title, fontsize=10.2, fontweight="bold", pad=6)

    mesh = None
    letter_index = 0
    for row, (stage, months) in enumerate(base.PENG_STAGES.items()):
        target = base.stage_mean(ohca, (base.TARGET_YEAR,), stage)
        composite = base.stage_mean(ohca, base.COMPOSITE_YEARS, stage)
        target_abs = base.stage_mean(temperature, (base.TARGET_YEAR,), stage)
        composite_abs = base.stage_mean(temperature, base.COMPOSITE_YEARS, stage)
        clim_abs = base.climatological_mean(climatology, months)
        fields = (target, composite, target - composite)
        absolutes = (target_abs, composite_abs, None)
        clim_fields = (clim_abs, clim_abs, None)
        for col in range(3):
            ax = axes[row, col]
            mesh = draw_section(
                ax,
                fields[col],
                norm=norm,
                actual_temperature=absolutes[col],
                climatological_temperature=clim_fields[col],
            )
            format_axis(
                ax,
                show_xlabel=row == len(base.PENG_STAGES) - 1,
                show_ylabel=col == 0,
            )
            base.panel_letter(ax, chr(ord("a") + letter_index))
            letter_index += 1
            if col == 0:
                ax.text(
                    -0.145,
                    0.50,
                    stage,
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    rotation=90,
                    fontsize=10.2,
                    fontweight="bold",
                )
    assert mesh is not None
    add_isotherm_legend(fig, x=0.5, y=0.925)
    cax = fig.add_axes((0.27, 0.075, 0.48, 0.020))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Cumulative OHC anomaly from surface to depth (GJ m⁻²)")
    fig.text(0.012, 0.016, figure_note(), fontsize=7.2, color="0.28")
    return save_figure(
        fig,
        output_dir,
        "fig_soda3_cumulative_ohca_jfm_aproct_ndj_2023_vs_strong_event_composite",
    )


def plot_four_season(
    temperature: xr.DataArray,
    ohca: xr.DataArray,
    climatology: xr.DataArray,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(4, 3, figsize=(12.8, 10.3), sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.078,
        right=0.985,
        top=0.88,
        bottom=0.13,
        wspace=0.07,
        hspace=0.13,
    )
    fig.suptitle(
        "Quarterly cumulative OHC-anomaly evolution: 2023 versus strong-event composite",
        fontsize=14.0,
        fontweight="bold",
        y=0.965,
    )
    titles = ("2023", "1982/1997/2015 composite", "2023 minus composite")
    for col, title in enumerate(titles):
        axes[0, col].set_title(title, fontsize=10.8, fontweight="bold", pad=6)

    mesh = None
    letter_index = 0
    for row, (season, months) in enumerate(base.SEASONS.items()):
        target = base.event_mean(ohca, (base.TARGET_YEAR,), months)
        composite = base.event_mean(ohca, base.COMPOSITE_YEARS, months)
        target_abs = base.event_mean(temperature, (base.TARGET_YEAR,), months)
        composite_abs = base.event_mean(temperature, base.COMPOSITE_YEARS, months)
        clim_abs = base.climatological_mean(climatology, months)
        fields = (target, composite, target - composite)
        absolutes = (target_abs, composite_abs, None)
        clim_fields = (clim_abs, clim_abs, None)
        for col in range(3):
            ax = axes[row, col]
            mesh = draw_section(
                ax,
                fields[col],
                norm=norm,
                actual_temperature=absolutes[col],
                climatological_temperature=clim_fields[col],
            )
            format_axis(
                ax,
                show_xlabel=row == len(base.SEASONS) - 1,
                show_ylabel=col == 0,
            )
            base.panel_letter(ax, chr(ord("a") + letter_index))
            letter_index += 1
            if col == 0:
                ax.text(
                    -0.14,
                    0.50,
                    season,
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    rotation=90,
                    fontsize=11.0,
                    fontweight="bold",
                )
    assert mesh is not None
    add_isotherm_legend(fig, x=0.5, y=0.930)
    cax = fig.add_axes((0.27, 0.062, 0.48, 0.018))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Cumulative OHC anomaly from surface to depth (GJ m⁻²)")
    fig.text(0.012, 0.012, figure_note(), fontsize=7.2, color="0.28")
    return save_figure(
        fig,
        output_dir,
        "fig_soda3_cumulative_ohca_jfm_amj_jas_ond_2023_vs_1982_1997_2015",
    )


def plot_monthly(
    temperature: xr.DataArray,
    ohca: xr.DataArray,
    climatology: xr.DataArray,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(3, 6, figsize=(19.2, 8.0), sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.061,
        right=0.995,
        top=0.84,
        bottom=0.18,
        wspace=0.055,
        hspace=0.11,
    )
    fig.suptitle(
        "Monthly cumulative OHC-anomaly evolution during early 2023",
        fontsize=15.2,
        fontweight="bold",
        y=0.965,
    )
    row_labels = ("2023", "1982/1997/2015\ncomposite", "2023 − composite")
    mesh = None
    for col, (month, label) in enumerate(zip(base.MONTHS, base.MONTH_LABELS)):
        axes[0, col].set_title(label, fontsize=10.8, fontweight="bold", pad=5)
        target = base.event_mean(ohca, (base.TARGET_YEAR,), (month,))
        composite = base.event_mean(ohca, base.COMPOSITE_YEARS, (month,))
        target_abs = base.event_mean(temperature, (base.TARGET_YEAR,), (month,))
        composite_abs = base.event_mean(temperature, base.COMPOSITE_YEARS, (month,))
        clim_abs = base.climatological_mean(climatology, (month,))
        fields = (target, composite, target - composite)
        absolutes = (target_abs, composite_abs, None)
        clim_fields = (clim_abs, clim_abs, None)
        for row in range(3):
            ax = axes[row, col]
            mesh = draw_section(
                ax,
                fields[row],
                norm=norm,
                actual_temperature=absolutes[row],
                climatological_temperature=clim_fields[row],
            )
            format_axis(ax, show_xlabel=row == 2, show_ylabel=col == 0)
            base.panel_letter(ax, chr(ord("a") + row * len(base.MONTHS) + col))
            if col == 0:
                ax.text(
                    -0.24,
                    0.50,
                    row_labels[row],
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    rotation=90,
                    fontsize=9.0,
                    fontweight="bold",
                )
    assert mesh is not None
    add_isotherm_legend(fig, x=0.53, y=0.885)
    cax = fig.add_axes((0.30, 0.083, 0.42, 0.025))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Cumulative OHC anomaly from surface to depth (GJ m⁻²)")
    fig.text(0.010, 0.015, figure_note(), fontsize=7.2, color="0.28")
    return save_figure(
        fig,
        output_dir,
        "fig_soda3_cumulative_ohca_jan_jun_2023_monthly_evolution",
    )


def regional_mean_at_depth(
    field: xr.DataArray,
    *,
    lon_bounds: tuple[float, float],
    depth: float,
) -> float:
    selected = field.sel(lon=slice(*lon_bounds)).sel(depth=depth, method="nearest")
    return float(selected.mean("lon", skipna=True))


def print_diagnostics(ohca: xr.DataArray, vlim: float) -> None:
    event_data = ohca.sel(time=ohca.time.dt.year.isin((*base.COMPOSITE_YEARS, base.TARGET_YEAR)))
    finite = event_data.values
    finite = finite[np.isfinite(finite)]
    print(
        "Cumulative-OHCA diagnostics: "
        f"range=[{finite.min():.3f}, {finite.max():.3f}] GJ m-2, "
        f"p01={np.percentile(finite, 1):.3f}, p99={np.percentile(finite, 99):.3f}, "
        f"fraction beyond +/-{vlim:g}={np.mean(np.abs(finite) > vlim):.4f}"
    )
    regions = (
        ("west_to_220m", (120.0, 180.0), 220.0),
        ("central_east_to_180m", (200.0, 270.0), 180.0),
        ("fep_to_100m", base.FEP_BOUNDS, 100.0),
        ("fep_to_300m", base.FEP_BOUNDS, 300.0),
    )
    for stage in base.PENG_STAGES:
        target = base.stage_mean(ohca, (base.TARGET_YEAR,), stage)
        composite = base.stage_mean(ohca, base.COMPOSITE_YEARS, stage)
        print(stage)
        for label, lon_bounds, depth in regions:
            target_value = regional_mean_at_depth(target, lon_bounds=lon_bounds, depth=depth)
            composite_value = regional_mean_at_depth(composite, lon_bounds=lon_bounds, depth=depth)
            print(
                f"  {label}: 2023={target_value:+.3f}, composite={composite_value:+.3f}, "
                f"difference={target_value - composite_value:+.3f} GJ m-2"
            )
    print("Monthly 2023 FEP cumulative OHCA at 300 m:")
    for month in base.MONTHS:
        field = base.event_mean(ohca, (base.TARGET_YEAR,), (month,))
        value = regional_mean_at_depth(field, lon_bounds=base.FEP_BOUNDS, depth=300.0)
        print(f"  month={month}: {value:+.3f} GJ m-2")


def main() -> None:
    args = parse_args()
    if args.vlim <= 0:
        raise ValueError("--vlim must be positive")
    base.setup_style()
    with open_dataset(args.input) as source:
        base.validate_input(source)
        temperature = base.equatorial_mean_temperature(source)
    climatology = base.build_monthly_climatology(temperature)
    temperature_anomaly = base.monthly_anomaly(temperature, climatology)
    ohca = cumulative_ohca(temperature_anomaly)

    print_diagnostics(ohca, args.vlim)
    plot_three_stage(temperature, ohca, climatology, args.output_dir, args.vlim)
    plot_four_season(temperature, ohca, climatology, args.output_dir, args.vlim)
    plot_monthly(temperature, ohca, climatology, args.output_dir, args.vlim)


if __name__ == "__main__":
    main()
