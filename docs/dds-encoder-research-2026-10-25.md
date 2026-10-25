# DDS 编码加速调研与本机原型实测

日期：2026-10-25。状态：研究原型已编译并实测；尚未切换 TheHerta4 的正式编码器。

**接续成果**：本笔记后提出的内存流水线现已实现，61 张完整 mip 的 16 线程中位数为 **4.684 s**，详见 [本轮实测与源代码](native-memory-pipeline-2026-10-25.md)。本文保留上一轮 21.848 s 的原始范围和数据，避免混淆两个版本。

## 结论

找到了一条值得继续实现的路径：Basis Universal 的 **BC7f 部分解析式编码器 + C ABI + 多线程调度**。它减少 BC7 模式搜索，输出仍是标准 BC7 DDS，不需要游戏端安装解码插件。自制辅助引擎可行，本轮已经实际编译、调用并生成了完整 DDS；推荐复用成熟算法，再自行优化数据管线，而不是从零发明 BC7 编码格式。

本机 61 张真实 BC7 源图、完整 mip 链的独立测试中，修正色彩处理后的原型流程用时 **21.85 s**，同批 texconv GPU 参考用时 **89.32 s**。这是单次独立编码测试，约 4.09 倍，不能当作整个 Blender 导出的加速倍数。此前正式后台导出的 73 张贴图批量编码阶段为 40.39 s，测试时间和进程环境不同，存在明显运行波动，应在正式集成后交错重复测量。

重要核对：本轮 texconv 参考生成的全部 61 张 BC7 DDS，与此前逐张正式导出基线的 SHA256 **61/61 一致**。本轮编码工作负载的产物正确；时长差异不能据此归因于编码参数不同。12 张未压缩 DDS 不属于这 61 张 BC7 的编码测试范围。

## 已比较的路线

| 路线 | 实际进展 | 判断 |
|---|---|---|
| 当前 texconv GPU 合批 | 已集成；73 张从 73 次调用减少到 3 次，原始产物字节保持一致 | 稳定基线；不是 Python 逐像素编码 |
| ISPCTextureCompressor / Python 原生绑定 | 安装到隔离测试目录；测过 veryfast、fast、basic 以及 alpha/不透明预设 | 可作质量回退候选，但当前样本吞吐不及 BC7f |
| BC7f 部分解析式编码 | C++ DLL 导出 C ABI，16 线程完成 61 张及全部 mip | 本轮最有希望的编码路线，需透明度与游戏端验收 |
| BC7f 完全解析 / 最快 mode 6 | 6 张基础层样本做过速度、RGB、alpha 对照 | 更快，但极端 alpha 误差更大，不作为本轮推荐预设 |
| texconv `-bc q` | 已核对官方选项；本轮未做完整对照 | 只用 BC7 mode 6；不能假定质量和当前设置等价 |
| bc7e / bc7enc_rdo、Compressonator | 查阅了上游资料，未在本机完成全流程对照 | 保留候选，不能把文档宣称当本机实测 |
| 自写常驻 GPU 编码程序 | 设计可行，尚未实现 | 当前 texconv 已使用 GPU；优先验证算法与流水线收益，再投入新 GPU 内核 |

## 测量范围与数据

机器：Windows x64，6 个物理核心，约 31.63 GiB 内存，RTX 2060。texconv 2025.10.28.1 已使用 DirectCompute 5.0。测试驱动使用 Blender 随附 Python 3.13，全部输出写入隔离临时目录，未替换正式导出的贴图。

### 61 张完整 mip 链

| 阶段 | 时间 |
|---|---:|
| texconv GPU 参考：输入规范化 + 读取、mip、BC7、写出 | 89.322 s |
| 原型：源扩展名规范化，复用同一项测量 | 0.849 s |
| 原型：按源图色彩信息分组读取，生成 RGBA mip 中间文件 | 16.684 s |
| 原型：16 线程读取 RGBA、BC7f 编码、DDS 写出 | 4.315 s |
| 原型完整流程合计 | **21.848 s** |

不包含质量复核解码时间。原型复用了同批 texconv 参考文件，未重新跑第二次 89 s GPU 测量。规范化耗时来自上一轮相同输入的测量，原型总数是这些阶段之和；不是从单个连续 Blender 导出计时器获得的端到端耗时。线程数 16 是本轮原型选择，不宣称它已经通过编码线程扫描证明最优。以前的 16/32 最优点来自去重解码测试，不能直接当作编码最优点。

8 张源文件虽然扩展名为 `.dds`，实际内容是 PNG。测试只在隔离目录复制为正确扩展名，未修改原图；不处理这一情况会让 texconv 按错误容器读取失败。

