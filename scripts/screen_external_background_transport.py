"""Retrospective background-state screening, not a causal ocean experiment."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/external_background_experiments_20261015'
BASE = ROOT / 'outputs/research_2026/three_event_ocean_preconditioning_20261014'
SST = ROOT / 'data/raw/ersstv5_sst_monthly_full.nc'
PMM = ROOT / 'outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014/official_PMM.csv'
DATES = pd.date_range('1982-01-01', '2024-12-01', freq='MS')
BOXES = {'TNA': (0, 20, 300, 340), 'TIO': (-20, 20, 40, 110),
         'ENP': (35, 45, 150, 240)}
GROUPS = {'A_IndoAtlantic': ['TNA', 'TIO'], 'B_ExtratropicalPacific': ['PMM', 'ENP'],
          'AB_joint': ['TNA', 'TIO', 'PMM', 'ENP']}
CONTROLS = ['spring_transport', 'early_west_wwv', 'early_nino34']
NBOOT = 3000


def read_monthly(path):
    d = pd.read_csv(path, parse_dates=['time']).set_index('time')
    d.index = d.index.to_period('M').to_timestamp()
    assert d.index.is_unique
    return d.reindex(DATES)


def remove_background(df, detrend):
    out = df - df.groupby(df.index.month).transform('mean')
    if detrend:
        t = np.arange(len(out), dtype=float)
        t -= t.mean()
        out = out - np.outer(t, t @ out.to_numpy() / (t @ t))
    return out


def seasonal(df, months):
    sub = df[df.index.month.isin(months)]
    counts = sub.groupby(sub.index.year).count()
    assert (counts == len(months)).all().all()
    return sub.groupby(sub.index.year).mean()


def build_monthly():
    ocean = read_monthly(BASE / 'ocean_monthly_anomalies.csv')
    air = read_monthly(BASE / 'atmosphere_anomaly_and_reference.csv')
    d = pd.DataFrame({'transport': ocean.u220_q_sv,
                      'west_wwv': ocean.west_wwv_m3 / 1e14,
                      'nino34': air.nino34}, index=DATES)
    d['PMM'] = read_monthly(PMM)['SST']
    qa = {}
    with xr.open_dataset(SST, engine='h5netcdf') as ds:
        sst = ds.sst.sel(time=slice('1982-01-01', '2024-12-31'))
        assert np.array_equal(pd.DatetimeIndex(sst.time.values), DATES)
        assert np.all(np.diff(sst.lon.values) > 0)
        for name, (s, n, w, e) in BOXES.items():
            box = sst.where((sst.lat >= s) & (sst.lat <= n) &
                            (sst.lon >= w) & (sst.lon <= e), drop=True).load()
            vals = box.values
            assert np.nanmin(vals) >= -3 and np.nanmax(vals) < 40
            mask = box.notnull().all('time')
            weight = np.cos(np.deg2rad(box.lat)) * xr.ones_like(mask) * mask
            series = (box.fillna(0) * weight).sum(('lat', 'lon')) / weight.sum()
            # Independent numpy spatial mean verifies the latitude weighting.
            manual = np.nansum(vals * weight.values, axis=(1, 2)) / float(weight.sum())
            err = float(np.max(np.abs(series.values - manual)))
            assert err < 1e-10 and int(mask.sum()) > 0
            d[name] = series.values
            qa[name] = {'box_s_n_w_e': [s, n, w, e], 'fixed_ocean_cells': int(mask.sum()),
                        'weighting_check_max_C': err,
                        'source_units': sst.attrs.get('units')}
    assert len(d) == 516 and np.isfinite(d.to_numpy()).all()
    d.to_csv(OUT / 'monthly_inputs.csv', index_label='time')
    return d, qa


def annual_table(raw, window, detrend):
    d = remove_background(raw, detrend)
    a = pd.DataFrame(index=np.arange(1982, 2025))
    a['summer_transport'] = seasonal(d[['transport']], [7, 8, 9]).transport
    a['spring_transport'] = seasonal(d[['transport']], [4, 5, 6]).transport
    early = seasonal(d[['west_wwv', 'nino34']], [1, 2, 3])
    a['early_west_wwv'] = early.west_wwv
    a['early_nino34'] = early.nino34
    for name in ['TNA', 'TIO', 'PMM', 'ENP']:
        a[name] = seasonal(d[[name]], window)[name]
    assert a.shape == (43, 8) and np.isfinite(a).all().all()
    return a


def fit(a, group, columns, key, rng):
    names = CONTROLS + columns
    x = a[names].to_numpy()
    means, scales = x.mean(axis=0), x.std(axis=0)
    z = (x - means) / scales
    X = np.column_stack([np.ones(len(x)), z])
    y = a.summer_transport.to_numpy()
    assert np.linalg.matrix_rank(X) == X.shape[1]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    pred = X @ beta
    residual = y - pred
    base = X[:, :1 + len(CONTROLS)]
    base_pred = base @ np.linalg.lstsq(base, y, rcond=None)[0]
    ss = np.sum((y - y.mean()) ** 2)
    base_sse, sse = np.sum((y - base_pred) ** 2), residual @ residual
    n, p = X.shape
    # Paired circular blocks preserve short interannual dependence.
    boots = []
    for _ in range(NBOOT):
        starts = rng.integers(0, n, size=int(np.ceil(n / 3)))
        ix = ((starts[:, None] + np.arange(3)) % n).ravel()[:n]
        if np.linalg.matrix_rank(X[ix]) == p:
            boots.append(np.linalg.lstsq(X[ix], y[ix], rcond=None)[0])
    boots = np.asarray(boots)
    assert len(boots) > 0.99 * NBOOT
    lo, hi = np.quantile(boots, [0.025, 0.975], axis=0)
    delete_one = []
    for i in range(n):
        ix = np.arange(n) != i
        delete_one.append(np.linalg.lstsq(X[ix], y[ix], rcond=None)[0])
    delete_one = np.asarray(delete_one)
    vif = np.diag(np.linalg.inv(z.T @ z / n))
    result = dict(setting=key, group=group, n=n, r2=1-sse/ss,
                  adjusted_r2=1-(sse/(n-p))/(ss/(n-1)),
                  base_r2=1-base_sse/ss, delta_r2=(base_sse-sse)/ss,
                  partial_r2=(base_sse-sse)/base_sse,
                  base_adjusted_r2=1-(base_sse/(n-base.shape[1]))/(ss/(n-1)),
                  condition_number=float(np.linalg.cond(X)), max_vif=float(max(vif)),
                  residual_lag1=float(np.corrcoef(residual[:-1], residual[1:])[0, 1]),
                  bootstrap_valid=len(boots))
    coeff = []
    for j, name in enumerate(names, 1):
        coeff.append(dict(setting=key, group=group, variable=name,
                          is_external=name in columns, beta_Sv_per_SD=beta[j],
                          bootstrap_lo=lo[j], bootstrap_hi=hi[j],
                          delete_one_same_sign=float(np.mean(np.sign(delete_one[:, j]) == np.sign(beta[j]))),
                          vif=float(vif[j-1]), source_mean=means[j-1], source_sd=scales[j-1]))
    predictions = pd.DataFrame({'setting': key, 'group': group, 'year': a.index,
                                'observed_Sv': y, 'base_fitted_Sv': base_pred,
                                'extended_fitted_Sv': pred, 'residual_Sv': residual})
    # FWL verification uses a separately residualized design.
    residualize = lambda v: v - base @ np.linalg.lstsq(base, v, rcond=None)[0]
    bx = np.linalg.lstsq(residualize(X[:, base.shape[1]:]), residualize(y), rcond=None)[0]
    err = float(np.max(np.abs(bx - beta[base.shape[1]:])))
    assert err < 1e-9
    result['fwl_check_max_Sv'] = err
    return result, coeff, predictions


def main():
    assert (OUT / '实验约定_先于计算.txt').exists()
    raw, qa = build_monthly()
    tables, summaries, coeffs, preds = [], [], [], []
    rng = np.random.default_rng(20261015)
    for detrend in [True, False]:
        for window, months in [('AMJ', [4, 5, 6]), ('MAM', [3, 4, 5])]:
            key = f'{window}_{"detrended" if detrend else "with_trend"}'
            a = annual_table(raw, months, detrend)
            tables.append(a.assign(setting=key).reset_index(names='year'))
            for group, columns in GROUPS.items():
                summary, coef, pred = fit(a, group, columns, key, rng)
                summaries.append(summary); coeffs.extend(coef); preds.append(pred)
    annual = pd.concat(tables, ignore_index=True)
    summary = pd.DataFrame(summaries)
    coeff = pd.DataFrame(coeffs)
    annual.to_csv(OUT / 'annual_inputs_all_settings.csv', index=False)
    summary.to_csv(OUT / 'model_comparisons.csv', index=False)
    coeff.to_csv(OUT / 'all_coefficients.csv', index=False)
    pd.concat(preds).to_csv(OUT / 'all_year_fitted_values.csv', index=False)
    annual[annual.year.isin([1997, 2015, 2023])].to_csv(OUT / 'three_event_comparison.csv', index=False)
    primary = coeff[(coeff.setting == 'AMJ_detrended') & coeff.is_external]
    rows = []
    for name in ['TNA', 'TIO', 'PMM', 'ENP']:
        own = 'A_IndoAtlantic' if name in ['TNA', 'TIO'] else 'B_ExtratropicalPacific'
        c = coeff[(coeff.variable == name) & (coeff.group == own)]
        p = c[c.setting == 'AMJ_detrended'].iloc[0]
        joint = primary[(primary.group == 'AB_joint') & (primary.variable == name)].iloc[0]
        rows.append(dict(variable=name, group=own,
                         primary_beta=p.beta_Sv_per_SD, primary_lo=p.bootstrap_lo,
                         primary_hi=p.bootstrap_hi, delete_one_same_sign=p.delete_one_same_sign,
                         four_settings_same_sign=bool((np.sign(c.beta_Sv_per_SD) == np.sign(p.beta_Sv_per_SD)).all()),
                         four_settings_ci_excludes_zero_count=int(((c.bootstrap_lo > 0) | (c.bootstrap_hi < 0)).sum()),
                         joint_beta=joint.beta_Sv_per_SD, joint_lo=joint.bootstrap_lo,
                         joint_hi=joint.bootstrap_hi,
                         joint_same_sign=bool(np.sign(joint.beta_Sv_per_SD) == np.sign(p.beta_Sv_per_SD))))
    stability = pd.DataFrame(rows)
    stability.to_csv(OUT / 'candidate_stability.csv', index=False)
    sources = [SST, PMM, BASE/'ocean_monthly_anomalies.csv',
               BASE/'atmosphere_anomaly_and_reference.csv', Path(__file__), OUT/'实验约定_先于计算.txt']
    manifest = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size,
                 'sha256': hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()} for p in sources]
    (OUT/'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    qa.update(months=516, years=43, fits=len(summary), bootstrap_replicates=NBOOT,
              primary='AMJ_detrended', interpretation='retrospective conditional association; no causal intervention')
    (OUT/'validation.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2))
    detail = []
    for r in stability.itertuples():
        detail.append(f'{r.variable}：主设定系数{r.primary_beta:+.2f} Sv/SD，95%区间[{r.primary_lo:+.2f}, {r.primary_hi:+.2f}]；'
                      f'四种设置方向一致={r.four_settings_same_sign}，区间排除零{r.four_settings_ci_excludes_zero_count}/4；'
                      f'联合模型{r.joint_beta:+.2f}，区间[{r.joint_lo:+.2f}, {r.joint_hi:+.2f}]。')
    text = ['外部海洋背景补充实验：首轮统计筛选结果', '',
            '主线未变；没有修改sLIM或把统计系数当物理替换结果。',
            '1982—2024全部43年；以春季输送、冬末西部WWV26、冬末Niño3.4为控制，比较背景与7—9月140°W输送的条件联系。',
            '主设定AMJ去趋势；区间为3年循环块bootstrap 3000次的95%区间。',
            '单位：外部指标每增加1个样本标准差，对应夏季输送变化多少Sv。', '',
            '逐项解释：', *detail, '',
            'TNA是当前优先核对的候选；PMM可作为第二候选。两组同时加入后，主设定各外部系数区间均跨零，不能分配独立贡献。',
            'TIO符号依赖背景处理，不能据此认定印度洋无作用：平均海温不是季风/海洋大陆对流加热。',
            'ENP在本条件模型中为正，未支持预设的“增暖抑制东向输送”；保留此反向结果，不改区框寻找负号。',
            '前期西部WWV、Niño3.4、春季输送及TIO互相关较高，主设定最大VIF约10.5；联合归因受共线性及小样本限制。',
            '以上区间是探索性逐项区间，没有作为多重检验后显著性使用；接近零的区间端点不应强调。',
            '筛选重新去1982—2024月气候均值；绝对距平零点与旧1982—2022图略有差别，不能混用数值。', '',
            '主设定所有组：', summary[summary.setting.eq('AMJ_detrended')].to_string(index=False), '',
            '候选稳定性（全部保留）：', stability.to_string(index=False), '',
            '选用约定：先看时间/背景敏感性与联合模型，再看区间和物理机制；增量R²仅是样本内拟合收益。',
            '本次未检验完整南太平洋、外部次表层状态、实际跨海盆海洋传输，也未完成因果方向识别。',
            'PMM与ENP只是赤道外北太平洋候选；TNA均值不是北大西洋三极子；TIO均值不是印度季风加热。',
            '风仍可能是外部SST影响输送的中介。去掉低频风异常仍有增暖，并不排除外部SST影响输送。',
            '若候选通过初筛，下一步沿实际流速/温度梯度和输送路径核对，再考虑配对替换实验。',
            '反向作用、共同驱动、选择季节及43年小样本限制仍存在；任何结果不得称独立因果贡献。']
    (OUT/'首轮结果与解释.txt').write_text('\n'.join(text), encoding='utf-8')
    print(summary[summary.setting.eq('AMJ_detrended')][['group','base_r2','delta_r2','adjusted_r2','max_vif']].to_string(index=False))
    print(stability.to_string(index=False))
    print(OUT/'首轮结果与解释.txt')


if __name__ == '__main__':
    main()
