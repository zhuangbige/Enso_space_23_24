#!/usr/bin/env python3
"""Read three regional raw ORAS5 indices from the official CDS ARCO store.

CDS credentials are sent only to the ECMWF host used by upstream XRO/state.py.
No anomaly, trend, standardization or future-dependent transformation is
applied here. Only compact regional means and validation metadata are saved.
"""
from pathlib import Path
import os
import sys
import json
import hashlib
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/xro_zarr_deps'))
# The desktop shell can inherit a stopped local proxy. Use the direct route.
for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:
    os.environ.pop(key,None)
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
import pandas as pd
import xarray as xr
import dask
import aiohttp

OUT=ROOT/'data/derived/research_2026/oras5_ro_raw_indices'
OUT.mkdir(parents=True,exist_ok=True)
URLS={kind:f'https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/{kind}/geoChunked.zarr'
      for kind in ['consolidated','operational']}
BOXES={'Nino34':('sosstsst',-5,5,190,240),
       'WWV':('so20chgt',-5,5,120,280),
       'NPMM':('sosstsst',10,25,200,240)}

def credential():
    path=Path('~/.cdsapirc').expanduser()
    for line in path.read_text().splitlines():
        if line.strip().startswith('key:'):
            return line.split(':',1)[1].strip().strip('"\'')
    raise RuntimeError('CDS token not configured')

def main():
    token=credential()
    options={'headers':{'Authorization':f'Bearer {token}'},
             'client_kwargs':{'timeout':aiohttp.ClientTimeout(total=180)}}
    audit={'source_urls':URLS,'regions':BOXES,'preprocessing':'none; raw monthly spatial means',
           'downloaded_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'products':{}}
    results=[]
    for product,url in URLS.items():
        output=OUT/f'{product}_raw_indices.nc'
        metadata=OUT/f'{product}_metadata.json'
        if output.exists() and metadata.exists():
            print('Using cache:',output.name,flush=True)
            results.append(xr.open_dataset(output).load())
            audit['products'][product]=json.loads(metadata.read_text())
            continue
        print('Opening',product,'metadata',flush=True)
        ds=xr.open_zarr(url,consolidated=True,storage_options=options)
        ds=ds.rename({'latitude':'lat','longitude':'lon'})
        ds=ds.sel(time=slice('1979-01','2014-12' if product=='consolidated' else '2026-09'))
        if product=='operational':ds=ds.sel(time=slice('2015-01',None))
        ds=ds.sortby('lat')
        dates=pd.DatetimeIndex(ds.time.values)
        print(product,'available',str(dates[0].date()),str(dates[-1].date()),dict(ds.sizes),flush=True)
        assert dates.equals(pd.date_range(dates[0],dates[-1],freq='MS'))
        fields={};details={}
        for name,(var,south,north,west,east) in BOXES.items():
            region=ds[var].sel(lat=slice(south,north))
            region=region.sel(lon=((region.lon%360-west)%360<=east-west+1e-7))
            w=np.cos(np.deg2rad(region.lat))
            # Normalize over valid ocean cells, not over missing land cells.
            average=region.weighted(w).mean(('lat','lon'))
            fields[name]=average
            fields[name+'_valid_count']=region.notnull().sum(('lat','lon'))
            details[name]={'variable':var,'units':region.attrs.get('units'),
                           'nlat':region.sizes['lat'],'nlon':region.sizes['lon'],
                           'region':{'south':south,'north':north,'west_0_360':west,'east_0_360':east}}
        result=xr.Dataset(fields)
        print('Reading required regional chunks:',product,flush=True)
        with dask.config.set(scheduler='threads',num_workers=8):
            result=result.compute()
        for name in BOXES:
            assert np.isfinite(result[name]).all()
            details[name]['min_valid_cells']=int(result[name+'_valid_count'].min())
            details[name]['max_valid_cells']=int(result[name+'_valid_count'].max())
            details[name]['min']=float(result[name].min())
            details[name]['max']=float(result[name].max())
            # A time-invariant ocean footprint is required for consistent means.
            assert details[name]['min_valid_cells']==details[name]['max_valid_cells']
        result.attrs.update(source=url,product_type=product,spatial_weighting='cos(latitude), valid-ocean normalization',
                            preprocessing='raw values: no climatology or trend removed')
        result.to_netcdf(output,engine='netcdf4')
        metadata.write_text(json.dumps(details,indent=2))
        audit['products'][product]=details
        results.append(result)
        print('Saved',output,flush=True)
    merged=xr.concat(results,dim='time').sortby('time')
    dates=pd.DatetimeIndex(merged.time.values)
    assert dates.is_unique and dates.equals(pd.date_range(dates[0],dates[-1],freq='MS'))
    assert merged.Nino34.min()>15 and merged.Nino34.max()<35
    assert merged.WWV.min()>50 and merged.WWV.max()<250
    assert merged.NPMM.min()>15 and merged.NPMM.max()<35
    merged=merged[list(BOXES)]
    merged.WWV.attrs.update(units='m',long_name='WWV proxy: area-mean D20 (5S–5N,120E–80W); not volume')
    merged.attrs.update(source='CDS ORAS5 ARCO consolidated through 2014; operational from 2015',
                        preprocessing='none; raw monthly regional means')
    output=OUT/'oras5_ro_raw_indices_1979_latest.nc'
    merged.to_netcdf(output,engine='netcdf4')
    merged.to_dataframe().to_csv(OUT/'oras5_ro_raw_indices_1979_latest.csv')
    audit.update(start=str(dates[0].date()),end=str(dates[-1].date()),months=len(dates),
                 sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    (OUT/'source_and_validation.json').write_text(json.dumps(audit,indent=2))
    print('Finished',audit['start'],audit['end'],flush=True)

if __name__=='__main__':
    main()
