#!/usr/bin/env python3
"""Plot all 13 El Niño episodes from the saved full-period D20 forecasts.

No model fitting, averaging of events, interpolation, or temporal smoothing.
The two sustained episodes retain separate panels for both development years.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import zipfile

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/maryland_enso_strength_mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "outputs/research_2026/enso_strength_fullperiod_D20_20261015"
BLUE, ORANGE, BLACK = "#0075BE", "#E56A0A", "#252A30"
EN = {"strong": "Strong", "moderate": "Moderate", "weak": "Weak"}
CN = {"strong": "强", "moderate": "中", "weak": "弱"}
GROUPS = ("strong", "moderate", "weak")
LIMITS = (-1.2, 3.15)
SOURCE_FILES = (
    "monthly_forecasts.csv", "event_catalog.csv", "inputs_absolute.csv",
    "display_climatology.csv", "event_summary.csv", "analysis_protocol.json",
    "models_and_preprocessing.json",
)
NOTE = (
    "使用1982—2024连续全时段拟合的两套D20 sLIM模型。黑色粗线为ERSST Niño3.4观测距平，"
    "蓝色虚线为RO，橙色实线为RO＋PMM。每个发展年保留2—6月五个起报，各积分9个月；"
    "空心点标出共同观测初态。横轴1—15为发展年1月至次年3月，13为次年1月。"
    "所有面板使用相同纵轴，距平参考1991—2020同月气候态。1986—88和2014—16各含两个发展年，"
    "在该事件的一张图中分为两个面板展示，不进行年际平均；统计仍各算一个事件。"
    "本次仅绘制已经保存的预测，不重拟合、不平滑。图上RMSE降幅为该事件五个起报、提前1—9月的既有评分；"
    "持续事件汇总两个发展年。"
)


def hashes(source):
    return {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def load(source):
    protocol = json.loads((source / "analysis_protocol.json").read_text())
    assert protocol["design"] == "full_period_in_sample" and protocol["model_count"] == 2
    assert protocol["climatology"] == "1991-2020" and "D20" in protocol["ocean_state"]
    forecasts = pd.read_csv(source / "monthly_forecasts.csv", parse_dates=["init", "target"])
    catalog = pd.read_csv(source / "event_catalog.csv", dtype={"development_years": str})
    raw = pd.read_csv(source / "inputs_absolute.csv", index_col="time", parse_dates=True)
    climate = pd.read_csv(source / "display_climatology.csv", index_col="month")
    scores = pd.read_csv(source / "event_summary.csv").query("target_type == 'monthly' and view == 'overall'").set_index("event")
    assert len(catalog) == 13 and catalog.event.is_unique and scores.index.is_unique
    assert catalog.strength.value_counts().to_dict() == {"strong": 7, "moderate": 3, "weak": 3}
    assert len(forecasts) == 750 and forecasts.init.nunique() == 75
    assert not forecasts.duplicated(["event", "init", "lead"]).any()
    assert np.isfinite(forecasts[["RO", "RO_PMM", "observed"]]).all().all()
    forecasts["relative_month"] = (forecasts.target.dt.year-forecasts.development_year)*12+forecasts.target.dt.month
    assert forecasts.relative_month.eq(forecasts.init_month+forecasts.lead).all()
    panels, obs_rows, maximum = [], [], 0.
    for strength in GROUPS:
        for event in catalog[catalog.strength.eq(strength)].sort_values("event").itertuples(index=False):
            for year in map(int, event.development_years.split(",")):
                selected = forecasts[forecasts.event.eq(event.event) & forecasts.development_year.eq(year)]
                assert len(selected) == 50 and set(selected.init_month) == set(range(2, 7))
                dates = pd.date_range(f"{year}-01-01", periods=15, freq="MS")
                obs = raw.loc[dates, "sst"].to_numpy()-climate.loc[dates.month, "sst"].to_numpy()
                assert np.isfinite(obs).all()
                for month, part in selected.groupby("init_month"):
                    part = part.sort_values("lead")
                    assert part.lead.to_list() == list(range(10))
                    assert part.init.eq(pd.Timestamp(year, int(month), 1)).all()
                    difference = float(abs(part.observed.to_numpy()-obs[part.relative_month.to_numpy()-1]).max())
                    maximum = max(maximum, difference)
                    np.testing.assert_allclose(part.iloc[0][["RO", "RO_PMM"]].to_numpy(dtype=float),
                                               obs[month-1], atol=1e-10, rtol=0)
                all_values = np.concatenate([obs, selected[["RO", "RO_PMM"]].to_numpy().ravel()])
                assert all_values.min() > LIMITS[0] and all_values.max() < LIMITS[1]
                panels.append(dict(event=event.event, strength=strength, year=year, obs=obs, forecasts=selected))
                obs_rows.extend(dict(event=event.event, strength=strength, development_year=year,
                    time=t, relative_month=i+1, observed=float(v)) for i, (t, v) in enumerate(zip(dates, obs)))
    assert len(panels) == 15 and maximum < 1e-10
    score_error = 0.
    for event, part in forecasts[forecasts.lead.gt(0)].groupby("event"):
        rmse = np.sqrt(np.mean((part[["RO", "RO_PMM"]].to_numpy()-part.observed.to_numpy()[:, None])**2, axis=0))
        gain = 100*(1-rmse[1]/rmse[0])
        score_error = max(score_error, abs(float(gain-scores.loc[event, "improvement_percent"])))
    assert score_error < 1e-9
    return forecasts, catalog, scores, panels, pd.DataFrame(obs_rows), dict(
        event_count=13, development_year_panel_count=15, start_count=75,
        forecast_rows=750, observed_rows=225, max_saved_observation_error=maximum,
        max_saved_score_error=score_error, all_initial_states_match=True,
        uniform_y_limits=list(LIMITS), all_data_inside_axes=True,
        refitted=False, temporal_smoothing=False, event_or_year_averaging=False)


def style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "svg.fonttype": "none"})


def draw_panel(ax, panel, compact=False):
    for month in range(2, 7):
        f = panel["forecasts"].query("init_month == @month").sort_values("lead")
        ax.plot(f.relative_month, f.RO, color=BLUE, lw=1.15 if compact else 1.45, ls=(0, (5, 4)), zorder=2)
        ax.plot(f.relative_month, f.RO_PMM, color=ORANGE, lw=1.15 if compact else 1.45, zorder=3)
    ax.plot(range(1, 16), panel["obs"], color=BLACK, lw=2.4 if compact else 2.9, zorder=4)
    ax.scatter(range(2, 7), panel["obs"][1:6], s=15 if compact else 23,
               facecolor="white", edgecolor=BLACK, lw=.8, zorder=5)
    ax.set(xlim=(1, 15), ylim=LIMITS, xticks=[1, 5, 9, 13], yticks=[-1, 0, 1, 2, 3])
    ax.tick_params(axis="both", length=0, pad=7, labelsize=10 if compact else 12, colors="#243C50", labelleft=True, labelbottom=True)
    for spine in ("left", "bottom"):
        ax.spines[spine].set(color="#BDCCD7", linewidth=.7)
    ax.grid(axis="y", color="#D9E2E9", lw=.65)
    ax.axhline(0, color="#B2C6D5", lw=.7, zorder=1)
    year, event = panel["year"], panel["event"].replace("-", "–")
    title = f"{event} · {year} starts" if compact else f"{year} development year"
    ax.set_title(title, loc="left", color="#052D50", fontsize=13 if compact else 16, fontweight="bold", pad=14)
    if compact:
        ax.text(.025, .94, EN[panel["strength"]], transform=ax.transAxes, fontsize=9, color="#607482", va="top")


def legend(fig, y, size=11):
    handles = [Line2D([], [], color=BLACK, lw=2.8, label="Observed"),
        Line2D([], [], color=BLUE, lw=1.5, ls=(0, (5, 4)), label="RO"),
        Line2D([], [], color=ORANGE, lw=1.5, label="RO + PMM")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, y), ncol=3,
               frameon=False, fontsize=size, handlelength=3, columnspacing=2.6)


def event_figure(event, panels, score):
    selected = [p for p in panels if p["event"] == event.event]
    n = len(selected)
    fig, axes = plt.subplots(1, n, figsize=(9.4 if n == 1 else 15.6, 5.7), squeeze=False, sharey=True)
    fig.subplots_adjust(left=.09 if n == 1 else .06, right=.97, top=.73, bottom=.30, wspace=.18)
    for ax, panel in zip(axes.flat, selected):
        draw_panel(ax, panel)
    axes[0, 0].set_ylabel("Niño-3.4 SSTA (°C)", fontsize=12)
    fig.suptitle(f"{event.event.replace('-', '–')}  ·  {EN[event.strength]} El Niño", y=.975,
                 fontsize=22, color="#052D50", fontweight="bold")
    fig.text(.5, .89, f"Peak ONI {event.peak_oni:.1f}°C  |  Event RMSE: {score.RMSE_RO:.3f} → {score.RMSE_RO_PMM:.3f}°C"
             f"  |  Reduction: {score.improvement_percent:+.1f}%", ha="center", fontsize=11, color="#4D606F")
    fig.text(.5, .205, "Month of development year  (13 = January of following year)", ha="center", fontsize=11, color="#4D606F")
    legend(fig, .105)
    fig.text(.09 if n == 1 else .06, .025,
        "Five starts: February–June; 9-month free forecasts. ERSST anomalies: 1991–2020 reference.\n"
        "One 1982–2024 fit per model, including all events; RO = Niño3.4 + D20. Same vertical scale in every panel.",
        fontsize=8.8, color="#62717D", linespacing=1.6)
    return fig


def save(fig, out, stem):
    for extension in ("png", "pdf", "svg"):
        fig.savefig(out / f"{stem}.{extension}", dpi=220, facecolor="white")


def overview(panels, out):
    fig, axes = plt.subplots(5, 3, figsize=(17.4, 18.3), sharex=True, sharey=True)
    fig.subplots_adjust(left=.055, right=.985, top=.90, bottom=.105, hspace=.48, wspace=.20)
    for i, (ax, panel) in enumerate(zip(axes.flat, panels)):
        draw_panel(ax, panel, compact=True)
        if i % 3 == 0:
            ax.set_ylabel("SSTA (°C)", fontsize=11)
    fig.suptitle("Niño-3.4 trajectories for all 13 El Niño events", y=.985, fontsize=25, fontweight="bold", color="#052D50")
    fig.text(.5, .952, "Full-period D20 sLIM · One 1982–2024 fit per model · Five starts: February–June · 9-month free forecasts",
             ha="center", fontsize=12, color="#4D606F")
    legend(fig, .918, size=12)
    fig.text(.5, .067, "Month of development year  (13 = January of following year)", ha="center", fontsize=12, color="#4D606F")
    fig.text(.055, .018,
        "1986–88 and 2014–16 each retain two development-year panels; all 15 panels use the same vertical scale.\n"
        "Monthly ERSST anomalies relative to 1991–2020. Open circles: shared observed initial states. Saved forecasts; no refitting or smoothing.",
        fontsize=10.5, color="#62717D", linespacing=1.6)
    save(fig, out, "all_events_overview")
    plt.close(fig)


def gallery(out, catalog, scores):
    sections = []
    nav = []
    for strength in GROUPS:
        sections.append(f'<h2>{CN[strength]}事件 · {int(catalog.strength.eq(strength).sum())}次</h2>')
        for row in catalog[catalog.strength.eq(strength)].sort_values("event").itertuples(index=False):
            stem = "event_"+row.event+"_Nino34_trajectories"
            score = scores.loc[row.event]
            nav.append(f'<a href="#event-{row.event}">{row.event}</a>')
            sections.append(f'''<section id="event-{row.event}"><h3>{row.event} · {CN[strength]}事件</h3>
<img loading="lazy" src="{stem}.png" alt="{row.event}的Niño3.4多起报对比">
<p>事件RMSE：{score.RMSE_RO:.3f} → {score.RMSE_RO_PMM:.3f}°C；降幅 {score.improvement_percent:+.2f}%。</p>
<p><a href="{stem}.png">PNG</a> · <a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></p></section>''')
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>13次厄尔尼诺：逐事件Niño3.4多起报图</title>
<style>body{{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;background:#f4f5f6;color:#25323a;line-height:1.8;margin:0}}
main{{max-width:1280px;margin:32px auto;padding:0 24px}}section{{background:white;margin:24px 0;padding:24px;border-radius:12px}}
img{{width:100%;height:auto}}h1{{font-size:30px}}h2{{margin-top:48px}}h3{{font-size:22px}}a{{color:#256c94}}nav a{{display:inline-block;margin:4px 12px 4px 0}}</style>
<main><h1>每个事件的Niño3.4多起报对比</h1><p>{html.escape(NOTE)}</p>
<p><a href="all_events_13pages.pdf">13事件合并PDF</a> · <a href="all_event_figures.zip">全部单图下载ZIP</a> ·
<a href="all_events_overview.png">15面板总览PNG</a> · <a href="all_events_overview.pdf">总览PDF</a> · <a href="../index.html">返回分组报告</a></p>
<nav>{' · '.join(nav)}</nav>{''.join(sections)}
<section><h2>数据与核验</h2><p><a href="forecast_plot_data.csv">全部预测曲线</a> ·
<a href="observation_plot_data.csv">全部观测曲线</a> · <a href="figure_index.csv">图片目录</a> ·
<a href="plot_QA.json">绘图核验</a> · <a href="source_manifest.json">来源校验值</a> ·
<a href="readme_cn.txt">说明与复现命令</a></p></section></main></html>'''
    (out / "index.html").write_text(page, encoding="utf-8")


def add_to_parent_report(source):
    path = source / "index.html"
    if not path.exists():
        return
    start, end = "<!-- event-trajectories:start -->", "<!-- event-trajectories:end -->"
    page = path.read_text()
    if start in page:
        before, rest = page.split(start, 1)
        _, after = rest.split(end, 1)
        page = before+after
    block = f'''{start}<section><h2>全部13次事件：逐事件多起报图</h2>
<p>每个事件独立出图；1986—88和2014—16各分两个发展年面板。每个面板均保留2—6月五起报。</p>
<p><a href="event_trajectories/index.html">打开全部事件图册</a> ·
<a href="event_trajectories/all_events_13pages.pdf">合并PDF</a> ·
<a href="event_trajectories/all_events_overview.png">全部事件总览</a> ·
<a href="event_trajectories/all_event_figures.zip">全部单图ZIP</a></p></section>{end}'''
    anchor = "<section><h2>全部事件逐一核对</h2>"
    assert anchor in page
    path.write_text(page.replace(anchor, block+anchor, 1), encoding="utf-8")


def run(source):
    before = hashes(source)
    forecasts, catalog, scores, panels, observations, qa = load(source)
    out = source / "event_trajectories"
    out.mkdir(parents=True, exist_ok=True)
    forecasts.to_csv(out / "forecast_plot_data.csv", index=False)
    observations.to_csv(out / "observation_plot_data.csv", index=False)
    style()
    records = []
    with PdfPages(out / "all_events_13pages.pdf") as pdf:
        for strength in GROUPS:
            for row in catalog[catalog.strength.eq(strength)].sort_values("event").itertuples(index=False):
                stem = "event_"+row.event+"_Nino34_trajectories"
                fig = event_figure(row, panels, scores.loc[row.event])
                save(fig, out, stem)
                pdf.savefig(fig, facecolor="white")
                plt.close(fig)
                records.append(dict(event=row.event, strength=strength, development_years=row.development_years,
                    panels=int(row.n_development_years), png=stem+".png", pdf=stem+".pdf", svg=stem+".svg"))
        assert pdf.get_pagecount() == 13
    overview(panels, out)
    pd.DataFrame(records).to_csv(out / "figure_index.csv", index=False)
    qa.update(individual_figures=len(records), combined_pdf_pages=13,
              saved_forecast_models_and_scores_unchanged=hashes(source) == before)
    assert qa["saved_forecast_models_and_scores_unchanged"]
    for record in records:
        for extension in ("png", "pdf", "svg"):
            assert (out / record[extension]).stat().st_size > 1000
    (out / "plot_QA.json").write_text(json.dumps(qa, indent=2)+"\n")
    (out / "source_manifest.json").write_text(json.dumps(dict(
        source_directory=str(source), sha256=before,
        plotting_script=str(Path(__file__).resolve()),
        plotting_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        matplotlib=matplotlib.__version__, numpy=np.__version__, pandas=pd.__version__), indent=2)+"\n")
    (out / "readme_cn.txt").write_text(NOTE+"\n\n"
        "13张逐事件图均有PNG/PDF/SVG；合并PDF共13页；总览共15面板。\n"
        "复现：在Maryland目录、已安装numpy/pandas/matplotlib的Python环境运行：\n"
        "  python scripts/plot_enso_event_trajectories.py\n"
        "如重建分组主报告，随后重跑本脚本可恢复图册入口。\n", encoding="utf-8")
    gallery(out, catalog, scores)
    with zipfile.ZipFile(out / "all_event_figures.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for record in records:
            for extension in ("png", "pdf", "svg"):
                path = out / record[extension]
                archive.write(path, arcname=path.name)
        for name in ("readme_cn.txt", "figure_index.csv", "plot_QA.json"):
            archive.write(out / name, arcname=name)
    add_to_parent_report(source)
    print(json.dumps(qa, indent=2), flush=True)
    print(out / "index.html", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    run(parser.parse_args().source)
