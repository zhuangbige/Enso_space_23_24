#!/usr/bin/env python3
"""Two figures and a Chinese evidence report from frozen diagnostics."""
from pathlib import Path
import argparse, html, json, hashlib
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.integrate import cumulative_trapezoid

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/three_event_summer_current_dynamics_20261015'
EVENTS=[1997,2015,2023]
COLORS={1997:'#0072B2',2015:'#D28A00',2023:'#CC493B'}
F_COLORS={'wind':'#1f77b4','pressure_ssh':'#e68a00','pressure_density':'#9370b5','coriolis':'#228b66','advection':'#8c564b','unresolved':'#ce496b'}
F_LABELS={'wind':'Surface wind input','pressure_ssh':'Effective sea-level pressure','pressure_density':'Density pressure','coriolis':'Coriolis','advection':'Horizontal advection + metric','unresolved':'Unresolved'}
MOM=['wind','pressure_ssh','pressure_density','coriolis','horizontal_advection','metric']

def save(fig,stem):
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{stem}.{ext}',dpi=220,facecolor='white')
    plt.close(fig)

def time_axis(ax):
    ax.set_xlim(.8,12.2);ax.set_xticks(range(1,13));ax.set_xticklabels(list('JFMAMJJASOND'))
    ax.axvspan(3.5,6.5,color='#d9edf3',alpha=.45,zorder=-1);ax.axvspan(6.5,9.5,color='#fff0ce',alpha=.55,zorder=-1)
    ax.axhline(0,color='#666',lw=.6)

