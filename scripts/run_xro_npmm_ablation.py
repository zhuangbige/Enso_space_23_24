#!/usr/bin/env python3
"""Official XRO 1.0.1 core with past-only NPMM ablations on local data.

This is an ERSSTv5 + PMEL application, not a numerical reproduction of the
paper's ORAS5 hindcasts. Vendor code is kept unchanged with its license.
"""
from pathlib import Path
import os
import sys
import json
import hashlib
import time
import warnings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/xro_npmm_ablation_2015_2026'
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'fits').mkdir(exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/ro_pmm_mpl'))
sys.path.insert(0, str(ROOT / 'scripts/vendor/xro_1_0_1'))
import numpy as np
import pandas as pd
import xarray as xr
import xarray.core.groupby  # upstream accessor registration expects this submodule imported
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from XRO import XRO
FIT_WARNING_COUNTS = {}
AUDIT_STATUS = ('2026-10-14 核查：本轮输入与前处理尚未验证为可靠XRO基准；'
                '消融数值只作为敏感性试验记录。详见 audit_20261014/audit_notes_cn.txt。')

VARS = ['Nino34', 'WWV', 'NPMM', 'SPMM', 'IOB', 'IOD', 'SIOD', 'TNA', 'ATL3', 'SASD']
BOXES = {
    'Nino34': (-5,5,190,240), 'NPMM': (10,25,200,240), 'SPMM': (-25,-15,250,270),
    'IOB': (-20,20,40,100), 'IODw': (-10,10,50,70), 'IODe': (-10,0,90,110),
    'SIODe': (-30,-5,90,120), 'SIODw': (-25,-10,65,85),
    'TNA': (5,25,305,345), 'ATL3': (-3,3,340,360),
    'SASD_SW': (-45,-35,300,360), 'SASD_NE': (-30,-20,320,380),
}
LEADS, NSTEPS, TREND_ORDER = 12, 10, 2
MODEL = XRO(ncycle=12, ac_order=2, is_forward=True)
COLORS = {'Observed':'#202833', 'XRO_full':'#D55E00', 'XRO_noNPMM_refit':'#2878B5',
          'XRO_NPMM_init0':'#009E73', 'NRO':'#888888'}
LABELS = {'Observed':'Observed', 'XRO_full':'Full XRO', 'XRO_noNPMM_refit':'XRO without NPMM (refit)',
          'XRO_NPMM_init0':'Full XRO, initial NPMM = 0', 'NRO':'Nonlinear RO'}
MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']


def read_raw():
    sstpath = ROOT / 'data/raw/ersstv5_sst_monthly_full.nc'
    sst = xr.open_dataset(sstpath, engine='netcdf4').sst.sel(time=slice('1980-01',None)).sortby('lat')
    assert sst.attrs['units'] == 'degC'
    dates = pd.DatetimeIndex(sst.time.values)
    assert dates.equals(pd.date_range(dates[0], dates[-1], freq='MS'))
    d, coverage = {}, {}
    for name, (south,north,west,east) in BOXES.items():
        # Modular longitude selection includes the SASD sector across Greenwich
        # exactly once; latitude weights are normalized over valid ocean cells.
        a = sst.sel(lat=slice(south,north))
        a = a.sel(lon=((a.lon-west)%360 <= east-west+1e-7)).load()
        assert a.sizes['lat'] and a.sizes['lon']
        weights = np.cos(np.deg2rad(a.lat))
        d[name] = a.weighted(weights).mean(('lat','lon')).values
        coverage[name] = {'nlat': a.sizes['lat'], 'nlon': a.sizes['lon'],
                          'min_valid_ocean_cells': int(a.notnull().sum(('lat','lon')).min())}
    d['IOD'] = d.pop('IODw')-d.pop('IODe')
    d['SIOD'] = d.pop('SIODe')-d.pop('SIODw')
    d['SASD'] = d.pop('SASD_SW')-d.pop('SASD_NE')
    wwvpath = ROOT / 'data/raw/godas/authoritative_recharge_sections/pmel_tao_wwv.dat'
    wwv = pd.read_csv(wwvpath, sep=r'\s+', skiprows=6, names=['date','total','official_anomaly'])
    ht = pd.DatetimeIndex(pd.to_datetime(wwv.date.astype(str), format='%Y%m'))
    hs = pd.Series(wwv.total.to_numpy()/1e14, index=ht)
    d['WWV'] = hs.reindex(dates).to_numpy()
    raw = pd.DataFrame(d, index=dates)[VARS]
    assert np.isfinite(raw.to_numpy()).all()
    raw.index.name = 'time'
    raw.to_csv(OUT / 'raw_xro_indices_1980_2026.csv')
    inputs = [{'path':str(p.relative_to(ROOT)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in [sstpath,wwvpath]]
    return raw, hs, {'inputs':inputs, 'boxes':BOXES, 'coverage':coverage,
                     'sst_end':str(dates[-1].date()), 'wwv_end':str(ht[-1].date())}


def anomalies(raw, year, order=TREND_ORDER):
    dates = raw.index
    train = dates.year < year
    assert dates[0].month == 1 and dates[train][-1].month == 12
    a = raw.to_numpy(float)
    clim = np.stack([a[train & (dates.month==m)].mean(axis=0) for m in range(1,13)])
    a = a-clim[dates.month-1]
    t = (np.arange(len(dates))-np.flatnonzero(train).mean())/12
    design = np.column_stack([t**k for k in range(order+1)])
    beta = np.linalg.lstsq(design[train], a[train], rcond=None)[0]
    result = pd.DataFrame(a-design@beta,index=dates,columns=raw.columns)
    return result


def as_dataset(frame):
    return xr.Dataset({v:('time',frame[v].to_numpy()) for v in frame}, coords={'time':frame.index.values})


def fit_model(frame):
    # These masks are the control configuration in the official cookbook.
    ds = as_dataset(frame)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',RuntimeWarning)
        fit = MODEL.fit_matrix(ds, maskb=['IOD'] if 'IOD' in frame else [], maskc=[],
                               maskNT=['T2','TH'], maskNH=[])
    for warning in caught:
        message=str(warning.message)
        FIT_WARNING_COUNTS[message]=FIT_WARNING_COUNTS.get(message,0)+1
    for k in ['Lac','NLb_Lac','NLc_Lac','NROT_Lac','NROH_Lac']:
        assert np.isfinite(fit[k]).all(), k
    return fit


def forecast(fit, state, month, nstep=NSTEPS):
    # Call the unchanged upstream kernel with the ACTUAL calendar month. The
    # public reforecast wrapper assumes successive initializations are monthly.
    out = MODEL._integration_forecast(fit, np.asarray(state,float), month-1,
                                     n_month=LEADS,nstep=nstep,ncopy=1,noise_type='zero')
    values = out.isel(member=0).values.T
    assert np.allclose(values[0],state)
    return values


def cut_outgoing(fit, receivers):
    modified = fit.copy(deep=True)
    # rankx is the source, ranky is the receiving tendency; NPMM is rank 3.
    for key in ['Lac','Lcoef','Lcomp']:
        modified[key].loc[{'rankx':3,'ranky':receivers}] = 0
    assert np.all(modified.Lac.sel(rankx=3,ranky=receivers).values == 0)
    return modified


def run_experiments(raw, hseries):
    rows, audits, qa = [], [], {}
    hraw = hseries.loc[raw.index[0]:].to_frame('WWV')
    # Pre-declared event and historical windows, same in all model families.
    for year in range(2000,2027):
        started=time.time()
        a = anomalies(raw,year)
        ah = anomalies(hraw,year)
        assert np.allclose(a.WWV,ah.loc[a.index,'WWV'])
        train = a.loc[:f'{year-1}-12']
        assert train.index.max() < pd.Timestamp(year,1,1)
        specs = {'XRO_full':VARS, 'XRO_noNPMM_refit':[v for v in VARS if v!='NPMM'],
                 'NRO':['Nino34','WWV'], 'NRO_NPMM':['Nino34','WWV','NPMM']}
        fits = {name:fit_model(train[variables]) for name,variables in specs.items()}
        init_dates = a.index[a.index.year==year]
        if year in [2015,2026]:
            a.to_csv(OUT / f'processed_indices_before_{year}.csv')
            for name,fit in fits.items():
                fit.to_netcdf(OUT / f'fits/{name}_{year}.nc',engine='netcdf4')
            fits.update({
                'XRO_cut_NPMM_to_T':cut_outgoing(fits['XRO_full'],[1]),
                'XRO_cut_NPMM_to_H':cut_outgoing(fits['XRO_full'],[2]),
                'XRO_cut_all_NPMM_out':cut_outgoing(fits['XRO_full'],[i for i in range(1,11) if i!=3]),
            })
            for key in list(fits):
                if key.startswith('XRO_cut'):
                    specs[key]=VARS
        fits['XRO_NPMM_init0']=fits['XRO_full']
        specs['XRO_NPMM_init0']=VARS
        for name,fit in fits.items():
            variables=specs[name]
            for ini in init_dates:
                # Pathway interventions only need the requested event starts.
                if name.startswith('XRO_cut') and ini.month not in [1,3,5]:
                    continue
                state=a.loc[ini,variables].to_numpy().copy()
                if name=='XRO_NPMM_init0':
                    state[variables.index('NPMM')]=0
                fc=forecast(fit,state,ini.month)
                for lead in range(LEADS+1):
                    target=ini+pd.DateOffset(months=lead)
                    rows.append({'init':ini,'year':year,'month':ini.month,'target':target,'lead':lead,
                                 'model':name,'Nino34':fc[lead,0],'WWV':fc[lead,1],
                                 'obs_Nino34':a.Nino34.get(target,np.nan),'obs_WWV':ah.WWV.get(target,np.nan),
                                 'sd_Nino34':train.Nino34.std(),'sd_WWV':train.WWV.std(),
                                 'training_end':train.index.max(),
                                 'NPMM_initial':a.NPMM.loc[ini],
                                 'finite_forecast':bool(np.isfinite(fc[lead]).all())})
        audits.append({'year':year,'train_start':train.index[0],'train_end':train.index[-1],
                       'train_months':len(train),'NPMM_initial_Jan':a.NPMM.loc[f'{year}-01-01'],
                       'NPMM_sd':train.NPMM.std(),'WWV_sd':train.WWV.std()})
        if year==2015:
            altered=raw.copy()
            altered.loc[altered.index>pd.Timestamp('2015-01-01')]+=4.0
            altered_a=anomalies(altered,year)
            assert np.allclose(altered_a.loc[:'2015-01'],a.loc[:'2015-01'],atol=1e-12)
            altered_fit=fit_model(altered_a.loc[:'2014-12'])
            change=float(abs(altered_fit.Lac-fits['XRO_full'].Lac).max())
            qa['future_perturbation_fit_max_difference']=change
            assert change<1e-10
            v=a.loc['2015-03-01',VARS].to_numpy()
            ten=forecast(fits['XRO_full'],v,3)
            twenty=forecast(fits['XRO_full'],v,3,nstep=20)
            qa['march2015_step10_vs20_max_T_difference_C']=float(max(abs(ten[:,0]-twenty[:,0])))
            # Public API parity on contiguous starts verifies seasonal indexing.
            public=MODEL.reforecast(fits['XRO_full'],as_dataset(a.loc['2015-01':'2015-03']),
                                    n_month=LEADS,nstep=NSTEPS,noise_type='zero')
            assert np.allclose(public.Nino34.isel(init=2),ten[:,0],atol=1e-12)
            qa['official_public_api_parity']=True
            # Cutting all outgoing paths must make ENSO independent of P0.
            cut=fits['XRO_cut_all_NPMM_out']
            shifted=v.copy(); shifted[2]+=2
            effect=forecast(cut,shifted,3)[:,:2]-forecast(cut,v,3)[:,:2]
            assert np.max(abs(effect))<1e-12
            qa['cut_all_outgoing_P0_effect_on_ENSO']=float(np.max(abs(effect)))
        print(f'Fold {year}: {len(train)} training months, {time.time()-started:.1f}s',flush=True)
    frame=pd.DataFrame(rows)
    frame.to_csv(OUT/'all_forecasts.csv',index=False)
    pd.DataFrame(audits).to_csv(OUT/'training_audit.csv',index=False)
    qa['nonfinite_forecast_rows']=int((~frame.finite_forecast).sum())
    # Do not remove unstable forecasts to make skill appear better.
    assert qa['nonfinite_forecast_rows']==0, 'Unstable forecasts recorded; investigate before claiming skill.'
    return frame,qa


def score(frame):
    historical=frame[frame.year.between(2000,2024)&frame.lead.gt(0)]
    skill=[]
    for (name,lead),g in historical.groupby(['model','lead']):
        for var in ['Nino34','WWV']:
            err=g[var]-g['obs_'+var]
            skill.append({'model':name,'lead':lead,'variable':var,'n':len(g),
                          'rmse':np.sqrt(np.mean(err**2)),
                          'correlation':np.corrcoef(g[var],g['obs_'+var])[0,1]})
    pd.DataFrame(skill).to_csv(OUT/'historical_skill.csv',index=False)
    event=[]
    for (year,month,name),g in frame[frame.year.isin([2015,2026])&frame.month.isin([1,3,5])&frame.lead.gt(0)].groupby(['year','month','model']):
        for var in ['Nino34','WWV']:
            for window in [5,6,12]:
                gg=g[g.lead.le(window)].dropna(subset=['obs_'+var])
                if len(gg):
                    err=gg[var]-gg['obs_'+var]
                    event.append({'year':year,'month':month,'model':name,'variable':var,'horizon':window,
                                  'n_verified':len(gg),'verified_end':gg.target.max(),
                                  'rmse':np.sqrt(np.mean(err**2)),'bias':err.mean()})
    event=pd.DataFrame(event)
    event.to_csv(OUT/'event_skill.csv',index=False)
    keys=['year','month','variable','horizon','n_verified','verified_end']
    comparison=event.pivot(index=keys,columns='model',values='rmse').reset_index()
    comparison['NPMM_incremental_rmse_reduction_percent']=100*(1-comparison.XRO_full/comparison.XRO_noNPMM_refit)
    comparison.to_csv(OUT/'event_ablation_comparison.csv',index=False)
    # Same-metric phase-space validation, standardized only to combine units.
    phase=[]
    for (year,month,name),g in frame[frame.year.isin([2015,2026])&frame.month.isin([1,3,5])&frame.lead.gt(0)].groupby(['year','month','model']):
        g=g.dropna(subset=['obs_Nino34','obs_WWV'])
        if len(g):
            d=((g.Nino34-g.obs_Nino34)/g.sd_Nino34)**2+((g.WWV-g.obs_WWV)/g.sd_WWV)**2
            phase.append({'year':year,'month':month,'model':name,'n_verified':len(g),'rmse_phase_sd':np.sqrt(d.mean())})
    pd.DataFrame(phase).to_csv(OUT/'phase_space_skill.csv',index=False)
    # Paired 3-year moving-block bootstrap of full vs retrained no-NPMM errors.
    rng=np.random.default_rng(20261014)
    boot=[]
    for var in ['Nino34','WWV']:
        for lead in [1,3,6,9,12]:
            g=historical[(historical.lead==lead)&historical.model.isin(['XRO_full','XRO_noNPMM_refit'])].copy()
            g['error2']=(g[var]-g['obs_'+var])**2
            x=g.groupby(['year','model']).error2.mean().unstack()[['XRO_full','XRO_noNPMM_refit']].to_numpy()
            n=len(x); values=[]
            for k in range(4000):
                starts=rng.integers(0,n,int(np.ceil(n/3)))
                ix=((starts[:,None]+np.arange(3))%n).ravel()[:n]
                e=x[ix].mean(axis=0)
                values.append(100*(1-np.sqrt(e[0]/e[1])))
            e=x.mean(axis=0); lo,hi=np.percentile(values,[2.5,97.5])
            boot.append({'variable':var,'lead':lead,'rmse_reduction_percent':100*(1-np.sqrt(e[0]/e[1])),
                         'ci95_low_percent':lo,'ci95_high_percent':hi,'n_init_years':n})
    pd.DataFrame(boot).to_csv(OUT/'historical_paired_bootstrap.csv',index=False)
    return comparison


def savefig(fig,name):
    for ext in ['png','pdf']:
        fig.savefig(OUT/f'{name}.{ext}',dpi=220,bbox_inches='tight',facecolor='white')
    plt.close(fig)


def plot_interventions(frame):
    month=3
    cases={'XRO_NPMM_init0':('Initial NPMM = 0','#009E73','-'),
           'XRO_cut_NPMM_to_T':('Cut NPMM → SST','#2878B5',':'),
           'XRO_cut_NPMM_to_H':('Cut NPMM → WWV','#D55E00','--'),
           'XRO_cut_all_NPMM_out':('Cut all outgoing NPMM links','#8c62aa','-.')}
    deltas=[]
    fig,axes=plt.subplots(2,2,figsize=(12,7.5),sharex=True,sharey='row')
    fig.subplots_adjust(top=.77,bottom=.20,wspace=.16,hspace=.30)
    fig.suptitle('Experimental XRO: NPMM pathway sensitivity | March start',y=.98,fontsize=15)
    handles=[Line2D([0],[0],color=c,ls=ls,lw=2,label=label) for label,c,ls in cases.values()]
    fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.5,.935),frameon=False,fontsize=9.5)
    for col,year in enumerate([2015,2026]):
        g=frame[(frame.year==year)&(frame.month==month)]
        full=g[g.model=='XRO_full'].set_index('lead')
        for case,(label,color,ls) in cases.items():
            other=g[g.model==case].set_index('lead')
            for row,var in enumerate(['Nino34','WWV']):
                delta=full[var]-other[var]
                axes[row,col].plot(delta.index,delta,color=color,ls=ls,lw=2.2)
                for lead,value in delta.items():
                    deltas.append({'year':year,'init_month':month,'lead':lead,'variable':var,
                                   'intervention':case,'full_minus_intervention':value})
        for row,var in enumerate(['Nino34','WWV']):
            ax=axes[row,col]
            ax.axhline(0,lw=.8,color='.4');ax.grid(alpha=.15)
            ax.set(title=f'{year} | '+('Niño3.4' if row==0 else 'WWV'),xlim=(0,12),xticks=[0,3,6,9,12])
            if col==0: ax.set_ylabel('Δ Niño3.4 (°C)' if row==0 else r'Δ WWV ($10^{14}$ m$^3$)')
            if row==1: ax.set_xlabel('Lead time (months)')
    fig.text(.065,.035,'Curves show FULL minus INTERVENTION, with full-model coefficients otherwise unchanged; these are forecast changes, not skill gains.\n'
             'Initial-state neutralization differs from removing NPMM throughout integration. Direct path cuts retain indirect routes through other modes.\n'
             'Input/preprocessing baseline is under audit. Effects need not add; these are model sensitivities, not real-world causal estimates.',
             fontsize=8.6,color='#4e5660',linespacing=1.6,va='bottom')
    savefig(fig,'xro_pathway_sensitivity_init_03')
    pd.DataFrame(deltas).to_csv(OUT/'pathway_sensitivity.csv',index=False)


def trend_sensitivity(raw,h):
    """Report linear-trend alternative; never select a winner on event skill."""
    rows=[]
    for year in [2015,2026]:
        a=anomalies(raw,year,order=1)
        ah=anomalies(h.loc[raw.index[0]:].to_frame('WWV'),year,order=1)
        train=a.loc[:f'{year-1}-12']
        for name,variables in {'XRO_full':VARS,'XRO_noNPMM_refit':[v for v in VARS if v!='NPMM']}.items():
            fit=fit_model(train[variables])
            for month in [1,3,5]:
                ini=pd.Timestamp(year,month,1)
                fc=forecast(fit,a.loc[ini,variables].to_numpy(),month)
                assert np.isfinite(fc).all()
                for iv,var in enumerate(['Nino34','WWV']):
                    truth=a[var] if var=='Nino34' else ah.WWV
                    times=pd.date_range(ini+pd.DateOffset(months=1),periods=LEADS,freq='MS')
                    y=truth.reindex(times).to_numpy()
                    ok=np.isfinite(y)
                    rows.append({'year':year,'month':month,'model':name,'variable':var,
                                 'trend_order':1,'n_verified':int(ok.sum()),
                                 'rmse':float(np.sqrt(np.mean((fc[1:,iv][ok]-y[ok])**2)))})
    linear=pd.DataFrame(rows)
    linear.to_csv(OUT/'linear_trend_sensitivity.csv',index=False)
    return linear


def write_notes(comparison,linear,qa):
    lines=[
        '官方 XRO 核心的 NPMM 消融实验：2015 与 2026（2026-10-14）',
        AUDIT_STATUS,
        '',
        '本轮已完成：',
        '1. 固定使用 XRO 1.0.1 本地官方代码副本，保留许可证和文件哈希；未修改其拟合与积分核心。',
        '2. 按官方 Cookbook 控制配置：年度及半年度季节项、SST 方程 T²和T×H 项、IOD 方程 IOD²项。',
        '3. 用 ERSSTv5 与 PMEL 建立1980–2026年6月完整十状态输入，WWV另可验证至7月。',
        '4. 每年只用此前数据估计气候态、二次趋势及模型系数；完成2000–2024年逐月起报历史检验及2015/2026事件实验。',
        '5. 生成1/3/5月起报的时间序列和横轴Niño3.4、纵轴WWV相图，另有3月起报的路径敏感性图。',
        '',
        '数据与模型边界：',
        '本轮是官方 XRO 动力核心在 ERSSTv5+PMEL 上的应用；不是原论文 ORAS5 数据与技巧数值的完整复现。',
        '官方 NPMM 是10–25N、160–120W区域SST型指数；本轮沿用此定义。它与此前联合SST–风EOF PMM-like指数不同。',
        'WWV使用PMEL总体积重新去气候态/趋势，单位10^14 m³；官方示例中名为WWV的变量实际是区域平均D20，单位m。',
        '区域均值按有效海洋格点余弦纬度加权；跨0°经线的SASD区域不截断，格点不重复计入。',
        '历史资料有修订，未模拟当时发布时滞；起报月是整月平均，仅在该月结束后可获得。',
        '使用官方零随机扰动积分作确定性对照；不是随机集合均值。未向任何预报输入未来实测模态。',
        '',
        '消融设计：',
        'XRO_full：十状态完整模型。',
        'XRO_noNPMM_refit：删除NPMM后，用同样训练时段重新拟合九状态模型。衡量其他模态已知时，NPMM的条件增量预测价值。',
        'XRO_NPMM_init0：保持完整模型系数，只将起报时NPMM异常置零；之后NPMM仍自行演变，也可被ENSO再激发。衡量初值敏感性。',
        'XRO_cut_NPMM_to_T / _to_H：分别关闭NPMM→SST、NPMM→WWV的全部季节性直接耦合系数，其他参数不动；间接路径仍存在。',
        'XRO_cut_all_NPMM_out：关闭NPMM向其他所有状态的作用；包括通过其他海盆的间接入口。',
        'NRO / NRO_NPMM：用同一个官方核心，分别只训练二状态与三状态，保留一致的ENSO非线性和季节项。',
        '初值归零、固定系数路径干预、删变量重训回答不同问题，不应统一称为PMM因果贡献。',
        '',
        '主对照：完整XRO相对删除NPMM后重训的模型，RMSE下降百分比（负值表示恶化）。',
    ]
    for r in comparison[comparison.horizon==12].itertuples():
        lines.append(f'{r.year}年{r.month}月起报，{r.variable}，验证{r.n_verified}个月至{r.verified_end:%Y-%m}：'
                     f'{r.XRO_noNPMM_refit:.3f} → {r.XRO_full:.3f}；下降{r.NPMM_incremental_rmse_reduction_percent:.1f}%。')
    lines += ['', '解释：',
              '2015年各起报月的Niño3.4误差下降，但WWV误差增加。完整模型仍低估2015暖事件的峰值和后期放电。',
              '2026年可验证的SST样本很短，尤其5月起报仅有6月一个验证点；其百分比不能作为稳定技巧估计。',
              '2000–2024历史检验的各预设提前期（1/3/6/9/12月），Niño3.4和WWV增益的三年块自助95%区间均跨零；尚不能认定稳定增益。',
              '在此未验证基准下，3月起报的路径干预对NPMM→WWV更敏感；该结果不能据以判断稳健机制。',
              '2015年11月：切断NPMM→WWV后，Niño3.4预测约下降0.59℃；只切断NPMM→SST则约下降0.01℃。路径效应存在非线性互动，不能直接相加。',
              '数据源、NPMM定义及去趋势阶数都改变了，所以本轮增益不能与前一轮线性RO百分比直接相减。',
              '', '去趋势敏感性：',
              '额外报告线性去趋势替代方案，只作敏感性检验，不根据事件结果选择更好看的方案。']
    lp=linear.pivot(index=['year','month','variable','n_verified'],columns='model',values='rmse').reset_index()
    for r in lp.itertuples():
        gain=100*(1-r.XRO_full/r.XRO_noNPMM_refit)
        lines.append(f'线性趋势：{r.year}/{r.month:02d} {r.variable}，验证{r.n_verified}个月，NPMM增益{gain:.1f}%。')
    lines += ['', '验证：',json.dumps(qa,ensure_ascii=False,indent=2),
              '部分噪声阻尼诊断量会因负滞后相关而出现无定义的log/power；它们不进入本次零噪声积分。所有参与积分的动力系数和预报均为有限值。',
              '路径干预属于模型内敏感性实验，不能据此认定真实世界的因果效应。',
              '', '参考：',
              'https://github.com/senclimate/XRO',
              'https://www.nature.com/articles/s41586-024-07534-6',
              'https://raw.githubusercontent.com/senclimate/XRO/main/XRO/state.py',
              'https://raw.githubusercontent.com/senclimate/XRO/main/notebooks/XRO_realtime_states_forecasts.ipynb']
    (OUT/'experiment_notes_cn.txt').write_text('\n'.join(lines)+'\n')


def plot(frame):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,
                         'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    names=['Observed','XRO_full','XRO_noNPMM_refit']
    handles=[Line2D([0],[0],color=COLORS[n],lw=2.2,label=LABELS[n],
                    ls='--' if n=='XRO_noNPMM_refit' else '-') for n in names]
    focal=frame[frame.year.isin([2015,2026])&frame.month.isin([1,3,5])&frame.model.isin(names)]
    limits={}
    for var in ['Nino34','WWV']:
        allvalues=np.r_[focal[var],focal['obs_'+var].dropna()]
        lo,hi=np.nanmin(allvalues),np.nanmax(allvalues)
        limits[var]=(lo-.12*(hi-lo),hi+.14*(hi-lo))
    for month in [1,3,5]:
        fig,axes=plt.subplots(2,2,figsize=(12,8),sharex='col',sharey='row')
        fig.subplots_adjust(top=.82,bottom=.23,hspace=.30,wspace=.14)
        fig.suptitle(f'Experimental XRO: NPMM ablation | {MONTHS[month-1]} initialization',y=.98,fontsize=16)
        fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.935),ncol=3,frameon=False)
        fig.text(.5,.866,'Input / preprocessing sensitivity experiment; baseline validation pending',
                 ha='center',fontsize=9,color='#9a4935')
        for col,year in enumerate([2015,2026]):
            g=focal[(focal.year==year)&(focal.month==month)]
            base=g[g.model=='XRO_full'].sort_values('lead')
            for row,var in enumerate(['Nino34','WWV']):
                ax=axes[row,col]
                if year==2026:
                    end=base.loc[base['obs_'+var].notna(),'lead'].max()
                    ax.axvspan(end+.15,12.2,color='#edf0f3',zorder=-2)
                    if row==0:
                        ax.text((end+12)/2,.95,'No local observations',transform=ax.get_xaxis_transform(),
                                ha='center',va='top',fontsize=8.5,color='#66717a')
                for name in names:
                    d=base if name=='Observed' else g[g.model==name].sort_values('lead')
                    ax.plot(d.lead,d['obs_'+var] if name=='Observed' else d[var],color=COLORS[name],
                            lw=2.2,ls='--' if name=='XRO_noNPMM_refit' else '-',
                            marker='o' if name=='Observed' else None,ms=3.5,zorder=5 if name=='Observed' else 3)
                ax.scatter(0,base['obs_'+var].iloc[0],s=100,marker='*',color=COLORS['Observed'],zorder=8)
                ax.axhline(0,lw=.7,color='.5'); ax.grid(axis='y',alpha=.15)
                ax.set(xlim=(-.2,12.2),ylim=limits[var],title=f'{chr(97+row*2+col)}) {year} — '+('Niño3.4' if row==0 else 'WWV'))
                ax.set_xticks(range(0,13,2),[MONTHS[(month-1+l)%12]+('\n+1 yr' if month-1+l>=12 else '') for l in range(0,13,2)])
                if col==0: ax.set_ylabel('Niño3.4 anomaly (°C)' if row==0 else r'WWV anomaly ($10^{14}$ m$^3$)')
                if row==1: ax.set_xlabel('Target month')
        fig.text(.06,.035,'Full XRO: 10 states. Ablation: remove NPMM and re-fit 9 states; SPMM and other basin modes retained.\n'
                 'Official XRO 1.0.1 core; cookbook nonlinear terms and seasonality. ERSSTv5 + PMEL, not the paper\'s ORAS5 experiment.\n'
                 'Training: 1980–2014 / 1980–2025. Monthly climatology and quadratic trend fitted on past data only.\n'
                 'Zero-noise trajectories; future climate modes evolve internally. 2026 SST available through June; WWV through July.',
                 fontsize=8.5,linespacing=1.6,color='#4e5660',va='bottom')
        savefig(fig,f'xro_time_series_init_{month:02d}')

        fig,axes=plt.subplots(1,2,figsize=(12,6.5),sharex=True,sharey=True)
        fig.subplots_adjust(top=.80,bottom=.25,wspace=.13)
        fig.suptitle(f'Experimental XRO phase space | {MONTHS[month-1]} initialization',y=.98,fontsize=16)
        fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.935),ncol=3,frameon=False)
        fig.text(.5,.866,'Input / preprocessing sensitivity experiment; baseline validation pending',
                 ha='center',fontsize=9,color='#9a4935')
        for ax,year in zip(axes,[2015,2026]):
            g=focal[(focal.year==year)&(focal.month==month)]
            base=g[g.model=='XRO_full'].sort_values('lead')
            for name in names:
                d=base if name=='Observed' else g[g.model==name].sort_values('lead')
                pre='obs_' if name=='Observed' else ''
                d=d.dropna(subset=[pre+'Nino34',pre+'WWV'])
                x,y=d[pre+'Nino34'].to_numpy(),d[pre+'WWV'].to_numpy()
                ax.plot(x,y,color=COLORS[name],lw=2.1,marker='o',ms=3,
                        ls='--' if name=='XRO_noNPMM_refit' else '-',zorder=5 if name=='Observed' else 3)
                for k in range(1,len(x)):
                    lead=int(d.lead.iloc[k])
                    if lead%3==0 or k==len(x)-1:
                        ax.annotate('',xy=(x[k],y[k]),xytext=(x[k-1],y[k-1]),
                                    arrowprops={'arrowstyle':'->','lw':1.4,'color':COLORS[name]})
                        if name=='Observed' or k==len(x)-1:
                            text=MONTHS[(month-1+lead)%12]+(' +1' if month-1+lead>=12 else '')
                            ax.annotate(text,(x[k],y[k]),xytext=(5,8 if name!='XRO_noNPMM_refit' else -15),
                                        textcoords='offset points',color=COLORS[name],fontsize=8)
            ax.scatter(base.obs_Nino34.iloc[0],base.obs_WWV.iloc[0],s=120,marker='*',color='#202833',zorder=9)
            ax.axhline(0,color='.5',lw=.7);ax.axvline(0,color='.5',lw=.7);ax.grid(alpha=.15)
            ax.set(xlim=limits['Nino34'],ylim=limits['WWV'],xlabel='Niño3.4 anomaly (°C)',title=str(year))
        axes[0].set_ylabel(r'WWV anomaly ($10^{14}$ m$^3$)')
        fig.text(.06,.035,'Star: shared initial Niño3.4 / WWV. Arrows: time direction. Forecast horizon: 12 months.\n'
                 'The observed 2026 phase trajectory ends in June. Both models use the same past-only anomaly baseline.\n'
                 'Official XRO core applied to ERSSTv5 + PMEL; the removed variable is regional SST NPMM (10–25°N, 160–120°W).',
                 fontsize=8.7,linespacing=1.7,color='#4e5660',va='bottom')
        savefig(fig,f'xro_phase_space_init_{month:02d}')


