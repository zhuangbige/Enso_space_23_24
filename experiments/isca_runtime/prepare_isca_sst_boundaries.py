"""Convert the existing 2023 IA×FEP SST factorial into Isca boundary files.

March-August use each 2023 factorial SST field. The other six months, land
points, and polar points outside ERSST coverage use Isca's bundled AMIP
climatology. Each output variable has the same name as its file stem, which is
the convention expected by Isca's ``mixed_layer_nml.sst_file`` option.
"""

from pathlib import Path

import numpy as np
import xarray as xr


RUNTIME = Path(__file__).resolve().parent
SOURCE = (
    RUNTIME.parent
    / "enso_type_transition_matrix"
    / "forcing"
    / "ersstv5_2023_agcm_ia_fep_factorial_mar_aug.nc"
)
REFERENCE = (
    RUNTIME
    / "Isca"
    / "exp"
    / "test_cases"
    / "realistic_continents"
    / "input"
    / "sst_clim_amip.nc"
)
OUTPUT_DIR = RUNTIME / "forcing_isca"

FACTORIAL_VARIABLES = [
    "sst_AG_IA0_FEP0",
    "sst_AG_IA0_FEP1",
    "sst_AG_IA1_FEP0",
    "sst_AG_IA1_FEP1",
    "sst_AG_IAR0_FEP0",
    "sst_AG_IAR0_FEP1",
    "sst_AG_IAR1_FEP0",
    "sst_AG_IAR1_FEP1",
]


def bilinear_periodic(
    field: xr.DataArray,
    target_lat: xr.DataArray,
    target_lon: xr.DataArray,
) -> xr.DataArray:
    """Bilinearly regrid a regular lat-lon field with a periodic longitude.

    If any of the four source corners is missing, the result remains missing
    and is subsequently filled by the AMIP reference climatology. This avoids
    interpolating SST across source-land cells.
    """
    source_lat = np.asarray(field.lat.values, dtype=float)
    source_lon = np.asarray(field.lon.values, dtype=float)
    values = np.asarray(field.values, dtype=float)
    output_lat = np.asarray(target_lat.values, dtype=float)
    output_lon = np.mod(np.asarray(target_lon.values, dtype=float), 360.0)

    if not (np.all(np.diff(source_lat) > 0) and np.all(np.diff(source_lon) > 0)):
        raise ValueError("Source latitude and longitude must be strictly increasing")

    lat_upper = np.searchsorted(source_lat, output_lat, side="right")
    valid_lat = (output_lat >= source_lat[0]) & (output_lat <= source_lat[-1])
    lat_upper = np.clip(lat_upper, 1, source_lat.size - 1)
    lat_lower = lat_upper - 1
    lat_weight = (
        (output_lat - source_lat[lat_lower])
        / (source_lat[lat_upper] - source_lat[lat_lower])
    )

    lon_upper_unwrapped = np.searchsorted(source_lon, output_lon, side="right")
    lon_lower = (lon_upper_unwrapped - 1) % source_lon.size
    lon_upper = lon_upper_unwrapped % source_lon.size
    lon_lower_value = source_lon[lon_lower]
    lon_upper_value = source_lon[lon_upper].copy()
    lon_upper_value[lon_upper_unwrapped == source_lon.size] += 360.0
    lon_weight = (
        (output_lon - lon_lower_value) / (lon_upper_value - lon_lower_value)
    )

    q00 = values[lat_lower[:, None], lon_lower[None, :]]
    q01 = values[lat_lower[:, None], lon_upper[None, :]]
    q10 = values[lat_upper[:, None], lon_lower[None, :]]
    q11 = values[lat_upper[:, None], lon_upper[None, :]]
    wx = lon_weight[None, :]
    wy = lat_weight[:, None]
    result = (
        q00 * (1.0 - wx) * (1.0 - wy)
        + q01 * wx * (1.0 - wy)
        + q10 * (1.0 - wx) * wy
        + q11 * wx * wy
    )
    result[~valid_lat, :] = np.nan
    return xr.DataArray(
        result,
        dims=("lat", "lon"),
        coords={"lat": target_lat, "lon": target_lon},
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = xr.open_dataset(SOURCE)
    reference = xr.open_dataset(REFERENCE, decode_times=False)
    base = reference["sst_clim_amip"]

    months = source.time.dt.month.values.astype(int)
    if months.tolist() != [3, 4, 5, 6, 7, 8]:
        raise ValueError(f"Expected March-August forcing, found months {months}")

    for source_name in FACTORIAL_VARIABLES:
        # Isca's legacy interpolator lowercases NetCDF field names internally,
        # so the file stem and data variable must also be lowercase.
        output_name = f"{source_name.lower()}_isca"
        output = base.copy(deep=True).rename(output_name)
        for source_index, month in enumerate(months):
            field_c = source[source_name].isel(time=source_index)
            field_k = bilinear_periodic(field_c, reference.lat, reference.lon) + 273.15
            month_index = month - 1
            filled = field_k.where(np.isfinite(field_k), base.isel(time=month_index))
            output[month_index, :, :] = filled.astype("float32")

        output.attrs = {
            "units": "K",
            "long_name": f"Isca prescribed SST for {source_name}",
            "source": str(SOURCE),
            "reference_climatology": str(REFERENCE),
            "forcing_months": "March-August 2023",
            "missing_value_policy": "AMIP climatology over land, polar gaps, and interpolation gaps",
        }
        dataset = xr.Dataset(
            {output_name: output},
            coords={name: reference.coords[name] for name in reference.coords},
            attrs={
                "title": f"2023 IA x FEP prescribed-SST boundary: {source_name}",
                "calendar": "THIRTY_DAY_MONTHS",
                "source_factorial": str(SOURCE),
            },
        )
        destination = OUTPUT_DIR / f"{output_name}.nc"
        dataset.to_netcdf(
            destination,
            engine="netcdf4",
            encoding={output_name: {"dtype": "float32", "zlib": True, "complevel": 2}},
            unlimited_dims=["time"],
        )

        check = xr.open_dataset(destination, decode_times=False)
        values = check[output_name]
        if bool(values.isnull().any()):
            raise RuntimeError(f"NaNs remain in {destination}")
        print(
            f"WROTE {destination.name} "
            f"shape={values.shape} min={float(values.min()):.3f} "
            f"max={float(values.max()):.3f}"
        )


if __name__ == "__main__":
    main()
