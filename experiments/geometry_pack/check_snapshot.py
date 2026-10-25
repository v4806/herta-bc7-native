import hashlib,importlib.util,json,re,struct,sys
from pathlib import Path
root=Path(__file__).resolve().parent
addon=Path(r'D:\Program Files\Blender Foundation\scripts\addons\TheHerta4-main')
for a,b in ((root/'geometry_hash.py',addon/'common'/'geometry_hash.py'),
            (root/'geometry_pack.c',addon/'common'/'native'/'geometry_pack.c'),
            (root/'native'/'herta_geometry_windows_x64.dll',addon/'common'/'native'/'herta_geometry_windows_x64.dll')):
    assert hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(b.read_bytes()).digest()
sys.path.insert(0,str(root))
from geometry_hash import WeightColumns,pack_weight_columns,_native_library
from array import array
assert _native_library() is not None
columns=WeightColumns(array('I',[2,0,1]),array('i',[7,2,5]),array('f',[.25,.75,1]))
assert bytes(pack_weight_columns(columns))==b''.join(struct.pack('iif',*r) for r in ((0,7,.25),(0,2,.75),(2,5,1)))
repo=root.parents[1]
for path in (repo/'docs').glob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if '://' not in link:assert (path.parent/link).exists(),(path,link)
manifest={'abi':1,'platform':'Windows x64, no CRT dependencies, SSE2 baseline',
          'blender_export_regression':'Not yet run on user project after integration',
          'core_tests_passed':32,'extended_himi':{'passed':48,'baseline_errors':3},
          'files':[{'file':str(p.relative_to(root)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in (root/'geometry_hash.py',root/'geometry_pack.c',root/'native'/'herta_geometry_windows_x64.dll')]}
target=root/'snapshot.json';assert not target.exists();target.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'native_self_test':'pass','installed_snapshot_hashes':'match','local_note_links':'pass','snapshot':str(target)}))
