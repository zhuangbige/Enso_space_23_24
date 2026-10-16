#!/usr/bin/env python3
"""Three figures and a compact Chinese report from saved paired forecasts."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/maryland_enso_strength_mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

GROUPS = ("strong", "moderate", "weak")
EN = {"strong": "Strong", "moderate": "Moderate", "weak": "Weak", "all": "All events"}
CN = {"strong": "强", "moderate": "中", "weak": "弱", "all": "全部"}
BASE, AUGMENTED = "#737B84", "#256C94"
POSITIVE, NEGATIVE = "#267E77", "#B65D3C"
GROUP_COLORS = {"strong": "#AD593F", "moderate": "#856A9C", "weak": "#397D9C"}
FIGURES = [
    ("Fig1_skill_by_lead", "各强度组的 RMSE 与 PMM 增益随提前期变化"),
    ("Fig2_all_event_improvements", "全部 13 次事件：RO 与 RO＋PMM 的误差和增益"),
    ("Fig3_initialization_lead_skill", "起报月份 × 提前期：强、中、弱三组的 PMM 增益"),
]


def save(fig, out, stem):
    for extension in ("png", "pdf", "svg"):
        fig.savefig(out / f"{stem}.{extension}", dpi=240, facecolor="white")
    plt.close(fig)


def style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
        "axes.titlesize": 12, "axes.labelsize": 10, "axes.spines.top": False,
        "axes.spines.right": False, "axes.linewidth": .8, "lines.linewidth": 2,
        "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none"})


def lead_figure(groups, out, subtitle=None):
    source = groups.query("target_type == 'monthly' and view == 'lead' and group != 'all'")
    source.to_csv(out / "Fig1_source.csv", index=False)
    fig, axes = plt.subplots(2, 3, figsize=(13.4, 8.2), sharex=True, sharey="row")
    fig.subplots_adjust(left=.075, right=.98, top=.83, bottom=.18, wspace=.15, hspace=.2)
    fig.suptitle("Does PMM improve El Niño forecasts?", fontsize=20, fontweight="bold", y=.975)
    fig.text(.5, .927, subtitle or "Leave-one-event-out sLIM  •  RO = Niño3.4 + WWV26  •  RO + PMM adds PMM-SST",
             ha="center", fontsize=11, color="#4D5660")
    lower = min(0, source.ci_low.min())
    upper = max(0, source.ci_high.max())
    pad = max((upper-lower)*.09, 2)
    for col, name in enumerate(GROUPS):
        data = source[source.group.eq(name)].sort_values("lead")
        x = data.lead.to_numpy()
        n = int(data.n_events.iloc[0])
        a, b = axes[:, col]
        a.set_title(f"({chr(97+col)}) {EN[name]}  ·  {n} events", fontweight="bold", pad=14)
        a.plot(x, data.RMSE_RO, "o--", color=BASE, markersize=4, label="RO")
        a.plot(x, data.RMSE_RO_PMM, "o-", color=AUGMENTED, markersize=4, label="RO + PMM")
        a.set_ylim(0, source[["RMSE_RO", "RMSE_RO_PMM"]].to_numpy().max()*1.12)
        a.grid(axis="y", color="#E7E9EB", linewidth=.7)
        b.fill_between(x, data.ci_low.to_numpy(), data.ci_high.to_numpy(), color=AUGMENTED,
                       alpha=.13, linewidth=0, label="95% event-bootstrap interval")
        b.plot(x, data.improvement_percent, "o-", color=AUGMENTED, markersize=4)
        b.axhline(0, color="#50565C", linewidth=.9)
        b.set_ylim(lower-pad, upper+pad)
        b.grid(axis="y", color="#E7E9EB", linewidth=.7)
        b.set(xticks=range(1, 10), xlabel="Lead from initial month (months)")
        b.text(.04, .92, f"({chr(100+col)}) PMM gain", transform=b.transAxes, fontweight="bold", va="top")
    axes[0, 0].set_ylabel("Niño3.4 RMSE (°C)")
    axes[1, 0].set_ylabel("RMSE reduction (%)\nPositive = improvement")
    axes[0, 0].legend(loc="upper left", fontsize=9)
    fig.text(.075, .04, "Equal weight per event; February–June starts; monthly verification, leads 1–9.\n"
             "Shading: 5,000 paired event-bootstrap draws, pointwise 95% intervals. Moderate/weak groups have only 3 events.\n"
             "1982–2024 data; traditional ONI classes. Current-vintage retrospective forecasts; no future observed forcing.",
             fontsize=9, color="#555D66", linespacing=1.5)
    save(fig, out, FIGURES[0][0])


def event_figure(events, catalog, out, model_note=None):
    data = events.query("target_type == 'monthly' and view == 'overall'").copy()
    data["group_order"] = data.strength.map({k: i for i, k in enumerate(GROUPS)})
    data = data.sort_values(["group_order", "event"]).reset_index(drop=True)
    data.to_csv(out / "Fig2_source.csv", index=False)
    fig, (left, right) = plt.subplots(1, 2, figsize=(13.5, 8.2), sharey=True, gridspec_kw={"width_ratios": [1.2, 1]})
    fig.subplots_adjust(left=.22, right=.95, top=.84, bottom=.19, wspace=.23)
    fig.suptitle("PMM gains differ across individual events", fontsize=20, fontweight="bold", y=.97)
    fig.text(.5, .92, "All 13 episodes retained  •  Monthly forecasts at leads 1–9  •  No event-specific tuning",
             ha="center", fontsize=11, color="#4D5660")
    y = np.arange(len(data))
    for i, row in enumerate(data.itertuples(index=False)):
        left.plot([row.RMSE_RO, row.RMSE_RO_PMM], [i, i], color="#CDD1D5", linewidth=2.5, zorder=1)
    left.scatter(data.RMSE_RO, y, s=40, color=BASE, label="RO", zorder=3)
    left.scatter(data.RMSE_RO_PMM, y, s=40, color=AUGMENTED, label="RO + PMM", zorder=3)
    left.set(yticks=y, yticklabels=[r.event.replace("-", "–")+f"   {EN[r.strength]}" for r in data.itertuples()],
             xlabel="Niño3.4 RMSE (°C)", xlim=(0, data[["RMSE_RO", "RMSE_RO_PMM"]].to_numpy().max()*1.15))
    left.invert_yaxis()
    left.legend(loc="upper center", bbox_to_anchor=(.5, 1.09), ncol=2, fontsize=9)
    left.grid(axis="x", color="#E7E9EB", linewidth=.7)
    gains = data.improvement_percent.to_numpy()
    colors = [POSITIVE if v >= 0 else NEGATIVE for v in gains]
    right.barh(y, gains, color=colors, height=.64)
    right.axvline(0, color="#50565C", linewidth=.9)
    extent = max(abs(gains).max(), 5.)
    right.set_xlim(min(gains.min(), 0)-extent*.26, max(gains.max(), 0)+extent*.28)
    for i, value in enumerate(gains):
        right.text(value + (extent*.025 if value >= 0 else -extent*.025), i, f"{value:+.1f}%",
                   ha="left" if value >= 0 else "right", va="center", fontsize=10)
    right.set_xlabel("RMSE reduction (%)\nPositive = improvement; negative = deterioration")
    right.tick_params(axis="y", left=False)
    right.spines["left"].set_visible(False)
    right.grid(axis="x", color="#E7E9EB", linewidth=.7)
    right.set_axisbelow(True)
    for boundary in (6.5, 9.5):
        for ax in (left, right):
            ax.axhline(boundary, color="#CFD3D8", linewidth=.8)
    fig.text(.22, .035, "1986–88 includes starts in 1986 and 1987; 2014–16 includes starts in 2014 and 2015.\n"
             "Each sustained episode counts once in group averages. All other episodes have five starts (45 monthly pairs).\n"
             + (model_note or "RO uses total WWV26; both models use the same ERSST target and leave-one-event-out training mask."),
             fontsize=9, color="#555D66", linespacing=1.5)
    save(fig, out, FIGURES[1][0])


def heatmap_figure(groups, out, subtitle=None):
    data = groups.query("target_type == 'monthly' and view == 'init_lead' and group != 'all'").copy()
    data.to_csv(out / "Fig3_source.csv", index=False)
    limit = max(5, np.ceil(abs(data.improvement_percent).max()/5)*5)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    fig, axes = plt.subplots(1, 3, figsize=(14.4, 6.1), sharex=True, sharey=True)
    fig.subplots_adjust(left=.065, right=.96, top=.79, bottom=.36, wspace=.13)
    fig.suptitle("When does PMM help — and when does it hurt?", fontsize=20, fontweight="bold", y=.96)
    fig.text(.5, .90, subtitle or "RMSE reduction relative to RO (%)  •  One shared color scale  •  Equal weight per event",
             ha="center", fontsize=11, color="#4D5660")
    for i, (ax, group) in enumerate(zip(axes, GROUPS)):
        selected = data[data.group.eq(group)]
        matrix = selected.pivot(index="init_month", columns="lead", values="improvement_percent").loc[range(2, 7), range(1, 10)]
        im = ax.imshow(matrix.to_numpy(), origin="upper", aspect="auto", cmap="BrBG", norm=norm)
        ax.set_title(f"({chr(97+i)}) {EN[group]}  ·  {int(selected.n_events.iloc[0])} events", pad=14, fontweight="bold")
        ax.set(xticks=range(9), xticklabels=range(1, 10), yticks=range(5),
               yticklabels=["Feb", "Mar", "Apr", "May", "Jun"], xlabel="Lead (months)")
        ax.tick_params(length=0)
        for (row, col), value in np.ndenumerate(matrix.to_numpy()):
            ax.text(col, row, f"{value:+.0f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(value) > limit*.60 else "#25323A")
    axes[0].set_ylabel("Initialization month")
    color_ax = fig.add_axes([.34, .23, .32, .025])
    fig.colorbar(im, cax=color_ax, orientation="horizontal").set_label("← Worse with PMM                 Better with PMM →", labelpad=7)
    fig.text(.065, .055, "Cells show the percent reduction in event-weighted RMSE, not event improvement counts.\n"
             "These are descriptive, overlapping forecast comparisons; moderate/weak groups contain only three episodes.\n"
             "1982–2024, traditional ONI classes; February–June complete-month initial states; no future observed forcing.",
             fontsize=9, color="#555D66", linespacing=1.5)
    save(fig, out, FIGURES[2][0])


def summary_table(frame):
    return pd.DataFrame([dict(
        组别=CN[r.group], 事件数=r.n_events, RO_RMSE=f"{r.RMSE_RO:.3f}",
        加PMM_RMSE=f"{r.RMSE_RO_PMM:.3f}", 提升率=f"{r.improvement_percent:+.1f}%",
        区间=f"[{r.ci_low:+.1f}%, {r.ci_high:+.1f}%]",
        改善事件=f"{r.improved_events}/{r.n_events}",
        RO偏差=f"{r.bias_RO:+.3f}", 加PMM偏差=f"{r.bias_RO_PMM:+.3f}")
        for r in frame.itertuples(index=False)])


def report(out: Path):
    style()
    groups = pd.read_csv(out / "group_scores.csv")
    events = pd.read_csv(out / "event_scores.csv")
    catalog = pd.read_csv(out / "event_catalog.csv")
    qa = json.loads((out / "numerical_QA.json").read_text())
    lead_figure(groups, out)
    event_figure(events, catalog, out)
    heatmap_figure(groups, out)
    monthly = groups.query("target_type == 'monthly' and view == 'overall'")
    seasonal = groups.query("target_type == 'seasonal' and view == 'overall'")
    primary = events.query("target_type == 'monthly' and view == 'overall'").merge(
        catalog[["event", "peak_oni", "development_years"]], on="event", validate="one_to_one")
    all_score = monthly[monthly.group.eq("all")].iloc[0]
    headlines = []
    for r in monthly.itertuples(index=False):
        word = "改善" if r.improvement_percent > 0 else "变差"
        interval = "区间跨零" if r.ci_low <= 0 <= r.ci_high else ("区间完全为正" if r.ci_low > 0 else "区间完全为负")
        headlines.append(f"{CN[r.group]}组：RMSE {r.RMSE_RO:.3f} → {r.RMSE_RO_PMM:.3f}°C，"
            f"{word} {abs(r.improvement_percent):.1f}%；{r.improved_events}/{r.n_events} 次事件改善；"
            f"95%事件重采样区间 [{r.ci_low:+.1f}%, {r.ci_high:+.1f}%]（{interval}）。")
    worse = primary[primary.improvement_percent.lt(0)].sort_values("improvement_percent")
    worse_text = "、".join(f"{r.event}（{r.improvement_percent:+.1f}%）" for r in worse.itertuples()) or "无"
    event_table = pd.DataFrame([dict(
        事件=r.event, 等级=CN[r.strength], ONI峰值=f"{r.peak_oni:.1f}",
        起报年=r.development_years, 配对数=r.n_pairs,
        RO_RMSE=f"{r.RMSE_RO:.3f}", 加PMM_RMSE=f"{r.RMSE_RO_PMM:.3f}",
        提升率=f"{r.improvement_percent:+.1f}%") for r in primary.itertuples()])
    caveats = [
        "中、弱组各只有3次事件，置信区间是描述性区间，不能据此作稳定的显著性判断。所有区间是逐指标区间，未作多重比较校正。",
        "bootstrap按事件重采样既有预测，不重新训练；不包含模型参数、PMM模态、再分析产品和全部跨事件依赖的不确定性。",
        "事件等级由完整事件的观测ONI峰值决定，仅用于事后评分。持续事件1986–88及2014–16分别含两个起报年，但汇总各占一个事件权重。",
        "这是模型参数样本外的回溯试验。训练可使用目标事件以外的较晚年份；官方PMM采用1950–2005固定模态；完整月均初态及现版本资料不等于当时实时可用资料。",
        "RO＋PMM与RO分别拟合，其差异包括增广后重新估计海温／海洋系数的变化；这是预测增益，不是PMM独立因果效应。",
        "本轮海洋状态为总WWV26，不能继承旧D20模型的数值。三个月平均评分的第一目标窗包含共同的起报月，单列为补充，不与月平均主结果混排。",
    ]
    method = (
        "共同资料1982-01至2024-12，516个月，无缺测。13次暖事件（强7、中3、弱3），15个发展年，75个起报。"
        "每个起报自由积分9个月，主评分共675对预测；两个模型始终逐条配对。"
        "每次排除首个达标季节首月至最后达标季节末月，再向两侧各扩12个月，边界裁至资料范围。"
        "其余全部ENSO位相参与拟合，预处理只用训练样本，分段矩估计不跨缺口。"
        "SST/WWV去训练同月均值后去单条线性趋势；PMM仅去训练均值。"
        "采用原sLIM年／半年谐波、perturb2估计和RK4积分，不调参、不增加其他模型。"
        "恢复训练趋势后用1982–2022同月海温气候态展示。"
        "汇总先计算每事件MSE、再等权平均开方；改善率=100×(1−RMSE加PMM/RMSE_RO)。"
    )
    stable = f"26个拟合中年度传播谱半径≥1的有{qa['unstable_fits']}个；范围 {qa['annual_radius_min']:.4f}–{qa['annual_radius_max']:.4f}。"
    qa_text = (
        f"留出资料扰动系数最大差 {qa['max_heldout_coef_error']:.2e}；固定初态、修改未来留出观测后预测最大差 "
        f"{qa['max_future_observation_error']:.2e}；RK4步长加密最大差 {qa['max_rk4_error']:.2e}；"
        f"单位变换最大差 {qa['max_unit_scaling_error']:.2e}；保存表独立重算评分最大差 {qa['saved_score_max_error']:.2e}。"
        + stable + "数值稳定不等于物理模型充分。"
    )
    text = "厄尔尼诺强度分组：RO＋PMM预报增益\n\n" + "\n".join(headlines)
    text += "\n\n变差事件：" + worse_text + "。\n\n月平均主结果（RMSE/偏差单位°C）\n" + summary_table(monthly).to_string(index=False)
    text += "\n\n全部事件\n" + event_table.to_string(index=False)
    text += "\n\n三个月平均补充（中心提前1—5个月）\n" + summary_table(seasonal).to_string(index=False)
    text += "\n\n方法\n" + method + "\n\n解释边界\n" + "\n".join(caveats)
    text += "\n\n验证\n" + qa_text + "\n"
    (out / "results_cn.txt").write_text(text, encoding="utf-8")
    caption = (
        f"整体RMSE {all_score.RMSE_RO:.3f} → {all_score.RMSE_RO_PMM:.3f}°C；"
        f"提升率 {all_score.improvement_percent:+.1f}%；改善 {all_score.improved_events}/13 次事件。"
    )
    cards = "".join(f'<p>{html.escape(line)}</p>' for line in headlines)
    images = "".join(f'<section><h2>{html.escape(title)}</h2><img src="{stem}.png" alt="{html.escape(title)}">'
        f'<p class="downloads"><a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a> · '
        f'<a href="Fig{i+1}_source.csv">图源数据 CSV</a></p></section>'
        for i, (stem, title) in enumerate(FIGURES))
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>强中弱厄尔尼诺：RO＋PMM预报增益</title>
<style>body{{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;color:#25323a;background:#f4f5f6;margin:0;line-height:1.8}}
main{{max-width:1200px;margin:40px auto;padding:0 24px}}h1{{font-size:32px;line-height:1.4}}h2{{font-size:22px}}
section,.summary{{background:white;padding:26px;margin:22px 0;border-radius:12px}}img{{width:100%;height:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:9px 12px;border-bottom:1px solid #e2e6e9;text-align:right}}
th:first-child,td:first-child{{text-align:left}}.scroll{{overflow-x:auto}}a{{color:#256c94}}.subtitle,.downloads{{color:#5a6670}}
.lead{{font-size:20px;font-weight:600}}li{{margin:10px 0}}</style><main>
<p class="subtitle">1982—2024 · 传统 ONI · 13 次事件 · 逐事件留出 · 总 WWV26</p>
<h1>加入 PMM 后，强、中、弱事件的预报改善多少？</h1>
<div class="summary"><p class="lead">{html.escape(caption)}</p>{cards}
<p><strong>变差事件：</strong>{html.escape(worse_text)}。</p></div>
<section><h2>月平均主结果</h2><p>提前1—9个月；事件等权；RMSE和偏差单位°C；正提升率表示改善。</p>
<div class="scroll">{summary_table(monthly).to_html(index=False, border=0)}</div></section>
{images}
<section><h2>全部事件逐一核对</h2><div class="scroll">{event_table.to_html(index=False, border=0)}</div></section>
<section><h2>三个月平均补充</h2><p>中心提前1—5个月；与旧图的评分定义衔接，模型训练样本不同，不直接继承旧数值。</p>
<div class="scroll">{summary_table(seasonal).to_html(index=False, border=0)}</div></section>
<section><h2>方法与解释边界</h2><p>{html.escape(method)}</p><ul>{''.join('<li>'+html.escape(c)+'</li>' for c in caveats)}</ul>
<p>分类来源：<a href="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v5/">NOAA ONI</a>；冻结本地2026-07-30版本，按发布的一位小数识别事件。</p></section>
<section><h2>数值验证</h2><p>{html.escape(qa_text)}</p><p><a href="numerical_QA.json">完整数值核验</a> ·
<a href="fit_diagnostics.csv">全部拟合诊断</a> · <a href="source_manifest.json">数据和代码校验值</a></p></section>
<section><h2>下载结果</h2><p><a href="results_cn.txt">中文结果</a> · <a href="event_catalog.csv">事件目录</a> ·
<a href="event_summary.csv">逐事件汇总</a> · <a href="group_summary.csv">分组汇总</a> ·
<a href="monthly_forecasts.csv">逐起报月平均预测</a> · <a href="seasonal_forecasts.csv">季节平均预测</a> ·
<a href="group_scores.csv">全部分组技巧</a> · <a href="protocol_before_run.txt">固定试验口径</a></p></section></main></html>'''
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "reproduce.txt").write_text(
        "From the Maryland project root, with numpy, pandas and matplotlib installed:\n"
        "  .venv/bin/python scripts/analyze_enso_strength_pmm_skill.py\n"
        "  .venv/bin/python scripts/analyze_enso_strength_pmm_skill.py --validate-only\n"
        "  .venv/bin/python -m unittest discover -s tests -p test_enso_strength_pmm_skill.py -v\n"
        "  .venv/bin/python scripts/analyze_enso_strength_pmm_skill.py --report-only\n\n"
        "The first command regenerates this dedicated output folder only. Numerical\n"
        "protocol and source hashes are saved before fitting. Existing three-event\n"
        "outputs and model code are unchanged. See protocol_before_run.txt for all\n"
        "definitions. group_scores.csv contains overall / lead / init / init_lead\n"
        "views, for monthly main and seasonal supplemental scores. Zero in a\n"
        "coordinate column means aggregation over that dimension, not lead0 scoring.\n"
        "Both forecasts are columns in each row of monthly_forecasts.csv so paired\n"
        "samples cannot silently diverge. Event-level MSE values are in event_scores.csv.\n",
        encoding="utf-8")
    print(f"Report: {out / 'index.html'}", flush=True)


if __name__ == "__main__":
    from analyze_enso_strength_pmm_skill import DEFAULT_OUT
    report(DEFAULT_OUT)
