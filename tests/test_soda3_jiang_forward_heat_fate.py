from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts import analyze_soda3_jiang_forward_heat_fate as fate


class SyntheticSnapshot:
    def __init__(
        self,
        timestamp: str,
        *,
        u: float | np.ndarray = 0.0,
        v: float | np.ndarray = 0.0,
        w: float | np.ndarray = 0.0,
        temp: float | np.ndarray = 19.0,
    ) -> None:
        self.timestamp = pd.Timestamp(timestamp)
        self.z_t = np.asarray([10.0, 30.0])
        self.z_w = np.asarray([10.0, 30.0])
        self.lat_t = np.asarray([-1.0, 1.0])
        self.lon_t = np.asarray([219.0, 221.0])
        self.lat_uv = self.lat_t
        self.lon_uv = self.lon_t
        self._values = {"u": u, "v": v, "w": w, "temp": temp}

    def interpolate(self, name: str, positions: np.ndarray) -> np.ndarray:
        value = np.asarray(self._values[name], dtype=float)
        if value.ndim == 0:
            return np.full(len(positions), float(value))
        return np.resize(value, len(positions)).astype(float)


def expected_temperature(value: float = 18.0) -> SimpleNamespace:
    return SimpleNamespace(
        depth=np.asarray([10.0, 30.0]),
        lat=np.asarray([-1.0, 1.0]),
        lon=np.asarray([220.0]),
        temperature_c=np.full((2, 2, 1), value),
        month=1,
    )


def test_gate_seed_weight_is_anomalous_heat_flux() -> None:
    seeds = fate.seed_gate_particles(
        SyntheticSnapshot("2015-01-03", u=0.5, temp=19.0),
        expected_temperature(18.0),
        interval_seconds=86_400.0,
        event=2015,
    )
    assert len(seeds) == 4
    assert (seeds["gate_u_ms"] > 0.0).all()
    assert np.allclose(seeds["release_temp_anomaly_c"], 1.0)
    expected = (
        fate.RHO0
        * fate.CP0
        * 0.5
        * seeds["section_area_m2"].sum()
        * 86_400.0
        / 1.0e21
    )
    assert seeds["heat_weight_zj"].sum() == pytest.approx(expected)


def test_gate_seed_rejects_westward_and_nonpositive_anomaly() -> None:
    seeds = fate.seed_gate_particles(
        SyntheticSnapshot(
            "2023-01-02",
            u=np.asarray([0.5, -0.5, 0.5, 0.5]),
            temp=np.asarray([19.0, 19.0, 18.0, 18.2]),
        ),
        expected_temperature(18.0),
        interval_seconds=86_400.0,
        event=2023,
    )
    assert len(seeds) == 2
    assert (seeds["gate_u_ms"] > 0.0).all()
    assert (seeds["release_temp_anomaly_c"] > fate.MINIMUM_ANOMALY_C).all()


def test_centered_release_intervals_cover_requested_window() -> None:
    times = pd.DatetimeIndex(["2015-01-05", "2015-02-04", "2015-03-06"])
    seconds = fate.centered_release_intervals_seconds(
        times,
        pd.Timestamp("2015-01-01"),
        pd.Timestamp("2015-04-01"),
    )
    assert seconds.sum() == pytest.approx(90.0 * 86_400.0)
    assert (seconds > 0.0).all()


@pytest.mark.parametrize(
    ("u", "v", "w", "expected"),
    [
        (-2.0, 0.0, 0.0, "returned_west_140w"),
        (0.0, 2.0, 0.0, "north_of_5n"),
        (0.0, -2.0, 0.0, "south_of_10s"),
        (0.0, 0.0, -1.0e-3, "below_300m"),
    ],
)
def test_forward_first_exit_classification(
    u: float,
    v: float,
    w: float,
    expected: str,
) -> None:
    earlier = SyntheticSnapshot("2015-01-01", u=u, v=v, w=w)
    later = SyntheticSnapshot("2015-01-11", u=u, v=v, w=w)
    state = pd.DataFrame(
        {
            "lon": [220.1],
            "lat": [0.0],
            "depth_m": [50.0],
            "active": [True],
            "destination": ["active"],
            "surface_clip_steps": [0],
        }
    )
    result = fate.integrate_interval_forward(
        state,
        earlier,
        later,
        step_hours=12.0,
        w_to_depth_sign=-1.0,
    )
    assert result.loc[0, "destination"] == expected
    assert not bool(result.loc[0, "active"])
