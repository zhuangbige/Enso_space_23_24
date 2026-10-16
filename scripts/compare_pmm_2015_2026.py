"""Compare archived PMM-like indices and independently observed SST/wind fields.

Reuses the original 1982-2025 preprocessing and saved EOF patterns without
refitting the mode. Outputs are separate from the original PMM analysis.
"""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/pmm_2015_2026_comparison_20261014'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/pmm_compare_mpl'))
sys.path.insert(0, str(ROOT / 'scripts'))
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import plot_pmm_index_eof as original

original.open_netcdf = lambda p: xr.open_dataset(p, engine='netcdf4')
print('Loading existing SST and 10 m wind data', flush=True)
sst_raw = original.load_sst().load()
wind_raw = original.load_wind(sst_raw.lat, sst_raw.lon).load()
times = np.intersect1d(sst_raw.time.values, wind_raw.time.values)
sst_raw = sst_raw.sel(time=times)
wind_raw = wind_raw.sel(time=times)
training = (sst_raw.time.dt.year.values >= 1982) & (sst_raw.time.dt.year.values <= 2025)
assert training.sum() == 528
assert len(np.unique(times)) == len(times)
fields = [original.monthly_anomaly_detrend(a, training) for a in
          [sst_raw, wind_raw.u10, wind_raw.v10]]
n34 = original.area_mean(fields[0], lat0=-5, lat1=5, lon0=190, lon1=240)
residual = [original.remove_linear_index(a, n34, training) for a in fields]
saved = np.load(original.FIELDS_NPZ)
assert np.array_equal(saved['time'], times)
assert np.allclose(saved['lat'], sst_raw.lat)
assert np.allclose(saved['lon'], sst_raw.lon)
index = pd.read_csv(original.INDEX_CSV, parse_dates=['time'])
assert np.array_equal(index.time.values, times)

# A regression pattern against the standardized PC is proportional to its EOF
# after applying exactly the field scaling and area weighting used originally.
# This allows an exact algebraic projection decomposition, not causal attribution.
matrix, train_matrix, masks, scales = original.build_matrix(residual, training)
weights = np.broadcast_to(np.sqrt(np.cos(np.deg2rad(sst_raw.lat.values)))[:, None], masks[0].shape)
pattern = np.concatenate([saved[k][mask] * weights[mask] / scale for k, mask, scale in
                          zip(['sst_joint', 'u_joint', 'v_joint'], masks, scales)])
eof = pattern / np.linalg.norm(pattern)
projection = matrix @ eof
pc_std = projection[training].std(ddof=1)
reconstructed = (projection - projection[training].mean()) / pc_std
pc_error = float(np.max(np.abs(reconstructed - index.pmm_joint_sst_wind.values)))
assert pc_error < 2e-5, pc_error
offset = 0
for name, mask in zip(['sst', 'u10', 'v10'], masks):
    count = int(mask.sum())
    part = matrix[:, offset:offset+count] @ eof[offset:offset+count]
    index['joint_projection_' + name] = (part - part[training].mean()) / pc_std
    offset += count
index['joint_projection_wind'] = index.joint_projection_u10 + index.joint_projection_v10
assert np.max(np.abs(index[['joint_projection_sst', 'joint_projection_wind']].sum(axis=1) - reconstructed)) < 1e-10

# Lin et al. (2025) uses this box SST index, not the official MCA or our EOF PC.
for name, fld in [('sst_c', fields[0]), ('sst_residual_c', residual[0]),
                  ('u10_ms', fields[1]), ('v10_ms', fields[2]),
                  ('u10_residual_ms', residual[1]), ('v10_residual_ms', residual[2])]:
    index['ne_box_' + name] = original.area_mean(fld, lat0=15, lat1=25, lon0=210, lon1=240).values
index['nino34_used_for_removal_c'] = n34.values
index.to_csv(OUT / 'monthly_diagnostics_1982_2026.csv', index=False)
focus = index[index.year.isin([1997, 2015, 2023, 2026]) & index.month.le(5)].copy()
focus.to_csv(OUT / 'monthly_comparison_jan_may.csv', index=False)
summaries = []
value_cols = ['pmm_joint_sst_wind', 'pmm_sst_only', 'joint_projection_sst',
              'joint_projection_wind', 'ne_box_sst_c', 'ne_box_sst_residual_c',
              'ne_box_u10_ms', 'ne_box_v10_ms', 'ne_box_u10_residual_ms', 'ne_box_v10_residual_ms']
