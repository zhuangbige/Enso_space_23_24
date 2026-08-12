from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from scripts import compare_2015_2023_coupling_exchange as module


def synthetic_monthly_frame(start_year: int, end_year: int) -> pd.DataFrame:
    rows = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "value": 2.5 * month + 0.2 * (year - start_year),
                }
            )
    return pd.DataFrame(rows)


def test_same_month_linear_anomaly_removes_month_specific_trend() -> None:
    frame = synthetic_monthly_frame(1982, 2016)
    result = module.same_month_linear_anomaly(frame, "value")
    assert np.allclose(result, 0.0, atol=1e-10)


def test_same_month_linear_anomaly_preserves_index() -> None:
    frame = synthetic_monthly_frame(1982, 2016).sample(frac=1.0, random_state=7)
    result = module.same_month_linear_anomaly(frame, "value")
    assert result.index.equals(frame.index)


def test_to_upward_loss_reverses_era5_downward_sign() -> None:
    result = module.to_upward_loss(
        np.array([-100.0]),
        np.array([-10.0]),
        np.array([200.0]),
        np.array([-50.0]),
    )
    assert result["latent_loss"][0] == 100.0
    assert result["sensible_loss"][0] == 10.0
    assert result["turbulent_loss"][0] == 110.0
    assert result["net_ocean_loss"][0] == -40.0


def test_weighted_box_mean_uses_cosine_latitude_weights() -> None:
    field = xr.DataArray(
        np.array([[[0.0]], [[10.0]]]),
        dims=("lat", "lon", "time"),
        coords={"lat": [0.0, 60.0], "lon": [220.0], "time": [0]},
    )
    result = module.weighted_box_mean(field, 0.0, 60.0, 220.0, 220.0)
    assert float(result.item()) == pytest.approx(10.0 / 3.0)


def test_overlapping_season_windows_are_exact() -> None:
    assert module.SEASON_MONTHS["MAM"] == (3, 4, 5)
    assert module.SEASON_MONTHS["MJJ"] == (5, 6, 7)
    assert module.SEASON_MONTHS["JJA"] == (6, 7, 8)
    assert module.SEASON_MONTHS["SON"] == (9, 10, 11)


def test_audited_arrival_values_match_current_ppt() -> None:
    table = module.audited_arrival_table().set_index("year")
    assert table.loc[2015, "transport_140w_zj"] == 8.49
    assert table.loc[2015, "east_ohc_gain_zj"] == 8.60
    assert table.loc[2023, "transport_140w_zj"] == 9.90
    assert table.loc[2023, "east_ohc_gain_zj"] == 11.12
