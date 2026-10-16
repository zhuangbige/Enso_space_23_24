"""ERA5 wind and NCEP latent-heat evidence beside the frozen D20 sLIM.

CDS throttled the required full ERA5 flux archive. The delivered comparison
uses NCEP-NCAR R1 flux with ERA5 vector winds, explicitly labelled as mixed
products. Wind weakening is a projection, not a monthly scalar-speed anomaly.
No model is fitted here.
"""
from pathlib import Path
import hashlib
import json
import os
import sys

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/maryland_enso_strength_mpl')
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/research_2026/enso_strength_screenshot_D20_2002_2024_20261015'
OUT = BASE / 'pmm_wind_flux_evidence'
RAW = ROOT / 'data/raw/era5/pmm_wind_flux_20261015'
WIND = ROOT / 'data/raw/era5/era5_monthly_10m_wind_pmm_1deg_1982_2025.nc'
SST = ROOT / 'data/raw/ersstv5_sst_monthly_full.nc'
FLUX = ROOT / 'data/raw/ncep_pmm_flux_20261015/lhtfl.sfc.mon.mean.nc'
BOX = dict(lat_min=10, lat_max=30, lon_min=205, lon_max=245)
SEASONS = dict(Feb_Jun=range(2, 7), MAM=range(3, 6), JJA=range(6, 9),
               SON=range(9, 12), DJF=range(12, 15))
SERIES = ['pmm', 'sst_anomaly_c', 'wind_weakening_ms', 'along_trade_weakening_ms',
          'latent_down_anomaly_wm2', 'u10_anomaly_ms', 'v10_anomaly_ms']
PROTECTED = ['models_and_preprocessing.json', 'monthly_forecasts.csv',
             'seasonal_forecasts.csv', 'development_year_summary.csv',
             'primary_event_summary.csv', 'primary_group_summary.csv']


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def normalize(data):
    names = {a: b for a, b in [('valid_time', 'time'), ('latitude', 'lat'), ('longitude', 'lon')]
             if a in data.dims}
    data = data.rename(names)
    for coord in ['number', 'expver']:
        if coord in data.coords and coord not in data.dims:
            data = data.drop_vars(coord)
    data = data.assign_coords(lon=data.lon % 360).sortby('lon').sortby('lat')
    data = data.assign_coords(time=pd.DatetimeIndex(data.time.values).to_period('M').to_timestamp())
    assert data.indexes['time'].is_unique
    return data.sel(time=slice('1982-01', '2024-12'), lat=slice(0, 30), lon=slice(190, 260))


def anomaly(data):
    data = data.astype(float)
    baseline = data.sel(time=slice('1991', '2020'))
    assert len(baseline.time) == 360
    clim = baseline.groupby('time.month').mean('time')
    out = data.groupby('time.month') - clim
    error = float(abs(out.sel(time=slice('1991', '2020')).groupby('time.month').mean('time')).max())
    assert error < 1e-9
    return out, clim, error


def load_land_mask():
    try:
        import eccodes as ec
    except ImportError:
        sys.path.append(str(ROOT / '.venv/lib/python3.12/site-packages'))
        import eccodes as ec
    path = RAW / 'era5_pmm_wind_flux_m01_1982_2024.grib'
    assert sha(path) == json.loads(path.with_suffix('.json').read_text())['sha256']
    masks = []
    with path.open('rb') as stream:
        while (handle := ec.codes_grib_new_from_file(stream)) is not None:
            try:
                if ec.codes_get(handle, 'paramId') != 172:
                    continue
                ni, nj = ec.codes_get(handle, 'Ni'), ec.codes_get(handle, 'Nj')
                values = ec.codes_get_values(handle).reshape(nj, ni)
                lat = ec.codes_get_array(handle, 'latitudes').reshape(nj, ni)[:, 0]
                lon = ec.codes_get_array(handle, 'longitudes').reshape(nj, ni)[0] % 360
                masks.append(values)
            finally:
                ec.codes_release(handle)
    assert len(masks) == 43 and np.max(np.abs(np.stack(masks) - masks[0])) < 1e-6
    return xr.DataArray(masks[0], dims=['lat','lon'], coords=dict(lat=lat,lon=lon)).sortby('lat')


