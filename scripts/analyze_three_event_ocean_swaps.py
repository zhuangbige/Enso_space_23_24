"""Residual-conditioned 3 x 3 ocean-trajectory swaps, with a fixed full-sample sLIM.

Rows retain the recipient's January SST and diagnosed SST innovation sequence.
Columns supply the donor's same-calendar-month three-box ocean trajectory.
The primary exchange transfers detrended anomalies into the recipient background;
direct transfer of absolute volumes is a predeclared background sensitivity.
No refitting, independent forecast claim, or physical forcing identification.
"""
from pathlib import Path
import hashlib
import html
import json
import os
import shutil
import zipfile

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/maryland_story_mpl')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import three_event_segmented_slim as slim
import build_three_event_scientific_figures as style

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'outputs/research_2026'
SOURCE = BASE/'three_event_fullsample_replay_20261015'
OUT = BASE/'three_event_ocean_trajectory_swaps_20261015'
EVENTS = (1997, 2015, 2023)
COLS = ['nino34', 'west_wwv', 'central_wwv', 'east_wwv']
REGIONS = ('west', 'central', 'east')
MODES = ('donor_detrended_anomaly', 'donor_absolute_volume')
PRIMARY = MODES[0]
COLORS = style.COLORS
QA, FIGURES = {}, []


def serial(x):
    if isinstance(x, np.ndarray): return x.tolist()
    if isinstance(x, np.generic): return x.item()
    raise TypeError(type(x))


