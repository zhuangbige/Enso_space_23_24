"""Fetch or verify the frozen public NCEP flux used in the PMM evidence report.

ERA5 wind is reused locally; the cancelled CDS flux attempt is archived in
data/raw/era5/pmm_wind_flux_20261015/. No CDS requests are resumed here.
"""
from pathlib import Path
import hashlib
import json
import requests

ROOT=Path(__file__).resolve().parents[1]


def main():
    target=ROOT/'data/raw/ncep_pmm_flux_20261015/lhtfl.sfc.mon.mean.nc'
    meta=target.with_suffix('.json')
    if target.exists() and meta.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest()==json.loads(meta.read_text())['sha256']
        print('Verified frozen NCEP file',flush=True)
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    url='https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis.derived/surface_gauss/lhtfl.sfc.mon.mean.nc'
    response=requests.get(url,stream=True,timeout=(30,120));response.raise_for_status()
    partial=target.with_suffix('.partial')
    with partial.open('wb') as stream:
        for block in response.iter_content(1024*1024):stream.write(block)
    partial.replace(target)
    meta.write_text(json.dumps(dict(url=url,bytes=target.stat().st_size,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest()),indent=2))
    print('Downloaded NCEP flux',target.stat().st_size,flush=True)


if __name__ == "__main__":
    main()
