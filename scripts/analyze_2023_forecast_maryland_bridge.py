"""Extend the frozen manuscript experiment to 2023 and join Maryland diagnostics.

Run from the Maryland project (or its physical cache). All forecasts evolve freely;
no event-specific bias fitting, model refitting, or post-initialization forcing.
IRI dates denote centers of three-month seasons, not monthly initial conditions.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import paper_ro_slim as slim
from compare_iri_ro_pmm_2015_2026 import extract, season, MODELS

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/research_2026'
DATA = ROOT / 'data/derived/research_2026'
OLD = BASE / 'slim_RO_PMM_2015_manuscript_style_20261014'
NEW = BASE / 'slim_RO_PMM_2026_manuscript_style_20261014'
IRI_OLD = BASE / 'IRI_RO_PMM_2015_2026_20261014'
RAW = ROOT / 'data/raw/iri_plumes_2023_20261014'
OUT = BASE / 'IRI_RO_PMM_Maryland_bridge_20261014'
PROTOCOL = 'paper_2002_2024'
METHODS = ['RO', 'RO_SST'] + MODELS
V = ['Nino34', 'WWV']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric(pred, obs):
    mask = np.isfinite(pred) & np.isfinite(obs)
    pred, obs = np.asarray(pred)[mask], np.asarray(obs)[mask]
    err = pred - obs
    return dict(n=len(err), r=float(np.corrcoef(pred, obs)[0, 1]),
                RMSE=float(np.sqrt(np.mean(err**2))), bias=float(np.mean(err)))


def frozen_forecasts():
    archive = json.loads((OLD / 'models_and_preprocessing.json').read_text())[PROTOCOL]
    meta = archive['preprocessing']
    raw = pd.read_csv(NEW / 'observed_raw_indices.csv', index_col=0, parse_dates=True)[V]
    p = pd.read_csv(ROOT / 'data/raw/ro_pmm_2026_update_20261014/PMM_uw.txt', sep=r'\s+')
    p.index = pd.to_datetime(dict(year=p.Year, month=p.Mo, day=1))
    dates = raw.index
    background = np.asarray(meta['clim'])[dates.month - 1] + np.column_stack([
        np.ones(len(dates)), slim.decimal_time(dates) - meta['center']]) @ np.asarray(meta['beta'])
    a = pd.DataFrame(raw.to_numpy() - background, index=dates, columns=V)
    a['PMM_SST'] = p.SST.reindex(dates) - meta['pmm_mean'][0]
    a['PMM_wind'] = p.Wind.reindex(dates) - meta['pmm_mean'][1]
    fits = {}
    for name in ['RO', 'RO_SST']:
        fits[name] = dict(archive['fits'][name])
        for key in ['coef', 'scale']:
            fits[name][key] = np.asarray(fits[name][key])
    rows, errors, integration = [], [], []
    for year in [2015, 2023]:
        for name in ['RO', 'RO_SST', 'RO_SST_cut']:
            model = fits[name.removesuffix('_cut')]
            for month in range(2, 7):
                init = pd.Timestamp(year, month, 1)
                target = pd.date_range(init, periods=10, freq='MS')
                x0 = a.loc[init, model['columns']].to_numpy()
                forecast = slim.predict(model, x0, month, months=9, cut_pmm=name.endswith('_cut'))
                errors.append(float(abs(forecast[0] - x0).max()))
                fine = slim.predict(model, x0, month, months=9, steps=48, cut_pmm=name.endswith('_cut'))
                integration.append(float(abs(fine - forecast).max()))
                bg = np.asarray(meta['clim'])[target.month - 1] + np.column_stack([
                    np.ones(10), slim.decimal_time(target) - meta['center']]) @ np.asarray(meta['beta'])
                physical = forecast[:, :2] + bg
                obs = a.reindex(target)[V].to_numpy()
                for lead, date in enumerate(target):
                    rows.append(dict(year=year, protocol=PROTOCOL, model=name, init=init,
                        month=month, lead=lead, target=date, T=forecast[lead, 0], H=forecast[lead, 1],
                        obs_T=obs[lead, 0], obs_H=obs[lead, 1], raw_T=physical[lead, 0],
                        raw_H=physical[lead, 1], initial_PMM_SST=float(p.loc[init, 'SST'])))
    f = pd.DataFrame(rows)
    previous = pd.read_csv(OLD / 'forecasts_2015.csv', parse_dates=['init', 'target'])
    previous = previous[previous.protocol.eq(PROTOCOL) & previous.model.isin(['RO', 'RO_SST'])]
    keys = ['model', 'init', 'lead']
    joined = previous.merge(f[f.year.eq(2015)], on=keys, suffixes=('_old', '_new'))
    assert len(joined) == 100
    previous_error = max(float(abs(joined[c + '_old'] - joined[c + '_new']).max())
                         for c in ['T', 'H', 'raw_T', 'raw_H', 'obs_T', 'obs_H'])
    assert previous_error < 1e-9, previous_error
    assert max(errors) < 1e-10 and max(integration) < 1e-5
    scores = []
    for (year, model), g in f[f.lead.between(1, 9)].groupby(['year', 'model']):
        row = dict(year=year, model=model)
        for var in ['T', 'H']:
            row.update({var + '_' + k: v for k, v in metric(g[var], g['obs_' + var]).items()})
        scores.append(row)
    f.to_csv(OUT / 'forecasts_2015_2023.csv', index=False)
    f[f.year.eq(2023)].to_csv(OUT / 'forecasts_2023.csv', index=False)
    pd.DataFrame(scores).to_csv(OUT / 'monthly_event_scores.csv', index=False)
    a.to_csv(OUT / 'processed_states_official_PMM.csv', index_label='time')
    p[['SST', 'Wind']].to_csv(OUT / 'official_PMM.csv', index_label='time')
    (OUT / 'frozen_models_and_preprocessing.json').write_text(json.dumps(archive, indent=2))
    return f, raw, dict(initial_state_max_error=max(errors), rk4_max_difference=max(integration),
                        reproduced_2015_max_difference=previous_error)


def iri_and_seasonal(f, raw):
    rows, audit = [], []
    for month in range(2, 7):
        r, q = extract(RAW / f'iri_plume_2023_{month:02}.svg', 2023, month)
        rows.extend(r); audit.extend(q)
    new = pd.DataFrame(rows)
    previous = pd.read_csv(IRI_OLD / 'iri_values_from_official_vector_plumes.csv', parse_dates=['init', 'center'])
    iri = pd.concat([previous, new], ignore_index=True)
    iri.to_csv(OUT / 'iri_values_2015_2023_2026.csv', index=False)
    (OUT / 'vector_extraction_QA_2023.json').write_text(json.dumps(audit, indent=2))
    climatology = raw.Nino34.loc['1991':'2020'].groupby(raw.Nino34.loc['1991':'2020'].index.month).mean()
    monthly = raw.Nino34 - climatology.reindex(raw.index.month).to_numpy()
    obs = monthly.rolling(3, center=True, min_periods=3).mean()
    pd.DataFrame(dict(monthly_1991_2020=monthly, seasonal_1991_2020=obs)).to_csv(
        OUT / 'observations.csv', index_label='time')
    ro_rows = []
    for (model, init), g in f[f.year.eq(2023) & f.model.isin(['RO', 'RO_SST'])].groupby(['model', 'init']):
        g = g.sort_values('lead')
        anomaly = pd.Series(g.raw_T.values - climatology.reindex(g.target.dt.month).values, index=g.target)
        smooth = anomaly.rolling(3, center=True, min_periods=3).mean().dropna()
        for center, value in smooth.items():
            ro_rows.append(dict(year=2023, issue_month=init.month, init=init, center=center,
                                method=model, value=value, observed=obs.loc[center]))
    old_ro = pd.read_csv(IRI_OLD / 'RO_PMM_seasonal_full_trajectories.csv', parse_dates=['init', 'center'])
    ro = pd.concat([old_ro, pd.DataFrame(ro_rows)], ignore_index=True)
    ro.to_csv(OUT / 'RO_PMM_seasonal_full_trajectories.csv', index=False)
    keys = ['year', 'issue_month', 'init', 'center']
    matched = ro.pivot(index=keys, columns='method', values='value').reset_index().merge(
        iri.pivot(index=keys, columns='iri_model', values='IRI').reset_index(), on=keys).dropna(subset=METHODS)
    matched['observed'] = obs.reindex(matched.center).values
    matched['season'] = matched.center.map(season)
    matched['season_end'] = matched.center + pd.DateOffset(months=1)
    matched['lead_center'] = (matched.center.dt.year - matched.init.dt.year) * 12 + matched.center.dt.month - matched.init.dt.month
    matched['verified'] = matched.observed.notna()
    assert matched.lead_center.between(1, 5).all()
    assert matched[matched.year.eq(2023)].shape[0] == 25
    scores = [dict(year=y, model=m, **metric(g[m], g.observed))
              for y, g in matched[matched.verified].groupby('year') for m in METHODS]
    matched.to_csv(OUT / 'common_seasonal_forecasts.csv', index=False)
    score = pd.DataFrame(scores)
    score.to_csv(OUT / 'seasonal_skill_common_pairs.csv', index=False)
    # Skill and extraction for the two completed previous tasks must remain unchanged.
    old_score = pd.read_csv(IRI_OLD / 'seasonal_skill_common_pairs.csv')
    check = old_score.merge(score, on=['year', 'model'], suffixes=('_old', '_new'))
    assert len(check) == 12
    for c in ['n', 'r', 'RMSE', 'bias']:
        np.testing.assert_allclose(check[c + '_old'], check[c + '_new'], atol=1e-10)
    residuals = matched[matched.verified].copy()
    residuals['PMM_increment'] = residuals.RO_SST - residuals.RO
    for m in METHODS:
        residuals[m + '_error'] = residuals[m] - residuals.observed
    residuals.to_csv(OUT / 'forecast_errors_and_PMM_increment.csv', index=False)
    summary = []
    for (year, month), g in residuals.groupby(['year', 'issue_month']):
        summary.append(dict(year=year, issue_month=month, n=len(g),
                            RO_bias=g.RO_error.mean(), PMM_increment=g.PMM_increment.mean(),
                            RO_RMSE=metric(g.RO, g.observed)['RMSE'],
                            RO_PMM_RMSE=metric(g.RO_SST, g.observed)['RMSE']))
    pd.DataFrame(summary).to_csv(OUT / 'scores_and_increment_by_start.csv', index=False)
    print(score.to_string(index=False), flush=True)
    return score


def maryland_tables():
    events = pd.read_csv(DATA / 'nonh20_third_question_event_table.csv')
    events = events[events.event_year.isin([1997, 2015, 2023])].copy()
    sinks = ['decay_westward_return_zj', 'decay_eastward_export_zj', 'decay_northward_output_zj',
             'decay_southward_output_zj', 'decay_surface_loss_zj', 'decay_residual_sink_zj']
    closure = events[sinks].sum(axis=1) - events.decay_storage_loss_zj
    assert abs(closure).max() < 1e-7
    events.to_csv(OUT / 'Maryland_event_bridge.csv', index=False)
    monthly = pd.read_csv(DATA / 'soda3_three_box_ohc_anomaly_budget_monthly.csv', parse_dates=['time'])
    selected = []
    for year in [2015, 2023]:
        g = monthly[(monthly.year.eq(year)) | (monthly.year.eq(year+1) & monthly.month.le(5))].copy()
        assert len(g) == 17 and g.time.is_monotonic_increasing
        g['event_year'] = year
        selected.append(g)
        arrive = g[g.year.eq(year) & g.month.between(1, 6)]
        x = (arrive.time - arrive.time.iloc[0]).dt.total_seconds().to_numpy()
        arrival = np.trapezoid(arrive.east_west_theta_heat_in_corr_anom_pw, x=x) / 1e6
        expected = events.loc[events.event_year.eq(year), 'arrival_140w_heat_in_zj'].iloc[0]
        np.testing.assert_allclose(arrival, expected, atol=1e-7)
    pd.concat(selected).to_csv(OUT / 'Maryland_monthly_bridge.csv', index=False)
    coupling = pd.read_csv(DATA / 'enso_full_year_coupling_monthly_1982_2024.csv')
    coupling = coupling[coupling.year.isin([2015, 2023])].copy()
    assert len(coupling) == 24
    coupling['time'] = pd.to_datetime(dict(year=coupling.year, month=coupling.month, day=1))
    coupling.to_csv(OUT / 'Maryland_atmospheric_coupling.csv', index=False)
    return dict(max_budget_closure_error_ZJ=float(abs(closure).max()),
                budget_window='following January 15 to May 15 (existing trapezoidal monthly-center convention)',
                arrival_window='January 15 to June 15 (existing monthly-center convention)')


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    f, raw, qa = frozen_forecasts()
    iri_and_seasonal(f, raw)
    qa.update(maryland_tables())
    qa.update(fit='Frozen 2002-2024; retrospective fit includes 2015 and 2023',
              trend_fit='2002-01 to 2025-04; unchanged manuscript preprocessing',
              official_PMM_used_for_2023=True, no_observed_forcing_after_initialization=True,
              IRI_anomaly_baselines_harmonized=False, forecasts_bias_adjusted=False,
              model_initial_states_available_for_IRI=False, equal_information_real_time_test=False,
              incomplete_2026_decay_not_evaluated=True)
    sources = [OLD / 'models_and_preprocessing.json', OLD / 'forecasts_2015.csv',
               NEW / 'observed_raw_indices.csv', ROOT / 'data/raw/ro_pmm_2026_update_20261014/PMM_uw.txt',
               DATA / 'nonh20_third_question_event_table.csv',
               DATA / 'soda3_three_box_ohc_anomaly_budget_monthly.csv',
               DATA / 'enso_full_year_coupling_monthly_1982_2024.csv',
               DATA / 'enso_full_year_coupling_diagnostics.json']
    sources += sorted(RAW.glob('*.svg'))
    qa['input_sha256'] = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    (OUT / 'numerical_QA.json').write_text(json.dumps(qa, indent=2))
    print('Completed:', OUT, flush=True)


if __name__ == '__main__':
    main()
