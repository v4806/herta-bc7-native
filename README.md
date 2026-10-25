# Herta BC7 Native Decoder

A small C engine that decodes BC7 (all eight modes) DDS base mip levels and can compute a thumbnail's RGB mean-pooling features without allocating a full RGBA image. It is designed as an optional accelerator for texture similarity matching.

The Windows x64 DLL is standalone: it has no Python ABI, third-party DLL, or C runtime dependency. The decoder preserves the output of the NumPy reference implementation used by TheHerta4, including endpoint rounding, reserved blocks, alpha, orientation, and cropped edge blocks. The pooling export matches the reference means exactly.

## 两条加速路径 / Two accelerated paths

| 用途 | 接口 | 处理过程 |
|---|---|---|
| 图像相似度特征 | `pool_dds(data, grid=64)` | C 逐块解码并立即累计 RGB 均值，只存储小特征图，不分配完整 RGBA 图像 |
| 像素级精确去重 | `fingerprint_dds(data)` | C 完整解码 RGBA，直接对原生输出缓冲区计算 SHA256，包含 alpha；尺寸也参与结果比较 |
| 需要完整像素 | `decode_dds(data)` | 返回尺寸和完整 RGBA8 字节 |

两条路径都通过同一个可重入 DLL 执行。Python 的 `ctypes.CDLL` 调用期间释放 GIL，`analyze_files` 默认使用 16 个线程，最多保留同样数量的在途任务，并按输入顺序返回结果。可以显式指定 `workers=32`、`workers=64`、`workers=128` 或其它正整数。C 内部不再额外创建线程，不按 CPU 核心数限制调用方的并发数。

相似度接口输出 RGB 均值，范围为 0..255；它不自行判断相似度或修改阈值。接入方继续应用自己的特征计算、相似度指标和阈值。所有基础 mip 像素均参与计算；不使用抽样或较小 mip。sRGB 标志不触发颜色变换，以保留参考实现的数值语义。

## Python usage (standard library only)

Run from the repository root or add it to `PYTHONPATH`:

```python
from pathlib import Path
from herta_bc7 import BC7Engine

engine = BC7Engine()
data = Path("texture.dds").read_bytes()
thumbnail = engine.pool_dds(data, grid=64)       # path 1: RGB mean features
fingerprint = engine.fingerprint_dds(data)      # path 2: exact RGBA fingerprint
image = engine.decode_dds(data)                 # optional full RGBA8 pixels

# Results retain input order. Both modes use bounded native parallel calls.
for path, result in engine.analyze_files(
        ["a.dds", "b.dds"], mode="similarity", workers=16):
    print(path, result.width, result.height)
for path, result in engine.analyze_files(
        ["a.dds", "b.dds"], mode="pixels", workers=32):
    print(path, result.sha256)
```

`RGBThumbnail.values` is row-major packed RGB. `PixelFingerprint` equality includes width, height and the SHA256 of RGBA bytes. Invalid files and unsupported formats raise errors; they are not considered duplicates. The Python DDS loader supports one 2D BC7_UNORM/BC7_UNORM_SRGB DX10 surface and the legacy `BC7 ` FourCC; arrays, cubemaps, volumes and other BC formats are rejected. Later mip levels are ignored.

Command-line examples:

```powershell
python examples/analyze_dds.py --mode similarity --workers 128 a.dds b.dds
python examples/analyze_dds.py --mode pixels --workers 32 a.dds b.dds
```

2026-10-25 已测试到 128 线程，包含 61 张真实 BC7、244 个重复计算任务，以及
TheHerta4 的 73 张目标贴图预检。所有档位的结果均一致。当前批次下 16 线程的
相似度路径中位数最低，独立接口默认用 16；实际导出预检按吞吐量选相似度 16、
像素去重 32。更大任务队列可显式提高并发。完整数据及测量范围见
[BENCHMARKS.md](BENCHMARKS.md)。

## C ABI

Include `include/herta_bc7.h`. `herta_dds_decode_bc7` writes packed RGBA8;
`herta_dds_pool_bc7` writes packed RGB float64 means. These C functions accept
raw base-mip BC7 blocks, without a DDS header. The caller allocates the output
and may call either function concurrently with separate output buffers. Both
return 1 on success or 0 for invalid input/capacity. ABI version remains 1.

## Files

- `src/dds_decode.c`: C implementation.
- `src/dds_tables.h`: generated BC7 lookup tables required to build the C source.
- `bin/herta_dds_windows_x64.dll`: prebuilt Windows x64 library.
- `scripts/build_windows.ps1`: rebuild the DLL with MSVC.
- `include/herta_bc7.h`: public C/C++ ABI declarations and buffer contracts.
- `herta_bc7.py`: Python loader, both accelerated paths and bounded batch API.
- `examples/analyze_dds.py`: command-line example for both paths.
- `tests/`: independent fixed vectors, exact pooling checks and concurrency tests.

## Build

Install Visual Studio Build Tools with the x64 C++ compiler, then run PowerShell:

```powershell
.\scripts\build_windows.ps1 -VcVars "C:\Path\To\VC\Auxiliary\Build\vcvars64.bat"
```

The output is written to `bin/herta_dds_windows_x64.dll`.

## Validation

```powershell
python -m unittest discover -s tests -v
```

Tests use synthetic vectors for every BC7 mode, with fixed expected pixels from
the independent NumPy reference. NumPy is not required to run them. Coverage
includes cropped edges, exact RGB pooling, alpha-inclusive pixel fingerprints,
invalid buffers/containers, and both ordered bounded concurrent paths. Fixture
regeneration instructions are in `tests/fixtures/README.md`.

## License and attribution

This repository is distributed under GPL-3.0-or-later. The BC7 decoding logic follows the BPTC specification and a scalar reference implementation adapted from the bimg project. See the TheHerta4 project for the original NumPy reference and integration.
