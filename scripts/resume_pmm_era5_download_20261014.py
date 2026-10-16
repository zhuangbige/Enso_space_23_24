"""Resume this task's existing CDS jobs, then fetch the remaining months serially.

This only archives data. It does not replace the validated ERSSTv5 analysis.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import os
import json
import shutil
from datetime import datetime, timezone

PENDING={1:'7d0fa877-167b-41fc-922e-506c82f63aa4',
    3:'c81a0775-33ed-4c2c-b267-30f4c8a29987',
    4:'f4d5ba5a-741b-4572-b8c7-f355028e6369',
    11:'ee0fcd53-f88c-479b-bf49-a528cce7f83f',
    12:'bb96dc20-35ec-4bd6-b205-7870a516d880'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive-root',type=Path,required=True)
    args=p.parse_args()
    import cdsapi
    import fetch_mca_reconstruction_inputs_20261014 as download
    archive=args.archive_root/'data/raw/pmm_mca_reconstruction_20261014'
    archive.mkdir(parents=True,exist_ok=True)
    state=dict(started_utc=datetime.now(timezone.utc).isoformat(),pending_jobs=PENDING,
               completed_months=[],failed_months={},status='running')
    def save():
        (archive/'era5_download_status.json').write_text(json.dumps(state,indent=2))
    def archive_month(month):
        src=download.OUT/f'era5_sst_uv10_month{month:02d}_1950_2026.grib'
        for file in [src,src.with_suffix('.grib.json')]:
            if file.resolve()!=(archive/file.name).resolve():shutil.copyfile(file,archive/file.name)
        state['completed_months'].append(month);save()
    def resume(month,job):
        client=cdsapi.Client(quiet=True,progress=False)
        remote=client.client.get_remote(job);spec=remote.request
        assert spec['month']==[f'{month:02d}']
        target=download.OUT/f'era5_sst_uv10_month{month:02d}_1950_2026.grib'
        remote.download(str(target))
        download.record(target,dict(dataset='reanalysis-era5-single-levels-monthly-means',request=spec,job_id=job))
        return month
    save()
    with ThreadPoolExecutor(max_workers=len(PENDING)) as ex:
        jobs={ex.submit(resume,m,j):m for m,j in PENDING.items()}
        for job in as_completed(jobs):
            month=jobs[job]
            try:archive_month(job.result());print('Archived ERA5 month',month,flush=True)
            except Exception as e:state['failed_months'][month]=str(e);save()
    for month in range(1,13):
        if month in state['completed_months']:continue
        try:
            download.era5(month);archive_month(month);print('Archived ERA5 month',month,flush=True)
        except Exception as e:state['failed_months'][month]=str(e);save()
    state['status']='complete' if len(set(state['completed_months']))==12 else 'incomplete'
    state['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':main()
