#!/usr/bin/env python3
"""Render the corrected full-period D20 comparison from saved prediction tables."""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

import report_enso_strength_pmm_skill as figures
import plot_enso_strength_mean_trajectories as plumes

CN = figures.CN
CAPTION = (
    "Five starts per model: February–June; 9-month free forecasts. ERSST anomalies relative to 1991–2020.\n"
    "One 1982–2024 fit per model, including all events; RO = Niño3.4 + D20. Events have equal weight; sustained events average two development years."
)
METHOD = (
    "先用1982年1月至2024年12月的516个连续月份拟合，包含全部暖、冷和中性阶段；"
    "RO=[ERSST Niño3.4, GODAS平均D20]，RO＋PMM增加官方PMM-SST。"
    "D20为5°S—5°N、120°E—80°W的面积加权20°C等温线深度，单位m。"
    "整个分析只有两套正式模型，各自拟合一次，然后所有事件及起报月份共用固定系数。"
    "沿用原复现的1991—2020同月气候态、线性去趋势、年/半年谐波、二阶扰动估计及RK4积分；"
    "新分析的趋势、尺度及PMM均值均在1982—2024期内估计，不保留旧复现延至2025年4月的趋势端点。"
    "不再排除事件，也不按强度另拟合模型。"
    "75个起报来自15个发展年的2—6月，分别由当月观测初态自由积分9个月，起报后不输入未来观测。"
    "恢复趋势后，在1991—2020同月海温距平坐标中展示及评分。"
    "主结果为提前1—9个月共675个配对预测；先计算各事件MSE和偏差，再对事件等权，MSE平均后开方。"
    "提升率=100×(1−RMSE_RO＋PMM/RMSE_RO)。1986—88、2014—16各含两个发展年，但统计时各占一个事件。"
)
NOTE = (
    "强、中、弱各自平均，保留2、3、4、5、6月五个起报节点。黑色粗线为观测，蓝色虚线为RO，"
    "橙色实线为RO＋PMM；空心点标示共同初态。横轴1为发展年1月，13为次年1月。"
    "持续事件先在事件内部平均两个发展年，再进行组内事件等权平均。未作时间平滑；"
    "平均曲线展示演变，技巧表则保留逐事件误差后再汇总，二者不能混算。"
)


