# Native geometry hash packing

TheHerta4 的原对象哈希字节流保持不变，将权重拆成连续的顶点影响数、组编号和 float32 权重列，由 C 批量写回原来的 `(vertex:int32, group:int32, weight:float32)` 顺序，再交给 hashlib 的原生 MD5。每个对象独立处理，可通过 ctypes 并行调用；无共享状态、内存分配或内部线程。

`geometry_pack.c` 与 `native/herta_geometry_windows_x64.dll` 是 C 内核及已测 Windows x64 DLL。没有 C runtime 或其它 DLL 依赖，也不要求 AVX2。调用方提供有效、互不重叠的输入输出缓冲区；长度和影响数不一致会在写出前拒绝，ABI 版本为 1。

`geometry_hash.py` 是与已安装插件一致的包装：Blender API 提取仅在主线程进行，后台线程仅处理拥有的数据数组。默认最多 8 个图形哈希任务同时进行，调用方可显式传入更高 `workers`；同一批重复对象只读取和计算一次，但保留原结果列表的顺序。缓存仅限这次预计算，不跨导出复用可能已经修改的几何数据。

可设置 `HERTA_GEOMETRY_NATIVE=0` 禁用本 DLL。缺少 DLL/ABI 不支持时，继续用同字节序的批量 struct 回退，不影响正常导出。

```python
from array import array
from geometry_hash import WeightColumns, pack_weight_columns

columns = WeightColumns(array('I', [2, 0, 1]),
                        array('i', [7, 2, 5]),
                        array('f', [.25, .75, 1.0]))
data = bytes(pack_weight_columns(columns))  # 3 x 12 bytes, original order
```

本地 MSVC 重建入口为 `build_local.py`，其中编译器路径是本机路径；C 源码本身不需要 SDK/CRT。将构建结果复制到包装旁边的 `native/` 后使用。插件安装位置是 `TheHerta4-main/common/native/`。

实测与边界见 [几何哈希优化笔记](../../docs/geometry-hash-optimization-2026-10-25.md)。基准是合成 RNA 风格对象，不代表真实 Blender 工程的完整导出时间。测试入口在安装插件 `tests/test_geometry_hash.py`；`benchmark_geometry_hash.py` 是本机开发基准，依赖该测试夹具。