def dump(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=serial),encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calculate():
    OUT.mkdir(exist_ok=True)
    (OUT/'presentation').mkdir(exist_ok=True)
    files=[SOURCE/'model_and_preprocessing.json', SOURCE/'inputs_absolute.csv',
           SOURCE/'processed_states.csv', Path(slim.__file__), ROOT/'scripts/paper_ro_slim.py']
    before={str(p.relative_to(ROOT)):sha(p) for p in files}
    frozen=json.loads(files[0].read_text())
    assert frozen['key']=='three_wwv_fullsample_detrend_perturb2'
    model=frozen['model']; meta=frozen['preprocessing']
    for field in ['coef','scale']: model[field]=np.asarray(model[field])
    for field in ['clim','trend']: meta[field]=np.asarray(meta[field])
    assert model['columns']==COLS and model['order']==2 and model['method']=='perturb2'
    assert model['diag']['original_months']==516
    raw=pd.read_csv(files[1],parse_dates=['time']).set_index('time')[COLS]
    assert raw.index.equals(pd.date_range('1982-01-01','2024-12-01',freq='MS'))
    background=slim.background_at(meta,raw.index)
    a=raw.to_numpy()-background
    saved=pd.read_csv(files[2],parse_dates=['time']).set_index('time')[COLS]
    assert np.max(abs(a-saved.to_numpy()))<1e-10
    processed=pd.DataFrame(a,index=raw.index,columns=COLS)
    display=raw.loc['1982':'2022'].groupby(raw.loc['1982':'2022'].index.month).mean().to_numpy()
    phi=np.array([slim.propagators(model,month=m,months=1)[1] for m in range(1,12)])
    aa,bb=phi[:,0,0],phi[:,0,1:]
    event_states={}; residuals=[]; ocean_rows=[]
    for event in EVENTS:
        dates=pd.date_range(f'{event}-01-01',periods=12,freq='MS')
        obs=processed.loc[dates].to_numpy()
        bg=slim.background_at(meta,dates)
        actual=raw.loc[dates].to_numpy()
        residual=obs[1:,0]-np.einsum('ni,ni->n',phi[:,0,:],obs[:-1])
        event_states[event]=dict(observed=obs,background=bg,absolute=actual,residual=residual,
                                 display=actual[:,0]-display[:,0])
        for k in range(11):
            residuals.append(dict(recipient=event,source_month=k+1,target_month=k+2,
                observed_next_sst_model=obs[k+1,0],sst_memory=aa[k]*obs[k,0],
                ocean_term=float(bb[k]@obs[k,1:]),residual_sst=residual[k]))
        for k in range(12):
            ocean_rows.append(dict(event=event,month=k+1,**{
                f'{region}_{suffix}':arr[k,j+1] for j,region in enumerate(REGIONS)
                for suffix,arr in [('absolute',actual),('model_anomaly',obs),('background',bg)]}))
    protocol=dict(
        question='Within the fixed statistical model, how does recipient SST change when another event supplies the same-month ocean trajectory?',
        primary_mode=PRIMARY, sensitivity_mode=MODES[1], recipients=list(EVENTS), donors=list(EVENTS),
        primary_combinations=9, sensitivity_combinations=9, model_refitted=False,
        fitted_model_key=frozen['key'], training_period='1982--2024, all 516 months including target events',
        fixed_for_each_recipient=['January observed SST in model coordinates','SST residual sequence diagnosed from that recipient','same fitted operator','recipient display/background transformation'],
        replaced='All three WWV26 coordinates together, matched by calendar month. January--November oceans drive February--December SST; January SST is fixed.',
        primary_coordinate_rule='Donor model anomaly = donor absolute volume minus donor full-sample fitted monthly climatology and trend. Transfer this anomaly into the recipient background.',
        sensitivity_coordinate_rule='Transfer donor absolute volume; subtract the recipient background before using the fixed operator.',
        recurrence='T_cf[m+1] = Phi_TT[m]*T_cf[m] + Phi_TV[m]@V_donor_in_recipient_coordinates[m] + residual_recipient[m+1]',
        residual='T_obs_model[m+1] - Phi_TT[m]*T_obs_model[m] - Phi_TV[m]@V_obs_model[m]',
        control='Self-swap reconstructs recipient observations by construction; this is an identity check, not model validation.',
        display_anomaly='Niño3.4 SST relative to 1982--2022 monthly climatology; degC',
        ocean_definition='SODA3 WWV26, units 1e14 m3, 9S--9N, 120E/180/140W/80W boundaries, surface to instantaneous sigma-theta=26.',
        inference='Conditional linear-model sensitivity with recipient residuals frozen. Residuals may contain unresolved ocean feedback and are not identified external atmospheric forcing.',
        algebra='Common linear coefficients imply antisymmetric and transitive swap differences. Nine cells are not nine independent physical experiments.')
    dump('protocol.json',protocol)
    rows=[]; summaries=[]; regional=[]; deviations={}
    max_self=max_delta=max_sum=0.; min_volume=np.inf
    for mode in MODES:
        for recipient in EVENTS:
            target=event_states[recipient]
            for donor in EVENTS:
                source=event_states[donor]
                ocean=(source['observed'][:,1:] if mode==PRIMARY else source['absolute'][:,1:]-target['background'][:,1:])
                transplanted_absolute=ocean+target['background'][:,1:]
                min_volume=min(min_volume,float(transplanted_absolute.min()))
                t=np.zeros(12);t[0]=target['observed'][0,0]
                by_region=np.zeros((12,3))
                dv=ocean-target['observed'][:,1:]
                for k in range(11):
                    t[k+1]=aa[k]*t[k]+bb[k]@ocean[k]+target['residual'][k]
                    by_region[k+1]=aa[k]*by_region[k]+bb[k]*dv[k]
                prediction=t+target['background'][:,0]-display[:,0]
                delta=prediction-target['display']
                deviations[(mode,recipient,donor)]=delta
                max_sum=max(max_sum,float(abs(delta-by_region.sum(axis=1)).max()))
                # Independent closed-form impulse-response calculation.
                direct=np.zeros(12)
                for n in range(1,12):
                    direct[n]=sum(np.prod(aa[k+1:n])*(bb[k]@dv[k]) for k in range(n))
                max_delta=max(max_delta,float(abs(delta-direct).max()))
                if recipient==donor:max_self=max(max_self,float(abs(delta).max()))
                assert np.isfinite(prediction).all()
                for k in range(12):
                    rows.append(dict(mode=mode,recipient=recipient,donor=donor,month=k+1,
                        sst=prediction[k],control_sst=target['display'][k],delta_sst=delta[k],
                        sst_model=t[k],residual_added=0. if k==0 else target['residual'][k-1],
                        ocean_used_for_next_step=k<11,**{f'{r}_{suffix}':v[k,j] for j,r in enumerate(REGIONS)
                        for suffix,v in [('model_anomaly',ocean),('transplanted_absolute',transplanted_absolute),('delta_contribution',by_region)]}))
                for season,lo,hi in [('JFM',0,3),('AMJ',3,6),('JAS',6,9),('OND',9,12)]:
                    summaries.append(dict(mode=mode,recipient=recipient,donor=donor,season=season,
                        sst=float(prediction[lo:hi].mean()),control_sst=float(target['display'][lo:hi].mean()),
                        delta_sst=float(delta[lo:hi].mean()),peak_sst=float(prediction.max()),
                        peak_month=int(np.argmax(prediction)+1),max_abs_delta=float(abs(delta).max())))
                    for j,r in enumerate(REGIONS):
                        regional.append(dict(mode=mode,recipient=recipient,donor=donor,season=season,
                                             region=r,contribution=float(by_region[lo:hi,j].mean())))
    assert max_self<1e-10 and max_sum<1e-10 and max_delta<1e-10 and min_volume>0
    antisym=max(float(abs(deviations[(mode,i,j)]+deviations[(mode,j,i)]).max())
                for mode in MODES for i in EVENTS for j in EVENTS)
    transitive=max(float(abs(deviations[(mode,i,j)]+deviations[(mode,j,k)]-deviations[(mode,i,k)]).max())
                   for mode in MODES for i in EVENTS for j in EVENTS for k in EVENTS)
    assert antisym<1e-10 and transitive<1e-10
    monthly=pd.DataFrame(rows);summary=pd.DataFrame(summaries);contrib=pd.DataFrame(regional)
    monthly.to_csv(OUT/'swap_monthly_trajectories.csv',index=False)
    summary.to_csv(OUT/'swap_seasonal_summary.csv',index=False)
    contrib.to_csv(OUT/'regional_model_contributions.csv',index=False)
    pd.DataFrame(residuals).to_csv(OUT/'recipient_residual_sequences.csv',index=False)
    pd.DataFrame(ocean_rows).to_csv(OUT/'observed_ocean_states.csv',index=False)
    for mode in MODES:
        sub=summary[summary['mode'].eq(mode)&summary.season.eq('OND')]
        for value in ['sst','delta_sst']:
            sub.pivot(index='recipient',columns='donor',values=value).reindex(index=EVENTS,columns=EVENTS).to_csv(OUT/f'OND_{value}_{mode}.csv')
    # The saved monthly outputs independently reproduce the reported seasonal values.
    reread=pd.read_csv(OUT/'swap_monthly_trajectories.csv')
    reread['season']=np.array(['JFM','AMJ','JAS','OND'])[(reread.month.to_numpy()-1)//3]
    check=reread.groupby(['mode','recipient','donor','season'])[['sst','delta_sst']].mean()
    reference=summary.set_index(['mode','recipient','donor','season'])[['sst','delta_sst']]
    assert float(abs(check-reference).max().max())<1e-12
    after={str(p.relative_to(ROOT)):sha(p) for p in files}
    assert before==after
    QA.update(model_and_inputs_unchanged=True,number_of_refits=0,model_training_months=516,primary_combinations=9,
        sensitivity_combinations=9,monthly_rows=len(monthly),
        self_swap_max_error=max_self,regional_additivity_max_error=max_sum,
        direct_impulse_vs_recurrence_max_error=max_delta,
        antisymmetry_max_error=antisym,transitivity_max_error=transitive,
        minimum_transplanted_absolute_volume_1e14m3=min_volume,
        january_sst_unchanged=bool(np.max(abs(monthly[monthly.month.eq(1)].delta_sst))<1e-12),
        saved_seasonal_means_checked=True,control_reconstruction_is_by_construction=True,
        not_an_independent_forecast_or_identified_physical_intervention=True)
    dump('fixed_model_snapshot.json',frozen)
    raw.to_csv(OUT/'source_inputs_absolute.csv',index_label='time')
    dump('input_manifest.json',before)
    dump('validation.json',QA)
    print('PRIMARY OND SST',flush=True)
    print(summary[(summary['mode']==PRIMARY)&summary.season.eq('OND')].pivot(index='recipient',columns='donor',values='sst').round(4).to_string(),flush=True)
    print('PRIMARY OND CHANGE',flush=True)
    print(summary[(summary['mode']==PRIMARY)&summary.season.eq('OND')].pivot(index='recipient',columns='donor',values='delta_sst').round(4).to_string(),flush=True)
    print('ABSOLUTE-VOLUME SENSITIVITY CHANGE',flush=True)
    print(summary[(summary['mode']==MODES[1])&summary.season.eq('OND')].pivot(index='recipient',columns='donor',values='delta_sst').round(4).to_string(),flush=True)
    return monthly,summary,contrib


def save(fig,stem,title,caption,pdf):
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer();outside=[]
    for text in fig.findobj(matplotlib.text.Text):
        if not text.get_visible() or not text.get_text():continue
        box=text.get_window_extent(renderer)
        if box.width and (box.x0<-1 or box.y0<-1 or box.x1>fig.bbox.width+1 or box.y1>fig.bbox.height+1):
            outside.append(text.get_text())
    QA.setdefault('text_outside_page',{})[stem]=outside
    assert not outside,outside
    for extension in ['png','pdf','svg']:
        fig.savefig(OUT/f'{stem}.{extension}',dpi=400)
    fig.savefig(OUT/'presentation'/f'{stem}.png',dpi=500)
    pdf.savefig(fig,dpi=400)
    FIGURES.append(dict(stem=stem,title=title,caption=caption))
    plt.close(fig)


def plot(monthly,summary,contrib):
    style.style()
    q=monthly[monthly['mode'].eq(PRIMARY)]
    ond=summary[summary.season.eq('OND')]
    with PdfPages(OUT/'ocean_swap_figure_book.pdf') as pdf:
        fig=plt.figure(figsize=(7.2,6.75))
        fig.text(.10,.975,'Cross-event ocean trajectory swaps',fontsize=11,weight='bold',va='top')
        fig.text(.10,.937,'Rows: recipient SST + residuals. Columns: donor ocean anomalies. One fixed full-sample model.',fontsize=6.4,color='#535B63')
        fig.legend(handles=[Line2D([],[],color=style.BLACK,lw=1.6,label='Recipient control / observations'),
            Line2D([],[],color='#777777',marker='o',ms=3,label='Ocean-swap response (column color)')],
            loc='upper center',bbox_to_anchor=(.53,.924),ncol=2,fontsize=7)
        gs=fig.add_gridspec(3,3,left=.10,right=.96,bottom=.12,top=.835,hspace=.32,wspace=.15)
        low=np.floor((min(q.sst.min(),q.control_sst.min())-.12)*2)/2
        high=np.ceil((max(q.sst.max(),q.control_sst.max())+.12)*2)/2
        for i,recipient in enumerate(EVENTS):
            for j,donor in enumerate(EVENTS):
                ax=fig.add_subplot(gs[i,j])
                data=q[q.recipient.eq(recipient)&q.donor.eq(donor)].sort_values('month')
                ax.plot(data.month,data.control_sst,color=style.BLACK,lw=1.5,zorder=2)
                ax.plot(data.month,data.sst,color=COLORS[donor],lw=1.15,marker=style.MARKERS[donor],
                        markevery=[0,3,6,9,11],ms=2.8,zorder=3)
                ax.set_ylim(low,high);style.months(ax)
                if i==0:ax.set_title(f'Ocean donor: {donor}',fontsize=8,color=COLORS[donor],pad=8)
                if j==0:ax.set_ylabel(f'Recipient {recipient}\nNiño3.4 anomaly (°C)',fontsize=7)
                else:ax.tick_params(labelleft=False)
                if i<2:ax.tick_params(labelbottom=False)
                delta=float(data[data.month.ge(10)].delta_sst.mean())
                if abs(delta)<1e-10:delta=0.
                ax.text(.97,.06,f'ΔOND = {delta:+.2f}°C',ha='right',va='bottom',transform=ax.transAxes,
                        fontsize=7,color=COLORS[donor],bbox=dict(facecolor='white',edgecolor='none',alpha=.85,pad=1))
        fig.text(.10,.045,'Same-month detrended ocean anomalies are exchanged; recipient background and residuals are retained.\nDiagonal agreement is exact by construction. SST display: 1982–2022 monthly anomalies.',fontsize=6.4,color='#535B63')
        save(fig,'M1_ocean_swap_trajectories','三个事件的海洋轨迹互换',
             '行固定目标年的1月海温、同一模型及目标年残差，列换入供体事件同历月的三区WWV26去趋势异常。黑线为目标年观测/重建对照，彩线为互换结果；各面板共用坐标范围。1月至11月海洋驱动2月至12月海温。对角线精确贴合来自残差重建定义，不是模型验证。标注ΔOND为相对目标年重建对照的10—12月平均海温变化。',pdf)
        fig=plt.figure(figsize=(7.2,6.3))
        fig.text(.10,.975,'Late-year response and regional model contributions',fontsize=10,weight='bold',va='top')
        gs=fig.add_gridspec(2,2,left=.13,right=.89,bottom=.16,top=.86,height_ratios=[1,1.12],hspace=.58,wspace=.44)
        maximum=float(ond.delta_sst.abs().max())
        bound=max(.1,np.ceil(maximum*10)/10)
        for j,(mode,title) in enumerate(zip(MODES,['a  Detrended-anomaly transfer','b  Absolute-volume transfer'])):
            ax=fig.add_subplot(gs[0,j])
            matrix=ond[ond['mode'].eq(mode)].pivot(index='recipient',columns='donor',values='delta_sst').reindex(index=EVENTS,columns=EVENTS).to_numpy()
            im=ax.imshow(matrix,cmap='RdBu_r',vmin=-bound,vmax=bound,aspect='equal')
            ax.set_title(title,loc='left',fontsize=7.5,pad=7)
            ax.set_xticks(range(3),EVENTS);ax.set_yticks(range(3),EVENTS)
            ax.set_xlabel('Ocean donor');ax.set_ylabel('Recipient')
            for i in range(3):
                for k in range(3):
                    value=matrix[i,k] if abs(matrix[i,k])>1e-10 else 0.
                    ax.text(k,i,f'{value:+.2f}',ha='center',va='center',fontsize=8,
                            color='white' if abs(value)>.62*bound else style.BLACK)
        cax=fig.add_axes([.905,.595,.014,.225])
        cb=fig.colorbar(im,cax=cax);cb.set_label('ΔOND SST (°C)',fontsize=7)
        ax=fig.add_subplot(gs[1,:])
        pairs=[(r,d) for r in EVENTS for d in EVENTS if r!=d]
        colors={'west':'#21918C','central':'#756BB1','east':'#D5A126'}
        sub=contrib[contrib['mode'].eq(PRIMARY)&contrib.season.eq('OND')]
        vals=np.array([[sub[sub.recipient.eq(r)&sub.donor.eq(d)&sub.region.eq(region)].contribution.iloc[0] for region in REGIONS] for r,d in pairs])
        yy=np.arange(len(pairs));positive=np.zeros(6);negative=np.zeros(6)
        for j,region in enumerate(REGIONS):
            v=vals[:,j];left=np.where(v>=0,positive,negative)
            ax.barh(yy,v,left=left,height=.6,color=colors[region],label=region.capitalize())
            positive+=np.maximum(v,0);negative+=np.minimum(v,0)
        ax.scatter(vals.sum(axis=1),yy,color=style.BLACK,marker='D',s=13,zorder=4,label='Net change')
        ax.axvline(0,color='#9AA2AB',lw=.6)
        ax.set_yticks(yy,[f'{r} ← {d}' for r,d in pairs]);ax.invert_yaxis()
        ax.set_xlabel('Contribution to ΔOND SST (°C)');ax.set_ylabel('Recipient ← donor')
        ax.set_title('c  Regional contributions under detrended-anomaly transfer',loc='left',fontsize=8,pad=7)
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.23),ncol=4,fontsize=6.5)
        fig.text(.10,.025,'Shared color limits in a–b. Regional terms are additive model responses, not a physical heat budget.\nOpposite swaps are antisymmetric because the same linear operator is used.',fontsize=6.2,color='#535B63')
        save(fig,'S1_swap_summary_and_contributions','互换效应、背景口径与区域贡献',
             'a：主实验去趋势异常互换的ΔOND；b：直接转移供体原始体积的背景敏感性，两矩阵使用同一零中心色标。c：主实验西、中、东三区输入差异经过同一海温记忆项传播后的线性贡献；黑菱形为净变化。区域项严格相加，但不是实际热收支。由于算子相同且线性，反向互换效应互为相反数、三事件差值可加；这些结构约束不能当作独立物理验证。',pdf)
    dump('figure_manifest.json',FIGURES)
    dump('validation.json',QA)


