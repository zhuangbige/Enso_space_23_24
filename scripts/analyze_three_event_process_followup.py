"""Fixed-model failure diagnosis against observed air--sea and ocean processes.

No refitting, no event-specific parameters, no residual interpreted as forcing.
Observed-state replay is retrospective diagnostic conditioning, not a forecast.
"""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import three_event_segmented_slim as slim

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/research_2026/three_event_ocean_preconditioning_20261014'
MODEL=ROOT/'outputs/research_2026/three_event_slim_baseline_20261014'
OUT=ROOT/'outputs/research_2026/three_event_process_followup_20261015'
EVENTS=(1997,2015,2023)
REGIONS=('west','central','east')
EDGES={'west':('u120','u180'),'central':('u180','u220'),'east':('u220','u280')}
PRIMARY='three_wwv_detrend_perturb2'
KEYS=[f'three_wwv_{p}_{m}' for p in ('detrend','mean') for m in ('perturb2','exact')]
READS=[]


def read(path,dates=True):
    READS.append(path)
    a=pd.read_csv(path)
    if dates and 'time' in a:a['time']=pd.to_datetime(a.time)
    return a


def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else x),encoding='utf-8')


def protocol():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol_before_run.txt').write_text('''2026-10-15: fixed-sLIM failure follow-up; scope frozen before the new replay.
Compare 1996--1997, 2014--2015, 2022--2023. Present all months and common
JFM/AMJ/JAS/OND windows, plus the previously reported top-three error months.
All targeted-month comparisons are exploratory; no p-values from selected peaks.
Reuse existing OISST/ERA5/SODA3 diagnostics and fixed sLIM coefficients.
Do not tune parameters or state sets on these event outcomes.

Diagnostic replay: monthly Phi matrices from the same four-state sLIM. Initialize
at observed January. Before each transition either replace all three ocean
coordinates with that month's observations and advance SST, or replace SST with
its observation and advance ocean. No target-month observation enters its one-step
prediction. These trajectories use development-year observations repeatedly;
they are NOT independent forecasts, interventions or causal attribution.
Retain detrend/mean and perturbative/exact estimator sensitivities.

Use instantaneous model one-step residual separately from the previously saved
residual propagated to OND. Wind is a contemporaneous SST/pattern-conditioned
statistical residual, not the same residual and not an identified forcing.
Show absolute stress, stress anomaly, and trend/no-trend wind reference together.
No identification of daily westerly bursts from monthly averages.

Use source 1982--2022 calendar-month anomalies for ocean/airsea diagnostics.
Volume is WWV26 (surface to instantaneous sigma-theta=26), +/-9 degrees; transport
Sv, volume m3. Adjacent-midmonth interval budget uses trapezoidal integration and
actual elapsed seconds. Positive net input = west-east + south-north.
Warm temperature anomalies in 0--50/50--150/150--300m are structure diagnostics,
not interchangeable with warm-water volume. SST/wind Hovmollers are +/-5 degrees.
Two heat terms at 180 and 140W are mean flow*T' and flow'*mean T, PW, positive
eastward; both instantaneous and climatological sections retained. An interval
with <95% effective area coverage is flagged, not filled. These are not the full
heat transport anomaly or a mixed-layer SST tendency. Unresolved volume budget
cannot be labeled heat loss, mixing or a named physical process.

