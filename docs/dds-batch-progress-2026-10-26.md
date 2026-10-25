# 贴图落盘从 0 跳到 61：批量进度上报修复

用户本轮导出：`C:\Temp\herta_bg_export_08hmlx13\worker.log`。DDSArtifactCacheProfile：hits=0 / misses=73；DDSNativeBatchProfile：attempts=61 / successes=61 / cache_hits=0 / 16 workers / elapsed=2.39027 s。剩余 12 张 r8g8b8a8_unorm 走 texconv，耗时 4.79235 s。因此这 61 张确实重新编码，没有读到未清理的 DDS 产物缓存。

原实现 `convert_new_textures_to_dds_batch` 在整批原生任务结束后才 progress_callback(len(completed))，所以用户只能看到 0→61。pool.map 还会按提交顺序等待结果，让靠前的慢任务挡住后面的完成通知。

已修改安装目录 `toolkit/tt_dds_conversion.py`：

- 原生任务和产物恢复使用 submit / as_completed，协调线程逐一接收实际完成结果并上报；工作线程不操作 bpy/进度中台。
- texconv 编码仍保持合批，在每张目标文件移动/发布成功后上报张数。
- 移除整批末尾重复的回调；不插入假计数、延迟或动画。

新增 tests/test_dds_batch_progress.py 3 项：阻塞第一个原生任务、通过第二个任务的完成回调解除阻塞，以验证进度不等整批且在协调线程运行；产物缓存恢复同样验证；texconv 验证每个回调对应实际已写出文件数。3 项新增、11 项原生编码、7 项产物集成通过；121 项后台导出检查通过。

当前 Blender PID 9028 已只热更新该转换函数，不重启、不保存或重载用户原工程。

完整后台冷测试使用 `C:\Temp\herta_cold_optimized_63pvgw2x` 的空输出及独立缓存，成功完成。实际进度文件监测启动时已到 61，因此只记录到 61、62、…、73；不将这份采样称作已观察到 1～60。前 61 项逐张回调由上述阻塞任务测试验证。`texture_progress_observed.json` 保存真实采样。并行处理和 GUI 约 0.2 秒刷新意味着显示可跨过多个数字，即使每张都有完成回调。

改前 SHA256 校验备份：DSH file-backups/native-memory-pipeline-20261026-041114。热更新脚本：`D:\DEV\codec-probes\bc7f-engine\install_dds_progress_live_20261026.py`；监测脚本：`observe_dds_progress_20261026.py`。
