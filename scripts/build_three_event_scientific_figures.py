"""Replot the three-event diagnostics; this figure builder does not fit models.

Five main and two supporting figures form the current presentation.
The former final S3 group is replaced by the two summer-mechanism figures.
Original analyses and the historical S3 files remain available.
"""
from pathlib import Path
import os
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/maryland_story_mpl")
import hashlib
import html
import json
import textwrap
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.colors import BoundaryNorm

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/research_2026"
OCEAN = BASE / "three_event_ocean_preconditioning_20261014"
PROCESS = BASE / "three_event_process_followup_20261015"
LOCAL = BASE / "three_event_temperature_tendency_20261015"
FULLSAMPLE = BASE / "three_event_fullsample_replay_20261015"
REPLAY_KEY = "three_wwv_fullsample_detrend_perturb2"
OUT = BASE / "three_event_scientific_figures_20261015"
EVENTS = (1997, 2015, 2023)
COLORS = {1997: "#0072B2", 2015: "#B98200", 2023: "#D55E00"}
MARKERS = {1997: "o", 2015: "s", 2023: "^"}
BLACK, GRAY, PURPLE, TEAL = "#22252A", "#889099", "#77549A", "#21847B"
FILES = [OCEAN / "atmosphere_monthly.nc", OCEAN / "ocean_case_fields.nc",
         OCEAN / "january_ocean_initial_states.csv", PROCESS / "all_month_evidence.csv",
         PROCESS / "common_quarter_evidence.csv", FULLSAMPLE / "observed_state_replay.csv",
         PROCESS / "volume_interval_summaries.csv", LOCAL / "case_quarter_tendencies.csv",
         LOCAL / "summer_zonal_advection_robustness.csv"]
META, QA = [], {"scope": "5 main + 2 supporting figures", "figure_builder_does_not_fit_models": True}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def style():
    plt.rcParams.update({"font.family": "Arial", "font.size": 7.5,
        "mathtext.fontset": "dejavusans", "axes.titlesize": 8, "axes.labelsize": 7.5,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": .6, "xtick.major.width": .6, "ytick.major.width": .6,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "lines.linewidth": 1.2, "legend.frameon": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "figure.facecolor": "white", "savefig.facecolor": "white",
        "text.color": BLACK, "axes.labelcolor": BLACK, "axes.edgecolor": BLACK})


def figbase(height, title, note):
    # Paper figures contain panel labels, axes and legends. Narrative notes live in captions.
    return plt.figure(figsize=(7.2, height))


def panel(ax, letter, title="", color=BLACK):
    ax.set_title(f"({letter}) {title}", loc="left", color="black", pad=6, fontsize=8)
    ax.title.set_fontweight("normal")


def zero(ax):
    ax.axhline(0, lw=.55, color="#AEB4BA", zorder=0)


def eventlegend(fig, y=.905):
    handles = [Line2D([], [], color=COLORS[e], marker=MARKERS[e], ms=3.6,
                       lw=1.3, label=str(e)) for e in EVENTS]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.52, y),
               ncol=3, handlelength=2, columnspacing=2.5)


def months(ax):
    ax.set_xlim(.7, 12.3)
    ax.set_xticks([1, 4, 7, 10, 12], ["Jan", "Apr", "Jul", "Oct", "Dec"])
    zero(ax)


def eventline(ax, x, y, e, **kwargs):
    return ax.plot(x, y, color=COLORS[e], marker=MARKERS[e], ms=3,
                   lw=1.5 if e == 2023 else 1.15, label=str(e), **kwargs)


def save(fig, stem, title_cn, caption_cn, caption_en, sources, role, pdf):
    fig.canvas.draw()
    # Check that visible text stays within the physical page.
    renderer = fig.canvas.get_renderer()
    bad = []
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_visible() or not t.get_text():
            continue
        bb = t.get_window_extent(renderer)
        if bb.width > 0 and (bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fig.bbox.width+1 or bb.y1 > fig.bbox.height+1):
            bad.append(t.get_text())
    QA.setdefault("text_outside_page", {})[stem] = bad
    for ext in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"{stem}.{ext}", dpi=400)
    # A high-resolution projection copy preserves the exact chart geometry.
    fig.savefig(OUT / "presentation" / f"{stem}.png", dpi=500)
    pdf.savefig(fig, dpi=400)
    META.append(dict(stem=stem, title=title_cn, caption_cn=caption_cn,
                     caption_en=caption_en, sources=[str(p.relative_to(ROOT)) for p in sources], role=role,
                     size_inches=list(fig.get_size_inches())))
    assert not bad, (stem, bad)
    plt.close(fig)


