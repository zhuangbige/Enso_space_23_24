#!/usr/bin/env python3
"""Download only SSH and zonal stress halos; never alter the earlier caches."""
from pathlib import Path
import argparse, concurrent.futures, hashlib, json, struct, time
import numpy as np
import requests
import fetch_chen2015_reanalysis as remote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/three_event_summer_current_dynamics_20261015'
DEST = OUT / 'inputs'
URL = remote.URL

def classic(data):
    p = 4
    def number():
        nonlocal p
        n = struct.unpack_from('>I', data, p)[0]; p += 4
        return n
    def string():
        nonlocal p
        n=number(); s=data[p:p+n].decode(); p += (n+3)//4*4
        return s
    def attrs():
        nonlocal p
        tag,n=number(),number(); out={}
        for _ in range(n):
            name=string(); typ=number(); k=number(); dt=np.dtype(remote.DT[typ]); size=k*dt.itemsize
            a=np.frombuffer(data[p:p+size],dt).copy(); p+=(size+3)//4*4
            out[name]=a.tobytes().decode(errors='replace') if typ==2 else a.tolist()
        return out
    nt=number(); tag,nd=number(),number(); dims=[]
    for _ in range(nd): dims.append((string(),number()))
    glob=attrs(); tag,nv=number(),number(); variables={}
    for _ in range(nv):
        name=string(); n=number(); ids=[number() for _ in range(n)]; at=attrs(); typ=number(); size=number()
        off=struct.unpack_from('>Q' if data[3]==2 else '>I',data,p)[0]; p+=8 if data[3]==2 else 4
        variables[name]=dict(shape=[nt if dims[i][1]==0 else dims[i][1] for i in ids],
            dims=[dims[i][0] for i in ids],dtype=remote.DT[typ],offset=off,
            record=bool(ids and dims[ids[0]][1]==0),vsize=size,attrs=at)
    return dict(kind='CDF2',vars=variables,record_size=sum(v['vsize'] for v in variables.values() if v['record']),global_attrs=glob)

def metadata(year,session):
    url=URL.format(year=year)
    h=remote.ranges(url,[(0,65536)],session)[0]
    if h[:3]==b'CDF':
        m=classic(h); coords={}
        for n in ['xt_ocean','yt_ocean','xu_ocean','yu_ocean','time']:
            v=m['vars'][n]; size=np.dtype(v['dtype']).itemsize
            spans=[(v['offset']+i*m['record_size'],v['offset']+i*m['record_size']+size) for i in range(v['shape'][0])] if v['record'] else [(v['offset'],v['offset']+int(np.prod(v['shape']))*size)]
            coords[n]=np.concatenate([np.frombuffer(b,v['dtype']) for b in remote.ranges(url,spans,session)]).tolist()
        m['coords']=coords
    else:
        import fsspec,h5py,aiohttp
        m=dict(kind='HDF5',vars={},coords={})
        with fsspec.open(url,'rb',block_size=65536,cache_type='readahead',client_kwargs={'trust_env':True,'timeout':aiohttp.ClientTimeout(total=90)}).open() as f:
            with h5py.File(f,'r') as d:
                for n in ['xt_ocean','yt_ocean','xu_ocean','yu_ocean','time']:
                    m['coords'][n]=d[n][:].tolist()
                for n in ['ssh','taux']:
                    q=d[n]
                    assert q.ndim==3 and q.shape[0]==12
                    assert q.compression is None and not q.shuffle and not q.fletcher32
                    dims=[q.dims[i][0].name.rsplit('/',1)[-1] for i in range(q.ndim)]
                    v=dict(shape=list(q.shape),dims=dims,dtype=str(q.dtype),chunks=list(q.chunks),
                        attrs={k:str(v) for k,v in q.attrs.items() if k in ['units','long_name','standard_name','_FillValue','missing_value']},offsets=[])
                    assert tuple(q.chunks)==(1,330,720)
                    for it in range(12):
                        info=q.id.get_chunk_info_by_coord((it,0,0));assert info.filter_mask==0
                        v['offsets'].append(info.byte_offset)
                    m['vars'][n]=v
    m.update(url=url,header_sha256=hashlib.sha256(h).hexdigest())
    return m

def fetch(year):
    DEST.mkdir(parents=True,exist_ok=True)
    out=DEST/f'surface_{year}.npz'; meta=DEST/f'surface_{year}_metadata.json'
    if out.exists() and meta.exists():return f'{year} cached'
    session=requests.Session();m=metadata(year,session);result={}
    for name in ['ssh','taux']:
        v=m['vars'][name]; yname,xname=v['dims'][-2:]
        assert yname in ['yt_ocean','yu_ocean'] and xname in ['xt_ocean','xu_ocean'],v['dims']
        lat=np.round(m['coords'][yname],6);lon=np.round(np.array(m['coords'][xname])%360,6)
        iy=np.flatnonzero((lat>=-5.5)&(lat<=5.5));ix=np.flatnonzero((lon>=189.5)&(lon<=240.5))
        dt=np.dtype(v['dtype']);size=dt.itemsize;ny,nx=v['shape'][-2:];spans=[]
        assert len(iy)>20 and len(ix)>100 and np.all(np.diff(ix)==1)
        for it in range(12):
            base=v['offset']+it*m['record_size'] if m['kind']=='CDF2' else v['offsets'][it]
            spans.append((int(base+(iy[0]*nx+ix[0])*size),int(base+(iy[-1]*nx+ix[-1]+1)*size)))
        payload=remote.ranges(m['url'],spans,session);arr=[]
        for b in payload:
            flat=np.frombuffer(b,dt)
            a=np.stack([flat[j*nx:j*nx+len(ix)] for j in range(len(iy))]).astype('float32')
            a[(a<-1e10)|(a>1e10)]=np.nan;arr.append(a)
        result[name]=np.stack(arr);result['lat_'+name]=lat[iy];result['lon_'+name]=lon[ix]
        assert result[name].shape[0]==12
    result['source_time']=m['coords']['time']
    np.savez_compressed(out.with_suffix('.partial.npz'),**result)
    out.with_suffix('.partial.npz').replace(out)
    m['subset_sha256']=hashlib.sha256(out.read_bytes()).hexdigest()
    meta.write_text(json.dumps(m,indent=2))
    return f'{year}: ssh/taux, {out.stat().st_size/1e3:.0f} kB, grids '+str({n:m['vars'][n]['dims'] for n in ['ssh','taux']})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--years',nargs='+',type=int,default=list(range(1982,2025)));p.add_argument('--workers',type=int,default=3);a=p.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futures={ex.submit(fetch,y):y for y in a.years}
        for f in concurrent.futures.as_completed(futures): print(f.result(),flush=True)
