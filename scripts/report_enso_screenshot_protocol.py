#!/usr/bin/env python3
"""Screenshot-style seasonal plumes and consistently seasonal skill displays."""
from pathlib import Path
import html
import json
import os
import zipfile

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/maryland_enso_strength_mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

BLUE, ORANGE, BLACK, INK = "#0075BE", "#E56A0A", "#252A30", "#052D50"
GROUPS = ("strong", "moderate", "weak")
EN = dict(strong="Strong", moderate="Moderate", weak="Weak", all="All")
CN = dict(strong="强", moderate="中", weak="弱", all="全部")
FORMULA = "dX/dt = L(t)X       RO: X = (T,h)ᵀ       RO+PMM: X = (T,h,p)ᵀ"
def protocol_note(start_year):
    period = ("只把拟合起始年从2002提前至1982：算子拟合1982—2024，" if start_year == 1982
        else "拟合期恢复为2002—2024，仅比较这23年内的事件，")
    return ("完全按旧截图的季节平均方法：观测与自由预报均取三个月中心平均，展示中心提前1—8月的完整有效曲线，"
        "评分只用中心提前1—5月。五个起报为2—6月，月初态积分9个月后才求季节平均。"
        +period+"去趋势终点仍为2025年4月；D20、完整1991—2020气候态、原sLIM估计及积分设置均与旧图一致。"
        "表中RMSE变化=100×(加PMM/RO−1)，负数表示改善。r为事件内起报—季节配对相关。")


def style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "svg.fonttype": "none", "legend.frameon": False})


def save(fig, out, stem):
    for ext in ("png", "pdf", "svg"):
        fig.savefig(out / f"{stem}.{ext}", dpi=220, facecolor="white")


def draw(ax, data, observations, title, compact=False, count=None):
    for month in range(2, 7):
        f = data[data.init_month.eq(month)].sort_values("lead")
        assert f.lead.to_list() == list(range(1, 9))
        ax.plot(f.relative_month, f.RO, color=BLUE, lw=1.2 if compact else 1.4, ls=(0, (5, 4)))
        ax.plot(f.relative_month, f.RO_PMM, color=ORANGE, lw=1.2 if compact else 1.4)
    obs = observations.sort_values("relative_month")
    assert obs.relative_month.to_list() == list(range(1, 16))
    values = np.concatenate([obs.observed, data[["RO", "RO_PMM"]].to_numpy().ravel()])
    assert np.isfinite(values).all() and values.min() >= -1 and values.max() < 3.5
    ax.plot(obs.relative_month, obs.observed, color=BLACK, lw=2.5 if compact else 3.)
    ax.set(xlim=(1, 15), ylim=(-1, 3.5), xticks=[1, 5, 9, 13], yticks=[-1, 0, 1, 2, 3])
    ax.tick_params(length=0, pad=7, labelleft=True, labelbottom=True, labelsize=10 if compact else 12, colors="#233C50")
    ax.set_title(title, loc="left", color=INK, fontweight="bold", fontsize=12 if compact else 17, pad=16 if compact else 22)
    for name in ("left", "bottom"):
        ax.spines[name].set_color("#B8CAD7"); ax.spines[name].set_linewidth(.7)
    ax.grid(axis="y", color="#D9E2E9", lw=.65)
    ax.axhline(0, color="#B2C6D5", lw=.7, zorder=0)
    if count:
        ax.text(.02, .94, count, transform=ax.transAxes, va="top", color="#617483", fontsize=10)


def legend(fig, y, size=11):
    fig.legend(handles=[Line2D([], [], color=BLACK, lw=3, label="Observed"),
        Line2D([], [], color=BLUE, lw=1.4, ls=(0, (5, 4)), label="RO"),
        Line2D([], [], color=ORANGE, lw=1.4, label="RO + PMM")], loc="lower center",
        bbox_to_anchor=(.5, y), ncol=3, handlelength=3, columnspacing=3, fontsize=size)


def table_rows(scores, groups=False):
    columns = ["Group" if groups else "Event", "Improved events" if groups else "r (RO / RO+PMM)",
               "RMSE °C (RO / RO+PMM)", "RMSE change"]
    rows = []
    for label, s in scores:
        rows.append([label, f"{int(s.improved_events)}/{int(s.n_events)}" if groups else f"{s.r_RO:.3f} / {s.r_RO_PMM:.3f}",
                     f"{s.RMSE_RO:.3f} / {s.RMSE_RO_PMM:.3f}", f"{s.rmse_change_percent:+.1f}%"])
    return columns, rows


