# TheHerta4 导出性能实测与改动

**最新状态**：已将已验证的原生 PNG→BC7 编码接入正式单张/批量导出流程，同时核对 C 解码、跨进程缓存与几何哈希并行。安装文件和实测见 [正式落盘清单](herta4-installed-accelerators-2026-10-25.md)。下文是各阶段原始记录，较早的“尚未切换”已由本次正式接入更新。

日期：2026-10-25。实例：Blender 5.2.2 LTS，PID 5524；蓝图 `SSMT BluePrint`。
使用现有工程，通过 `INVOKE_DEFAULT` 启动独立后台导出进程。所有实机导出均成功。

## 已接入的优化

- BC7 由可重入 C DLL 解码。相似度直接累计 RGB 特征图，像素模式输出完整 RGBA。
- 实际目标预检使用相似度 16 线程；开启像素去重时使用 32 线程。选择依据是实际 73 张目标的吞吐量，不按 CPU 核心数压低原生并发。
- 新的 DDS 目标按输出格式和目标目录合批调用 texconv。相同进程复用 GPU 上下文；保持原格式、色彩标志、mip 和质量参数。
- 源词干冲突时分批，避免同名覆盖；限制每批数量与命令行长度；单批部分失败只接收有效产物，未完成项继续走原转换与回退机制。
- 已存在的目标仍由资源合并节点的配置执行同名智能覆盖检查。
- 识别 texconv 默认输出的 legacy RGBA8/BGRA8 位掩码头，避免把有效未压缩 DDS 误判为未知并重新编码。
- 增加逐张/批量编码计时、贴图计划统计和后台阶段 `timings.json`。

## 整体结果

| 测试 | 观测总耗时 | 转码调用耗时 | 实际结果 |
|---|---:|---:|---|
| 空输出贴图目录，原逐张转码 | 97.45 s | 60.62 s | 73 次调用，73 张重新编码 |
| 批量编码的中间验证 | 91.33 s | 47.63 s | 61 张批量；12 张 legacy DDS 走回退 |
| 空目录，最终批量方案 | 76.44 s | 40.39 s | 3 次调用，73 张全部批量，无逐张重试 |
| 已有贴图，智能覆盖回归 | 38.93 s | 0 s | 16 线程预检，73 张全跳过，写入 0 |

最终空目录测试比逐张基线总耗时少约 21.6%，转码调用耗时少约 33.4%。这不是完全清空缓存的测试：源特征缓存保持工程正常配置，输出贴图目录在空目录测试前已移空。总耗时为外部监控的进程生命周期观测值，含轮询采样误差，不是多轮性能保证。

原文件在移走前完成 SHA256 备份核对。最终 73 张 DDS 与逐张编码基线字节完全一致，73 个唯一贴图 INI 引用均有效。已有贴图回归再次确认 SHA256 未改变。

基线日志证实 BC7 已使用 RTX 2060 的 DirectCompute 5.0。8 张真实源图的独立对照中，逐张编码约 7.79 s、单批约 5.29 s；尝试 2/4/8 个 GPU 编码进程约 5.0～5.4 s，未出现额外显著收益。因此当前采用同格式合批。

后台 Blender 工作集峰值约 2.3 GiB；本轮没有内存容量不足的证据。

## 剩余耗时与优化优先级

最终空目录和已有目标两轮中，导出器构建约 20.9～22.4 s，包含以下子阶段，不能把父阶段与子阶段相加：

| 子阶段 | 最终空目录 | 已有目标 | 代码分析与下一步 |
|---|---:|---:|---|
| 几何/权重哈希预计算 | 6.84 s | 8.42 s | `_extract_object_raw_data` 逐顶点遍历权重，生成大量 Python 对象；`compute_hash` 再逐项 `struct.pack`/`md5.update`。MD5 本身已有原生实现，优先批量打包权重与减少 Python 调用。 |
| Element 数据解析 | 6.92 s | 6.89 s | 包含 Blender 网格求值、切线计算、属性提取。需要分开计时；Blender API 读取留在主线程，提取后的纯数组转换可交给 NumPy/C 或并行任务。 |
| 索引去重与 Buffer 构建 | 3.64 s | 3.66 s | 当前已用 NumPy 的 C 排序/unique。可评估哈希去重和减少结构化数组拷贝；替代算法需要复现原来的去重键、首项和索引顺序。 |

此外，前处理约 2.5 s，蓝图解析约 2.7～2.9 s。缓冲文件写出约 0.09 s，INI 生成约 0.8～1.0 s，形态键资源生成约 0.3 s；这些不是当前优先优化项。

已有目标预检实际墙钟耗时 0.926 s，73 次缓存命中。`target_md5=9.413s` 是 16 个并行任务的累计耗时，不能把它当作 9.413 秒串行等待。相似度比较 73 对约 0.021 s，继续增加比较线程的收益有限。

## 其它 DDS 编码方案与专用引擎

后续已完成 BC7f 原生编码原型和 ISPC 对照。详细测量、色彩空间排查、质量限制及上游资料见 [DDS 编码调研笔记](dds-encoder-research-2026-10-25.md)。当前正式导出仍使用已有 texconv GPU 合批方案。

