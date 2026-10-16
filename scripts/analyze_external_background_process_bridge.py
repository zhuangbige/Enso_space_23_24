"""Check physical-process consistency of exploratory external-state signals."""
from pathlib import Path
import gc
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import screen_external_background_transport as screen
import analyze_three_event_temperature_tendency as process

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/external_background_process_bridge_20261015'
PREV = ROOT / 'outputs/research_2026/external_background_experiments_20261015'
CACHE = ROOT / 'outputs/research_2026/three_event_temperature_tendency_20261015/local_fields_cache.npz'
DATES = screen.DATES
RESPONSES = {
    'tau': ('JAS zonal wind stress', 'N m-2'),
    'u_prime_meanT': ('JAS current-anomaly advection', 'C month-1'),
    'mean_u_Tprime': ('JAS temperature-anomaly advection', 'C month-1'),
    'transport': ('JAS warm-water transport at 140W', 'Sv'),
    'nino34_growth': ('OND minus AMJ Nino3.4', 'C')}
NBOOT = 3000
COLORS = {1997: '#0072B2', 2015: '#E69F00', 2023: '#D55E00'}


def dump(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2,
        default=lambda v: v.item() if isinstance(v, np.generic) else str(v)), encoding='utf-8')


def local_fields():
    # Read a frozen cache; all new diagnostics go to this task's output directory.
    with np.load(CACHE) as z:
        f = {k: z[k] for k in z.files}
    process.MASK = np.ones(len(DATES), dtype=bool)
    process.OUT = OUT
    data = process.local_diagnostics(f)
    # Supporting scalar diagnostics use the identical valid mask/volume convention.
    t = f['temp'].astype(float)
    u = f['u'].astype(float)
    v = f['v'].astype(float)
    lat, lon = f['lat'], f['lon']
    tx = np.gradient(t, np.deg2rad(lon), axis=-1) / (process.R*np.cos(np.deg2rad(lat))[None,None,:,None])
    ty = np.gradient(t, np.deg2rad(lat), axis=-2) / process.R
    t, u, v, tx, ty = [a[:,:,1:-1,1:-1] for a in [t,u,v,tx,ty]]
    q = f['q'][:,1:-1,1:-1]
    wet = np.isfinite(t).all(0)&np.isfinite(u*tx+v*ty).all(0)&np.isfinite(q).all(0)[None]
    area = process.R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat[1:-1]+.25))-
           np.sin(np.deg2rad(lat[1:-1]-.25)))[:,None]*np.ones((1,len(lon)-2))
    dz = np.maximum(0,np.minimum(f['bottom'],50)-np.r_[0,f['bottom'][:-1]])
    w = dz[:,None,None]*area[None]*wet
    avg = lambda a: np.nansum(np.where(wet,a,0)*w[None],axis=(1,2,3))/w.sum()
    scalars = pd.DataFrame({'time': DATES,'u_0_50_m_s':avg(u),
                           'dTdx_0_50_C_per_1000km':avg(tx)*1e6})
    scalars.to_csv(OUT/'supporting_current_gradient.csv',index=False)
    qa = {'coverage_scalar_50m':float(w.sum()/(50*area.sum())),
          'climatology_years':list(range(1982,2025)),
          'all_target_years_included':True,
          'pointwise_product_before_volume_average':True}
    assert qa['coverage_scalar_50m'] > .995
    del f,t,u,v,tx,ty,q
    gc.collect()
    return data, scalars, qa


