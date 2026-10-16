#!/usr/bin/env python3
"""Two-term heat-transport diagnostic on the Maryland 5N eastern-Pacific gate.

Only mean-v * theta' and v' * mean-theta are retained. The primary diagnostic
uses each calendar month's climatological sigma0=26 section, so its background
transport is fixed between years. Instantaneous-section integrals of the same
two terms are reported separately as a geometry sensitivity. No full heat or
WWV budget is claimed, and no background or nonlinear term is added to the sum.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import xarray as xr
import gsw

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/chen2015_linear_transport_20261014'
OUT = ROOT / 'outputs/research_2026/chen2015_linear_transport_20261014'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/chen2015_linear_mpl'))
RHO = 1025.0
CP = 3990.0
R_EARTH = 6371000.0
LAT = 5.0
THRESHOLD = 26.0
FILES = ['soda3_5n_geostrophic_sections_1980_2022.nc',
         'soda3_5n_geostrophic_section_2024_jan_may.nc']
QA: dict = {}


def density(ds: xr.Dataset, eos: str = 'TEOS10') -> np.ndarray:
    theta = ds.temp.values.astype('float64')
    salt = ds.salt.values.astype('float64')
    if eos == 'EOS80':
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            import seawater
        return seawater.dens0(salt, theta) - 1000.0
    p = gsw.p_from_z(-ds.depth.values[None, :, None], LAT)
    sa = gsw.SA_from_SP(salt, p, ds.lon.values[None, None, :], LAT)
    ct = gsw.CT_from_pt(sa, theta)
    return gsw.sigma0(sa, ct)


def interface(sigma: np.ndarray, depth: np.ndarray) -> tuple[np.ndarray, dict]:
    crossing = (sigma[:, :-1] < THRESHOLD) & (sigma[:, 1:] >= THRESHOLD)
    found = crossing.any(axis=1)
    idx = crossing.argmax(axis=1)
    a = np.take_along_axis(sigma, idx[:, None], axis=1)[:, 0]
    b = np.take_along_axis(sigma, idx[:, None] + 1, axis=1)[:, 0]
    with np.errstate(divide='ignore', invalid='ignore'):
        z = depth[idx] + (THRESHOLD - a) / (b - a) * (depth[idx + 1] - depth[idx])
    surfaced = np.isfinite(sigma[:, 0]) & (sigma[:, 0] >= THRESHOLD)
    z = np.where(surfaced, 0.0, np.where(found, z, np.nan))
    wet = np.isfinite(sigma[:, 0])
    stats = {'profiles': int(wet.sum()), 'unresolved': int((wet & ~found & ~surfaced).sum()),
             'multiple_crossings': int((crossing.sum(axis=1) > 1).sum()),
             'd26_min_m': float(np.nanmin(z)), 'd26_max_m': float(np.nanmax(z))}
    if stats['unresolved']:
        raise ValueError(f'Unresolved density interface: {stats}')
    return z, stats


def area_weights(z: np.ndarray, depth: np.ndarray, lon: np.ndarray) -> np.ndarray:
    bounds = np.r_[0.0, (depth[:-1] + depth[1:]) / 2,
                   depth[-1] + (depth[-1] - depth[-2]) / 2]
    if not np.all(np.diff(bounds) > 0):
        raise ValueError('Non-increasing depth bounds')
    dz = np.maximum(0, np.minimum(bounds[1:][None, :, None], z[:, None])
                    - bounds[:-1][None, :, None])
    spacing = np.diff(lon)
    if not np.allclose(spacing, .5):
        raise ValueError('Unexpected longitude grid')
    dx = R_EARTH * np.cos(np.deg2rad(LAT)) * np.deg2rad(.5)
    weights = dz * dx
    if not np.allclose(weights.sum(axis=1), z * dx, rtol=1e-12, atol=1e-6):
        raise AssertionError('Partial-cell thickness does not sum to D26')
    return weights


def climatology(hist: xr.Dataset, start: int, end: int) -> xr.Dataset:
    selected = hist.sel(time=slice(f'{start}-01-01', f'{end}-12-31'))
    n = selected.time.dt.year.groupby(selected.time.dt.month).count().values
    if not np.all(n == end - start + 1):
        raise ValueError('Incomplete calendar-month baseline')
    out = selected.groupby('time.month').mean('time').rename(month='time')
    return out


def compute(ds: xr.Dataset, clim: xr.Dataset, eos: str, baseline: str):
    months = ds.time.dt.month.values
    mean = clim.sel(time=months)
    mean = mean.assign_coords(time=ds.time)
    tbar = mean.temp.values
    vbar = mean.v.values
    tp = ds.temp.values - tbar
    vp = ds.v.values - vbar
    tterm = vbar * tp
    vterm = vp * tbar
    zmean, qmean = interface(density(mean, eos), ds.depth.values)
    zactual, qactual = interface(density(ds, eos), ds.depth.values)
    QA[f'{baseline}_{eos}_interfaces'] = {'climatological': qmean, 'instantaneous': qactual}
    frames = []
    fields = None
    for geometry, z in [('climatological_sigma26', zmean), ('instantaneous_sigma26', zactual)]:
        weights = area_weights(z, ds.depth.values, ds.lon.values)
        valid = np.isfinite(ds.temp.values) & np.isfinite(ds.salt.values) & np.isfinite(ds.v.values)
        if np.any((weights > 0) & ~valid):
            raise ValueError('Missing data inside active section')
        fp1 = (tterm * weights).sum(axis=(1, 2)) * RHO * CP / 1e15
        fp2 = (vterm * weights).sum(axis=(1, 2)) * RHO * CP / 1e15
        total = ((tterm + vterm) * weights).sum(axis=(1, 2)) * RHO * CP / 1e15
        error = float(np.max(np.abs(total - fp1 - fp2)))
        if error > 1e-12:
            raise AssertionError('Two-term sum fails')
        QA[f'{baseline}_{eos}_{geometry}_sum_error_pw'] = error
        df = pd.DataFrame({'time': pd.to_datetime(ds.time.values), 'baseline': baseline,
                           'eos': eos, 'geometry': geometry,
                           'vbar_Tprime_pw': fp1, 'vprime_Tbar_pw': fp2,
                           'linear_sum_pw': total,
                           'vprime_volume_sv': (vp * weights).sum(axis=(1, 2)) / 1e6,
                           'section_area_m2': weights.sum(axis=(1, 2)),
                           'mean_d26_m': z.mean(axis=1),
                           'minimum_d26_m': z.min(axis=1), 'maximum_d26_m': z.max(axis=1)})
        frames.append(df)
        if geometry == 'climatological_sigma26':
            fields = xr.Dataset({
                'vbar_Tprime_heat_flux_density': (('time', 'depth', 'lon'), tterm * RHO * CP),
                'vprime_Tbar_heat_flux_density': (('time', 'depth', 'lon'), vterm * RHO * CP),
                'climatological_active_area': (('time', 'depth', 'lon'), weights),
                'd26_climatology': (('time', 'lon'), zmean),
                'd26_actual': (('time', 'lon'), zactual),
            }, coords={'time': ds.time, 'depth': ds.depth, 'lon': ds.lon})
    return pd.concat(frames, ignore_index=True), fields


def integrate(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (baseline, eos, geometry), group in df.groupby(['baseline', 'eos', 'geometry']):
        for onset in [1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023]:
            yr = onset + 1
            event = group.loc[group.time.dt.year.eq(yr) & group.time.dt.month.between(1, 5)].sort_values('time')
            if event.shape[0] != 5:
                raise ValueError(f'Missing Jan-May {yr}')
            seconds = (event.time - event.time.iloc[0]).dt.total_seconds().to_numpy()
            row = {'onset_year': onset, 'verification_year': yr, 'baseline': baseline,
                   'eos': eos, 'geometry': geometry, 'n_months': 5,
                   'window_start': str(event.time.iloc[0].date()),
                   'window_end': str(event.time.iloc[-1].date()),
                   'elapsed_days': float(seconds[-1] / 86400)}
            for col in ['vbar_Tprime_pw', 'vprime_Tbar_pw', 'linear_sum_pw']:
                row[col.replace('_pw', '_zj')] = float(np.trapezoid(event[col], seconds) / 1e6)
                row[col.replace('_pw', '_mean_pw')] = float(np.trapezoid(event[col], seconds) / seconds[-1])
                row[col.replace('_pw', '_calendar_months_zj')] = float(
                    (event[col] * event.time.dt.days_in_month * 86400).sum() / 1e6)
            rows.append(row)
    return pd.DataFrame(rows)


def checks(hist: xr.Dataset, clim: xr.Dataset):
    zero, _ = compute(clim.assign_coords(time=pd.to_datetime([f'2000-{m:02d}-15' for m in clim.time.values])),
                      clim, 'TEOS10', 'climatology_identity_check')
    err = float(zero[['vbar_Tprime_pw', 'vprime_Tbar_pw']].abs().to_numpy().max())
    if err > 1e-12:
        raise AssertionError('Climatology must produce zero anomalies')
    QA['climatology_identity_max_pw'] = err


def main():
    paths = [RAW / f for f in FILES]
    hist = xr.open_dataset(paths[0]).load().astype('float64')
    extension = xr.open_dataset(paths[1]).load().astype('float64')
    for dim in ['depth', 'lon']:
        np.testing.assert_allclose(hist[dim], extension[dim], rtol=0, atol=1e-8)
        QA[f'{dim}_coordinate_roundoff_max'] = float(np.max(np.abs(hist[dim].values - extension[dim].values)))
        extension = extension.assign_coords({dim: hist[dim]})
    all_data = xr.concat([hist, extension], dim='time').sortby('time')
    if not all_data.indexes['time'].is_unique:
        raise ValueError('Duplicate source dates')
    for var in ['temp', 'salt', 'v']:
        if not np.isfinite(all_data[var].values).all():
            raise ValueError(f'Missing section data: {var}')
    QA['source_ranges'] = {v: [float(all_data[v].min()), float(all_data[v].max())]
                           for v in ['temp', 'salt', 'v']}
    QA['files'] = [{'name': p.name, 'bytes': p.stat().st_size,
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    clim = climatology(hist, 1980, 2022)
    checks(hist, clim)
    main_df, fields = compute(all_data, clim, 'TEOS10', '1980-2022')
    alternative, _ = compute(all_data, clim, 'EOS80', '1980-2022')
    past_clim = climatology(hist, 1980, 2014)
    past, _ = compute(all_data, past_clim, 'TEOS10', '1980-2014')
    monthly = pd.concat([main_df, alternative, past], ignore_index=True)
    summary = integrate(monthly)
    main_df.to_csv(OUT / 'two_term_monthly_main.csv', index=False)
    monthly.to_csv(OUT / 'two_term_monthly_with_sensitivity.csv', index=False)
    summary.to_csv(OUT / 'event_JanMay_integrals.csv', index=False)
    highlighted = summary.loc[summary.onset_year.isin([2015, 2023])]
    highlighted.to_csv(OUT / '2015_2023_JanMay_summary.csv', index=False)
    primary = main_df.loc[main_df.geometry.eq('climatological_sigma26')]
    baseline_mean = primary.loc[primary.time.dt.year.between(1980, 2022)].groupby(primary.time.dt.month)[
        ['vbar_Tprime_pw', 'vprime_Tbar_pw']].mean()
    QA['climatology_mean_max_pw'] = float(np.abs(baseline_mean.to_numpy()).max())
    if QA['climatology_mean_max_pw'] > 1e-6:
        raise AssertionError('Monthly transport anomaly does not have zero baseline mean')
    fields = fields.sel(time=fields.time.dt.year.isin([2016, 2024]) &
                        (fields.time.dt.month >= 1) & (fields.time.dt.month <= 5))
    fields.attrs.update({'latitude_degrees_north': LAT,
        'longitude_bounds_degrees_east': '220,280', 'density_boundary': 'sigma0=26 kg m-3',
        'baseline': '1980-2022 calendar-month climatology; no detrend or bandpass',
        'method': 'two retained linear terms only; primary fixed monthly climatological sigma26 section',
        'theta_reference_degC': 0.0, 'rho0_kg_m3': RHO, 'cp_j_kg_k': CP,
        'sign': 'positive northward; negative is southward anomaly',
        'scope': '5N eastern-Pacific regional extension, not the original Chen 2015 +/-9N STC geometry'})
    for name in ['vbar_Tprime_heat_flux_density', 'vprime_Tbar_heat_flux_density']:
        fields[name].attrs['units'] = 'W m-2'
    fields.climatological_active_area.attrs['units'] = 'm2'
    fields.d26_climatology.attrs['units'] = 'm'
    fields.d26_actual.attrs['units'] = 'm'
    fields.to_netcdf(OUT / 'retained_terms_2016_2024_sections.nc')
    (OUT / 'numerical_QA.json').write_text(json.dumps(QA, ensure_ascii=False, indent=2) + '\n')
    print(highlighted[['onset_year', 'baseline', 'eos', 'geometry',
                       'vbar_Tprime_zj', 'vprime_Tbar_zj', 'linear_sum_zj']].to_string(index=False))


if __name__ == '__main__':
    main()
