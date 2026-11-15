# 实施方案

用户选择复用上游 27.3 路线后，采用独立入口直接实施。旧 26.5 构建器及锁文件保留；新入口使用 `out/macos27/` 下独立的固定版本源码和构建目录。

- 使用 UniXNU 的 ARM64E/SM8550/macOS 27.3/sheng 四层配置及原有驱动构建器。避免把 27.3 私有 ABI 地址和 vtable 直接塞入 26.5 的 SHENG 内核。
- sheng 使用 PR #99 的固定提交：该分支记录了完整 Intel macOS 镜像构建检查，未声称该提交完成真机启动验证。
- 在板级 macOS 参数中同时传入 `data-persist=2` 和 `sheng-data-persist=2`，兼容已记录的存储参数更名。来源为上游 PR #97；不改变存储地址和分区布局。
- macOS 蓝牙目前只有控制器初始化记录，配对未确认，新路线默认 `bluetooth=0`；不把 iPadOS AirPods 测试冒充 macOS 验收。
- `prepare` 仅获取固定源码；`check` 使用真实上游配置解析器核对系统、驱动选择和完整补丁顺序。`kernel` 仅在 macOS 构建内核；`images` 要求原始 Data seed 和私有平台 seed，产物保留在主机。
- CI 默认运行无需 Apple 镜像的主机检查；完整内核编译使用手动 macOS job。报告始终保持本仓库 `hardware_verified=false`。

验证重点：错版本/错 ABI 拒绝、固定提交及修改保护、Data 持久化参数兼容、macOS kext 闭包、GPU/触控板级实现的实际接入，以及入口中不存在设备部署路径。