for year in [1997, 2015, 2023, 2026]:
    for label, months in [('Jan-May', [1,2,3,4,5]), ('JFM', [1,2,3]), ('FMA', [2,3,4]), ('MAM', [3,4,5])]:
        selected = focus[(focus.year == year) & focus.month.isin(months)]
        assert len(selected) == len(months)
        summaries.append({'year': year, 'season': label, **selected[value_cols].mean().to_dict()})
summary = pd.DataFrame(summaries)
summary.to_csv(OUT / 'seasonal_comparison.csv', index=False)

def composite(fld, year, months=(3,4,5)):
    return fld.sel(time=(fld.time.dt.year == year) & fld.time.dt.month.isin(months)).mean('time')

def spatial_metrics(a, b, lat0, lat1, lon0, lon1):
    a = a.sel(lat=slice(lat0,lat1), lon=slice(lon0,lon1))
    b = b.sel(lat=slice(lat0,lat1), lon=slice(lon0,lon1))
    weight = np.broadcast_to(np.cos(np.deg2rad(a.lat.values))[:,None], a.shape)
    mask = np.isfinite(a.values) & np.isfinite(b.values)
    x, y, w = a.values[mask], b.values[mask], weight[mask]
    w = w / w.sum()
    xc, yc = x - np.sum(w*x), y - np.sum(w*y)
    return {'centered_pattern_r': float(np.sum(w*xc*yc) / np.sqrt(np.sum(w*xc**2)*np.sum(w*yc**2))),
            'rms_difference_c': float(np.sqrt(np.sum(w*(x-y)**2))), 'gridpoints': int(mask.sum())}

spatial = []
for label, group in [('detrended_anomaly', fields), ('nino34_removed_residual', residual)]:
    for region, bounds in [('original_domain', (-20,30,120,280)),
                           ('north_pacific_sector', (0,30,175,275)),
                           ('lin_npmm_box', (15,25,210,240))]:
        spatial.append({'field': label, 'region': region, 'season': 'MAM',
                        **spatial_metrics(composite(group[0],2015), composite(group[0],2026), *bounds)})
pd.DataFrame(spatial).to_csv(OUT / 'sst_spatial_comparison.csv', index=False)

plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'axes.titlesize':13,
                     'axes.labelsize':11, 'savefig.dpi':300, 'axes.spines.top':False,
                     'axes.spines.right':False})
colors = {2015:'#d27013', 2026:'#125fab', 2023:'#777777'}
fig, axs = plt.subplots(1,2,figsize=(12,4.5),sharey=True)
for ax, col, title in zip(axs, ['pmm_joint_sst_wind','pmm_sst_only'],
                          ['Joint SST + wind EOF index', 'SST-only EOF index']):
    ax.axhline(0,color='#333333',lw=.8)
    ax.axvspan(2.8,5.2,color='#f2f2f2',zorder=0)
    for year in [2015,2026,2023]:
        part = focus[focus.year == year]
        mam = part.loc[part.month.isin([3,4,5]),col].mean()
        ax.plot(part.month,part[col],color=colors[year],marker='o',lw=2.3 if year!=2023 else 1.5,
                ls='-' if year!=2023 else '--',label=f'{year}   MAM {mam:+.2f}')
    ax.set(title=title,xlim=(.8,5.2),ylim=(-1.9,2.9),xticks=range(1,6),xticklabels=['Jan','Feb','Mar','Apr','May'])
    ax.grid(axis='y',alpha=.17)
    ax.legend(loc='upper right',fontsize=10,frameon=False)
axs[0].set_ylabel('Standardized monthly index')
fig.suptitle('Local PMM-like indices in 2015 and 2026',fontsize=15,y=.98)
fig.subplots_adjust(left=.07,right=.985,bottom=.18,top=.82,wspace=.13)
fig.text(.07,.035,'OISST + ERA5 | Fixed 1982–2025 EOFs | Linear trend and Niño-3.4 removed\nCommon window: January–May. Shading marks MAM. Local diagnostics, not the official PMM indices.',fontsize=9,color='#444444')
for ext in ['png','pdf']: fig.savefig(OUT/f'pmm_indices_2015_2026.{ext}',bbox_inches='tight')
plt.close(fig)