def hovmoller(atmos, pdf):
    fig = figbase(5.25, "Air-sea evolution across three strong El Niño events",
                  "OISST / ERA5; 5°S–5°N; 1982–2022 monthly anomalies.\nYear 0 = 1997 / 2015 / 2023; year −1 = preceding year. Dashed line: start of year 0.")
    gs = fig.add_gridspec(2, 4, left=.095, right=.935, bottom=.12, top=.94,
                          width_ratios=[1, 1, 1, .055], wspace=.16, hspace=.30)
    for i, (var, lon, limit, factor, label) in enumerate([
        ("sst_anomaly", "sst_lon", 4., 1., "SSTA (°C)"),
        ("tau_anomaly", "tau_lon", 8., 100., r"Zonal stress anomaly ($10^{-2}$ N m$^{-2}$)")]):
        levels = np.linspace(-limit, limit, 17)
        cm = plt.get_cmap("RdBu_r", 16).copy(); cm.set_bad("#E6E8EB")
        norm = BoundaryNorm(levels, cm.N)
        all_values = []
        for j, e in enumerate(EVENTS):
            ax = fig.add_subplot(gs[i, j])
            q = atmos.sel(time=slice(f"{e-1}-01", f"{e}-12"))
            assert q.sizes["time"] == 24
            vals = q[var].values * factor; all_values.append(vals.ravel())
            mesh = ax.contourf(q[lon], np.arange(24), vals, levels=levels,
                               cmap=cm, norm=norm, extend="both")
            ax.set_xlim(float(q[lon].min()), float(q[lon].max())); ax.set_ylim(23, 0)
            ax.set_xticks([120, 180, 220, 280], ["120°E", "180°", "140°W", "80°W"])
            ax.set_yticks([0, 6, 12, 18, 23], ["Jan (−1)", "Jul (−1)", "Jan (0)", "Jul (0)", "Dec (0)"])
            ax.tick_params(axis="x", labelsize=6.2)
            ax.tick_params(axis="y", labelsize=6.5)
            if j: ax.tick_params(labelleft=False)
            ax.get_xticklabels()[0].set_ha("left")
            ax.get_xticklabels()[-1].set_ha("right")
            ax.axhline(11.5, color=BLACK, ls="--", lw=.65)
            for x in [180, 220]: ax.axvline(x, color="#616972", ls=":", lw=.45, alpha=.6)
            panel(ax, chr(97+i*3+j), f"{e} · " + ("SSTA" if i == 0 else r"$\tau_x$ anomaly"), COLORS[e])
        ca = fig.add_subplot(gs[i, 3])
        cb = fig.colorbar(mesh, cax=ca, ticks=np.linspace(-limit, limit, 5), extend="both")
        cb.set_label(label, fontsize=7, labelpad=5); cb.outline.set_linewidth(.5)
        v = np.concatenate(all_values); v = v[np.isfinite(v)]
        QA.setdefault("color_limits", {})[var] = dict(limit=limit/factor,
            fraction_beyond_limit=float(np.mean(np.abs(v) > limit)), extends=True)
    save(fig, "M1_air_sea_evolution", "海温与风应力的共同演变",
         "三个案例分别显示前一年1月至发展年12月，年0对应各列发展年，年−1为前一年；上排海温、下排向东风应力距平，同行使用相同色标，色标尖端表示范围外值。等值填色沿原格点绘制，无额外平滑或增密重采样。风应力只是月平均距平，正值不等于绝对西风，不能据此识别日尺度西风爆发。垂直虚线标记180°和140°W。三事件对比本身及弱风现象已有文献覆盖，本图提供本项目的统一资料背景，不声称首次发现。",
         "Monthly equatorial SST and zonal wind-stress anomalies for the preceding and development years. Common color limits are used across events. Positive stress anomalies need not imply absolute westerlies; monthly data do not identify daily wind bursts. Anomalies use the 1982–2022 calendar-month climatology. This is a descriptive comparison, not a causal feedback diagnosis.",
         [FILES[0]], "main", pdf)


def initial_configuration(ocean, monthly, quarters, pdf):
    from paper_figure_blocks import plot_jfm
    import sys
    plot_jfm(sys.modules[__name__], ocean, monthly, quarters, pdf)