def figures(local,season,section,wind):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'axes.titlesize':11,'axes.labelsize':9,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,axes=plt.subplots(3,2,figsize=(12,12.3),gridspec_kw={'height_ratios':[1,1.05,1]})
    fig.subplots_adjust(left=.075,right=.90,bottom=.09,top=.91,hspace=.55,wspace=.30)
    fig.suptitle('Where does the weaker 2023 summer transport come from?',fontsize=17,y=.977)
    fig.text(.5,.947,'JAS contrasts: 2023 minus each control | SODA3.15.2 | All 1982–2024 years define the background',ha='center',fontsize=10,color='#555')
    bands=['0_50','50_150','150_sigma26','all'];labels=['0–50 m','50–150 m','>150 m','All warm water']
    for j,control in enumerate([1997,2015]):
        ax=axes[0,j];s=section[(section.control==control)&(section.season=='JAS')].set_index('band').loc[bands]
        x=np.arange(4);ax.bar(x-.16,s.current_sv,.30,color='#277DA8',label='Velocity change');ax.bar(x+.16,s.thickness_sv,.30,color='#D9A344',label='Active-thickness change')
        ax.scatter(x,s.total_sv,marker='D',s=30,c='#242424',label='Total difference',zorder=5)
        ax.axhline(0,color='#555',lw=.7);ax.set_xticks(x,labels);ax.set_ylabel('140°W transport difference (Sv)')
        ax.set_title(f'({"ab"[j]}) 2023 − {control}: exact symmetric split',loc='left')
        ax.set_ylim(-12.5,4.3)
        if j==0:ax.legend(fontsize=8,loc='lower left',frameon=False)
    ds=xr.open_dataset(OUT/'spatial_diagnostics.nc',engine='h5netcdf')
    diffs=[ds.u_prime_meanT.sel(event=2023)-ds.u_prime_meanT.sel(event=c) for c in [1997,2015]]
    limit=max(float(abs(a).quantile(.99)) for a in diffs);limit=np.ceil(limit*10)/10
    for j,control in enumerate([1997,2015]):
        ax=axes[1,j];z=diffs[j]
        im=ax.pcolormesh(ds.lon,ds.lat,z,cmap='RdBu_r',vmin=-limit,vmax=limit,shading='nearest')
        bg=ds.background_Tx.sel(event=2023)
        contours=ax.contour(ds.lon,ds.lat,bg,levels=[-1.0,-.6,-.2],colors='#286941',linewidths=.8,linestyles='dashed')
        ax.clabel(contours,inline=True,fontsize=7,fmt='%.1f')
        ax.text(.0,-.18,'Green contours: background ∂xT (°C per 1000 km)',transform=ax.transAxes,fontsize=8,color='#286941')
        flow=ds.u_anomaly.sel(event=2023)-ds.u_anomaly.sel(event=control)
        stride=(slice(1,None,4),slice(3,None,10))
        xx,yy=np.meshgrid(ds.lon,ds.lat)
        qq=ax.quiver(xx[stride],yy[stride],flow.to_numpy()[stride],np.zeros_like(flow.to_numpy()[stride]),color='#333',scale=2.5,width=.003)
        ax.quiverkey(qq,.82,1.08,.1,'0.1 m s⁻¹',labelpos='E',coordinates='axes',fontproperties={'size':8})
        ax.set_xlim(190,240);ax.set_ylim(-5,5);ax.set_xticks([190,200,210,220,230,240],['170°W','160°W','150°W','140°W','130°W','120°W'])
        ax.set_yticks([-5,0,5],['5°S','0°','5°N']);ax.set_title(f'({"cd"[j]}) 0–50 m current-advection: 2023 − {control}',loc='left',pad=22)
    pos=axes[1,1].get_position();cax=fig.add_axes([.917,pos.y0,.012,pos.height]);fig.colorbar(im,cax=cax,label='°C per standard month',extend='both')
    ax=axes[2,0]
    for e in EVENTS:
        x=local[(local.depth_m==50)&(local.background=='mean')&local.time.dt.year.eq(e)]
        ax.plot(x.time.dt.month,x.u_prime_meanT,color=COLORS[e],label=str(e),lw=2)
    time_axis(ax);ax.set_ylabel('Current-anomaly advection (°C month⁻¹)');ax.set_title('(e) Spring–summer evolution, 0–50 m',loc='left');ax.legend(ncol=3,frameon=False)
    ax=axes[2,1];s=season[(season.depth_m==50)&(season.background=='mean')&(season.season=='JAS')].set_index('event')
    keys=['advection_mean','advection_horizontal_cov','advection_vertical_cov'];labels=['Mean-current contribution','Horizontal covariance','Vertical covariance'];cols=['#277DA8','#D9A344','#8F79AA']
    x=np.arange(2)
    for k,label,color,shift in zip(keys,labels,cols,[-.22,0,.22]):ax.bar(x+shift,[s.loc[2023,k]-s.loc[c,k] for c in [1997,2015]],.21,label=label,color=color)
    ax.scatter(x,[s.loc[2023,'u_prime_meanT']-s.loc[c,'u_prime_meanT'] for c in [1997,2015]],c='#222',marker='D',s=30,zorder=5,label='Total difference')
    ax.axhline(0,c='#555',lw=.7);ax.set_xticks(x,['2023 − 1997','2023 − 2015']);ax.set_ylabel('Advection difference (°C month⁻¹)');ax.set_title('(f) Exact mean / spatial-structure split',loc='left');ax.legend(fontsize=8,frameon=False,loc='lower right')
    fig.text(.075,.035,'Section: 9°S–9°N, surface–σθ=26. Local advection: 5°S–5°N, 170°W–120°W.\nThe two diagnostics have different domains. Signed contributions are kinematic decompositions, not causal effects.\nThe 2023 advection sign depends on background treatment; the lower-than-both-controls ordering is robust.',fontsize=9,color='#555')
    save(fig,'M1_transport_and_advection');ds.close()

    fig,axes=plt.subplots(3,2,figsize=(12,12.8))
    fig.subplots_adjust(left=.075,right=.97,bottom=.13,top=.91,hspace=.50,wspace=.30)
    fig.suptitle('Weak wind input is consistent with weak currents; the budget remains incomplete',fontsize=15.5,y=.975)
    fig.text(.5,.945,'Niño3.4, 0–50 m | Reconstructed monthly momentum terms | No residual is assigned to a named mechanism',ha='center',fontsize=10,color='#555')
    for e in EVENTS:
        x=local[(local.depth_m==50)&(local.background=='mean')&local.time.dt.year.eq(e)]
        axes[0,0].plot(x.time.dt.month,x.u_m_s,color=COLORS[e],lw=2,label=str(e))
        w=wind[wind.time.dt.year.eq(e)]
        axes[0,1].plot(w.time.dt.month,w.soda_nino34_taux_anomaly,color=COLORS[e],lw=1.8)
        axes[0,1].plot(w.time.dt.month,w.era5_nino34_taux_anomaly,color=COLORS[e],lw=1.2,ls='--')
    for ax in axes[0]:time_axis(ax)
    axes[0,0].set_title('(a) Layer-mean zonal current anomaly',loc='left');axes[0,0].set_ylabel('m s⁻¹');axes[0,0].legend(ncol=3,frameon=False)
    axes[0,1].set_title('(b) Wind stress in the same nominal region',loc='left');axes[0,1].set_ylabel('N m⁻²')
    axes[0,1].plot([],[],c='#333',ls='-',label='SODA forcing');axes[0,1].plot([],[],c='#333',ls='--',label='ERA5');axes[0,1].legend(frameon=False,ncol=2)
    season50=season[(season.depth_m==50)&(season.background=='mean')&(season.season=='JAS')].set_index('event')
    for j,c in enumerate([1997,2015]):
        ax=axes[1,j];a=season50.loc[2023];b=season50.loc[c]
        vals=[(a[k+'_m_s2']-b[k+'_m_s2'])*1e7 if k!='advection' else sum(a[x+'_m_s2']-b[x+'_m_s2'] for x in ['horizontal_advection','metric'])*1e7 for k in F_COLORS]
        ax.bar(range(6),vals,color=list(F_COLORS.values()));ax.axhline(0,c='#555',lw=.7)
        ax.axhline((a.tendency_m_s2-b.tendency_m_s2)*1e7,c='#111',ls='--',lw=1.5,label='Actual tendency difference')
        ax.set_xticks(range(6),['Wind','Sea-level\npressure','Density\npressure','Coriolis','Horiz. adv.\n+ metric','Unresolved']);ax.set_ylim(-4.3,2.6)
        ax.set_ylabel('10⁻⁷ m s⁻²');ax.set_title(f'({"cd"[j]}) JAS acceleration: 2023 − {c}',loc='left');ax.legend(fontsize=8,frameon=False,loc='lower left')
        ax=axes[2,j]
        a=local[(local.depth_m==50)&(local.background=='mean')&local.time.dt.year.eq(2023)].reset_index(drop=True)
        b=local[(local.depth_m==50)&(local.background=='mean')&local.time.dt.year.eq(c)].reset_index(drop=True)
        sec=(a.time-a.time.iloc[0]).dt.total_seconds().to_numpy();months=a.time.dt.month.to_numpy()
        # Both current YEARS are non-leap; month spacings match exactly.
        for k in F_COLORS:
            delta=(a[k+'_m_s2']-b[k+'_m_s2']).to_numpy() if k!='advection' else sum((a[x+'_m_s2']-b[x+'_m_s2']).to_numpy() for x in ['horizontal_advection','metric'])
            integ=cumulative_trapezoid(delta,sec,initial=0)
            ax.plot(months,integ,c=F_COLORS[k],lw=1.5,ls='--' if k=='unresolved' else '-',label=F_LABELS[k])
        du=(a.u_m_s-b.u_m_s).to_numpy();ax.plot(months,du-du[0],c='#111',lw=2.2,label='Actual change in contrast')
        ax.text(.03,.06,f'Initial Jan contrast: {du[0]:+.3f} m s⁻¹',transform=ax.transAxes,fontsize=8,bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
        time_axis(ax);ax.set_ylabel('Integrated acceleration (m s⁻¹)');ax.set_title(f'({"ef"[j]}) Accumulation from Jan 15: 2023 − {c}',loc='left');ax.set_ylim(-10.7,5.1)
    handles,labels=axes[2,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.52,.062),ncol=4,fontsize=8.5,frameon=False)
    fig.text(.075,.018,'Large opposing terms and unresolved contributions prevent causal percentages. Endpoint quadrature errors are saved separately.\nERA5 and SODA forcing are not independent evidence: SODA3.15.2 uses ERA5 forcing. Surface pressure loading is already included in SSH.',fontsize=8.5,color='#555')
    save(fig,'M2_partial_momentum_budget')