def report(out: Path):
    figures.style()
    groups = pd.read_csv(out / "group_scores.csv")
    events = pd.read_csv(out / "event_scores.csv")
    catalog = pd.read_csv(out / "event_catalog.csv", dtype={"development_years": str})
    qa = json.loads((out / "numerical_QA.json").read_text())
    figures.lead_figure(groups, out,
        subtitle="Full-period fit: 1982–2024 (all events included)  •  RO = Niño3.4 + D20  •  + PMM-SST")
    figures.event_figure(events, catalog, out,
        model_note="RO uses D20. One full-period 1982–2024 fit per model; all target events are included in fitting.")
    figures.heatmap_figure(groups, out,
        subtitle="Full-period D20 sLIM  •  RMSE reduction relative to RO (%)  •  Equal weight per event")
    forecasts, observations = plumes.make_composites(out)
    plumes.plot(forecasts, observations, out, caption=CAPTION)
    (out / "mean_trajectory_notes_cn.txt").write_text(NOTE+"\n"+METHOD+"\n", encoding="utf-8")
    monthly = groups.query("target_type == 'monthly' and view == 'overall'")
    seasonal = groups.query("target_type == 'seasonal' and view == 'overall'")
    primary = events.query("target_type == 'monthly' and view == 'overall'").merge(
        catalog[["event", "peak_oni", "development_years"]], on="event", validate="one_to_one")
    headlines = []
    for r in monthly.itertuples(index=False):
        headlines.append(f"{CN[r.group]}组：RMSE {r.RMSE_RO:.3f} → {r.RMSE_RO_PMM:.3f}°C，"
            f"提升率 {r.improvement_percent:+.2f}%；{r.improved_events}/{r.n_events} 次事件改善；"
            f"95%事件重采样区间 [{r.ci_low:+.2f}%, {r.ci_high:+.2f}%]。")
    worse = primary[primary.improvement_percent.lt(0)].sort_values("improvement_percent")
    worse_text = "、".join(f"{r.event}（{r.improvement_percent:+.2f}%）" for r in worse.itertuples()) or "无"
    event_table = pd.DataFrame([dict(
        事件=r.event, 等级=CN[r.strength], ONI峰值=f"{r.peak_oni:.1f}", 起报年=r.development_years,
        RO_RMSE=f"{r.RMSE_RO:.3f}", 加PMM_RMSE=f"{r.RMSE_RO_PMM:.3f}",
        提升率=f"{r.improvement_percent:+.2f}%", RO偏差=f"{r.bias_RO:+.3f}",
        加PMM偏差=f"{r.bias_RO_PMM:+.3f}") for r in primary.itertuples()])
    limitations = [
        "这是全时段拟合后的样本内起报比较，目标事件参与参数拟合；不称为参数样本外检验或当时实时预报。",
        "PMM作为起报时的第三个状态，随后与海温和D20共同演变。比较的是独立拟合的两状态和三状态系统；没有在某条既有RO轨迹中途切换系数。",
        "事件强度只用于事后分组。固定本地ONI版本按发布一位小数识别，包含2019—20弱事件；超强并入强组。",
        "5000次配对bootstrap以整个事件为单位，固定两套模型不重拟合。中、弱组各仅3次事件，区间描述本组离散程度；不代表独立样本外泛化能力。",
        "图与评分均保留PMM带来的正负变化。三个月平均为中心提前1—5个月的补充，首个平均窗含起报月。",
    ]
    rep = qa["original_replication"]
    qa_text = (
        f"已复核旧2002—2024本地复现：预处理最大差{rep['saved_2002_2024_preprocessing_max_error']:.2e}，"
        f"系数最大差{rep['saved_2002_2024_coefficient_max_error']:.2e}。"
        f"正式分析只有{qa['fits']}套模型，每套{qa['training_months_per_model']}个连续月份；"
        f"与分段核心在全样本掩膜下的系数差{qa['max_continuous_segmented_coefficient_error']:.2e}。"
        f"初态误差{qa['max_initial_error']:.2e}，固定模型和初态后修改未来观测的预报差"
        f"{qa['max_fixed_model_future_observation_error']:.2e}；"
        f"RK4步长加密最大差{qa['max_rk4_error']:.2e}，"
        f"保存表独立重算评分差{qa['saved_score_max_error']:.2e}。"
        f"年度传播谱半径{qa['annual_radius_min']:.4f}—{qa['annual_radius_max']:.4f}，"
        f"不稳定模型{qa['unstable_fits']}套。"
    )
    text = "全时段D20 sLIM：强、中、弱厄尔尼诺的PMM比较\n\n"+"\n".join(headlines)
    text += "\n\n变差事件："+worse_text+"。\n\n"+METHOD
    text += "\n\n月平均主结果（°C）\n"+figures.summary_table(monthly).to_string(index=False)
    text += "\n\n逐事件\n"+event_table.to_string(index=False)
    text += "\n\n三个月平均补充\n"+figures.summary_table(seasonal).to_string(index=False)
    text += "\n\n平均曲线\n"+NOTE+"\n\n解释范围\n"+"\n".join(limitations)+"\n\n验证\n"+qa_text+"\n"
    (out / "results_cn.txt").write_text(text, encoding="utf-8")
    cards = "".join(f"<p>{html.escape(line)}</p>" for line in headlines)
    panels = "".join(f'<section><h2>{title}</h2><img src="{stem}.png" alt="{title}">'
        f'<p><a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a> · '
        f'<a href="Fig{i+1}_source.csv">图源数据</a></p></section>'
        for i, (stem, title) in enumerate(figures.FIGURES))
    table = lambda t: '<div class="scroll">'+t.to_html(index=False, border=0)+"</div>"
    files = [
        ("results_cn.txt", "中文结果"), ("event_catalog.csv", "事件分类"),
        ("monthly_forecasts.csv", "全部起报预测"), ("event_scores.csv", "逐事件全部评分"),
        ("group_scores.csv", "分组全部评分"), ("group_summary.csv", "分组汇总"),
        ("seasonal_forecasts.csv", "三个月平均预测"),
        ("models_and_preprocessing.json", "两套模型和预处理参数"),
        ("fitted_period_states.csv", "连续516个月拟合状态"),
        ("forecast_model_states.csv", "逐起报全部状态演变"),
        ("training_period.csv", "统一拟合时段"), ("protocol_before_run.txt", "计算口径"),
        ("numerical_QA.json", "数值核验"), ("mean_trajectory_QA.json", "合成核验"),
        ("source_manifest.json", "来源校验值"), ("reproduce.txt", "复现命令")]
    downloads = " · ".join(f'<a href="{f}">{label}</a>' for f, label in files)
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>全时段D20 sLIM：强中弱平均轨迹与PMM增益</title>
<style>body{{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;background:#f4f5f6;color:#25323a;line-height:1.8;margin:0}}
main{{max-width:1280px;margin:36px auto;padding:0 24px}}section{{background:white;padding:26px;margin:22px 0;border-radius:12px}}
h1{{font-size:30px}}h2{{font-size:22px}}img{{width:100%;height:auto}}a{{color:#256c94}}.sub{{color:#526675}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:8px 10px;border-bottom:1px solid #e2e6e9;text-align:right}}
td:first-child,th:first-child{{text-align:left}}.scroll{{overflow:auto}}</style><main>
<p class="sub">1982—2024连续全时段 · D20 · 13次事件 · 两套固定模型 · 样本内起报比较</p>
<h1>先拟合完整时段，再比较各起报节点加入PMM的变化</h1>
<section><h2>强、中、弱：Niño3.4平均轨迹</h2><img src="{plumes.STEM}.png" alt="强中弱平均多起报轨迹">
<p>{NOTE}</p><p><a href="{plumes.STEM}.pdf">PDF</a> · <a href="{plumes.STEM}.svg">SVG</a> ·
<a href="mean_trajectory_group_forecasts.csv">平均预测数据</a> · <a href="mean_trajectory_group_observations.csv">平均观测数据</a></p></section>
<section><h2>月平均主结果</h2>{cards}<p>变差事件：{html.escape(worse_text)}。</p>
<p>提前1—9个月；事件等权；RMSE和偏差单位°C；正提升率表示改善。</p>{table(figures.summary_table(monthly))}</section>
{panels}<section><h2>全部事件逐一核对</h2>{table(event_table)}</section>
<section><h2>三个月平均补充</h2><p>中心提前1—5个月；首窗含共同起报月。</p>{table(figures.summary_table(seasonal))}</section>
<section><h2>拟合和起报方式</h2><p>{METHOD}</p>{''.join('<p>'+html.escape(s)+'</p>' for s in limitations)}
<p>此前WWV26逐事件留出结果保存在原目录，已不作为本轮主结果。</p></section>
<section><h2>数值验证</h2><p>{qa_text}</p></section><section><h2>下载结果</h2><p>{downloads}</p></section>
</main></html>'''
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "reproduce.txt").write_text(
        "From the Maryland project root, using Python with numpy/pandas/matplotlib:\n"
        "python scripts/analyze_enso_strength_fullperiod_d20.py\n"
        "python scripts/analyze_enso_strength_fullperiod_d20.py --validate-only\n"
        "python scripts/analyze_enso_strength_fullperiod_d20.py --report-only\n\n"
        "All four figures and the report are included in the main entry point.\n"
        "Old leave-one-event-out/WWV26 outputs are never overwritten.\n"
        "group_scores.csv and event_scores.csv include overall, lead, init and init_lead views.\n"
        "The original 2002--2024 implementation is only a numerical regression audit;\n"
        "the two models used in all new predictions are fit over 1982--2024.\n",
        encoding="utf-8")
    print(f"Report: {out / 'index.html'}", flush=True)


if __name__ == "__main__":
    from analyze_enso_strength_fullperiod_d20 import DEFAULT_OUT
    report(DEFAULT_OUT)
