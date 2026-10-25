from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from PIL import Image
import herta_pipeline as native
from dds_artifact_cache import DDSArtifactCache


class CachedPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='herta_native_cache_test_')
        self.addCleanup(self.temporary.cleanup)
        self.cache=DDSArtifactCache(Path(self.temporary.name)/'cache')
        output=BytesIO();Image.new('RGBA',(8,8),(42,80,128,255)).save(output,format='PNG');self.png=output.getvalue()

    def test_hit_skips_native_decoder_mips_and_encoder(self):
        first,profile=native.convert(self.png,False,cache=self.cache)
        self.assertFalse(profile['cache_hit'])
        with mock.patch.object(native._lib,'herta_png_to_dds',side_effect=AssertionError('Native path used')):
            second,profile=native.convert(self.png,False,cache=self.cache)
        self.assertTrue(profile['cache_hit']);self.assertEqual(first,second)

    def test_output_options_and_binary_identity_invalidate(self):
        native.convert(self.png,False,cache=self.cache)
        for kwargs in ({'output_srgb':True},{'output_srgb':False,'profile':0},{'output_srgb':False,'mip_srgb':1}):
            _,profile=native.convert(self.png,cache=self.cache,**kwargs)
            self.assertFalse(profile['cache_hit'])
        with mock.patch.object(native,'_encoder_sha256','different engine'):
            _,profile=native.convert(self.png,False,cache=self.cache)
            self.assertFalse(profile['cache_hit'])

    def test_corrupt_artifact_recomputes(self):
        first,_=native.convert(self.png,False,cache=self.cache)
        path=next(self.cache.root.rglob('*.hdds'));data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
        second,profile=native.convert(self.png,False,cache=self.cache)
        self.assertFalse(profile['cache_hit']);self.assertEqual(first,second)

    def test_raw_and_explicit_bypass_do_not_use_artifacts(self):
        native.convert(self.png,False,cache=self.cache)
        _,profile=native.convert(self.png,False,cache=False)
        self.assertFalse(profile['cache_hit'])
        raw,_=native.convert(self.png,False,raw=True,cache=self.cache)
        self.assertEqual(raw[148:152],bytes([42,80,128,255]))

if __name__=='__main__':unittest.main()
