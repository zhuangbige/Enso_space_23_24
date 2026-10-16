"""Recompute delivered numbers independently from saved spatial/monthly files."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import xarray as xr

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/research_2026/enso_strength_screenshot_D20_2002_2024_20261015'
OUT=BASE/'pmm_wind_flux_evidence'


def main():
    table=pd.read_csv(OUT/'monthly_regional_evidence_1982_2024.csv',parse_dates=['time']).set_index('time')
    monthly=pd.read_csv(OUT/'event_monthly_evidence.csv',parse_dates=['time'])
    seasonal=pd.read_csv(OUT/'development_year_seasonal_evidence.csv')
    event=pd.read_csv(OUT/'event_equal_weight_seasonal_evidence.csv')
    grouped=pd.read_csv(OUT/'group_equal_weight_seasonal_evidence.csv')
    max_area_error=0.
    with xr.open_dataset(OUT/'spatial_evidence.nc',engine='scipy') as ds:
        subset=ds.sel(lat=slice(10,30),lon=slice(205,245))
        weights=np.cos(np.deg2rad(subset.lat.values))[:,None]*subset.ocean_fraction.values
        for column in ['wind_weakening_ms','u10_anomaly_ms','v10_anomaly_ms']:
            values=subset[column].values
            independent=np.nansum(values*weights[None,:,:],axis=(1,2))/weights.sum()
            error=float(np.max(np.abs(independent-table[column].values)))
            max_area_error=max(max_area_error,error)
            assert error<1e-7,(column,error)
        flux=ds.sel(flux_lat=slice(10,30),flux_lon=slice(205,245))
        flux_weights=flux.flux_lat_area_weight.values[:,None]*flux.flux_ocean_fraction.values
        independent=np.nansum(flux.latent_down_anomaly_wm2.values*flux_weights[None,:,:],axis=(1,2))/flux_weights.sum()
        error=float(np.max(abs(independent-table.latent_down_anomaly_wm2.values)))
        max_area_error=max(max_area_error,error)
        assert error<1e-7
        p=ds.sst_anomaly_c.sel(sst_lat=slice(10,30),sst_lon=slice(205,245))
        weights=np.cos(np.deg2rad(p.sst_lat.values.astype(float)))[:,None]*np.isfinite(p.values).all(axis=0)
        independent=np.nansum(p.values*weights[None,:,:],axis=(1,2))/weights.sum()
        error=float(np.max(abs(independent-table.sst_anomaly_c.values)))
        max_area_error=max(max_area_error,error)
        assert error<1e-7
    windows={'Feb_Jun':[2,3,4,5,6],'MAM':[3,4,5],'JJA':[6,7,8],'SON':[9,10,11],'DJF':[12,13,14]}
    metrics=['pmm','sst_anomaly_c','wind_weakening_ms','latent_down_anomaly_wm2']
    max_seasonal_error=0.
    for row in seasonal.itertuples(index=False):
        part=monthly[(monthly.development_year==row.development_year)&monthly.relative_month.isin(windows[row.season])]
        assert len(part)==len(windows[row.season])
        for col in metrics:
            error=abs(float(part[col].sum()/len(part))-getattr(row,col))
            max_seasonal_error=max(max_seasonal_error,error)
            assert error<1e-7
    max_weight_error=0.
    for row in grouped.itertuples(index=False):
        part=seasonal[(seasonal.strength==row.strength)&(seasonal.season==row.season)]
        episodes=sorted(part.event.unique())
        assert len(episodes)==row.n_events
        for col in metrics:
            expected=sum(part[part.event==e][col].sum()/len(part[part.event==e]) for e in episodes)/len(episodes)
            error=abs(expected-getattr(row,col));max_weight_error=max(max_weight_error,error)
            assert error<1e-7
    assert len(monthly)==135 and monthly.event.nunique()==8 and monthly.development_year.nunique()==9
    assert len(monthly[monthly.is_initialization])==45
    assert len(seasonal)==45 and len(event)==40 and len(grouped)==15
    assert np.max(abs(table.latent_loss_up_anomaly_wm2+table.latent_down_anomaly_wm2))<1e-10
    for column in table.columns:
        if column.endswith('_detrended'):
            baseline=table.loc['1991':'2020',column]
            assert baseline.groupby(baseline.index.month).mean().abs().max()<1e-7
    skill=pd.read_csv(BASE/'development_year_summary.csv').set_index('development_year')
    for row in seasonal.itertuples(index=False):
        assert abs(row.rmse_change_percent-skill.loc[row.development_year,'rmse_change_percent'])<1e-7
        assert row.both_same_sign_as_pmm == ((row.pmm*row.wind_weakening_ms>0) and (row.pmm*row.latent_down_anomaly_wm2>0))
    qa=json.loads((OUT/'QA.json').read_text())
    for filename,digest in qa['protected_sha256'].items():
        assert hashlib.sha256((BASE/filename).read_bytes()).hexdigest()==digest
    report=dict(status='passed',area_mean_recomputation_max_error=max_area_error,
        seasonal_recomputation_max_error=max_seasonal_error,event_weight_recomputation_max_error=max_weight_error,
        sign_convention_verified=True,complete_8_events=True,all_45_initializations_present=True,
        detrended_climatology_zero=True,original_model_forecasts_scores_unchanged=True)
    (OUT/'independent_QA.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