def evolution(monthly, quarters, pdf):
    fig = figbase(4.95, "Spring-to-summer transport, storage and wind response",
                  "Monthly values are unsmoothed. AMJ = April–June; JAS = July–September. Anomaly baseline: 1982–2022.")
    eventlegend(fig, .965)
    gs = fig.add_gridspec(2, 2, left=.105, right=.94, bottom=.14, top=.87, wspace=.30, hspace=.60)
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]
    for e in EVENTS:
        q = monthly[(monthly.event == e) & (monthly.year == e)].sort_values("month")
        assert q.month.tolist() == list(range(1, 13))
        eventline(axes[0], q.month, q.u220_q_sv, e, markevery=[0,3,6,9,11])
        eventline(axes[1], q.month, q.east_wwv_m3/1e14, e, markevery=[0,3,6,9,11])
        vals = []
        for field in ["u220_q_sv", "tau"]:
            values = np.array([q[q.month.between(a,b)][field].mean() for a,b in [(4,6),(7,9)]])
            check = quarters[(quarters.event == e) & quarters.quarter.isin([2,3])].sort_values("quarter")[field].values
            assert np.allclose(values, check, atol=1e-10)
            vals.append(values)
        eventline(axes[2], [0,1], vals[0], e)
        eventline(axes[3], [0,1], vals[1]*100, e)
    for ax in axes[:2]:
        months(ax)
        ax.axvspan(3.5, 6.5, color="#ECEFF1", zorder=-2)
        ax.axvspan(6.5, 9.5, color="#F6F7F8", zorder=-2)
    axes[0].set_ylabel("Eastward transport anomaly (Sv)")
    axes[1].set_ylabel(r"WWV26 anomaly ($10^{14}$ m$^3$)")
    axes[2].set_ylabel("Eastward transport anomaly (Sv)")
    axes[3].set_ylabel(r"Stress anomaly ($10^{-2}$ N m$^{-2}$)")
    for ax in axes[2:]:
        ax.set_xlim(-.3, 1.3); ax.set_xticks([0,1], ["AMJ", "JAS"]); zero(ax)
    for ax, letter, title in zip(axes, "abcd", ["140°W transport anomaly", "Eastern WWV26 anomaly",
                                              "AMJ/JAS transport anomalies", r"AMJ/JAS west-central $\tau_x$ anomalies"]):
        panel(ax, letter, title)
    save(fig, "M3_transport_persistence", "春夏输入、储量与风响应的阶段差异",
         "a：140°W断面9°S—9°N、海面至瞬时σθ=26面的向东体积输送距平；b：140°W—80°W、9°S—9°N的WWV26距平；c：a的AMJ/JAS均值；d：160°E—140°W、5°S—5°N的向东风应力距平季节均值。所有月值保留，无额外平滑。灰底标记AMJ和JAS，季节平均由原月表重算并与已存季度表核验。断面通过量不等于区域净储量增长，海洋与大气指标的纬带不同；季节对应关系不证明单一因果链。",
         "Monthly eastward WWV26 transport across 140°W and eastern-box WWV26, with AMJ/JAS transport and zonal stress means. Ocean quantities use 9°S–9°N; the wind region is 5°S–5°N, 160°E–140°W. Transport is a boundary throughflow, not net storage change. Lines joining seasonal points show descriptive phase changes, not independent replicates or fitted relationships.",
         [FILES[3], FILES[4]], "main", pdf)


def wind_reference(monthly, pdf):
    fig = figbase(4.9, "Wind-response differences depend on the reference definition",
                  "SST-conditioned reference: calendar month, Niño3.4 and Niño3–Niño4; 34 years, target event blocks excluded.")
    gs = fig.add_gridspec(2,3,left=.095,right=.94,bottom=.13,top=.86,wspace=.18,hspace=.44)
    specs = [("tau", BLACK, "-", "Actual anomaly"),
             ("wind_expected_full_with_trend", PURPLE, "-", "Reference with trend"),
             ("wind_expected_full_no_trend", TEAL, "--", "Reference without trend")]
    fig.legend(handles=[Line2D([],[],color=c,ls=ls,label=lab) for _,c,ls,lab in specs],
               ncol=3,loc="upper center",bbox_to_anchor=(.52,.97),columnspacing=1.3)
    plotaxes = []
    for i in range(2):
        rowaxes=[]
        for j,e in enumerate(EVENTS):
            q=monthly[(monthly.event==e)&(monthly.year==e)]
            ax=fig.add_subplot(gs[i,j],sharey=rowaxes[0] if rowaxes else None);rowaxes.append(ax)
            if i==0:
                for var,c,ls,lab in specs:ax.plot(q.month,q[var]*100,color=c,ls=ls,lw=1.25)
            else:
                ax.plot(q.month,q.wind_z_full_with_trend,color=PURPLE)
                ax.plot(q.month,q.wind_z_full_no_trend,color=TEAL,ls="--")
            months(ax);panel(ax,chr(97+i*3+j),f"{e}: "+("Wind-stress anomaly" if i==0 else "Standardized residual"),COLORS[e])
            if j:ax.tick_params(labelleft=False)
        plotaxes.append(rowaxes)
    plotaxes[0][0].set_ylabel(r"Stress anomaly ($10^{-2}$ N m$^{-2}$)")
    plotaxes[1][0].set_ylabel("Wind residual / reference SD")
    save(fig,"S1_wind_reference","风响应的参考关系与趋势敏感性",
         "上排为实际风应力距平和两种海温条件参考；下排为各自训练残差标准差归一后的偏差。两种参考只区别是否含线性时间项，均按历月拟合并排除1996—1998、2014—2016、2022—2024。未把±1标准差画成显著性阈值，未把风残差当成独立大气强迫。本图保留2023是否低于历史预期对背景处理的敏感性；参考均值的不确定性可查原诊断，不在本图中伪造置信带。",
         "Observed wind-stress anomalies and SST-conditioned reference responses, with and without a linear time term. Residuals are normalized by their respective training residual standard deviations. Excluded years are 1996–1998, 2014–2016 and 2022–2024. No ±1-SD significance threshold is implied, and reference departures are not identified external forcing.",
         [FILES[3]],"support",pdf)


