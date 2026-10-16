"""Independent algebra, exclusion, data-consistency, and delivery checks."""
import json
import hashlib
import importlib.metadata
import platform
from pathlib import Path
import numpy as np
import pandas as pd
import experiment_three_event_initial_states as e


def main():
    qa={'runtime':{'python':platform.python_version(),**{p:importlib.metadata.version(p) for p in ['numpy','pandas','matplotlib','scikit-learn']}}}
    frame=e.prepare();dates=frame.index
    np.testing.assert_array_equal(dates,pd.date_range('1982-01-01','2024-12-01',freq='MS')+pd.Timedelta(days=14))
    assert np.isfinite(frame.to_numpy()).all()
    np.testing.assert_allclose(frame[e.VOLUME].sum(axis=1),frame.basin_wwv,atol=1e-10)
    qa['516_months_finite_and_volume_consistent']=True
    models=json.loads((e.OUT/'fitted_models.json').read_text());m=models[e.PRIMARY+'_mean']
    for k in ['matrix','intercept','background','scale','coefficients']:m[k]=np.array(m[k])
    weights=(~np.isin(dates.year,list(e.EXCLUDED))).astype(float)
    raw=frame[m['columns']].to_numpy()
    # Perturb excluded observations by a huge amount: fitted parameters must not change.
    altered=raw.copy();altered[weights==0]+=1000
    changed=e.fit(altered,dates,weights,m['ridge'],False)
    for k in ['matrix','intercept','background','scale']:
        np.testing.assert_allclose(changed[k],m[k],atol=1e-11,rtol=1e-11)
    qa['target_values_cannot_change_fitted_parameters']=True
    wind=e.wind_closure(frame)
    changed_frame=frame.copy();changed_frame.loc[weights==0,['nino34','pattern','tau']]+=1000
    np.testing.assert_allclose(e.wind_closure(changed_frame),wind,atol=1e-12)
    qa['target_values_cannot_change_wind_closure']=True
    pairs=np.array(m['training_pair_indices'])
    assert not set(dates.year[pairs])&e.EXCLUDED
    assert not set(dates.year[pairs+1])&e.EXCLUDED
    qa['both_transition_endpoints_excluded']=True
    for _,w,starts,valid in e.folds(dates):
        used=set(dates.year[w>0])
        assert not used&set(valid)
        for y in valid:assert not used&{y-1,y,y+1}
    qa['cross_validation_calendar_guards']=True
    # Synthetic known scalar solution with a nonzero affine intercept and background.
    ds=pd.date_range('2000-01-01',periods=12,freq='MS')+pd.Timedelta(days=14)
    synthetic={'matrix':np.full((12,1,1),.8),'intercept':np.full((12,1),.1),
               'scale':np.array([2.]),'background':np.zeros((12,2,1))}
    predicted=e.forecast(synthetic,np.array([3.]),ds)[:,0]
    truth=2*(.5+(1.5-.5)*.8**np.arange(12))
    np.testing.assert_allclose(predicted,truth,atol=1e-12)
    qa['forecast_matches_independent_affine_solution']=True
    # Exact matrix propagation independently verifies every initial-condition effect.
    x=frame.loc[pd.Timestamp(2023,1,15),m['columns']].to_numpy()
    ds=pd.date_range('2023-01-01',periods=12,freq='MS')+pd.Timedelta(days=14)
    base=e.forecast(m,x,ds)
    kernel=e.initial_response(m)
    err=0.
    for j in range(len(x)):
        xx=x.copy();xx[j]+=.1
        finite=(e.forecast(m,xx,ds)[:,0]-base[:,0])/.1
        err=max(err,float(np.max(abs(finite-kernel[:,j]))))
    assert err<1e-10;qa['initial_response_kernel_vs_finite_difference_error']=err
    tr=pd.read_csv(e.OUT/'initial_swap_trajectories.csv')
    main=tr.loc[tr.model.eq(e.PRIMARY)&~tr.detrend&tr.swap.eq('direct')]
    assert len(main)==108
    assert np.isfinite(main.nino34_predicted).all()
    assert ((main.month==1).sum()==9)
    jan=main.loc[main.month==1]
    np.testing.assert_allclose(jan.nino34_predicted,jan.nino34_observed,atol=1e-12)
    # Three direct ocean columns have identical pairwise differences across SST rows.
    arr=main.pivot(index=['sst_year','month'],columns='ocean_year',values='nino34_predicted')
    d=arr[1997]-arr[2023]
    np.testing.assert_allclose(d.loc[1997],d.loc[2015],atol=1e-11)
    np.testing.assert_allclose(d.loc[1997],d.loc[2023],atol=1e-11)
    qa['linear_swap_effects_are_additive_not_independent_interactions']=True
    control=tr.loc[tr.model.eq('sst_only')&~tr.detrend&tr.swap.eq('direct')]
    assert control.groupby(['sst_year','month']).nino34_predicted.std().max()<1e-12
    qa['no_ocean_control_invariant_to_donor']=True
    dec=pd.read_csv(e.OUT/'within_model_initial_state_decomposition.csv')
    np.testing.assert_allclose(dec.iloc[:,2:5].sum(axis=1),dec.all_ocean,atol=1e-12)
    effects=pd.read_csv(e.OUT/'swap_seasonal_effects.csv')
    effects=effects.loc[effects.model.eq(e.PRIMARY)&~effects.detrend&effects.swap.eq('direct')]
    comp=dec.merge(effects,on=['sst_year','ocean_year'])
    np.testing.assert_allclose(comp.all_ocean,comp.nino34_OND_C_change_from_native,atol=1e-11)
    qa['within_model_components_exactly_sum_to_total_swap_effect']=True
    # Existing stage-one January volume values must still be the same observations.
    old=pd.read_csv(e.SOURCE/'january_ocean_initial_states.csv')
    old=old.loc[old.baseline_method.eq('anomalies')].set_index('event')
    display=pd.read_csv(e.OUT/'display_anomalies.csv',parse_dates=['time']).set_index('time')
    for event in e.EVENTS:
        for region in ['basin',*e.REGIONS]:
            np.testing.assert_allclose(display.loc[pd.Timestamp(event,1,15),region+'_wwv'],old.loc[event,region+'_wwv_1e14m3'],atol=1e-11)
    thermal=pd.read_csv(e.SOURCE/'january_thermal_structure.csv',parse_dates=['time'])
    differences=[]
    for row in thermal.itertuples():
        col=f'{row.region}_t{int(row.layer_top_m)}_{int(row.layer_bottom_m)}'
        differences.append(abs(display.loc[row.time,col]-row.profile_mean_temperature_anomaly_C))
    qa['temperature_anomaly_operation_order_max_difference_C']=float(max(differences))
    assert max(differences)<.02
    qa['january_volume_matches_audited_stage_one']=True
    timing=pd.read_csv(e.OUT/'native_forecast_error_timing.csv').groupby('event').OND_nino34_error_contribution_C.sum()
    native=pd.read_csv(e.OUT/'native_initialization_skill.csv')
    native=native.loc[native.model.eq(e.PRIMARY)&~native.detrend].set_index('event')
    np.testing.assert_allclose(timing.loc[list(e.EVENTS)],(native.observed_OND_C-native.predicted_OND_C).loc[list(e.EVENTS)],atol=1e-10)
    qa['native_error_timing_sums_to_free_forecast_error']=True
    qa['common_fit_training_months']=int(weights.sum());qa['common_fit_training_pairs']=len(pairs)
    qa['all_model_annual_radii_below_one']=bool(all(v['annual_radius']<1 for v in models.values()))
    qa['physical_density_velocity_balanced_initialization_verified']=False
    qa['native_event_skill_is_separate_from_numerical_checks']=True
    html=(e.OUT/'海洋初态替换试验_结果与适用边界.html').read_text()
    from PIL import Image
    figures=sorted(e.OUT.glob('Fig*.png'));assert len(figures)==6
    for p in figures:
        with Image.open(p) as image:image.verify()
        assert p.name in html
        assert p.with_suffix('.pdf').stat().st_size>1000
        assert p.with_suffix('.svg').stat().st_size>1000
    qa['six_figures_in_three_formats_and_report_links']=True
    e.dump('validation_results.json',qa)
    print(json.dumps(qa,indent=2))
    files=[p for p in e.OUT.iterdir() if p.is_file() and p.name!='delivery_manifest.json']
    files += [e.ROOT/'scripts'/name for name in ['experiment_three_event_initial_states.py','validate_three_event_initial_states.py','plot_report_three_event_initial_states.py'] if (e.ROOT/'scripts'/name).exists()]
    e.dump('delivery_manifest.json',[{'path':str(p.relative_to(e.ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files])


if __name__=='__main__':main()
