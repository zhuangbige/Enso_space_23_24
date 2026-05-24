from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    priority: str
    temporal_coverage: str
    resolution: str
    variables: tuple[str, ...]
    official_url: str
    research_use: str
    access_notes: str


CORE_DATASET_IDS = (
    "era5",
    "oisst_v2_1",
    "ersst_v5",
    "gpcp",
    "noaa_olr",
    "oras5",
    "tao_triton",
)

EXPANSION_DATASET_IDS = (
    "glorys12v1",
    "argo",
    "duacs",
)

PAPER_DATASET_IDS = (
    "paper_zenodo",
    "oisst_v2_1",
    "era5",
    "gpcp",
    "godas",
    "cesm_lens2",
)


_DATASETS = {
    "paper_zenodo": Dataset(
        id="paper_zenodo",
        name="Peng 2025 Zenodo code and figure-data archive",
        priority="paper",
        temporal_coverage="Figure-specific processed data for Peng et al. 2025",
        resolution="MAT files and Python scripts; 92.2 MB record page file set",
        variables=("figure_data", "plotting_code", "supplementary_figure_data"),
        official_url="https://zenodo.org/records/15074285",
        research_use="Direct figure data and plotting code for reproducing the source paper's diagnostics.",
        access_notes="Start here before downloading raw gridded data; use it to identify variable names, regions, and plotting conventions.",
    ),
    "era5": Dataset(
        id="era5",
        name="ECMWF ERA5 atmospheric reanalysis",
        priority="core",
        temporal_coverage="1940-present",
        resolution="0.25 deg regular lat-lon; hourly and monthly products",
        variables=(
            "u850",
            "v850",
            "slp",
            "precipitation",
            "surface_fluxes",
            "velocity_potential_200",
        ),
        official_url="https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview",
        research_use="Wind, SOI/SLP, Walker circulation, and atmospheric response diagnostics.",
        access_notes="Use monthly means first; retrieve hourly fields only for event-scale wind burst checks.",
    ),
    "oisst_v2_1": Dataset(
        id="oisst_v2_1",
        name="NOAA Optimum Interpolation SST v2.1",
        priority="core",
        temporal_coverage="1981-09-present",
        resolution="0.25 deg daily",
        variables=("sst", "sst_anomaly"),
        official_url="https://www.ncei.noaa.gov/products/optimum-interpolation-sst",
        research_use="Primary SST product for Nino indices and seasonal anomaly maps.",
        access_notes="Start with monthly averages derived from daily fields.",
    ),
    "ersst_v5": Dataset(
        id="ersst_v5",
        name="NOAA Extended Reconstructed SST v5",
        priority="core",
        temporal_coverage="1854-present",
        resolution="2 deg monthly",
        variables=("sst",),
        official_url="https://www.ncei.noaa.gov/products/extended-reconstructed-sst",
        research_use="Long-record robustness check and historical strong El Nino comparison.",
        access_notes="Use for event classification and sensitivity to SST product choice.",
    ),
    "gpcp": Dataset(
        id="gpcp",
        name="Global Precipitation Climatology Project",
        priority="core",
        temporal_coverage="1979-present for commonly used monthly products",
        resolution="2.5 deg monthly for v2.3",
        variables=("precipitation",),
        official_url="https://psl.noaa.gov/data/gridded/data.gpcp.html",
        research_use="Independent precipitation check for weak tropical Pacific rainfall response.",
        access_notes="Use alongside ERA5 precipitation to separate observational signals from reanalysis behavior.",
    ),
    "noaa_olr": Dataset(
        id="noaa_olr",
        name="NOAA interpolated outgoing longwave radiation",
        priority="core",
        temporal_coverage="1974-present with gaps before interpolation products",
        resolution="2.5 deg daily/monthly",
        variables=("olr",),
        official_url="https://psl.noaa.gov/data/gridded/data.interp_OLR.html",
        research_use="Convection proxy for tropical Pacific and Maritime Continent response.",
        access_notes="Use monthly anomalies for seasonal maps and July 2023 convection diagnostics.",
    ),
    "oras5": Dataset(
        id="oras5",
        name="ECMWF Ocean Reanalysis System 5",
        priority="core",
        temporal_coverage="1979-present for main reanalysis; extension may be available",
        resolution="0.25 deg; 5 ensemble members",
        variables=("temperature", "salinity", "ssh", "currents", "ohc", "d20"),
        official_url="https://www.ecmwf.int/en/forecasts/dataset/ocean-reanalysis-system-5",
        research_use="Auxiliary ocean precondition check: OHC, thermocline, and recharge state.",
        access_notes="Use ensemble spread as an uncertainty guide for OHC/D20 diagnostics.",
    ),
    "godas": Dataset(
        id="godas",
        name="NOAA Global Ocean Data Assimilation System",
        priority="paper",
        temporal_coverage="1980-present on NOAA PSL gridded pages",
        resolution="Product-dependent ocean grid; monthly fields are sufficient for first replication",
        variables=("temperature", "sea_level", "currents", "mixed_layer_heat_budget_inputs"),
        official_url="https://psl.noaa.gov/data/gridded/data.godas.html",
        research_use="Source-paper ocean reanalysis for equatorial temperature, SLA-like diagnostics, and mixed-layer budget context.",
        access_notes="Methods point to GODAS for 1980-2024 ocean temperature and related ocean diagnostics.",
    ),
    "cesm_lens2": Dataset(
        id="cesm_lens2",
        name="CESM2 Large Ensemble Community Project",
        priority="paper",
        temporal_coverage="Historical and scenario ensemble output; variable-dependent availability",
        resolution="Single-variable timeseries at annual to 3-hourly frequencies",
        variables=("sst", "sea_level", "surface_wind_stress", "large_ensemble_context"),
        official_url="https://www.cesm.ucar.edu/community-projects/lens2/data-sets",
        research_use="Source-paper large-ensemble context for 2023-like El Nino frequency in a warming climate.",
        access_notes="Use later; the first-stage decoupling diagnosis does not need the full LENS2 archive.",
    ),
    "tao_triton": Dataset(
        id="tao_triton",
        name="TAO/TRITON tropical Pacific moored buoy array",
        priority="core",
        temporal_coverage="Operational ENSO observing system, strongest after 1990s",
        resolution="Station observations along the tropical Pacific",
        variables=("winds", "sst", "subsurface_temperature", "currents"),
        official_url="https://www.pmel.noaa.gov/gtmba/building-tao",
        research_use="Anchor observations for equatorial wind and thermocline anomalies.",
        access_notes="Use selected equatorial stations for validation rather than gridded map production.",
    ),
    "glorys12v1": Dataset(
        id="glorys12v1",
        name="Copernicus Marine GLORYS12V1 global ocean reanalysis",
        priority="expansion",
        temporal_coverage="1993-present",
        resolution="1/12 deg; 50 vertical levels",
        variables=("temperature", "salinity", "currents", "sea_level", "mixed_layer_depth"),
        official_url="https://data.marine.copernicus.eu/product-detail/GLOBAL_MULTIYEAR_PHY_001_030",
        research_use="High-resolution ocean background and propagation-path extension.",
        access_notes="Reserve for later boundary-wave or pathway diagnostics because of data volume.",
    ),
    "argo": Dataset(
        id="argo",
        name="Argo profiling floats",
        priority="expansion",
        temporal_coverage="Global mature coverage mainly after mid-2000s",
        resolution="Profiles roughly every 10 days to 2000 m for core Argo",
        variables=("temperature", "salinity", "pressure"),
        official_url="https://www.aoml.noaa.gov/argo/",
        research_use="Independent profile constraint on OHC and stratification.",
        access_notes="Use gridded Argo products first unless profile-level QC is required.",
    ),
    "duacs": Dataset(
        id="duacs",
        name="DUACS/Copernicus satellite altimetry sea level",
        priority="expansion",
        temporal_coverage="1993-present",
        resolution="Daily gridded SLA/ADT products, product-dependent grid",
        variables=("sla", "adt", "geostrophic_currents"),
        official_url="https://climate.copernicus.eu/about-indicators-sea-level",
        research_use="SLA/SSH bridge to ocean memory and off-equatorial recharge.",
        access_notes="Use delayed-time products for climate diagnostics when current-year latency allows.",
    ),
}


def list_datasets(priority: str | None = None) -> tuple[Dataset, ...]:
    if priority == "paper":
        return tuple(_DATASETS[dataset_id] for dataset_id in PAPER_DATASET_IDS)
    datasets = tuple(_DATASETS[dataset_id] for dataset_id in _DATASETS)
    if priority is None:
        return datasets
    return tuple(dataset for dataset in datasets if dataset.priority == priority)


def get_dataset(dataset_id: str) -> Dataset:
    try:
        return _DATASETS[dataset_id]
    except KeyError as exc:
        available = ", ".join(sorted(_DATASETS))
        raise KeyError(f"Unknown dataset '{dataset_id}'. Available datasets: {available}") from exc
