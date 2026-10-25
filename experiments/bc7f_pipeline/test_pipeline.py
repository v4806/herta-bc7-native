from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import ctypes as ct
import struct
import unittest
import numpy as np
from PIL import Image,PngImagePlugin
from herta_pipeline import convert as _convert,_lib,Profile

def convert(*args,**kwargs):
    return _convert(*args,cache=False,**kwargs)

def png(image,info=None):
    stream=BytesIO();image.save(stream,format='PNG',pnginfo=info);return stream.getvalue()

class PipelineTests(unittest.TestCase):
    def test_dimensions_roundtrip_and_concurrent_determinism(self):
        rng=np.random.default_rng(20261025)
        for w,h in ((1,1),(2,4),(4,4),(16,8),(32,32)):
            source=rng.integers(0,256,(h,w,4),dtype=np.uint8);data=png(Image.fromarray(source))
            raw,profile=convert(data,False,raw=True)
            self.assertEqual(raw[148:148+w*h*4],source.tobytes())
            expected=convert(data,False)[0]
            with Image.open(BytesIO(expected)) as im:self.assertEqual(im.size,(w,h))
            with ThreadPoolExecutor(max_workers=16) as pool:
                self.assertTrue(all(x==expected for x in pool.map(lambda _:convert(data,False)[0],range(32))))

    def test_png_types(self):
        for mode in ('RGB','RGBA','L','LA','P','1'):
            image=Image.new(mode,(8,8));data=png(image)
            raw,_=convert(data,True,raw=True)
            self.assertEqual(raw[148:148+8*8*4],image.convert('RGBA').tobytes())

    def test_srgb_mips_and_alpha(self):
        source=np.zeros((2,2,4),np.uint8);source[:,:,3]=[[0,128],[255,255]];source[0,1,:3]=255;source[1,1,:3]=255
        image=Image.fromarray(source)
        info=PngImagePlugin.PngInfo();info.add(b'sRGB',bytes([0]))
        tagged,profile=convert(png(image,info),True,raw=True)
        numeric,_=convert(png(image),True,raw=True)
        self.assertEqual(profile['source_srgb'],1)
        self.assertLess(abs(tagged[-4]-188),2)
        # UNORM follows WIC's premultiplied-alpha filtering: 96*255/160.
        self.assertEqual(numeric[-4],153)
        self.assertEqual(tagged[-1],160)
        self.assertEqual(numeric[-1],160)
        self.assertEqual(struct.unpack_from('<I',tagged,144)[0],1)
        opaque,_=convert(png(Image.new('RGBA',(4,4),(1,2,3,255))),False)
        self.assertEqual(struct.unpack_from('<I',opaque,144)[0],3)

    def test_unsupported_inputs_fail_explicitly(self):
        for data in (b'',b'not PNG',png(Image.new('RGBA',(7,5))),png(Image.new('I;16',(4,4)))):
            with self.assertRaises(ValueError):convert(data,False)
        info=PngImagePlugin.PngInfo();info.add(b'gAMA',struct.pack('>I',50000))
        with self.assertRaises(ValueError):convert(png(Image.new('RGBA',(4,4)),info),False)

    def test_invalid_c_arguments(self):
        source=png(Image.new('RGBA',(4,4)))
        for pointer,length,srgb,mip,profile,mode in ((None,0,0,-1,2,0),(source,len(source),2,-1,2,0),
                (source,len(source),0,2,2,0),(source,len(source),0,-1,4,0),(source,len(source),0,-1,2,2)):
            out=ct.c_void_p(123);size=ct.c_size_t(123);timing=Profile()
            result=_lib.herta_png_to_dds(pointer,length,srgb,mip,profile,mode,ct.byref(out),ct.byref(size),ct.byref(timing))
            self.assertEqual(result,-1);self.assertIsNone(out.value);self.assertEqual(size.value,0)

if __name__=='__main__':unittest.main()
