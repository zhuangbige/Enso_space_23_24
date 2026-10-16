#!/usr/bin/env python3
"""Read SODA3 official annual-file tropical subsets via checked HTTP ranges.
No full annual downloads. Supports CDF2 and uncompressed HDF5 chunks.
"""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,re,struct,time,threading
import requests,numpy as np
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/chen2015_reanalysis_20261014'
RAW.mkdir(parents=True,exist_ok=True)
URL='https://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/soda3.15.2_mn_ocean_reg_{year}.nc'
DT={1:'i1',2:'S1',3:'>i2',4:'>i4',5:'>f4',6:'>f8'}

def ranges(url,spans,session=None):
 s=session or requests.Session()
 header={'Range':'bytes='+','.join(f'{a}-{b-1}' for a,b in spans),'Accept-Encoding':'identity'}
 for attempt in range(5):
  try:
   r=s.get(url,headers=header,timeout=(15,120),stream=True);r.raise_for_status()
   if r.status_code!=206:
    status=r.status_code;r.close();raise ValueError(f'Range ignored: {status}')
   expected_max=sum(b-a for a,b in spans)+len(spans)*512+2048
   if int(r.headers.get('Content-Length','0'))>expected_max:
    r.close();raise ValueError('Unexpected oversized range response')
   typ=r.headers.get('Content-Type','')
   parts={}
   if 'multipart/byteranges' in typ:
    boundary=re.search('boundary="?([^"; ]+)',typ).group(1).encode()
    for p in r.content.split(b'--'+boundary):
     if b'Content-range:' not in p and b'Content-Range:' not in p:continue
     h,payload=p.lstrip(b'\r\n').split(b'\r\n\r\n',1)
     a,b,total=map(int,re.search(rb'Content-range: bytes (\d+)-(\d+)/(\d+)',h,re.I).groups())
     data=payload[:b-a+1]
     if len(data)!=b-a+1:raise ValueError('Short multipart segment')
     parts[(a,b+1)]=data
   else:
    a,b,total=map(int,re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',r.headers['Content-Range']).groups())
    if len(r.content)!=b-a+1:raise ValueError('Short range')
    parts[(a,b+1)]=r.content
   out=[]
   for a,b in spans:
    match=[p[a-x:b-x] for (x,y),p in parts.items() if x<=a and y>=b]
    if len(match)!=1:raise ValueError(f'Missing/ambiguous range {a}:{b}')
    out.append(match[0])
   return out
  except Exception:
   if attempt==4:raise
   time.sleep(attempt+1)

def classic_meta(data):
 p=4
 def num():
  nonlocal p
  x=struct.unpack_from('>I',data,p)[0];p+=4;return x
 def string():
  nonlocal p
  n=num();v=data[p:p+n].decode();p+=(n+3)//4*4;return v
 def attrs():
  nonlocal p
  tag,n=num(),num();o={}
  for _ in range(n):
   name=string();typ=num();k=num();dt=np.dtype(DT[typ]);sz=dt.itemsize*k
   a=np.frombuffer(data[p:p+sz],dt).copy();p+=(sz+3)//4*4
   o[name]=a.tobytes().decode(errors='replace') if typ==2 else a.tolist()
  return o
 nt=num();tag,nd=num(),num();dims=[]
 for _ in range(nd):dims.append((string(),num()))
 glob=attrs();tag,nv=num(),num();var={}
 for _ in range(nv):
  name=string();k=num();ids=[num() for _ in range(k)];at=attrs();typ=num();size=num()
  off=struct.unpack_from('>Q' if data[3]==2 else '>I',data,p)[0];p+=8 if data[3]==2 else 4
  var[name]={'shape':[nt if dims[i][1]==0 else dims[i][1] for i in ids],'dtype':DT[typ],'offset':off,'record':bool(ids and dims[ids[0]][1]==0),'vsize':size,'attrs':at}
 recsize=sum(v['vsize'] for v in var.values() if v['record'])
 return {'kind':'CDF2','nrecords':nt,'record_size':recsize,'vars':var,'global':glob}

def metadata(year,s):
 u=URL.format(year=year);p=RAW/f'metadata_{year}.json'
 if p.exists():return json.loads(p.read_text())
 h=ranges(u,[(0,65536)],s)[0]
 if h[:3]==b'CDF':
  m=classic_meta(h);coords={}
  for name in ['st_ocean','sw_ocean','xt_ocean','yt_ocean','xu_ocean','yu_ocean','time']:
   v=m['vars'][name];n=np.prod(v['shape']);dt=np.dtype(v['dtype'])
   if name=='time' and v['record']:
    b=ranges(u,[(v['offset']+i*m['record_size'],v['offset']+i*m['record_size']+dt.itemsize) for i in range(v['shape'][0])],s)
    a=np.concatenate([np.frombuffer(x,dt) for x in b])
   else:a=np.frombuffer(ranges(u,[(v['offset'],v['offset']+int(n)*dt.itemsize)],s)[0],dt)
   coords[name]=a.tolist()
  m['coords']=coords
 else:
  import fsspec,h5py
  f=fsspec.open(u,'rb',block_size=65536,cache_type='readahead',client_kwargs={'trust_env':True}).open()
  m={'kind':'HDF5','vars':{},'coords':{}}
  with h5py.File(f,'r') as d:
   for name in ['st_ocean','sw_ocean','xt_ocean','yt_ocean','xu_ocean','yu_ocean','time']:
    m['coords'][name]=d[name][:].tolist()
   for name in ['temp','salt','u','v','net_heating']:
    q=d[name];assert q.compression is None and not q.shuffle and not q.fletcher32
    at={k:(v.tolist() if isinstance(v,np.ndarray) and v.dtype.kind!='O' else str(v)) for k,v in q.attrs.items() if k in ['units','long_name','missing_value','_FillValue']}
    v={'shape':list(q.shape),'dtype':str(q.dtype),'attrs':at,'chunks':q.chunks,'offsets':{}}
    nz=24 if q.ndim==4 else 1
    for it in range(q.shape[0]):
     for iz in range(nz):
      c=(it,iz,0,0) if q.ndim==4 else (it,0,0)
      info=q.id.get_chunk_info_by_coord(c);assert info.filter_mask==0
      v['offsets'][f'{it},{iz}']=info.byte_offset
    m['vars'][name]=v
  f.close()
 m['url']=u;m['header_sha256']=hashlib.sha256(h).hexdigest()
 p.write_text(json.dumps(m,indent=2));return m

def getsubset(year,name,m,s):
 v=m['vars'][name];co=m['coords'];isvel=name in ['u','v']
 yy=np.array(co['yu_ocean' if isvel else 'yt_ocean']);xx=np.array(co['xu_ocean' if isvel else 'xt_ocean'])%360
 ym=np.flatnonzero((yy>=(-10.5 if isvel else -10.25))&(yy<=(9.5 if isvel else 9.25)))
 xm=np.flatnonzero((xx>=119.5)&(xx<=280.5))
 assert np.all(np.diff(ym)==1) and np.all(np.diff(xm)==1)
 ny,nx=v['shape'][-2:];dt=np.dtype(v['dtype']);sz=dt.itemsize;nz=24 if len(v['shape'])==4 else 1
 spans=[]
 for it in range(v['shape'][0]):
  for iz in range(nz):
   if m['kind']=='CDF2':base=v['offset']+it*m['record_size']+iz*ny*nx*sz
   else:base=v['offsets'][f'{it},{iz}']
   start=base+(ym[0]*nx+xm[0])*sz;end=base+(ym[-1]*nx+xm[-1]+1)*sz
   spans.append((int(start),int(end)))
 result=[]
 blocks=[spans[i:i+24] for i in range(0,len(spans),24)]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  payloads=list(pool.map(lambda sp:ranges(m['url'],sp),blocks))
 for payload in payloads:
  for b in payload:
   a=np.frombuffer(b,dt);rows=np.lib.stride_tricks.as_strided(a,shape=(len(ym),len(xm)),strides=(nx*sz,sz)).copy().astype('float32')
   rows[(rows<-1e10)|(rows>1e10)]=np.nan;result.append(rows)
 a=np.array(result).reshape(v['shape'][0],nz,len(ym),len(xm))
 return a if nz>1 else a[:,0],yy[ym],xx[xm]

def fetch(year):
 p=RAW/f'soda3_sigma26_inputs_{year}.npz'
 if p.exists():return f'{year} cached'
 started=time.time();s=requests.Session();m=metadata(year,s);out={}
 for name in ['temp','salt','u','v','net_heating']:
  a,y,x=getsubset(year,name,m,s);out[name]=a
  print(f'{year} {name} retrieved',flush=True)
  tag='u' if name in ['u','v'] else 't';out['lat_'+tag]=y;out['lon_'+tag]=x
 out['depth']=np.array(m['coords']['st_ocean'])[:24];out['layer_bottom']=np.array(m['coords']['sw_ocean'])[:24]
 assert out['temp'].shape==out['salt'].shape
 np.savez_compressed(p.with_suffix('.partial.npz'),**out);p.with_suffix('.partial.npz').replace(p)
 return f'{year} done {p.stat().st_size/1e6:.1f} MB in {time.time()-started:.1f}s'

def main():
 a=argparse.ArgumentParser();a.add_argument('--years',nargs='+',type=int,default=list(range(1980,2025)));a.add_argument('--workers',type=int,default=3);o=a.parse_args()
 with concurrent.futures.ThreadPoolExecutor(max_workers=o.workers) as ex:
  futures={ex.submit(fetch,y):y for y in o.years}
  for f in concurrent.futures.as_completed(futures):
   try:print(f.result(),flush=True)
   except Exception as e:print('FAILED',futures[f],repr(e),flush=True);raise
if __name__=='__main__':main()
