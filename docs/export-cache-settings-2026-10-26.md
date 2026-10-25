# 统一导出缓存设置（2026-10-26）

已修改并加载到安装目录 `D:\Program Files\Blender Foundation\scripts\addons\TheHerta4-main`。位置：3D 视图右侧 N 面板 → TheHerta4 → 基础信息 → 导出缓存（原“前处理缓存”）。

## 行为

- 一个“启用导出缓存”总开关控制前处理磁盘缓存、相似度/像素分析 SQLite 缓存、DDS 编码产物磁盘缓存；关闭后不读写这三类缓存，保留磁盘现有内容。
- 展开显示三类文件数量、占用及总占用。“清空导出缓存”清当前工程前处理缓存及本机共享贴图分析/DDS 产物缓存，后台导出运行期间禁用清空按钮。
- 保留原 RNA 字段 `enable_preprocess_cache` / `expand_preprocess_cache` 和操作符 ID `ssmt.clear_preprocess_cache`，继承已有工程设置及目录。
- 读取方法改为 `GlobalProterties.enable_export_cache()`，避免原同名 classmethod 与 RNA 字段冲突；所有串行/并行前处理调用已迁移。
- 主线程捕获总开关；工作线程只读快照，避免从工作线程访问 bpy。既有 DDSArtifactCache 实例也立即遵循新开关。
- DDS 统计和清理只处理托管 `.hdds` 文件，分析缓存只处理数据库及 SQLite sidecar；不会清理导出 Mod 的贴图。前处理统计/清理包含嵌套文件并避免遍历目录链接。

## 验证

缓存设置 6 项、前处理缓存 4 项、DDS 产物 16 项、原生编码 11 项、贴图导出计划 17 项、后台导出 121 项、相似度去重 22 项均通过。HIMI 清理测试 17 项中 4 项跳过，其余通过。后台测试须使用 `python -X utf8`，默认 GBK 会在既有 emoji 打印处报编码错误。

扩展检查 `test_export_logic_name_htmi.py` 的直接导出用例无法导入其模拟包的 export_progress（该文件本轮未修改）；另一用例通过，没有为此更改导出逻辑。

当前 Blender PID 9028 实测关闭/开启总开关、同一 DDS 实例响应、分析读写禁用及 16 次工作线程快照检查通过。四个前处理入口已实时更新为新读取方法。原工程路径、未保存状态、总开关启用状态保留；未保存或重载用户工程，未清空用户缓存。本轮没有启动完整导出速度测试。

当次统计：前处理 0 文件；分析 1 文件 / 6,582,272 字节；DDS 196 文件 / 1,208,028,047 字节；合计 1,214,610,319 字节（UI 1.13 GB）。

主要实现：`common/export_cache.py`、`common/global_properties.py`、`common/texture_dedup.py`、`toolkit/dds_artifact_cache.py`、`blueprint/preprocess_cache.py`、前处理调用入口及 `ui/ui_panel_basic.py`。

实时更新脚本及验证脚本：`D:\DEV\codec-probes\bc7f-engine\reload_export_cache_ui.py`、`verify_export_cache_live.py`。UI 截图：`C:\Temp\herta_export_cache_panel_final_20261026.png`。源码修改前的 SHA256 校验备份位于 DSH `file-backups/native-memory-pipeline-*`。