def plume(panels, scores, groups=False, start_year=1982):
    n = len(panels)
    width = {1: 9.4, 2: 15.4, 3: 17.2}[n]
    fig, axes = plt.subplots(1, n, figsize=(width, 7.0), squeeze=False)
    fig.subplots_adjust(left=.07 if n == 1 else .045, right=.98, top=.75, bottom=.43, wspace=.25)
    for ax, p in zip(axes.flat, panels):
        draw(ax, p["forecast"], p["observed"], p["title"], count=p.get("count"))
    fig.text(.045 if n > 1 else .07, .963, FORMULA, color=INK, fontsize=19 if n > 1 else 12.5, fontweight="bold")
    fig.text(.045 if n > 1 else .07, .91,
        "Seasonal linear model. Standardized states: T = SST, h = GODAS mean D20, p = PMM", color="#617483", fontsize=11.5 if n > 1 else 9.2)
    legend(fig, .325, size=11)
    fig.text(.5, .30, "Five February–June starts; Jan = 1, next Jan = 13. Three-month mean Niño-3.4 SSTA.",
             ha="center", fontsize=10, color="#617483")
    tax = fig.add_axes([.07 if n == 1 else .045, .12, .90 if n == 1 else .935, .15]); tax.axis("off")
    headers, rows = table_rows(scores, groups)
    t = tax.table(cellText=rows, colLabels=headers, cellLoc="center", colLoc="center", bbox=[0, 0, 1, 1],
                  colWidths=[.16, .27, .36, .21])
    t.auto_set_font_size(False); t.set_fontsize(10 if n == 1 else 11)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor("#D4E0E8"); cell.set_linewidth(.6)
        if r == 0:
            cell.set_facecolor(INK); cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#F4F7F9" if r % 2 else "white")
    fig.text(.07 if n == 1 else .045, .038,
        f"Fit: {start_year}–2024; original detrending end: Apr 2025; 1991–2020 SST reference. In-sample retrospective comparison.\n"
        "Curves: center leads 1–8. Scores: center leads 1–5. Negative RMSE change = improvement; no additional smoothing.",
        fontsize=8.5, color="#617483", linespacing=1.6)
    return fig


def overview(panels, out, start_year=1982):
    nrows = int(np.ceil(len(panels)/3))
    n_events = len({p["event"] for p in panels})
    fig, axes = plt.subplots(nrows, 3, figsize=(17.4, 3.1*nrows+2.7), sharex=True, sharey=True, squeeze=False)
    fig.subplots_adjust(left=.055, right=.985, top=.82 if nrows == 3 else .90,
        bottom=.14 if nrows == 3 else .105, hspace=.46, wspace=.20)
    for i, (ax, p) in enumerate(zip(axes.flat, panels)):
        draw(ax, p["forecast"], p["observed"], p["overview_title"], compact=True, count=p["strength"])
        if i % 3 == 0:
            ax.set_ylabel("Seasonal SSTA (°C)")
    for ax in axes.flat[len(panels):]: ax.set_visible(False)
    fig.suptitle(f"All {n_events} El Niño events · Screenshot-matched seasonal trajectories", fontsize=22, color=INK, fontweight="bold", y=.983)
    fig.text(.5, .93 if nrows == 3 else .95, FORMULA, ha="center", color=INK, fontsize=17)
    legend(fig, .89 if nrows == 3 else .918, 12)
    fig.text(.5, .067, "Month of development year  (13 = January of following year)", ha="center", fontsize=12)
    fig.text(.055, .018, f"{start_year}–2024 fit; original April-2025 detrending end. Same D20, sLIM, 1991–2020 SST reference, February–June starts and 9-month integration.\n"
        "Both observations and forecasts are centered three-month means. Sustained episodes retain separate development-year panels.",
        fontsize=10.2, color="#617483", linespacing=1.6)
    save(fig, out, "all_events_overview"); plt.close(fig)


