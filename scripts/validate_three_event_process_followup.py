"""Validate source alignment, reset chronology, budgets, and reported numbers."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
import paper_ro_slim as original
from analyze_three_event_process_followup import ROOT,SOURCE,MODEL,OUT,EVENTS,PRIMARY,KEYS


def main():
    m=pd.read_csv(OUT/'all_month_evidence.csv',parse_dates=['time'])
    replay=pd.read_csv(OUT/'observed_state_replay.csv');scores=pd.read_csv(OUT/'replay_scores.csv')
    budget=pd.read_csv(OUT/'adjacent_month_volume_budget.csv',parse_dates=['start','end'])
    heat=pd.read_csv(OUT/'internal_gate_heat_terms.csv')
    focus=pd.read_csv(OUT/'previously_selected_error_months.csv')
    assert len(m)==72 and len(budget)==414 and len(replay)==1728 and len(scores)==144 and len(heat)==288
    assert not m.duplicated(['event','time']).any()
    for event in EVENTS:
        a=m[m.event.eq(event)].sort_values('time')
        assert list(a.relative_month)==list(range(-11,13))
        assert a.time.dt.day.eq(15).all()
        assert a.loc[a.year.eq(event)&a.month.gt(1),'residual_nino34'].notna().all()
        assert a.loc[~(a.year.eq(event)&a.month.gt(1)),'residual_nino34'].isna().all()
    assert np.isfinite(m.drop(columns=['time','residual_nino34','residual_west_wwv','residual_central_wwv','residual_east_wwv','ond_propagated_residual']).to_numpy()).all()
    np.testing.assert_allclose(m[['west_wwv_m3','central_wwv_m3','east_wwv_m3']].sum(axis=1),m.basin_wwv_m3,rtol=0,atol=20.)
    reference=pd.read_csv(SOURCE/'atmosphere_anomaly_and_reference.csv',parse_dates=['time']).set_index('time')
    alignment=[]
    for event in EVENTS:
        a=m[m.event.eq(event)]
        for c in ['nino34','tau','tau_residual_z']:alignment.append(abs(a[c].to_numpy()-reference.loc[a.time,c].to_numpy()).max())
    assert max(alignment)<1e-10
    assert np.array_equal(budget.seconds,((budget.end-budget.start).dt.total_seconds()).to_numpy())
    assert ((budget.end.dt.to_period('M').astype(int)-budget.start.dt.to_period('M').astype(int))==1).all()
    np.testing.assert_allclose(budget.storage_change,budget.zonal_input+budget.meridional_input+budget.unresolved,atol=1e-12)
    # Exact expected focus is inherited, not changed after examining wind/ocean.
    assert {e:sorted(focus[focus.event.eq(e)].month.tolist()) for e in EVENTS}=={1997:[3,7,8],2015:[2,7,10],2023:[6,8,11]}
    assert heat.area_coverage.ge(.95).all()
    np.testing.assert_allclose(heat.two_term_sum_pw,heat.mean_flow_temperature_anomaly_pw+heat.anomalous_flow_mean_temperature_pw,atol=1e-12)
    # Independently reconstruct replay with the original integrator, starting
    # from absolute raw inputs and saved background, not the new replay arrays.
    raw=pd.read_csv(MODEL/'inputs_absolute.csv',parse_dates=['time']).set_index('time')
    clim=pd.read_csv(MODEL/'display_climatology_1982_2022.csv').set_index('month')
    models=json.loads((MODEL/'models_and_preprocessing.json').read_text())
    max_replay_error=0.;score_errors=[]
    for key in KEYS:
        model=models[key]['model'];meta=models[key]['preprocessing'];cols=model['columns']
        model['coef']=np.array(model['coef']);model['scale']=np.array(model['scale'])
        matrices={month:np.column_stack([original.predict(model,np.eye(4)[j],month,months=1)[-1] for j in range(4)]) for month in range(1,12)}
        for event in EVENTS:
            dates=pd.date_range(f'{event}-01-01',periods=12,freq='MS')
            background=np.array(meta['clim'])[dates.month-1]+np.column_stack([np.ones(12),original.decimal_time(dates)-meta['center']])@np.array(meta['trend'])
            obs=raw.loc[dates,cols].to_numpy()-background
            restore=background-clim.loc[dates.month,cols].to_numpy()
            for exp in ['free','observed_ocean_replay','observed_sst_replay']:
                a=[obs[0].copy()]
                for i in range(1,12):
                    inp=a[-1].copy()
                    if exp=='observed_ocean_replay':inp[1:]=obs[i-1,1:]
                    if exp=='observed_sst_replay':inp[0]=obs[i-1,0]
                    a.append(matrices[i]@inp)
                actual=np.array(a)+restore
                selected=replay[(replay.key==key)&(replay.year==event)&(replay.experiment==exp)]
                saved=selected.pivot(index='month',columns='variable',values='predicted')[cols].to_numpy()
                max_replay_error=max(max_replay_error,float(abs(saved-actual).max()))
                for j,col in enumerate(cols):
                    record=scores[(scores.key==key)&(scores.year==event)&(scores.experiment==exp)&(scores.variable==col)].iloc[0]
                    truth=obs[:,j]+restore[:,j]
                    score_errors.extend([abs(record.ond_pred-actual[9:,j].mean()),abs(record.ond_obs-truth[9:].mean()),
                        abs(record.rmse_feb_dec-np.sqrt(np.mean((actual[1:,j]-truth[1:])**2)))])
    assert max_replay_error<1e-9 and max(score_errors)<1e-9
    # Check the concrete anchors printed in Chinese prose against derived CSVs.
    quarters=pd.read_csv(OUT/'common_quarter_evidence.csv').set_index(['event','quarter'])
    anchors=[(quarters.loc[(2023,2),'u220_q_sv'],19.55,.006),(quarters.loc[(2023,3),'u220_q_sv'],2.35,.006),
        (quarters.loc[(2023,2),'east_t0_50'],1.18,.006),(quarters.loc[(2023,2),'east_t50_150'],.35,.006),
        (quarters.loc[(2023,2),'wind_z_full_with_trend'],.07,.006),(quarters.loc[(2023,2),'wind_z_full_no_trend'],-1.,.006)]
    for value,printed,tolerance in anchors:assert abs(value-printed)<tolerance
    primary=scores[scores.key.eq(PRIMARY)&scores.variable.eq('nino34')&scores.experiment.eq('observed_ocean_replay')].set_index('year')
    np.testing.assert_allclose(primary.loc[list(EVENTS),'ond_pred'],[.699379,.459945,-.365385],atol=1e-6)
    # 2023 ocean replay is colder than its corresponding free run in all variants.
    comp=scores[scores.year.eq(2023)&scores.variable.eq('nino34')].pivot(index='key',columns='experiment',values='ond_pred')
    assert (comp.observed_ocean_replay<comp.free).all()
    for stem in json.loads((OUT/'figure_captions.json').read_text()):
        for ext in ['png','pdf','svg']:assert (OUT/f'{stem}.{ext}').stat().st_size>1000
        with Image.open(OUT/f'{stem}.png') as img:img.verify()
    result=dict(status='PASS: numerical consistency, source alignment and diagnostic chronology',
        all_month_records=len(m),budget_intervals=len(budget),replay_records=len(replay),
        independent_original_integrator_replay_error=max_replay_error,score_error=float(max(score_errors)),
        source_alignment_error=float(max(alignment)),focus_months_match_previous_stage=True,
        interpretation='No independent forecast or causal forcing identification is claimed.')
    (OUT/'validation_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    code=[Path(__file__),ROOT/'scripts/analyze_three_event_process_followup.py',ROOT/'scripts/report_three_event_process_followup.py']
    (OUT/'followup_code_sha256.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code},indent=2))
    rows=[]
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='file_manifest_sha256.csv':rows.append(dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    pd.DataFrame(rows).to_csv(OUT/'file_manifest_sha256.csv',index=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