def fit_response(table, y, columns, rng):
    names = screen.CONTROLS + columns
    x = table[names].to_numpy()
    z = (x-x.mean(0))/x.std(0)
    X = np.column_stack([np.ones(len(x)),z]); y=np.asarray(y)
    n,p=X.shape
    beta=np.linalg.lstsq(X,y,rcond=None)[0]
    base=X[:,:1+len(screen.CONTROLS)]
    bp=base@np.linalg.lstsq(base,y,rcond=None)[0]
    residual=y-X@beta
    ss=np.sum((y-y.mean())**2);sse=residual@residual
    boot=[]
    for _ in range(NBOOT):
        start=rng.integers(n,size=int(np.ceil(n/3)))
        ix=((start[:,None]+np.arange(3))%n).ravel()[:n]
        if np.linalg.matrix_rank(X[ix])==p:
            boot.append(np.linalg.lstsq(X[ix],y[ix],rcond=None)[0])
    assert len(boot)>NBOOT*.99
    lo,hi=np.quantile(boot,[.025,.975],axis=0)
    deleted=np.asarray([np.linalg.lstsq(np.delete(X,i,axis=0),np.delete(y,i),rcond=None)[0]
                        for i in range(n)])
    ys=y.std()
    records=[dict(variable=var,beta=beta[j],lo=lo[j],hi=hi[j],
                  beta_standardized=beta[j]/ys,lo_standardized=lo[j]/ys,hi_standardized=hi[j]/ys,
                  response_sd=ys,delete_one_same_sign=np.mean(np.sign(deleted[:,j])==np.sign(beta[j])))
             for j,var in enumerate(names,1) if var in columns]
    # Independent normal-equation and FWL checks.
    normal=np.linalg.solve(X.T@X,X.T@y)
    r=lambda a:a-base@np.linalg.lstsq(base,a,rcond=None)[0]
    fwl=np.linalg.lstsq(r(X[:,base.shape[1]:]),r(y),rcond=None)[0]
    err=max(np.max(abs(normal-beta)),np.max(abs(fwl-beta[base.shape[1]:])))
    assert err<1e-8
    metrics=dict(n=n,r2=1-sse/ss,delta_r2=(np.sum((y-bp)**2)-sse)/ss,
                 condition_number=np.linalg.cond(X),coefficient_check_error=float(err))
    return records,metrics


def analyze(local):
    raw=pd.read_csv(PREV/'monthly_inputs.csv',parse_dates=['time']).set_index('time')
    air=screen.read_monthly(screen.BASE/'atmosphere_anomaly_and_reference.csv')
    raw['tau']=air.tau
    annual_inputs=pd.read_csv(PREV/'annual_inputs_all_settings.csv')
    rng=np.random.default_rng(2026101502)
    coeffs=[];metrics=[];annual=[];monthly=[]
    for depth in [50,30,75]:
        native=local[local.depth_m.eq(depth)].set_index('time')
        combined=raw.join(native[['u_prime_meanT','mean_u_Tprime','horizontal_total','tendency']])
        for dt in ([True,False] if depth==50 else [True]):
            prepared=screen.remove_background(combined,dt)
            if depth==50:
                monthly.append(prepared.assign(background='detrended' if dt else 'with_trend').reset_index(names='time'))
            for season,months in ([('AMJ',[4,5,6]),('MAM',[3,4,5])] if depth==50 else [('AMJ',[4,5,6])]):
                key=f'{season}_{"detrended" if dt else "with_trend"}'
                table=annual_inputs[annual_inputs.setting.eq(key)].set_index('year').copy()
                summer=screen.seasonal(prepared,[7,8,9])
                ys={k:summer[k] for k in ['tau','u_prime_meanT','mean_u_Tprime','transport']}
                ys['nino34_growth']=screen.seasonal(prepared[['nino34']],[10,11,12]).nino34-screen.seasonal(prepared[['nino34']],[4,5,6]).nino34
                assert np.max(abs(ys['transport'].to_numpy()-table.summer_transport.to_numpy()))<1e-10
                targets=list(RESPONSES) if depth==50 else ['u_prime_meanT','mean_u_Tprime']
                for target in targets:
                    for year,value in ys[target].items():
                        annual.append(dict(depth_m=depth,setting=key,target=target,year=year,value=value,unit=RESPONSES[target][1]))
                    for group,cols in screen.GROUPS.items():
                        rows,m=fit_response(table,ys[target].to_numpy(),cols,rng)
                        meta=dict(depth_m=depth,setting=key,target=target,group=group,unit=RESPONSES[target][1])
                        coeffs.extend([{**meta,**row} for row in rows]);metrics.append({**meta,**m})
        print('finished depth',depth,flush=True)
    c=pd.DataFrame(coeffs); m=pd.DataFrame(metrics)
    c.to_csv(OUT/'all_process_coefficients.csv',index=False)
    m.to_csv(OUT/'all_model_comparisons.csv',index=False)
    pd.DataFrame(annual).to_csv(OUT/'annual_process_responses.csv',index=False)
    month=pd.concat(monthly,ignore_index=True)
    month.to_csv(OUT/'monthly_process_chain.csv',index=False)
    # Exactly reproduce the preceding primary transport coefficients.
    old=pd.read_csv(PREV/'all_coefficients.csv')
    new=c[c.depth_m.eq(50)&c.target.eq('transport')]
    merged=new.merge(old,on=['setting','group','variable'])
    err=float(np.max(abs(merged.beta-merged.beta_Sv_per_SD)))
    assert len(merged)==32 and err<1e-9
    return c,m,month,err


