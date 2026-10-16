"""Audit the existing 1982--2024 four-state model without replacing it.

The full moment solve is an estimator sensitivity with the same preprocessing,
harmonics, interpolation and mixed mean/seasonal lags. It is not ground truth.
Run with the scientific Python environment from the project root.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import paper_ro_slim as core
import three_event_segmented_slim as slim

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/research_2026/three_event_fullsample_replay_20261015'
OUT = ROOT / 'outputs/research_2026/three_event_slim_original_audit_20261015'
EVENTS = (1997, 2015, 2023)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    paths = [SOURCE / 'model_and_preprocessing.json', SOURCE / 'processed_states.csv',
             ROOT / 'scripts/paper_ro_slim.py', ROOT / 'scripts/three_event_segmented_slim.py',
             ROOT / 'scripts/analyze_three_event_ocean_swaps.py']
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    saved = json.loads(paths[0].read_text())
    base = saved['model']
    for key in ['coef', 'scale']:
        base[key] = np.asarray(base[key])
    a = pd.read_csv(paths[1], parse_dates=['time']).set_index('time')[base['columns']]
    assert a.index.equals(pd.date_range('1982-01-01', '2024-12-01', freq='MS'))
    assert np.isfinite(a.to_numpy()).all()
    reconstructed = core.fit(a, order=2, method='perturb2')
    reproduction_error = float(abs(base['coef'] - reconstructed['coef']).max())
    assert reproduction_error < 1e-10

    # Check Appendix A7 trigonometric-product form independently of the code's
    # direct products. Negative sine harmonics retain their odd symmetry.
    z = a.to_numpy() / base['scale']
    grid = np.arange((len(a) - 1) * 6 + 1) / 6
    x = np.column_stack([np.interp(grid, np.arange(len(a)), z[:, j]) for j in range(z.shape[1])])
    t = a.index[0].year + (a.index[0].month - .5) / 12 + grid / 12
    ids = np.arange(1, len(x) - 1)
    xx, lagged = x[ids], x[ids - 1]
    def harmonic(n, sine=False):
        weight = (np.sin if sine else np.cos)(2 * np.pi * n * t[ids])
        return np.einsum('n,ni,nj->ij', weight, xx, lagged) / len(ids)
    _, _, blocks = core.moments(x, np.gradient(x, 1 / 72, axis=0), t, 1, 2)
    product_errors = []
    for n in (1, 2):
        for m in (1, 2):
            product_errors.extend([
                np.max(abs(blocks[m, n] - (harmonic(n + m) + harmonic(n - m)) / 2)),
                np.max(abs(blocks[m + 2, n] - (harmonic(n + m, True) - harmonic(n - m, True)) / 2)),
                np.max(abs(blocks[m, n + 2] - (harmonic(n + m, True) + harmonic(n - m, True)) / 2)),
                np.max(abs(blocks[m + 2, n + 2] - (harmonic(n - m) - harmonic(n + m)) / 2)),
            ])
    assert max(product_errors) < 1e-9

    # One comparison fit only. No model selection, new states or preprocessing.
    full = slim.fit(a, np.ones(len(a), dtype=bool), method='exact', order=2)
    diagnostics, swaps, closure, correlations = [], [], [], []
    for label, model in [('saved_perturb2', base), ('full_moment_sensitivity', full)]:
        phi = np.array([slim.propagators(model, month=m, months=1)[1] for m in range(1, 13)])
        annual = slim.propagators(model, months=12)
        refined = slim.propagators(model, months=12, steps=48)
        integration_error = float(abs(annual - refined).max())
        assert integration_error < 1e-7
        state = a.to_numpy()
        one_step = np.einsum('nij,nj->ni', phi[a.index.month[:-1] - 1], state[:-1])
        residual = state[1:] - one_step
        diagnostics.append(dict(estimator=label,
            annual_spectral_radius=float(max(abs(np.linalg.eigvals(annual[-1])))),
            rk4_24_vs_48_max_error=integration_error,
            one_step_sst_rmse_C=float(np.sqrt(np.mean(residual[:, 0] ** 2))),
            sst_residual_lag1_correlation=float(np.corrcoef(residual[1:, 0], residual[:-1, 0])[0, 1]),
            **model['diag']))
        corr = np.corrcoef(residual.T)[0, 1:]
        for variable, value in zip(model['columns'][1:], corr):
            correlations.append(dict(estimator=label, ocean_variable=variable,
                sst_ocean_residual_same_transition_correlation=float(value)))
        for recipient in EVENTS:
            target = a.loc[str(recipient)].to_numpy()
            r = target[1:, 0] - np.einsum('ni,ni->n', phi[:11, 0], target[:-1])
            replay = np.zeros(12)
            replay[0] = target[0, 0]
            restored = np.zeros(12)
            for k in range(11):
                replay[k + 1] = phi[k, 0, 0] * replay[k] + phi[k, 0, 1:] @ target[k, 1:]
                restored[k + 1] = phi[k, 0, 0] * restored[k] + r[k]
            error = float(abs(replay + restored - target[:, 0]).max())
            assert error < 1e-10
            closure.append(dict(estimator=label, recipient=recipient,
                ond_residual_restoration_C=float(restored[9:].mean()),
                ocean_replay_sst_rmse_feb_dec_C=float(np.sqrt(np.mean((replay[1:] - target[1:, 0]) ** 2))),
                reconstruction_identity_max_error=error))
            for donor in EVENTS:
                dv = a.loc[str(donor)].to_numpy()[:, 1:] - target[:, 1:]
                delta = np.zeros(12)
                region = np.zeros((12, 3))
                for k in range(11):
                    delta[k + 1] = phi[k, 0, 0] * delta[k] + phi[k, 0, 1:] @ dv[k]
                    region[k + 1] = phi[k, 0, 0] * region[k] + phi[k, 0, 1:] * dv[k]
                assert np.max(abs(region.sum(axis=1) - delta)) < 1e-10
                for k in range(12):
                    swaps.append(dict(estimator=label, recipient=recipient, donor=donor,
                        month=k + 1, delta_sst_C=delta[k],
                        **{f'{name}_contribution_C': region[k, j]
                           for j, name in enumerate(['west', 'central', 'east'])}))
    pd.DataFrame(swaps).to_csv(OUT / 'solver_swap_monthly.csv', index=False)
    ond = pd.DataFrame(swaps).query('month >= 10').groupby(
        ['estimator', 'recipient', 'donor']).mean(numeric_only=True).drop(columns='month').reset_index()
    ond.to_csv(OUT / 'solver_swap_OND.csv', index=False)
    pd.DataFrame(closure).to_csv(OUT / 'residual_restoration.csv', index=False)
    pd.DataFrame(correlations).to_csv(OUT / 'residual_correlations.csv', index=False)
    pivot = ond.pivot(index=['recipient', 'donor'], columns='estimator', values='delta_sst_C')
    report = dict(
        primary_model_changed=False, primary_figures_changed=False,
        comparison_fits=1, target_years_excluded=[], original_months=len(a),
        saved_model_reproduction_max_error=reproduction_error,
        appendix_trigonometric_product_max_error=float(max(product_errors)),
        relative_coefficient_difference_to_full_moment=float(
            np.linalg.norm(base['coef'] - full['coef']) / np.linalg.norm(full['coef'])),
        max_absolute_OND_swap_difference_C=float(abs(pivot.iloc[:, 0] - pivot.iloc[:, 1]).max()),
        diagnostics=diagnostics,
        qualifications=[
            'Full moment solve retains the code convention: one-month lag for the mean equation and one-pentad lag for seasonal equations; it is not an independently validated truth.',
            'Numerical stability and agreement of two solvers do not establish physical closure or causal validity.',
            'Residual correlations are descriptive in-sample quantities; no independent-white-noise hypothesis test or causal identification is claimed.',
            'The propagated residual correction is not an atmospheric contribution or an explained-variance fraction.',
            'The checks do not assess input-field extraction errors, alternative ocean proxies, parameter sampling uncertainty, or continuous ocean-clamping sensitivity.',
        ],
        sources=[
            dict(doi='10.1175/JCLI-D-20-0874.1', sections='2a--c, 3b, Appendix A1--A7',
                 url='https://journals.ametsoc.org/view/journals/clim/34/12/JCLI-D-20-0874.1.xml'),
            dict(doi='10.1029/2021GL097603', sections='2.1--2.4',
                 url='https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2021GL097603'),
        ], input_sha256=before)
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    report['input_files_unchanged'] = True
    (OUT / 'numerical_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(pivot.round(6).to_string())
    print(pd.DataFrame(closure).round(6).to_string(index=False))
    print('Reproduction error:', reproduction_error)
    print('Appendix product identity error:', max(product_errors))
    print('Coefficient relative difference:', report['relative_coefficient_difference_to_full_moment'])


if __name__ == '__main__':
    main()
