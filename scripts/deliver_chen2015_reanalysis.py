from pathlib import Path
import shutil,hashlib,json,pandas as pd
SRC=Path(__file__).resolve().parents[1];DEST=Path('/Users/daiyue/Documents/Maryland');TAG='chen2015_reanalysis_20261014';OUT=SRC/'outputs/research_2026'/TAG
required=['WWV26_monthly_1980_2024.nc','main_event_comparison.csv','summary_QA.json','Chen2015_WWV26_2015_2023.png','Chen2015_STC_2015_2023.png','Chen2015_D26_longitude_time_2015_2023.png','Maryland_forecast_WWV26_bridge_2015_2023.png','results_and_methods_cn.txt']
for name in required:
 p=OUT/name
 if not p.exists() or p.stat().st_size==0:raise RuntimeError('Incomplete deliverable: '+name)
manifest=[]
files=list((SRC/'data/raw'/TAG).glob('*'))+list(OUT.glob('*'))
names=['fetch_chen2015_reanalysis.py','fetch_chen2015_deep_west.py','analyze_chen2015_reanalysis.py','plot_chen2015_reanalysis.py','report_chen2015_reanalysis.py','export_chen2015_reanalysis.py','check_chen2015_north_gate_reference.py','process_available_chen.py','run_chen2015_reanalysis_when_ready.py','deliver_chen2015_reanalysis.py','refine_chen_climatology_coverage.py']
files += [SRC/'scripts'/n for n in names]
for p in files:
 if not p.is_file() or '.partial.' in p.name or p.name=='delivery_manifest.json':continue
 rel=p.relative_to(SRC);q=DEST/rel;q.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(p,q);digest=hashlib.sha256(p.read_bytes()).hexdigest()
 if hashlib.sha256(q.read_bytes()).hexdigest()!=digest:raise RuntimeError('Delivery checksum mismatch: '+str(rel))
 manifest.append({'path':str(rel),'bytes':p.stat().st_size,'sha256':digest})
 print('Delivered',rel,flush=True) if p.suffix=='.png' else None
m={'files':manifest,'bytes':sum(f['bytes'] for f in manifest),'file_count':len(manifest),'checksum_verified':True}
(OUT/'delivery_manifest.json').write_text(json.dumps(m,indent=2));shutil.copy2(OUT/'delivery_manifest.json',DEST/'outputs/research_2026'/TAG/'delivery_manifest.json')
s=pd.read_csv(OUT/'main_event_comparison.csv').set_index('event_year')
section=f'''## 2026-10-14：已按陈2015定义统一重算暖水储备与输送

- 本轮用户要求“以陈老师的为准把之前的再做一遍”，已完成1980—2024共540个月、13事件的重算；重点更新2015/16与2023/24，1997/98作参照。输出 `outputs/research_2026/{TAG}/`。
- 主储备：9°S—9°N、120°E—80°W、瞬时σθ=26面的WWV26；同算±9°内部50m—σ26、总0—σ26和太平洋侧西边界流。原10°S—5°N三箱采用同一瞬时界面，明确标为区域扩展。
- 统一基期为1980—2022同月平均；主序列无去趋势/平滑/带通，另存同月线性趋势敏感性。该基期是SODA3扩展设定，不冒称原文1960—2010年的规定。主累计统一为Jan15—Jun15及次年Jan15—May15（2016、2024均121天）。
- 已新下载官方年度温盐、流速、海表通量区域子集：上层至525m，西部小区域补齐50层；无未解析下载截断剖面。历史CDF的sw_ocean与层中心重合，不能当作层界；所有年份统一采用与中心坐标核验一致的有效2024层界，避免伪造跨格式事件差异。
- 体积预算不再套用旧固定300m的强制四边质量平衡；未解析项=储量变化−水平输入，不能命名为海表散热。WWV/体积输送用m³/Sv；用户指定两项热输送用PW/ZJ另列；没有计算被省略背景/非线性项或声称它们足够小。
- 140°W发展期体积异常输入（10^14 m³），2015/2023：{s.loc[2015,'arrival_west_in_1e14m3']:.4f}/{s.loc[2023,'arrival_west_in_1e14m3']:.4f}；东箱衰减期WWV异常损失：{-s.loc[2015,'decay_storage_change_1e14m3']:.4f}/{-s.loc[2023,'decay_storage_change_1e14m3']:.4f}。
- 东箱衰减期北向体积异常输出（10^14 m³）2015/2023：{-s.loc[2015,'decay_north_in_1e14m3']:.4f}/{-s.loc[2023,'decay_north_in_1e14m3']:.4f}；5°N两项热积分合计（ZJ）：{s.loc[2015,'decay_linear_sum_zj']:.4f}/{s.loc[2023,'decay_linear_sum_zj']:.4f}。两项是移动断面上的线性贡献，不是完整热输送距平；不能据此自动推出纯风驱原因。
- 已更新综合图 `Maryland_forecast_WWV26_bridge_2015_2023.png` 的物理两行，另有WWV/区域收支/热两项主图、±9°STC图及D26经度时间图；各有PNG/SVG。NetCDF `WWV26_monthly_1980_2024.nc`、CSV、QA、方法报告和脚本可复现。RO/PMM/IRI保持原预报，其状态仍为D20，没有重新拟合为WWV26。
- 原0—300m OHC′/焓图和上一轮固定气候态断面两项图保留为历史/敏感性结果，不再与本轮体积结果混标。完整解释见 `results_and_methods_cn.txt` 与 `method_contract_cn.txt`。

'''
mem=DEST/'PROJECT_MEMORY.md';old=mem.read_text();text=old.replace('# Maryland ENSO 项目持久研究记忆\n\n','# Maryland ENSO 项目持久研究记忆\n\n'+section,1);mem.write_text(text);(SRC/'PROJECT_MEMORY.md').write_text(text)
status='\n\n2026-10-14 最新状态：已完成陈2015 σ26定义的统一重算。当前结果见 outputs/research_2026/chen2015_reanalysis_20261014/；原0—300m图保留为历史结果，新综合图为 Maryland_forecast_WWV26_bridge_2015_2023.png。详见新目录 results_and_methods_cn.txt。\n'
for rel in ['docs/chen2015_wwv_method_20261014.txt','docs/warm_water_transport_notes_20261014.txt','outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014/METHOD_STATUS_CN.txt']:
 p=SRC/rel
 if p.exists():
  old_status=p.read_text()
  if status.strip() not in old_status:p.write_text(old_status+status)
  shutil.copy2(p,DEST/rel)
print('DELIVERY COMPLETE',m['file_count'],m['bytes'],flush=True)