fig = plt.figure(figsize=(13.5,8.0))
proj = ccrs.PlateCarree(central_longitude=180)
trans = ccrs.PlateCarree()
axes = []
for row, year in enumerate([2015,2026]):
    for col, (name, group) in enumerate([('Detrended SST and wind anomalies',fields),('After linear Niño-3.4 removal',residual)]):
        ax = fig.add_subplot(2,2,2*row+col+1,projection=proj)
        axes.append(ax)
        s,u,v = [composite(f,year) for f in group]
        mesh = ax.pcolormesh(s.lon,s.lat,s,cmap='RdBu_r',vmin=-1.5,vmax=1.5,shading='auto',transform=trans,rasterized=True)
        ocean = np.isfinite(s)
        q = ax.quiver(u.lon.values[::7],u.lat.values[::4],u.where(ocean).values[::4,::7],v.where(ocean).values[::4,::7],
                      transform=trans,scale=32,width=.0028,headwidth=3.2,color='#242424')
        ax.quiverkey(q,.85,-.13,2,'2 m s$^{-1}$',coordinates='axes',labelpos='E',fontproperties={'size':9})
        ax.set_extent([120,280,-20,30],crs=trans)
        ax.add_feature(cfeature.LAND.with_scale('110m'),facecolor='#dfdfdf',zorder=3)
        ax.coastlines(resolution='110m',linewidth=.55,zorder=4)
        ax.plot([210,240,240,210,210],[15,15,25,25,15],transform=trans,color='#5c1477',lw=1.4,zorder=5)
        ax.text(211,26.5,'NPMM SST box',transform=trans,color='#5c1477',fontsize=8.5)
        gl = ax.gridlines(draw_labels=True,linewidth=.4,alpha=.2,xlocs=[-140,-100,120,160,180],ylocs=[-20,0,15,30])
        gl.top_labels=False;gl.right_labels=False
        gl.xlabel_style={'size':9};gl.ylabel_style={'size':9}
        box_name = 'ne_box_sst_c' if col==0 else 'ne_box_sst_residual_c'
        box_value = summary[(summary.year==year)&(summary.season=='MAM')][box_name].iloc[0]
        ax.set_title(f'({"abcd"[2*row+col]}) MAM {year} | {name}\nBox-mean SST: {box_value:+.2f}°C',fontsize=11.5,pad=10)
fig.subplots_adjust(left=.055,right=.965,bottom=.22,top=.86,hspace=.4,wspace=.12)
cax=fig.add_axes([.30,.12,.40,.020])
fig.colorbar(mesh,cax=cax,orientation='horizontal',label='SST anomaly or residual (°C)')
fig.suptitle('North Pacific SST–wind structure: 2015 versus 2026',fontsize=16,y=.97)
fig.text(.5,.915,'March–May means | OISST SST and ERA5 10 m winds | Identical color and vector scales',ha='center',fontsize=11)
fig.text(.055,.015,'1982–2025 monthly climatology and linear detrending. Right column removes the fitted concurrent Niño-3.4 signal.\nPurple box: 15–25°N, 150–120°W (Lin et al., 2025 region; OISST implementation). These are event fields, not EOF reconstructions.',fontsize=9,color='#444444')
for ext in ['png','pdf']:fig.savefig(OUT/f'pmm_spatial_MAM_2015_2026.{ext}',bbox_inches='tight')
plt.close(fig)

