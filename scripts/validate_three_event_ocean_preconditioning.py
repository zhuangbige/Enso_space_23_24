"""Numerical and delivery checks for the new three-event diagnostics."""
import argparse
import hashlib
import json
import platform
import importlib.metadata
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from PIL import Image
from analyze_three_event_ocean_preconditioning import OUT, ROOT, EVENTS, CASE_YEARS, REGIONS, BASE


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument('--source-geometry',action='store_true')
    args=arg.parse_args()
    checks={}
    checks['runtime']={'python':platform.python_version(),**{p:importlib.metadata.version(p) for p in ['numpy','pandas','xarray','gsw','scipy','matplotlib','h5netcdf']}}
    raw=pd.read_csv(OUT/'ocean_monthly_absolute.csv',parse_dates=['time'])
    an=pd.read_csv(OUT/'ocean_monthly_anomalies.csv',parse_dates=['time'])
    atm=pd.read_csv(OUT/'atmosphere_anomaly_and_reference.csv',parse_dates=['time'])
    for name,f in [('ocean',raw),('atmosphere',atm)]:
        expected=pd.date_range('1982-01-01','2024-12-01',freq='MS')+pd.Timedelta(days=14)
        np.testing.assert_array_equal(f.time.to_numpy(),expected.to_numpy())
        assert len(f)==516 and not f.time.duplicated().any()
        checks[name+'_calendar_complete']=True
    scale=raw.drop(columns='time').abs().max().replace(0,1)
    baseline=an.loc[an.time.dt.year.between(*BASE)].groupby(an.time.dt.month).mean(numeric_only=True)
    error=float((baseline.abs().max()/scale).max())
    assert error<1e-12
    checks['monthly_climatology_relative_zero_error']=error
    volume_error=abs(raw[[r+'_wwv_m3' for r in REGIONS]].sum(axis=1)-raw.basin_wwv_m3)
    assert np.max(volume_error/raw.basin_wwv_m3)<1e-12
    checks['three_regions_equal_basin']=True
    internal_sum=(raw.u120_q_sv-raw.u180_q_sv)+(raw.u180_q_sv-raw.u220_q_sv)+(raw.u220_q_sv-raw.u280_q_sv)
    np.testing.assert_allclose(internal_sum,raw.u120_q_sv-raw.u280_q_sv,atol=1e-12)
    checks['internal_zonal_gates_cancel']=True
    # An independent dimensional reference: 1 Sv sustained for 365 days.
    v=1e6*365*86400/1e14
    assert np.isclose(v,.31536)
    checks['one_Sv_year_1e14m3']=v
    wqa=json.loads((OUT/'wind_reference_QA.json').read_text())
    assert not set(wqa['reference_years'])&set(CASE_YEARS)
    assert len(wqa['reference_years'])==34
    checks['reference_excludes_target_years']=True
    with xr.open_dataset(OUT/'ocean_case_fields.nc',engine='scipy') as ds:
        assert ds.sizes['time']==72
        assert set(ds.time.dt.year.values)==set(CASE_YEARS)
        assert float(ds.depth.min())>0 and np.all(np.diff(ds.depth)>0)
        checks['case_fields_72_months']=True
    budget=pd.read_csv(OUT/'cumulative_volume_budget.csv')
    assert len(budget)==882
    e=np.max(abs(budget.storage_change-budget.zonal_input-budget.meridional_input-budget.unresolved))
    assert e<1e-10
    checks['accounting_identity_not_physical_closure_error']=float(e)
    heat=pd.read_csv(OUT/'two_term_heat_transport.csv')
    assert len(heat)==1440
    active=heat.active_area_m2>0
    assert heat.loc[active,'area_coverage'].between(0,1+1e-12).all()
    assert heat.loc[:,['mean_flow_temperature_anomaly_pw','anomalous_flow_mean_temperature_pw']].notna().all().all()
    checks['minimum_active_heat_section_coverage']=float(heat.loc[active,'area_coverage'].min())
    if args.source_geometry:
        import analyze_chen2015_reanalysis as g
        a=g.load_inputs(1996)
        for latitude,label in [(-9,'south'),(9,'north')]:
            direct=g.integrate_gate(g.section(a,'v',latitude,120,280),a['depth'],a['layer_bottom'])[0]
            split=sum(g.integrate_gate(g.section(a,'v',latitude,lo,hi),a['depth'],a['layer_bottom'])[0] for lo,hi in REGIONS.values())
            err=float(np.max(abs(direct-split)));assert err<1e-10
            checks[label+'_independent_split_gate_error_Sv']=err
        z=np.array([[123.4,230.6,0.]])
        np.testing.assert_allclose(g.weights(z,np.array([10.,30.,80.,150.,300.])).sum(axis=1),z,atol=1e-12)
        checks['analytic_partial_layer_check']=True
        iy=np.array([np.argmin(abs(a['lat_t']-x)) for x in [-7,-3,0,3,7]])
        ix=np.array([np.argmin(abs(a['lon_t']-x)) for x in [145,170,190,230,265]])
        temp=a['temp'][:1,:,iy[:,None],ix]
        salt=a['salt'][:1,:,iy[:,None],ix]
        density=g.sigma(temp,salt,a['depth'],a['lat_t'][iy],a['lon_t'][ix])
        recomputed,_,_=g.d26(density,a['depth'],a['layer_bottom'])
        cache=np.load(g.OUT/'d26_1996.npz')['d26'][:1,iy[:,None],ix]
        difference=float(np.nanmax(abs(recomputed-cache)))
        assert difference<1e-3
        checks['cached_density_depth_vs_current_runtime_max_difference_m']=difference
    elif (OUT/'independent_geometry_QA.json').exists():
        checks['independent_geometry']=json.loads((OUT/'independent_geometry_QA.json').read_text())
    html=(OUT/'论文结果初稿_海洋预置与海气响应.html').read_text()
    figures=sorted(OUT.glob('Fig*.png'))
    assert len(figures)==6
    for p in figures:
        with Image.open(p) as image:
            image.verify()
        assert p.name in html
        assert p.with_suffix('.pdf').stat().st_size>1000
        assert p.with_suffix('.svg').stat().st_size>1000
    checks['six_figure_assets_and_html_links']=True
    checks['new_dynamical_model_run']=False
    (OUT/'validation_results.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    paths=list(OUT.glob('*'))+[ROOT/'scripts'/p for p in ['analyze_three_event_ocean_preconditioning.py','plot_report_three_event_ocean_preconditioning.py','validate_three_event_ocean_preconditioning.py']]
    manifest=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths if p.is_file() and p.name!='delivery_manifest.json']
    (OUT/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2))


if __name__=='__main__':main()