def skill_figures(groups, events, out, start_year=1982):
    counts = events.strength.value_counts()
    sample_note = f"Strong: {counts.strong}; moderate: {counts.moderate}; weak: {counts.weak} events. Small-sample group results."
    lead = groups.query("view == 'lead' and group != 'all'")
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.9), sharex=True, sharey="row")
    fig.subplots_adjust(left=.075, right=.98, top=.84, bottom=.14, hspace=.17, wspace=.18)
    fig.suptitle("Seasonal forecast skill · Screenshot scoring protocol", fontsize=19, color=INK, fontweight="bold", y=.97)
    for i, group in enumerate(GROUPS):
        g = lead[lead.group.eq(group)].sort_values("lead"); x = g.lead.to_numpy()
        a, b = axes[:, i]; a.set_title(EN[group]+f" · {int(g.n_events.iloc[0])} events", pad=13)
        a.plot(x, g.RMSE_RO, "o--", color=BLUE, label="RO"); a.plot(x, g.RMSE_RO_PMM, "o-", color=ORANGE, label="RO + PMM")
        b.fill_between(x, g.change_ci_low, g.change_ci_high, color=BLUE, alpha=.13)
        b.plot(x, g.rmse_change_percent, "o-", color=BLUE); b.axhline(0, color="#596D7A", lw=.8)
        for ax in (a, b):
            ax.grid(axis="y", alpha=.18); ax.set_xticks(range(1, 6))
        b.set_xlabel("Season-center lead (months)")
    axes[0, 0].set_ylabel("RMSE (°C)"); axes[0, 0].legend(fontsize=9)
    axes[1, 0].set_ylabel("RMSE change (%)\nNegative = improvement")
    fig.text(.075, .035, "Centered 3-month means; center leads 1–5; February–June starts; equal event weights. Shading: 5,000 paired-event bootstrap draws.\n"
        +sample_note+f" D20 sLIM, {start_year}–2024 fit.", fontsize=9, color="#617483")
    save(fig, out, "Fig1_seasonal_skill_by_lead"); plt.close(fig)
    fig, (left, right) = plt.subplots(1, 2, figsize=(13.5, 8), sharey=True)
    fig.subplots_adjust(left=.22, right=.96, top=.85, bottom=.16, wspace=.25)
    e = events.assign(order=events.strength.map({g: i for i, g in enumerate(GROUPS)})).sort_values(["order", "event"])
    y = np.arange(len(e))
    left.scatter(e.RMSE_RO, y, color=BLUE, label="RO"); left.scatter(e.RMSE_RO_PMM, y, color=ORANGE, label="RO + PMM")
    for i, row in enumerate(e.itertuples()):
        left.plot([row.RMSE_RO, row.RMSE_RO_PMM], [i, i], color="#CFD9E0", lw=2, zorder=0)
    left.set(yticks=y, yticklabels=e.event, xlabel="Seasonal Niño3.4 RMSE (°C)"); left.invert_yaxis(); left.legend(loc="upper right", fontsize=9)
    values = e.rmse_change_percent.to_numpy(); extent = max(abs(values).max(), 5)
    right.barh(y, values, color=["#278176" if v < 0 else "#B76842" for v in values]); right.axvline(0, color="#596D7A", lw=.8)
    right.set_xlim(min(0, values.min())-.35*extent, max(0, values.max())+.25*extent)
    for i, value in enumerate(values):
        right.text(value+(.02*extent if value >= 0 else -.02*extent), i, f"{value:+.1f}%", va="center", ha="left" if value >= 0 else "right")
    right.set_xlabel("RMSE change (%) · Negative = improvement")
    for ax in (left, right): ax.grid(axis="x", alpha=.15); ax.set_axisbelow(True)
    fig.suptitle(f"All {len(events)} events · Same seasonal scoring as the screenshot", fontsize=19, color=INK, y=.96, fontweight="bold")
    fig.text(.22, .045, "Each event retains all five starts and center leads 1–5. Sustained episodes include two development years.\n"
        "Green: lower RMSE with PMM. Brown: higher RMSE with PMM. No outcomes omitted.", fontsize=9.5, color="#617483")
    save(fig, out, "Fig2_seasonal_event_changes"); plt.close(fig)
    data = groups.query("view == 'init_lead' and group != 'all'")
    limit = max(5, float(np.ceil(data.rmse_change_percent.abs().max()/5)*5))
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 5.5), sharey=True)
    fig.subplots_adjust(left=.07, right=.97, top=.78, bottom=.33, wspace=.18)
    for ax, group in zip(axes, GROUPS):
        matrix = data[data.group.eq(group)].pivot(index="init_month", columns="lead", values="rmse_change_percent").loc[range(2, 7), range(1, 6)]
        im = ax.imshow(matrix, cmap="BrBG_r", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit), aspect="auto")
        ax.set(xticks=range(5), xticklabels=range(1, 6), yticks=range(5), yticklabels=["Feb", "Mar", "Apr", "May", "Jun"], xlabel="Season-center lead (months)")
        ax.set_title(EN[group], pad=12)
        for (i, j), value in np.ndenumerate(matrix.to_numpy()):
            ax.text(j, i, f"{value:+.0f}", ha="center", va="center", color="white" if abs(value) > limit*.6 else "#263C48")
    axes[0].set_ylabel("Initialization month")
    ca = fig.add_axes([.34, .18, .32, .025]); fig.colorbar(im, cax=ca, orientation="horizontal").set_label("RMSE change (%) · Negative = improvement")
    fig.suptitle("Initialization month × seasonal lead · PMM effect", fontsize=19, color=INK, fontweight="bold", y=.95)
    fig.text(.07, .035, "Three-month means; shared color scale; equal event weights. "+sample_note, fontsize=9.5, color="#617483")
    save(fig, out, "Fig3_seasonal_init_lead_changes"); plt.close(fig)