def report(local,season,section,wind):
    s=season[(season.depth_m==50)&(season.background=='mean')&(season.season=='JAS')].set_index('event')
    q=section[(section.season=='JAS')&(section.band=='all')].set_index('control')
    intr=pd.read_csv(OUT/'momentum_pair_intervals.csv')
    use=intr[(intr.depth_m==50)&(intr.background=='mean')&(intr.start_month==7)&(intr.end_month==10)].set_index('control')
    wind=wind.copy();wind['event']=wind.time.dt.year
    w=wind[wind.time.dt.month.isin([7,8,9])&wind.event.isin(EVENTS)].groupby('event').mean(numeric_only=True)
    qa=json.loads((OUT/'local_QA.json').read_text());validation=json.loads((OUT/'validation.json').read_text())
    lines=[
      '三事件夏季流速差异：补缺口结果',
      '结论：补上了“输送差异主要来自流速、平流差异主要对应平均异常流速”的定量环节；较弱的向东风应力异常获得一致性支持，但完整动力归因仍未闭合。',
      '',
      '1. 输送差异首先来自流速，最大单层贡献位于0—50m。',
    ]
    for c in [1997,2015]:
        r=q.loc[c]
        lines.append(f'JAS 2023−{c}：140°W输送差 {r.total_sv:+.4f} Sv = 流速项 {r.current_sv:+.4f} + 暖水层厚度项 {r.thickness_sv:+.4f}。这是一致口径下的对称运动学分解，不是风或海洋强迫的因果百分比。')
    lines += ['', '2. 局地平流偏弱对应较弱的区域平均异常纬向流。']
    for e in EVENTS:
        r=s.loc[e];lines.append(f'{e} JAS：0—50m平均u′={r.u_m_s:+.5f} m/s；−u′∂xT̄={r.u_prime_meanT:+.5f} °C/标准月。')
    for c in [1997,2015]:
        a=s.loc[2023];b=s.loc[c]
        lines.append(f'2023−{c}平流差 {a.u_prime_meanT-b.u_prime_meanT:+.5f} = 平均流速项 {a.advection_mean-b.advection_mean:+.5f} + 水平协方差 {a.advection_horizontal_cov-b.advection_horizontal_cov:+.5f} + 垂直协方差 {a.advection_vertical_cov-b.advection_vertical_cov:+.5f} °C/标准月。')
    lines += ['2023主背景下区域平均u′略为正，而平流项为负，是空间协方差抵消的结果；不能把平均u′正负直接当作平流正负。去趋势后2023平流项可转正，稳健的是低于两次对照的排序。',
      '', '3. 风输入偏弱有支持，“2023压力阻力更强”没有一致支持。']
    for e in EVENTS:lines.append(f'{e} JAS Niño3.4应力距平：SODA {w.loc[e,"soda_nino34_taux_anomaly"]:+.6f}，ERA5 {w.loc[e,"era5_nino34_taux_anomaly"]:+.6f} N/m²。')
    lines += ['两产品均显示2023向东应力异常较弱；SODA本身使用ERA5强迫，故这只是资料一致性，不是独立因果验证。风输入均指相对气候态的向东应力贡献，正距平不代表绝对西风，也不能据月值识别西风爆发。',
      '2023夏季海面压力项仍为向西加速，但其强度弱于1997、接近2015。相对1997，它实际上抵消了一部分风输入不足，不能写成“更强压力阻力导致2023流速偏弱”。密度压力项也没有提供稳定更强的向西阻力。',
      '', '4. 动量收支仍有大幅抵消与未解析项，不能给出可信的风致归因比例。']
    for c in [1997,2015]:
        r=use.loc[c]
        lines.append(f'Jul15—Oct15，2023−{c}的流速差变化 {r.delta_u:+.5f} m/s；风输入累计 {r.wind:+.5f}，海面压力 {r.pressure_ssh:+.5f}，密度压力 {r.pressure_density:+.5f}，科氏项 {r.coriolis:+.5f}，水平平流+几何 {r.horizontal_advection+r.metric:+.5f}，未解析 {r.unresolved:+.5f}，另列积分离散误差 {r.integration_mismatch:+.5f} m/s。')
    lines += ['以上受力贡献指固定观测轨迹上的诊断积分；数值可远大于实际流速变化，因为多个大项抵消。它们不是单独施加某项强迫后会产生的反事实速度。部分时窗的积分离散误差也与流速净变化同量级，进一步限制了积分归因。',
      '未解析项含层底应力、垂向动量输送、高频协方差、同化、z*坐标及重网格/离散误差；本轮不能将其指定为摩擦、垂向混合或其他单一机制。',
      '', '5. 对主线的修订',
      '可以写：2023夏季较弱的暖水东向输送主要对应上层异常纬向流减弱；局地平流增暖的事件差异也主要对应较弱的平均异常流。较弱的向东风应力异常与这一差异一致，但压力与科氏等项的补偿、较大的未解析动量贡献，使完整动力归因仍未闭合。',
      '不能写：已证明弱风独立造成全部输送减弱；初始暖水储备决定了后续流速；外海盆抑制已形成闭合因果链；表面压力阻力增强是三个事件差异的统一原因。',
      '', '口径与核验',
      '所有主背景为1982—2024全部43年；保留30/50/75m×去/不去趋势的全部结果。去趋势作用于已定义的诊断序列，不重新选择温度梯度或事件。月季均值与月中至月中的时间积分分别标示。',
      f'新共同有效体积覆盖：30m {qa["coverage"]["30"]*100:.4f}%，50m {qa["coverage"]["50"]*100:.4f}%，75m {qa["coverage"]["75"]*100:.4f}%。压力和流速梯度要求略收紧掩膜；与此前同43年背景的平流诊断在原掩膜上最大差 {qa["existing_43yr_process_max_error_C_month"]:.2g} °C/月，改用共同掩膜的全月全项最大变化 {qa["common_mask_change_max_C_month"]:.5f} °C/月。',
      '原三事件图的1982—2022背景、旧34年训练背景均未覆盖。不同背景的绝对距平不能混用；断面原始输送已逐月交叉复现。',
      f'数值核验：{validation["status"]}。解析场符号、分解恒等式、独立压力/风重算及实际时间导数检查通过；冻结的8项原模型与图件哈希不变。数值通过不代表完整物理闭合。',
      '本轮到此停止，未追加高频下载、外海盆筛选或新预测模型。'
    ]
    text='\n'.join(lines)+'\n';(OUT/'结果与解释.txt').write_text(text)
    caps={
      'M1_transport_and_advection':'图1：JAS 2023分别减1997和2015。a—b在逐格部分层厚上作精确对称分解，再积分到140°W ±9°断面；c—d为Niño3.4 0—50m异常流平流差，箭头为异常纬向流差，绿色虚线为共同背景温度纬向梯度（°C/1000km）；两者为层平均显示，底色仍按逐格乘积后积分计算；e保留三个发展年全部月值；f区分平均量乘积、水平与垂直协方差。这是运动学分解，不是因果干预。地图颜色在两例间固定。',
      'M2_partial_momentum_budget':'图2：0—50m层平均流速与同名区域风应力；SODA与ERA5网格、海洋掩膜不同，二者并非独立资料。c—d展示JAS动量倾向差与各项，虚线为实际倾向差；e—f为自1月15日起各项差值的累计，黑线为相对1月的实际流速差变化。期初差异单独标注。未解析项、积分误差和原有流速差异不可混称风强迫贡献。'}
    (OUT/'figure_captions.json').write_text(json.dumps(caps,ensure_ascii=False,indent=2))
    show=s[['u_m_s','u_prime_meanT','wind_m_s2','pressure_ssh_m_s2','pressure_density_m_s2','coriolis_m_s2','unresolved_m_s2']].copy()
    for c in show:
        if c.endswith('m_s2'):show[c]*=1e7
    show=show.rename(columns={'u_m_s':'u′ (m/s)','u_prime_meanT':'平流 (°C/月)','wind_m_s2':'风输入','pressure_ssh_m_s2':'海面压力','pressure_density_m_s2':'密度压力','coriolis_m_s2':'科氏项','unresolved_m_s2':'未解析'})
    sens=season[season.season.eq('JAS')][['event','depth_m','background','u_m_s','u_prime_meanT']]
    blocks=[]
    for para in text.strip().split('\n\n'):
        blocks.append('<p>'+html.escape(para).replace('\n','<br>')+'</p>')
    links=['section_pair_seasons.csv','section_reference_sensitivity_monthly.csv','case_seasons.csv','momentum_pair_intervals.csv','wind_product_comparison.csv','background_and_mask_bridge_JAS.csv','validation.json','protocol_before_run.txt','reproduce.txt','结果与解释.txt']
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>三事件夏季流速差异：动力诊断</title><style>body{font:16px/1.85 system-ui,-apple-system,sans-serif;color:#1d2c39;background:#f5f7f8;margin:0}main{max-width:1120px;margin:auto;padding:35px}h1{font-size:30px;line-height:1.4}p{background:white;padding:20px 24px;border-radius:10px;margin:18px 0}img{max-width:100%;background:white}figure{margin:35px 0}figcaption{font-size:14px;color:#536371}.lead{border-left:5px solid #247a9e;background:#eaf4f7;padding:22px}.table{overflow:auto}table{border-collapse:collapse;background:white;width:100%;font-size:14px}th,td{padding:9px 12px;border-bottom:1px solid #e1e6e9;text-align:right}a{color:#126c91}details{margin:20px 0}code{background:#edf0f2}</style><main>'''
    page+='<h1>三事件夏季流速差异：补上了哪一段？</h1><div class="lead"><strong>输送和平流的流速环节已量化；弱风输入获得一致性支持，完整动力归因仍未闭合。</strong><br>1997 / 2015 / 2023 · SODA3.15.2 · 全43年背景 · 两张机制图</div>'
    page+=''.join(blocks[:4])
    for stem in caps:page+=f'<figure><a href="{stem}.pdf"><img src="{stem}.png" alt="{html.escape(caps[stem])}"></a><figcaption>{caps[stem]} <a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></figcaption></figure>'
    page+='<h2>50m主设置：夏季均值</h2><p>受力列单位为10⁻⁷ m/s²。流速、平流和加速度不能直接相加或互换。</p><div class="table">'+show.round(5).to_html(border=0)+'</div>'
    page+=''.join(blocks[4:])
    page+='<details><summary>全部层厚与背景敏感性（JAS）</summary><div class="table">'+sens.round(5).to_html(index=False,border=0)+'</div></details>'
    page+='<h2>数据与复现</h2><ul>'+''.join(f'<li><a href="{html.escape(p)}">{html.escape(p)}</a></li>' for p in links)+'</ul><p>方法依据：<a href="https://www2.atmos.umd.edu/~carton/soda/soda3_readme.htm">SODA资料说明</a>；<a href="https://mom-ocean.github.io/assets/pdfs/MOM5_manual.pdf">MOM动量诊断</a>。本轮重建不是模式原生动量倾向输出。</p></main></html>'
    (OUT/'index.html').write_text(page)

def main():
    local=pd.read_csv(OUT/'local_monthly.csv',parse_dates=['time']);season=pd.read_csv(OUT/'case_seasons.csv');section=pd.read_csv(OUT/'section_pair_seasons.csv');wind=pd.read_csv(OUT/'wind_product_comparison.csv',parse_dates=['time'])
    figures(local,season,section,wind);report(local,season,section,wind)
    print('Two figures and report ready',flush=True)

if __name__=='__main__':main()
