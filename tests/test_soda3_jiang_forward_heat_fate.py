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
        self.z_t = np.asarray([10.0, 300.0])
        self.z_w = np.asarray([10.0, 300.0])
        self.lat_t = np.asarray([-5.0, 5.0])
        self.lon_t = np.asarray([218.0, 280.0])
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
        depth=np.asarray([10.0, 300.0]),
        lat=np.asarray([-5.0, 5.0]),
        lon=np.asarray([218.0, 280.0]),
        temperature_c=np.full((2, 2, 2), value),
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
        (0.0, -2.0, 0.0, "south_of_5s"),
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


def test_tracking_calendar_runs_january_to_following_may() -> None:
    files = [
        (pd.Timestamp("2014-12-27"), "before"),
        (pd.Timestamp("2015-01-04"), "start"),
        (pd.Timestamp("2015-06-28"), "release-end"),
        (pd.Timestamp("2015-12-30"), "year-end"),
        (pd.Timestamp("2016-05-29"), "finish"),
        (pd.Timestamp("2016-06-03"), "after"),
    ]
    selected = fate.filter_tracking_calendar(files, 2015)
    assert selected[0][0] == pd.Timestamp("2015-01-04")
    assert selected[-1][0] == pd.Timestamp("2016-05-29")
    assert [item[1] for item in selected] == [
        "start",
        "release-end",
        "year-end",
        "finish",
    ]


def test_release_calendar_ends_in_development_june() -> None:
    assert fate.is_release_time(pd.Timestamp("2015-01-04"), 2015)
    assert fate.is_release_time(pd.Timestamp("2015-06-28"), 2015)
    assert not fate.is_release_time(pd.Timestamp("2015-07-03"), 2015)
    assert not fate.is_release_time(pd.Timestamp("2016-01-03"), 2015)


def test_subsample_tracking_files_preserves_release_and_terminal_endpoints() -> None:
    times = pd.date_range("2015-01-01", "2016-05-31", freq="5D")
    files = [(time, str(index)) for index, time in enumerate(times)]
    selected = fate.subsample_tracking_files(files, event=2015, stride=6)
    assert selected[0] == files[0]
    assert selected[-1] == files[-1]
    assert max(time for time, _ in selected if fate.is_release_time(time, 2015)).month == 6


def test_heat_weighted_destination_summary_keeps_full_denominator() -> None:
    endpoints = pd.DataFrame(
        {
            "event": [2015, 2015, 2015],
            "destination": ["returned_west_140w", "north_of_5n", "invalid_velocity"],
            "heat_weight_zj": [2.0, 1.0, 1.0],
            "release_temp_anomaly_c": [2.0, 1.0, 1.0],
            "endpoint_temp_anomaly_c": [np.nan, np.nan, np.nan],
            "surface_clip_steps": [0, 1, 0],
        }
    )
    summary = fate.summarize_endpoints(endpoints)
    assert summary["gate_positive_anomaly_heat_zj"] == pytest.approx(4.0)
    assert summary["heat_fraction_returned_west_140w"] == pytest.approx(0.5)
    assert summary["heat_fraction_north_of_5n"] == pytest.approx(0.25)
    assert summary["heat_fraction_invalid_velocity"] == pytest.approx(0.25)
    assert summary["resolved_heat_fraction"] == pytest.approx(0.75)
    assert summary["resolved_fraction_returned_west_140w"] == pytest.approx(2.0 / 3.0)
    assert summary["resolved_fraction_north_of_5n"] == pytest.approx(1.0 / 3.0)
    fraction_columns = [key for key in summary if key.startswith("heat_fraction_")]
    assert sum(float(summary[key]) for key in fraction_columns) == pytest.approx(1.0)


