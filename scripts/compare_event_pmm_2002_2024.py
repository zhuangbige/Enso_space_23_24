#!/usr/bin/env python3
"""Compare the observed PMM-SST used by the frozen 2002--2024 D20 sLIM."""
from pathlib import Path
import hashlib
import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/maryland_enso_strength_mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/research_2026/enso_strength_screenshot_D20_2002_2024_20261015"
OUT = BASE / "pmm_comparison"
SOURCE = ROOT / "data/raw/climate_indices/standard_pmm_20261014/PMM_uw.txt"
GROUPS = ("strong", "moderate", "weak")
EN = dict(strong="Strong", moderate="Moderate", weak="Weak")
CN = dict(strong="强", moderate="中", weak="弱")
COLORS = {2009: "#0075BE", 2014: "#3D8B75", 2015: "#E56A0A", 2023: "#912E64",
          2002: "#0075BE", 2018: "#E56A0A", 2004: "#0075BE", 2006: "#E56A0A", 2019: "#3D8B75"}
METRICS = ("Feb_Jun", "MAM", "JJA", "SON", "DJF")
MONTHS = {"Feb_Jun": range(2, 7), "MAM": range(3, 6), "JJA": range(6, 9),
          "SON": range(9, 12), "DJF": range(12, 15)}


def save(fig, stem):
    for ext in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"{stem}.{ext}", dpi=240, facecolor="white")
    plt.close(fig)


