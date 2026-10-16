"""Full-sample four-state sLIM and observed-ocean diagnostic replay.

User-selected protocol: all 516 months of 1982--2024 enter preprocessing and
operator estimation. One fixed operator is shared by all three target events.
The former target-excluded analysis is historical comparison, not the primary.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd
import paper_ro_slim as original
import three_event_segmented_slim as slim

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/research_2026'
OUT = BASE / 'three_event_fullsample_replay_20261015'
FIGURES = BASE / 'three_event_scientific_figures_20261015'
SOURCE = BASE / 'three_event_slim_baseline_20261014/inputs_absolute.csv'
EVENTS = (1997, 2015, 2023)
COLUMNS = ['nino34', 'west_wwv', 'central_wwv', 'east_wwv']
KEY = 'three_wwv_fullsample_detrend_perturb2'


def serial(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    raise TypeError(type(x))


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                     default=serial), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trajectories(model, observed):
    """Target-month states are recorded before any subsequent observation reset."""
    phi = {m: slim.propagators(model, m, 1)[1] for m in range(1, 12)}
    free = np.zeros_like(observed)
    replay = np.zeros_like(observed)
    free[0] = replay[0] = observed[0]
    for i in range(1, 12):
        free[i] = phi[i] @ free[i-1]
        replay[i] = phi[i] @ np.r_[replay[i-1, 0], observed[i-1, 1:]]
    return free, replay


def analyze():
    OUT.mkdir(exist_ok=True)
    before = sha(SOURCE)
    raw = pd.read_csv(SOURCE, parse_dates=['time']).set_index('time')[COLUMNS]
    dates = pd.date_range('1982-01-01', '2024-12-01', freq='MS')
    assert raw.index.equals(dates) and np.isfinite(raw.to_numpy()).all()
    mask = np.ones(len(raw), dtype=bool)
    a, preprocessing = slim.preprocess(raw, mask.astype(float), detrend=True)
    model = slim.fit(a, mask, method='perturb2', order=2)
    comparison = original.fit(a, order=2, method='perturb2', interpolation='linear')
    equivalent = float(np.max(abs(model['coef'] - comparison['coef'])))
    assert equivalent < 1e-8
    annual = slim.propagators(model, months=12)
    refined = slim.propagators(model, months=12, steps=48)
    integration_error = float(np.max(abs(annual-refined)))
    assert integration_error < 1e-7
    climatology = raw.loc['1982':'2022'].groupby(raw.loc['1982':'2022'].index.month).mean()
    records, scores, qa = [], [], {}
    for event in EVENTS:
        ds = pd.date_range(f'{event}-01-01', periods=12, freq='MS')
        observed = a.loc[ds].to_numpy()
        free, replay = trajectories(model, observed)
        free_direct = slim.forecast(model, observed[0], months=11, month=1)
        error = float(abs(free-free_direct).max())
        assert error < 1e-8
        qa[f'{event}_monthly_vs_continuous_integration_error'] = error
        background = slim.background_at(preprocessing, ds)
        display = climatology.loc[ds.month].to_numpy()
        obs_display = raw.loc[ds].to_numpy()-display
        for experiment, prediction in [('free', free), ('observed_ocean_replay', replay)]:
            physical = prediction + background - display
            for i, d in enumerate(ds):
                for j, col in enumerate(COLUMNS):
                    records.append(dict(key=KEY, year=event, month=d.month,
                        experiment=experiment, variable=col, predicted=physical[i,j],
                        observed=obs_display[i,j], predicted_model=prediction[i,j],
                        observed_model=observed[i,j], training_scope='full_sample_1982_2024'))
            # Score SST only: replay repeatedly conditions on ocean observations.
            scores.append(dict(year=event, experiment=experiment,
                ond_pred=float(physical[9:,0].mean()), ond_obs=float(obs_display[9:,0].mean()),
                rmse_feb_dec=float(np.sqrt(np.mean((physical[1:,0]-obs_display[1:,0])**2)))))
        changed = observed.copy()
        changed[6:,1:] += 99.
        free_changed, replay_changed = trajectories(model, changed)
        assert np.array_equal(free_changed, free)
        assert np.array_equal(replay_changed[:7], replay[:7])
        assert np.max(abs(replay_changed[7:,0]-replay[7:,0])) > 1e-6
    frame = pd.DataFrame(records)
    frame.to_csv(OUT/'observed_state_replay.csv', index=False)
    score = pd.DataFrame(scores)
    score.to_csv(OUT/'replay_scores.csv', index=False)
    raw.to_csv(OUT/'inputs_absolute.csv', index_label='time')
    a.to_csv(OUT/'processed_states.csv', index_label='time')
    climatology.to_csv(OUT/'display_climatology_1982_2022.csv', index_label='month')
    pd.DataFrame({'time':dates, 'training':mask}).to_csv(OUT/'training_mask.csv', index=False)
    protocol = dict(key=KEY, training_period=['1982-01','2024-12'], training_months=516,
        training_years=43, excluded_years=[], target_events_included=list(EVENTS),
        states=COLUMNS, number_of_fitted_models=1,
        preprocessing='All 516 months: monthly climatology, then one linear trend per variable; training SD.',
        operator='Existing sLIM perturb2 moment estimator, annual + semiannual harmonics; deterministic RK4.',
        state_units=['degC','1e14 m3','1e14 m3','1e14 m3'],
        display_climatology='1982--2022 monthly means; restored after integration; not the fitting climatology.',
        replay='At each monthly transition, replace the three ocean coordinates with current-month observed model anomalies, retain model SST, and advance one month with the SAME fitted operator.',
        interpretation='In-sample retrospective diagnostic replay. No target-specific refit, independent forecast, or identified causal intervention.',
        previous_target_excluded_results='Historical sensitivity only; original files retained.')
    dump('protocol.json', protocol)
    dump('model_and_preprocessing.json', dict(key=KEY, model=model, preprocessing=preprocessing))
    reloaded = pd.read_csv(OUT/'observed_state_replay.csv')
    for row in score.itertuples():
        sub=reloaded[(reloaded.year==row.year)&reloaded.experiment.eq(row.experiment)&reloaded.variable.eq('nino34')].sort_values('month')
        rmse=float(np.sqrt(np.mean((sub.predicted.iloc[1:]-sub.observed.iloc[1:])**2)))
        assert abs(rmse-row.rmse_feb_dec)<1e-12
    assert sha(SOURCE)==before
    qa.update(training_months=516, excluded_years=[], fitted_models=1,
        all_target_months_in_training=bool(mask[raw.index.year.isin([1996,1997,1998,2014,2015,2016,2022,2023,2024])].all()),
        continuous_core_coefficient_max_error=equivalent, rk4_24_vs_48_max_error=integration_error,
        annual_propagator_spectral_radius=float(max(abs(np.linalg.eigvals(annual[-1])))),
        fixed_model_free_run_independent_of_later_observations=True,
        july_ocean_change_affects_august_not_january_to_july=True,
        source_input_unchanged=True, saved_scores_independently_recomputed=True,
        fit_diagnostics=model['diag'])
    dump('validation.json',qa)
    dump('input_manifest.json',{str(SOURCE.relative_to(ROOT)):before,
        str(Path(slim.__file__).relative_to(ROOT)):sha(Path(slim.__file__)),
        str(Path(original.__file__).relative_to(ROOT)):sha(Path(original.__file__))})
    print(score.round(6).to_string(index=False),flush=True)
    print(json.dumps(qa,default=serial,indent=2),flush=True)


def render():
    import build_three_event_scientific_figures as figures
    from matplotlib.backends.backend_pdf import PdfPages

    frame=pd.read_csv(OUT/'observed_state_replay.csv')
    budgets=pd.read_csv(FIGURES/'source_data/volume_budgets.csv')
    archive=OUT/'historical_target_excluded'
    archive.mkdir(exist_ok=True)
    # Archive only once, so rerendering does not erase the historical version.
    oldbook=archive/'three_event_figure_book.pdf'
    if not oldbook.exists():
        shutil.copy2(FIGURES/'three_event_figure_book.pdf',oldbook)
    oldmanifest=archive/'figure_manifest.json'
    if not oldmanifest.exists():
        shutil.copy2(FIGURES/'figure_manifest.json',oldmanifest)
    oldreplay=archive/'fixed_model_replay.csv'
    if not oldreplay.exists():
        with zipfile.ZipFile(FIGURES/'figure_data.zip') as z:
            oldreplay.write_bytes(z.read('source_data/fixed_model_replay.csv'))
    old=pd.read_csv(oldreplay)
    old=old[old.key.eq('three_wwv_detrend_perturb2')&old.variable.eq('nino34')&old.experiment.isin(['free','observed_ocean_replay'])]
    new=frame[frame.variable.eq('nino34')]
    paired=new.merge(old,on=['year','month','experiment','variable'],suffixes=('_full','_heldout'),validate='one_to_one')
    assert len(paired)==72
    assert np.max(abs(paired.observed_full-paired.observed_heldout))<1e-10
    comparison=[]
    for (year,experiment),q in paired.groupby(['year','experiment']):
        q=q.sort_values('month')
        row=dict(year=year,experiment=experiment,ond_observed=q.observed_full.iloc[9:].mean())
        for scope in ['full','heldout']:
            row[f'ond_{scope}']=q[f'predicted_{scope}'].iloc[9:].mean()
            row[f'rmse_{scope}']=np.sqrt(np.mean((q[f'predicted_{scope}'].iloc[1:]-q.observed_full.iloc[1:])**2))
        comparison.append(row)
    pd.DataFrame(comparison).to_csv(OUT/'fullsample_vs_target_excluded.csv',index=False)
    figures.style()
    figures.META.clear()
    figures.QA.clear()
    figures.FILES[5]=OUT/'observed_state_replay.csv'
    with PdfPages(OUT/'S3_fullsample_replay.pdf') as pdf:
        figures.attribution_limits(frame,budgets,pdf)
    newmeta=figures.META[0]
    newmeta['model_protocol']=str((OUT/'protocol.json').relative_to(ROOT))
    oldmeta=json.loads((FIGURES/'figure_manifest.json').read_text())
    updated=[newmeta if m['stem']=='S3_attribution_limits' else m for m in oldmeta]
    (FIGURES/'figure_manifest.json').write_text(json.dumps(updated,ensure_ascii=False,indent=2))
    figures.META[:]=updated
    temporary=FIGURES/'three_event_figure_book.new.pdf'
    # Reuse the bundled PDF runtime without changing the scientific Python environment.
    pdf_python=sys.executable if importlib.util.find_spec('pypdf') else os.environ.get(
        'CODEX_PDF_PYTHON', str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'))
    merge_code='''from pypdf import PdfReader, PdfWriter
import sys
old, new = PdfReader(sys.argv[1]), PdfReader(sys.argv[2])
assert len(old.pages)==6 and len(new.pages)==1
writer=PdfWriter()
for page in old.pages[:5]: writer.add_page(page)
writer.add_page(new.pages[0])
with open(sys.argv[3], 'wb') as stream: writer.write(stream)
'''
    subprocess.run([pdf_python,'-c',merge_code,str(oldbook),str(OUT/'S3_fullsample_replay.pdf'),str(temporary)],check=True)
    temporary.replace(FIGURES/'three_event_figure_book.pdf')
    frame.to_csv(FIGURES/'source_data/fixed_model_replay.csv',index=False)
    v=json.loads((FIGURES/'validation.json').read_text())
    v.pop('no_model_refit',None)
    v['figure_builder_does_not_fit_models']=True
    v['S3_model_refitted_full_sample']=dict(training_months=516,excluded_years=[],key=KEY)
    v.setdefault('text_outside_page',{}).update(figures.QA['text_outside_page'])
    v['visual_pdf_review']['updated_S3_status']='pending final render review'
    (FIGURES/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2))
    inputs=json.loads((FIGURES/'input_manifest.json').read_text())
    inputs.pop('outputs/research_2026/three_event_process_followup_20261015/observed_state_replay.csv',None)
    inputs[str((OUT/'observed_state_replay.csv').relative_to(ROOT))]=sha(OUT/'observed_state_replay.csv')
    (FIGURES/'input_manifest.json').write_text(json.dumps(inputs,indent=2))
    target_zip=FIGURES/'figure_data.new.zip'
    replacements={
        'source_data/fixed_model_replay.csv':FIGURES/'source_data/fixed_model_replay.csv',
        'input_manifest.json':FIGURES/'input_manifest.json',
        'build_three_event_scientific_figures.py':Path(figures.__file__),
        'analyze_three_event_fullsample_replay.py':Path(__file__),
        'fullsample_model/protocol.json':OUT/'protocol.json',
        'fullsample_model/model_and_preprocessing.json':OUT/'model_and_preprocessing.json',
        'fullsample_model/replay_scores.csv':OUT/'replay_scores.csv',
        'fullsample_model/validation.json':OUT/'validation.json',
        'historical_target_excluded/fixed_model_replay.csv':oldreplay,
    }
    with zipfile.ZipFile(FIGURES/'figure_data.zip') as source, zipfile.ZipFile(target_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for item in source.infolist():
            if item.filename not in replacements:
                z.writestr(item,source.read(item.filename))
        for name,path in replacements.items():
            z.write(path,name)
    target_zip.replace(FIGURES/'figure_data.zip')
    figures.gallery()
    scores=pd.read_csv(OUT/'replay_scores.csv')
    table=scores.rename(columns={'year':'事件','experiment':'实验','ond_pred':'OND模型海温','ond_obs':'OND观测海温','rmse_feb_dec':'2—12月RMSE'}).round(3).to_html(index=False)
    (OUT/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>全样本sLIM诊断重放</title><style>body{font-family:Arial,"PingFang SC",sans-serif;max-width:1000px;margin:40px auto;padding:0 24px;line-height:1.75;color:#24313b}img{width:100%}td,th{padding:10px;border-bottom:1px solid #ddd}table{border-collapse:collapse}a{color:#006b9f}</style><h1>全样本拟合后的海洋状态重放</h1><p>按用户确认的研究设计，1982—2024全部43年516个月，包括三个目标事件及邻年，都参与气候态、趋势、尺度和同一四状态sLIM算子的估计。保持年/半年谐波、perturb2与RK4，参数拟合一次后固定。每次月积分前仅替换三区海洋状态，海温持续由模型演化。本次是样本内诊断重放，不以事件留出作为主实验。</p><p>表中OND为10—12月平均Niño3.4距平（°C），RMSE为2—12月海温误差（°C），均使用1982—2022显示气候态。自由演化只使用1月完整月平均初态；重放反复使用当前月海洋观测推进下一月。</p>'''+table+'''<p><a href="../three_event_scientific_figures_20261015/index.html">返回六图图集</a> · <a href="protocol.json">完整实验口径</a> · <a href="fullsample_vs_target_excluded.csv">与旧留出版的对照表</a> · <a href="historical_target_excluded/three_event_figure_book.pdf">历史留出版图册</a></p><img src="../three_event_scientific_figures_20261015/S3_attribution_limits.png"><p>暖水体积并非完整三维海洋状态。全样本拟合可以检验当前统计表示的重现能力；曲线变化不等同于已识别的物理因果贡献。其他五张图及体积收支数值沿用原诊断。</p></html>''',encoding='utf-8')
    print(pd.DataFrame(comparison).round(6).to_string(index=False),flush=True)
    print(json.dumps(figures.QA,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--render-only',action='store_true')
    parser.add_argument('--update-figures',action='store_true')
    args=parser.parse_args()
    if not args.render_only:
        analyze()
    if args.render_only or args.update_figures:
        render()