def test_retained_endpoint_anomaly_is_heat_weighted() -> None:
    endpoints = pd.DataFrame(
        {
            "event": [2023, 2023],
            "destination": ["retained_east", "retained_east"],
            "heat_weight_zj": [1.0, 3.0],
            "release_temp_anomaly_c": [1.0, 3.0],
            "endpoint_temp_anomaly_c": [0.5, 1.5],
            "surface_clip_steps": [0, 2],
        }
    )
    summary = fate.summarize_endpoints(endpoints)
    assert summary["retained_weighted_endpoint_temp_anomaly_c"] == pytest.approx(1.25)
    assert summary["retained_weighted_anomaly_ratio"] == pytest.approx(0.5)
    assert summary["surface_exposure_heat_fraction"] == pytest.approx(0.75)


def test_track_event_cohorts_releases_only_in_development_window() -> None:
    snapshots = [
        SyntheticSnapshot("2015-01-05", u=0.01, temp=19.0),
        SyntheticSnapshot("2015-06-28", u=0.01, temp=19.0),
        SyntheticSnapshot("2016-05-29", u=0.0, temp=19.0),
    ]
    endpoints, trajectories = fate.track_event_cohorts(
        event=2015,
        snapshots=snapshots,
        release_expected_fields={1: expected_temperature(), 6: expected_temperature()},
        final_expected_field=expected_temperature(),
        step_hours=24.0,
    )
    assert len(endpoints) == 8
    assert set(pd.DatetimeIndex(endpoints["release_date"]).month) == {1, 6}
    assert endpoints["destination"].eq("retained_east").all()
    assert np.allclose(endpoints["endpoint_temp_anomaly_c"], 1.0)
    assert endpoints["particle_id"].is_unique
    assert trajectories["particle_id"].nunique() == 8


def test_audit_requires_destination_fractions_to_sum_to_one() -> None:
    summary = pd.DataFrame(
        [
            {
                "event": 2015,
                "gate_positive_anomaly_heat_zj": 3.0,
                **{
                    f"heat_fraction_{destination}": (1.0 if destination == "retained_east" else 0.0)
                    for destination in fate.DESTINATIONS
                },
            }
        ]
    )
    audit = fate.audit_summary(summary)
    assert audit["events"] == [2015]
    assert audit["maximum_destination_fraction_sum_error"] < 1.0e-12


def test_record_variable_offset_includes_record_stride() -> None:
    assert fate.record_variable_offset(
        variable_begin=100,
        record_size=1000,
        time_index=3,
        spatial_element_index=7,
        itemsize=4,
    ) == 3128


def test_midpoint_grid_exit_is_classified_before_interpolation_nan() -> None:
    class BoundedSnapshot(SyntheticSnapshot):
        def interpolate(self, name: str, positions: np.ndarray) -> np.ndarray:
            output = super().interpolate(name, positions)
            outside = (positions[:, 1] < -5.0) | (positions[:, 1] > 5.0)
            output[outside] = np.nan
            return output

    earlier = BoundedSnapshot("2015-01-01", v=2.0)
    later = BoundedSnapshot("2015-01-02", v=2.0)
    state = pd.DataFrame(
        {
            "lon": [230.0],
            "lat": [4.9],
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
        step_hours=24.0,
        w_to_depth_sign=-1.0,
    )
    assert result.loc[0, "destination"] == "north_of_5n"


def test_surface_clipping_uses_shallowest_velocity_grid_depth() -> None:
    class BoundedDepthSnapshot(SyntheticSnapshot):
        def interpolate(self, name: str, positions: np.ndarray) -> np.ndarray:
            output = super().interpolate(name, positions)
            output[positions[:, 2] < 10.0] = np.nan
            return output

    earlier = BoundedDepthSnapshot("2015-01-01", w=1.0e-3)
    later = BoundedDepthSnapshot("2015-01-02", w=1.0e-3)
    state = pd.DataFrame(
        {
            "lon": [230.0],
            "lat": [0.0],
            "depth_m": [10.0],
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
    assert bool(result.loc[0, "active"])
    assert result.loc[0, "depth_m"] == pytest.approx(10.0)
    assert result.loc[0, "surface_clip_steps"] > 0
