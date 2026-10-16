"""Curate existing evidence and state a bounded final-test proposal; no fitting."""
from pathlib import Path
import os, json, shutil, hashlib, html
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/maryland_three_events_mpl')
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/d20_pmm_figure_selection_20261015'
OUT.mkdir(parents=True,exist_ok=True)
F=ROOT/'outputs/interview_redesign_20261014/source_data'
P=ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015'
W=ROOT/'outputs/research_2026/three_event_process_followup_20261015'
B=ROOT/'outputs/research_2026/pmm_advection_bridge_20261015'
N=ROOT/'outputs/research_2026/d20_pmm_process_bridge_20261015'
WW=ROOT/'outputs/research_2026/wwv26_pmm_replacement_20261015'
for group in ['00_overview','01_main','02_mechanism_checks','03_backup']:
    (OUT/group).mkdir(exist_ok=True)

# A standalone display of the existing three-event forecasts (unchanged values).
t=pd.read_csv(F/'RO_PMM_three_event_trajectories.csv')
s=pd.read_csv(F/'RO_PMM_three_event_metrics.csv')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
    'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
fig,axs=plt.subplots(1,3,figsize=(14.5,5.7),sharey=True)
fig.subplots_adjust(top=.79,bottom=.34,wspace=.16)
fig.suptitle('Adding PMM improves 1997/2015 retrospective skill, but worsens 2023',fontsize=18,y=.97)
fig.text(.5,.89,'Five February–June starts per event; lines show the full available seasonal trajectories',ha='center',color='#555555')
for j,y in enumerate([1997,2015,2023]):
    ax=axs[j];g=t[t.year.eq(y)].copy()
    g['x']=(pd.to_datetime(g.center).dt.year-y)*12+pd.to_datetime(g.center).dt.month
    for name,col,ls in [('RO','#9ba7b0','--'),('RO_SST','#2b6f97','-')]:
        for n,(_,a) in enumerate(g[g.method.eq(name)].groupby('init')):
            a=a.sort_values('x')
            ax.plot(a.x,a.value,color=col,ls=ls,lw=1.35,alpha=.85,label=('RO' if name=='RO' else 'RO + PMM') if n==0 else None)
    o=g.groupby('x')['observed'].first()
    ax.plot(o.index,o.values,color='#222222',lw=2.2,label='Observed')
    q=s[s.year.eq(y)].set_index('model');skill=100*(1-q.loc['RO_SST','RMSE']/q.loc['RO','RMSE'])
    ax.set_title(f'{y}   |   skill change {skill:+.1f}%',fontweight='bold')
    ax.set_xticks([3,6,9,12,15],['Mar','Jun','Sep','Dec','Mar +1']);ax.set_xlim(2,15)
    ax.axhline(0,color='#999999',lw=.6);ax.grid(axis='y',alpha=.16)
    ax.text(.02,-.23,f"RMSE  {q.loc['RO','RMSE']:.3f} → {q.loc['RO_SST','RMSE']:.3f} °C\nr          {q.loc['RO','r']:.3f} → {q.loc['RO_SST','r']:.3f}",transform=ax.transAxes,fontsize=11,va='top')
axs[0].set_ylabel('Seasonal Niño3.4 SSTA (°C)')
axs[0].legend(frameon=False,fontsize=10,loc='upper left')
fig.text(.075,.075,'Scores: 25 overlapping start–season pairs, 9 unique targets/event, common center leads 1–5; r is event-pooled Pearson correlation.\n'
 'Frozen 2002–2024 fits: 1997 uses later-fitted parameters; 2015/2023 are in sample. No post-start observed forcing.\n'
 'RO uses SST and GODAS mean D20. The PMM extension refits the full operator; its difference is not a pure causal PMM effect.',
 fontsize=9,color='#555555',va='center')
stem=OUT/'03_backup/S0_legacy_D20_forecasts'
for ext in ['png','pdf','svg']:fig.savefig(stem.with_suffix('.'+ext),dpi=180,bbox_inches='tight',facecolor='white')
plt.close(fig)

