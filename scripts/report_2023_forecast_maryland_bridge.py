"""Build the quantitative Chinese reading guide and a PDF figure collection."""
from pathlib import Path
import json
import hashlib
import pandas as pd
from pypdf import PdfReader, PdfWriter
from analyze_2023_forecast_maryland_bridge import OUT, ROOT, MODELS


def main():
    scores=pd.read_csv(OUT/'seasonal_skill_common_pairs.csv')
    monthly=pd.read_csv(OUT/'monthly_event_scores.csv')
    past=pd.read_csv(OUT/'past_only_sensitivity_scores.csv')
    cases=pd.read_csv(OUT/'Maryland_event_bridge.csv').set_index('event_year')
    starts=pd.read_csv(OUT/'scores_and_increment_by_start.csv')
    pmm=pd.read_csv(OUT/'official_PMM.csv',index_col=0,parse_dates=True).SST
    coupling=pd.read_csv(OUT/'Maryland_atmospheric_coupling.csv')
    summary=[]
    for year in [2015,2023]:
        s=scores[scores.year.eq(year)].set_index('model')
        c=cases.loc[year]
        summary.append(dict(year=year,RO_seasonal_RMSE=s.loc['RO','RMSE'],RO_PMM_seasonal_RMSE=s.loc['RO_SST','RMSE'],
             PMM_mean_Feb_Jun=pmm.loc[f'{year}-02':f'{year}-06'].mean(),
             PMM_model_increment_common_pairs=starts[starts.year.eq(year)].PMM_increment.mean(),
             MJJ_tau_pattern_residual_z=coupling[coupling.year.eq(year)&coupling.month.between(5,7)].tau_pattern_residual_z.mean(),
             early_central_OHC_GJ_m2=c.early_central_ohc_gj_m2,May_June_u850_m_s=c.u850_cwp_mj_ms,
             arrival_140W_ZJ=c.arrival_140w_heat_in_zj,decay_north_output_ZJ=c.decay_northward_output_zj,
             decay_surface_loss_ZJ=c.decay_surface_loss_zj,decay_west_return_ZJ=c.decay_westward_return_zj,
             decay_storage_loss_ZJ=c.decay_storage_loss_zj))
    pd.DataFrame(summary).to_csv(OUT/'forecast_physics_summary_2015_2023.csv',index=False)
    lines=['2023 年预报补充与马里兰研究的连接', '生成日期：2026-10-14', '',
      '核心结果',
      '在原稿固定 2002—2024 拟合下，PMM 对 SST 预报的帮助取决于事件：2015 改善，2023 加重低估。',
      '2015、2023 的 2—6 月五个起报分别全部具有上述方向。仅用事件发生前资料重新拟合的敏感性分析也保留了这个方向。',
      '这支持将预报部分放在马里兰第三个科学问题之后，作为“耦合背景信息能否转化为预报增益”的检验。它不证明 PMM 导致了某种暖量命运。', '',
      '一、完成的分析与读图顺序',
      '1. Maryland_forecast_heat_fate_bridge_2015_2023：核心综合图，左 2015、右 2023。',
      '   第一行：相同 4 月的 RO、RO＋PMM、四个 IRI 动力模式范围及观测；取 4 月作为春季示例，未按技巧筛选。',
      '   第二行：相同季节中心提前期 1—5 的误差；正值为高估、负值为低估。',
      '   第三行：发展年官方 PMM-SST 和 SST 幅度／型态调整后的 ERA5 风应力残差；灰底为 MJJ。',
      '   第四行：前三个海区的 0—300 m OHC′ 与通过 140°W 的累计异常焓输入。',
      '   第五行：次年 Jan—May 东箱暖量损失分配，保留东西南北、海表、残差和总储存损失。',
      '2. forecast_skill_2015_2023_2026_overview：三事件的同事件共同样本 RMSE 概览。',
      '3. figure_2023_RO_vs_standard_PMM：沿用用户参考图的两相图＋时间曲线＋技巧柱。',
      '4. IRI_only_four_models_2023_obs_reference：四个 IRI 模式与观测的四联图。',
      '5. IRI_only_*_2023、IRI_*_2023_RO_PMM：每个模式单图及其与 RO／RO＋PMM 的三方法图。',
      '上述图均有 PNG、PDF、SVG；全部图汇总在 Maryland_bridge_and_2023_all_figures.pdf。', '',
      '二、统一季节验证结果',
      '观测／RO：ERSSTv5，1991—2020 气候态，先恢复原稿移除的趋势，再计算三个月平均。',
      'IRI：采用公开发布的提供方距平，未利用事件观测拟合偏差，也未强行统一未知的提供方基准。',
      '共同验证：2—6 月五个起报，季节中心提前 1—5 个月，同一事件所有六种方法使用完全相同的掩码。',
      '2015、2023 各 25 对；2026 仅 19 个已完整观测季节对。重叠起报和重叠季节不是独立样本。', '',
      scores.to_string(index=False,float_format=lambda x:f'{x:.3f}'), '',
      '其中 2023 RO RMSE 为 0.348°C，RO＋PMM 为 0.454°C，增加 30.2%；相关系数 0.940→0.910。',
      '2015 同口径为 0.768→0.620°C，降低 19.2%。2026 为 0.965→0.832°C，降低 13.8%，但验证样本和 PMM 来源不同。',
      'IRI 在这些事件共同样本上的误差提供参照，不能据此宣称某个方法在一般业务预报中优于其他方法。', '',
      '三、原稿月尺度结果与拟合期敏感性',
      '原稿四联图使用去趋势坐标、月提前期 1—9、45 对，所以与上面的季节表数值不同。',
      monthly.to_string(index=False,float_format=lambda x:f'{x:.3f}'), '',
      '2023 SST 月尺度 RMSE 为 0.574→0.756°C；海洋平均 D20 RMSE 为 2.449→2.426 m，仅小幅变化。',
      '因此本次“2023 变差”指 SST 预报，不应概括为所有状态量均变差。',
      'RO_SST_cut 在已拟合增广模型内部将 PMM→T/h 系数置零，其余系数不变；2023 SST 月 RMSE 为 0.469°C。',
      '这个消融说明结果对模型中的 PMM 反馈通道敏感；它不是对真实气候系统的因果干预。', '',
      '独立敏感性：仅用 2014 年底前／2022 年底前资料拟合，分别从 2002 和 1982 年开始。',
      '气候态、趋势和 PMM 均值均只用该训练期估计；1991—2020 仅用于统一显示和评分坐标。主结果仍沿用已授权的原稿协议。',
      past[past['sample'].eq('season_center_leads_1_5')].to_string(index=False,float_format=lambda x:f'{x:.3f}'), '',
      '两种训练窗均保留 2015 改善、2023 变差的方向。它们仍使用当前版本历史资料和完整月状态，不能视为当年实时业务试验。', '',
      '四、与马里兰的物理连接',
      pd.DataFrame(summary).to_string(index=False,float_format=lambda x:f'{x:.3f}'), '',
      '2015 和 2023 的发展期通过 140°W 的异常焓输入分别为 8.49 和 9.90 ZJ，属于接近量级；但初始空间配置并不相同。',
      '既有事件表中的 Jan—Mar 中部 OHC′ 面密度分别为 1.021 和 0.189 GJ/m²，May—June 中西太平洋 u850 为 3.37 和 0.29 m/s。',
      '次年北向异常焓输出分别为 2.99 和 2.17 ZJ，海表损失为 1.51 和 0.47 ZJ；向西返回为 8.65 和 9.45 ZJ。',
      '因此 2023 不能描述成“暖量没有到达东部”或“所有出口关闭”；其空间配置和释放分配与 2015 不同，西向返回仍很重要。',
      'PMM 初态在两年分别为正、负，增广模型相应向上、向下修正 SST 轨迹。2015 的上调减轻了低估，2023 的下调加重了低估。',
      'PMM 和发展期风响应的对应关系可以作为机制线索；图中的 ERA5 风应力残差、SODA3 OHC 和收支均为独立诊断，并未作为未来信息喂给预报模型。',
      '“RO＋PMM − RO”包括扩展状态空间后重新估计 T/h 子矩阵带来的变化，不能把整个增量解释成纯 PMM 因果效应。', '',
      '既有 13 事件结果只为后半段物理解释提供支持：控制暖量到达后，局地 5°N 风应力与北向输出偏相关 r=0.742、q=0.014；',
      '同期东部 SST 与海表损失偏相关 r=0.647、q=0.016。早期中部 OHC→May—June u850 的 bootstrap 区间仍跨零。',
      '发展期风场、次年局地风场不是同一个指标；后者与释放同期，不能当成已知的提前预测因子。',
      '既有局地 5°N 应力无法解释最大的西向回流支路（偏相关 −0.308，p=0.306），SSH／压强梯度和盆地调整仍需单独研究。', '',
      '五、可直接用于论文或汇报的衔接段',
      '“2015 与 2023 年对照显示，加入经向模态信息并不必然改善赤道 SST 预报。相同建模框架下，PMM 信息改善了 2015 年的低估，却加重了 2023 年的低估，且该方向在事件前训练的敏感性试验中保持。与此同时，热收支诊断表明，两次事件具有接近量级的东部异常焓输入，却有不同的早期热含量配置、大气响应和后续暖量分配。这提示，评价背景模态的预报价值需要结合海洋空间结构及耦合过程，不能仅凭单一 SST 指数增益推断暖量命运。IRI 动力预报提供了同期 SST 演变的独立业务参照，但其机制解释仍需对应的风场与海洋预报场。”', '',
      '保留既有三个科学问题及其顺序：',
      '1. 暖量是否、以及通过什么路径到达东太平洋？',
      '2. 到达后的暖量在北向输出、南向输出、海表散热和海洋储存之间如何分配？',
      '3. 为什么相似的 FEP 先暖和东部暖量输入，会通过不同的海气耦合产生完全不同的暖量命运？',
      '本文增加的预报图置于第三问之后；2026 作为发展期的拟合期外案例，完整的 2026—2027 暖量命运暂不下结论。', '',
      '六、图注中的定义和核验',
      'RO h 为 GODAS 赤道太平洋面积平均 D20（m），不是体积 WWV，也不是 SODA3 0—300 m 热含量。',
      '热收支：10°S—5°N，0—300 m；西箱 160°E—180°、中箱 180°—140°W、东箱 140°W—80°W。',
      'OHC′、异常焓输送采用原项目 1980—2022 同月趋势基准；输送有质量平衡修正及共同的预期边界温度参照。',
      '沿用已有月中心梯形积分：到达为 Jan 15—Jun 15；衰减为次年 Jan 15—May 15，并非完整 1 月 1 日至 5 月 31 日积分。',
      '收支柱中正值表示东箱异常损失，负值表示异常输入；残差包含未解析交换、混合、同化及离散误差，不能命名为已识别通道。',
      '第三行 PMM 按 2002—2024 均值、标准差标准化；风应力残差来自 1982—2014 的逐月 Niño3.4＋Niño3−Niño4 预期响应。',
      '两者参照期不同，不可比较绝对标准化幅度，也不构成独立因果检验。MJJ 阴影只是发展期参考。',
      'IRI 为三个月季节平均，横坐标为季节中心；2 月发布的首个预报 FMA 位于 3 月。',
      'IRI 空心圆为发布月之前结束的最近完整观测季节：例如 2 月发布对应 NDJ、中心在上年 12 月；它不是不可取得的模式真实初值。',
      '虚线连接仅作视觉引导，不参与评分；保持所有原始 IRI 预报值，无平移、无强制贴合观测。',
      '四模式为既定的 NCEP CFSv2、NASA GMAO、CMC CANSIP、JMA；2023 全部覆盖 2—6 月，未根据技巧改选模式。',
      'IRI 数据从官方 SVG 轴坐标反演，逐条核对图例、绘图顺序和标记顶点；并非原始集合成员数据或截图目测。',
      '档案为 2026-10-14 获取的现有公开历史页面，不能保证与历史发布当天字节级一致；不同年份的机构序列也不代表相同模式版本。',
      '数值 QA：复现已交付 2015 轨迹；保留 2015/2026 已交付季节分数；所有起报状态一致；RK4 步长检查；热收支闭合；积分与已有事件表一致。', '',
      '七、来源与复现',
      'IRI 2023 年 6 月官方说明：https://iri.columbia.edu/our-expertise/climate/forecasts/enso/2023-June-quick-look/',
      'IRI 官方各月 SVG：https://ensoforecast.iri.columbia.edu/figure4_plot/2023/<month>，month=2,...,6（CC BY 4.0）。',
      '下载清单：data/raw/iri_plumes_2023_20261014/source_manifest.json；包含 URL、获取时间和 SHA256。',
      '核心数值与来源：numerical_QA.json、vector_extraction_QA_2023.json、IRI_2023_observed_reference_QA.json。',
      '复现顺序：analyze_2023_forecast_maryland_bridge.py → check_maryland_bridge_past_only.py → plot_2023_forecast_maryland_bridge.py → report_2023_forecast_maryland_bridge.py。',
      '以上脚本均在项目 scripts/ 下，读取已有项目数据；不覆盖此前的 2015／2026 图。', '',
      '解释边界',
      '本轮完成了同协议个例检验和物理诊断对齐。尚未检验 OHC 空间结构能否在跨事件预测中解释 PMM 增益差异，不能宣称已找到唯一原因。',
      '若要进一步识别 IRI 模式为何不同，需要相应模式的风应力、SSH、热含量和输送预报场，Niño3.4 羽流本身无法提供这些信息。']
    (OUT/'results_and_integration_cn.txt').write_text('\n'.join(lines)+'\n')
    stems=json.loads((OUT/'figure_index.json').read_text())
    order=['Maryland_forecast_heat_fate_bridge_2015_2023','forecast_skill_2015_2023_2026_overview',
           'figure_2023_RO_vs_standard_PMM','IRI_only_four_models_2023_obs_reference']
    order += [s for s in stems if s not in order]
    writer=PdfWriter()
    for title in order:
        source=OUT/f'{title}.pdf'
        reader=PdfReader(source)
        assert len(reader.pages)==1
        page=len(writer.pages)
        writer.append(reader)
        writer.add_outline_item(title,page)
    writer.add_metadata({'/Title':'ENSO forecasts and Maryland heat-fate analysis: 2015, 2023, 2026'})
    writer.write(OUT/'Maryland_bridge_and_2023_all_figures.pdf')
    assert len(PdfReader(OUT/'Maryland_bridge_and_2023_all_figures.pdf').pages)==12
    print('Report and 12-page figure collection completed:',OUT)


if __name__=='__main__':main()
