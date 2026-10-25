# 原生 PNG→DDS 内存流水线：完成结果

日期：2026-10-25。完成本轮用户授权的下一步：把源图解码、mip 生成、BC7f 编码与 DDS 封装串成原生内存流水线，移除 texconv 准备子进程及 RGBA 中间文件。状态为**实验引擎，尚未接入 TheHerta4 正式导出**。

## 实现与产物

- [实验目录](../experiments/bc7f_pipeline/README.md) 包含 C++ 源码、PNG 解码依赖、ctypes 接口、已测 DLL、测试和源文件 SHA256 清单。
- Python 读取原始 PNG 字节，C/C++ 完成解码→mip→BC7→DDS，Python 写最终 DDS；ctypes 调用释放 GIL。源图实际是 PNG 即可，不再为 8 张扩展名 `.dds` 的源图创建别名文件。
- 复用固定版本 Basis Universal BC7f 部分解析编码；PNG 解码为原生 stb_image 2.30，采用上游头文件 git blob `9eedabedc45b3e6fd88fae6f14a160b4d53272ec`。
- 普通 RGBA 路径按当前 WIC/Fant 语义处理预乘 alpha；sRGB 路径在线性光下缩图，alpha 独立平均。最终 DXGI 98/99 仍由每张图的原导出格式指定。
- 以查表替代 8-bit alpha 还原的重复除法，以位移替代 2 的幂面积除法。优化前后的 61 张完整 DDS 字节相同。
- 保持现有主目录 C 解码引擎、去重机制、合并节点阈值及正式插件编码器不变；实验引擎只负责编码，不自行判断覆盖或重复。

## 性能实测

Windows x64、RTX 2060、约 31.63 GiB RAM，仍使用同一批 61 张工程 BC7 源图，完整 mip。每档新 Python 进程、交错顺序、3 次，文件缓存可能已热；实际输出、SHA256 计算均计入墙钟时间。质量验证所需的额外解码与 RGBA 验证文件不计入性能时间。

| 线程 | 3 次中位耗时 | 工作集峰值，3 次最大 |
|---:|---:|---:|
| 4 | 5.169 s | 286.9 MiB |
| 8 | 4.807 s | 392.0 MiB |
| **16** | **4.684 s** | **611.3 MiB** |
| 24 | 4.924 s | 746.8 MiB |
| 32 | 5.033 s | 742.7 MiB |

当前批次选 16 线程；8 线程只慢约 2.6%，测试有运行波动，不能把它描述成所有工程的固定最优点。更多线程未带来稳定收益，峰值不到 1 GiB，没有内存容量不足的证据。61 张不是 73 张整工程贴图：12 张未压缩 DDS 不属于这组 BC7 测试。

上一轮“texconv 准备 RGBA/mip + C 编码”的流程为 **21.848 s**；本轮 16 线程中位数 **4.684 s**，阶段时间减少约 **78.6%**，约 **4.66 倍**。两轮不是同一组交错基准，倍数仅表示该本机数据的独立转码观测，不能外推成整工程导出保证。

更早 GPU 参考单次 89.322 s、正式后台导出的贴图编码 40.39 s，运行条件存在差异。不能挑最大参考时长宣称整导出获得十几倍提升。本轮未启动正式 Blender 导出。

## 正确性与质量

