# 清空缓存后的导出热点与已安装优化（2026-10-26）

当前用户工程 PID 9028，选中蓝图“蕾米埃尔-紫霄金鳞”。安装目录：`D:\Program Files\Blender Foundation\scripts\addons\TheHerta4-main`。

## 用户刚完成的冷导出证据

日志 `C:\Temp\herta_bg_export_rbe6rm9r\worker.log`，分段时间 `timings.json`：前处理 13.972 s，构建导出器 15.019 s（其中 Element 解析 6.799 s、索引去重 3.401 s），基础 INI 2.344 s。源图分析 14.396 s，其中解码 10.939 s；DDS 转码总计 7.480 s。TexturePlanProfile 的 elapsed=60.588 s 自计划初始化计时，包含之前的模型处理，不能全部算到材质节点。

## 已安装改动

1. 自制 `common/native/bc7f/png_analysis.cpp` 编译为 `herta_png_analysis_windows_x64.dll`（ABI 1，MSVC 14.50、x64 SSE2、无 AVX2 要求）。基于已捆绑 stb_image，常规静态 8 位 PNG 直接解码为原始 RGBA8，或在 C 内完成精确 RGB 均值池化，跳过 Blender 图像创建、float32 foreach_get、量化和大数组池化。
2. `common/png_native.py` 管理 ABI、缓冲生命周期、并发及失败回退。16 位、动画、不支持输入继续原路径。阈值、特征算法、色彩/透明度语义均保持原设置。`HERTA_NATIVE_PNG_ANALYSIS=0` 可禁用原生入口。
3. 材质节点在主线程只收集当前 INI 涉及的目标物体/材质的源路径，计划器以最多 16 个 worker 提前分析。工作线程不访问 bpy；主线程仍按原登记顺序决定代表、切换组与文件名。文件 size/mtime 改变后丢弃预分析；不支持的输入在主线程回退。结果放单次导出内存，磁盘特征缓存仍服从“导出缓存”总开关。
4. 单次材质处理复用按名称映射产生的有序候选物体列表，每次仍重新执行实际过滤器，避免把无过滤、材质过滤、目标白名单混成同一个结果。异常/下一次导出自动清掉这个临时缓存。
5. Element 诊断的 Python float 有限性检查由 numpy.isfinite 改为 math.isfinite，保留判断语义；给并行前处理的 Snapshot / Workers / Integrate 加独立时间日志。

新增源图分析缓存目录的环境覆盖 `HERTA_TEXTURE_ANALYSIS_CACHE_DIR`，用于隔离冷缓存测试；正常默认目录及 UI 设置不变。不要通过覆盖 LOCALAPPDATA 隔离测试缓存，因为 SSMT4GlobalConfigs 也依赖它。

源码、Python 接入、CMake 目标、DLL 和 PNG_ANALYSIS_BUILD.json 均已落盘；当前 Blender 已按类方法热加载，不需要重启或保存用户工程。

## 验证与实测范围

- 当前工程 178 张支持的 PNG：原生 RGBA8 与 Blender Non-Color 结果逐字节一致，C 池化与原 NumPy 池化完全一致；23 张不满足入口条件而回退。该组串行原生解码 9.884 s，对照 Blender 28.307 s，另一次独立对照，不是完整导出时间。
- 新增 9 项测试：4 项 PNG 解码/池化/并发/工作线程约束，2 项候选物体缓存的过滤和异常生命周期，3 项源图预分析复用、缺失特征回退与文件变更失效，全部通过。17 项计划器、22 项相似度、6 项缓存设置、121 项后台导出及颜色/形态键相关检查通过。
- 4 个既有 Pro fake 模块测试（pro_scope、clear_textures、tail_restore、scan_objects）在导入时缺少假基类中的 resolve_keyswap_key，未为此修改产品行为。这些测试的 Pro 导入列表本轮没有改动。
- 同一用户保留快照、同一选中蓝图、同一原始 INI，临时 SQLite 冷缓存、带 cProfile 的节点独立重放：改前 **21.985 s**、改后 **7.958 s**（约减少 63.8%），均登记 73 项，生成 INI SHA256 均为 `16a494190152661079d62167f75f2d29483077c48d9ba0d8d924ab6aa5956531`。报告 `C:\Temp\herta_material_selected_baseline.json` / `herta_material_selected_optimized.json`。这是节点独立重放，不是整次导出加速比例。
- 从当前打开工程创建 copy 快照，使用真实 BackgroundExportSession 的完整后台 worker、空输出目录、独立的前处理/分析/DDS 缓存：**success，53.284 s**（启动 worker 至轮询观察完成）。目录 `C:\Temp\herta_cold_optimized_6p12qhk0`。53.284 s 不包含主进程约 0.4 s 保存副本，含启动和最多 2 s 完成轮询延迟。未用同步模式，未清理用户输出目录或缓存。
- 本轮完整冷导出：前处理 11.814 s；其中分类 1.819 s、快照 0.367 s、四个子进程 6.598 s、整合/缓存写入 2.848 s。源图预分析 153 文件、16 worker、1.905 s，登记内其余分析 2.843 s。61 张 BC7 原生编码 2.871 s，缓存命中 0。Element 解析 6.015 s，索引去重/Buffer 3.648 s，基础 INI 2.443 s。
- 对照用户刚才输出：73 张 DDS、45 个 buf、5 个 hlsl 逐字节相同。INI 仅 SLOT_ICON_1 注释的绝对输出路径随临时目录改变。另 2 个 Position.buf 存在微小 float32 差异，最大 4.65e-6 / 1.79e-7；未把几何称为逐字节一致，也未做游戏画面验收。报告 `C:\Temp\herta_cold_export_compare_20261026.json`。

最初的一次隔离导出因错误地隔离了 LOCALAPPDATA、且未取 selected_blueprint_name 而在读取提取数据时失败；已修正这两个测试设置。失败会话 3v1xbk57 不计入成功/性能结论。早期 SSMT BluePrint 节点重放数据也由上面的选中蓝图对照替代。

最终核对当前 PID 9028 无活动导出，原工程路径、未保存状态、选中蓝图、导出缓存开启状态保留。没有保存或重载用户原工程。

## 剩余优先级

1. Element 权重/属性提取约 6 s：诊断与正式提取仍分别扫描 RNA 权重，适合下一轮提取一次后交给批量 C 排序、降宽、归一化内核；需保持稳定 tie-break、异常权重、刚性兜底与现有字节规则。
2. 冷前处理的多进程启动/加载和结果整合：6.60 / 2.85 s。增加线程不能消除 Blender 子进程初始化与库载入；优先测量依赖加载、重复快照/结果读取及缓存写入。
3. 索引去重约 3.65 s，考虑专用 C 稳定哈希，但须保留逆映射、首项顺序和接缝键。基础 INI 写入只有约 2.44 s，不是目前第一瓶颈。
4. 12 张非 BC7 的 texconv 路径仍含较明显写文件时间。原生 RGBA DDS 路线需单独核对 mip、数据图格式及输出字节，不应直接套用 BC7 有损编码。

开发/验证脚本位于 `D:\DEV\codec-probes\bc7f-engine`：build_png_analysis.py、profile_selected_material_20261026.py、verify_png_against_blender_20261026.py、install_cold_optimizations_live_20261026.py、start_isolated_cold_background_20261026.py。改前 SHA256 校验备份在 DSH file-backups/native-memory-pipeline-20261026-*。
