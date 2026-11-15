# macOS-ForSheng · UniXNU sheng 移植

> [!CAUTION]
> **项目尚未成熟，请勿刷机。**
>
> 本项目的硬件适配尚未完成，目前不能正确驱动全部设备硬件，不具备正常使用条件。源码、构建产物和历史启动记录仅供开发研究；构建成功或出现启动画面不代表系统可用。
>
> **请勿将本项目的镜像或构建产物刷入设备，也不要照搬文档中的实验分区操作。相关操作可能导致无法启动或数据丢失。**

本分支已完整替换为 [UniXNU/UniXNU-sheng](https://github.com/UniXNU/UniXNU-sheng) 的设备源码，基线为 `9ae0df2cc6666b03b83a0ca6d5691606b9024c4f`（上游 PR #99）。旧 26.5 实现和之前的混合接入层已从当前工作树移除，历史版本仍可恢复。

当前 macOS 开发目标为 **macOS 27.3 / 26C5035r**。源码、驱动子模块、板级配置、补丁、固件选择及打包脚本沿用上游；仅增加本说明和 [来源与验证说明](UPSTREAM.md)。驱动子模块应通过 `git clone --recurse-submodules` 获取，GitHub 的源码 ZIP 不包含其内容。

**上游的 `--os 27` 和原始 package 工作流默认选择 iPadOS；macOS 必须显式使用 `--os macos-27.3-26C5035r`。** 上游其他版本进入桌面的记录不等于本分支已完成真机验证。PR #99 记录的是主机完整镜像构建通过，未测试设备启动。

以下保留上游原始说明及其多系统支持范围。构建 macOS 请先阅读 [UPSTREAM.md](UPSTREAM.md)。

---

# UniXNU sheng

Device support for Xiaomi Pad 6S Pro 12.4, codename `sheng`, with Qualcomm
SM8550. The device profile selects
[UniXNU-sm8550-common](https://github.com/UniXNU/UniXNU-sm8550-common). One
branch builds every OS profile; `--os 17|26|27` picks the target (the 27
profile is the one under active maintenance).

## Structure

| Path | Contents |
| --- | --- |
| `porting.toml` | Subsystem inputs, findings, evidence and completion criteria |
| `board.toml` | Device configuration and component selection |
| `feeds.toml` | Pinned SoC source |
| `configs/sheng_defconfig` | Device kernel settings |
| `dts/sheng.dts` | Memory, CPU selection, and peripheral configuration |
| `patches/xnu/series` | Board patches |
| `proprietary-files.txt` | Firmware input paths |
| `package/` | Device policy, display, input, and diagnostics |
| `scripts/` | Device build and inspection tools |

`Adreno740` and `AdrenoMetal` provide the GPU implementation. Shared GMU,
command database, and GPU SMMU operations are in the SoC repository's
`Sm8550Platform` kit. sheng supplies GPU votes, signed ZAP firmware,
reserved memory, and display integration. GPU initialization uses the
staged platform build. The hardware DTS contains GPU resources; the ADT
exports nodes with `unixnu,adt-name`.

`ShengUfs` includes the device's storage and persistence policy.
`ShengHidInput` and `ShengNovatekTouch` provide the input integration.
`QcomGeniSpi` provides the shared SPI controller interface.
`Ath12kWifi` supplies the Wi-Fi stack through board PCIe, MSI, DMA,
and network interfaces. The payload volume is 208 MiB. The device selects
sRGB display properties and a 120 Hz display timing request.

## Development record

Maintain [porting.toml](porting.toml) with every subsystem change. It records
hardware, configuration, procedures, findings, evidence and completion criteria.
The [device page](https://unixnu.com/devices/sheng) renders this record.
Maintainers and agents follow the [same guide](https://unixnu.com/porting/records).
The required `Porting record` CI check validates structure, component coverage
and updates to findings or evidence for changed code.

This repository owns the ShengUfs, ShengHidInput, ShengNovatekTouch and
ShengPreflight submodules. Shared components come from the selected profiles
and UniXNU catalog. Read the [UFS guide](https://unixnu.com/porting/ufs) before
changing storage resources or policy.

## Build

One command from this repository builds everything: dependencies, preflight,
patches, kernel, package, firmware, payload, boot image and the manifest.

```sh
UNIXNU_UNIQUE_CHIP_ID=<8 hex digits> scripts/package.sh --os 27 --uefi ../uefi-sheng
```

- The firmware inputs come from the official fastboot archive pinned in
  `board.toml` `[firmware.image]`: the preflight downloads it with concurrent
  HTTP ranges, keeps only the porting inputs, deletes the archive and
  generates the `Binaries/sheng` modules the firmware volume builds from.
  Extracted firmware lives in no repository.
- `UNIXNU_UNIQUE_CHIP_ID` is the platform seed of the device, 8 hex digits.
  It is baked into the images and stays out of every repository.
- The kernelcache, trust caches and OS volumes come from the IPSW the OS
  profile pins; the generated GPU headers come from the pinned sources the
  kernel archives fetch.
- Outputs land under `out/sheng/<profile>/<config>/` of the UniXNU checkout:
  `boot/boot.img`, `payload/payload.img`, `kernel/kernel.macho` and
  `package.manifest.json`.
- `--check` stops after deps, preflight and patches; `--no-deps` skips
  fetching on a machine whose sources are already pinned.

See the [packaging script](https://unixnu.com/porting/packaging) page for the
fixed steps, the board.toml keys and the verification the run performs.

## Build on GitHub

`.github/workflows/package.yml` runs the same script on a macOS runner and
offers the images as the run's artifacts.

1. Fork this repository and set its `UNIXNU_UNIQUE_CHIP_ID` secret to the
   platform seed of the device.
2. Actions, package, Run workflow, pick the OS profile.
3. Download the run's artifacts, then delete the run. The images serve the one
   device whose seed they bake; they are not kept.

The run installs and asserts its own tools; nothing else is needed on the
runner.

## Documentation

The documentation site is maintained in UniXNU:

- [sheng device guide](https://unixnu.com/devices/sheng)
- [Building](https://unixnu.com/building)
- [Device repository specification](https://unixnu.com/porting/device-repository)
- [Device-tree specification](https://unixnu.com/porting/device-tree)
- [Component catalog](https://unixnu.com/reference/components)
- [Migration](https://unixnu.com/porting/migration)

Report build results and device boot, storage, display, input, and GPU
observations separately, with source revisions and commands.

## GPU frame diagnostics

`gpu-trace=1 diag-export=240` exports the latency capture at 240 seconds of boot-log time. It does not schedule a reboot. The capture holds the render server's frame trace, GPU submission and display arrival, large GPU allocations, CPU occupancy, render thread waits, faults, shared-region unnests and the touch report times. `scripts/read-sheng-log.py` extracts the files and runs the decoders; the `*.touch.*` outputs keep only the touch windows. See [GPU frame diagnostics](https://unixnu.com/porting/gpu-diagnostics).

On macOS, starting the Ethernet controller without the BSD wait and the display's hot plug binding follow [macOS-DroidVM](https://github.com/Droid-VM/macOS-DroidVM), the DroidVM port booted with UniXNU.