entries=[]
def add(group,name,source,title,claim,limit,priority):
    dest=OUT/group/name
    if source:
        for ext in ['png','pdf','svg']:
            p=source.with_suffix('.'+ext)
            if p.exists():shutil.copy2(p,dest.with_suffix('.'+ext))
    entries.append(dict(group=group,name=name,title=title,claim=claim,limit=limit,priority=priority,
        source=str(source) if source else str(F/'RO_PMM_three_event_trajectories.csv'),
        image=str(dest.relative_to(OUT))+'.png'))

add('00_overview','Overview_D20_bridge',B/'Bridge01_skill_correction_advection','总览｜原D20预报与物理差异','保留原预报结果与平流事实的概览，适合介绍研究问题。','旧拟合协议；机制是否成立由下面新的同状态留出检验判断。','问题总览')
add('01_main','M1_D20_forecasts',N/'D0_D20_PMM_forecasts','M1｜D20预报：提出问题','同状态、同训练留出下，1997/2015改善，2023下降；原预报现象的方向保留。','新34年事件剔除设置，数值不是旧13%/19%/−30%；仍是回顾性检验。','最重要')
add('01_main','M2_local_process_history',P/'Fig24_matched_local_process_history','M2｜物理过程：春季建立，夏季减弱','2023异常纬向平流春季已提供增暖，夏季减弱；同时保留海表与未解析项。','层温度不同于SST；这张物理诊断不因模型状态换成D20而改变。','主线过程')
add('01_main','M3_advection_robustness',P/'Fig29_zonal_advection_robustness','M3｜最明确结论：2023夏季平流增暖稳健偏弱','30/50/75m与趋势处理均保留2023低于1997/2015。','2023绝对正负号依赖背景，六种设置不是独立样本。','最重要')
add('01_main','M4_D20_process_reconstruction',N/'D1_D20_PMM_process_reconstruction','M4｜真正的桥接检验：D20平流重建','与预报完全相同的SST、D20、PMM状态；比较有无PMM的实际过程重建。','2015变差、2023在主设置中改善，不能直接把预报技巧变化归于平流。条件重建不是自由预报。','最重要')
add('01_main','M5_D20_process_sensitivity',N/'D2_process_skill_sensitivity','M5｜桥接解释是否稳健','2023平流重建增益依赖趋势处理；2015未显示改善。','主文不能只选主设置的+25.2%；估计与背景敏感性要共同呈现。','必要约束')
add('02_mechanism_checks','D1_airsea_space_time',W/'Fig18_airsea_space_time_context','D1｜风场空间背景','交代向东风应力异常出现的经度与持续性。','月平均不是WWB，观测风场不全由PMM造成。','机制补充')
add('02_mechanism_checks','D2_process_compensation',P/'Fig25_common_season_process_comparison','D2｜过程抵消与未解析倾向','2023动力增暖弱而海表冷却也弱，约束单一原因解释。','异常流柱合并纬向与经向；未解析项与净增暖同量级。','机制补充')
add('03_backup','S0_legacy_D20_forecasts',None,'S0｜原D20预报图','保留最初13%/19%/−30%的结果出处。','原2002—2024拟合期内/回推结果，不与新事件剔除数值混排。','原结果')
add('03_backup','S1_old_WWV_process',P/'Fig27_process_projection_check','S1｜旧层温度＋三区WWV26过程重建','保留历史模型诊断。','已由M4的D20同状态重建替代，不再充当当前预报误差的证据。','历史备份')
add('03_backup','S2_WWV_forecast_trial',WW/'W1_forecasts_heldout34','S2｜WWV26替换试验','完整保存中途WWV26结果以便追溯。','用户已明确恢复D20；此图不进入当前主线。','历史备份')
add('03_backup','S3_ocean_configuration',W/'Fig20_ocean_configuration_and_transport','S3｜暖水配置与输送','回答2023是否已存在暖水东向输入。','断面体积输送不等于局地温度倾向。','问答备份')

