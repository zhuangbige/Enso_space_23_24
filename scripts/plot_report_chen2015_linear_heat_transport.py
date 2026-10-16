#!/usr/bin/env python3
"""Make a figure and an auditable report for the requested two retained terms."""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/chen2015_linear_transport_20261014'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'tmp/chen2015_linear_mpl'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TEMP = '#56859b'
FLOW = '#d98270'
BLACK = '#222222'
COLS = ['vbar_Tprime_pw', 'vprime_Tbar_pw', 'linear_sum_pw']
LABELS = [r'$\overline{v}T^{\prime}$', r'$v^{\prime}\overline{T}$', 'Linear sum']
COLORS = [TEMP, FLOW, BLACK]


def main():
    full = pd.read_csv(OUT/'two_term_monthly_main.csv',parse_dates=['time'])
    primary = full[full.geometry.eq('climatological_sigma26')]
    focus = primary[primary.time.dt.year.isin([2016,2024]) & primary.time.dt.month.between(1,5)].copy()
    summary = pd.read_csv(OUT/'2015_2023_JanMay_summary.csv')
    chosen = summary.query("baseline == '1980-2022' and eos == 'TEOS10' and geometry == 'climatological_sigma26'").set_index('onset_year')
    phases=[]
    for year,g in focus.groupby(focus.time.dt.year):
        for name,months in [('Jan-Feb',[1,2]),('Mar-May',[3,4,5]),('Jan-May',[1,2,3,4,5])]:
            piece=g[g.time.dt.month.isin(months)]
            duration=piece.time.dt.days_in_month.to_numpy()*86400
            row={'onset_year':int(year-1),'analysis_year':int(year),'window':name,
                 'integration':'sum of complete calendar-month means times month duration',
                 'days':int(duration.sum()/86400)}
            for col in COLS:
                row[col.replace('_pw','_zj')]=float(np.sum(piece[col].to_numpy()*duration)/1e6)
            phases.append(row)
    phases=pd.DataFrame(phases)
    phases.to_csv(OUT/'calendar_month_phase_integrals.csv',index=False)

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
        'axes.titlesize':13,'axes.titleweight':'bold','axes.labelsize':11,
        'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,
        'axes.linewidth':1.1,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,2,figsize=(13.2,9.5),gridspec_kw={'hspace':.36,'wspace':.27})
    fig.subplots_adjust(top=.84,bottom=.18,left=.08,right=.97)
    fig.suptitle('Linear Warm-Layer Heat Transport: 2015/16 and 2023/24',fontsize=20,fontweight='bold',y=.975)
    fig.text(.5,.935,r'$5^{\circ}$N, $140^{\circ}$W-$80^{\circ}$W | $\sigma_\theta=26$ boundary | Positive northward',
             ha='center',fontsize=12,color='#555555')
    fig.text(.5,.906,r'Retained terms: $\overline{v}T^{\prime}$ and $v^{\prime}\overline{T}$ | 1980-2022 monthly climatology',
             ha='center',fontsize=12,color='#b65747')
    for j,year in enumerate([2016,2024]):
        ax=axes[0,j]
        event=focus[focus.time.dt.year.eq(year)]
        x=event.time.dt.month.to_numpy()
        for col,label,color in zip(COLS,LABELS,COLORS):
            ax.plot(x,event[col],'-o',color=color,lw=2.3 if col=='linear_sum_pw' else 2,
                    ms=4.5,label=label)
        ax.axhline(0,color='#777777',lw=.8,ls='--')
        ax.set(xlim=(.85,5.15),ylim=(-.46,1.09),xticks=np.arange(1,6),
               xticklabels=['Jan','Feb','Mar','Apr','May'],ylabel='Linear heat-transport terms (PW)')
        ax.set_title(f'({chr(97+j)})  {year-1}/{str(year)[-2:]} decay: January-May {year}',loc='left',pad=10)
        if j==0: ax.legend(frameon=False,fontsize=10,loc='upper right')
        ax.text(.98,.04,'Climatological section',ha='right',va='bottom',transform=ax.transAxes,
                color='#777777',fontsize=9)

    ax=axes[1,0]
    x=np.arange(2)
    values1=chosen.loc[[2015,2023],'vbar_Tprime_calendar_months_zj'].to_numpy()
    values2=chosen.loc[[2015,2023],'vprime_Tbar_calendar_months_zj'].to_numpy()
    ax.bar(x,values1,.52,color=TEMP,label=LABELS[0])
    ax.bar(x,values2,.52,bottom=values1,color=FLOW,label=LABELS[1])
    for i,(a,b) in enumerate(zip(values1,values2)):
        ax.text(i,a+b+.10,f'{a+b:.2f}',ha='center',fontweight='bold',fontsize=12)
        ax.text(i,a+b/2,f'{b:.2f}',ha='center',va='center',fontsize=11,color='white',fontweight='bold')
        ax.text(i+.29,max(a/2,.12),f'{a:.2f}',ha='left',va='center',fontsize=10,color=TEMP)
    ax.set(xticks=x,xticklabels=['2016','2024'],xlim=(-.55,1.65),ylim=(0,3.95),ylabel='Integrated linear terms (ZJ)')
    ax.set_title('(c)  Full calendar months: 1 Jan-31 May',loc='left',pad=10)
    ax.legend(frameon=False,loc='upper right',fontsize=10)

    ax=axes[1,1]
    windows=['Jan-Feb','Mar-May']
    x=np.arange(2)
    width=.23
    for k,(col,label,color) in enumerate(zip(COLS,LABELS,COLORS)):
        key=col.replace('_pw','_zj')
        vals=[]
        for win in windows:
            both=phases[phases.window.eq(win)].set_index('analysis_year')
            vals.append(both.loc[2024,key]-both.loc[2016,key])
        bars=ax.bar(x+(k-1)*width,vals,width,color=color,label=label)
        for b,val in zip(bars,vals):
            ax.annotate(f'{val:+.2f}',(b.get_x()+b.get_width()/2,val),
                        xytext=(0,4 if val>=0 else -5),textcoords='offset points',
                        ha='center',va='bottom' if val>=0 else 'top',fontsize=9)
    ax.axhline(0,color='#777777',lw=.9)
    ax.set(xticks=x,xticklabels=windows,ylim=(-4.25,4.25),ylabel='2024 minus 2016 (ZJ)')
    ax.set_title('(d)  Early and late contributions compensate',loc='left',pad=10)
    ax.legend(frameon=False,fontsize=9,loc='upper left',ncol=3)

    fig.text(.08,.125,'SODA3.15.2 temperature, salinity and current. Main integrals use complete calendar months (152 days in both years).',fontsize=9.5)
    fig.text(.08,.101,r'Only the requested two linear terms are included; the background and nonlinear terms are omitted. $T_{ref}=0^{\circ}$C.',fontsize=9.5)
    fig.text(.08,.077,'Monthly climatological density surfaces fix section geometry; instantaneous surfaces are evaluated separately.',fontsize=9.5)
    fig.text(.08,.053,'Chen (2015) density threshold applied to a regional 5N gate; this is not a closed heat budget or basin-wide WWV.',fontsize=9.5)
    for ext in ['png','svg']:
        fig.savefig(OUT/f'two_term_heat_transport_2015_2023.{ext}',dpi=240,facecolor='white')
    plt.close(fig)

    # A second figure shows the spatial patterns behind the section integrals.
    import xarray as xr
    d=xr.open_dataset(OUT/'retained_terms_2016_2024_sections.nc')
    dx=6371000*np.cos(np.deg2rad(5))*np.deg2rad(.5)
    dz=d.climatological_active_area/dx
    flds=[(d[name]*dz).sum('depth')/1e6 for name in
          ['vbar_Tprime_heat_flux_density','vprime_Tbar_heat_flux_density']]
    fig,axes=plt.subplots(2,2,figsize=(13.2,8.8),sharex=True,sharey=True,
                          gridspec_kw={'hspace':.32,'wspace':.14})
    fig.subplots_adjust(top=.85,bottom=.17,left=.08,right=.86)
    fig.suptitle('Where the Two Linear Transport Contributions Occur',fontsize=19,fontweight='bold',y=.974)
    fig.text(.5,.928,'5N | Warm-layer vertical integrals | Same color scale within each row',ha='center',fontsize=11)
    for r,fld in enumerate(flds):
        limit=float(np.ceil(np.abs(fld.values).max()*10)/10)
        for c,year in enumerate([2016,2024]):
            ax=axes[r,c]
            ev=fld.sel(time=fld.time.dt.year==year)
            mesh=ax.pcolormesh(np.r_[220, d.lon.values+.25],np.arange(.5,6.5),ev.values,
                               cmap='RdBu_r',vmin=-limit,vmax=limit,shading='flat')
            ax.set(yticks=np.arange(1,6),yticklabels=['Jan','Feb','Mar','Apr','May'],ylim=(5.5,.5),
                   xticks=[220,240,260,280],xticklabels=['140W','120W','100W','80W'])
            ax.set_title(f'({chr(97+r*2+c)})  {year}: '+LABELS[r],loc='left',pad=10)
        box=axes[r,1].get_position()
        cax=fig.add_axes([.887,box.y0,.018,box.height])
        fig.colorbar(mesh,cax=cax,label='Vertically integrated flux (MW m$^{-1}$)')
    fig.text(.08,.09,'Positive northward. Each longitude is vertically integrated through the monthly climatological sigma=26 warm layer.',fontsize=9.5)
    fig.text(.08,.061,'Different color ranges between rows reflect their different magnitudes; 2016 and 2024 share the same range within each row.',fontsize=9.5)
    for ext in ['png','svg']:
        fig.savefig(OUT/f'two_term_longitude_month_2015_2023.{ext}',dpi=240,facecolor='white')
    plt.close(fig)

    # Report does not treat the requested omission as an empirical verification of smallness.
    rows=[]
    for year in [2015,2023]:
        r=chosen.loc[year]
        rows.append(f"{year}/{year+1}: 温度项 {r.vbar_Tprime_calendar_months_zj:.6f} ZJ；环流项 {r.vprime_Tbar_calendar_months_zj:.6f} ZJ；线性合计 {r.linear_sum_calendar_months_zj:.6f} ZJ。")
    report='''按用户指定的两项重新计算北向暖层热输送
2026-10-14

一、实际计算范围
暖水储备的定义继续采用 Chen et al. (2015) 的 sigma_theta=26 等密度面方案，本次没有另换储备定义，也没有重新拟合 RO/PMM。
本次计算的是 Maryland 既有东太平洋北向出口：5°N、140°W—80°W，海表至 sigma0=26 层的两个线性输送项。5°N 是区域扩展，不声称复制 Chen 原文 +/-9°N 的 STC 断面。未把旧 H20/Q20 或固定层 OHC′ 数值换标签。
对比 2015/16 与 2023/24 厄尔尼诺衰减期，即 2016 和 2024 的1—5月；同时保留13个历史事件的同定义结果。

二、只保留用户指定的两项
Q_temperature = rho0*cp*∫v_bar*theta_prime dS
Q_circulation = rho0*cp*∫v_prime*theta_bar dS
Q_linear = Q_temperature + Q_circulation
省略 v_bar*theta_bar 和 v_prime*theta_prime。本次是按指定近似计算，不把线性合计称作实际总热输送，也不声称本次已验证非线性项大小。
theta 为 SODA 位温（摄氏度），参考温度0°C；rho0=1025 kg/m3、cp=3990 J/(kg K)。正值表示北向异常贡献；负值不自动表示实际总流速已经向南。
两项逐格相乘后作断面积分，不能以平均流速乘平均温度代替。

三、气候态、暖层下边界与积分
主气候态：1980—2022年的同月平均；逐年对应月份减同月均值得异常。无去趋势、无2—8年带通、无平滑；这是回溯物理诊断，不是实时预报训练。
主断面：用同月平均温盐确定 sigma0=26 的深度，对全部事件使用同一月份的同一几何。这样省略背景项的假设与线性分解一致。采用TEOS-10，由实用盐度转换绝对盐度、由位温转换保守温度，计算0 dbar参考的密度异常；热输送仍以资料原始位温theta按上述rho0*cp近似计算。
对跨等密度面的末层使用部分层厚；已检查所有温盐剖面均在已存数据层内穿过26面，没有把300 m硬当作下边界。
另外计算同样两项在逐月实际等密度面断面上的积分；这是几何敏感性，并非补算背景几何项或完整非线性预算。
主累计采用完整1—5月的每月平均乘当月秒数；2016与2024都是152天。旧分析中Jan15—May15的月中梯形积分另列，实际仅121天，不与完整月份累计混称。

四、主结果（完整1—5月，ZJ）
'''+ '\n'.join(rows)+'''

2024−2016：温度异常输送项减少约0.310 ZJ，环流项增加约0.095 ZJ，合计减少约0.216 ZJ（约6.6%）。
这套两项近似下，两年输送均以环流项为主；2024温度项明显偏弱，但不能将五个月的环流项整体描述为更弱。
逐月结构更清楚：2016年1—2月环流贡献很强，3—5月转为负；2024年1—5月环流项持续为正。负项描述相对于月气候态的贡献。

五、窗口与方法敏感性
旧Jan15—May15口径：2016温度项0.398、环流项1.952、合计2.350 ZJ；2024分别0.168、2.287、2.455 ZJ。该较短窗口的两年合计排序与完整月份相反。
因此稳健表述是：温度项2024较弱、环流项有明显阶段差异、两年线性合计相近且排序对累计窗口敏感。不能仅据一个总数声称2023显著更强/更弱放电。
输出还保留1980—2014基期、EOS-80密度算法和实际移动断面的敏感性，详见2015_2023_JanMay_summary.csv。数值不能与旧热含量预算的ZJ直接合并。

六、适用边界
这是单个开放边界的热输送诊断，v_prime*theta_bar 的数值依赖统一温度参考；不能解释为完整箱体净热损失或暖水体积变化。对其他参考温度，可由同文件的v_prime_volume_sv计算相应改变量。
使用SODA3.15.2的0.5°重网格再分析，流速重网格不是原生网格守恒输送；本次不宣称严格闭合热预算。
按用户要求不引入背景和非线性项；不据此直接证明PMM因果作用。本轮只更新这两项输送，不修改先前预报技巧和储备数值。

七、数据与复现
历史温盐流速：soda3_5n_geostrophic_sections_1980_2022.nc，来自APDRC SODA3.15.2；2024：UMD官方年度文件的1—5月断面缓存。两者交错网格插值方式一致，坐标尾数差已核查并对齐。
官方数据说明：https://www2.atmos.umd.edu/~carton/soda/soda3_readme.htm
状态方程说明：https://www.teos-10.org/pubs/gsw/html/gsw_sigma0.html
计算脚本：scripts/analyze_chen2015_linear_heat_transport.py
出图与报告：scripts/plot_report_chen2015_linear_heat_transport.py
SHA256、有效层检查、两项求和和气候态零异常检验：numerical_QA.json。
'''
    (OUT/'results_and_methods_cn.txt').write_text(report)
    display=chosen[['vbar_Tprime_calendar_months_zj','vprime_Tbar_calendar_months_zj','linear_sum_calendar_months_zj']].rename(
        columns={'vbar_Tprime_calendar_months_zj':'temperature_term_zj',
                 'vprime_Tbar_calendar_months_zj':'circulation_term_zj',
                 'linear_sum_calendar_months_zj':'linear_sum_zj'})
    display.to_csv(OUT/'main_result_full_JanMay.csv')
    print(display)
    print(phases.to_string(index=False))


if __name__=='__main__':
    main()