1. **61/61 基础层原始 RGBA 与上一轮准备流程逐字节一致**；PNG 调色板、透明度、方向均没有在这些样本上改变。
2. **61/61 基础层 BC7 压缩数据与上一轮已验证原型逐字节一致**，所以继承其现有相似度判定：61 张全部通过 98%，最低 99.2106%。这是与 BC7f 旧原型比较，不是与 texconv GPU 的压缩字节比较。
3. **15 次线程测试完整 DDS SHA256 全部相同**，并与修正 alpha 后、查表优化前的原型一致，证明这次热点替换和线程数没有改变产物。
4. 全部 mip 尺寸、层数、DXGI 标记及文件长度均校验；各层可解码。
5. 与上一轮 RGBA/mip 准备参考相比，各级平均通道偏差最大 **1/255**；所有像素最大 RGBA 差为 **[9,9,2,2]**。存在整数取整、低 alpha 还原及 gamma LUT 的微小差异，不能声称 mip 字节相同。
6. 对上一轮完整 mip 原始参考计算，最差整链 RGB PSNR 为 **40.7033 dB**，上一版 BC7f 约 40.7031 dB；基础层保持完全一致。继承的单像素 alpha 最大压缩误差仍可能为 86/255，不能仅凭 RGB 相似度完成透明边缘或数据图验收。
7. 5 组原生接口测试通过：多尺寸及 32 次并发确定性、RGB/RGBA/灰度/灰度 alpha/调色板/1-bit PNG、sRGB 与 alpha 缩图、明确拒绝不支持输入、非法 C 参数。归档目录的 DLL 和 Python 包装再次运行这 5 组检查通过。

## 排查与修正，不作为最终成果的数据

首版内存流程为 4.747 s，但 UNORM 缩图使用直接平均，没有复现 WIC 的预乘 alpha。部分半透明图小 mip 出现明显变暗，原始 mip RGB 最大误差达 240，均值偏差最大 51.375。因此该首版已经否决，不能用它作为通过验收的性能结果。

补齐预乘/还原后单次 5.856 s；再用输出等价的查表和位移优化，单次 4.853 s，随后进行上述 15 次线程基准。没有放宽用户相似度阈值，也没有改写源图来通过验证。

## 支持边界与接入前事项

- 当前支持 8-bit PNG 和低位深调色板/灰度，尺寸为 2 的幂且最大 16384；16-bit、自定义 ICC/未知 gamma、非 2 的幂尺寸会显式返回不支持。正式接入时必须继续调用现有编码器处理它们，不能静默改过滤规则或精度。
- 只实现当前实验需要的 BC7_UNORM/BC7_UNORM_SRGB 和完整 mip。其它 BC 格式、HDR、缩放、特殊 mip 参数、数组/立方体等仍应沿用现有流程。
- 预置 DLL 为本机 Windows x64 AVX2、动态 MSVC runtime；仍需通用指令集回退、安装打包和干净环境构建验证。
- 尚无游戏内视觉验收；正式启用需要透明边缘、通道打包图检查与高误差回退策略。不能用 RGB 去重通过代替这些检查。
- 正式接入后必须继续由材质转资源 Pro 调用用户所选合并节点的机制/配置完成重复检测，只有确需写出的编码任务才进入该流水线。
- 接入后再做多轮空目标、已有目标的 **INVOKE_DEFAULT 后台导出**，核对贴图引用与跳过/覆盖结果，才能确认整工程收益。

## 证据

- 线程扫描完整结果：`C:/Users/master/AppData/Local/Temp/herta_memory_worker_scan_77zwyasq/results.json`
- 逐层验证：`C:/Users/master/AppData/Local/Temp/herta_memory_pipe_v2_16_b3di_a6a/validation.json`
- 修正后、查表优化前基准：`C:/Users/master/AppData/Local/Temp/herta_memory_pipe_v2_16_b3di_a6a/results.json`
- 查表优化后单次：`C:/Users/master/AppData/Local/Temp/herta_memory_pipe_v3_16_4d5dhhwc/results.json`
- 无原始素材的持久数据：[测量汇总 JSON](native-memory-pipeline-results-2026-10-25.json)
- 既有结果及下一步优先级：[整体路线](performance-roadmap-2026-10-25.md)、[上一轮编码调研](dds-encoder-research-2026-10-25.md)、[成果工作记录](worklog-2026-10-25.md)

上游实现参考：[DirectXTex mip 源码](https://github.com/microsoft/DirectXTex/blob/main/DirectXTex/DirectXTexMipmaps.cpp)、[stb_image](https://github.com/nothings/stb/blob/master/stb_image.h)、[BC7f 说明](https://github.com/BinomialLLC/basis_universal/wiki/Transcoder-Internals-Analytical-Real-Time-Encoders-and-Transcoders)。
