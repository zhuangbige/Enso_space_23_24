from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgcmExperiment:
    id: str
    name: str
    sst_forcing: str
    purpose: str
    expected_signal: str
    optional: bool = False


REQUIRED_AGCM_EXPERIMENTS = (
    "global_observed_sst",
    "pacific_only",
    "atlantic_only",
    "indian_ocean_only",
    "atlantic_plus_indian",
    "detrended_global_sst",
    "trend_retained_global_sst",
)


_REQUIRED_EXPERIMENTS = (
    AgcmExperiment(
        id="global_observed_sst",
        name="Global observed SST control",
        sst_forcing="Observed global monthly SST anomalies.",
        purpose="Baseline atmospheric response to the observed 2023/24 SST pattern.",
        expected_signal="Should reproduce weak atmospheric coupling if SST boundary forcing is sufficient.",
    ),
    AgcmExperiment(
        id="pacific_only",
        name="Pacific-only SST anomaly",
        sst_forcing="Observed SST anomalies retained in tropical Pacific; climatology elsewhere.",
        purpose="Estimate canonical atmospheric response to Pacific El Nino forcing alone.",
        expected_signal="Expected to produce stronger westerly/precipitation response than observed if extra-Pacific basins damped coupling.",
    ),
    AgcmExperiment(
        id="atlantic_only",
        name="Atlantic-only SST anomaly",
        sst_forcing="Observed Atlantic anomalies retained; climatology elsewhere.",
        purpose="Isolate tropical Atlantic contribution to anomalous easterlies and rainfall displacement.",
        expected_signal="Can test whether Atlantic warming suppresses Pacific convective response.",
    ),
    AgcmExperiment(
        id="indian_ocean_only",
        name="Indian Ocean-only SST anomaly",
        sst_forcing="Observed Indian Ocean anomalies retained; climatology elsewhere.",
        purpose="Isolate Indian Ocean warming and monsoon/Maritime Continent pathway.",
        expected_signal="Expected to matter most in summer-autumn decoupling diagnostics.",
    ),
    AgcmExperiment(
        id="atlantic_plus_indian",
        name="Atlantic plus Indian Ocean SST anomalies",
        sst_forcing="Observed Atlantic and Indian Ocean anomalies retained; climatological Pacific.",
        purpose="Estimate combined extra-Pacific damping of Pacific wind/rainfall response.",
        expected_signal="Should clarify whether combined basins reproduce weak coupling residuals.",
    ),
    AgcmExperiment(
        id="detrended_global_sst",
        name="Detrended global SST forcing",
        sst_forcing="Observed SST anomalies after removing long-term trend by grid cell.",
        purpose="Separate event pattern from background warming contribution.",
        expected_signal="If rainfall response strengthens after detrending, background relative warming raised Pacific convection threshold.",
    ),
    AgcmExperiment(
        id="trend_retained_global_sst",
        name="Trend-retained global SST forcing",
        sst_forcing="Observed SST anomalies with long-term trend retained.",
        purpose="Reference case for comparing against detrended SST forcing.",
        expected_signal="Should retain the observed pan-tropical warmth and weak teleconnection tendencies.",
    ),
)


_OPTIONAL_EXPERIMENTS = (
    AgcmExperiment(
        id="tna_only",
        name="Tropical North Atlantic-only SST anomaly",
        sst_forcing="Observed tropical North Atlantic anomalies retained; climatology elsewhere.",
        purpose="Target July 2023 easterly-response mechanism.",
        expected_signal="Useful if the initial diagnostics show a strong summer TNA-wind residual link.",
        optional=True,
    ),
    AgcmExperiment(
        id="ism_mc_heating",
        name="Indian summer monsoon/Maritime Continent heating",
        sst_forcing="Idealized diabatic heating over ISM/MC regions.",
        purpose="Test whether regional heating can reverse Pacific westerly response in summer.",
        expected_signal="Useful only after diagnosing a robust July-August convection anomaly.",
        optional=True,
    ),
)


def build_agcm_matrix(include_optional: bool = False) -> tuple[AgcmExperiment, ...]:
    if include_optional:
        return _REQUIRED_EXPERIMENTS + _OPTIONAL_EXPERIMENTS
    return _REQUIRED_EXPERIMENTS


def seasonal_windows() -> dict[str, tuple[int, ...]]:
    return {
        "AMJ": (4, 5, 6),
        "JJA": (6, 7, 8),
        "SON": (9, 10, 11),
        "DJF": (12, 1, 2),
    }