def savefig(fig,name):
    for ext in ['png','pdf','svg']:
        fig.savefig(OUT/f'{name}.{ext}',dpi=300,bbox_inches='tight')
    plt.close(fig)


def figures(c,monthly):
    sys.path.insert(0,'/Users/daiyue/.codex/skills/climate-plotting/scripts')
    from climate_plot_style import apply_climate_style
    apply_climate_style(10)
    specs=[('TNA','Tropical North Atlantic SST','°C'),('PMM','PMM SST index','°C (mode amplitude)'),
           ('tau','Central-western Pacific wind stress','N m$^{-2}$'),
           ('transport','140°W warm-water transport','Sv'),
           ('u_prime_meanT',r'Current-anomaly term: $-u^\prime\partial_x\overline{T}$','°C month$^{-1}$'),
           ('mean_u_Tprime',r'Temperature-anomaly term: $-\overline{u}\partial_x T^\prime$','°C month$^{-1}$')]
    fig,axes=plt.subplots(3,2,figsize=(10.6,8.2),sharex=True,layout='constrained')
    data=monthly[monthly.background.eq('detrended')].copy();data['time']=pd.to_datetime(data.time)
    for i,(ax,(var,title,unit)) in enumerate(zip(axes.flat,specs)):
        ax.axvspan(6.5,9.5,color='#eeeeee',zorder=0)
        ax.axhline(0,color='.55',lw=.7,zorder=1)
        for year in [1997,2015,2023]:
            g=data[data.time.dt.year.eq(year)]
            ax.plot(g.time.dt.month,g[var],label=str(year),color=COLORS[year],lw=1.9)
        ax.set_title(f'{chr(97+i)}  {title}',loc='left',fontsize=10)
        ax.set_ylabel(unit);ax.set_xlim(1,12);ax.spines[['top','right']].set_visible(False)
        ax.set_xticks([1,3,5,7,9,11],['Jan','Mar','May','Jul','Sep','Nov'])
    axes[1,1].legend(ncol=3,frameon=False,loc='upper right')
    fig.suptitle('External backgrounds and summer transport: three event evolutions',fontsize=13)
    fig.supxlabel('1982–2024 monthly climatology and linear trend removed; shading: July–September\nLocal advection: Niño3.4, 0–50 m. Transport: 9°S–9°N, above σθ = 26.',fontsize=9)
    savefig(fig,'Fig1_event_process_evolution')

    primary=c[c.depth_m.eq(50)&c.setting.eq('AMJ_detrended')]
    labels=['Wind stress','Current-anomaly advection','Temperature-anomaly advection',
            '140°W warm-water transport','Niño3.4 growth (OND − AMJ)']
    targets=list(RESPONSES)
    fig,axes=plt.subplots(1,2,figsize=(11.6,5.7),sharex=True,sharey=True)
    fig.subplots_adjust(left=.29,right=.985,bottom=.24,top=.79,wspace=.08)
    for ax,var,own,color in zip(axes,['TNA','PMM'],['A_IndoAtlantic','B_ExtratropicalPacific'],['#0072B2','#D55E00']):
        for offset,group,marker,label in [(-.12,own,'o','Within-basin-group model'),(.12,'AB_joint','s','Both groups together')]:
            for j,target in enumerate(targets):
                r=primary[primary.variable.eq(var)&primary.group.eq(group)&primary.target.eq(target)].iloc[0]
                y=j+offset
                ax.plot([r.lo_standardized,r.hi_standardized],[y,y],color=color,alpha=.85,lw=1.5)
                ax.scatter(r.beta_standardized,y,marker=marker,s=36,edgecolors=color,
                           facecolors=color if group==own else 'white',label=label if j==0 else None,zorder=3)
        ax.axvline(0,color='.3',lw=.8)
        ax.set_title(var);ax.set_xlabel('Response SD per +1 SD background index')
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',color='.92',lw=.6)
    axes[0].set_yticks(np.arange(5),labels);axes[0].invert_yaxis()
    fig.suptitle('Conditional process associations, not a causal pathway',fontsize=13,y=.98)
    handles,legend_labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc='upper center',bbox_to_anchor=(.63,.92),ncol=2,frameon=False,fontsize=9)
    fig.text(.5,.045,'43 years, 1982–2024; AMJ background → JAS processes. 95% pointwise 3-year block-bootstrap intervals.\nCommon controls: AMJ transport, JFM western WWV26, JFM Niño3.4. No multiple-testing significance claim.',ha='center',fontsize=8.5)
    savefig(fig,'Fig2_conditional_process_associations')


