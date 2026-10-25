import ctypes as ct
from hashlib import sha256
from pathlib import Path
import struct
import tempfile
import unittest

from herta_bc7 import BC7Engine, PixelFingerprint, _base_mip


FIXTURES = Path(__file__).resolve().parent / 'fixtures'


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = BC7Engine()
        cls.dds = (FIXTURES / 'all_modes.dds').read_bytes()
        cls.rgba = (FIXTURES / 'all_modes.rgba').read_bytes()

    def test_all_eight_modes_match_fixed_reference_including_edges(self):
        image = self.engine.decode_dds(self.dds)
        self.assertEqual((image.width, image.height), (29, 63))
        self.assertEqual(image.rgba, self.rgba)

    def test_pixel_path_hashes_every_rgba_byte(self):
        self.assertEqual(self.engine.fingerprint_dds(self.dds),
                         PixelFingerprint(29, 63, sha256(self.rgba).hexdigest()))

    def test_fused_pool_matches_full_reference_at_multiple_grids(self):
        for grid in (1, 7, 64):
            with self.subTest(grid=grid):
                thumb = self.engine.pool_dds(self.dds, grid)
                ow, oh = min(grid, 29), min(grid, 63)
                expected = []
                for y in range(oh):
                    for x in range(ow):
                        ys, ye = y * 63 // oh, (y + 1) * 63 // oh
                        xs, xe = x * 29 // ow, (x + 1) * 29 // ow
                        count = (ye - ys) * (xe - xs)
                        for channel in range(3):
                            total = sum(self.rgba[(row * 29 + col) * 4 + channel]
                                        for row in range(ys, ye) for col in range(xs, xe))
                            expected.append(total / count)
                self.assertEqual((thumb.width, thumb.height), (ow, oh))
                self.assertEqual(thumb.values, tuple(expected))

    def test_reserved_blocks_are_transparent_black(self):
        data = bytearray(self.dds[:148])
        struct.pack_into('<II', data, 12, 3, 2)
        data += bytes(16)
        self.assertEqual(self.engine.decode_dds(bytes(data)).rgba, bytes(24))
        self.assertEqual(self.engine.pool_dds(bytes(data)).values, (0.0,) * 18)

    def test_srgb_tag_preserves_encoded_values_and_ignores_later_mips(self):
        data = bytearray(self.dds)
        struct.pack_into('<I', data, 128, 99)
        self.assertEqual(self.engine.decode_dds(bytes(data) + bytes(16)).rgba, self.rgba)

    def test_legacy_bc7_fourcc(self):
        data = bytearray(self.dds[:128])
        data[84:88] = b'BC7 '
        self.assertEqual(self.engine.decode_dds(bytes(data) + self.dds[148:]).rgba, self.rgba)

    def test_bad_or_unsupported_container_is_rejected(self):
        invalid = [b'', self.dds[:147], self.dds[:-1], b'bad!' + self.dds[4:]]
        for offset, value in ((4, 0), (12, 0), (76, 0), (80, 0), (112, 0x200),
                              (128, 95), (132, 4), (136, 4), (140, 2)):
            data = bytearray(self.dds)
            struct.pack_into('<I', data, offset, value)
            invalid.append(bytes(data))
        for data in invalid:
            with self.subTest(header=data[:16]):
                with self.assertRaises(ValueError):
                    self.engine.pool_dds(data)
                with self.assertRaises(ValueError):
                    self.engine.fingerprint_dds(data)

    def test_pool_grid_validation(self):
        for grid in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                self.engine.pool_dds(self.dds, grid)

    def test_c_rejects_short_buffers_before_writing_output(self):
        width, height, blocks = _base_mip(self.dds)
        output = (ct.c_ubyte * (width * height * 4))(*([67] * (width * height * 4)))
        for size, capacity in ((len(blocks) - 1, len(output)), (len(blocks), len(output) - 1)):
            self.assertEqual(self.engine.library.herta_dds_decode_bc7(
                blocks, size, width, height, output, capacity), 0)
            self.assertEqual(bytes(output), bytes([67]) * len(output))
        means = (ct.c_double * 12)(*([67.0] * 12))
        self.assertEqual(self.engine.library.herta_dds_pool_bc7(
            blocks, len(blocks), width, height, 2, 2, means, 11), 0)
        self.assertEqual(tuple(means), (67.0,) * 12)

    def test_both_batch_paths_are_ordered_bounded_and_reentrant(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            for index in range(12):
                # Each file has different content, so output aliasing is visible.
                blocks = self.dds[148:]
                shift = index * 16
                path = Path(temporary) / f'{index}.dds'
                path.write_bytes(self.dds[:148] + blocks[shift:] + blocks[:shift])
                paths.append(path)
            for mode in ('similarity', 'pixels'):
                method = (lambda data: self.engine.pool_dds(data, 7)) if mode == 'similarity' else self.engine.fingerprint_dds
                expected = [(path, method(path.read_bytes())) for path in paths]
                for workers in (2, 4, 8, 16, 32, 64, 128):
                    with self.subTest(mode=mode, workers=workers):
                        requested = []

                        def source():
                            for path in paths:
                                requested.append(path)
                                yield path

                        results = self.engine.analyze_files(
                            source(), mode=mode, workers=workers, grid=7)
                        first = next(results)
                        self.assertEqual(len(requested), min(workers, len(paths)))
                        self.assertEqual([first] + list(results), expected)

    def test_batch_errors_are_not_treated_as_duplicates(self):
        with self.assertRaises(FileNotFoundError):
            list(self.engine.analyze_files([FIXTURES / 'missing.dds']))
        for kwargs in ({'workers': 0}, {'workers': True}, {'mode': 'unknown'}):
            with self.assertRaises(ValueError):
                list(self.engine.analyze_files([], **kwargs))


if __name__ == '__main__':
    unittest.main()