Deliver all-month evidence, common-window summaries, observed-state replays,
scientific figures, Chinese report, reproducibility notes and numerical checks.
Only add convection analysis if these diagnostics identify a specific unmet need;
do not silently extend the state model or claim a complete mechanism.
''',encoding='utf-8')


def replay():
    path=MODEL/'models_and_preprocessing.json';READS.append(path)
    models=json.loads(path.read_text())
    f=read(MODEL/'native_forecasts.csv')
    out=[];scores=[];resids=[];qa={}
    for key in KEYS:
        model=models[key]['model']
        model['coef']=np.array(model['coef']);model['scale']=np.array(model['scale'])
        cols=model['columns'];assert cols==['nino34','west_wwv','central_wwv','east_wwv']
        phis={m:slim.propagators(model,m,1)[1] for m in range(1,12)}
        for year in EVENTS:
            g=f[f.key.eq(key)&f.year.eq(year)]
            observed=g.pivot(index='month',columns='variable',values='observed_model')[cols].to_numpy()
            actual=g.pivot(index='month',columns='variable',values='observed')[cols].to_numpy()
            bg=actual-observed
            free=np.zeros_like(observed);ocean_replay=free.copy();sst_replay=free.copy()
            free[0]=ocean_replay[0]=sst_replay[0]=observed[0]
            for i in range(1,12):
                phi=phis[i]
                free[i]=phi@free[i-1]
                # Store the forecast of each target month before its state reset.
                ocean_replay[i]=phi@np.r_[ocean_replay[i-1,0],observed[i-1,1:]]
                sst_replay[i]=phi@np.r_[observed[i-1,0],sst_replay[i-1,1:]]
                residual=observed[i]-phi@observed[i-1]
                for j,col in enumerate(cols):
                    resids.append(dict(key=key,year=year,month=i+1,variable=col,one_step_residual=residual[j]))
                # Repeated-substitution recurrence is independently checked.
                assert abs(observed[i,0]-ocean_replay[i,0]-(phi[0,0]*(observed[i-1,0]-ocean_replay[i-1,0])+residual[0]))<1e-10
            saved=g.pivot(index='month',columns='variable',values='predicted_model')[cols].to_numpy()
            qa[f'{key}_{year}_free_reproduction']=float(abs(saved-free).max())
            assert abs(saved-free).max()<1e-9
            for experiment,arr in [('free',free),('observed_ocean_replay',ocean_replay),('observed_sst_replay',sst_replay)]:
                for i in range(12):
                    for j,col in enumerate(cols):
                        out.append(dict(key=key,year=year,month=i+1,experiment=experiment,variable=col,
                                        predicted=arr[i,j]+bg[i,j],observed=actual[i,j]))
                for j,col in enumerate(cols):
                    pred=arr[:,j]+bg[:,j]
                    scores.append(dict(key=key,year=year,experiment=experiment,variable=col,
                        ond_pred=pred[9:].mean(),ond_obs=actual[9:,j].mean(),
                        rmse_feb_dec=np.sqrt(np.mean((pred[1:]-actual[1:,j])**2))))
    pd.DataFrame(out).to_csv(OUT/'observed_state_replay.csv',index=False)
    pd.DataFrame(scores).to_csv(OUT/'replay_scores.csv',index=False)
    pd.DataFrame(resids).to_csv(OUT/'one_step_state_residuals.csv',index=False)
    # Replay is causal in its input chronology, though retrospective overall.
    model=models[PRIMARY]['model'];cols=model['columns']
    obs=f[f.key.eq(PRIMARY)&f.year.eq(2023)].pivot(index='month',columns='variable',values='observed_model')[cols].to_numpy()
    def replay_temperature(z):
        tr=[z[0,0]]
        for i in range(1,12):tr.append((slim.propagators(model,i,1)[1]@np.r_[tr[-1],z[i-1,1:]])[0])
        return np.array(tr)
    changed=obs.copy();changed[6:,1:]+=99
    qa['future_july_ocean_perturbation_jan_through_july_error']=float(abs(replay_temperature(obs)[:7]-replay_temperature(changed)[:7]).max())
    assert qa['future_july_ocean_perturbation_jan_through_july_error']<1e-10
    return pd.DataFrame(resids),qa


def assemble(resids):
    atm=read(SOURCE/'atmosphere_anomaly_and_reference.csv').set_index('time')
    absolute=read(SOURCE/'atmosphere_absolute.csv').set_index('time')
    ocean=read(SOURCE/'ocean_monthly_anomalies.csv').set_index('time')
    trend=read(SOURCE/'ocean_monthly_trend_sensitivity.csv').set_index('time')
    thermal=read(SOURCE/'thermal_structure_monthly.csv')
    wind=read(SOURCE/'wind_reference_sensitivity_monthly.csv')
    heat=read(SOURCE/'two_term_heat_transport.csv')
    timing=read(MODEL/'native_error_timing.csv',False)
    r=resids[resids.key.eq(PRIMARY)].pivot(index=['year','month'],columns='variable',values='one_step_residual')
    records=[];intervals=[];qa={}
    for event in EVENTS:
        dates=pd.date_range(f'{event-1}-01-01',f'{event}-12-01',freq='MS')+pd.Timedelta(days=14)
        for t in dates:
            row=dict(event=event,time=t,year=t.year,month=t.month,relative_month=(t.year-event)*12+t.month)
            for c in ('nino34','nino3','nino4','pattern','tau','tau_expected','tau_residual','tau_residual_z'):
                row[c]=atm.loc[t,c]
            row['tau_absolute']=absolute.loc[t,'tau']
            for ref in ['full_with_trend','full_no_trend','early_with_trend','amplitude_only']:
                w=wind[wind.reference.eq(ref)&wind.time.eq(t)].iloc[0]
                row['wind_z_'+ref]=w.residual_z
                row['wind_expected_'+ref]=w.expected
            for col in ocean.columns:row[col]=ocean.loc[t,col]
            for reg in REGIONS:
                for top,bottom in [(0,50),(50,150),(150,300)]:
                    x=thermal[thermal.time.eq(t)&thermal.region.eq(reg)&thermal.layer_top_m.eq(top)&thermal.layer_bottom_m.eq(bottom)]
                    assert len(x)==1
                    row[f'{reg}_t{top}_{bottom}']=x.profile_mean_temperature_anomaly_C.iloc[0]
                row[reg+'_wwv_trend_m3']=trend.loc[t,reg+'_wwv_m3']
            if t.year==event and t.month>1:
                for col in r.columns:row['residual_'+col]=r.loc[(event,t.month),col]
                row['ond_propagated_residual']=timing[timing.year.eq(event)&timing.target_month.eq(t.month)].contribution_to_ond_sst.iloc[0]
            else:
                for col in r.columns:row['residual_'+col]=np.nan
                row['ond_propagated_residual']=np.nan
            records.append(row)
        for baseline,tab in [('monthly_mean',ocean),('monthly_trend',trend)]:
            for left,right in zip(dates[:-1],dates[1:]):
                seconds=(right-left).total_seconds()
                for reg in REGIONS:
                    west,east=EDGES[reg]
                    zi=.5*((tab.loc[left,west+'_q_sv']-tab.loc[left,east+'_q_sv'])+(tab.loc[right,west+'_q_sv']-tab.loc[right,east+'_q_sv']))*seconds/1e8
                    mi=.5*((tab.loc[left,reg+'_south_q_sv']-tab.loc[left,reg+'_north_q_sv'])+(tab.loc[right,reg+'_south_q_sv']-tab.loc[right,reg+'_north_q_sv']))*seconds/1e8
                    storage=(tab.loc[right,reg+'_wwv_m3']-tab.loc[left,reg+'_wwv_m3'])/1e14
                    intervals.append(dict(event=event,region=reg,baseline=baseline,start=left,end=right,
                        seconds=seconds,storage_change=storage,zonal_input=zi,meridional_input=mi,unresolved=storage-zi-mi))
    monthly=pd.DataFrame(records)
    monthly.to_csv(OUT/'all_month_evidence.csv',index=False)
    budget=pd.DataFrame(intervals);budget.to_csv(OUT/'adjacent_month_volume_budget.csv',index=False)
    dev=monthly[monthly.year.eq(monthly.event)].copy();dev['quarter']=(dev.month-1)//3+1
    numeric=[c for c in dev.select_dtypes('number').columns if c not in ['year','month','event','relative_month','quarter']]
    quarters=dev.groupby(['event','quarter'])[numeric].mean().reset_index()
    quarters.to_csv(OUT/'common_quarter_evidence.csv',index=False)
    # Error-based focus months are explicit, not an independent validation sample.
    focus=dev.dropna(subset=['ond_propagated_residual']).sort_values('ond_propagated_residual',ascending=False).groupby('event').head(3).sort_values(['event','month'])
    focus.to_csv(OUT/'previously_selected_error_months.csv',index=False)
    # Report Jan15--Apr15 / Apr15--Jul15 / Jul15--Oct15 / Oct15--Dec15;
    # the last is two months, explicitly not a three-full-month OND integral.
    summaries=[]
    for event in EVENTS:
        for lo,hi in [(1,4),(4,7),(7,10),(10,12),(1,12)]:
            for reg in REGIONS:
                for baseline in ['monthly_mean','monthly_trend']:
                    sub=budget[(budget.event==event)&(budget.region==reg)&(budget.baseline==baseline)&
                        (budget.start>=pd.Timestamp(event,lo,15))&(budget.end<=pd.Timestamp(event,hi,15))]
                    summaries.append(dict(event=event,region=reg,baseline=baseline,window=f'{lo:02d}15_to_{hi:02d}15',
                        elapsed_days=sub.seconds.sum()/86400,**sub[['storage_change','zonal_input','meridional_input','unresolved']].sum().to_dict()))
    summary=pd.DataFrame(summaries);summary.to_csv(OUT/'volume_interval_summaries.csv',index=False)
    # Heat inputs are retained per gate; no unsupported full-box heat closure.
    hh=heat[heat.gate.isin(['u180','u220'])].copy()
    hh['year']=hh.time.dt.year;hh['month']=hh.time.dt.month
    hh['two_term_sum_pw']=hh.mean_flow_temperature_anomaly_pw+hh.anomalous_flow_mean_temperature_pw
    hh['coverage_at_least_95pct']=hh.area_coverage.ge(.95)
    hh.to_csv(OUT/'internal_gate_heat_terms.csv',index=False)
    qa['budget_accounting_error']=float(abs(budget.storage_change-budget.zonal_input-budget.meridional_input-budget.unresolved).max())
    # Reconstruct the prior cumulative products with independent interval sums.
    prior=read(SOURCE/'cumulative_volume_budget.csv')
    errors=[]
    for row in summary[summary.window.eq('0115_to_1215')].itertuples():
        priorbase='anomalies' if row.baseline=='monthly_mean' else 'trend_sensitivity'
        g=prior[(prior.event==row.event)&prior.region.eq(row.region)&prior.baseline_method.eq(priorbase)&prior.window.eq('development')].sort_values('time').iloc[-1]
        for col in ['storage_change','zonal_input','meridional_input','unresolved']:errors.append(abs(getattr(row,col)-g[col]))
    qa['prior_cumulative_reproduction_error']=float(max(errors));assert max(errors)<1e-10
    qa['internal_gate_min_heat_coverage']=float(hh.area_coverage.min())
    qa['all_month_rows']=len(monthly);qa['focus_rows']=len(focus)
    qa['scope']='3 cases; 24-month process context, development-year fixed-model diagnosis; no causal attribution'
    return monthly,qa


def main():
    protocol()
    residuals,qa1=replay();monthly,qa2=assemble(residuals)
    dump('analysis_QA.json',{**qa1,**qa2})
    READS.extend([Path(__file__),Path(slim.__file__)])
    dump('source_sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(READS))})
    scores=pd.read_csv(OUT/'replay_scores.csv')
    print(scores[scores.key.eq(PRIMARY)&scores.variable.eq('nino34')].to_string(index=False),flush=True)
    cols=['event','month','nino34','tau','wind_z_full_with_trend','wind_z_full_no_trend','residual_nino34','ond_propagated_residual','u180_q_sv','u220_q_sv']
    print(monthly[monthly.year.eq(monthly.event)&monthly.month.gt(1)][cols].to_string(index=False),flush=True)
    print(json.dumps(qa2,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