def report(c,m,qa):
    rows=[]
    for var,group in [('TNA','A_IndoAtlantic'),('PMM','B_ExtratropicalPacific')]:
        for target in RESPONSES:
            g=c[c.variable.eq(var)&c.group.eq(group)&c.target.eq(target)&c.depth_m.eq(50)]
            p=g[g.setting.eq('AMJ_detrended')].iloc[0]
            j=c[c.variable.eq(var)&c.group.eq('AB_joint')&c.target.eq(target)&c.depth_m.eq(50)&c.setting.eq('AMJ_detrended')].iloc[0]
            rows.append(dict(variable=var,target=target,unit=p.unit,beta=p.beta,lo=p.lo,hi=p.hi,
                settings_same_sign=bool((np.sign(g.beta)==np.sign(p.beta)).all()),
                settings_interval_excludes_zero=int(((g.lo>0)|(g.hi<0)).sum()),
                joint_beta=j.beta,joint_lo=j.lo,joint_hi=j.hi))
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'process_evidence_summary.csv',index=False)
    text=['外部海洋背景补充实验：过程一致性核对','',
          '主线保持海洋储备—夏季输送持续性—Niño3.4发展。此结果是补充探索，尚无外部SST替换积分。',
          '重新用1982—2024全部43年计算局地过程背景；目标年全部纳入。旧sLIM、图件和首轮结果不变。',
          '表内beta为外部指标每增加1 SD对应的物理量变化；区间为3年循环块bootstrap 3000次的逐项95%区间。',
          '所有响应保持相同前期控制；同期风—海流—平流联系不能直接解释成已识别中介因果链。','',
          '当前判断：TNA与弱风应力、弱140°W输送及较少后续增暖的组内联系较一致，但联合模型区间跨零，局地平流中间环节未得到稳定支持。',
          'PMM与风应力及后续海温增长的条件联系较清楚；与局地平流及140°W输送的联系较弱，不宜把它直接写成输送原因。',
          '30/50/75m检查均未使TNA或PMM的主设定局地平流区间稳定排除零。保留TNA为优先补充试验，PMM/北太平洋为对照；不将任一分支升为主线。',
          '首轮PMM输送区间下限约+0.05 Sv，本轮约−0.06 Sv；点估计完全相同，差别来自事先固定的不同bootstrap抽样序列。它处在蒙特卡洛区间边缘，不能强调显著性跨越。','',
          summary.to_string(index=False),'',
          '图1：三次事件的外部海温、PMM、风应力、暖水输送和两个局地平流项；灰色为JAS。',
          '图2：TNA与PMM对五个响应的条件回归，实心点为组内模型，空心点为两组联合；横线为逐项区间。',
          '不把温度异常平流项等同于区域平均温度梯度，不把异常流项等同于纯风驱贡献。',
          '0—30/50/75m全部局地结果存入同表；未解析垂向/混合/同化项仍未闭合。',
          '选图时保留不支持和反向结果的档案；不能把后筛选的同一43年资料称为独立验证。']
    (OUT/'过程结果与解释.txt').write_text('\n'.join(text),encoding='utf-8')
    qa.update(fits=len(m),all_target_years_included=True,monthly_field_count=516,
              max_coefficient_check_error=float(m.coefficient_check_error.max()))
    dump('numerical_validation.json',qa)
    sources=[CACHE,Path(__file__),PREV/'monthly_inputs.csv',PREV/'annual_inputs_all_settings.csv',
             OUT/'过程核对事前约定.txt',screen.BASE/'atmosphere_anomaly_and_reference.csv']
    manifests=[]
    for p in sources:
        with p.open('rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
        manifests.append(dict(path=str(p.relative_to(ROOT)),sha256=sha,bytes=p.stat().st_size))
    dump('source_manifest.json',manifests)
    print(summary.to_string(index=False),flush=True)


def main():
    assert (OUT/'过程核对事前约定.txt').is_file()
    if '--render-only' in sys.argv:
        c=pd.read_csv(OUT/'all_process_coefficients.csv')
        m=pd.read_csv(OUT/'all_model_comparisons.csv')
        monthly=pd.read_csv(OUT/'monthly_process_chain.csv')
        qa=json.loads((OUT/'numerical_validation.json').read_text())
        figures(c,monthly);report(c,m,qa)
        return
    local,scalars,qa=local_fields();print('full-period local diagnostics complete',flush=True)
    c,m,monthly,err=analyze(local);qa['previous_transport_coefficients_max_error']=err
    figures(c,monthly);report(c,m,qa)


if __name__=='__main__':main()