def local_process(robust, local, pdf):
    fig=figbase(5.0,"Local warming: robust ordering and an incomplete budget",
                "Niño3.4: 5°S–5°N, 170°W–120°W. Reference uses 34 non-target years; 1 month = 365.25/12 days.")
    eventlegend(fig,.965)
    gs=fig.add_gridspec(2,2,left=.105,right=.94,bottom=.17,top=.86,hspace=.66,wspace=.28)
    axs=[]
    for j,background in enumerate(["mean","detrend"]):
        ax=fig.add_subplot(gs[0,j]);axs.append(ax)
        for e in EVENTS:
            q=robust[robust.event.eq(e)&robust.background.eq(background)].sort_values("depth_m")
            assert q.depth_m.tolist()==[30,50,75]
            eventline(ax,q.depth_m,q.JAS_zonal_advective_contribution,e)
        zero(ax);ax.set_xticks([30,50,75]);ax.set_xlabel("Layer thickness (m)")
        ax.set_ylim(-.12,.23)
        assert robust.JAS_zonal_advective_contribution.min() > -.12
        assert robust.JAS_zonal_advective_contribution.max() < .23
        panel(ax,"ab"[j],r"JAS $-u'\partial_x\overline{T}$: monthly background" if j==0 else r"JAS $-u'\partial_x\overline{T}$: detrended")
    axs[0].set_ylabel(r"$-u'\,\partial_x\overline{T}$ (°C month$^{-1}$)")
    axs[1].set_ylabel(r"$-u'\,\partial_x\overline{T}$ (°C month$^{-1}$)")
    ax=fig.add_subplot(gs[1,:]);xx=np.arange(4)
    fields=["tendency","horizontal_total","surface_flux_proxy","unresolved"]
    for j,e in enumerate(EVENTS):
        q=local[local.event.eq(e)&local.depth_m.eq(50)&local.quarter.eq(3)].iloc[0]
        yy=q[fields].to_numpy(dtype=float)
        assert np.isclose(yy[0],yy[1:].sum(),atol=1e-10)
        ax.plot(xx+(j-1)*.15,yy,ls="none",marker=MARKERS[e],ms=4.7,color=COLORS[e])
    zero(ax);ax.set_xlim(-.4,3.4)
    ax.set_xticks(xx,["Temperature\ntendency","Total horizontal\nadvection","Surface-flux\nproxy","Unresolved"])
    ax.set_ylabel(r"Contribution (°C month$^{-1}$)")
    panel(ax,"c","JAS, 0–50 m temperature-tendency anomalies")
    save(fig,"S2_local_process_limits","局地平流的稳健排序与未闭合项",
         "a—b：7—9月异常纬向流作用于背景温度梯度的增暖贡献，比较30/50/75m固定层厚及过程去趋势处理。两种背景均保持2023低于1997和2015，但其正负号并不稳健。六种设置不是六个独立样本。c：50m层、未额外去过程趋势的JAS温度倾向、完整水平平流距平、海表通量代理和未解析项。未解析项与净增暖同量级，不能称为完整热收支，也不能命名为垂向平流或混合。海表项未扣除穿透层底短波；其冷却弱于另外两例。这里使用34年非目标窗口背景，区别于主图1982—2022背景。",
         "JAS anomalous zonal advection under three fixed layer thicknesses and two background treatments. The case ranking is stable, but the 2023 sign is background-sensitive. The six settings are not independent samples. The lower panel retains the large unresolved tendency; the surface-flux proxy lacks a penetrating-shortwave correction. Background statistics use 34 years excluding target event blocks, unlike the main figures' 1982–2022 climatology.",
         [FILES[7],FILES[8]],"support",pdf)


