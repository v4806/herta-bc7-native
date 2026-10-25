"""Experimental native PNG-to-DDS interface; no subprocess/intermediate files."""
import ctypes as ct
import hashlib
import struct
import time
from pathlib import Path
from dds_artifact_cache import DDSArtifactCache

class Profile(ct.Structure):
    _fields_=[('decode_s',ct.c_double),('mip_s',ct.c_double),('encode_s',ct.c_double),
              ('width',ct.c_uint32),('height',ct.c_uint32),('levels',ct.c_uint32),('source_srgb',ct.c_uint32)]

_lib=ct.CDLL(str(Path(__file__).with_name('herta_pipeline_windows_x64.dll')))
_lib.herta_bc7f_init.argtypes=[];_lib.herta_bc7f_init.restype=ct.c_uint
assert _lib.herta_bc7f_init()==1
_lib.herta_png_to_dds.argtypes=[ct.c_char_p,ct.c_size_t,ct.c_uint,ct.c_int,ct.c_uint,ct.c_uint,
                                ct.POINTER(ct.c_void_p),ct.POINTER(ct.c_size_t),ct.POINTER(Profile)]
_lib.herta_png_to_dds.restype=ct.c_int
_lib.herta_pipeline_free.argtypes=[ct.c_void_p];_lib.herta_pipeline_free.restype=None
_encoder_sha256=hashlib.sha256(Path(__file__).with_name('herta_pipeline_windows_x64.dll').read_bytes()).hexdigest()
_default_cache=DDSArtifactCache()
ERRORS={-1:'Invalid arguments',-2:'PNG precision/colorspace not supported',-3:'Requires power-of-two dimensions within 16384',
        -4:'PNG decoding failed',-5:'Allocation or internal failure',-6:'BC7 encoding failed'}

def convert(png:bytes,output_srgb:bool,*,profile=2,raw=False,mip_srgb=-1,cache=True):
    if output_srgb not in (False,True) or mip_srgb not in (-1,0,1) or profile not in (0,1,2,3):
        raise ValueError('Invalid encoding options')
    cache_started=time.perf_counter()
    store=_default_cache if cache is True else cache
    key=None
    if not raw and store and store.enabled:
        recipe={'backend':'bc7f-png-memory-v1','encoder_sha256':_encoder_sha256,
                'format':99 if output_srgb else 98,'profile':profile,'mip_srgb':mip_srgb,'mips':'full'}
        key=store.key(hashlib.sha256(png).hexdigest(),recipe)
        data=store.get(key)
        if data is not None:
            height,width=struct.unpack_from('<II',data,12)
            return data,{'decode_s':0.0,'mip_s':0.0,'encode_s':0.0,'width':width,'height':height,
                         'levels':struct.unpack_from('<I',data,28)[0],'source_srgb':None,
                         'cache_hit':True,'cache_s':time.perf_counter()-cache_started}
    output=ct.c_void_p();size=ct.c_size_t();timing=Profile()
    status=_lib.herta_png_to_dds(png,len(png),int(output_srgb),mip_srgb,profile,int(raw),
                                ct.byref(output),ct.byref(size),ct.byref(timing))
    if status!=1:raise ValueError(f'{status}: {ERRORS.get(status,"Unknown failure")}')
    try:data=ct.string_at(output,size.value)
    finally:_lib.herta_pipeline_free(output)
    stages={name:getattr(timing,name) for name,_ in Profile._fields_}
    stages['cache_hit']=False
    if key is not None:
        started=time.perf_counter();stages['cache_stored']=store.put(key,data)
        stages['cache_s']=time.perf_counter()-started
    return data,stages