def area_mean(data, weights):
    p = data.sel(lat=slice(BOX['lat_min'], BOX['lat_max']), lon=slice(BOX['lon_min'], BOX['lon_max']))
    w = weights.sel(lat=p.lat, lon=p.lon).fillna(0)
    # Complete fixed ocean mask: never silently lose a grid point at one time.
    assert bool(np.isfinite(p).where(w > 0, True).all())
    return p.weighted(w).mean(('lat', 'lon'))


def detrended_series(series):
    values = np.asarray(series, dtype=float)
    dates = series.index
    t = np.arange(len(values), dtype=float) / 12
    slope = np.sum((t - t.mean()) * (values - values.mean())) / np.sum((t - t.mean()) ** 2)
    ref = (dates.year >= 1991) & (dates.year <= 2020)
    expected = np.array([t[ref & (dates.month == m)].mean() for m in dates.month])
    return values - slope * (t - expected), float(slope)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    protected_before = {name: sha(BASE / name) for name in PROTECTED}
    protocol = dict(events='8 events / 9 development years from frozen 2002-2024 comparison',
        climatology='1991-2020 calendar-month means; 360 complete months',
        region=BOX, map_domain=dict(lat=[0, 30], lon=[190, 260]),
        primary_window='February-June (same months as the existing model starts)',
        extra_windows=list(SEASONS)[1:], field_processing='monthly anomalies; no ENSO removal; no smoothing',
        wind_metric='negative ERA5 wind anomaly projected onto local calendar-month climatological wind unit vector; positive weakens mean trades; NOT scalar wind speed anomaly',
        directional_check='individual u and v anomalies are also saved',
        flux_metric='NCEP-NCAR R1 LHTFL positive UPWARD, negated before forming downward anomalies; W m-2; no 86400 division',
        products='ERA5 10m u/v + NCEP-NCAR R1 latent heat flux + ERSSTv5 SST',
        fallback='CDS remaining ERA5 requests throttled; own pending jobs cancelled; no partial ERA5 flux mixed into monthly series',
        ocean_mask='ERA5 lsm < 0.5; cos(lat)*(1-lsm) for regular wind grid; Gaussian quadrature*(1-lsm) for native flux grid; ERSST native mask',
        sensitivity='remove 1982-2024 linear trend from each regional anomaly, anchored to each 1991-2020 calendar-month mean',
        weighting='average development years within an event, then equal event weights',
        interpretation='descriptive consistency of phases, not a causal WES estimate or heat budget closure',
        existing_forecasts='unchanged; full-period fitted retrospective comparison',
        no_model_refitting=True, region_reference='https://doi.org/10.1029/2024GL108924')
    (OUT / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    print('Loading gridded fields', flush=True)
    with xr.open_dataset(WIND, engine='h5netcdf' if 'h5netcdf' in xr.backends.list_engines() else 'netcdf4') as source:
        wind = normalize(source[['u10', 'v10']]).load()
    with xr.open_dataset(SST, engine='h5netcdf' if 'h5netcdf' in xr.backends.list_engines() else 'netcdf4') as source:
        sst = normalize(source.sst).load()
    assert sha(FLUX) == json.loads(FLUX.with_suffix('.json').read_text())['sha256']
    with xr.open_dataset(FLUX, engine='h5netcdf' if 'h5netcdf' in xr.backends.list_engines() else 'netcdf4') as source:
        assert source.lhtfl.attrs['units'] == 'W/m^2' and source.lhtfl.attrs['GRIB_id'] == 121
        nodes, gaussian_weights = np.polynomial.legendre.leggauss(len(source.lat))
        np.testing.assert_allclose(np.rad2deg(np.arcsin(nodes)), np.sort(source.lat.values), atol=1e-4)
        latitude_weights = xr.DataArray(gaussian_weights, dims='lat', coords=dict(lat=np.sort(source.lat.values)))
        flux = normalize(-source.lhtfl.astype(float)).load()
    np.testing.assert_array_equal(wind.time, flux.time)
    lsm = load_land_mask()
    ocean = lsm < .5
    weights = (np.cos(np.deg2rad(wind.lat)) * (1 - lsm)).where(ocean, 0)
    flux_lsm = lsm.interp(lat=flux.lat, lon=flux.lon, method='nearest')
    flux_ocean = flux_lsm < .5
    flux_weights = (latitude_weights.sel(lat=flux.lat) * (1-flux_lsm)).where(flux_ocean, 0)
    sst_ocean = np.isfinite(sst).all('time')
    sst_weights = np.cos(np.deg2rad(sst.lat.astype(float))) * sst_ocean
    fields, clims, clim_errors = {}, {}, {}
    for name, data in dict(u10=wind.u10, v10=wind.v10, latent_down=flux, sst=sst).items():
        fields[name], clims[name], clim_errors[name] = anomaly(data.astype(float))
    magnitude = np.hypot(clims['u10'], clims['v10'])
    aligned = -(fields['u10'] * clims['u10'].sel(month=wind.time.dt.month)
                + fields['v10'] * clims['v10'].sel(month=wind.time.dt.month)) / magnitude.sel(month=wind.time.dt.month)
    min_reference_wind = float(magnitude.where(ocean).sel(lat=slice(10, 30), lon=slice(205, 245)).min())
    assert min_reference_wind > 1e-6, 'Undefined climatological direction at an ocean grid point'
    table = pd.DataFrame(index=pd.DatetimeIndex(wind.time.values, name='time'))
    mapping = dict(sst_anomaly_c=(fields['sst'], sst_weights), wind_weakening_ms=(aligned, weights),
        along_trade_weakening_ms=(aligned, weights), latent_down_anomaly_wm2=(fields['latent_down'], flux_weights),
        u10_anomaly_ms=(fields['u10'], weights), v10_anomaly_ms=(fields['v10'], weights),
        latent_down_wm2=(flux, flux_weights))
    for name, (data, weight) in mapping.items():
        table[name] = area_mean(data, weight).values
    table['latent_loss_up_anomaly_wm2'] = -table.latent_down_anomaly_wm2
    pmm_source = pd.read_csv(ROOT / 'data/raw/climate_indices/standard_pmm_20261014/PMM_uw.txt', sep=r'\s+')
    pmm_source.index = pd.to_datetime(dict(year=pmm_source.Year, month=pmm_source.Mo, day=1))
    table['pmm'] = pmm_source.SST.reindex(table.index)
    trends = {}
    for name in SERIES:
        if name != 'pmm':
            table[f'{name}_detrended'], trends[name] = detrended_series(table[name])
    assert len(table) == 516 and np.isfinite(table.to_numpy()).all()
    assert table.latent_down_wm2.mean() < 0
    table.to_csv(OUT / 'monthly_regional_evidence_1982_2024.csv', float_format='%.10g')
    curves = pd.read_csv(BASE / 'pmm_comparison/monthly_event_PMM.csv', parse_dates=['time'])
    original_pmm = curves.pmm.copy()
    curves = curves.drop(columns='pmm').merge(table.reset_index(), on='time', how='left', validate='many_to_one')
    np.testing.assert_allclose(curves.pmm, original_pmm, atol=1e-12)
    assert len(curves) == 135 and curves[SERIES].notna().all().all()
    curves.to_csv(OUT / 'event_monthly_evidence.csv', index=False, float_format='%.10g')
    initials = curves[curves.is_initialization]
    assert len(initials) == 45
    initials.to_csv(OUT / 'initialization_evidence_45.csv', index=False, float_format='%.10g')
    cols = SERIES + [f'{name}_detrended' for name in SERIES if name != 'pmm']
    rows = []
    for (event, strength, year), group in curves.groupby(['event', 'strength', 'development_year']):
        for season, months in SEASONS.items():
            part = group[group.relative_month.isin(months)]
            assert len(part) == len(months)
            row = dict(event=event, strength=strength, development_year=year, season=season, n_months=len(part))
            row.update(part[cols].mean().to_dict())
            rows.append(row)
    seasonal = pd.DataFrame(rows)
    skill = pd.read_csv(BASE / 'development_year_summary.csv')
    seasonal = seasonal.merge(skill[['development_year', 'rmse_change_percent']], on='development_year', validate='many_to_one')
    seasonal['wind_same_sign_as_pmm'] = seasonal.pmm * seasonal.wind_weakening_ms > 0
    seasonal['flux_same_sign_as_pmm'] = seasonal.pmm * seasonal.latent_down_anomaly_wm2 > 0
    seasonal['both_same_sign_as_pmm'] = seasonal.wind_same_sign_as_pmm & seasonal.flux_same_sign_as_pmm
    seasonal['both_same_sign_detrended'] = (seasonal.pmm * seasonal.wind_weakening_ms_detrended > 0) & (seasonal.pmm * seasonal.latent_down_anomaly_wm2_detrended > 0)
    seasonal.to_csv(OUT / 'development_year_seasonal_evidence.csv', index=False, float_format='%.10g')
    event = seasonal.groupby(['event', 'strength', 'season'], as_index=False)[cols].mean()
    event.to_csv(OUT / 'event_equal_weight_seasonal_evidence.csv', index=False, float_format='%.10g')
    groups = event.groupby(['strength', 'season'], as_index=False)[cols].mean()
    counts = event.groupby(['strength', 'season']).size().rename('n_events').reset_index()
    groups = groups.merge(counts, on=['strength', 'season'])
    groups.to_csv(OUT / 'group_equal_weight_seasonal_evidence.csv', index=False, float_format='%.10g')
    saved_fields = xr.Dataset({
        'u10_anomaly_ms': fields['u10'].where(ocean).drop_vars('month'),
        'v10_anomaly_ms': fields['v10'].where(ocean).drop_vars('month'),
        'wind_weakening_ms': aligned.where(ocean).drop_vars('month'),
        'latent_down_anomaly_wm2': fields['latent_down'].where(flux_ocean).drop_vars('month').rename(lat='flux_lat',lon='flux_lon'),
        'ocean_fraction': (1 - lsm).where(ocean, 0),
        'flux_ocean_fraction': (1-flux_lsm).where(flux_ocean,0).rename(lat='flux_lat',lon='flux_lon'),
        'flux_lat_area_weight': latitude_weights.sel(lat=flux.lat).rename(lat='flux_lat'),
        'sst_anomaly_c': fields['sst'].drop_vars('month').rename(lat='sst_lat', lon='sst_lon')})
    saved_fields.attrs.update(climatology='1991-2020', flux_positive='downward after negating NCEP LHTFL',
        sources='ERA5 wind; NCEP-NCAR R1 flux; ERSSTv5 SST',wind_metric='negative along-climatological-wind anomaly projection',no_model_refitting='true')
    saved_fields.to_netcdf(OUT / 'spatial_evidence.nc', engine='scipy')
    for name in PROTECTED:
        assert protected_before[name] == sha(BASE / name)
    qa = dict(n_events=curves.event.nunique(), n_development_years=curves.development_year.nunique(),
        n_monthly_event_rows=len(curves), n_initializations=len(initials), n_complete_source_months=len(table),
        mixed_products_explicitly_labeled=True, wind_metric_is_projection_not_scalar_speed=True,
        minimum_ocean_climatological_vector_speed_ms=min_reference_wind,
        native_flux_grid_gaussian_weights=True, climatology_max_errors=clim_errors,
        mean_ocean_latent_down_flux_wm2=float(table.latent_down_wm2.mean()),
        no_missing_regional_values=True, no_silent_event_exclusion=True,
        monthly_anomaly_not_enso_removed=True, original_models_forecasts_scores_unchanged=True,
        protected_sha256=protected_before, linear_trends_per_year=trends)
    (OUT / 'QA.json').write_text(json.dumps(qa, indent=2))
    paths = [WIND, SST, FLUX, FLUX.with_suffix('.json'), BASE / 'event_catalog.csv', BASE / 'development_year_summary.csv',
        BASE / 'pmm_comparison/monthly_event_PMM.csv', Path(__file__).resolve()]
    paths += [RAW/'era5_pmm_wind_flux_m01_1982_2024.grib',RAW/'era5_pmm_wind_flux_m01_1982_2024.json']
    (OUT / 'source_manifest.json').write_text(json.dumps(dict(sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
        era5_dataset='https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means',
        latent_flux_dataset='https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface_gauss/lhtfl.sfc.mon.mean.nc.html'), indent=2))
    print(seasonal[seasonal.season.eq('Feb_Jun')][['development_year','pmm','sst_anomaly_c','wind_weakening_ms','latent_down_anomaly_wm2','both_same_sign_as_pmm','both_same_sign_detrended','rmse_change_percent']].to_string(index=False), flush=True)
    print(OUT, flush=True)


if __name__ == '__main__':
    run()
