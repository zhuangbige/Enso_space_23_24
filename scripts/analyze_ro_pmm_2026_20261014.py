"""2026 counterpart of the manuscript-style 2015 free-evolution experiment."""
from pathlib import Path
import os
import json
import hashlib
import numpy as np
import pandas as pd
import xarray as xr
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'tmp/ro_pmm_mpl_2026'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import paper_ro_slim as slim
import run_paper_ro_pmm as base
from build_paper_ro_indices import d20,sst_index

RAW=ROOT/'data/raw/ro_pmm_2026_update_20261014'
REC=ROOT/'outputs/research_2026/pmm_mca_reconstruction_20261014'
OLD=ROOT/'outputs/research_2026/slim_RO_PMM_2015_manuscript_style_20261014'
OUT=ROOT/'outputs/research_2026/slim_RO_PMM_2026_manuscript_style_20261014'
OUT.mkdir(parents=True,exist_ok=True)
V=['Nino34','WWV'];P=['PMM_SST','PMM_wind']
MODELS={'RO':V,'RO_SST':V+[P[0]],'RO_wind':V+[P[1]],'RO_both':V+P}
COLORS={2:'#EDAF9D',3:'#E79783',4:'#DC7D69',5:'#C76C5C',6:'#B35B4E'}
LABELS={'RO':'RO','RO_SST':'RO + PMM-SST','RO_wind':'RO + PMM-wind',
    'RO_both':'RO + both','RO_SST_cut':'PMM-SST coupling cut','RO_both_cut':'Both PMM couplings cut'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load_current():
    raw=pd.read_csv(base.SOURCE/'raw_indices.csv',index_col=0,parse_dates=True)[V]
    s=sst_index(RAW/'ersstv5_nino34_2026.nc')
    with xr.open_dataset(RAW/'pottmp_2026_5S5N_120E80W.nc') as ds:
        a=ds.pottmp.where((abs(ds.lat)<=5)&(ds.lon>=120)&(ds.lon<=280),drop=True).load()
        assert a.attrs['units']=='K'
        h=d20(a.values.astype(float)-273.15,ds.level.values.astype(float))
        valid=np.isfinite(h);assert np.all(valid==valid[0])
        w=np.cos(np.deg2rad(a.lat.values.astype(float)))[:,None]*np.ones((1,a.sizes['lon']))
        w=np.where(valid[0],w,0)
        hs=pd.Series(np.nansum(h*w,axis=(1,2))/w.sum(),index=pd.DatetimeIndex(a.time.values))
        assert np.nanmin(h)>=0 and np.nanmax(h)<500
    new=pd.concat([s.rename(V[0]),hs.rename(V[1])],axis=1)
    qa={'latest_T':str(s.index[-1].date()),'latest_H':str(hs.index[-1].date()),
        'T_units':'degree_C','H_units':'m (area-mean D20, not volume)',
        'updated_overlap_max_abs':{v:float(abs(raw[v].reindex(new.index)-new[v]).max()) for v in V}}
    raw=pd.concat([raw.loc[raw.index<new.index.min()],new])
    raw.index.name='time';raw.to_csv(OUT/'observed_raw_indices.csv')
    p=pd.read_csv(RAW/'PMM_uw.txt',sep=r'\s+')
    p.index=pd.to_datetime(dict(year=p.Year,month=p.Mo,day=1))
    p=p[['SST','Wind']].rename(columns=dict(zip(['SST','Wind'],P)))
    reconstructed=pd.read_csv(REC/'ersst_fixed_r1_mca_monthly_reconstruction.csv',index_col=0,parse_dates=True)
    reconstructed=reconstructed.rename(columns={'SST':P[0]})
    reconstructed[P[1]]=np.nan
    return raw,p,reconstructed,qa


def convert_model(model):
    m=model.copy()
    for k in ['coef','scale']:m[k]=np.asarray(m[k])
    return m


def apply_meta(raw,pmm,meta):
    dates=raw.index
    bg=np.asarray(meta['clim'])[dates.month.to_numpy()-1]+np.column_stack([
        np.ones(len(dates)),slim.decimal_time(dates)-meta['center']])@np.asarray(meta['beta'])
    a=pd.DataFrame(raw[V].values-bg,index=dates,columns=V)
    a[P]=pmm.reindex(dates)-np.asarray(meta['pmm_mean'])
    return a


def evaluate(g,scale):
    result={}
    for j,v in enumerate(['T','H']):
        sub=g[[v,'obs_'+v]].dropna();e=sub[v]-sub['obs_'+v]
        result[v+'_n']=len(sub)
        result[v+'_RMSE']=float(np.sqrt(np.mean(e**2)))
        result[v+'_bias']=float(e.mean())
        result[v+'_r']=float(sub[v].corr(sub['obs_'+v])) if len(sub)>2 else np.nan
    both=g[['T','H','obs_T','obs_H']].dropna()
    result['TH_n']=len(both)
    result['TH_normalized_RMSE']=float(np.sqrt(np.mean(((both[['T','H']].values-both[['obs_T','obs_H']].values)/scale)**2)))
    return result


def run():
    raw,official,reconstructed,qa=load_current()
    saved=json.loads((OLD/'models_and_preprocessing.json').read_text())['paper_2002_2024']
    frozen={k:convert_model(m) for k,m in saved['fits'].items()}
    meta=saved['preprocessing']
    for k in ['clim','beta','pmm_mean']:meta[k]=np.asarray(meta[k])
    ao=apply_meta(raw,official,meta)
    ar=apply_meta(raw,reconstructed,meta)
    # Keep identical T/h processing; fit only PMM centering on 2002–2024.
    mr=dict(meta,pmm_mean=reconstructed.loc['2002':'2024'].mean().values)
    ac=apply_meta(raw,reconstructed,mr)
    fits={k:slim.fit(ac.loc['2002':'2024',cols]) for k,cols in MODELS.items() if k in ['RO','RO_SST']}
    np.testing.assert_allclose(fits['RO']['coef'],frozen['RO']['coef'],atol=1e-12)
    protocols={'official_JanFeb':(ao,frozen,meta,[1,2]),
        'frozen_official_model_reconstructed_input':(ar,{k:frozen[k] for k in ['RO','RO_SST']},meta,list(range(1,7))),
        'consistent_reconstruction':(ac,fits,mr,list(range(1,7)))}
    rows=[];allfits={};initial_checks=[];integration_checks=[]
    for protocol,(a,models,pre,months) in protocols.items():
        allfits[protocol]=dict(preprocessing=pre,fits=models)
        for name in list(models)+['RO_SST_cut']+(['RO_both_cut'] if 'RO_both' in models else []):
            cut=name.endswith('_cut');key=name[:-4] if cut else name
            m=models[key];cols=MODELS[key]
            for month in months:
                init=pd.Timestamp(2026,month,1);dates=pd.date_range(init,periods=10,freq='MS')
                x0=a.loc[init,cols].values;assert np.isfinite(x0).all()
                f=slim.predict(m,x0,month,months=9,cut_pmm=cut)
                np.testing.assert_allclose(f[0],x0,atol=1e-12)
                initial_checks.append(float(abs(f[0]-x0).max()))
                if name=='RO_SST':
                    f48=slim.predict(m,x0,month,months=9,steps=48)
                    integration_checks.append(float(abs(f48-f).max()))
                obs=a.reindex(dates)[V].values;restored=base.restore(f,dates,pre)
                for lead,target in enumerate(dates):
                    rows.append(dict(protocol=protocol,model=name,init=init,month=month,lead=lead,
                        target=target,T=f[lead,0],H=f[lead,1],obs_T=obs[lead,0],obs_H=obs[lead,1],
                        raw_T=restored[lead,0],raw_H=restored[lead,1],
                        initial_PMM_SST=float(a.loc[init,P[0]]+pre['pmm_mean'][0]),
                        initial_PMM_wind=float(a.loc[init,P[1]]+pre['pmm_mean'][1])))
        a.loc['2025':].to_csv(OUT/f'processed_states_{protocol}.csv',index_label='time')
    f=pd.DataFrame(rows);f.to_csv(OUT/'forecasts_2026.csv',index=False)
    scores=[];by_start=[]
    for (protocol,model),g in f[f.lead.between(1,9)].groupby(['protocol','model'],sort=False):
        main=g if protocol=='official_JanFeb' else g[g.month.between(2,6)]
        scores.append(dict(protocol=protocol,model=model,initializations='Jan-Feb' if protocol=='official_JanFeb' else 'Feb-Jun',
            **evaluate(main,frozen['RO']['scale'])))
        for month,gg in g.groupby('month'):
            by_start.append(dict(protocol=protocol,model=model,month=month,**evaluate(gg,frozen['RO']['scale'])))
    score=pd.DataFrame(scores)
    for protocol in protocols:
        sel=score.protocol.eq(protocol);ref=score[sel & score.model.eq('RO')].iloc[0]
        for v in ['T','H','TH_normalized']:
            score.loc[sel,v+'_RMSE_improvement_pct']=100*(1-score.loc[sel,v+'_RMSE']/ref[v+'_RMSE'])
    score.to_csv(OUT/'event_scores_2026.csv',index=False)
    pd.DataFrame(by_start).to_csv(OUT/'scores_by_initialization.csv',index=False)
    qa.update(training='2002-01 through 2024-12; 276 monthly states',
        TH_climatology='1991-2020',TH_trend_fit='2002-01 through 2025-04 (unchanged manuscript protocol)',
        MCA_and_calibration_fit='1950-2005',official_PMM_last='2026-02',
        reconstructed_PMM_last=str(reconstructed.index[-1].date()),
        no_post_initialization_forcing=True,initial_state_max_error=max(initial_checks),
        rk4_24_vs_48_max_difference=max(integration_checks),
        frozen_model_archive_sha256=sha(OLD/'models_and_preprocessing.json'),
        reconstructed_index_sha256=sha(REC/'ersst_fixed_r1_mca_monthly_reconstruction.csv'),
        reconstructed_components=['PMM_SST'],wind_extension_status='ERA5 queued; no post-Feb wind index inferred',
        evaluation='leads 1-9; observed target months only; overlapping initializations, not independent samples',
        operational_caveat='Monthly states become available after the month. This is a retrospective free-evolution analysis, not an archived real-time forecast.')
    assert max(integration_checks)<1e-5
    assert not f.duplicated(['protocol','model','init','lead']).any()
    assert f.loc[f.target>pd.Timestamp(qa['latest_T']),'obs_T'].isna().all()
    assert f.loc[f.target>pd.Timestamp(qa['latest_H']),'obs_H'].isna().all()
    (OUT/'numerical_QA.json').write_text(json.dumps(qa,indent=2))
    (OUT/'models_and_preprocessing.json').write_text(json.dumps(allfits,default=base.jsonable,indent=2))
    print(score.to_string(index=False),flush=True)
    return f,score,ac,ao,qa,frozen['RO']['scale']


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,
        'axes.titleweight':'bold','axes.labelsize':11,'xtick.direction':'in','ytick.direction':'in',
        'xtick.top':True,'ytick.right':True,'savefig.facecolor':'white','svg.fonttype':'none'})