def attribution_limits(replay, budgets, pdf):
    fig=figbase(5.1,"Full-sample sLIM replay and eastern volume budgets",
                "Fit: all 516 months, 1982–2024, target events included. One fixed operator; in-sample diagnostic replay.")
    gs=fig.add_gridspec(2,3,left=.095,right=.94,bottom=.16,top=.86,hspace=.55,wspace=.18)
    handles=[Line2D([],[],color=BLACK,label="Observed SST"),
             Line2D([],[],color=GRAY,ls="--",label="Free sLIM"),
             Line2D([],[],color=PURPLE,label="Observed-ocean replay")]
    fig.legend(handles=handles,loc="upper center",bbox_to_anchor=(.52,.915),ncol=3,columnspacing=1.6)
    top=[];bottom=[]
    for j,e in enumerate(EVENTS):
        q=replay[replay.key.eq(REPLAY_KEY)&replay.year.eq(e)&replay.variable.eq("nino34")]
        obs=q[q.experiment.eq("free")].sort_values("month")
        ax=fig.add_subplot(gs[0,j],sharey=top[0] if top else None);top.append(ax)
        ax.plot(obs.month,obs.observed,color=BLACK,lw=1.4)
        ax.plot(obs.month,obs.predicted,color=GRAY,ls="--")
        rr=q[q.experiment.eq("observed_ocean_replay")].sort_values("month")
        ax.plot(rr.month,rr.predicted,color=PURPLE)
        months(ax);panel(ax,chr(97+j),str(e),COLORS[e])
        if j:ax.tick_params(labelleft=False)
        q=budgets[budgets.event.eq(e)&budgets.region.eq("east")&budgets.baseline.eq("monthly_mean")]
        windows=["0115_to_0415","0415_to_0715","0715_to_1015"]
        q=q.set_index("window").loc[windows]
        ax=fig.add_subplot(gs[1,j],sharey=bottom[0] if bottom else None);bottom.append(ax)
        xx=np.arange(3)
        for shift,values,color,label in [(-.24,q.storage_change,BLACK,"Storage change"),
            (0,q.zonal_input+q.meridional_input,"#87919B","Horizontal input"),
            (.24,q.unresolved,"#D5D9DD","Unresolved")]:
            ax.bar(xx+shift,values,width=.22,color=color,edgecolor="#65707A",linewidth=.35,label=label)
        assert np.allclose(q.storage_change,q.zonal_input+q.meridional_input+q.unresolved,atol=1e-10)
        zero(ax);ax.set_xticks(xx,["Jan–Apr","Apr–Jul","Jul–Oct"],rotation=25,ha="right")
        ax.tick_params(axis="x",labelsize=6.5)
        panel(ax,chr(100+j),f"{e}: eastern budget",COLORS[e])
        if j:ax.tick_params(labelleft=False)
    top[0].set_ylabel("Niño3.4 anomaly (°C)")
    bottom[0].set_ylabel(r"Volume change ($10^{14}$ m$^3$)")
    hh,ll=bottom[0].get_legend_handles_labels()
    fig.legend(hh,ll,loc="center",bbox_to_anchor=(.52,.08),ncol=3,fontsize=6.5,columnspacing=1.3)
    save(fig,"S3_attribution_limits","全样本拟合下的海洋状态重放与体积收支",
         "上排按用户指定方案，将1982—2024全部43年516个月（含三个目标事件及邻年）用于气候态、趋势、标准差和四状态sLIM算子的估计。拟合一次后固定参数，比较1月初态自由演化、逐月替换实际三区WWV26但保留模型海温的诊断重放与OISST观测。展示距平仍为1982—2022背景。这是样本内诊断重放，不能当作事件留出或独立实时预报；统计状态替换也不等于物理干预。旧留出版仅保留为历史对照。下排体积收支沿用原诊断，分别为1月15日至4月15日、4月15日至7月15日、7月15日至10月15日，保留水平净输入和未解析项；未解析体积项不是已识别的热损失过程。",
         "The same four-state sLIM is fitted to all 516 months of 1982–2024, including the target events and neighboring years. Full-sample climatology, linear trends and scales are estimated before fitting. The operator is then held fixed for January-initialized free runs and monthly observed-ocean replay with model SST retained. Display anomalies use the 1982–2022 climatology. This is in-sample diagnostic conditioning, not independent forecasting or a physical intervention. Eastern-box volume budgets are unchanged and retain unresolved terms; intervals are 15 January–15 April, 15 April–15 July and 15 July–15 October.",
         [FILES[5],FILES[6]],"support",pdf)