def figures(curves, groups, summary, initials):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
        "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
        "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6), sharey=True)
    fig.subplots_adjust(left=.055, right=.972, top=.77, bottom=.24, wspace=.15)
    for ax, group in zip(axes, GROUPS):
        part = curves[curves.strength.eq(group)]
        ax.axvspan(2, 6, color="#E6EDF3", alpha=.65, zorder=0)
        ax.axhline(0, color="#4D5E6B", lw=.85)
        for year, p in part.groupby("development_year"):
            label = f"{year} ({'year 1' if year == 2014 else 'year 2'})" if year in (2014, 2015) else str(year)
            ax.plot(p.relative_month, p.pmm, color=COLORS[year], lw=2, label=label,
                ls="--" if year == 2014 else "-")
            initial = p[p.is_initialization]
            ax.scatter(initial.relative_month, initial.pmm, s=27, color=COLORS[year], zorder=5)
        ax.set(xlim=(1, 15), ylim=(-9, 10), xticks=[1, 3, 6, 9, 12, 15],
            xticklabels=["Jan", "Mar", "Jun", "Sep", "Dec", "Mar+1"], yticks=[-8, -4, 0, 4, 8])
        ax.set_title(f"{EN[group]} · {part.event.nunique()} events", loc="left", color="#052D50", weight="bold", pad=16)
        ax.grid(axis="y", alpha=.16); ax.legend(loc="upper right", ncol=2 if group == "strong" else 1, fontsize=9.5)
    axes[0].set_ylabel("PMM-SST mode amplitude (°C)")
    fig.suptitle("Observed PMM across the 8 El Niño events", fontsize=21, color="#052D50", weight="bold", y=.97)
    fig.text(.5, .88, "Events in 2002–2024 · Monthly values used by the existing RO+PMM model", ha="center", fontsize=12, color="#617483")
    fig.text(.055, .105, "Shading and dots: February–June initialization months. Lines: supplied monthly PMM-SST; no additional smoothing.\n"
        "2014 and 2015 are two development years of one event. All panels share the same scale; amplitude is not a regional-mean SST anomaly.",
        fontsize=10, color="#617483", linespacing=1.7)
    save(fig, "Fig1_PMM_event_evolution")

    ordered = summary.assign(group_order=summary.strength.map({g: i for i, g in enumerate(GROUPS)})).sort_values(["group_order", "development_year"])
    columns = ["Feb", "Mar", "Apr", "May", "Jun", "MAM", "JJA", "SON", "DJF"]
    rows, labels = [], []
    for row in ordered.itertuples(index=False):
        initial = initials[initials.development_year.eq(row.development_year)].sort_values("relative_month")
        rows.append([*initial.pmm.to_list(), *[getattr(row, key) for key in ("MAM", "JJA", "SON", "DJF")]])
        suffix = " (2014–16)" if row.development_year in (2014, 2015) else ""
        labels.append(f"{row.development_year}{suffix} · {EN[row.strength]}")
    values = np.array(rows)
    limit = float(np.ceil(abs(values).max()))
    fig, ax = plt.subplots(figsize=(13.2, 7.8))
    fig.subplots_adjust(left=.21, right=.96, top=.80, bottom=.23)
    im = ax.imshow(values, aspect="auto", cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit))
    ax.set(xticks=range(9), xticklabels=columns, yticks=range(9), yticklabels=labels)
    ax.axvline(4.5, color="white", lw=4)
    ax.axhline(3.5, color="white", lw=3); ax.axhline(5.5, color="white", lw=3)
    ax.text(2, 1.065, "Actual monthly initialization values", transform=ax.get_xaxis_transform(), ha="center", fontsize=12)
    ax.text(6.5, 1.065, "Observed seasonal means", transform=ax.get_xaxis_transform(), ha="center", fontsize=12)
    for (i, j), value in np.ndenumerate(values):
        ax.text(j, i, f"{value:+.2f}", ha="center", va="center", color="white" if abs(value) > .56*limit else "#19364A", fontsize=10.7)
    ca = fig.add_axes([.36, .12, .40, .022])
    fig.colorbar(im, cax=ca, orientation="horizontal").set_label("PMM-SST mode amplitude (°C)", fontsize=11)
    fig.suptitle("PMM at the five starts and through event development", fontsize=20, color="#052D50", weight="bold", y=.96)
    fig.text(.21, .025, "MAM = Mar–May; JJA = Jun–Aug; SON = Sep–Nov; DJF = Dec–next Feb.\n"
        "All values are observed PMM. Observations after initialization are not supplied to the free forecasts.",
        fontsize=9.5, color="#617483", linespacing=1.6)
    save(fig, "Fig2_PMM_initializations_and_seasons")

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    fig.subplots_adjust(left=.09, right=.97, top=.81, bottom=.24)
    ax.axvspan(2, 6, color="#E6EDF3", alpha=.65, zorder=0); ax.axhline(0, color="#4D5E6B", lw=.85)
    for group, color in zip(GROUPS, ("#912E64", "#E56A0A", "#0075BE")):
        p = groups[groups.strength.eq(group)]
        ax.plot(p.relative_month, p.pmm, lw=2.5, color=color, label=f"{EN[group]} (n={int(p.n_events.iloc[0])})")
    ax.set(xlim=(1, 15), ylim=(-9, 10), xticks=[1, 3, 6, 9, 12, 15],
        xticklabels=["Jan", "Mar", "Jun", "Sep", "Dec", "Mar+1"], ylabel="PMM-SST mode amplitude (°C)", yticks=[-8, -4, 0, 4, 8])
    ax.grid(axis="y", alpha=.16); ax.legend(loc="upper right", ncol=3, fontsize=10)
    fig.suptitle("Mean PMM by El Niño strength · Equal event weights", fontsize=18, color="#052D50", weight="bold", y=.96)
    fig.text(.09, .09, "2014/2015 are averaged within the 2014–16 event before averaging events in each group.\n"
        "Small groups (3/2/3 events); class means can conceal opposing PMM histories. Same scale as individual-event panels.",
        fontsize=9.5, color="#617483", linespacing=1.7)
    save(fig, "Fig3_PMM_strength_means")


