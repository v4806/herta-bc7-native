"""Standalone BC7 DDS APIs. Runtime dependencies: Python standard library + DLL."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct
import sys


@dataclass(frozen=True)
class RGBAImage:
    width: int
    height: int
    rgba: bytes


@dataclass(frozen=True)
class PixelFingerprint:
    width: int
    height: int
    sha256: str


@dataclass(frozen=True)
class RGBThumbnail:
    width: int
    height: int
    # Row-major RGB mean values, in the original encoded 0..255 range.
    values: tuple


def _base_mip(data):
    """Read one 2D BC7 surface; reject arrays/cubemaps/volumes explicitly."""
    if not isinstance(data, bytes):
        raise TypeError('DDS data must be bytes')
    if len(data) < 128 or data[:4] != b'DDS ':
        raise ValueError('Invalid or truncated DDS header')
    if struct.unpack_from('<I', data, 4)[0] != 124:
        raise ValueError('Invalid DDS header size')
    height, width = struct.unpack_from('<II', data, 12)
    pf_size, pf_flags = struct.unpack_from('<II', data, 76)
    caps2 = struct.unpack_from('<I', data, 112)[0]
    if not width or not height or pf_size != 32 or not pf_flags & 4:
        raise ValueError('Invalid BC7 dimensions or pixel format')
    if caps2 & (0xFE00 | 0x200000):
        raise ValueError('Cubemap and volume DDS textures are unsupported')
    fourcc, offset = data[84:88], 128
    if fourcc == b'DX10':
        if len(data) < 148:
            raise ValueError('Truncated DX10 header')
        dxgi, dimension, misc, array_size, _ = struct.unpack_from('<5I', data, 128)
        if dxgi not in (98, 99):
            raise ValueError('Only BC7_UNORM and BC7_UNORM_SRGB are supported')
        if dimension != 3 or array_size != 1 or misc & 4:
            raise ValueError('Only a single 2D BC7 surface is supported')
        offset = 148
    elif fourcc != b'BC7 ':
        raise ValueError('Only BC7 DDS textures are supported')
    size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if len(data) - offset < size:
        raise ValueError('Truncated BC7 base mip')
    return width, height, data[offset:offset + size]


class BC7Engine:
    """Both native paths share one reentrant CDLL, which releases the GIL."""

    def __init__(self, library_path=None):
        if library_path is None:
            name = ('herta_dds_windows_x64.dll' if sys.platform == 'win32'
                    else 'libherta_bc7.dylib' if sys.platform == 'darwin'
                    else 'libherta_bc7.so')
            library_path = Path(__file__).resolve().parent / 'bin' / name
        self.library = ct.CDLL(str(Path(library_path).resolve()))
        self.library.herta_dds_abi_version.argtypes = []
        self.library.herta_dds_abi_version.restype = ct.c_uint
        if self.library.herta_dds_abi_version() != 1:
            raise ValueError('Unsupported Herta BC7 ABI version')
        self.library.herta_dds_decode_bc7.argtypes = [
            ct.c_char_p, ct.c_size_t, ct.c_uint, ct.c_uint, ct.c_void_p, ct.c_size_t]
        self.library.herta_dds_decode_bc7.restype = ct.c_int
        self.library.herta_dds_pool_bc7.argtypes = [
            ct.c_char_p, ct.c_size_t, ct.c_uint, ct.c_uint,
            ct.c_uint, ct.c_uint, ct.c_void_p, ct.c_size_t]
        self.library.herta_dds_pool_bc7.restype = ct.c_int

    def _rgba_buffer(self, data):
        width, height, blocks = _base_mip(data)
        output = (ct.c_ubyte * (width * height * 4))()
        if not self.library.herta_dds_decode_bc7(
                blocks, len(blocks), width, height, output, len(output)):
            raise ValueError('Native BC7 decode rejected input')
        return width, height, output

    def decode_dds(self, data):
        """Full native decode including alpha. Returns row-major RGBA8 bytes."""
        width, height, output = self._rgba_buffer(data)
        return RGBAImage(width, height, bytes(output))

    def fingerprint_dds(self, data):
        """Full native decode + SHA256 of every RGBA byte for exact dedup.

        Hash the native output buffer directly, avoiding another full pixel copy.
        Compare the whole result so dimensions participate in equality.
        """
        width, height, output = self._rgba_buffer(data)
        return PixelFingerprint(width, height, sha256(output).hexdigest())

    def pool_dds(self, data, grid=64):
        """Decode blocks directly into RGB means; no full image allocation.

        This supplies features to a caller's similarity metric. It does not
        decide which similarity threshold to use or compare alpha channels.
        """
        if isinstance(grid, bool) or not isinstance(grid, int) or grid <= 0:
            raise ValueError('grid must be a positive integer')
        width, height, blocks = _base_mip(data)
        ow, oh = min(grid, width), min(grid, height)
        output = (ct.c_double * (ow * oh * 3))()
        if not self.library.herta_dds_pool_bc7(
                blocks, len(blocks), width, height, ow, oh, output, len(output)):
            raise ValueError('Native BC7 pooling rejected input')
        return RGBThumbnail(ow, oh, tuple(output))

    def analyze_files(self, paths, *, mode='similarity', workers=4, grid=64):
        """Yield (Path, result) in input order, with at most workers jobs active.

        similarity uses fused pooling; pixels uses full decode + fingerprint.
        File reading and native work run in the same bounded worker pool.
        File/format errors propagate to the caller instead of being duplicates.
        """
        if mode not in ('similarity', 'pixels'):
            raise ValueError('mode must be similarity or pixels')
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise ValueError('workers must be a positive integer')

        def analyze(path):
            path = Path(path)
            data = path.read_bytes()
            result = (self.pool_dds(data, grid) if mode == 'similarity'
                      else self.fingerprint_dds(data))
            return path, result

        source = iter(paths)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = deque()
            for _ in range(workers):
                try:
                    path = next(source)
                except StopIteration:
                    break
                pending.append(pool.submit(analyze, path))
            while pending:
                yield pending.popleft().result()
                try:
                    path = next(source)
                except StopIteration:
                    continue
                pending.append(pool.submit(analyze, path))
