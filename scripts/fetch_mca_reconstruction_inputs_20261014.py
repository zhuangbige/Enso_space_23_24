"""Download archived R1 controls and ERA5 monthly PMM reconstruction fields."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('PMM_DOWNLOAD_DIR',ROOT / 'data/raw/pmm_mca_reconstruction_20261014'))
OUT.mkdir(parents=True, exist_ok=True)


def record(path, spec):
    data = dict(spec, file=path.name, bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                retrieved_utc=datetime.now(timezone.utc).isoformat())
    path.with_suffix(path.suffix + '.json').write_text(json.dumps(data, indent=2))


def r1(var):
    name = {'skt':'skt.sfc.mon.mean.nc','uwnd':'uwnd.10m.mon.mean.nc',
            'vwnd':'vwnd.10m.mon.mean.nc','land':'land.sfc.gauss.nc'}[var]
    base = 'https://psl.noaa.gov/thredds/'
    target = OUT / ('r1_' + name)
    if target.exists():
        print('exists', target.name, flush=True); return
    path = 'Datasets/' + ('ncep.reanalysis' if var == 'land' else 'ncep.reanalysis.derived') + '/surface_gauss/' + name
    url = base + ('fileServer/' if var == 'land' else 'ncss/grid/') + path
    params = None if var == 'land' else dict(var=var, north=34, south=-23,
        west=172, east=273, time_start='1950-01-01T00:00:00Z',
        time_end='2026-02-01T00:00:00Z', accept='netcdf4')
    s = requests.Session(); s.trust_env = False
    r = s.get(url, params=params, timeout=(30, 180)); r.raise_for_status()
    assert r.content[:3] == b'CDF' or r.content[:4] == b'\x89HDF'
    target.write_bytes(r.content)
    record(target, dict(url=r.url, last_modified=r.headers.get('Last-Modified')))
    print('downloaded', target.name, target.stat().st_size, flush=True)


def era5(month):
    import cdsapi
    target = OUT / f'era5_sst_uv10_month{month:02d}_1950_2026.grib'
    if target.exists() and target.with_suffix('.grib.json').exists():
        print('exists', target.name, flush=True); return
    spec = dict(product_type=['monthly_averaged_reanalysis'],
        variable=['sea_surface_temperature','10m_u_component_of_wind','10m_v_component_of_wind'],
        year=[str(y) for y in range(1950, 2027 if month <= 9 else 2026)],
        month=[f'{month:02d}'], time=['00:00'], area=[34,-180,-24,180],
        grid=[1.875,1.875], data_format='grib', download_format='unarchived')
    ds = 'reanalysis-era5-single-levels-monthly-means'
    target.with_suffix('.request.json').write_text(json.dumps(dict(dataset=ds, request=spec), indent=2))
    cdsapi.Client(quiet=True, progress=False).retrieve(ds, spec, str(target))
    record(target, dict(dataset=ds, request=spec))
    print('downloaded', target.name, target.stat().st_size, flush=True)


def ersst():
    target=OUT/'ersstv5_pmm_sst_1950_2026.nc'
    if target.exists() and target.with_suffix('.nc.json').exists(): return
    url='https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.ersst.v5/sst.mnmean.nc'
    params=dict(var='sst',north=36,south=-26,west=168,east=278,
        time_start='1950-01-01T00:00:00Z',time_end='2026-09-01T00:00:00Z',accept='netcdf4')
    session=requests.Session();session.trust_env=False
    response=session.get(url,params=params,timeout=(30,150));response.raise_for_status()
    assert response.content[:4]==b'\x89HDF'
    target.write_bytes(response.content);record(target,dict(url=response.url))
    print('downloaded',target.name,target.stat().st_size,flush=True)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=['r1','era5','ersst'], required=True)
    args = p.parse_args()
    if args.source=='ersst': ersst(); return
    with ThreadPoolExecutor(max_workers=3 if args.source=='r1' else 1) as ex:
        jobs = {ex.submit(r1 if args.source == 'r1' else era5, v):v for v in
                (['skt','uwnd','vwnd','land'] if args.source == 'r1' else range(1,13))}
        failed = []
        for job in as_completed(jobs):
            try: job.result()
            except Exception as error:
                failed.append(str(jobs[job])); print('FAILED', jobs[job], type(error).__name__, str(error), flush=True)
        if failed: raise SystemExit('Failed: ' + ','.join(failed))


if __name__ == '__main__': main()
