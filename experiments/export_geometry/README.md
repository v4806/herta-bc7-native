# Lossless geometry export acceleration

This standalone snapshot contains the original C++ kernels, C ABI DLL, NumPy /
ctypes adapter, CMake target and deterministic reference tests installed in
TheHerta4 on 2026-10-26. No Blender project or game assets are included.

Functions: `blend_layout_arrays(offsets, groups, weights, loops, channels)` and
`stable_unique_rows(uint8_rows)`. They return `None` when unavailable, so a caller
can keep its Python / NumPy fallback. The optional `extract_blend_layout(mesh,...)`
adapter reads Blender RNA on its calling main thread, then invokes the array
kernel. No worker touches bpy. Windows x64 / SSE2, Python 3.12+ and NumPy are
the validated weight path; row hashing is independent of Python sum semantics.

Build with an x64 MSVC C++20 toolchain:

```
cmake -S common/native/export_geometry -B build -A x64
cmake --build build --config Release
```

Copy the resulting DLL beside `common/native/export_geometry.cpp`. Keep strict
floating arithmetic (`/fp:precise`). Run reference tests from this directory:

```
python -m unittest discover -s tests -p test_export_geometry_native.py
```

`BUILD.json` records compiler flags and SHA256s matching the installed files.
The detailed ABI / performance notes are in the native source folder README in
the installed addon, and `docs/geometry-export-optimization-2026-10-26.md` in
the repository root. Per-kernel speedups are not whole-export speedups.
