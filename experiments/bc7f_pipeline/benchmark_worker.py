from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import hashlib,json,sys,time
from pathlib import Path
from herta_pipeline import convert

class Memory(ct.Structure):
    _fields_=[('cb',ct.c_uint32),('PageFaultCount',ct.c_uint32)]+[(name,ct.c_size_t) for name in
        ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
         'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]

def main():
    sources=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    out=Path(sys.argv[2]);out.mkdir();workers=int(sys.argv[3]);records=[]
    def process(s):
        data,profile=convert(Path(s['path']).read_bytes(),s['format'].endswith('srgb'),cache=False)
        (out/s['target']).write_bytes(data)
        return {'target':s['target'],'sha256':hashlib.sha256(data).hexdigest(),**profile}
    wall=time.perf_counter();cpu=time.process_time()
    with ThreadPoolExecutor(max_workers=workers) as pool:records=list(pool.map(process,sources))
    cpu_s=time.process_time()-cpu;wall_s=time.perf_counter()-wall
    memory=Memory();memory.cb=ct.sizeof(memory)
    get_process=ct.windll.kernel32.GetCurrentProcess;get_process.restype=ct.c_void_p
    get_memory=ct.windll.psapi.GetProcessMemoryInfo;get_memory.argtypes=[ct.c_void_p,ct.POINTER(Memory),ct.c_uint32]
    if not get_memory(get_process(),ct.byref(memory),memory.cb):raise ct.WinError()
    result={'workers':workers,'files':len(records),'wall_s':wall_s,'process_cpu_s':cpu_s,
            'peak_working_set_MiB':memory.PeakWorkingSetSize/1024**2,
            'cumulative_stage_wall_s':{key:sum(x[key] for x in records) for key in ('decode_s','mip_s','encode_s')},
            'records':records}
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)
if __name__=='__main__':main()
