"""Reproducible seasonal comparisons with four publicly displayed IRI models.

The IRI archive currently exposes vector plumes rather than a numeric download.
Read affine axis coordinates and match each curve to its exact legend signature
(stroke plus marker reference). Never estimate values from raster screenshots.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/iri_plumes_2015_2026_20261014'
OUT = ROOT / 'outputs/research_2026/IRI_RO_PMM_2015_2026_20261014'
BASE = ROOT / 'outputs/research_2026'
OLD = BASE / 'slim_RO_PMM_2015_manuscript_style_20261014'
NEW = BASE / 'slim_RO_PMM_2026_manuscript_style_20261014'
MODELS = ['NCEP CFSv2', 'NASA GMAO', 'CMC CANSIP', 'JMA']
NS = {'s': 'http://www.w3.org/2000/svg'}
XLINK = '{http://www.w3.org/1999/xlink}href'
INITIALS = 'JFMAMJJASOND'


def comments(node):
    return [e.text.strip() for e in node.iter() if e.tag is ET.Comment]


def attributes(style):
    return dict(p.strip().split(':', 1) for p in style.split(';') if ':' in p)


def signature(node):
    path = node.find('s:path', NS)
    if path is None:
        return None
    s = {k: v.strip() for k, v in attributes(path.get('style', '')).items()}
    uses = node.findall('.//s:use', NS)
    return (s.get('stroke'), s.get('stroke-width', '1'), s.get('stroke-dasharray'),
            uses[0].get(XLINK) if uses else None)


def vertices(node):
    d = node.find('s:path', NS).get('d')
    assert not re.search('[ACHQSTVZachqstvz]', d), d
    values = re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', d)
    return np.asarray(values, dtype=float).reshape(-1, 2)


def season(center):
    return ''.join(INITIALS[(center.month + delta - 1) % 12] for delta in [-1, 0, 1])


def extract(path, year, month):
    root = ET.parse(path, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))).getroot()
    ax = next(e for e in root.iter() if e.get('id') == 'axes_1')
    x_ticks, y_ticks = [], []
    for el in ax.iter():
        eid = el.get('id', '')
        if eid.startswith(('xtick_', 'ytick_')):
            label = comments(el)[0]
            mark = el.find('.//s:use', NS)
            if eid.startswith('xtick_'):
                x_ticks.append((float(mark.get('x')), label))
            else:
                y_ticks.append((float(mark.get('y')), float(label.replace('−', '-'))))
    assert len(x_ticks) == 12
    calibration = np.polyfit(np.array(y_ticks)[:, 0], np.array(y_ticks)[:, 1], 1)
    tick_error = abs(np.polyval(calibration, np.array(y_ticks)[:, 0]) - np.array(y_ticks)[:, 1]).max()
    assert tick_error < 1e-10
    legend = ax.find("s:g[@id='legend_1']", NS)
    named = {}; pending = None; category = None
    for ch in legend:
        if ch.get('id', '').startswith('line2d_'):
            pending = signature(ch)
        elif ch.get('id', '').startswith('text_'):
            label = comments(ch)[0]
            if label == 'DYN MODELS:': category = 'Dynamical'
            if label == 'STAT MODELS:': category = 'Statistical'
            if pending is not None:
                named[label] = (pending, category)
            pending = None
    rows, audit = [], []
    init = pd.Timestamp(year, month, 1)
    axis_lines = [ch for ch in ax if ch.get('id', '').startswith('line2d_')]
    assert any(f'from {init:%b %Y}' in label for label in comments(ax))
    model_names = [name for name, (_, cat) in named.items()
                   if cat in ['Dynamical', 'Statistical']
                   and name not in ['', 'DYN MODELS:', 'STAT MODELS:', 'DYN Average', 'STAT Average']]
    drawn = [ch for ch in axis_lines if signature(ch)[1] == '1'
             and len(vertices(ch)) > 2 and abs(vertices(ch)[0, 0] - x_ticks[3][0]) < 1e-5]
    assert len(drawn) == len(model_names)
    assert [signature(ch) for ch in drawn] == [named[name][0] for name in model_names]
    for model in MODELS:
        source_name = 'NASA GMAOv3' if model == 'NASA GMAO' and 'NASA GMAOv3' in named else model
        sig, category = named[source_name]
        assert category == 'Dynamical'
        matches = [ch for ch in axis_lines if signature(ch) == sig]
        # The renderer cycles its style palette. Repeated signatures retain the
        # same within-signature order in plotted artists and legend handles.
        same_style_names = [name for name, (key, _) in named.items() if key == sig]
        assert len(matches) == len(same_style_names), (path, model, len(matches), same_style_names)
        ordinal = same_style_names.index(source_name)
        line = matches[ordinal]
        assert line is drawn[model_names.index(source_name)]
        points = vertices(line)
        uses = line.findall('.//s:use', NS)
        if uses:
            marker_xy = np.array([[float(u.get('x')), float(u.get('y'))] for u in uses])
            np.testing.assert_allclose(marker_xy, points, atol=1e-6)
        # Sub-pixel vector coordinates permit accurate inversion; retain provenance.
        for x, y in points:
            i = int(np.argmin([abs(x - tick[0]) for tick in x_ticks]))
            assert abs(x - x_ticks[i][0]) < 1e-5 and i >= 3
            center = init + pd.DateOffset(months=i - 2)
            assert season(center) == x_ticks[i][1], (center, x_ticks[i][1])
            value = float(np.polyval(calibration, y))
            assert -5 < value < 6
            rows.append(dict(year=year, issue_month=month, init=init, iri_model=model,
                             center=center, season=season(center), lead_center=i - 2,
                             IRI=value, source_model_name=source_name,
                             source_svg=path.name, source_line=line.get('id'),
                             svg_x=x, svg_y=y))
        audit.append(dict(source=path.name, model=model, source_model_name=source_name,
                          line=line.get('id'), n=len(points),
                          legend_signature=list(sig), marker_checked=bool(uses),
                          same_style_names=same_style_names, within_style_ordinal=ordinal,
                          axis_calibration_max_error=float(tick_error)))
    return rows, audit


def load_and_match():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, audit = [], []
    for year in [2015, 2026]:
        for month in range(2, 7):
            r, a = extract(RAW / f'iri_plume_{year}_{month:02}.svg', year, month)
            rows.extend(r); audit.extend(a)
    iri = pd.DataFrame(rows)
    assert not iri.duplicated(['year', 'issue_month', 'iri_model', 'center']).any()
    iri.to_csv(OUT / 'iri_values_from_official_vector_plumes.csv', index=False)
    (OUT / 'vector_extraction_QA.json').write_text(json.dumps(audit, indent=2))
    print(iri.groupby(['year', 'iri_model', 'issue_month']).size().unstack().to_string(), flush=True)
    raw = pd.read_csv(NEW / 'observed_raw_indices.csv', index_col=0, parse_dates=True).Nino34
    climatology = raw.loc['1991':'2020'].groupby(raw.loc['1991':'2020'].index.month).mean()
    assert len(climatology) == 12
    # Restore the removed trend first (raw_T is absolute SST), then use physical SSTA.
    # This avoids directly comparing IRI SSTA to detrended sLIM state coordinates.
    observed = raw - climatology.reindex(raw.index.month).to_numpy()
    seasonal_obs = observed.rolling(3, center=True, min_periods=3).mean()
    forecast_rows = []
    for year, folder, protocol in [(2015, OLD, 'paper_2002_2024'),
                                    (2026, NEW, 'consistent_reconstruction')]:
        f = pd.read_csv(folder / f'forecasts_{year}.csv', parse_dates=['init', 'target'])
        f = f[f.protocol.eq(protocol) & f.model.isin(['RO', 'RO_SST']) & f.month.between(2, 6)]
        for (model, init), g in f.groupby(['model', 'init']):
            g = g.sort_values('lead')
            assert list(g.lead) == list(range(10))
            anomaly = pd.Series(g.raw_T.values - climatology.reindex(g.target.dt.month).values,
                                index=pd.DatetimeIndex(g.target))
            smooth = anomaly.rolling(3, center=True, min_periods=3).mean().dropna()
            for center, value in smooth.items():
                forecast_rows.append(dict(year=year, issue_month=init.month, init=init, center=center,
                                          method=model, value=value, observed=seasonal_obs.get(center, np.nan)))
    ro = pd.DataFrame(forecast_rows)
    ro.to_csv(OUT / 'RO_PMM_seasonal_full_trajectories.csv', index=False)
    paircols = ['year', 'issue_month', 'init', 'center']
    ro_wide = ro.pivot(index=paircols, columns='method', values='value').reset_index()
    iri_wide = iri.pivot(index=paircols, columns='iri_model', values='IRI').reset_index()
    matched = ro_wide.merge(iri_wide, on=paircols, how='inner').dropna(subset=['RO', 'RO_SST'] + MODELS)
    matched['observed'] = seasonal_obs.reindex(matched.center).values
    matched['season'] = matched.center.map(season)
    matched['season_start'] = matched.center - pd.DateOffset(months=1)
    matched['season_end'] = matched.center + pd.DateOffset(months=1)
    matched['lead_center'] = (matched.center.dt.year - matched.init.dt.year) * 12 + matched.center.dt.month - matched.init.dt.month
    matched['verified'] = matched.observed.notna()
    # Every column uses the same issue/target mask, including all four IRI models.
    assert matched.lead_center.between(1, 8).all()
    assert matched.loc[matched.year.eq(2026) & matched.verified, 'season_end'].max() <= raw.dropna().index.max()
    matched.to_csv(OUT / 'common_seasonal_forecasts.csv', index=False)
    pd.DataFrame({'monthly_1991_2020': observed, 'seasonal_1991_2020': seasonal_obs}).to_csv(OUT / 'observations.csv', index_label='time')
    climatology.to_csv(OUT / 'observed_climatology_1991_2020.csv', index_label='month')
    scores = []
    # This is an as-published anomaly comparison: IRI provider baselines remain mixed.
    # Do not fit an offset to either verification event to improve a model's score.
    for year, group in matched[matched.verified].groupby('year'):
        for method in ['RO', 'RO_SST'] + MODELS:
            error = group[method] - group.observed
            scores.append(dict(year=year, model=method, n=len(group),
                               r=group[method].corr(group.observed),
                               RMSE=np.sqrt(np.mean(error**2)), bias=error.mean(),
                               target_first=str(group.center.min().date()),
                               target_last=str(group.center.max().date())))
    scores = pd.DataFrame(scores)
    scores.to_csv(OUT / 'seasonal_skill_common_pairs.csv', index=False)
    # Uniform offset sensitivity only, not a confidence interval or bias correction.
    sensitivity = []
    for year, group in matched[matched.verified].groupby('year'):
        for method in MODELS:
            for offset in [-.25, 0, .25]:
                err = group[method] + offset - group.observed
                sensitivity.append(dict(year=year, model=method, IRI_offset_degC=offset,
                                        RMSE=np.sqrt(np.mean(err**2))))
    pd.DataFrame(sensitivity).to_csv(OUT / 'IRI_uniform_offset_sensitivity.csv', index=False)
    print(scores.to_string(index=False), flush=True)
    return matched, scores, seasonal_obs, iri


def render(matched, scores, observed, iri):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/iri_comparison_mpl'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MultipleLocator
    from matplotlib.backends.backend_pdf import PdfPages
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 13, 'axes.titleweight': 'bold', 'axes.labelsize': 11,
                         'axes.linewidth': 1, 'xtick.direction': 'in', 'ytick.direction': 'in',
                         'xtick.top': True, 'ytick.right': True, 'svg.fonttype': 'none',
                         'pdf.fonttype': 42, 'savefig.facecolor': 'white'})
    full = pd.read_csv(OUT / 'RO_PMM_seasonal_full_trajectories.csv', parse_dates=['init', 'center'])
    displayed_obs = pd.concat([observed.loc[f'{y}-01-01':f'{y+1}-03-01'] for y in [2015, 2026]])
    values = np.r_[full.value, iri.IRI, displayed_obs.dropna()]
    ylim = (.5 * np.floor((values.min() - .15) / .5), .5 * np.ceil((values.max() + .2) / .5))
    colors = {'RO': '#999999', 'RO_SST': '#DC7D69', 'IRI': '#387DAB'}
    labels = {'NCEP CFSv2': 'NCEP\nCFSv2', 'NASA GMAO': 'NASA\nGMAO',
              'CMC CANSIP': 'CMC\nCanSIPS', 'JMA': 'JMA'}
    file_map = []
    with PdfPages(OUT / 'IRI_RO_PMM_all_8_figures.pdf') as book:
        for year in [2015, 2026]:
            for model in MODELS:
                score = scores[scores.year.eq(year)].set_index('model').loc[['RO', 'RO_SST', model]]
                n = int(score.n.iloc[0])
                assert score.n.eq(n).all()
                fig = plt.figure(figsize=(14, 6))
                gs = fig.add_gridspec(1, 2, left=.065, right=.975, top=.79, bottom=.315,
                                     width_ratios=[4.4, 1.2], wspace=.27)
                ax = fig.add_subplot(gs[0, 0]); skill = fig.add_subplot(gs[0, 1])
                dates = pd.to_datetime([f'{year}-01-01', f'{year}-04-01', f'{year}-07-01',
                                        f'{year}-10-01', f'{year+1}-01-01', f'{year+1}-04-01'])
                obs = observed.loc[dates[0]:dates[-1] - pd.offsets.MonthBegin(1)].dropna()
                if year == 2026:
                    # Three-month JAS is plotted at August; ASO is still incomplete.
                    boundary = obs.index[-1] + pd.Timedelta(days=15)
                    ax.axvspan(boundary, dates[-1], color='.95', zorder=0)
                    ax.axvline(boundary, color='.65', lw=.65, ls=':')
                    ax.text(.98, .96, 'Unverified seasons', ha='right', va='top',
                            transform=ax.transAxes, color='.45', fontsize=9)
                ax.plot(obs.index, obs.values, color='#171717', lw=2.5, zorder=6)
                for method, ls in [('RO', '--'), ('RO_SST', '-')]:
                    for _, g in full[full.year.eq(year) & full.method.eq(method)].groupby('issue_month'):
                        ax.plot(g.center, g.value, c=colors[method], ls=ls,
                                lw=1.1 if method == 'RO' else 1.5, alpha=.9, zorder=3)
                for month, g in iri[iri.year.eq(year) & iri.iri_model.eq(model)].groupby('issue_month'):
                    ax.plot(g.center, g.IRI, color=colors['IRI'], lw=1.45, alpha=.9,
                            marker='o', ms=2.5, zorder=4)
                    ax.scatter(g.center.iloc[0], g.IRI.iloc[0], s=22, facecolors='white',
                               edgecolors=colors['IRI'], linewidths=.9, zorder=7)
                ax.axhline(0, color='.3', lw=.75)
                for level in [-.5, .5]: ax.axhline(level, color='.4', ls='--', lw=.7)
                ax.axvline(dates[-2], color=colors['RO_SST'], ls='--', lw=.9, alpha=.8)
                ax.set(xlim=(dates[0], dates[-1]), ylim=ylim, ylabel='Seasonal Niño3.4 SSTA (°C)')
                ax.set_xticks(dates, [f'Jan\n{year}', 'Apr', 'Jul', 'Oct', f'Jan\n{year+1}', 'Apr'])
                ax.yaxis.set_major_locator(MultipleLocator(.5))
                ax.set_title('(a)  Observed and Predicted Niño3.4 Index', pad=10)
                handles = [Line2D([], [], color='#171717', lw=2.3, label='Observed'),
                           Line2D([], [], color=colors['RO'], ls='--', lw=1.2, label='RO'),
                           Line2D([], [], color=colors['RO_SST'], lw=1.6, label='RO + PMM'),
                           Line2D([], [], color=colors['IRI'], marker='o', ms=3, lw=1.5, label=f'IRI: {model}')]
                ax.legend(handles=handles, loc='upper left', frameon=False, fontsize=9)
                skill.bar(range(3), score.r, width=.57,
                          color=[colors['RO'], colors['RO_SST'], colors['IRI']], edgecolor='.3', lw=.8)
                for x, value in enumerate(score.r):
                    skill.text(x, value + .035, f'{value:.2f}', ha='center', va='bottom', fontsize=10)
                skill.axhline(0, color='.4', lw=.7)
                skill.yaxis.set_major_locator(MultipleLocator(.5))
                skill.set(xlim=(-.65, 2.65), ylim=(-.78, 1.12), ylabel='Correlation coefficient',
                          xticks=[0, 1, 2], xticklabels=['RO', 'RO +\nPMM', labels[model]])
                skill.set_title(f'(b)  Prediction Skill\n({year}; n = {n})', pad=10)
                skill.text(.04, .23, 'RMSE (°C)', transform=skill.transAxes, fontsize=9)
                for x, value in enumerate(score.RMSE):
                    skill.text(x, -.49, f'{value:.2f}', ha='center', va='center', fontsize=10)
                skill.tick_params(axis='x', labelsize=9)
                fig.suptitle(f'{year} El Niño: RO, RO + PMM and {model}', fontsize=16.5,
                             fontweight='bold', y=.97)
                fitting = 'retrospective fit includes 2015' if year == 2015 else '2026 excluded from parameter fitting'
                fig.text(.5, .906, f'Fit: 2002–2024 | {fitting}', color='#9B4335', fontsize=11, ha='center')
                pmm = 'official MCA SST index' if year == 2015 else 'fixed-mode ERSSTv5 SST reconstruction'
                extra = ' NASA: GMAOv3 in May–Jun 2026.' if year == 2026 and model == 'NASA GMAO' else ''
                fig.text(.065, .035,
                         'All curves are three-month means, plotted at the central month; February–June issues / monthly-state initializations.\n'
                         f'Skill uses the same {n} observed issue–season pairs across all six methods (center leads 1–5 months); longer curves are shown but not scored.\n'
                         'RO / observations: ERSSTv5 SSTA relative to 1991–2020, with the removed trend restored. IRI: published provider baselines, not harmonized.\n'
                         'RO uses completed monthly initial states; IRI is issued during the month. These are event comparisons, not equal-information real-time tests.\n'
                         f'PMM: {pmm}. IRI: values read from official vector plumes (CC BY 4.0).{extra}',
                         fontsize=8.3, linespacing=1.5)
                stem = f'IRI_{model.replace(" ", "_")}_{year}_RO_PMM'
                for ext in ['png', 'svg', 'pdf']:
                    fig.savefig(OUT / f'{stem}.{ext}', dpi=250, bbox_inches='tight')
                book.savefig(fig, bbox_inches='tight')
                plt.close(fig)
                file_map.append(dict(year=year, model=model, stem=stem, n=n))
    (OUT / 'figure_index.json').write_text(json.dumps(file_map, indent=2))
    return file_map, [float(x) for x in ylim]


def report(matched, scores, file_map, ylim):
    rows = ['IRI 动力预报与 RO / RO＋PMM：2015、2026 年八张独立比较图', '',
            '四个动力模式：NCEP CFSv2、NASA GMAO、CMC CANSIP（CanSIPS）、JMA。选择依据是两年 2—6 月档案都有记录及机构代表性，未按技巧挑选。',
            'NASA 的 2026 年 5—6 月来源名称为 NASA GMAOv3；按同一机构系列分组并明确标注，不能当作两年完全相同的模式版本。', '',
            '比较口径',
            '1. 完全复用原稿协议的 RO / RO＋PMM 2002—2024 年参数与已有 2—6 月、9 个月自由预报，不重新训练。2015 参与参数拟合，2026 未参与。',
            '2. IRI 是三个连续月的平均值。将已保存 RO 绝对 SST 预报恢复为 1991—2020 距平，再计算同样的连续三个月平均；观测使用已有 ERSSTv5 原始 Niño3.4 SST 以及相同基期。',
            '3. 第一季节从初值月开始，例如二月发布的 FMA 画在三月。RO 的整月初值是 lead 0，参与 FMA 的平均；不将 lead 0 单独当作一个预报检验样本。每个三月平均都要求三个完整值，不补值、不外推。',
            '4. JMA 仅有五个目标季节。图中展示每种方法的全部已发布/已积分轨迹，但主评分统一使用全部六种方法共同具备的“发布月—目标季节”配对，中心月提前 1—5 个月。',
            '5. 2015 为 25 个共同配对；2026 仅 19 个已观测共同配对，最后一个完整季节是 JAS（中心月八月，使用七至九月实况）。2026 后续季节没有真值，不评分。',
            '6. 评分是所有共同配对的 Pearson 相关和 RMSE。五个起报相互重叠，不是独立样本；没有给出虚构置信区间。原月值图的技巧不直接搬到此处。', '',
            '数据来源与提取核查',
            'IRI 原有 JSON 数据下载入口返回 404，官网说明不再提供直接预报数据下载。这里从仍公开的官方 SVG 矢量预报图提取坐标，明确作为图中数值读取结果保存，不声称拿到了模式原始集合数据。',
            '使用所有纵轴刻度拟合像素坐标到 °C 的线性映射；横坐标逐项核对季节标签。模式映射同时检查图例的颜色、线型、点型和全序列绘图顺序；重复图例样式使用相同样式内的排序。所有带点曲线另用 marker 坐标检查折线顶点。',
            '原始十张 SVG、下载时间、URL、SHA256、逐值源文件和 SVG artist id 均保存。当前公开档案可能包含提供者更正，不保证就是当年首次发布时的文件。', '',
            '解释边界',
            'IRI 明确说明各模式按各自的气候基期提供距平，并未统一基期。主图保留 IRI 原值，不用 2015 / 2026 实况拟合偏差订正；因此这是 as-published 个例比较，不能将较小的 RMSE 差异直接解释为纯动力技巧差异。附带 ±0.25°C 一致偏移敏感性表，仅是确定性检验，不是可信区间，也不代表任何模式实际基期差。',
            'RO 采用完整初值月的月均状态，而 IRI 一般在月中发布、各模式初始化时间不同。这不构成严格等信息量的实时预报排名。2015 的 RO 参数拟合本身包含该事件，尤其不能用于宣称独立预报优劣。',
            'PMM：2015 使用官方标准 MCA SST 指数；2026 使用前面已验证的 ERSSTv5 固定 R1 MCA 模态重建序列。所有预测状态均自由演变，没有沿途输入后来观测的 PMM。', '',
            '共同目标季节评分', scores.to_string(index=False), '',
            '官方来源：',
            'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/',
            'https://iri.columbia.edu/our-expertise/climate/enso/enso-prediction-models/',
            'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/2015-June-quick-look/',
            'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/2026-June-quick-look/',
            '图源链接见 data/raw/iri_plumes_2015_2026_20261014/source_manifest.json。IRI 内容使用 CC BY 4.0 许可。', '',
            '图件：IRI_RO_PMM_all_8_figures.pdf 汇总八页；每张另有 PNG / PDF / SVG。',
            '共同样本 common_seasonal_forecasts.csv；技巧 seasonal_skill_common_pairs.csv；所有读取值 iri_values_from_official_vector_plumes.csv。']
    (OUT / 'methods_and_results_cn.txt').write_text('\n'.join(rows) + '\n')
    inputs = [OLD / 'forecasts_2015.csv', NEW / 'forecasts_2026.csv', NEW / 'observed_raw_indices.csv']
    inputs += sorted(RAW.glob('*.svg'))
    provenance = dict(plots=file_map, common_sst_ylim=ylim,
                      inputs={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                      code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      model_selection='Coverage and institutional representation; not skill selection',
                      future_observations_filled=False, IRI_baselines_harmonized=False,
                      model_refitting=False, IRI_source='Published SVG coordinates, not raw member forecasts')
    (OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2))


if __name__ == '__main__':
    matched, scores, observed, iri = load_and_match()
    file_map, ylim = render(matched, scores, observed, iri)
    report(matched, scores, file_map, ylim)
    print('Completed:', OUT, flush=True)