def report(out):
    style()
    protocol = json.loads((out / "analysis_protocol.json").read_text())
    start_year = int(protocol["start"][:4])
    note = protocol_note(start_year)
    f = pd.read_csv(out / "seasonal_plot_forecasts.csv")
    obs = pd.read_csv(out / "seasonal_plot_observations.csv")
    catalog = pd.read_csv(out / "event_catalog.csv", dtype={"development_years": str})
    events = pd.read_csv(out / "primary_event_summary.csv")
    groups = pd.read_csv(out / "primary_group_scores.csv")
    overall = groups.query("view == 'overall'")
    years = pd.read_csv(out / "development_year_summary.csv").set_index("development_year")
    n_events, n_years = len(catalog), len(years)
    counts = catalog.strength.value_counts()
    small_sample = f"强、中、弱组分别只有{counts.strong}、{counts.moderate}、{counts.weak}次事件；各强度组为小样本结果。" if start_year == 2002 else "中、弱组各只有3次事件。"
    conclusion_parts = []
    for group in GROUPS:
        row = overall[overall.group.eq(group)].iloc[0]
        conclusion_parts.append(f"{CN[group]}组RMSE{'下降' if row.rmse_change_percent < 0 else '上升'}{abs(row.rmse_change_percent):.2f}%（{int(row.improved_events)}/{int(row.n_events)}次事件改善）")
    total = overall[overall.group.eq("all")].iloc[0]
    conclusion = "；".join(conclusion_parts)+f"。全部{n_events}次中{int(total.improved_events)}次改善、{int(total.worsened_events)}次变差，效果不一致。"
    if (overall.change_ci_low.le(0) & overall.change_ci_high.ge(0)).all():
        conclusion += "所有组的95%事件重采样区间均跨零，未显示稳定改善。"
    pdf_name = f"all_events_{n_events}pages.pdf"
    panels = []
    for group in GROUPS:
        for event in catalog[catalog.strength.eq(group)].sort_values("event").itertuples(index=False):
            for year in map(int, event.development_years.split(",")):
                panels.append(dict(event=event.event, year=year, strength=EN[group],
                    forecast=f[f.development_year.eq(year)], observed=obs[obs.development_year.eq(year)],
                    title=f"{year}   Niño-3.4 SSTA (°C)", overview_title=f"{event.event} · {year} starts"))
    eventdir = out / "event_trajectories"; eventdir.mkdir(exist_ok=True)
    files, cards = [], []
    with PdfPages(eventdir / pdf_name) as pdf:
        for group in GROUPS:
            cards.append(f"<h2>{CN[group]}事件</h2>")
            for event in catalog[catalog.strength.eq(group)].sort_values("event").itertuples(index=False):
                p = [v for v in panels if v["event"] == event.event]
                s = events[events.event.eq(event.event)].iloc[0]
                fig = plume(p, [(event.event, s)], start_year=start_year)
                stem = f"event_{event.event}_Nino34_trajectories"
                save(fig, eventdir, stem); pdf.savefig(fig, facecolor="white"); plt.close(fig)
                files.append(dict(event=event.event, development_years=event.development_years,
                    png=stem+".png", pdf=stem+".pdf", svg=stem+".svg"))
                cards.append(f'<section><h3>{event.event} · {CN[group]}</h3><img src="{stem}.png" alt="{event.event}季节预报">'
                    f'<p><a href="{stem}.png">PNG</a> · <a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></p></section>')
        assert pdf.get_pagecount() == n_events
    overview(panels, eventdir, start_year)
    pd.DataFrame(files).to_csv(eventdir / "figure_index.csv", index=False)
    example_years = (1997, 2015, 2023) if start_year == 1982 else (2009, 2015, 2023)
    fig = plume([next(p for p in panels if p["year"] == y) for y in example_years],
                 [(str(y), years.loc[y]) for y in example_years], start_year=start_year)
    save(fig, out, "Fig0_three_events_screenshot_style"); plt.close(fig)
    means = pd.read_csv(out / "seasonal_group_mean_forecasts.csv")
    mean_obs = pd.read_csv(out / "seasonal_group_mean_observations.csv")
    ps, ss = [], []
    for g in GROUPS:
        row = overall[overall.group.eq(g)].iloc[0]
        ps.append(dict(forecast=means[means.strength.eq(g)], observed=mean_obs[mean_obs.strength.eq(g)],
            title=EN[g]+"   Niño-3.4 SSTA (°C)", count=f"Mean of {int(row.n_events)} events"))
        ss.append((EN[g], row))
    fig = plume(ps, ss, groups=True, start_year=start_year); save(fig, out, "Fig4_strength_mean_Nino34_trajectories"); plt.close(fig)
    skill_figures(groups, events, out, start_year)
    page_style = '''<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;background:#f4f5f6;color:#243b4c;line-height:1.8;margin:0}
main{max-width:1300px;margin:34px auto;padding:0 22px}section{background:white;padding:24px;margin:24px 0;border-radius:10px}img{width:100%;height:auto}
a{color:#256c94}h1{font-size:30px}h2{font-size:23px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:8px 10px;border-bottom:1px solid #dce5eb;text-align:right}.scroll{overflow-x:auto}</style>'''
    event_page = '<!doctype html><html lang="zh-CN">'+page_style+f'<title>截图口径：全部{n_events}事件</title><main><h1>{start_year}—2024：全部{n_events}事件 · 季节平均多起报图</h1><p>'+note+'</p>'
    event_page += f'<p><a href="{pdf_name}">{n_events}页合并PDF</a> · <a href="all_event_figures.zip">全部单图ZIP</a> · <a href="all_events_overview.png">{n_years}面板总览</a> · <a href="../index.html">分组与方法报告</a></p>'
    event_page += ''.join(cards)+'</main></html>'
    (eventdir / "index.html").write_text(event_page, encoding="utf-8")
    (eventdir / "readme_cn.txt").write_text(note+f"\n{n_events}事件，{n_years}发展年面板，PNG/PDF/SVG；与同目录主报告共用季节评分。\n")
    with zipfile.ZipFile(eventdir / "all_event_figures.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for item in files:
            for ext in ("png", "pdf", "svg"): z.write(eventdir / item[ext], arcname=item[ext])
        for name in ("figure_index.csv", "readme_cn.txt"): z.write(eventdir / name, arcname=name)
    summary = pd.DataFrame([dict(组别=CN[r.group], 事件数=r.n_events,
        RO_RMSE=f"{r.RMSE_RO:.3f}", 加PMM_RMSE=f"{r.RMSE_RO_PMM:.3f}",
        RMSE变化=f"{r.rmse_change_percent:+.2f}%", 变化95区间=f"[{r.change_ci_low:+.2f}, {r.change_ci_high:+.2f}]%",
        改善事件=f"{r.improved_events}/{r.n_events}", RO偏差=f"{r.bias_RO:+.3f}", 加PMM偏差=f"{r.bias_RO_PMM:+.3f}") for r in overall.itertuples()])
    event_table = pd.DataFrame([dict(事件=r.event, 强度=CN[r.strength], RO相关=f"{r.r_RO:.3f}", 加PMM相关=f"{r.r_RO_PMM:.3f}",
        RO_RMSE=f"{r.RMSE_RO:.3f}", 加PMM_RMSE=f"{r.RMSE_RO_PMM:.3f}", RMSE变化=f"{r.rmse_change_percent:+.2f}%") for r in events.itertuples()])
    qa = json.loads((out / "screenshot_QA.json").read_text())
    qa_text = f"把起始年恢复2002后，两套模型及旧图240个季节预测均成功复现，最大预测差{qa['old_240_seasonal_values_max_error']:.2e}°C。新图全部季节观测与旧观测系列差{qa['old_observation_match_max_error']:.2e}°C；三个月平均、事件等权和保存表评分均独立核验。"
    if start_year == 2002:
        qa_text = f"当前两套模型与原截图冻结模型一致，系数及尺度最大差{qa['current_models_equal_legacy_max_error']:.2e}；2015、2023两案例全部160个季节预测值与旧图最大差{qa['current_2015_2023_curves_equal_legacy_max_error']:.2e}°C。完整1991—2020气候态、三个月平均、事件等权和保存表评分均独立核验。"
    text = note+"\n\n"+conclusion+"\n\n分组结果（RMSE变化负数为改善）\n"+summary.to_string(index=False)+"\n\n逐事件\n"+event_table.to_string(index=False)+"\n\n"+qa_text
    text += "\n"+small_sample+"区间以事件为配对重采样单位。全时段样本内回溯比较。持续事件先在内部平均发展年，再进行事件等权；不对合成平均曲线直接计算分组技巧。\n"
    (out / "results_cn.txt").write_text(text, encoding="utf-8")
    main = '<!doctype html><html lang="zh-CN">'+page_style+f'<title>{start_year}—2024：D20季节预报</title><main><h1>按截图口径：{start_year}—2024拟合与事件比较</h1><p>'+note+'</p>'
    main += f'<p><a href="event_trajectories/index.html">全部{n_events}事件单图</a> · <a href="event_trajectories/{pdf_name}">{n_events}页PDF</a> · <a href="event_trajectories/all_event_figures.zip">单图ZIP</a></p>'
    for stem, label in [("Fig0_three_events_screenshot_style", "、".join(map(str, example_years))+"：截图样式"),
                        ("Fig4_strength_mean_Nino34_trajectories", "强、中、弱：事件等权平均轨迹")]:
        main += f'<section><h2>{label}</h2><img src="{stem}.png" alt="{label}"><p><a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></p></section>'
    main += '<section><h2>主评分：季节中心提前1—5月</h2><p>'+conclusion+'</p><p>RMSE变化负数为改善。'+small_sample+'</p><div class="scroll">'+summary.to_html(index=False, border=0)+'</div></section>'
    for stem, label in [("Fig1_seasonal_skill_by_lead", "提前期技巧"), ("Fig2_seasonal_event_changes", "逐事件增益"), ("Fig3_seasonal_init_lead_changes", "起报月×提前期")]:
        main += f'<section><h2>{label}</h2><img src="{stem}.png" alt="{label}"><p><a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></p></section>'
    main += '<section><h2>全部事件评分</h2><div class="scroll">'+event_table.to_html(index=False, border=0)+'</div></section>'
    main += '<section><h2>一致性核验</h2><p>'+qa_text+'</p><p>算子拟合截至2024年12月，趋势拟合截至2025年4月，与旧流程的两类终点一致。模型包含目标事件，属于样本内回溯比较。</p></section>'
    links = [("results_cn.txt", "中文结果"), ("primary_event_summary.csv", "逐事件主评分"), ("primary_group_scores.csv", "分组全部季节评分"),
        ("development_year_summary.csv", "逐发展年评分"), ("seasonal_plot_forecasts.csv", "季节预测曲线"), ("seasonal_plot_observations.csv", "季节观测曲线"),
        ("seasonal_group_mean_forecasts.csv", "分组平均曲线"), ("protocol_before_run.txt", "完整口径"), ("screenshot_QA.json", "一致性核验"),
        ("models_and_preprocessing.json", "模型和预处理"), ("source_manifest.json", "来源校验值"), ("reproduce.txt", "复现命令")]
    main += '<section><h2>数据与代码</h2><p>'+" · ".join(f'<a href="{p}">{t}</a>' for p, t in links)+'</p></section></main></html>'
    (out / "index.html").write_text(main, encoding="utf-8")
    (out / "reproduce.txt").write_text("From the Maryland project root with numpy, pandas and matplotlib installed:\n"
        f"python scripts/analyze_enso_screenshot_protocol.py --start-year {start_year}\n"
        f"python scripts/analyze_enso_screenshot_protocol.py --start-year {start_year} --report-only\n"
        f"python scripts/analyze_enso_screenshot_protocol.py --start-year {start_year} --validate-only\n\n"
        "Primary scores and figures are seasonal. monthly_forecasts.csv and the mixed target_type score tables are audit intermediates.\n"
        f"Fit and event selection: {start_year}--2024. The legacy detrending endpoint Apr2025 is retained.\n")
    print(summary.to_string(index=False), flush=True)
    print(out / "index.html", flush=True)
