"""Exploratory fixed-state least-squares check of the sLIM process limitation.

This is a response regression diagnostic, not a replacement dynamical model.
It retains the same states, harmonics, preprocessing, and excluded windows.
"""
import numpy as np
import pandas as pd
from analyze_three_event_temperature_tendency import OUT,PREV,DATES,MASK,TERMS,EVENTS
import three_event_segmented_slim as slim
import paper_ro_slim as original


def main():
    d=pd.read_csv(OUT/'monthly_local_tendencies.csv',parse_dates=['time'])
    raw=pd.read_csv(PREV/'inputs_absolute.csv',parse_dates=['time']).set_index('time')
    rows=[];cases=[];coefficients=[]
    for h in [30,50,75]:
        layer=d[d.depth_m.eq(h)].set_index('time')
        for detrend in [True,False]:
            for scheme,cols in [('three_wwv',['west_wwv','central_wwv','east_wwv']),('total_wwv',['basin_wwv'])]:
                key=f'{h}m_{scheme}_{"detrend" if detrend else "mean"}_ols_diagnostic'
                inp=pd.concat([layer[['temperature']],raw[cols]],axis=1)
                a,_=slim.preprocess(inp,MASK.astype(float),detrend)
                resp,_=slim.preprocess(layer[TERMS],MASK.astype(float),detrend)
                z=a.to_numpy()/a.loc[MASK].std(ddof=0).to_numpy()
                phi=original.basis(original.decimal_time(DATES),2)
                design=np.einsum('nk,nd->nkd',phi,z).reshape(len(z),-1)
                coef,_,rank,svals=np.linalg.lstsq(design[MASK],resp.to_numpy()[MASK],rcond=None)
                assert rank==design.shape[1]
                pred=design@coef
                for j,process in enumerate(TERMS):
                    for sample,use in [('training',MASK),('held_out_three_windows',~MASK)]:
                        y=resp.to_numpy()[use,j];p=pred[use,j]
                        rows.append(dict(key=key,process=process,sample=sample,n=int(use.sum()),
                            correlation=np.corrcoef(y,p)[0,1],rmse=np.sqrt(np.mean((y-p)**2)),
                            mse_skill_vs_zero=1-np.mean((y-p)**2)/np.mean(y**2),condition=svals[0]/svals[-1]))
                    for k,c in enumerate(coef[:,j]):coefficients.append(dict(key=key,process=process,column=k,value=c))
                    for event in EVENTS:
                        ids=np.flatnonzero(DATES.year==event)
                        for idx in ids:cases.append(dict(key=key,event=event,month=DATES[idx].month,process=process,
                            diagnosed=resp.iloc[idx,j],reconstructed=pred[idx,j]))
    pd.DataFrame(rows).to_csv(OUT/'ols_same_state_process_skill.csv',index=False)
    pd.DataFrame(cases).to_csv(OUT/'ols_same_state_case_reconstructions.csv',index=False)
    pd.DataFrame(coefficients).to_csv(OUT/'ols_same_state_coefficients.csv',index=False)
    a=pd.DataFrame(rows)
    print(a[a.key.eq('50m_three_wwv_detrend_ols_diagnostic')].round(4).to_string(index=False))
    b=pd.DataFrame(cases);b=b[b.key.eq('50m_three_wwv_detrend_ols_diagnostic')&b.process.eq('u_prime_meanT')&b.month.between(7,9)]
    print(b.groupby('event')[['diagnosed','reconstructed']].mean().round(4).to_string())


if __name__=='__main__':main()
