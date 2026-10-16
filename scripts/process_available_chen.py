import analyze_chen2015_reanalysis as a
for year in range(1980,2025):
 p=a.OUT/f'monthly_raw_{year}.csv';q=a.OUT/f'qa_{year}.json'
 if p.exists() and q.exists():continue
 if not all((a.RAW/f'{n}_{year}.npz').exists() for n in ['soda3_sigma26_inputs','soda3_deep_west']):continue
 d,info=a.year_diagnostics(year);d.to_csv(p,index=False);q.write_text(a.json.dumps(info,indent=2));print('Computed',year,'WWV min/max (1e15 m3)',d.chen_basin_wwv_m3.min()/1e15,d.chen_basin_wwv_m3.max()/1e15,flush=True)
