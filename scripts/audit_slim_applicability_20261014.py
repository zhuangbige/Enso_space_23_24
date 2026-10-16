"""Check the existing paper-period fits without changing them or selecting a model.

Run: .venv/bin/python scripts/audit_slim_applicability_20261014.py
The full moment-system solution is a numerical sensitivity, not ground truth.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import paper_ro_slim as slim

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/slim_RO_PMM_2015_manuscript_style_20261014'


def main():
    input_paths = [OUT / 'models_and_preprocessing.json', OUT / 'processed_states.csv']
    models = json.loads(input_paths[0].read_text())['paper_2002_2024']['fits']
    data = pd.read_csv(input_paths[1], parse_dates=['time'])
    data = data[data.protocol.eq('paper_2002_2024')].set_index('time')
    rows = []
    for name, saved in models.items():
        model = dict(saved)
        model['coef'] = np.asarray(model['coef'])
        model['scale'] = np.asarray(model['scale'])
        cols = model['columns']
        n = len(cols)
        train = data.loc['2002':'2024', cols]
        assert len(train) == 276 and np.isfinite(train.to_numpy()).all()
        reconstructed = slim.fit(train)
        np.testing.assert_allclose(model['coef'], reconstructed['coef'], atol=1e-11, rtol=1e-11)
        exact = slim.fit(train, method='exact')
        identity = np.eye(n)
        annual = np.column_stack([
            slim.predict(model, identity[:, j], 1, months=12, steps=48)[-1]
            for j in range(n)
        ])
        differences = []
        for month in range(2, 7):
            initial = data.loc[pd.Timestamp(2015, month, 1), cols].to_numpy()
            differences.append(
                slim.predict(model, initial, month, months=9)[1:, :2]
                - slim.predict(exact, initial, month, months=9)[1:, :2]
            )
        delta = np.vstack(differences)
        assert delta.shape == (45, 2) and np.isfinite(delta).all()
        rows.append(dict(
            model=name, states=n, monthly_training_values=len(train),
            scalar_drift_coefficients=5*n*n,
            lag_covariance_condition=model['diag']['condition'],
            second_first_correction_norm_ratio=(model['diag']['second_order_norm']
                                               / model['diag']['first_order_norm']),
            annual_propagator_spectral_radius=float(max(abs(np.linalg.eigvals(annual)))),
            full_moment_system_condition=exact['diag']['condition'],
            perturb_vs_full_relative_coefficient_norm=float(
                np.linalg.norm(model['coef'] - exact['coef']) / np.linalg.norm(exact['coef'])),
            perturb_vs_full_T_forecast_rms_difference_C=float(np.sqrt(np.mean(delta[:, 0]**2))),
            perturb_vs_full_h_forecast_rms_difference_m=float(np.sqrt(np.mean(delta[:, 1]**2))),
        ))
    result = dict(
        protocol='paper_2002_2024',
        input_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in input_paths + [ROOT / 'scripts/paper_ro_slim.py']},
        interpretation=[
            'Numerical diagnostics only; not an independent forecast validation or proof of physical adequacy.',
            'Annual propagator spectral radius < 1 means asymptotic stability of the fitted periodic deterministic model; transient growth remains possible.',
            'Full moment-system solution uses the same harmonics, interpolation and separate mean/seasonal lags as the perturbation estimate. It is not truth.',
            'Forecast RMS differences compare two solvers, not either solver against observations.',
            'Correction norm ratio is measured in standardized coordinates and is not a universal rejection threshold.',
            'No sample-size adequacy, residual-noise closure or resampling robustness claim follows from these checks.',
            'Input models, forecasts, figures, fitting windows and preprocessing are unchanged.',
        ],
        results=rows,
    )
    path = OUT / 'slim_applicability_numerical_audit.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
