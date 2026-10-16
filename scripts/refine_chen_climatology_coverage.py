"""Require all 43 baseline years for local two-term field climatologies."""
import analyze_chen2015_reanalysis as a,numpy as np,json
p=a.RAW/'field_climatology_1980_2022.npz';cl=dict(np.load(p));counts={k:np.zeros_like(cl[k],dtype='int8') for k in ['temp','salt','u','v']}
for y in range(1980,2023):
 d=a.load_inputs(y)
 for k in counts:counts[k]+=np.isfinite(d[k]).astype('int8')
for k,n in counts.items():cl[k]=np.where(n==43,cl[k],np.nan)
np.savez_compressed(a.RAW/'field_climatology_1980_2022_complete_wet_mask.npz',**cl)
np.savez_compressed(a.RAW/'field_climatology_valid_year_counts.npz',**counts)
print('Complete 43-year field mask saved',flush=True)
