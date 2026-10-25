# Thread scaling measurements

2026-10-25, Windows x64, 6 physical CPU cores, 31.63 GiB system RAM.

Each configuration runs in a fresh Python process. Order is shuffled between repeats. File-system caches may be warm. Times are medians, and memory values are the largest process working-set peak for that configuration. The 244-job workload repeats the same 61 files four times; it is not 244 distinct images. Each result digest must match across configurations. These are local measurements, not guarantees for other machines.

The standalone default is 16, based on latency for the actual 61-file batch. TheHerta4 integration uses 16 for similarity and 32 when exact pixel dedup is enabled, selected from the real 73-target preflight measurements. Explicit worker counts remain unrestricted; there is no native CPU-core cap.

## 61 张 BC7（每档 5 次）

| Workers | Similarity seconds | Peak MiB | Pixel seconds | Peak MiB |
|---:|---:|---:|---:|---:|
| 4 | 1.625 | 69.0 | 1.712 | 130.0 |
| 8 | 1.279 | 107.0 | 1.082 | 231.8 |
| 16 | 0.926 | 165.9 | 1.048 | 404.6 |
| 24 | 0.979 | 181.0 | 1.129 | 414.5 |
| 32 | 1.039 | 199.4 | 1.024 | 413.8 |
| 48 | 0.947 | 201.2 | 1.039 | 431.2 |
| 64 | 0.934 | 199.1 | 1.016 | 413.9 |

## 244 个重复计算任务（每档 3 次）

| Workers | Similarity seconds | Peak MiB | Pixel seconds | Peak MiB |
|---:|---:|---:|---:|---:|
| 8 | 5.106 | 108.0 | 5.167 | 231.3 |
| 16 | 3.992 | 185.2 | 4.663 | 426.0 |
| 32 | 4.111 | 294.7 | 4.419 | 755.8 |
| 48 | 3.995 | 314.7 | 3.829 | 788.5 |
| 64 | 3.868 | 330.4 | 4.338 | 793.8 |
| 96 | 4.286 | 343.8 | 3.857 | 800.6 |
| 128 | 3.657 | 360.5 | 4.508 | 777.7 |

## TheHerta4 73 张目标预检（每档 3 次）

| Workers | Similarity seconds | Peak MiB | Pixel seconds | Peak MiB |
|---:|---:|---:|---:|---:|
| 4 | 2.175 | 517.3 | 2.071 | 532.7 |
| 16 | 1.953 | 828.1 | 1.873 | 948.1 |
| 32 | 2.069 | 1097.5 | 1.620 | 1094.7 |
| 64 | 2.022 | 1101.7 | 1.848 | 1200.9 |

The standalone measurements include input reading, native work and verification-digest generation. The real target preflight includes MD5, DDS metadata checks, decoding and feature extraction. Its persistent feature cache is disabled for this experiment, and it does not write textures. The 73 targets contain 61 BC7 and 12 uncompressed DDS files; non-BC7 decoding uses TheHerta4's existing decoder. These phases must not be added together or presented as total export time.