### 质量检查

| 指标，61 张中的最差值 | texconv GPU | BC7f 部分解析原型 |
|---|---:|---:|
| 基础层：三个现有相似度分数的最小值 | 99.7396% | **99.2106%** |
| 基础层通过当前 98% 阈值 | 61/61 | **61/61** |
| 基础层 RGB PSNR | 45.12 dB | 42.94 dB |
| 完整 mip 链 RGB PSNR，按像素数加权 | 41.85 dB | 40.70 dB |
| 完整 mip 链 alpha PSNR，按像素数加权 | 48.32 dB | 49.20 dB |
| 基础层单像素最大 alpha 绝对误差，0～255 | 66 | **86** |

表格各最差值可能来自不同图。通过 RGB 相似度不等于透明边缘、通道打包数据或材质渲染完全一致。BC7 本身有损，不能承诺新编码器输出字节等于旧编码器。用户放宽相似度要求可用于选择更快的搜索策略，但透明度和数据通道仍须单独检查；本轮没有修改合并节点阈值来制造通过结果。

剩余 mip 像素差异不宜直接解释成色彩空间错误。例如某张 LightMap 的 2×2 mip 原始 RGBA 中 G 为 102/32/38/14，texconv 解码后为 56/36/97/12，原型为 102/32/38/12。这种样本的跨编码器均值差异主要来自块压缩，且新编码器在该样本更接近预编码 mip；不能要求不同有损编码器的每个小 mip 均值完全相同。本轮没有游戏内视觉验收。

### 6 张基础层微基准，不能与完整流程直接相除

- GPU texconv：3.339 s，包含读取与写出，但只编码基础层。
- ISPC 依据 alpha 是否全 255 选择预设：veryfast 单线程 10.617 s、6 线程 2.472 s；fast 18.248/4.750 s；basic 41.299/9.865 s。这里只计内存中的原生编码。
- BC7f 部分解析：单线程约 0.564 s、6 线程约 0.224 s；这里只计内存中的原生编码。
- ISPC 统一强制 alpha_veryfast 时，部分纯色图的直方图分数会在量化分箱边界骤降，即使 RGB PSNR 仍约 53 dB。采用合适的不透明预设后，该组样本最低相似度约 99.84%。这说明应同时记录像素误差，不能把直方图分数简单解释成视觉失真百分比。

## 排查过程中修正的色彩问题

1. 第一版统一生成 RGBA_SRGB mip，令一些原先按数值空间过滤的图改变亮度；6 张样本已有明显差异，不能直接接入。
2. 第二版统一生成 RGBA_UNORM mip，修好了前一组，却使带 sRGB/gamma 信息的脸部 PNG 在小 mip 上偏离；61 张测试最大跨编码器 mip 均值差约 25。其 18.80 s 时长只是排查数据，不是最终推荐版本。
3. 本轮最终原型根据源图的 sRGB/gamma 标记区分两批：49 张 UNORM、12 张 sRGB；最终 BC7 输出仍使用各贴图原配置的 DXGI 98/99。原先那批系统性 mip 亮度偏差消除。

正式实现不能仅靠本轮 PNG 标记启发式覆盖所有格式；应让原生加载器返回真实源格式与色彩标记，并复现现有导出的过滤语义。不得通过改写源图 metadata 或更改工程配置解决差异。

## 自制引擎已经做了什么

- 基于 Basis Universal 固定提交 `ee771a7f913a3233a252eb6d281b4446f6a3c9f5`（上游 Apache-2.0），提供 `herta_bc7f_init` 和 `herta_bc7f_encode` 两个 C ABI 入口。
- 主调线程初始化一次，随后 ctypes 调度并发任务；原生编码不依赖 Python 逐像素循环。当前调度粒度为图像，每张图内部依次编码 mip 和块。
- 支持任意尺寸边缘块重复填充，检查输入长度、stride、输出容量，输出标准 16 字节 BC7 块；实验 DDS 封装保留尺寸、mip 和目标 DXGI。
- 关闭上游允许不透明块 alpha 降到 254 的可选 mode-6 优化。混合透明块的单个 alpha=255 像素仍可能有损，不能据此声称所有不透明像素都保持精确。
- 验证了 1×1、2×3、4×4、7×5、31×17、64×64；每种尺寸并发 32 次输出一致；6 类非法参数均拒绝；这些随机全不透明样本解码 alpha 保持 255。
- 已有全图串行/并行确定性对照；61 张完整链均可解码。原型为本机 x64 AVX2 构建，尚未做通用 CPU 指令集回退、正式安装打包和崩溃隔离。

