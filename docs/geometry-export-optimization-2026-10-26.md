# Element / 去重 / 前处理及基础 INI 优化（2026-10-26）

已安装至 `D:\Program Files\Blender Foundation\scripts\addons\TheHerta4-main`，并在当前 Blender PID 9028 热加载。当前工程与选中蓝图沿用现场，未保存或重载原工程，测试产物与缓存均放独立临时目录。

## 已完成

1. **权重读取与诊断合并**：`VertexGroupUtils.get_blend_layout_with_diagnostics` 只读一次 RNA，随后 C++ 批量按权重降序、group ID 升序排序、选最强 N 项、按原规则归一化，并计算相同损失统计。保留无权重刚性兜底、异常权重过滤、非法 Loop 的零行及样本顺序。DLL 缺失或 Python <3.12 则用旧实现，避免不同 Python sum 算法改变数值。
2. **C 稳定哈希去重**：继续由原代码构建参与字段、接缝特殊键和 VertexId 字节；原生内核只替换 unique + 再排首次出现顺序，返回相同 first / inverse。哈希碰撞以 memcmp 完整比较，不降低判定精度。保留 NumPy 回退。
3. **缩小前处理回传结果**：子进程用 Blender library 只写实际副本及依赖，替代把整个工作文件再保存一遍；失败保留完整工程回退。四份结果由 219,765,838 降至 113,048,644 字节，原生物体、颜色、拓扑、材质原始 ID 名及矩阵等 51 个物体指纹一致。
4. **前处理缓存减少压缩**：新缓存默认不压缩，Blender 自动识别新旧库，已有缓存不迁移。51 文件写入 0.407/0.512 -> 0.147/0.150 s，读回 0.607/0.648 -> 0.442/0.456 s；相应大小 29,341,237 -> 92,833,005 字节，约 3.16 倍。可用 `HERTA_PREPROCESS_CACHE_COMPRESSION=1` 回到压缩写入。缓存总开关/统计/清空范围不变。
5. **基础 INI 内的源图分析并行**：cProfile 确认原约 2.1 s 在 Slot 贴图登记分析，而非 INI 文本拼接。现在登记前预分析源文件，仍按原顺序确定名称/代表。预分析分两步：并行算内容哈希，再按同内容只分析一次（材料批次 153 个路径合为 83 份内容）。同时修正工作线程按实际文件头选择 PNG/DDS 路径，伪 DDS 容器不再被放行到 Blender 解码器。
6. **修正分析工作量计数**：同一预分析结果跨路径/规格复用不再重复累加 decoded/count/duration；预分析日志单列 wall time，避免把复用当成再次解码。

尝试过每个前处理子进程限 1 / 2 / 4 线程，所有 51 对象的几何与 Loop 指纹一致；交错复测没有稳定胜过自动线程。保留自动线程，没有添加无效设置或提高进程数。

## 验证

原生内核：`common/native/export_geometry.cpp`、`herta_export_geometry_windows_x64.dll`，ABI 1，MSVC 14.50.35717，x64 SSE2，C++20，`/O2 /MD /EHsc /fp:precise`。`common/export_geometry_native.py` 接入。C++ 子线程仅处理自有数组，不读 bpy。生产默认 2 个计算线程；RNA 单线程提取仍是剩余开销。独立源码/DLL/测试镜像 `experiments/export_geometry/`，BUILD.json 与安装文件 SHA256 一致。

- 5 项原生测试：1/2/4/8 线程、1/2/4/8/16 通道、随机/异常数据、刚性兜底、first/inverse、Python 版本回退；通过。
- 25 项接缝/HIMI 去重回归在显式启用原生路径时通过；NumPy 回退亦通过。权重布局、27 项颜色、缓存设置、贴图计划、源图预分析、PNG 真实头、DDS 进度及 121 项后台导出等相关检查通过。
- 完整后台逐项验证 `C:\Temp\herta_cold_optimized_8uggj_ua`：10 组网格的权重/索引字节、损失统计、unique first/inverse 均与旧实现完全一致。最大组 323,996 顶点 / 1,227,083 权重记录：4.900 -> 1.120 s；1,793,634 行、104 字节键：2.520 -> 0.180 s。此轮重复算旧实现且带 INI cProfile，58.58 s 不能当优化后速度。
- 51 对象结果库指纹 `C:\Temp\herta_preprocess_library_verified_20261026.json`：changed=[]。测试首次误把 Blender loader 就地替换的 Material 对象当原始 ID 名比较，后来在传入前复制字符串列表，正确比较库中原始材质 ID 名。
- 缓存压缩与读取：`C:\Temp\herta_cache_compression_read_20261026.json`，两种写入格式数据一致。

## 实际后台计时

不含逐项旧算法对照的完整冷导出：`C:\Temp\herta_cold_optimized_em8ay1gl`，**success，46.238 s**。空输出、前处理/分析/DDS 缓存独立且初始为空。计时从 worker 启动至最多 2 秒粒度轮询观察成功，另约 0.46 秒保存 copy 快照。

| 阶段 | 上一轮截图所列 | 本轮冷导出 |
|---|---:|---:|
| 前处理子进程运行（含启动） | 6.60 s | 6.393 s |
| 前处理结果整合及缓存 | 2.85 s | 1.813 s |
| Element 解析 | 6.01 s | 2.573 s |
| 索引去重 / Buffer | 3.65 s | 1.383 s |
| 基础 INI | 2.44 s | 1.833 s |

完整前处理共 10.54 s，构建导出器共 9.28 s。对比更近的 63pvgw2x 基线：整体 51.49 -> 46.24 s，Element 5.93 -> 2.57 s，去重 3.54 -> 1.38 s。属于单次现场计时，有正常环境波动，不承诺固定加速比例。

复用上述缓存、空的另一个输出目录再跑完整后台导出：`C:\Temp\herta_cold_optimized_ehe88sgq`，**success，28.266 s**。前处理 51/51 命中（分类 1.840 s、加载 0.788 s）；DDS 12 份 texconv 产物恢复 + 61 份原生缓存命中，decode/mip/encode 时间均为 0；总共 73 张产物复用。

## 输出对照与范围

73 DDS、45 buf、5 hlsl 与较早的完整导出逐字节一致；另两个 Position.buf 继续存在此前已记录的 float32 级差异。新冷/暖两轮 INI 在替换临时输出绝对路径后完全一致，DDS/45 buf/5 hlsl 也一致；同样两个 Position.buf 不逐字节一致。没有把全部几何声称为逐字节相同，也未做游戏画面验收。

与 04:12 的旧 INI 对照还出现 VertexLimitRaise 条件包装差异；`node_postprocess_condition.py` 显示 04:30:11 的同期修改，该文件不在本轮性能改动清单中，未回退其变更。因此旧基线整份 INI 不作为本轮性能内核的字节等价证据；内核等价由同一输入的逐项对照确认。完整对照报告：`C:\Temp\herta_geometry_export_compare_20261026.json`。

最终保存的源图统计计数修正只影响诊断汇总，已用单测验证同内容跨路径只记一次；冷/暖性能数据记录于此修正之前，实际计算流程相同。

开发/测试脚本位于 `D:\DEV\codec-probes\bc7f-engine`，核心为 build_export_geometry.py、geometry_validation_worker_20261026.py、bench_export_geometry_real_20261026.py、bench_preprocess_cache_20261026.py、bench_preprocess_threads_20261026.py、install_geometry_live_20261026.py。初次验证启动脚本出现反斜线转义问题，失败会话 jv0jyh8n 不计入结果。所有源改前备份与 SHA256 清单在 DSH file-backups/native-memory-pipeline-20261026-*。
