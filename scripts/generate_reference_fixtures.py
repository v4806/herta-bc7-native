"""Regenerate fixed BC7 vectors using TheHerta4's independent NumPy reference.

Usage: python scripts/generate_reference_fixtures.py path/to/common/dds_pixel.py
NumPy is required only for regenerating these fixtures, not for engine use/tests.
"""
import importlib.util
from hashlib import sha256
from pathlib import Path
import struct
import sys
from unittest.mock import patch


def main():
    spec = importlib.util.spec_from_file_location('dds_reference', sys.argv[1])
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    blocks = []
    for mode in range(8):
        for index in range(16):
            block = bytearray(sha256(f'herta-bc7-{mode}-{index}'.encode()).digest()[:16])
            block[0] &= 255 ^ ((1 << (mode + 1)) - 1)
            block[0] |= 1 << mode
            blocks.append(block)
    width, height = 29, 63
    header = bytearray(148)
    header[:4] = b'DDS '
    struct.pack_into('<I', header, 4, 124)
    struct.pack_into('<I', header, 8, 0x81007)
    struct.pack_into('<III', header, 12, height, width, len(blocks) * 16)
    struct.pack_into('<II', header, 76, 32, 4)
    header[84:88] = b'DX10'
    struct.pack_into('<I', header, 108, 0x1000)
    struct.pack_into('<5I', header, 128, 98, 3, 0, 1, 0)
    data = bytes(header) + b''.join(blocks)
    with patch.object(reference, '_get_native_library', return_value=None, create=True):
        rgba = reference.decode_dds_rgba8(data)
    if rgba is None:
        raise RuntimeError('Reference failed to decode fixture')
    root = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'all_modes.dds').write_bytes(data)
    (root / 'all_modes.rgba').write_bytes(rgba.tobytes())
    print(f'Generated {width}x{height}, 128 blocks, all eight modes; native path disabled')


if __name__ == '__main__':
    main()