def save(fig,stem):
    for ext in ['png','svg','pdf']:
        fig.savefig(OUT/f'{stem}.{ext}',dpi=220,bbox_inches='tight')
    plt.close(fig)


def plot_main(f,score,a,qa,scale):
    from plot_ro_pmm_2026_manuscript_style import render_main
    render_main(f,score,a,qa,scale,OUT)


def plot_validation():
    p=pd.read_csv(REC/'official_and_reconstructed_pmm.csv',index_col=0,parse_dates=True)
    diag=pd.read_csv(REC/'historical_validation.csv')
    fig,axs=plt.subplots(2,2,figsize=(12,7))
    panels=[(axs[0,0],'R1','SST','R1_original_source','(a) Original-source SST reconstruction'),
            (axs[0,1],'R1','Wind','R1_original_source','(b) Original-source wind reconstruction'),
            (axs[1,0],'ERSSTv5','SST','ERSSTv5_fixed_R1_mode','(c) ERSSTv5 SST reconstruction')]
    for ax,source,v,key,title in panels:
        sel=p.loc['2010':]
        ax.plot(sel.index,sel['official_'+v],c='#171717',lw=1,label='Official PMM')
        ax.plot(sel.index,sel[source+'_'+v],c='#C76C5C',lw=1,alpha=.85,label=source+' reconstruction')
        ax.axhline(0,c='.8',lw=.6);ax.set(title=title,ylabel='Official index scale')
        d=diag[(diag.source==key)&(diag.period=='heldout_2006_2024')&(diag.component==v)].iloc[0]
        ax.text(.02,.96,f'2006–2024: r = {d.r:.3f}; RMSE = {d.RMSE:.2f}',transform=ax.transAxes,va='top',fontsize=9,bbox=dict(fc='white',ec='none',alpha=.8))
        ax.legend(loc='lower left',fontsize=8,frameon=False)
    ax=axs[1,1];sel=p.loc['2026']
    ax.plot(sel.index,sel['ERSSTv5_SST'],'o-',c='#C76C5C',lw=1.8,label='ERSSTv5 reconstruction')
    ax.plot(sel.index,sel['official_SST'],'s',c='#171717',ms=6,label='Official (Jan–Feb only)')
    ax.axhline(0,c='.8',lw=.6);ax.set(title='(d) 2026 PMM-SST',ylabel='Official index scale')
    ax.set_xticks(sel.index,[x.strftime('%b') for x in sel.index]);ax.grid(alpha=.15);ax.legend(fontsize=8,frameon=False)
    fig.suptitle('PMM reconstruction check — frozen 1950–2005 calibration',fontsize=15)
    fig.text(.5,.01,'Fixed R1 MCA pattern; all official PMM values after 2005 are held out of calibration. Extension covers SST only.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.03,1,.96));save(fig,'figure_PMM_reconstruction_validation')


def source_sensitivity(a,scale):
    """Perturb initial PMM by held-out reconstruction RMSE; not a confidence interval."""
    validation=pd.read_csv(REC/'historical_validation.csv')
    d=validation[(validation.source=='ERSSTv5_fixed_R1_mode')&
                 (validation.period=='heldout_2006_2024')&(validation.component=='SST')].iloc[0]
    saved=json.loads((OUT/'models_and_preprocessing.json').read_text())
    m=convert_model(saved['consistent_reconstruction']['fits']['RO_SST'])
    rows=[];forecasts=[]
    for sign in [-1,0,1]:
        frame=[]
        for month in range(2,7):
            init=pd.Timestamp(2026,month,1);dates=pd.date_range(init,periods=10,freq='MS')
            x0=a.loc[init,MODELS['RO_SST']].values.copy();x0[2]+=sign*d.RMSE
            fc=slim.predict(m,x0,month,months=9);obs=a.reindex(dates)[V].values
            for lead,target in enumerate(dates):
                frame.append(dict(sign=sign,PMM_offset=sign*d.RMSE,init=init,target=target,lead=lead,
                    T=fc[lead,0],H=fc[lead,1],obs_T=obs[lead,0],obs_H=obs[lead,1]))
        ff=pd.DataFrame(frame);forecasts.append(ff)
        rows.append(dict(PMM_initial_offset=sign*d.RMSE,**evaluate(ff[ff.lead>0],scale)))
    pd.concat(forecasts).to_csv(OUT/'source_error_sensitivity_forecasts.csv',index=False)
    pd.DataFrame(rows).to_csv(OUT/'source_error_sensitivity_scores.csv',index=False)


def plot_official_control(f,ao,qa):
    fig,axs=plt.subplots(2,2,figsize=(11,6.6),sharex=True)
    variants=[('official_JanFeb','RO','RO','#999999','--'),
        ('official_JanFeb','RO_SST','Official PMM-SST','#2878B5','-'),
        ('frozen_official_model_reconstructed_input','RO_SST','Reconstructed PMM-SST','#C76C5C','-')]
    for col,month in enumerate([1,2]):
        for row,(v,field,unit) in enumerate([('T','Nino34','T (°C)'),('H','WWV','h (m)')]):
            ax=axs[row,col];last=pd.Timestamp(qa['latest_'+v])
            obs=ao.loc['2026',field].dropna();ax.plot(obs.index,obs.values,'o-',c='#171717',lw=2,ms=3,label='Observed')
            for protocol,model,label,color,linestyle in variants:
                sub=f[(f.protocol==protocol)&(f.model==model)&(f.month==month)]
                ax.plot(sub.target,sub[v],c=color,ls=linestyle,lw=1.6,label=label)
            ax.axvspan(last+pd.Timedelta(days=15),pd.Timestamp('2026-11-01'),color='.94',zorder=0)
            ax.axhline(0,c='.8',lw=.6);ax.grid(alpha=.15)
            ax.set(ylabel=unit,title=f'({chr(97+row*2+col)}) '+pd.Timestamp(2026,month,1).strftime('%B')+' initialization')
            ticks=pd.to_datetime(['2026-01-01','2026-04-01','2026-07-01','2026-10-01'])
            ax.set_xticks(ticks,['Jan\n2026','Apr','Jul','Oct']);ax.set_xlim(pd.Timestamp('2026-01-01'),pd.Timestamp('2026-11-01'))
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,ncol=4,loc='lower center',frameon=False,fontsize=9)
    fig.suptitle('Official vs reconstructed initialization — identical frozen model',fontsize=14)
    fig.tight_layout(rect=(0,.055,1,.95));save(fig,'figure_official_JanFeb_control')