# Compact version for a presentation: actual ENSO-residual event maps only.
fig, axs = plt.subplots(1,2,figsize=(13,4.8),subplot_kw={'projection':proj})
for ax, year in zip(axs,[2015,2026]):
    s,u,v = [composite(f,year) for f in residual]
    mesh=ax.pcolormesh(s.lon,s.lat,s,cmap='RdBu_r',vmin=-1.5,vmax=1.5,shading='auto',transform=trans,rasterized=True)
    ocean=np.isfinite(s)
    q=ax.quiver(u.lon.values[::7],u.lat.values[::4],u.where(ocean).values[::4,::7],v.where(ocean).values[::4,::7],
                transform=trans,scale=32,width=.003,headwidth=3.2,color='#242424')
    ax.quiverkey(q,.73,-.17,2,'2 m s$^{-1}$',coordinates='axes',labelpos='E',fontproperties={'size':9})
    ax.set_extent([120,280,-10,30],crs=trans)
    ax.add_feature(cfeature.LAND.with_scale('110m'),facecolor='#dfdfdf',zorder=3)
    ax.coastlines(resolution='110m',linewidth=.55,zorder=4)
    ax.plot([210,240,240,210,210],[15,15,25,25,15],transform=trans,color='#5c1477',lw=1.5,zorder=5)
    gl=ax.gridlines(draw_labels=True,linewidth=.4,alpha=.2,xlocs=[-140,-100,120,160,180],ylocs=[0,15,30])
    gl.top_labels=False;gl.right_labels=False
    gl.xlabel_style={'size':9};gl.ylabel_style={'size':9}
    row=summary[(summary.year==year)&(summary.season=='MAM')].iloc[0]
    ax.set_title(f'March–May {year}\nLocal joint EOF index: {row.pmm_joint_sst_wind:+.2f}',fontsize=12,pad=10)
fig.subplots_adjust(left=.055,right=.97,bottom=.27,top=.78,wspace=.13)
fig.suptitle('A shared warm northeast-Pacific pattern in spring 2015 and 2026',fontsize=15,y=.99)
fig.text(.5,.91,'OISST SST and ERA5 10 m winds after linear Niño-3.4 removal',ha='center',fontsize=11)
cax=fig.add_axes([.31,.16,.38,.035])
fig.colorbar(mesh,cax=cax,orientation='horizontal',label='SST residual (°C)')
fig.text(.055,.018,'Baseline and EOF training: 1982–2025. Purple box: 15–25°N, 150–120°W. Arrows show wind residuals.\nActual event fields, not EOF reconstructions. Shared phase does not establish an identical mechanism or eventual event strength.',fontsize=8.8,color='#444444')
for ext in ['png','pdf']:fig.savefig(OUT/f'pmm_spatial_MAM_presentation.{ext}',bbox_inches='tight')
plt.close(fig)

selected = (sst_raw.time.dt.year.isin([2015,2023,2026])) & (sst_raw.time.dt.month<=5)
xr.Dataset({**{k:v.sel(time=selected) for k,v in zip(['sst_anomaly','u10_anomaly','v10_anomaly'],fields)},
            **{k:v.sel(time=selected) for k,v in zip(['sst_residual','u10_residual','v10_residual'],residual)}}).to_netcdf(OUT/'comparison_fields.nc')
meta = {
    'analysis_date':'2026-10-14','data_end':'2026-05','training_period':'1982-2025',
    'method':'Original local joint EOF and SST-only EOF; monthly climatology removed, one linear trend fitted across all training months, concurrent linear Niño-3.4 signal removed; sqrt(cos(lat)) area weighting; each variable scaled by its global training standard deviation.',
    'joint_index_reconstruction_max_abs_error':pc_error,
    'projection_components':'Exact linear contributions to the existing EOF score, not causal percentages.',
    'spatial_statistics':'Descriptive area-weighted centered SST pattern correlations; no gridpoint independence or significance claimed.',
    'lin_box':'15-25N, 150-120W. Uses OISST here, versus ERSSTv5 in Lin et al.; not an exact paper replication.',
    'official_pmm':'Official PMM uses SST-wind maximum covariance analysis. Local joint EOF and independent SST-only EOF are different definitions.',
    'sources':['https://www.nature.com/articles/s41612-025-01013-z','https://psl.noaa.gov/data/timeseries/month/PMM/'],
    'legacy_report':str(ROOT/'outputs/research_2026/reports/enso_event_comparison_unified_1980_2014_en_final_event_groups.docx'),
    'legacy_script':str(ROOT/'scripts/plot_pmm_index_eof.py'),
}
(OUT/'method_and_validation.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False))
print(summary[(summary.year.isin([2015,2023,2026])) & (summary.season.isin(['MAM','Jan-May']))].round(4).to_string(index=False),flush=True)
print('Spatial comparison:',json.dumps(spatial,indent=2),flush=True)
print('Projection reconstruction max error:',pc_error,flush=True)
print('Outputs:',OUT,flush=True)
