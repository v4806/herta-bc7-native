# TheHerta4 native modules

This folder is the corresponding C/C++ source snapshot for five optional Windows
x64 SSE2 DLLs shipped by TheHerta4: DDS decoding/pooling, hash-record packing,
blend selection/stable vertex uniqueness, BC7 encoding, and PNG analysis.

Build with an x64 MSVC toolchain and Windows SDK:

```
cmake -S addon_native -B build-addon -A x64 -DBASIS_UNIVERSAL_ROOT=<basis_universal>
cmake --build build-addon --config Release
```

Basis Universal must be pinned to ee771a7f913a3233a252eb6d281b4446f6a3c9f5.
To build only the independent DDS/geometry modules, pass HERTA_BUILD_BC7_ENCODER=OFF.
The checked-in DDS tables correspond to the addon decoder constants. Preserve
strict floating-point arithmetic and do not add AVX2 or fast-math requirements.

TheHerta4 loads these through ctypes and retains Python/NumPy/texconv fallbacks.
The repository root license applies to original code. Basis and stb notices are
retained beside their sources. SOURCE_MANIFEST.json records source SHA256s and
the exact production DLL digests, without shipping build intermediates here.
