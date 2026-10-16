#!/usr/bin/env python3
"""Explicit Chen & Jin (2021) seasonal LIM, Eqs. A5--A7.

Interpolated 72-step year; annual + semiannual harmonics by default.
Deterministic integration, no observed forcing after initialization.
"""
import numpy as np
import pandas as pd

def basis(t,order=2):
    t=np.atleast_1d(t)
    return np.column_stack([np.ones(len(t))]+[np.cos(2*np.pi*n*t) for n in range(1,order+1)]+[np.sin(2*np.pi*n*t) for n in range(1,order+1)])

def decimal_time(index):
    return index.year.to_numpy()+(index.month.to_numpy()-.5)/12

def moments(x,y,t,lag,order):
    # Common time support, with centered derivatives already finite.
    ids=np.arange(max(lag,1),len(x)-1)
    a=x[ids];b=x[ids-lag];d=y[ids];phi=basis(t[ids],order)
    c=np.einsum('nk,ni,nj->kij',phi,a,b)/len(ids)
    g=np.einsum('nk,ni,nj->kij',phi,d,b)/len(ids)
    blocks=np.einsum('nm,nk,ni,nj->mkij',phi,phi,a,b)/len(ids)
    return c,g,blocks

def estimate(x,y,t,order=2,method='perturb2',lag_mean=6,lag_season=1):
    c0,g0,b0=moments(x,y,t,lag_mean,order)
    c,g,blocks=moments(x,y,t,lag_season,order)
    k=len(c);dim=x.shape[1]
    if method=='exact':
        cc=np.empty((k*dim,k*dim));gg=np.empty((dim,k*dim))
        for j in range(k):
            cj,gj,bj=(c0,g0,b0) if j==0 else (c,g,blocks)
            gg[:,j*dim:(j+1)*dim]=gj[j]
            for m in range(k):cc[m*dim:(m+1)*dim,j*dim:(j+1)*dim]=bj[m,j]
        flat=np.linalg.solve(cc.T,gg.T).T
        coef=np.stack([flat[:,j*dim:(j+1)*dim] for j in range(k)])
        return coef,dict(condition=float(np.linalg.cond(cc)))
    assert method=='perturb2'
    inv=np.linalg.inv(c[0]);mean=g0[0]@np.linalg.inv(c0[0])
    first=np.zeros((k,dim,dim))
    for j in range(1,k):first[j]=2*(g[j]-mean@c[j])@inv
    second=np.zeros_like(first)
    second[0]=-sum(first[m]@c[m] for m in range(1,k))@inv
    for j in range(1,k):
        second[j]=-2*(sum(first[m]@blocks[m,j] for m in range(1,k))-.5*first[j]@c[0])@inv
    coef=first+second;coef[0]+=mean
    return coef,dict(condition=float(max(np.linalg.cond(c[0]),np.linalg.cond(c0[0]))),
                     second_order_norm=float(np.linalg.norm(second)),first_order_norm=float(np.linalg.norm(first)))

def fit(a,order=2,method='perturb2',interpolation='linear'):
    assert a.index.equals(pd.date_range(a.index[0],a.index[-1],freq='MS'))
    assert np.isfinite(a.to_numpy()).all()
    scale=a.std(ddof=0).to_numpy();assert (scale>0).all()
    monthly=a.to_numpy()/scale
    # Use integer month coordinates to avoid floating-point endpoint drift.
    grid=np.arange(0,(len(a)-1)*6+1)/6
    if interpolation=='linear':
        x=np.stack([np.interp(grid,np.arange(len(a)),monthly[:,j]) for j in range(a.shape[1])],axis=1)
    elif interpolation=='cubic':
        from scipy.interpolate import CubicSpline
        x=CubicSpline(np.arange(len(a)),monthly,axis=0)(grid)
    else:raise ValueError(interpolation)
    t=a.index[0].year+(a.index[0].month-.5)/12+grid/12
    y=np.gradient(x,1/72,axis=0,edge_order=2)
    coef,diag=estimate(x,y,t,order=order,method=method)
    return dict(coef=coef,scale=scale,order=order,method=method,interpolation=interpolation,diag=diag,columns=list(a.columns))

def predict(model,initial,month,months=12,steps=24,cut_pmm=False):
    coef=model['coef'].copy();scale=model['scale'];order=model['order']
    if cut_pmm:coef[:,:2,2:]=0
    y=np.array(initial,dtype=float)/scale
    phase=(month-.5)/12
    dt=1/(12*steps);traj=[y.copy()]
    # Precompute all coefficient matrices for RK4.
    ts=phase+np.arange(months*steps*2+1)*dt/2
    ls=np.einsum('nk,kij->nij',basis(ts,order),coef)
    for k in range(months*steps):
        a,b,c=ls[2*k],ls[2*k+1],ls[2*k+2]
        k1=a@y;k2=b@(y+dt*k1/2);k3=b@(y+dt*k2/2);k4=c@(y+dt*k3)
        y=y+dt*(k1+2*k2+2*k3+k4)/6
        if (k+1)%steps==0:traj.append(y.copy())
    return np.array(traj)*scale

def numerical_qa():
    # Known seasonal system on a rich deterministic state set: test exact
    # covariance algebra against prescribed derivatives, independent of fit().
    rng=np.random.default_rng(714);t=np.arange(3600)/72
    x=rng.normal(size=(len(t),3));order=2
    truth=rng.normal(size=(5,3,3))*.08;truth[0]-=np.eye(3)*.2
    y=np.einsum('nk,kij,nj->ni',basis(t,order),truth,x)
    # Zero-lag moments give a well-conditioned exact identification test.
    fitted,diag=estimate(x,y,t,order,'exact',0,0)
    error=float(np.max(abs(fitted-truth)));assert error<1e-10
    # Perturbation formula is an approximation, not an exact solver.
    fitted2,_=estimate(x,y,t,order,'perturb2',0,0)
    approx=float(np.max(abs(fitted2-truth)));assert approx<.02
    m=dict(coef=truth,scale=np.ones(3),order=2)
    a=predict(m,np.array([1,.5,-.4]),3,steps=24)
    b=predict(m,np.array([1,.5,-.4]),3,steps=48)
    diff=float(abs(a-b).max());assert diff<1e-7
    return dict(exact_known_operator_max_error=error,perturbation_known_operator_max_error=approx,rk4_24_vs_48_synthetic=diff)
