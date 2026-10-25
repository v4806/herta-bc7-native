# Herta BC7 Native Decoder

A small C engine that decodes BC7 (all eight modes) DDS base mip levels and can compute a thumbnail's RGB mean-pooling features without allocating a full RGBA image. It is designed as an optional accelerator for texture similarity matching.

The Windows x64 DLL is standalone: it has no Python ABI, third-party DLL, or C runtime dependency. Its exported ABI is documented in `src/dds_decode.c`. The decoder preserves the output of the NumPy reference implementation used by TheHerta4, including endpoint rounding, reserved blocks, alpha, orientation, and cropped edge blocks. The pooling export matches the reference means exactly.

## Files

- `src/dds_decode.c`: C implementation.
- `src/dds_tables.h`: generated BC7 lookup tables required to build the C source.
- `bin/herta_dds_windows_x64.dll`: prebuilt Windows x64 library.
- `scripts/build_windows.ps1`: rebuild the DLL with MSVC.

## Build

Install Visual Studio Build Tools with the x64 C++ compiler, then run PowerShell:

```powershell
.\scripts\build_windows.ps1 -VcVars "C:\Path\To\VC\Auxiliary\Build\vcvars64.bat"
```

The output is written to `bin/herta_dds_windows_x64.dll`.

## License and attribution

This repository is distributed under GPL-3.0-or-later. The BC7 decoding logic follows the BPTC specification and a scalar reference implementation adapted from the bimg project. See the TheHerta4 project for the original NumPy reference and integration.
