"""Run the three extended-suite errors against the pre-change SubMesh source."""
import importlib.util
from pathlib import Path
import sys,unittest
addon=Path(r'D:\Program Files\Blender Foundation\scripts\addons\TheHerta4-main')
before=Path(r'D:\Program Files\agent\deepseek\file-backups\native-memory-pipeline-20261025-215446\D\Program Files\Blender Foundation\scripts\addons\TheHerta4-main\common\submesh_model.py')
assert before.exists()
original=importlib.util.spec_from_file_location
def old_source(name,location,*args,**kwargs):
    if Path(location).resolve()==(addon/'common'/'submesh_model.py').resolve():location=before
    return original(name,location,*args,**kwargs)
importlib.util.spec_from_file_location=old_source
sys.path.insert(0,str(addon/'tests'))
import test_himi_stub_objects as module
names=['StubEndToEndIniTests.test_absent_part_without_reverse_lookup_gets_no_stub_section',
       'StubEndToEndIniTests.test_stub_ib_override_section_reaches_the_real_ini',
       'StubNailIntegrityTests.test_production_anchor_references_resolve']
suite=unittest.TestLoader().loadTestsFromNames(names,module)
result=unittest.TextTestRunner(verbosity=0).run(suite)
assert len(result.errors)==3 and not result.failures
texts=[error for test,error in result.errors]
assert sum('himi_family_x' in text for text in texts)==2
assert sum('05-decisions.md' in text for text in texts)==1
print('Confirmed all 3 errors also occur with pre-change SubMesh source; not hidden or skipped.')