def main():
    OUT.mkdir(exist_ok=True)
    catalog = pd.read_csv(BASE / "event_catalog.csv", dtype={"development_years": str})
    assert len(catalog) == 8 and catalog.n_development_years.sum() == 9
    model = json.loads((BASE / "models_and_preprocessing.json").read_text())
    mu, sigma = model["preprocessing"]["pmm_sst_mean"], model["models"]["RO_PMM"]["scale"][2]
    source = pd.read_csv(SOURCE, sep=r"\s+")
    source.index = pd.to_datetime(dict(year=source.Year, month=source.Mo, day=1))
    pmm = source.SST
    assert pmm.index.is_unique and pmm.index.equals(pd.date_range(pmm.index[0], pmm.index[-1], freq="MS"))
    fitting = pmm.loc["2002":"2024"]
    assert len(fitting) == 276 and fitting.notna().all()
    assert abs(fitting.mean()-mu) < 1e-12 and abs(fitting.std(ddof=0)-sigma) < 1e-12
    records = []
    for e in catalog.itertuples(index=False):
        for year in map(int, e.development_years.split(",")):
            dates = pd.date_range(f"{year}-01-01", periods=15, freq="MS")
            for relative_month, date in enumerate(dates, 1):
                value = float(pmm.loc[date])
                records.append(dict(event=e.event, strength=e.strength, development_year=year,
                    time=date, relative_month=relative_month, pmm=value, pmm_centered=value-mu,
                    pmm_model_z=(value-mu)/sigma, is_initialization=relative_month in range(2, 7)))
    curves = pd.DataFrame(records)
    assert len(curves) == 135 and np.isfinite(curves.pmm).all()
    initials = curves[curves.is_initialization].copy()
    assert len(initials) == 45
    event_curves = curves.groupby(["event", "strength", "relative_month"], as_index=False)[["pmm", "pmm_model_z"]].mean()
    groups = event_curves.groupby(["strength", "relative_month"], as_index=False)[["pmm", "pmm_model_z"]].mean()
    groups["n_events"] = groups.strength.map(catalog.strength.value_counts())
    summaries = []
    for year, g in curves.groupby("development_year"):
        row = dict(event=g.event.iloc[0], strength=g.strength.iloc[0], development_year=year)
        for key, months in MONTHS.items():
            row[key] = float(g.loc[g.relative_month.isin(months), "pmm"].mean())
            row[key+"_model_z"] = (row[key]-mu)/sigma
        init = g[g.is_initialization]
        row["positive_initials"] = int(init.pmm.gt(0).sum())
        row["positive_model_initials"] = int(init.pmm_model_z.gt(0).sum())
        for key, idx in [("minimum", g.pmm.idxmin()), ("maximum", g.pmm.idxmax())]:
            row[key] = float(g.loc[idx, "pmm"]); row[key+"_month"] = g.loc[idx, "time"].strftime("%Y-%m")
        summaries.append(row)
    summary = pd.DataFrame(summaries)
    skills = pd.read_csv(BASE / "development_year_summary.csv")
    summary = summary.merge(skills[["development_year", "RMSE_RO", "RMSE_RO_PMM", "rmse_change_percent"]], on="development_year", validate="one_to_one")
    event_summary = summary.groupby(["event", "strength"], as_index=False)[list(METRICS)].mean()
    event_skill = pd.read_csv(BASE / "primary_event_summary.csv")
    event_summary = event_summary.merge(event_skill[["event", "RMSE_RO", "RMSE_RO_PMM", "rmse_change_percent"]], on="event", validate="one_to_one")
    group_summary = event_summary.groupby("strength", as_index=False)[list(METRICS)].mean()
    group_summary["n_events"] = group_summary.strength.map(catalog.strength.value_counts())
    tables = {"monthly_event_PMM.csv": curves, "initialization_PMM.csv": initials,
        "event_mean_PMM_curves.csv": event_curves, "group_mean_PMM_curves.csv": groups,
        "development_year_PMM_summary.csv": summary, "event_PMM_summary.csv": event_summary,
        "group_PMM_summary.csv": group_summary}
    for name, table in tables.items(): table.to_csv(OUT / name, index=False)

    # Verify actual model inputs, calendar extraction, and composite weights independently.
    parent_states = pd.read_csv(BASE / "forecast_model_states.csv", parse_dates=["init"])
    initial_states = parent_states.query("model == 'RO_PMM' and variable == 'pmm' and lead == 0").set_index("init")
    assert len(initial_states) == 45
    state_error = float(abs(initials.pmm_centered.to_numpy()-initial_states.loc[initials.time, "initial_model_state"].to_numpy()).max())
    assert state_error < 1e-12
    weight_error = 0.
    for row in groups.itertuples(index=False):
        g = curves[curves.strength.eq(row.strength) & curves.relative_month.eq(row.relative_month)]
        weights = np.array([1/(g.event.nunique()*g.event.eq(event).sum()) for event in g.event])
        weight_error = max(weight_error, abs(float(weights@g.pmm.to_numpy()-row.pmm)))
    assert weight_error < 1e-12
    saved = pd.read_csv(OUT / "monthly_event_PMM.csv", parse_dates=["time"])
    np.testing.assert_allclose(saved.pmm, pmm.loc[saved.time], atol=1e-12, rtol=0)
    for row in summary.itertuples(index=False):
        for key, months in MONTHS.items():
            dates = [pd.Timestamp(row.development_year, 1, 1)+pd.DateOffset(months=m-1) for m in months]
            assert abs(getattr(row, key)-pmm.loc[dates].mean()) < 1e-12
    frozen = json.loads((BASE / "source_manifest.json").read_text())["sha256"]
    protected = [SOURCE, BASE / "models_and_preprocessing.json", BASE / "monthly_forecasts.csv",
        BASE / "primary_event_summary.csv", BASE / "development_year_summary.csv"]
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == frozen[str(SOURCE.relative_to(ROOT))]
    qa = dict(event_count=8, development_year_count=9, monthly_curve_rows=135,
        initial_state_count=45, source_version_same_as_forecasts=True,
        model_pmm_mean=mu, model_pmm_std_ddof0=sigma,
        actual_initial_state_max_error=state_error, event_weight_max_error=weight_error,
        missing_values=0, no_additional_smoothing=True, no_model_refitting=True)
    (OUT / "QA.json").write_text(json.dumps(qa, indent=2)+"\n")
    figures(curves, groups, summary, initials)

    note = ("比较2002—2024年内的8次事件，使用与当前模型完全相同的官方PMM-SST本地冻结文件。"
        "曲线直接画提供的月值，不另作平滑；圆点为2—6月五次起报。表中MAM/JJA/SON/DJF分别为3—5月、6—8月、9—11月和12月至次年2月的平均。"
        "2014、2015分别展示，均属于2014—16事件；分组时先在该事件内部平均，再按事件等权。"
        "PMM-SST按NOAA标注单位为°C，是海温空间模态的投影幅度，不能解读成某海域平均海温变化。模型实际标准化初态为(PMM−"
        f"{mu:.6f})/{sigma:.6f}，均值和标准差均固定于2002—2024年。后续观测曲线仅用于对比，不作为起报后的模型输入。")
    conclusions = [
        "强事件的PMM背景差别很大：2009年春季为负，2014、2015年春季为正，2023年春夏持续为负；强组平均会抵消这种差异。",
        "2023年MAM为−4.48、JJA为−6.54，2—6月五个起报全部为负，7月最低−7.85；这是所选发展年中最强的夏季负PMM。",
        "2015和2018年MAM分别为+5.63、+5.76，均为明显正值；2015年年末转负，而2018年后续仍总体偏正。",
        "弱事件也分化：2004、2019年春季为正，2006年春季为负；2019年的正PMM在夏秋进一步增强。",
        "与既有预报结果并列看，2015、2018的正PMM伴随技巧改善，2023的负PMM伴随技巧变差；但2014春季PMM也为正而该发展年RMSE增加16.75%。因此PMM正负不能直接等同于技巧增益，更不是单凭此图就确定的因果关系。"
    ]
    cn_table = pd.DataFrame([dict(事件=r.event, 发展年=r.development_year, 强度=CN[r.strength],
        **{"2—6月均值":f"{r.Feb_Jun:+.2f}", "MAM":f"{r.MAM:+.2f}", "JJA":f"{r.JJA:+.2f}",
           "SON":f"{r.SON:+.2f}", "DJF":f"{r.DJF:+.2f}", "该发展年RMSE变化":f"{r.rmse_change_percent:+.2f}%"}) for r in summary.itertuples(index=False)])
    text = note+"\n\n"+"\n".join(conclusions)+"\n\n"+cn_table.to_string(index=False)+"\n\nRMSE变化沿用季节中心提前1—5月的既有结果，负数改善；没有重拟合。\n"
    (OUT / "comparison_cn.txt").write_text(text)
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>8次事件的PMM比较</title><style>body{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;background:#f4f5f6;color:#243b4c;line-height:1.8;margin:0}main{max-width:1400px;margin:32px auto;padding:0 24px}section{background:white;padding:24px;margin:22px 0;border-radius:10px}img{width:100%;height:auto}a{color:#256c94}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #dde3e8;text-align:right}.scroll{overflow-x:auto}</style><main><h1>2002—2024：8次厄尔尼诺事件的PMM比较</h1><p>'+note+'</p><p><a href="../index.html">返回预报技巧比较</a></p>'
    page += '<section><h2>比较结果</h2>'+''.join('<p>'+c+'</p>' for c in conclusions)+'</section>'
    for stem, label in [("Fig1_PMM_event_evolution", "逐事件PMM演变"), ("Fig2_PMM_initializations_and_seasons", "五个起报月与季节均值"), ("Fig3_PMM_strength_means", "强中弱平均PMM")]:
        page += f'<section><h2>{label}</h2><img src="{stem}.png" alt="{label}"><p><a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></p></section>'
    page += '<section><h2>逐发展年数值与既有技巧</h2><p>PMM为观测指数；RMSE变化为已有Niño3.4预报的评分，负数为改善。2014、2015的评分不可与持续事件整体评分混用。</p><div class="scroll">'+cn_table.to_html(index=False,border=0)+'</div></section>'
    links = [("comparison_cn.txt", "中文结果"), ("monthly_event_PMM.csv", "全部月值"), ("initialization_PMM.csv", "45个实际起报值"),
        ("development_year_PMM_summary.csv", "逐发展年汇总"), ("event_PMM_summary.csv", "逐事件汇总"), ("group_PMM_summary.csv", "分组汇总"), ("QA.json", "核验"), ("source_manifest.json", "来源")]
    page += '<section><h2>数据与复现</h2><p>'+" · ".join(f'<a href="{p}">{label}</a>' for p,label in links)+'</p><p>运行：python scripts/compare_event_pmm_2002_2024.py</p></section></main></html>'
    (OUT / "index.html").write_text(page)
    paths = protected+[BASE / "event_catalog.csv", BASE / "forecast_model_states.csv", Path(__file__).resolve(),
        SOURCE.parent / "method_uw.html", SOURCE.parent / "source_manifest.json"]
    (OUT / "source_manifest.json").write_text(json.dumps(dict(
        sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        source_url="https://www.aos.wisc.edu/dvimont/MModes/RealTime/PMM.txt",
        observed_variable="PMM-SST, supplied monthly index", unit="degree_C, SST-mode projection amplitude",
        unit_reference="https://psl.noaa.gov/data/timeseries/month/PMM/", fitting_reference="2002-2024",
        model_mean=mu, model_std_ddof0=sigma, extra_smoothing=False,
        event_weighting="development years within episode first, then equal episodes"), indent=2)+"\n")
    print(text)
    print(OUT / "index.html")


if __name__ == "__main__":
    main()
