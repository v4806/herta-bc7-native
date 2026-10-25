import json,random,statistics,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0,r'D:\Program Files\Blender Foundation\scripts\addons\TheHerta4-main\tests')
from test_geometry_hash import geometry,object_fixture,legacy_extract,legacy_hash

objects=[object_fixture(120000,4,2) for _ in range(8)]
counts={'objects':len(objects),'vertices':sum(len(o.data.vertices) for o in objects),
        'weights':sum(sum(len(v.groups) for v in o.data.vertices) for o in objects)}
methods=['legacy','packed_fallback','packed_native','packed_parallel']*3
random.Random(20261025).shuffle(methods)
records=[];expected=None
for method in methods:
    stamp=time.perf_counter()
    raw=[legacy_extract(o) if method=='legacy' else geometry.extract_object_hash_data(o) for o in objects]
    extract_s=time.perf_counter()-stamp;stamp=time.perf_counter()
    if method=='legacy':hashes=[legacy_hash(r) for r in raw]
    elif method=='packed_parallel':
        with ThreadPoolExecutor(max_workers=8) as pool:hashes=list(pool.map(geometry.hash_object_data,raw))
    else:hashes=[geometry.hash_object_data(r,native=method=='packed_native') for r in raw]
    hash_s=time.perf_counter()-stamp
    if expected is None:expected=hashes
    else:assert hashes==expected
    row={'method':method,'extract_s':extract_s,'hash_s':hash_s,'total_s':extract_s+hash_s}
    records.append(row);print(json.dumps(row),flush=True)
    del raw
summary=[]
for method in ('legacy','packed_fallback','packed_native','packed_parallel'):
    group=[r for r in records if r['method']==method]
    summary.append({'method':method,**{k:statistics.median(r[k] for r in group) for k in ('extract_s','hash_s','total_s')}})
raw=[geometry.extract_object_hash_data(o) for o in objects]
parallel=[]
for workers in (1,4,8,16,32):
    runs=[]
    for _ in range(3):
        stamp=time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:hashes=list(pool.map(geometry.hash_object_data,raw))
        runs.append(time.perf_counter()-stamp);assert hashes==expected
    parallel.append({'workers':workers,'median_hash_s':statistics.median(runs)})
report={'scope':'Synthetic RNA-like Python objects, 8 x 120000 vertices, sparse 4 influences, 2 UV layers; not actual Blender RNA or full export. Hashes verified against unchanged original stream.',
        'counts':counts,'summary':summary,'thread_scan':parallel,'runs':records}
target=Path(r'D:\DEV\herta-bc7-native\docs\geometry-hash-benchmark-2026-10-25-v2.json')
assert not target.exists();target.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'report':str(target),'summary':summary,'thread_scan':parallel}),flush=True)