decision='''图件整理与最后一步｜2026-10-15｜最终按用户要求恢复D20

当前模型：预报和过程重建都使用[ERSST Niño3.4, GODAS D20]，加入PMM后为[ERSST Niño3.4, GODAS D20, 标准PMM-SST]。本轮没有任何WWV26预测状态。原物理平流诊断保持不变。

已完成什么
已恢复D20预报主线，并将旧层温度＋三区WWV26过程重建替换为同状态D20重建。共用1982—2024资料，排除1996—1998、2014—2016、2022—2024，以其余34年拟合背景/趋势/尺度/算子/响应。主设置50m、去趋势、二阶sLIM响应矩；保留精确解、不去趋势、30/75m以及同状态OLS检查。过程重建使用实际月状态，不是初始化自由预报。

五张主图
M1 D20预报轨迹和技巧：提出PMM对事件影响不同的问题。
M2 局地过程逐月图：说明2023春季已有增暖通道而夏季减弱。
M3 平流稳健性：最明确的物理结论，2023夏季增暖贡献相对较弱。
M4 D20平流重建：检验同一组状态能否把PMM技巧变化落实到平流过程。
M5 重建增量敏感性：显示桥接解释的稳定性和局限。
最重要三张：M1、M3、M4。M2解释时间发展，M5避免挑选有利设置。
风场空间图、季节过程抵消放机制补充；旧WWV26过程重建和WWV26替换试验留历史备份。原D20旧协议13%/19%/−30%原图留出处，不覆盖，不冒充新训练结果。

新的同口径结果
海温预报RMSE技巧：1997 +7.09%，2015 +14.20%，2023 −24.18%。这些来自事件剔除34年设置，与旧图的数值不同，方向保持。
发展年12个月平流条件重建的PMM RMSE技巧：1997 −0.45%，2015 −16.88%，2023 +25.23%。
JAS三个月平流重建：1997 +6.92%，2015 −4.54%，2023 +18.33%。事件个数与月份太少，不作显著性判断。
JAS实际/无PMM重建/有PMM重建（°C/标准月，恢复原固定同月背景）：
1997：+0.1547 / +0.0438 / +0.0602；
2015：+0.1105 / −0.0954 / −0.1015；
2023：−0.0503 / −0.1135 / −0.0806。
2015连夏季平流的符号都未恢复。2023的主设置改善源于重建更接近实际，并不表示PMM增加了真实世界平流增暖。
全部108个月留出窗口的平流RMSE只改善1.48%，相对零异常的MSE技巧仍为负（−0.126）；2023的全年改善在不去趋势下消失或转为小幅下降。平流实际偏弱的排序仍稳健，重建增益却不稳健，这是两件事。

当前桥梁结论
状态变量和训练口径的桥梁已经搭好，但“PMM预报技巧变化由异常纬向平流解释”未获得支持。不能把2015预报变好直接解释为平流表示更好，也不能把2023预报变差直接解释为平流表示更差。不能为得到同方向关系而只挑背景、季节或算法。

最后一步应做什么（本轮未继续运行）
最后只做一个直接的时序一致性检验：用已经冻结的D20＋PMM完整模型与PMM→SST/D20通道切断模型，比较逐月海温修正；再将各自自由预报状态送入相同、冻结的过程响应关系，比较平流预测修正及实际平流误差。所有起报都保持2—6月，统一目标月份，不沿途输入实际状态。与本轮的实际状态条件重建并排，区分过程响应表示不足与状态预测误差。
条件重建的PMM修正还应拆成显式PMM项和重新估计SST/D20系数产生的部分。两者的恒等分解已数值核验，可直接输出，不把显式项称为现实因果贡献。
主输出是一张三事件图：上排自由海温完整/切断差异；中排冻结响应下平流预测与实际；下排条件重建与自由状态诊断的差异。SST与固定层平流单位分开，不用其比值做归因百分比。
若修正的符号、时间和误差改善仍不一致，本研究就应保留为“PMM影响事件预测，但单一纬向平流通道不足以解释”。这也是可完成的科学结论，无需继续寻找能制造一致方向的模型。
如果这一步显示稳定一致，再单独开展PMM—风应力—异常流的时空路径检验；它属于更强机制归因阶段，不是当前整理图件必须完成的部分。
'''
(OUT/'选图与最后一步.txt').write_text(decision)
pd.DataFrame(entries).to_csv(OUT/'figure_index.csv',index=False)
cards=[]
groups={'00_overview':'总览图','01_main':'五张主图：按论证顺序','02_mechanism_checks':'机制检查与短讲替代','03_backup':'备份图：问到再展开'}
for group,label in groups.items():
    cards.append(f'<h2>{label}</h2><div class="grid">')
    for e in [e for e in entries if e['group']==group]:
        pdf=Path(e['image']).with_suffix('.pdf').as_posix()
        cards.append(f'<article><span class="tag">{e["priority"]}</span><h3>{e["title"]}</h3><a href="{e["image"]}"><img src="{e["image"]}" loading="lazy"></a><p>{e["claim"]}</p><p class="limit">边界：{e["limit"]}</p><a href="{pdf}">PDF</a> · <a href="{e["image"]}">大图</a></article>')
    cards.append('</div>')
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PMM—平流图件整理与最后一步</title><style>body{font-family:system-ui,sans-serif;max-width:1320px;margin:32px auto;padding:0 24px;background:#f5f7f9;color:#213143;line-height:1.8}h1{font-size:30px}h2{margin-top:38px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:22px}article{background:white;padding:20px;border:1px solid #e1e6eb;border-radius:10px}article h3{margin-top:8px}img{width:100%;background:white}.tag{font-size:12px;background:#e3edf3;padding:4px 9px;border-radius:4px;color:#2b6f97}.limit{font-size:14px;color:#596a7b}.lead{background:#e7eff5;padding:22px;border-left:4px solid #2b6f97}a{color:#236c9a}details{background:white;padding:20px;margin:24px 0}pre{white-space:pre-wrap;font-family:inherit;font-size:15px} @media(max-width:600px){.grid{display:block}article{margin:20px 0}}</style>
<h1>PMM—平流：图件已归类，最后一步已收紧</h1><p>2026-10-15 · 预报与平流重建已统一恢复D20；WWV26相关模型移入历史备份。</p>
<div class="lead"><b>先看三张：</b>M1（D20预报）、M3（平流稳健性）、M4（D20过程重建）。M2补充逐月演变，M5检验结论敏感性。<br><b>当前结论：</b>同状态检验已完成，但预报技巧和平流重建增益不呈一致方向，尚不支持单一平流通道解释。</div>
<p><a href="选图与最后一步.txt">完整选图说明与最后一步方案</a> · <a href="figure_index.csv">图件清单</a></p>
<h2>最后一步要回答的唯一核心问题</h2><p><b>在同一训练与验证口径下，PMM能否同时解释海温预报修正和异常纬向平流的事件差异？</b></p><p>D20下预报改善1997/2015、恶化2023的方向保持；条件平流重建却未呈对应改善。最后检验应把已冻结的完整/PMM通道切断自由状态送入同一个过程响应关系，区分状态预测误差与过程表示误差；若仍不一致，就保留单一平流通道解释不足的结论。</p>
<details><summary>展开：两套模型的区别、最后一步的检验顺序和完成标准</summary><pre>'''+html.escape(decision)+'</pre></details>'+''.join(cards)+'</html>'
(OUT/'index.html').write_text(page)
manifest=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name!='manifest.json':manifest.append({'path':str(p.relative_to(OUT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for e in entries:
    assert (OUT/e['image']).exists()
    assert (OUT/Path(e['image']).with_suffix('.pdf')).exists()
(OUT/'manifest.json').write_text(json.dumps({'figures':len(entries),'main_figures':5,'current_ocean_state':'D20','matched_conditional_process_reconstruction_complete':True,'free_forecast_process_pathway_test_run':False,'source_data':[str(F/'RO_PMM_three_event_metrics.csv'),str(F/'RO_PMM_three_event_trajectories.csv')],'files':manifest},ensure_ascii=False,indent=2))
print(OUT/'index.html')
print(f'{len(entries)} figures organized; all image/PDF links checked.')