REFERENCES = [
    ("Peng et al. (2025), Nature Geoscience", "https://www.nature.com/articles/s41561-025-01700-9",
     "海洋动力驱动强增暖、太平洋风响应偏弱，以及外海盆/背景增暖影响已经有模式与热收支证据。", "弱风与强海温是背景事实；我们的描述性诊断不能替代其强迫实验。"),
    ("Lin et al. (2025), npj Climate and Atmospheric Science", "https://www.nature.com/articles/s41612-025-01013-z",
     "同样比较1997、2015、2023；研究NPMM、MJO、西风爆发与Kelvin波。", "三事件选择、暖水储备大却未形成极端事件，均不能单独作为创新。"),
    ("Geng et al. (2024), Communications Earth & Environment", "https://www.nature.com/articles/s43247-024-01870-1",
     "解释2023双峰结构与东太平洋秋季停止增暖，涉及异常向西流及纬向平流冷却。", "局地平流差异已有直接先例；须区分其东太平洋ASON区域与本项目Niño3.4 JAS。"),
    ("Li, Zheng & Zhang (2026), Geoscience Letters", "https://link.springer.com/article/10.1186/s40562-026-00474-1",
     "2026年4月22日发表；比较2015与2023夏秋增暖率转换，诊断离赤道风、经向输送与纬向流反馈。", "与我们的输送—增暖过程高度邻近。现有春夏诊断不是该文秋季机制的独立因果证明。"),
    ("Fan et al. (2026), The Innovation Geoscience", "https://www.the-innovation.org/article/doi/10.59717/j.xinn-geo.2026.100224",
     "2026年4月20日在线；从多年La Niña后西太平洋暖水积累、次表层温度梯度和非线性冷却解释后续弱风响应。", "前期海洋配置影响弱风的大框架也已有研究。此处核验了期刊摘要与公开概述，不宣称完成全文复现。"),
    ("Kim, Tian & Yu (2025), npj Climate and Atmospheric Science", "https://www.nature.com/articles/s41612-024-00890-0",
     "研究多年La Niña之后持续东风对2023发展过程的限制。", "春夏弱风本身已经是已知问题，应强调本项目同口径过程比较。"),
    ("Chen et al. (2015), Journal of Climate", "https://doi.org/10.1175/JCLI-D-14-00134.1",
     "研究副热带环流与ENSO充放电，为密度层暖水储备和9°S/9°N输送提供方法背景。", "WWV26须与20°C等温面WWV、D20及固定层热含量分开；定义替换不是创新证明。"),
]


def gallery():
    cards=[]
    for m in META:
        stem=m['stem']
        links=' · '.join(f'<a href="{stem}.{ext}">{ext.upper()}</a>' for ext in ['png','pdf','svg'])
        links+=f' · <a href="presentation/{stem}.png">投影高分辨率PNG</a>'
        cards.append(f'''<article id="{stem}"><div class="tag">{'主图' if m['role']=='main' else '备份图'} · {stem.split('_')[0]}</div>
<h2>{html.escape(m['title'])}</h2><p>{links}</p><a href="{stem}.png"><img src="{stem}.png" alt="{html.escape(m['title'])}"></a>
<p class="caption">{html.escape(m['caption_cn'])}</p><details><summary>英文图注与数据来源</summary><p>{html.escape(m['caption_en'])}</p><ul>'''+''.join(f'<li><a href="../../../{p}">{html.escape(p)}</a></li>' for p in m['sources'])+'</ul></details></article>')
    refs=''.join(f'<tr><td><a href="{u}">{html.escape(n)}</a></td><td>{html.escape(found)}</td><td>{html.escape(limit)}</td></tr>' for n,u,found,limit in REFERENCES)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>三事件研究汇报 · 文献定位与图件</title><style>
