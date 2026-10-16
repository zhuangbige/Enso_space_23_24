#!/usr/bin/env python3
"""Cross-event reproduction audit and Chinese conclusions from saved results."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
import run_paper_ro_pmm as run
import matplotlib.pyplot as plt
OUT=run.OUT

def main():
    f=pd.read_csv(OUT/'monthly_forecasts.csv',parse_dates=['init','target'])
    s=pd.read_csv(OUT/'seasonal_forecasts.csv',parse_dates=['init','issue','target'])
    run.score_all(f,s)
    scores=pd.read_csv(OUT/'scores.csv');ci=pd.read_csv(OUT/'PMM_improvement_block_bootstrap.csv')
    # Printed two-decimal values, visually transcribed from supplied PDF p.12 Fig.4b.
    years=[2002,2004,2006,2009,2014,2015,2018,2023,2005,2007,2010,2016,2020,2024,2008,2011,2017,2021,2022]
    printed=[.66,-.38,.63,.64,.71,.47,.83,.91,-.03,.73,.52,.81,.62,.98,.32,-.53,-.18,-.57,.10]
    cr=[]
    for year,value in zip(years,printed):
        row=dict(year=year,manuscript_Fig4b_r=value)
        for kind in ['monthly_detrended','seasonal_detrended']:
            selected=scores[scores.protocol.eq('paper_main')&scores.target_type.eq(kind)&scores.window.eq(f'year_{year}_FebJun')].iloc[0]
            row[kind+'_r']=selected.T_r
        cr.append(row)
    compare=pd.DataFrame(cr);compare.to_csv(OUT/'manuscript_event_skill_comparison.csv',index=False)
    run.style()
    fig,axes=plt.subplots(2,1,figsize=(13,8),gridspec_kw={'height_ratios':[1,1.1]})
    fig.subplots_adjust(top=.87,bottom=.16,hspace=.44)
    gg=f[f.protocol.eq('paper_main')&f.model.eq('RO')&f.month.between(2,6)&f.lead.between(1,9)]
    raw,p,clim=run.load();a,meta=run.prepare(raw,p,'2002-01-01','2024-12-01',True)
    ax=axes[0];obs=a.Nino34.loc['2002-01':'2025-04'];ax.plot(obs.index,obs,color='#222C38',lw=1.8,label='Observed')
    for init,g in gg.groupby('init'):ax.plot(g.target,g.T_model,color='#D55E00',lw=.7,alpha=.58)
    ax.axhline(0,color='.6',lw=.7);ax.grid(alpha=.12);ax.set(ylabel='Detrended Niño3.4 (°C)',title='(a) RO reconstruction: February–June monthly-state starts, 1–9 month leads')
    ax=axes[1];x=np.arange(len(compare));w=.25
    ax.bar(x-w,compare.manuscript_Fig4b_r,w,color='#263540',label='Supplied manuscript Fig. 4b')
    ax.bar(x,compare.monthly_detrended_r,w,color='#D55E00',label='Reconstruction: monthly convention')
    ax.bar(x+w,compare.seasonal_detrended_r,w,color='#2878B5',label='Reconstruction: issue / season convention')
    ax.set_xticks(x,compare.year.astype(str).tolist(),rotation=45);ax.axhline(0,color='.5',lw=.8);ax.grid(axis='y',alpha=.15)
    ax.set(ylabel='Event forecast correlation',title='(b) All 19 labeled events; no event omitted')
    ax.legend(ncol=3,fontsize=9,loc='lower center',bbox_to_anchor=(.5,1.02),frameon=False)
    fig.suptitle('How closely does the same-source RO reproduce the manuscript?',fontsize=17,y=.98)
    fig.text(.055,.035,'Paper diagnostic: 2002–2024 fitted coefficients include the events shown; this is not independent validation.\n'
             'Manuscript values are the printed two-decimal labels in Fig. 4b (supplied PDF, p. 12).\n'
             'Across-event pattern r: monthly 0.943, seasonal 0.960. Remaining amplitude and event-skill differences prevent a claim of exact replication.',fontsize=9,color='#4c5560',linespacing=1.5)
    run.save(fig,'manuscript_all_event_audit')
    # Matched start-month comparison avoids pooling unavailable 2026 starts.
    event_rows=[]
    for year in [2015,2026]:
        g=f[f.protocol.eq('past_1982')&f.year.eq(year)&f.month.isin([1,2])&f.lead.between(1,12)&f.model.isin(run.MODELS)]
        for name,v in g.groupby('model'):
            row=dict(year=year,init_months='January and February',model=name,**run.metrics(v))
            for var in ['T','H']:
                base=run.metrics(g[g.model.eq('RO')])[var+'_RMSE']
                row[var+'_improvement_pct']=100*(1-row[var+'_RMSE']/base)
            event_rows.append(row)
    events=pd.DataFrame(event_rows);events.to_csv(OUT/'event_JanFeb_matched_scores.csv',index=False)
    # Explicit source and execution provenance; preserve source code hashes.
    files=[run.SOURCE/'raw_indices.csv',run.PMM,OUT/'protocol_frozen_before_run.txt']+[run.ROOT/'scripts'/n for n in ['fetch_paper_ro_inputs.py','build_paper_ro_indices.py','paper_ro_slim.py','run_paper_ro_pmm.py','finalize_paper_ro_results.py']]
    manifest=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    (OUT/'analysis_manifest.json').write_text(json.dumps(manifest,indent=2))
    lines=[
    'RO论文方法复现与标准PMM独立验证（2026-10-14）',
    '',
    '结论：已完成同源数据、文献sLIM实现、19个事件复现核查及过去资料限定的PMM消融。论文整体事件技能结构接近，但未达到逐点严格复现；独立预报仍明显低估2015/2026发展，PMM只有有限且不稳健的平均改善，不能声称问题已解决。',
    '',
    '1. 复现到什么程度',
    '所依据稿件：用户提供 manuscript.pdf，方法第4–6页，实际事件预报图4见第12页。另核对2026发表版 DOI10.1029/2025GL118767 和其引用的方法 Chen & Jin (2021) DOI10.1175/JCLI-D-20-0874.1 附录A5–A7。',
    '数据改为ERSSTv5 Niño3.4和GODAS逐网格20°C等温线深度，以5S–5N120E–80W有效海洋面积平均作为WWV状态h，单位m；未将总WWV(m³)和D20(m)混用。',
    '论文窗口：1991–2020气候态，2002–2024线性趋势和系数拟合；月值线性插值为六个五天步长，中心差分，零阶滞后1月、修正项滞后5天，年和半年季节项，二阶扰动解，预报无随机强迫。',
    '2015年2–6月月均状态起报、1–9个月：r=0.450（同样去趋势坐标；展示坐标0.449），稿件标注0.47；RMSE=1.237°C，仍明显低估强度。IRI签发/季平均口径为r=0.306、RMSE=1.456°C。不能从0.450接近0.47就断言作者采用了哪种口径。',
    '与稿件图4b所有19个事件比较：月值口径的事件技能结构相关=0.943，平均绝对差=0.110，最大差=0.502（2002）；季平均口径分别0.960、0.090、0.361。这里的0.943/0.960是“不同事件的技能排序结构”相关，不是逐月预报准确率。',
    '主配置没有因2015效果而更换。整块协方差解、1/3谐波和去趋势至2025年4月的敏感性都保存在scores.csv；例如整块解2015月值r=0.591，与扰动解并不完全相同。',
    '尚缺：作者实际RO系数、完整起报与季平均映射、插值细节、谐波个数及去趋势窗口。网站补充材料未成功获取，正文未充分说明。当前应称“透明假设下的方法复现”，不能写“严格复现论文”。',
    '',
    '2. PMM独立验证的定义',
    '主方案：1982年起扩展训练，每个起报年仅用前一年12月及以前的数据拟合气候态、趋势和所有动力系数；验证2006–2024全部12个月起报、月提前期1–9，共19年、2052个起报–目标对。三年连续块bootstrap保留重叠预报关联，2000次。',
    '标准PMM直接采用作者公开MCA SST和wind两列；训练期只重定均值与尺度，没有另造区域代理，也没有额外去ENSO。分别跑RO、+SST、+wind、+两者。所有PMM状态在起报后自由积分，绝不使用未来PMM实况。完整模型切断PMM→T/h另存cut_both，仅作机制诊断。',
    '当前版本再分析/指数用于回报；PMM固定模态用1950–2005，故2006年起验证。产品自身历史去趋势和数据修订不等于当年实时可得版本，因此这是拟合过程独立的伪业务回报，不是严格实时资料检验。',
    '',
    '2006–2024主结果（月提前期1–9；技能提升为RMSE下降百分比）：']
    for name in run.MODELS:
        ss=scores[scores.protocol.eq('past_1982')&scores.model.eq(name)&scores.target_type.eq('monthly')&scores.window.eq('2006_2024')].iloc[0]
        line=f'{run.LABELS[name]}：Niño3.4 RMSE={ss.T_RMSE:.4f}°C；WWV RMSE={ss.H_RMSE:.4f}m。'
        if name!='RO':
            ts=ci[ci.protocol.eq('past_1982')&ci.model.eq(name)&ci.period.eq('2006_2024')&ci.variable.eq('T')].iloc[0]
            hs=ci[ci.protocol.eq('past_1982')&ci.model.eq(name)&ci.period.eq('2006_2024')&ci.variable.eq('H')].iloc[0]
            line+=f' T改善{ts.improvement_pct:.2f}%（95%区间{ts.CI_low:.2f}至{ts.CI_high:.2f}%）；h改善{hs.improvement_pct:.2f}%（{hs.CI_low:.2f}至{hs.CI_high:.2f}%）。'
        lines.append(line)
    lines += ['',
    '所有PMM改善的95%区间都跨零；没有足够证据宣称稳定提升。以2002年为训练起点的敏感性，2015–2024主比较中+SST的T RMSE由0.74017仅到0.73998°C，h由4.1916升至4.3093m；结果依赖训练资料长度，不能只报告长训练的正收益。',
    '',
    '3. 2015和2026个例',
    '保持独立验证，训练终点分别2014/2025年底。2015年3月起报完整12个月：RO T RMSE=1.879°C，+PMM-SST=1.382°C，下降26.5%；但h从5.915升至7.524m，恶化27.2%。相图仍没抓住大幅增暖及后期放电。T趋势相关虽升到0.930，仍不表示幅度预测正确。',
    '2026年2月起报：RO T RMSE=1.593°C，+PMM-SST=1.553°C，只下降2.6%；h从8.861到8.517m。2026年1月分别1.647→1.591°C和8.576→8.031m。不能称为解决2026增长幅度的低估。',
    '2026标准PMM仅到2月，因此仅画1月和2月起报；ERSSTv5实况到9月、GODAS到8月，逐变量只评已有实况（1月起报T8个月/h7个月，2月起报T7个月/h6个月）。未来段淡色，仅表示模型推演；2026不是完整事件评分。',
    '同起报月份（1/2月）2015与2026汇总另见event_JanFeb_matched_scores.csv。两年验证窗口不同，不能直接把其RMSE高低归因于哪一年更可预测。',
    '',
    '4. 数据和数值检查',
    '1980–2026所有月份GODAS有效海洋格点为4653，掩膜稳定，正确按有效海洋权重归一。与独立NOAA/PMEL总WWV序列重算同基准异常，相关0.9977，等效深度RMSE约0.495m；绝对体积均值差约−3.37%，因此没有把两产品当完全相同。',
    '2026 ERSST更新与本地旧版：1–5月差值≤0.0007°C，6月修订+0.0983°C；本次2026统一采用最新下载文件。',
    '合成已知季节算子整块恢复误差5e−16；扰动近似误差约6.36e−4（与近似性质一致）。起报后所有T/h/PMM增加999再计算，预测变化为0；变量单位变换结果不变；RK4月24与48步差最大约2.7e−7。',
    '',
    '5. 图和复现入口',
    'baseline_2015_reconstruction.png：2015论文窗口/独立训练、月值/季平均两种口径。',
    'manuscript_all_event_audit.png：2002–2024整段羽状预报和稿件19个事件技能核查。',
    'event_2015_init_01/02/03.png、event_2026_init_01/02.png：Niño3.4时间序列、WWV时间序列、横轴Niño3.4/纵轴WWV相图。所有模型共享同一物理初值；没有沿途重置。',
    'independent_skill_by_lead.png、independent_PMM_improvement.png：多事件独立技能和不确定性。所有图另存SVG矢量版。',
    'raw_indices.csv和input_QA.json位于data/derived/research_2026/paper_ro_baseline_20261014。',
    '依次运行scripts/fetch_paper_ro_inputs.py、build_paper_ro_indices.py、run_paper_ro_pmm.py、finalize_paper_ro_results.py。macOS环境需DYLD_LIBRARY_PATH=/opt/anaconda3/pkgs/libjpeg-turbo-2.0.0-h1a28f6b_0/lib；使用/opt/anaconda3/bin/python。',
    '',
    '研究判断：当前支持“标准PMM-SST包含增量信息、部分个例有所改善”，不支持“已经显著提升RO预报”。应先取得作者配置以闭合严格复现差距；后续若比较非线性、风爆发或时变外部强迫，应另立实验，不能用2015/2026实况反向调整当前基准。',
    '',
    '公开来源：',
    'https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025GL118767',
    'https://journals.ametsoc.org/view/journals/clim/34/12/JCLI-D-20-0874.1.xml',
    'https://www.osti.gov/servlets/purl/1850896',
    'https://www.aos.wisc.edu/dvimont/MModes/PMM.html',
    'https://www.aos.wisc.edu/dvimont/MModes/RealTime/PMM.txt',
    'https://psl.noaa.gov/data/gridded/data.noaa.ersst.v5.html',
    'https://psl.noaa.gov/data/gridded/data.godas.html',
    ]
    (OUT/'results_cn.txt').write_text('\n'.join(lines)+'\n')
    print(events.to_string(index=False),flush=True)
    print('report saved',OUT/'results_cn.txt',flush=True)
if __name__=='__main__':main()
