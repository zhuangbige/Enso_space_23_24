#!/usr/bin/env python3
"""Download fixed-region monthly GODAS profiles and the 2026 ERSST update.
Public NOAA PSL NCSS; no substituted ocean index. Resume validated downloads.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, time, hashlib, json
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/godas/ro_baseline_20261014'
OUT.mkdir(parents=True,exist_ok=True)

def fetch(year):
    file=OUT/f'pottmp_{year}_5S5N_120E80W.nc'
    params=dict(var='pottmp',north=5.01,south=-5.01,west=119.99,east=280.01,disableProjSubset='on',horizStride=1,time_start=f'{year}-01-01T00:00:00Z',time_end=f'{year}-12-01T00:00:00Z',timeStride=1,accept='netcdf4')
    url=f'https://psl.noaa.gov/thredds/ncss/grid/Datasets/godas/pottmp.{year}.nc?'+urlencode(params)
    if not (file.exists() and file.stat().st_size>4096):
        session=requests.Session();session.trust_env=False
        for attempt in range(4):
            try:
                r=session.get(url,timeout=(30,240));r.raise_for_status()
                assert len(r.content)>4096 and r.content[:4] in (b'\x89HDF',b'CDF\x01',b'CDF\x02'),r.content[:100]
                file.with_suffix('.part').write_bytes(r.content);file.with_suffix('.part').replace(file)
                break
            except Exception:
                if attempt==3:raise
                time.sleep(2+attempt*3)
    data=file.read_bytes()
    print(year,round(len(data)/1e6,2),'MB',flush=True)
    return dict(year=year,path=str(file),url=url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        records=[f.result() for f in as_completed([pool.submit(fetch,y) for y in range(1980,2027)])]
    (OUT/'download_manifest.json').write_text(json.dumps(sorted(records,key=lambda x:x['year']),indent=2))
    session=requests.Session();session.trust_env=False
    params=dict(var='sst',north=5,south=-5,west=190,east=240,disableProjSubset='on',horizStride=1,time_start='2026-01-01T00:00:00Z',time_end='2026-12-01T00:00:00Z',accept='netcdf4')
    url='https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.ersst.v5/sst.mnmean.nc?'+urlencode(params)
    r=session.get(url,timeout=(30,240));r.raise_for_status();assert r.content[:4]==b'\x89HDF'
    file=OUT/'ersstv5_nino34_2026.nc';file.write_bytes(r.content)
    (OUT/'ersst_update_manifest.json').write_text(json.dumps(dict(url=url,sha256=hashlib.sha256(r.content).hexdigest()),indent=2))
    print('ERSST update',len(r.content),flush=True)