def report(summary,contrib):
    main=summary[summary['mode'].eq(PRIMARY)&summary.season.eq('OND')]
    matrices=[]
    for field,label in [('sst','互换后的OND海温距平（°C）'),('delta_sst','相对目标年对照的ΔOND（°C）')]:
        matrix=main.pivot(index='recipient',columns='donor',values=field).reindex(index=EVENTS,columns=EVENTS)
        matrices.append(f'<h2>{label}</h2><p>行是目标年，列是海洋供体年。</p>'+matrix.round(3).to_html())
    cards=[]
    for f in FIGURES:
        stem=f['stem']
        cards.append(f'<section><h2>{f["title"]}</h2><p>'+ ' · '.join(f'<a href="{stem}.{ext}">{ext.upper()}</a>' for ext in ['png','pdf','svg'])+f'</p><img src="{stem}.png"><p>{html.escape(f["caption"])}</p></section>')
    pairs=main[main.recipient.ne(main.donor)].copy()
    pairs=pairs[['recipient','donor','sst','control_sst','delta_sst','peak_sst','peak_month']].rename(columns={
        'recipient':'目标年','donor':'海洋供体','sst':'OND互换后','control_sst':'OND对照','delta_sst':'ΔOND','peak_sst':'年内最高海温','peak_month':'最高值月份'})
    sensitivity=summary[summary['mode'].eq(MODES[1])&summary.season.eq('OND')].pivot(index='recipient',columns='donor',values='delta_sst').reindex(index=EVENTS,columns=EVENTS)
    region_table=contrib[contrib['mode'].eq(PRIMARY)&contrib.season.eq('OND')&contrib.recipient.ne(contrib.donor)].pivot(index=['recipient','donor'],columns='region',values='contribution')[list(REGIONS)]
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>三事件海洋轨迹互换</title><style>body{font-family:Arial,"PingFang SC",sans-serif;background:#f5f6f7;color:#24313b;line-height:1.8;margin:0}main{max-width:1080px;margin:auto;padding:40px 28px}section{background:white;padding:26px;margin:24px 0;border:1px solid #dce2e6;border-radius:8px}h1{font-size:30px;line-height:1.4}h2{font-size:21px}a{color:#006b9f}img{width:100%;height:auto}td,th{padding:9px 14px;border-bottom:1px solid #ddd;text-align:right}table{border-collapse:collapse;font-size:14px}code{white-space:pre-wrap}.lead{font-size:18px}.note{color:#53616c;font-size:14px}nav{display:flex;gap:18px;flex-wrap:wrap}@media(max-width:600px){main{padding:20px 10px}section{padding:16px}td,th{padding:6px}table{font-size:12px}}</style><main><h1>1997、2015、2023海洋轨迹相互替换</h1><p class="lead">固定全样本sLIM、目标年海温初态和目标年残差，比较另一事件的海洋轨迹在模型中会改变多少海温。</p><nav><a href="ocean_swap_figure_book.pdf">两图PDF</a><a href="ocean_swap_data.zip">数据与复现代码</a><a href="protocol.json">完整协议</a><a href="../three_event_scientific_figures_20261015/index.html">原六图图集</a></nav><section><h2>如何定义替换</h2><p>沿用已拟合的1982—2024全部516个月四状态sLIM，没有再次拟合。9个主实验中，行固定目标年的1月海温、月度残差和背景，列搬入供体年同历月的西、中、东三区WWV26。主方案交换去趋势后的海洋异常；输入到目标年时加回目标年背景。因此这是异常结构/轨迹互换，并非直接复制供体年的绝对体积。</p><p>1—11月海洋驱动2—12月海温，1月海温始终不变。每一步使用该月海洋推进下一月，不使用下一月的供体海洋。海温没有在计算过程中重设为观测。</p><p><code>Tᶜᶠ(m+1) = a(m)Tᶜᶠ(m) + b(m)·V供体(m) + r目标(m+1)</code></p><p>残差从目标年的观测海温和自身海洋诊断得到。自身替换的对角线精确重建观测，是上述定义带来的代数恒等式，不是模型验证。残差没有被识别为独立大气强迫，也可能包含未解析海洋反馈。</p></section>'''
    recipient2023=main[main.recipient.eq(2023)].set_index('donor')
    base=float(recipient2023.loc[2023,'sst'])
    findings=f'''<section><h2>本轮结果</h2><p>主实验中，2023的OND海温距平由自身重建的{base:.2f}°C，变为换入1997海洋后的{recipient2023.loc[1997,'sst']:.2f}°C（增加{recipient2023.loc[1997,'delta_sst']:.2f}°C），或换入2015后的{recipient2023.loc[2015,'sst']:.2f}°C（增加{recipient2023.loc[2015,'delta_sst']:.2f}°C）。反过来，将2023海洋放入1997和2015，OND分别减少{abs(main[(main.recipient==1997)&(main.donor==2023)].delta_sst.iloc[0]):.2f}°C和{abs(main[(main.recipient==2015)&(main.donor==2023)].delta_sst.iloc[0]):.2f}°C。</p><p>直接转移原始体积时，2023换入1997或2015的ΔOND分别为{sensitivity.loc[2023,1997]:+.2f}°C和{sensitivity.loc[2023,2015]:+.2f}°C。此处比较的是两种背景定义，不是置信区间。</p><p>对2023而言，两个供体的中、东区贡献均为增暖，西区贡献抵消一部分增暖；具体数字见区域贡献表。这说明当前模型的差异集中在中东部轨迹，不能只用全盆地暖水总量解释，也不能把这些统计响应项直接命名为实际热输送。</p></section>'''
    doc+=findings+'<section>'+''.join(matrices)+'</section>'+''.join(cards)
    doc+='<section><h2>全部跨年组合</h2>'+pairs.round(3).to_html(index=False)+'<h2>原始体积转移的口径检查：ΔOND（°C）</h2>'+sensitivity.round(3).to_html()+'<h2>主方案三区对ΔOND的模型贡献（°C）</h2>'+region_table.round(3).to_html()+'</section>'
    doc+='''<section><h2>结果的解释范围</h2><p>当前比较回答的是：在目标年残差冻结、同一线性关系成立的条件下，换一条海洋轨迹会怎样。它不自动等于真实海洋的因果贡献。供体海洋轨迹被每月指定，没有允许它对新的海温反馈后重新调整。</p><p>差值满足 ΔT(m+1)=a(m)ΔT(m)+b(m)·[V供体(m)−V目标(m)]。因此目标年残差在差值中抵消，反向互换必然互为相反数，且三事件差值可加。这意味着这里没有识别出随目标年背景改变的非线性交互，也不能把9格当作9个独立样本。</p><p>三区贡献是固定算子下的加性响应，不能命名为实际热输送或热收支项。原始体积转移仅检查背景约定的影响，不据此挑选更符合预期的结果。</p><p class="note">检查包括：自身替换、固定1月海温、背景变换、直接传播核与递推一致性、三区贡献相加、反向/三角交换恒等式、原始体积正值、保存表独立季节平均及模型输入哈希不变。数值恒等式通过不等于物理替换已获验证。</p></section><footer>复现：scripts/analyze_three_event_ocean_swaps.py。模型与输入快照、月序列、季节表、残差、区域贡献及检查记录随数据包提供。</footer></main></html>'''
    (OUT/'index.html').write_text(doc,encoding='utf-8')
    with zipfile.ZipFile(OUT/'ocean_swap_data.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.glob('*.csv')):z.write(p,p.name)
        for p in sorted(OUT.glob('*.json')):z.write(p,p.name)
        for p in [Path(__file__),Path(slim.__file__),ROOT/'scripts/paper_ro_slim.py',ROOT/'scripts/build_three_event_scientific_figures.py']:
            z.write(p,'scripts/'+p.name)


if __name__=='__main__':
    data,seasonal,regional=calculate()
    plot(data,seasonal,regional)
    report(seasonal,regional)
    print(json.dumps(QA,ensure_ascii=False,indent=2),flush=True)
