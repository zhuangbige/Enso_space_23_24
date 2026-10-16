"""Resolve deep sigma26 in western marginal seas, retaining real bottom masks."""
from pathlib import Path
import sys,json,time,concurrent.futures
import numpy as np,requests
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fetch_chen2015_reanalysis as f

def meta(year):
 s=requests.Session();m=f.metadata(year,s)
 if m['kind']=='HDF5':
  p=f.RAW/f'metadata_deep_{year}.json'
  if p.exists():return json.loads(p.read_text())
  import fsspec,h5py
  remote=fsspec.open(m['url'],'rb',block_size=65536,cache_type='readahead',client_kwargs={'trust_env':True}).open()
  with h5py.File(remote,'r') as d:
   for name in ['temp','salt','u','v']:
    for it in range(12):
     for iz in range(24,50):m['vars'][name]['offsets'][f'{it},{iz}']=d[name].id.get_chunk_info_by_coord((it,iz,0,0)).byte_offset
  remote.close();p.write_text(json.dumps(m,indent=2))
 return m

def fetch(year):
 target=f.RAW/f'soda3_deep_west_{year}.npz'
 if target.exists():return f'{year} deep cached'
 started=time.time();m=meta(year);co=m['coords'];out={}
 for name in ['temp','salt','u','v']:
  vv=m['vars'][name];vel=name in ['u','v'];yy=np.array(co['yu_ocean' if vel else 'yt_ocean']);xx=np.array(co['xu_ocean' if vel else 'xt_ocean'])%360
  ym=np.flatnonzero((yy>=(-3.5 if vel else -3.25))&(yy<=9.5));xm=np.flatnonzero((xx>=119.5)&(xx<=136.5));ny,nx=vv['shape'][-2:];dt=np.dtype(vv['dtype']);sz=dt.itemsize
  spans=[]
  for it in range(12):
   for iz in range(24,50):
    base=vv['offset']+it*m['record_size']+iz*ny*nx*sz if m['kind']=='CDF2' else vv['offsets'][f'{it},{iz}']
    for j in ym:spans.append((int(base+(j*nx+xm[0])*sz),int(base+(j*nx+xm[-1]+1)*sz)))
  blocks=[spans[i:i+200] for i in range(0,len(spans),200)]
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:payload=list(pool.map(lambda sp:f.ranges(m['url'],sp),blocks))
  a=np.stack([np.frombuffer(b,dt) for block in payload for b in block]).astype('float32').reshape(12,26,len(ym),len(xm));a[abs(a)>1e10]=np.nan
  print(f'{year} deep {name} retrieved',flush=True)
  out[name]=a;tag='u' if vel else 't';out['lat_'+tag]=yy[ym];out['lon_'+tag]=xx[xm]
 out['depth']=np.array(co['st_ocean'])[24:];out['layer_bottom']=np.array(co['sw_ocean'])[24:]
 np.savez_compressed(target.with_suffix('.partial.npz'),**out);target.with_suffix('.partial.npz').replace(target)
 return f'{year} deep done {target.stat().st_size/1e6:.2f} MB {time.time()-started:.0f}s'
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--years',type=int,nargs='+',default=list(range(1980,2025)));p.add_argument('--workers',type=int,default=2);o=p.parse_args()
 with concurrent.futures.ThreadPoolExecutor(max_workers=o.workers) as ex:
  futures={ex.submit(fetch,y):y for y in o.years}
  for future in concurrent.futures.as_completed(futures):
   try:print(future.result(),flush=True)
   except Exception as e:print('FAILED',futures[future],repr(e),flush=True);raise
