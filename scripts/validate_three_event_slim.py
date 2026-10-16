"""Independent saved-product checks for segmented sLIM; not physical validation."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_three_event_slim import OUT,ROOT,EVENTS,EXCLUDED,STATES
import three_event_segmented_slim as slim


def main():
    raw=pd.read_csv(OUT/'inputs_absolute.csv',parse_dates=['time']).set_index('time')
    mask=pd.read_csv(OUT/'training_mask.csv',parse_dates=['time'])
    assert len(raw)==516 and len(mask)==516 and mask.training.sum()==408
    assert set(mask.loc[~mask.training,'time'].dt.year)==EXCLUDED
    assert np.isfinite(raw.to_numpy()).all()
    f=pd.read_csv(OUT/'native_forecasts.csv');s=pd.read_csv(OUT/'native_scores.csv')
    d=pd.read_csv(OUT/'fit_diagnostics.csv');models=json.loads((OUT/'models_and_preprocessing.json').read_text())
    assert len(models)==24 and len(d)==24 and len(s)==72
    allkeys=set(models);assert set(f.key)==allkeys==set(s.key)==set(d.key)
    assert not f.duplicated(['key','year','month','variable']).any()
    errors=[];initerr=[];radiuserr=[];forecast_error=[]
    for key,info in models.items():
        model=info['model'];model['coef']=np.array(model['coef']);model['scale']=np.array(model['scale'])
        mm=info['preprocessing'];mm['clim']=np.array(mm['clim']);mm['trend']=np.array(mm['trend'])
        radi=max(abs(np.linalg.eigvals(slim.propagators(model)[-1])))
        radiuserr.append(abs(radi-d[d.key.eq(key)].annual_radius.iloc[0]))
        cols=model['columns']
        for year in EVENTS:
            q=f[f.key.eq(key)&f.year.eq(year)]
            assert len(q)==12*len(cols)
            first=q[q.month.eq(1)]
            initerr.append(abs(first.predicted-first.observed).max())
            z=q[q.variable.eq(cols[0])].sort_values('month')
            record=s[s.key.eq(key)&s.year.eq(year)].iloc[0]
            err=np.sqrt(np.mean((z.predicted.to_numpy()[1:]-z.observed.to_numpy()[1:])**2))
            errors.extend([abs(err-record.rmse_feb_dec),abs(z[z.month.ge(10)].predicted.mean()-record.ond_pred),
                           abs(z[z.month.ge(10)].observed.mean()-record.ond_obs)])
            ini=q[q.month.eq(1)].set_index('variable').loc[cols,'observed_model'].to_numpy()
            saved=q.pivot(index='month',columns='variable',values='predicted_model')[cols].to_numpy()
            forecast_error.append(abs(slim.forecast(model,ini)-saved).max())
            dates=pd.date_range(f'{year}-01-01',periods=12,freq='MS')
            modelobs=raw.loc[dates,cols].to_numpy()-slim.background_at(mm,dates)
            observed=q.pivot(index='month',columns='variable',values='observed_model')[cols].to_numpy()
            errors.append(abs(modelobs-observed).max())
    assert max(errors)<1e-9 and max(initerr)<1e-9 and max(forecast_error)<1e-9 and max(radiuserr)<1e-9
    assert d[d.method.eq('exact')].relative_moment_residual.max()<1e-12
    boot=pd.read_csv(OUT/'parameter_weight_native_forecasts.csv')
    assert len(boot)==200*3*12 and boot.replicate.nunique()==200 and np.isfinite(boot.to_numpy()).all()
    assert (boot.groupby('replicate').annual_radius.nunique()==1).all()
    errorqa=json.loads((OUT/'native_error_identity_QA.json').read_text())
    assert max(z['closure_error'] for z in errorqa.values())<1e-8
    expected_figures=['Fig13_slim_native_sst','Fig14_slim_native_wwv','Fig15_slim_seasonal_coefficients',
                      'Fig16_slim_representation_sensitivity','Fig17_slim_error_timing']
    for stem in expected_figures:
        for ext in ['png','pdf','svg']:
            assert (OUT/f'{stem}.{ext}').stat().st_size>1000
    from PIL import Image
    for stem in expected_figures:
        with Image.open(OUT/f'{stem}.png') as img:img.verify()
    checks=dict(status='PASS: implementation and saved-output consistency only',models=24,case_scores=72,
                score_and_background_error=float(max(errors)),january_initial_error=float(max(initerr)),
                saved_forecast_reproduction_error=float(max(forecast_error)),radius_error=float(max(radiuserr)),
                parameter_weight_draws=200,figures=len(expected_figures),
                interpretation='Native event mismatch remains; no causal sufficiency claim.')
    (OUT/'saved_product_QA.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
    manifest=[]
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name!='file_manifest_sha256.csv':
            manifest.append(dict(path=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    pd.DataFrame(manifest).to_csv(OUT/'file_manifest_sha256.csv',index=False)
    print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
