"""Archive current public data for the frozen manuscript-period 2026 experiment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/raw/ro_pmm_2026_update_20261014'
BASE = 'https://psl.noaa.gov/thredds/ncss/grid/Datasets/'
TIME = dict(time_start='2026-01-01T00:00:00Z', time_end='2026-12-01T00:00:00Z',
            disableProjSubset='on', horizStride=1, accept='netcdf4')
ITEMS = [
    ('PMM_uw.txt', 'https://www.aos.wisc.edu/dvimont/MModes/RealTime/PMM.txt', None),
    ('pmm_sst_noaa.data', 'https://psl.noaa.gov/data/timeseries/month/data/pmm.data', None),
    ('pmm_wind_noaa.data', 'https://psl.noaa.gov/data/timeseries/month/data/pmmwind.data', None),
    ('pmm_source_page.html', 'https://www.aos.wisc.edu/dvimont/MModes/Data.html', None),
    ('godas_metadata.xml', BASE + 'godas/pottmp.2026.nc/dataset.xml', None),
    ('ersst_metadata.xml', BASE + 'noaa.ersst.v5/sst.mnmean.nc/dataset.xml', None),
    ('pottmp_2026_5S5N_120E80W.nc', BASE + 'godas/pottmp.2026.nc',
     dict(TIME, var='pottmp', north=5.01, south=-5.01, west=119.99, east=280.01)),
    ('ersstv5_nino34_2026.nc', BASE + 'noaa.ersst.v5/sst.mnmean.nc',
     dict(TIME, var='sst', north=5, south=-5, west=190, east=240)),
]


def fetch(item):
    name, url, params = item
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, params=params, timeout=(20, 60))
    response.raise_for_status()
    payload = response.content
    assert len(payload) > 500
    if name.endswith('.nc'):
        assert payload[:3] == b'CDF' or payload[:4] == b'\x89HDF', response.text[:200]
    (OUT / name).write_bytes(payload)
    record = dict(file=name, url=response.url, sha256=hashlib.sha256(payload).hexdigest(),
                  bytes=len(payload), retrieved_utc=datetime.now(timezone.utc).isoformat(),
                  last_modified=response.headers.get('Last-Modified'))
    print(name, len(payload), flush=True)
    return record


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        jobs = [(item[0], executor.submit(fetch, item)) for item in ITEMS]
        records = []
        for name, job in jobs:
            try:
                records.append(job.result())
            except Exception as error:
                records.append(dict(file=name, error=f'{type(error).__name__}: {error}'))
                print('FAILED', name, str(error), flush=True)
    (OUT / 'source_manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    required = {'PMM_uw.txt', 'pottmp_2026_5S5N_120E80W.nc', 'ersstv5_nino34_2026.nc'}
    assert not any(r['file'] in required and 'error' in r for r in records)


if __name__ == '__main__':
    main()
