# Experimental memory pipeline

此目录保留 2026-10-25 实测的编码原型源码、ctypes 接口、测试和 Windows x64 AVX2 DLL。**尚未接入 TheHerta4 正式导出**；原有解码接口及插件当前编码器没有改变。

直接读取 PNG 文件内容（不依赖扩展名），在原生代码里完成 PNG 解码、mip、BC7f 编码和 DDS 封装；Python 负责源文件读入与 DDS 写出，无 texconv 子进程、无 RGBA 中间文件。

已加入内容寻址的跨进程 DDS 磁盘缓存，默认位于 `%LOCALAPPDATA%/TheHerta4/cache/dds-artifacts-v1/`。`convert` 默认启用；`cache=False` 可做真实编码基准，或传入 `DDSArtifactCache(custom_directory)` 隔离缓存。`raw=True` 的验证接口始终绕过产物缓存。命中时返回 `cache_hit=True`、解码/mip/编码时间为 0，`source_srgb=None`（未重新解析源格式）。完整结果见 [磁盘缓存笔记](../../docs/dds-artifact-cache-2026-10-25.md)。正式插件只接入了 texconv 产物缓存，原生编码器仍为实验。

61 张真实贴图、完整 mip 的交错线程测试，每档三次：16 线程中位数 **4.684 s**，峰值工作集 **611 MiB**；4/8/24/32 线程分别 **5.169/4.807/4.924/5.033 s**。15 次运行的完整 DDS SHA256 均与修正后的原型一致。详细范围与质量限制见 [实测笔记](../../docs/native-memory-pipeline-2026-10-25.md)。

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from herta_pipeline import convert

def export_one(source, target, srgb):
    dds, stages = convert(Path(source).read_bytes(), srgb)
    Path(target).write_bytes(dds)
    return stages

# 在上层先依据工程配置完成去重/覆盖判断；这里只负责被选中的编码任务。
with ThreadPoolExecutor(max_workers=16) as pool:
    future = pool.submit(export_one, "input.png", "output.dds", True)
    print(future.result())
```

支持 8-bit PNG、低位深灰度/调色板 PNG，尺寸须为 2 的幂且不超过 16384；拒绝 16-bit、未知 gamma、ICC profile 和非 2 的幂尺寸。这些输入在正式集成时应继续走已有编码器。返回的 `decode_s/mip_s/encode_s` 是每个任务的墙钟计时，跨任务相加会重复计算并行时间。

普通 UNORM mip 复现 WIC/Fant 的 8-bit 预乘 alpha 缩图和还原；sRGB mip 在线性光下过滤，alpha 单独平均。整数舍入及浮点/LUT近似与原准备流程有微小差异，不能声称 mip 逐字节一致。61 张基础层像素及 BC7 数据均与上一版原型完全一致，但这不等于旧 texconv 压缩字节，也不等于游戏内视觉验收。

测试：在有 NumPy 与 Pillow 的 Python 环境中执行 `python test_pipeline.py`。`benchmark_worker.py <sources.json> <new-output-directory> <workers>` 接受记录数组，每项含 `path`、`target`、`format`（`bc7_unorm`/`bc7_unorm_srgb`）；输入清单及美术素材不随仓库分发。

重新编译需要 MSVC x64、Windows SDK 及 Basis Universal 固定提交 `ee771a7f913a3233a252eb6d281b4446f6a3c9f5`：

```powershell
cmake -S . -B build -A x64 -DBASIS_UNIVERSAL_ROOT="D:/path/to/basis_universal"
cmake --build build --config Release
```

将生成的 DLL 放到 `herta_pipeline.py` 同目录后使用。这里的 CMake 是标准 SDK 构建入口，本机预置 DLL 使用相同源码通过 MSVC 手工编译、链接并测试；尚未在装有完整 SDK 的干净环境验证 CMake 打包。预置 DLL 使用动态 MSVC runtime，与主目录的独立 C 解码 DLL 不同。

BC7f 来源 Basis Universal（Apache-2.0），保留 LICENSE_BASIS.txt、NOTICE_BASIS.txt；stb_image v2.30 的许可证在头文件末尾。自制封装遵循本仓库 GPL-3.0；`snapshot.json` 记录源码与已测 DLL 的 SHA256。只初始化一次后再并发调用，ctypes 包装已执行初始化；调用本 C ABI 的其他程序须遵守同样顺序。
