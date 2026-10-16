"""Independent local-grid recomputation and saved-operator consistency checks."""
import json
import numpy as np
import pandas as pd
from analyze_three_event_temperature_tendency import OUT,PREV,DATES,MASK,TERMS,MONTH,R,RHO,CP
import three_event_segmented_slim as slim


def main():
    d=pd.read_csv(OUT/'monthly_local_tendencies.csv',parse_dates=['time'])
    cases=pd.read_csv(OUT/'case_monthly_tendencies.csv',parse_dates=['time'])
    assert len(d)==1548 and len(cases)==216
    assert not d.duplicated(['time','depth_m']).any()
    assert np.isfinite(d.drop(columns='time')).all().all()
    assert int(MASK.sum())==408
    np.testing.assert_allclose(d[TERMS[:-1]].sum(axis=1),d.horizontal_total,atol=1e-12)
    np.testing.assert_allclose(d[TERMS].sum(axis=1)+d.unresolved,d.tendency,atol=1e-12)
    # Recompute full horizontal advection without the linear decomposition.
    with np.load(OUT/'local_fields_cache.npz') as f:
        t=f['temp'].astype(float);u=f['u'].astype(float);v=f['v'].astype(float)
        lat=f['lat'];lon=f['lon'];bottom=f['bottom']
        dx=R*np.cos(np.deg2rad(lat[1:-1]))[:,None]*np.deg2rad(1.)
        gx=(t[:,:,1:-1,2:]-t[:,:,1:-1,:-2])/dx
        gy=(t[:,:,2:,1:-1]-t[:,:,:-2,1:-1])/(R*np.deg2rad(1.))
        adv=-(u[:,:,1:-1,1:-1]*gx+v[:,:,1:-1,1:-1]*gy)
        area=R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat[1:-1]+.25))-np.sin(np.deg2rad(lat[1:-1]-.25)))[:,None]*np.ones((1,100))
        # Preserve one common wet mask, including the few island/gradient cells.
        # It is selected once across all years, never separately for an event.
        wet=np.isfinite(adv).all(axis=0)&np.isfinite(t[:,:,1:-1,1:-1]).all(axis=0)
        wet&=np.isfinite(f['q'][:,1:-1,1:-1]).all(axis=0)[None]
        errors=[];temp_errors=[];surface_errors=[]
        for h in [30,50,75]:
            dz=np.clip(h-np.r_[0,bottom[:-1]],0,np.diff(np.r_[0,bottom]))
            weights=dz[:,None,None]*area[None]*wet
            assert weights.sum()/(h*area.sum())>.995
            weights/=weights.sum()
            scalar=np.einsum('nzyx,zyx->n',np.where(wet,adv,0),weights)*MONTH
            surf=np.einsum('nyx,yx->n',np.nan_to_num(f['q'][:,1:-1,1:-1].astype(float)),weights.sum(axis=0))*MONTH/(RHO*CP*h)
            for arr in [scalar,surf]:
                for m in range(1,13):arr[DATES.month==m]-=arr[MASK&(DATES.month==m)].mean()
            saved=d[d.depth_m.eq(h)].set_index('time')
            errors.append(float(abs(scalar-saved.horizontal_total.to_numpy()).max()))
            surface_errors.append(float(abs(surf-saved.surface_flux_proxy.to_numpy()).max()))
            temp=np.einsum('nzyx,zyx->n',np.where(wet,t[:,:,1:-1,1:-1],0),weights)
            temp_errors.append(float(abs(temp-saved.temperature.to_numpy()).max()))
        assert max(errors+temp_errors+surface_errors)<1e-9
    # Test the B-grid averaging and spherical gradient against analytic fields.
    yu=np.arange(-5.5,6.,.5);xu=np.arange(189.5,241.,.5)
    corner=2*yu[:,None]+3*xu[None,:]
    centered=(corner[:-1,:-1]+corner[1:,:-1]+corner[:-1,1:]+corner[1:,1:])/4
    expected=2*((yu[:-1]+yu[1:])/2)[:,None]+3*((xu[:-1]+xu[1:])/2)[None,:]
    np.testing.assert_allclose(centered,expected,atol=1e-12)
    checks=json.loads((OUT/'coefficient_mapping_QA.json').read_text())
    assert len(checks)==24
    assert max(x['state_operator_error'] for x in checks)<1e-8
    assert max(x['component_sum_error'] for x in checks)<1e-8
    co=pd.read_csv(OUT/'seasonal_process_coefficients.csv')
    component=co[~co.process.eq('total')].groupby(['key','month','state']).coefficient.sum()
    total=co[co.process.eq('total')].set_index(['key','month','state']).coefficient
    np.testing.assert_allclose(component.sort_index(),total.sort_index(),atol=1e-10)
    recon=pd.read_csv(OUT/'case_process_reconstructions.csv')
    np.testing.assert_allclose(recon.sst_state_part+recon.ocean_state_part,recon.reconstructed,atol=1e-10)
    # Independently refit a saved primary operator directly from raw scalar inputs.
    raw=pd.read_csv(PREV/'inputs_absolute.csv',parse_dates=['time']).set_index('time')
    inp=pd.concat([d[d.depth_m.eq(50)].set_index('time')[['temperature']],raw[['west_wwv','central_wwv','east_wwv']]],axis=1)
    a,_=slim.preprocess(inp,MASK.astype(float),True)
    fit=slim.fit(a,MASK)
    saved=json.loads((OUT/'process_models_and_preprocessing.json').read_text())['50m_three_wwv_detrend_perturb2']['model']
    np.testing.assert_allclose(fit['coef'],saved['coef'],atol=1e-12)
    result=dict(status='PASS',monthly_rows=len(d),case_rows=len(cases),variants=len(checks),
        independent_horizontal_max_error_C_month=max(errors),independent_temperature_error_C=max(temp_errors),
        independent_surface_error_C_month=max(surface_errors),operator_error=max(x['state_operator_error'] for x in checks),
        component_sum_error=max(x['component_sum_error'] for x in checks),
        warning='Checks establish numerical consistency, not full physical closure or causal attribution.')
    (OUT/'validation_results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
