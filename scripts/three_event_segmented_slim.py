"""Chen--Jin sLIM moment estimator on disconnected monthly training segments.

The equations and integration convention match paper_ro_slim.py. Excluded
intervals are never interpolated, differentiated, or lagged across. Moment
averages are pooled by sample counts, not averaged equally across segments.
The weighted option is a block-weighted estimating-equation sensitivity.
"""
import numpy as np
import pandas as pd
import paper_ro_slim as original


def segments(index, mask):
    ids = np.flatnonzero(mask)
    breaks = np.flatnonzero(np.diff(ids) != 1) + 1
    return [g for g in np.split(ids, breaks) if len(g) >= 3]


def preprocess(raw, weights, detrend=True):
    """Training-only monthly climatology, then one linear trend per variable."""
    w = np.asarray(weights, float)
    v = raw.to_numpy()
    clim = np.stack([np.average(v[raw.index.month == m], axis=0,
                              weights=w[raw.index.month == m]) for m in range(1, 13)])
    anom = v - clim[raw.index.month - 1]
    t = original.decimal_time(raw.index)
    center = np.average(t, weights=w)
    design = np.column_stack([np.ones(len(t)), t-center])
    use = w > 0
    beta = np.zeros((2, v.shape[1]))
    if detrend:
        beta = np.linalg.lstsq(design[use] * np.sqrt(w[use, None]),
                              anom[use] * np.sqrt(w[use, None]), rcond=None)[0]
    background = clim[raw.index.month - 1] + design @ beta
    return pd.DataFrame(v-background, index=raw.index, columns=raw.columns), dict(
        clim=clim, trend=beta, center=center, detrend=detrend)


def background_at(meta, dates):
    design = np.column_stack([np.ones(len(dates)), original.decimal_time(dates)-meta['center']])
    return meta['clim'][dates.month-1] + design @ meta['trend']


def pool_moments(a, mask, order=2, weights=None):
    if weights is None:
        weights = np.asarray(mask, float)
    use = np.asarray(mask, bool)
    weights = np.asarray(weights, float)
    # Match ddof=0 standard deviation in the original implementation.
    avg = np.average(a.to_numpy()[use], weights=weights[use], axis=0)
    scale = np.sqrt(np.average((a.to_numpy()[use]-avg)**2, weights=weights[use], axis=0))
    assert np.all(scale > 1e-12)
    k, d = 2*order+1, a.shape[1]
    sums = {lag: [np.zeros((k,d,d)), np.zeros((k,d,d)),
                  np.zeros((k,k,d,d)), 0., 0] for lag in (1,6)}
    boundaries = []
    for ids in segments(a.index, use):
        z = a.iloc[ids].to_numpy()/scale
        grid = np.arange(0,(len(ids)-1)*6+1)/6
        x = np.column_stack([np.interp(grid, np.arange(len(z)), z[:,j]) for j in range(d)])
        first = a.index[ids[0]]
        t = first.year+(first.month-.5)/12+grid/12
        y = np.gradient(x,1/72,axis=0,edge_order=2)
        # Weight by the original monthly bin of the evaluation time. The actual
        # state/derivative/lag remain those of the unstitched chronological data.
        iw = weights[ids[np.minimum(np.floor(grid).astype(int),len(ids)-1)]]
        boundaries.append(dict(start=str(first.date()),end=str(a.index[ids[-1]].date()),months=len(ids)))
        for lag, acc in sums.items():
            ii = np.arange(max(lag,1),len(x)-1)
            phi = original.basis(t[ii],order)
            w = iw[ii]
            aa, bb, dy = x[ii], x[ii-lag], y[ii]
            acc[0] += np.einsum('n,nk,ni,nj->kij',w,phi,aa,bb,optimize=True)
            acc[1] += np.einsum('n,nk,ni,nj->kij',w,phi,dy,bb,optimize=True)
            acc[2] += np.einsum('n,nm,nk,ni,nj->mkij',w,phi,phi,aa,bb,optimize=True)
            acc[3] += w.sum()
            acc[4] += len(ii)
    pooled = {lag: tuple(v/acc[3] for v in acc[:3]) for lag,acc in sums.items()}
    return pooled, scale, dict(segments=boundaries,original_months=int(use.sum()),
        lag1_interpolated_count=sums[1][4],lag6_interpolated_count=sums[6][4])


def estimate_pooled(pooled, method='perturb2'):
    c0,g0,b0 = pooled[6]
    c,g,blocks = pooled[1]
    k,d = c.shape[:2]
    cc = np.empty((k*d,k*d)); gg = np.empty((d,k*d))
    for j in range(k):
        cj,gj,bj = (c0,g0,b0) if j == 0 else (c,g,blocks)
        gg[:,j*d:(j+1)*d] = gj[j]
        for m in range(k):
            cc[m*d:(m+1)*d,j*d:(j+1)*d] = bj[m,j]
    diag = dict(lag_cov_condition=float(max(np.linalg.cond(c[0]),np.linalg.cond(c0[0]))),
                full_moment_condition=float(np.linalg.cond(cc)))
    if method == 'exact':
        flat = np.linalg.solve(cc.T,gg.T).T
        coef = np.stack([flat[:,j*d:(j+1)*d] for j in range(k)])
        diag['second_first_norm_ratio'] = None
    elif method == 'perturb2':
        inv = np.linalg.inv(c[0]); mean = g0[0] @ np.linalg.inv(c0[0])
        first = np.zeros_like(c)
        for j in range(1,k):
            first[j] = 2*(g[j]-mean@c[j])@inv
        second = np.zeros_like(first)
        second[0] = -sum(first[m]@c[m] for m in range(1,k))@inv
        for j in range(1,k):
            second[j] = -2*(sum(first[m]@blocks[m,j] for m in range(1,k))-.5*first[j]@c[0])@inv
        coef = first+second
        coef[0] += mean
        flat = np.concatenate(list(coef),axis=1)
        diag.update(first_order_norm=float(np.linalg.norm(first)),second_order_norm=float(np.linalg.norm(second)),
                    second_first_norm_ratio=float(np.linalg.norm(second)/np.linalg.norm(first)))
    else:
        raise ValueError(method)
    diag['relative_moment_residual'] = float(np.linalg.norm(flat@cc-gg)/np.linalg.norm(gg))
    return coef,diag


def fit(a, mask, method='perturb2', order=2, weights=None):
    pooled,scale,diag = pool_moments(a,mask,order,weights)
    coef,diagnostics = estimate_pooled(pooled,method)
    return dict(coef=coef,scale=scale,order=order,method=method,columns=list(a.columns),
                interpolation='linear',diag={**diag,**diagnostics})


def propagators(model, month=1, months=12, steps=24):
    """Monthly physical-coordinate fundamental matrices, from one start time."""
    d = len(model['scale']); u = np.eye(d); ans = [u.copy()]
    dt = 1/(12*steps)
    ts = (month-.5)/12 + np.arange(months*steps*2+1)*dt/2
    ls = np.einsum('nk,kij->nij',original.basis(ts,model['order']),model['coef'])
    for k in range(months*steps):
        aa,bb,cc = ls[2*k:2*k+3]
        k1=aa@u; k2=bb@(u+dt*k1/2); k3=bb@(u+dt*k2/2); k4=cc@(u+dt*k3)
        u=u+dt*(k1+2*k2+2*k3+k4)/6
        if (k+1)%steps == 0:
            ans.append(u.copy())
    scale = model['scale']
    return np.array(ans)*scale[None,:,None]/scale[None,None,:]


def forecast(model, initial, months=11, month=1):
    return np.einsum('nij,j->ni',propagators(model,month,months),initial)
