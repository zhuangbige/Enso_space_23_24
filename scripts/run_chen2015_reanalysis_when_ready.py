"""Current-turn batch runner; waits only for this task's active download jobs."""
import time,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw/chen2015_reanalysis_20261014';OUT=ROOT/'outputs/research_2026/chen2015_reanalysis_20261014'
import analyze_chen2015_reanalysis as a
while True:
 missing=[]
 for year in range(1980,2025):
  if not all((RAW/f'{n}_{year}.npz').exists() for n in ['soda3_sigma26_inputs','soda3_deep_west']):missing.append(year);continue
  p=OUT/f'monthly_raw_{year}.csv';q=OUT/f'qa_{year}.json'
  if not p.exists() or not q.exists():
   d,info=a.year_diagnostics(year);d.to_csv(p,index=False);q.write_text(a.json.dumps(info,indent=2));print('Calculated',year,flush=True)
 if not missing:break
 print('Waiting for remaining input years:',missing,flush=True);time.sleep(30)
for name in ['analyze_chen2015_reanalysis.py','report_chen2015_reanalysis.py','export_chen2015_reanalysis.py','plot_chen2015_reanalysis.py']:
 print('RUN',name,flush=True);subprocess.run([sys.executable,str(ROOT/'scripts'/name)],check=True)
print('ALL CALCULATIONS AND FIGURES COMPLETE',flush=True)