持久原型源码：`D:/DEV/codec-probes/bc7f-engine/bc7f_bridge.cpp`。
DLL：`D:/DEV/codec-probes/bc7f-engine/build_dynamic/herta_bc7f_windows_x64.dll`。

当前原型仍借助 texconv 做 RGBA/mip 准备，不是完整的自研 PNG→DDS 一体引擎。它证明了编码算法替换的可行性，也暴露出前置准备成为主要耗时。

## 下一步实现顺序

1. **内存流水线优先**：原生 PNG/WIC 解码 → 按当前颜色规则生成 mip → BC7f → DDS，去掉 RGBA 中间文件和重复进程启动。先分别量 PNG 解码、mip、磁盘写入，避免把整段 16.68 s 都归成 PNG 解码。
2. **分块任务与线程扫描**：按图像大小分配工作，大图拆块或块行；交错测 4/8/16/24/32/64 线程和峰值内存，避免图内线程与图间线程相乘。不能因内存足够就假设线程越多越快。
3. **质量回退**：透明边缘、alpha 测试图、通道数据图进行单独误差检查；必要时只对误差大的块/图使用 ISPC 较高质量或现有 GPU 编码。测量检查和回退本身的成本；RGB 去重判定继续调用用户选中的合并节点机制和配置。
4. **跨次缓存**：对源内容、导出格式、颜色规则、mip 参数、编码器版本共同建立键，直接沿用已验证产物。源/参数/版本改变时失效；缓存不能绕开材质转资源 Pro 的同名覆盖规则。
5. **正式背景导出验证**：先隔离目标，核对所有引用、格式、mip、alpha 与同名覆盖回归，再进行多轮空目标/已有目标 INVOKE_DEFAULT 导出。只有这一步才能得出整工程收益。
6. **再评估更大投入**：SIMD 块统计、常量块快速通路、持续 GPU 上下文、源解码与编码重叠。如果需要自写 GPU 内核，应以已有成熟编码器为对照，不能保证从零研发一定更优。

网格与权重打包、Element 数据提取、索引去重等计划，继续见 [整体性能路线笔记](performance-roadmap-2026-10-25.md)。

## 证据位置

- 全部 61 张、按源色彩规则修正后的结果：`C:/Users/master/AppData/Local/Temp/herta_source_aware_mip_61_rjj_auzn/results.json`
- 原 texconv 参考及全局 UNORM 对照：`C:/Users/master/AppData/Local/Temp/herta_matched_mip_61_ccay904c/results.json`
- 测试驱动：`C:/Temp/herta_codec_probe_20261025/benchmark_source_aware_mips.py`
- 扩展名规范化和 GPU 参考驱动：`C:/Temp/herta_codec_probe_20261025/benchmark_matched_mips.py`
- ABI 与边缘尺寸检查：`C:/Temp/herta_codec_probe_20261025/test_bc7f_contract.py`
- ISPC 基础层结果：`C:/Temp/herta_codec_probe_20261025/ispc_adaptive_results.json`
- BC7f 基础层结果：`C:/Temp/herta_codec_probe_20261025/bc7f_base_results.json`
- 原基线 SHA256 清单：`D:/Program Files/agent/deepseek/file-backups/herta-empty-export-baseline-20261025-173153/manifest.json`
- 精简、无原始贴图的持久结果：`dds-encoder-results-2026-10-25.json`，位于本笔记同目录。

## 上游一手资料

- [BC7f 算法与内部接口说明](https://github.com/BinomialLLC/basis_universal/wiki/Transcoder-Internals-Analytical-Real-Time-Encoders-and-Transcoders)：预测/解析式选择，支持完整 BC7 模式；初始化要求、线程安全、内部 API 可能变化，速度与 PSNR 取舍。
- [texconv 官方选项](https://github.com/microsoft/DirectXTex/wiki/texconv)：GPU 已是默认 BC6H/BC7 路线，`-bc q` 限制为 mode 6。
- [Intel ISPCTextureCompressor](https://github.com/GameTechDev/ISPCTextureCompressor)，[Python 原生绑定](https://github.com/K0lb3/ispc_texcomp_py)：本轮隔离使用 `ispc_texcomp` 1.0.1 wheel，检查绑定确认原生压缩释放 GIL；Intel 原仓库已归档。
- [bc7enc_rdo](https://github.com/richgel999/bc7enc_rdo)，[Compressonator](https://github.com/GPUOpen-Tools/compressonator)：未完成本机全流程基准的其他候选。