def report(score,qa):
    main=score[score.protocol=='consistent_reconstruction']
    validation=pd.read_csv(REC/'historical_validation.csv')
    text='2026 年 RO + PMM 分析（2026-10-14 数据快照）\n\n'
    ro=main[main.model=='RO'].iloc[0];pmm=main[main.model=='RO_SST'].iloc[0];cut=main[main.model=='RO_SST_cut'].iloc[0]
    text+=f'主要结果：RO 加入重建 PMM-SST 后，T RMSE {ro.T_RMSE:.3f} → {pmm.T_RMSE:.3f} °C（改善 {pmm.T_RMSE_improvement_pct:.1f}%）；h RMSE {ro.H_RMSE:.3f} → {pmm.H_RMSE:.3f} m（改善 {pmm.H_RMSE_improvement_pct:.1f}%）。联合归一化 RMSE 改善 {pmm.TH_normalized_RMSE_improvement_pct:.1f}%。\n'
    text+=f'切断同一扩展模型中的 PMM→T/h 通道后，T/h RMSE 回升到 {cut.T_RMSE:.3f} °C / {cut.H_RMSE:.3f} m。这支持 PMM 通道在本次轨迹中有贡献，但不能把相对 RO 的全部改善都归为单一因果效应。\n'
    text+='保留原官方 PMM 模型、只更换 2026 起报输入的敏感性试验，T/h RMSE 均改善约 9.3%—9.4%，改善方向一致。两种模型仍明显低估实际增暖和热量积累：PMM 有增益，但尚不能解释 2026 年完整演变。\n\n'
    sensitivity=pd.read_csv(OUT/'source_error_sensitivity_scores.csv')
    text+=f'来源误差敏感性：将所有起报 PMM 同向加/减历史独立检验的一个 RMSE（{sensitivity.PMM_initial_offset.max():.3f} 指数单位），T RMSE 范围 {sensitivity.T_RMSE.min():.3f}—{sensitivity.T_RMSE.max():.3f} °C，h RMSE {sensitivity.H_RMSE.min():.3f}—{sensitivity.H_RMSE.max():.3f} m。这是确定性的输入扰动检验，不是置信区间，也不覆盖所有结构误差。\n\n'
    text+='主分析沿用原稿：sLIM 拟合 2002—2024，年周期+半年周期，二阶摄动解；T/h 气候态 1991—2020，去趋势系数固定于 2002-01—2025-04。\n'
    text+='h 是 GODAS 5S—5N、120E—80W 海域平均 D20，单位 m；不是体积单位的 WWV。\n\n'
    text+='数据截止：Niño3.4 '+qa['latest_T']+'；h '+qa['latest_H']+'；官方 PMM 2026-02；ERSSTv5 重建 PMM-SST '+qa['reconstructed_PMM_last']+'。\n'
    text+='官方 PMM 原始 NCEP/NCAR R1 在 2026-03 停更，因此不存在同源后续月度更新。本次为独立标注的 ERSSTv5 海温投影重建序列。ERA5 尚在服务端排队，后续月份的 PMM-wind/四变量扩展不填补、不评分；官方 1—2 月仍保留风指数对照。\n\n'
    text+='重建：NCEP R1 海洋 SST/10m u,v，175E—95W、21S—32N，全球网格对齐的 2×3 合并；去季节、线性趋势，3 个月平滑后回归去除 CTI，再 sqrt(cosφ) 加权及 SST—(u,v) MCA。模态和预处理基期固定为 1950—2005。\n'
    text+='ERSSTv5 先插值到 R1 网格（SST 沿岸缺测按最近海洋格点填补，再使用固定 R1 海陆掩膜），用自身 1950—2005 季节/趋势/CTI 系数，投影到冻结的 R1 海温模态；月度投影不平滑。仅用 1950—2005 官方序列做线性尺度校准。PMM-SST 的后续投影只需海温，不需重新估计风场模态。\n'
    text+='官方实现未公开所有边界、去趋势参考期与归一化细节，因此本结果不能声称逐值复制官方 PMM；2006 年之后只作独立时间段一致性检验。\n\n'
    text+='三组对照：\n1. official_JanFeb：原有官方 PMM 模型及官方 1—2 月起报。\n2. frozen_official_model_reconstructed_input：原有官方 PMM 模型，2026 起报输入替换为重建值，作为衔接敏感性。\n3. consistent_reconstruction（主图）：历史和 2026 都用同一重建序列，按相同 2002—2024 窗口重新估计扩展 sLIM；RO 的系数与原有模型逐值一致。\n\n'
    text+='主图为 2—6 月五个起报，每个向前自由积分 9 个月。评分排除 lead=0，只使用已发布观测：T 共 25 个起报—目标配对，h/联合指标共 20 个。不同起报有重叠，不能视作独立样本，不能据此做普遍技能显著性声明。\n'
    text+='初始化使用整月均值，观测产品有发布延迟和事后修订；这是以 2026 为参数样本外的回溯自由演变分析，不是当月 1 日实时发布的预报。未观测月份保留为预测，未补造真值，也未加入评分。\n\n'
    text+='历史重建检验：\n'+validation.to_string(index=False)+'\n\n'
    text+='2026 主分析：\n'+main.to_string(index=False)+'\n\n'
    text+='来源：\nhttps://www.aos.wisc.edu/dvimont/MModes/\nhttps://psl.noaa.gov/news/2026/r1datanotice.html\nhttps://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means\nhttps://psl.noaa.gov/data/gridded/data.godas.html\nhttps://psl.noaa.gov/data/gridded/data.noaa.ersst.v5.html\n'
    (OUT/'results_cn.txt').write_text(text)


def main():
    f,s,a,ao,qa,scale=run();style();source_sensitivity(a,scale)
    plot_main(f,s,a,qa,scale);plot_validation();plot_official_control(f,ao,qa);report(s,qa)
    print('Completed:',OUT,flush=True)


if __name__=='__main__':main()