def main():
    started=time.time()
    raw,h,metadata=read_raw()
    print('Raw states available:',raw.index[0],raw.index[-1],flush=True)
    frame,qa=run_experiments(raw,h)
    comparison=score(frame)
    plot(frame)
    plot_interventions(frame)
    linear=trend_sensitivity(raw,h)
    qa['upstream_fit_warning_counts']=FIT_WARNING_COUNTS
    write_notes(comparison,linear,qa)
    metadata.update({'audit_status':AUDIT_STATUS,
                     'official_source':json.loads((ROOT/'scripts/vendor/xro_1_0_1/provenance.json').read_text()),
                     'parameters':{'ac_order':2,'is_forward':True,'maskb':['IOD'],'maskNT':['T2','TH'],
                                   'maskNH':[],'maskc':[],'noise_type':'zero','nstep':NSTEPS,'lead_months':LEADS},
                     'preprocessing':'Each year: monthly climatology and quadratic trend on 1980 through previous December only.',
                     'data_application':'ERSSTv5 regional SST indices and raw PMEL WWV; not a reproduction of the paper ORAS5 scores.',
                     'PMM_definition':'NPMM 10–25N,160–120W regional SST; no regression of ENSO removed. Differs from earlier joint EOF.',
                     'ablation_definitions':{
                         'XRO_noNPMM_refit':'Remove NPMM input/state and refit all remaining equations, including residual parameters.',
                         'XRO_NPMM_init0':'Keep full coefficients; set ONLY initial NPMM anomaly to zero; it evolves and can be regenerated.',
                         'XRO_cut_NPMM_to_T':'Keep full coefficients except NPMM-source/Nino34-tendency linear coefficients at all seasons.',
                         'XRO_cut_NPMM_to_H':'Keep full coefficients except NPMM-source/WWV-tendency linear coefficients at all seasons.',
                         'XRO_cut_all_NPMM_out':'Cut all off-diagonal outgoing NPMM links, including routes through other modes.',
                         'NRO':'Same official nonlinear and seasonal core trained using only Nino34/WWV.',
                         'NRO_NPMM':'Same core trained using only Nino34/WWV/NPMM.'},
                     'limitations':['Historical reanalysis vintages/publication latency not represented.',
                                    'Zero-noise solution is not a nonlinear stochastic ensemble mean.',
                                    'Model interventions do not establish real-world causal effects.',
                                    'Future observed PMM never supplied; post-2026-June SST skill unavailable.'],
                     'validation':qa,'runtime_seconds':time.time()-started,
                     'sources':['https://github.com/senclimate/XRO','https://www.nature.com/articles/s41586-024-07534-6',
                                'https://raw.githubusercontent.com/senclimate/XRO/main/XRO/state.py']})
    (OUT/'methods_and_validation.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False))
    print(comparison[comparison.horizon==12][['year','month','variable','n_verified','XRO_full','XRO_noNPMM_refit','NPMM_incremental_rmse_reduction_percent']].to_string(index=False),flush=True)
    print(json.dumps(qa,indent=2),flush=True)
    print('Finished',OUT,flush=True)


if __name__=='__main__':
    main()
