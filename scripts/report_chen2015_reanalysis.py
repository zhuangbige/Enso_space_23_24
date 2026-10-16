from pathlib import Path
import json,numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/research_2026/chen2015_reanalysis_20261014';RAW=ROOT/'data/raw/chen2015_reanalysis_20261014'

def main():
 raw=pd.read_csv(OUT/'monthly_absolute.csv',parse_dates=['time']);a=pd.read_csv(OUT/'monthly_anomalies.csv',parse_dates=['time']);e=pd.read_csv(OUT/'event_volume_budget.csv');h=pd.read_csv(OUT/'event_two_term_heat.csv');t=pd.read_csv(OUT/'two_term_heat_monthly.csv',parse_dates=['time']);qa=json.loads((OUT/'numerical_QA.json').read_text())
 rows=[]
 for year in [1997,2015,2023]:
  r={'event_year':year}
  for phase in ['arrival','decay']:
   q=e.loc[e.event_year.eq(year)&e.phase.eq(phase)&e.box.eq('east')&e.baseline_method.eq('monthly_mean')].iloc[0]
   for c in ['storage_change_1e14m3','west_in_1e14m3','east_in_1e14m3','north_in_1e14m3','south_in_1e14m3','unresolved_1e14m3','surface_loss_zj']:r[phase+'_'+c]=q[c]
  q=e.loc[e.event_year.eq(year)&e.phase.eq('decay')&e.box.eq('chen_basin')&e.baseline_method.eq('monthly_mean')].iloc[0];r['basin_decay_storage_change_1e14m3']=q.storage_change_1e14m3
  q=h.loc[h.event_year.eq(year)&h.phase.eq('decay')&h.gate.eq('east_north')&h.geometry.eq('instantaneous_sigma26')].iloc[0]
  for c in ['vbar_Tprime_zj','vprime_Tbar_zj','linear_sum_zj']:r['decay_'+c]=q[c]
  q=a.loc[a.time.dt.year.eq(year)&a.time.dt.month.between(1,3)];r['early_central_wwv_anom_1e14m3']=q.central_wwv_m3.mean()/1e14
  rows.append(r)
 summary=pd.DataFrame(rows);summary.to_csv(OUT/'main_event_comparison.csv',index=False)
 # No physical closure is inferred from the algebraic residual; verify the accounting only.
 err=e.storage_change_1e14m3-e.horizontal_in_1e14m3-e.unresolved_1e14m3
 audit={'algebraic_accounting_error_1e14m3':float(abs(err).max()),'primary_north_gate_min_coverage':float(t.loc[t.gate.eq('east_north'),'included_section_area_fraction'].min()),'all_supplementary_gate_min_coverage':float(t.included_section_area_fraction.min()),'n_event_rows':len(e),'n_months':len(raw),'years':len(qa['source_files'])//2,
 'unresolved_density_profiles':sum(qa[str(y)]['unresolved'] for y in range(1980,2025)),
 'multiple_crossing_profiles':sum(qa[str(y)]['multiple_crossings'] for y in range(1980,2025)),
 'wet_profiles':sum(qa[str(y)]['wet_profiles'] for y in range(1980,2025))}
 ref=pd.read_csv(OUT/'independent_north_gate_reference.csv')
 errors=[]
 for _,r in ref.iterrows():
  col=r['term'].replace('_pw','_zj')
  value=h.loc[h.event_year.eq(r['year']-1)&h.phase.eq('decay')&h.gate.eq('east_north')&h.geometry.eq(r['geometry']),col].iloc[0]
  errors.append(abs(value-r['Jan15_May15_zj']))
 audit['independent_narrow_section_max_error_zj']=float(max(errors))
 if max(errors)>1e-4:raise ValueError('Full-field and independent narrow-section calculations disagree')
 (OUT/'summary_QA.json').write_text(json.dumps(audit,indent=2))
 # Timing is taken from the official annual product's record convention, not a bad auxiliary coordinate.
 cal=[]
 for year in range(1980,2025):
  m=json.loads((RAW/f'metadata_{year}.json').read_text());times=np.array(m['coords']['time']);cal.append({'year':year,'format':m['kind'],'n_records':len(times),'unique_source_time_values':len(np.unique(times)),'source_time_min':min(times),'source_time_max':max(times),'analysis_dates':'12 monthly records in filename year, Jan-Dec, assigned day 15'})
 pd.DataFrame(cal).to_csv(OUT/'source_calendar_QA.csv',index=False)
 # Reference-zero sensitivity of the current term equals -rho*cp*delta_ref*int(v_prime)dS.
 # Existing two-term output uses one explicit common reference (0C); no additional term is created.
 notes=['陈2015方法统一重算：结果与解释','',f'完成范围：{len(raw)}个月（1980—2024）、13个事件；重点图为2015/16、2023/24，1997/98提供参照。',
 '原暖量两行已重新计算并替换为WWV26与体积收支；原RO/PMM/IRI预报与大气诊断保留。原固定300m历史图没有覆盖。',
 '', '主设定：1980—2022同月均值，瞬时σθ=26界面；发展期Jan15—Jun15，衰减期次年Jan15—May15。所有体积数值单位为10^14 m^3，热输送积分另用ZJ。','',
 '一、三事件统一口径结果',
 '发展期：体积异常输入、储备配置（10^14 m^3）',summary[['event_year','early_central_wwv_anom_1e14m3','arrival_west_in_1e14m3','arrival_storage_change_1e14m3']].to_string(index=False),
 '衰减期：东箱各边界以输入为正、储备变化（10^14 m^3）',summary[['event_year','decay_west_in_1e14m3','decay_north_in_1e14m3','decay_south_in_1e14m3','decay_storage_change_1e14m3','decay_unresolved_1e14m3']].to_string(index=False),
 '衰减期：5N两项热输送（ZJ）与全盆地储量变化（10^14 m^3）',summary[['event_year','decay_vbar_Tprime_zj','decay_vprime_Tbar_zj','decay_linear_sum_zj','basin_decay_storage_change_1e14m3']].to_string(index=False), '',
 '二、统一口径后的主要变化',
 '2015/2023发展期跨140W体积异常输入为0.900/1.989×10^14m³；2023进入东箱的异常体积更多。它不能与旧8.49/9.90 ZJ热输入直接换算。',
 '两年早期中箱WWV26距平均约0.7×10^14m³；旧固定层OHC中的强弱差不能直接移植成同等比例的暖水体积差。',
 '东箱衰减期WWV26距平损失为1.925/1.674×10^14m³；北向体积异常输出为0.203/0.265×10^14m³，2024比2016约大30.5%。去趋势敏感性也保持2024北向输出较大的次序。',
 '两年已识别水平输出中仍以向西返回最大（2.701/2.544×10^14m³）。正的未解析体积输入抵消部分水平净输出，不能把全部储量损失按已识别边界给出闭合百分比。',
 '2023盆地WWV26距平在发展年即持续下降，2015则先增加、在年末及次年下降。因此只比较次年Jan-May损失会漏掉前期不同的充放电时序。',
 '这些结论都针对所标记的距平及窗口；次年盆地距平变化小，不等于绝对WWV没有季节性下降。',
 '', '三、原三问如何承接',
 '1. 是否到达：看140°W体积输送距平累计及东箱WWV26储备变化。欧拉体积输送不是同一水团的轨迹，也不保证进入暖水体积全部留在东箱。',
 '2. 到达后去向：看东箱西/东/南/北边界体积输入和储量变化；未解析体积项单列。海表热通量另列，不把ZJ混入m^3比例。跨等密度面转化尚未用热盐浮力通量与混合直接分解。',
 '3. 为什么不同：将北界两项热输送及±9°内部STC/西边界流时序，与既有风和预报差异并置。v′θ_bar不是纯风驱归因，图本身不证明PMM因果作用。','',
 '四、基准与积分层敏感性（东箱衰减期）',
 e.loc[e.event_year.isin([2015,2023])&e.box.eq('east')&e.phase.eq('decay'),['event_year','baseline_method','storage_change_1e14m3','west_in_1e14m3','north_in_1e14m3','south_in_1e14m3','unresolved_1e14m3']].to_string(index=False),
 '', '北界两项在实际断面与气候态断面的对照：',h.loc[h.event_year.isin([2015,2023])&h.phase.eq('decay')&h.gate.eq('east_north')].to_string(index=False),
 '', '五、未解析项及有效范围',
 '固定层版本曾施加水平质量平衡修正，本次暖水层体积允许变化，因此不照搬净水平输送强制归零。横向输送与储量变化差额不是自动识别的物理机制。',
 '局地两项分解的气候态要求每格都有43个基期年份；基期不足的沿岸格点不以少量年份冒充完整平均，逐断面保存included_section_area_fraction。主5N东部断面覆盖完整；部分其他沿岸断面的补充热分解仅覆盖约67%—100%的有效面积，不能当作完整断面热通量。事件表另存minimum_section_coverage和complete_section。',
 '两项热输送按用户指定仅保留v_bar*θ′和v′*θ_bar；移动断面上的背景积分仍可能变化，被省略的非线性项未单独验证很小。因此只称两项贡献，不称完整热输送距平。',
 '陈论文原用SODA2.2.4、1960—2010、并进行2—8年年际滤波。本次同源SODA3延伸为未滤波个例月距平，1980—2022为本项目统一基期，不冒称陈论文给出的具体年份或滤波结果。',
 '西部边缘海的深层和沿岸海底受限暖水均明确处理；源0.5°重网格数据不保证严格有限体积守恒。没有宣称定量闭合陈论文的全部物理收支。',
 '年度文件辅助time坐标中有重复值；根据官方年度产品的12个月记录顺序和文件年份赋Jan-Dec月中日期，已与既有2016/2024五个月缓存逐格核对。2021/2022年度文件与旧APDRC缓存存在差异，已额外保存逐月比较及最近邻月份核验；主计算统一采用本轮官方年度文件，不混用旧历史值。这些是来源/读取一致性检查，不是独立观测对2023/2024日期的验证。见source_calendar_QA.csv，不把坏time坐标当作验证依据。',
 '', '六、数值检查',json.dumps(audit,ensure_ascii=False,indent=2),
 '2016/2024新下载温盐流速与旧5°N缓存最大差均为0；随机剖面独立标量插值与向量D26算法一致；共用三箱边界输送逐值相等。',
 '多次密度交点取从表面向下的首个26交点；无未解析下载截断剖面。海底受限剖面用源层界近似实际湿柱底，影响体积另存。',
 '', '额外EOS80密度敏感性见EOS80_volume_sensitivity.json；2016/2024各箱绝对储量最大相对差小于0.5%，该检查不等于距平/技巧的不确定度估计。',
 '详细方法：method_contract_cn.txt。主事件表：main_event_comparison.csv；全部事件：event_volume_budget.csv、event_two_term_heat.csv。']
 (OUT/'results_and_methods_cn.txt').write_text('\n'.join(notes)+'\n')
 print(summary.to_string(index=False));print(audit)
if __name__=='__main__':main()