- Intel ISPCTextureCompressor：已测 6 张基础层的 veryfast/fast/basic 与不透明自适应预设；veryfast 原生编码 6 线程约 2.47 s，但不含解码、mip、文件读写。可保留为质量回退候选。https://github.com/GameTechDev/ISPCTextureCompressor
- bc7e / bc7enc_rdo：SIMD/多线程 BC7 编码器。https://github.com/richgel999/bc7enc_rdo
- bc7f：已编出 C ABI DLL，16 线程完成 61 张真实源图及完整 mip。按源色彩信息修正后的完整流程 21.85 s，其中原生编码与读写 4.32 s，RGBA/mip 前置准备 16.68 s，输入规范化 0.85 s。该次 GPU 参考为 89.32 s；与此前正式导出的 40.39 s 不是同一轮环境，不能直接外推整体加速。61 张全部通过现有 98% 相似度阈值，最低 99.21%；alpha 单点误差仍需单独验收。https://github.com/BinomialLLC/basis_universal/wiki/Transcoder-Internals-Analytical-Real-Time-Encoders-and-Transcoders
- Compressonator：有 CPU/GPU 编码 SDK 和可配置质量。https://github.com/GPUOpen-Tools/compressonator

texconv 本身已有 C++/GPU 编码。自制专用 C/C++ 引擎已经通过独立原型证明可行，合适的做法是复用成熟编码器，提供批量 C ABI、PNG 解码与 mip 生成流水线，减少跨进程和中间文件开销。已有正式 BC7 解码 DLL 与新实验编码 DLL 是不同组件；尚未切换正式编码流程。不能仅凭原生语言就推定总导出会获得数百倍提升。

DirectXTex 的 `-bc q` 也可减少搜索，但只使用 BC7 mode 6，属于质量/速度取舍；本轮未启用，保持了已有输出字节。官方选项文档：https://github.com/microsoft/DirectXTex/wiki/texconv

### 后续方案清单

**最新进度**：第 1 项已完成独立原型，移除 texconv/RGBA 中间步骤；61 张完整 mip 的 16 线程中位数 **4.684 s**，各档 3 次。第 2 项已完成图间 4/8/16/24/32 线程扫描，当前批次 16 最低；尚未做图内块行任务。源码及限制见 [原生内存流水线实测](native-memory-pipeline-2026-10-25.md)。正式导出编码器尚未切换。

**磁盘缓存已完成**：第 4 项已接入正式 texconv 单张/批量入口和实验原生接口。61 张跨新进程热轮：texconv **1.104/1.155 s**，原生 **1.823/1.931 s**；产物与各自基线一致。查重与覆盖机制不变，详见 [缓存成果](dds-artifact-cache-2026-10-25.md)。

**几何哈希优化已接入**：第 5 项完成连续权重列数组 + C 批量打包 + 对象并行，保留原哈希字节；合成 96 万顶点/256 万权重中位 **3.897 → 0.704 s**，未完成真实工程重测。第 6 项新增 Element 求值/切线/属性的分项日志。详见 [几何优化成果与限制](geometry-hash-optimization-2026-10-25.md)。

1. 原生内存流水线：读取/PNG 解码、按当前源颜色规则生成 mip、BC7f 编码和 DDS 写出直接衔接，消除 RGBA 中间文件；分别测量各阶段。
2. 图像与块行调度：大图可拆块，交错测编码 4/8/16/24/32/64 线程；避免图间与图内线程乘积过大。现有去重线程结论不能代替编码线程扫描。
3. 自适应质量回退：对透明边缘、alpha、数据图的误差单独检查，必要时回退 ISPC 高质量或原 GPU 编码；不能仅靠 RGB 相似度验收。
4. 跨次编码缓存：键包含源内容、导出格式、色彩/mip 参数及编码器版本；遵循材质转资源 Pro 与所选资源合并节点的检测规则。
5. 几何与权重哈希：批量提取和二进制打包，减少 Python 顶点/权重对象和逐项 struct.pack/md5.update；先保留原哈希语义。
6. Element 解析：拆分网格求值、切线、属性读取的时间；Blender API 访问留主线程，纯数组处理可 NumPy/C/并行。
7. 索引去重：比较稳定哈希去重与现有 NumPy 排序去重，减少拷贝；保持去重键、首项和索引顺序。
8. 更深层编码研究：SIMD 块统计、常量块快路、解码/编码重叠、常驻 GPU 上下文或自写 GPU 内核。优先做可验证的流水线优化，再决定是否值得新写内核。

正式接入新编码器后，需要重新做多轮空目标与已有目标的后台导出，并核对格式、mip、引用和透明效果；目前 21.85 s 是独立转码原型测试结果。

## 证据与还原点

- 总体机器可读结果：`C:/Temp/herta_export_optimization_report_20261025.json`
- 最终空目录日志：`C:/Temp/herta_bg_export_wfvbbvmu/worker.log`
- 最终空目录阶段计时：`C:/Temp/herta_bg_export_wfvbbvmu/timings.json`
- 已有贴图回归日志：`C:/Temp/herta_bg_export_ztv4y9p9/worker.log`
- 全程采样：`C:/Temp/herta_bg_export_wfvbbvmu_profile.json`、`C:/Temp/herta_bg_export_ztv4y9p9_profile.json`
- 输出贴图与 INI 基线备份：`D:/Program Files/agent/deepseek/file-backups/herta-empty-export-baseline-20261025-173153/manifest.json`
- 代码改前备份：`D:/Program Files/agent/deepseek/file-backups/herta-native-export-integration-20261025-171631/`
- 相关测试：48 项 DDS 转换、21 项格式识别、17 项贴图计划器、121 项后台导出、11 项独立原生引擎测试通过。
- 独立引擎的 128 线程测量记录已更新到 `https://github.com/v4806/herta-bc7-native`，提交 `ce387e6`。Blender 集成修改在当前安装的 TheHerta4 中。