body{font-family:Arial,"PingFang SC",sans-serif;margin:0;background:#f5f6f7;color:#24313b;line-height:1.75}main{max-width:1060px;margin:auto;padding:44px 28px}h1{font-size:30px;line-height:1.4;margin:12px 0}h2{font-size:22px}p{max-width:940px}a{color:#006b9f;text-underline-offset:3px}nav{display:flex;gap:18px;flex-wrap:wrap;margin:24px 0}.lead{font-size:18px}.box,article{background:white;padding:26px 30px;margin:24px 0;border:1px solid #dce2e6;border-radius:8px}.tag{color:#687580;font-size:13px;letter-spacing:1px}img{width:100%;height:auto;margin-top:12px}.caption{font-size:15px}table{border-collapse:collapse;font-size:14px}td,th{padding:13px 12px;border-bottom:1px solid #dce2e6;text-align:left;vertical-align:top}td:first-child{width:24%}details{font-size:13px;color:#53616c;overflow-wrap:anywhere}summary{cursor:pointer}footer{color:#687580;font-size:13px} @media(max-width:600px){main{padding:22px 12px}.box,article{padding:18px}h1{font-size:25px}table{font-size:12px}td,th{padding:8px 5px}}
</style><main><div class="tag">MARYLAND · 15 OCTOBER 2026 · FIGURE SET</div>
<h1>三次强厄尔尼诺：暖水配置、输送持续性与海气响应</h1>
<p class="lead"><b>核心结果：2023夏季140°W输送差主要来自纬向流变化；局地完整水平平流差异中，50m主设置的经向净贡献更大。较弱的向东风动量输入对应纬向流差异。</b></p>
<p>本套图保留一个研究问题、三个案例，整理为五张主图和两张备份图。当前版本按论文终图排版：小图标题注明异常量，M2为JFM平均，M2/M4采用水平场与垂向剖面的立体组合，长方法说明置于图注。末组为<b>M4：输送的流速来源与局地经纬向平流贡献</b>、<b>M5：风输入与纬向流的动力联系</b>，各组顺序保持。新增诊断统一使用1982—2024全部43年背景。</p>
<nav><a href="#M1_air_sea_evolution">主图1</a><a href="#M2_JFM_configuration">主图2</a><a href="#M3_transport_persistence">主图3</a><a href="#S1_wind_reference">备份图</a><a href="#M4_transport_current_advection">主图4：流速来源</a><a href="#M5_wind_current_momentum">主图5：风与流</a><a href="three_event_figure_book.pdf">完整7图PDF</a><a href="figure_captions.txt">中英文图注</a><a href="figure_data.zip">源图数据包</a><a href="#literature">文献定位</a></nav>
<section class="box" id="literature"><h2>文献核对后的取舍</h2>
<p>2023暖水储备大但风响应弱、NPMM与西风爆发不同、纬向平流及离赤道风影响增暖，均已有直接研究。尤其2026年的Li等和Fan等论文进一步压缩了宽泛机制叙事的新意空间。</p>
<p><b>本次汇报的具体结果：</b>140°W输送差精确分为流速与暖水层厚度贡献，最大单层流速贡献位于上层50m。完整温度平流进一步分开经、纬向及各自的温度结构、异常流和非线性交互项：JAS主设置中，2023相对1997/2015的纬向净差为−0.052/−0.054，经向净差为−0.145/−0.131°C/标准月。异常纬向流项的负差被非线性交互部分抵消，不能将整个局地水平平流差异等同于这一单项。</p>
<p>建议表述：“2023夏季较弱的140°W暖水输送主要对应纬向流变化；局地水平平流增暖差异则同时涉及经、纬向过程，50m主设置中经向净项贡献更大。较弱的向东风动量输入为纬向流差异提供动力解释线索。”经向净差在全部六设置中均低于两个对照；风与纬向动量诊断不直接解释经向差异。</p>
<table><thead><tr><th>相关工作</th><th>已覆盖的内容</th><th>对本项目的约束</th></tr></thead><tbody>'''+refs+'''</tbody></table></section>
<section class="box"><h2>绘图与使用口径</h2><p>主图1讲现象；主图2讲JFM储备、水平位置与垂向温度结构；主图3讲春夏持续性；主图4分开解释输送的流速来源与局地完整经纬向平流差异，主图5展示风动量输入、受力分项与累计纬向流速变化。备份S1、S2保留原背景的趋势和局地过程检查。事件颜色固定为蓝/赭黄/朱红，并配圆/方/三角点形；可比面板共享色标。</p>
<p>常规图宽183mm，M4按三面组合加宽至264mm；Arial字体，矢量PDF/SVG与400dpi PNG并存，投影副本500dpi。图内保留黑色的小图标题、坐标单位、图例和必要层界；区域、背景及完整方法置于图注。遵循<a href="https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/">Nature科研绘图指南</a>关于可读字体、颜色可及性、坐标单位和可编辑矢量的原则；最终投稿仍按目标期刊规格调整。</p>
<p>M1—M3沿用1982—2022显示背景；S1、S2保留原34年非目标背景；M4—M5使用1982—2024全部43年，目标年纳入。新旧背景差异单独核对，旧图绝对距平不直接与新图混排。当前平流结论见<a href="../three_event_directional_advection_20261015/index.html">完整经纬向平流补充报告</a>；输送和纬向受力详见<a href="../three_event_summer_current_dynamics_20261015/index.html">原纬向流专项诊断（历史结果）</a>，其中针对单个异常纬向流项的解释不再代表完整水平平流。</p>
<details><summary>历史模型图与替换实验</summary><p>原末组<a href="S3_attribution_limits.pdf">S3海洋状态重放与体积收支</a>保留为历史图件，不再进入当前图册。对应的<a href="../three_event_fullsample_replay_20261015/index.html">全样本重放</a>与<a href="../three_event_ocean_trajectory_swaps_20261015/index.html">三事件海洋轨迹互换</a>仍可查阅。</p></details></section>'''+''.join(cards)+'''
<footer>仅更新末组：scripts/update_three_event_mechanism_figures.py；全图重绘：scripts/build_three_event_scientific_figures.py。当前图册7页，含5张主图及2张备份图。图注、输入哈希及检查记录见figure_manifest.json、input_manifest.json、validation.json。</footer></main></html>'''
    (OUT/'index.html').write_text(page,encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True);(OUT/'presentation').mkdir(exist_ok=True);(OUT/'source_data').mkdir(exist_ok=True)
    before={str(p.relative_to(ROOT)):sha(p) for p in FILES}
    style()
    monthly=pd.read_csv(FILES[3]);quarters=pd.read_csv(FILES[4]);jan=pd.read_csv(FILES[2])
    replay=pd.read_csv(FILES[5]);budgets=pd.read_csv(FILES[6]);local=pd.read_csv(FILES[7]);robust=pd.read_csv(FILES[8])
    with xr.open_dataset(FILES[0],engine='scipy') as a, xr.open_dataset(FILES[1],engine='scipy') as o:
        with PdfPages(OUT/'three_event_figure_book.pdf') as pdf:
            hovmoller(a,pdf);initial_configuration(o,monthly,quarters,pdf);evolution(monthly,quarters,pdf)
            wind_reference(monthly,pdf);local_process(robust,local,pdf)
            import sys
            from update_three_event_mechanism_figures import render_figures
            render_figures(sys.modules[__name__], pdf)
        # Exact figure fields, no interpolated/smoothed replacements.
        dates=np.concatenate([np.arange(np.datetime64(f'{e-1}-01'),np.datetime64(f'{e+1}-01'),dtype='datetime64[M]') for e in EVENTS])
        years={int(str(d)[:4]) for d in dates}
        a.sel(time=a.time.dt.year.isin(sorted(years))).to_netcdf(OUT/'source_data/airsea_fields.nc',engine='scipy')
        o.sel(time=o.time.dt.month.isin([1,2,3])).to_netcdf(OUT/'source_data/JFM_monthly_ocean_fields.nc',engine='scipy')
    for frame,name in [(monthly,'monthly_diagnostics'),(quarters,'seasonal_diagnostics'),(jan,'january_WWV26'),
                       (replay,'fixed_model_replay'),(budgets,'volume_budgets'),(local,'local_quarter_tendencies'),(robust,'advection_sensitivity')]:
        frame.to_csv(OUT/'source_data'/f'{name}.csv',index=False)
    after={str(p.relative_to(ROOT)):sha(p) for p in FILES}
    assert before==after
    QA['source_hashes_unchanged']=True
    QA['basin_equals_sum_of_regions']=True
    QA['seasonal_means_match_saved_quarter_table']=True
    QA['budget_arithmetic_checked']=True
    QA['paper_final']=True
    QA['current_section_validation']=json.loads((OUT/'source_data/JAS_current_vertical_sections_QA.json').read_text())
    QA['figures']=len(META)
    QA['case_count']=3
    QA['inference']='descriptive case comparison; no new significance tests or causal claims'
    (OUT/'input_manifest.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    (OUT/'figure_manifest.json').write_text(json.dumps(META,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'validation.json').write_text(json.dumps(QA,ensure_ascii=False,indent=2),encoding='utf-8')
    import zipfile
    with zipfile.ZipFile(OUT/'figure_data.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted((OUT/'source_data').iterdir()):z.write(p,'source_data/'+p.name)
        z.write(OUT/'input_manifest.json','input_manifest.json')
        z.write(Path(__file__),'build_three_event_scientific_figures.py')
    gallery()
    from update_three_event_mechanism_figures import DYN, DATA, DIRECTIONAL
    before.update({str((DYN/n).relative_to(ROOT)):sha(DYN/n) for n in DATA})
    before.update(QA['current_section_validation']['source_sha256'])
    before.update(QA['M4_140W_section']['source_sha256'])
    before.update(json.loads((DIRECTIONAL/'input_manifest.json').read_text()))
    before.update({str(p.relative_to(ROOT)):sha(p) for p in DIRECTIONAL.iterdir()
                   if p.suffix in ['.csv','.nc','.json','.txt']})
    from paper_figure_blocks import CHEN_PAPER
    before[str(CHEN_PAPER.relative_to(ROOT))]=sha(CHEN_PAPER)
    (OUT/'input_manifest.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    import subprocess
    bundled='/Users/daiyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
    subprocess.run([bundled,str(ROOT/'scripts/package_three_event_figure_gallery.py')],check=True)
    print(json.dumps(QA,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
