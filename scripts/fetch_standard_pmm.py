#!/usr/bin/env python3
"""Archive published PMM-SST / PMM-wind, including source metadata."""
from pathlib import Path
import datetime, hashlib, json, requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/climate_indices/standard_pmm_20261014'
URLS={
    'PMM_uw.txt':'https://www.aos.wisc.edu/dvimont/MModes/RealTime/PMM.txt',
    'pmm_sst_noaa.data':'https://psl.noaa.gov/data/timeseries/month/data/pmm.data',
    'pmm_wind_noaa.data':'https://psl.noaa.gov/data/timeseries/month/data/pmmwind.data',
    'method_uw.html':'https://www.aos.wisc.edu/dvimont/MModes/PMM.html',
}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    session=requests.Session();session.trust_env=False
    manifest=[]
    for name,url in URLS.items():
        response=session.get(url,timeout=60);response.raise_for_status()
        payload=response.content
        assert len(payload)>500
        (OUT/name).write_bytes(payload)
        manifest.append(dict(file=name,url=url,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                             retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                             last_modified=response.headers.get('Last-Modified')))
        print(name,len(payload),response.text.splitlines()[-8:],flush=True)
    (OUT/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
