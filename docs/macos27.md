# macOS 27.3 开发路线

> [!CAUTION]
> **项目尚未成熟，请勿刷机。** 本仓库的新集成尚未完成真机验收。构建产物仅供开发研究，不要刷入设备或照搬历史分区操作。

用户于 2026-11-15 选择迁移到 UniXNU 的 `macos-27.3-26C5035r` 路线。当前入口为 `scripts/macos27.py`；旧 26.5 / 25F71 SHENG Recovery 实验保留供对照，不参与新路线的驱动、ABI 或镜像构建。

## 审查发现与替换范围

| 原项目的缺口 | 新路线接入的上游实现 | 验证边界 |
| --- | --- | --- |
| 主要启动到 Recovery，未验收日常桌面 | UniXNU macOS profile、配套系统卷与 macOS kext 闭包 | 上游有 Finder/Dock 桌面记录；本仓库集成尚未真机运行 |
| CPU 复制显示，没有 Adreno 真机加速 | Adreno740、AdrenoMetal、Turnip、GMU/SMMU、板级显示归档 | 上游仍存在 GPU 挂起及帧时序问题 |
| 输入是 QEMU VirtIO 路径，未完成真机触控 | sheng Novatek/GENI、原生 HID、键盘盖与按键集成 | 上游 macOS 有键盘、指针及触控记录，长时间空闲恢复仍需确认 |
| Recovery 根盘与临时 Data，完整桌面持久化未完成 | ShengUfs、macOS APFS 根卷、Data seed、firmlinks、boot shim | 纳入双名称 Data 持久化参数兼容；不改变 GPT 或写入设备 |
| 没有完整 macOS 网络、USB、音频与电源接入 | 上游板级 Wi-Fi/以太网接口、DWC3、ADSP/音频、充电与电池集成 | 不能把 iPadOS 测试直接视为 macOS 验收；需要逐项复测 |
| 旧固定提交及私有 ABI 重建输入依赖较多 | 固定新框架/设备/SoC/UEFI 提交，使用上游四层配置及原有构建器 | 源码和配置检查不等于完整镜像或真机测试 |

系统版本、配套 XNU、驱动 ABI 和原版系统组件由同一个 profile 选择，不能仅更换 IPSW 文件名，也不能复用 25F71 Recovery kernelcache、Data seed 或显示 ABI 地址。

## 固定来源

提交见 [`config/macos27-upstream.json`](../config/macos27-upstream.json)。新依赖使用独立 `out/macos27/sources/`，SoC 使用同一输出目录下的上游 feed cache。

- [UniXNU macOS profile](https://github.com/UniXNU/UniXNU/tree/0c1bac3d51a3009dca1708b15a5198f4b43d057a/profiles/os/macos-27.3-26C5035r)
- [设备构建修复 PR #99](https://github.com/UniXNU/UniXNU-sheng/pull/99)：选择固定提交，记录为上游主机完整构建通过，未记录该提交真机启动。
- [Data 持久化参数修复 PR #97](https://github.com/UniXNU/UniXNU-sheng/pull/97)：同时传递新旧参数名，兼容固定存储驱动。
- [macOS 桌面记录](https://github.com/UniXNU/UniXNU-sheng/pull/71) 与 [run139 GPU/内存报告](https://github.com/UniXNU/UniXNU-sheng/blob/5ae8b4876a378a5104330a5ae514ec9d6deae373/reports/macos27-memory-run139.md)。这些是上游指定版本的记录，不是本仓库这次集成的验收结果。

## 获取与检查

Python 3.12+、Git；无需平板、IPSW 或私有平台 seed。

```sh
python3 scripts/macos27.py plan
python3 scripts/macos27.py prepare
python3 scripts/macos27.py check
python3 -m unittest discover -s tests -p test_macos27.py -v
python3 scripts/macos27.py host-tests  # Linux / Ubuntu CI: upstream ASan/UBSan model suites
```

`prepare` 只获取固定源码，并对设备配置进行两项有边界的修改：增加兼容的 `sheng-data-persist=2`，将 macOS 的蓝牙改为默认关闭。遇到不匹配的提交或未知修改会停止，不执行 reset 或覆盖。

`check` 使用真实 UniXNU 解析器检查 OS/ABI、驱动选择、kext 闭包、Data 参数和完整补丁文件。报告为 `out/macos27/check.json`；其中 `hardware_verified` 始终为 `false`。仅通过检查时，`kernel_built` 和 `images_built` 也保持 `false`。

## 构建内核与镜像

完整编译需要 macOS、Xcode 和上游构建工具。可以运行 GitHub Actions 的 **macOS 27.3 upstream integration**，选择 `kernel`；默认 `check` 不下载 Apple 系统镜像、不编译内核。

```sh
python3 scripts/macos27.py kernel
```

本地完整镜像构建另需从**同一 macOS 27.3 系统卷**生成并保留的原始 APFS Data seed，以及私有 `UNIXNU_UNIQUE_CHIP_ID` 环境变量。种子创建方式见上游 [macOS profile](https://unixnu.com/porting/macos)。现有安装必须保留并复用其原 seed，不能因缓存缺失而重新生成。

```sh
python3 scripts/macos27.py images --data-seed /absolute/path/to/original/data.dbr
```

该命令只生成主机文件，不部署设备、不生成刷机脚本、不创建可刷机 Release。实际分区容量、原始 Data seed 身份、平台身份和恢复条件仍需另行核对；不能复用旧实验布局。默认板级容量来自上游固定配置，不表示本项目已经验证全部存储规格。

## 当前仍不完善

- 本次集成尚未完成 macOS 内核/完整镜像及真机验收；以实际生成的 `build-result.json` 和后续独立记录为准。
- 上游仍有 GPU 挂起；系统休眠被关闭，相机不可用。
- macOS 蓝牙配对/重连未验证，故默认关闭；iPadOS AirPods 成功记录不用于证明 macOS 可用。
- 键盘盖长时间空闲、充电恢复、音频路由、续航和充电能力仍需单独验证。
- 不承诺 Apple 激活、账号服务、DRM、原生快充或原厂 Android 的全部硬件功能。
