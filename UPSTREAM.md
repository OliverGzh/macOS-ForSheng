# Upstream baseline

This is a complete import of [UniXNU/UniXNU-sheng](https://github.com/UniXNU/UniXNU-sheng/tree/9ae0df2cc6666b03b83a0ca6d5691606b9024c4f), not a continuation of the old 26.5 hardware implementation.

| Source | Selected revision |
| --- | --- |
| Device repository | `9ae0df2cc6666b03b83a0ca6d5691606b9024c4f` (upstream PR #99) |
| Framework for macOS validation | `0c1bac3d51a3009dca1708b15a5198f4b43d057a` (UniXNU/UniXNU) |
| SM8550 | `2dc650ca76ae38715cd0712e60a44b14fe251745` (feeds.toml) |
| UEFI for macOS validation | `66421cb7bb5694843aec8de1ca3d1de4c20cca38` (UniXNU/uefi-sheng) |
| macOS profile | `macos-27.3-26C5035r` |
| Device defconfig | `sheng_macos_defconfig` |

All upstream tracked files, executable bits and seven driver gitlinks are preserved. Only README.md and this file differ from that baseline. The framework and SoC remain upstream dependencies; their sources are not replaced by private driver stubs. The original package workflow is preserved verbatim, including its own framework revision and iPadOS default. Use the explicit profile and paired revision below for macOS development.

## Host checks

Place the device and framework checkouts beside each other. Requires Python 3.12 or newer and Git; kernel compilation additionally requires the upstream host toolchain.

```sh
git clone --recurse-submodules https://github.com/OliverGzh/macOS-ForSheng.git device
git -C device switch 27.3
git -C device submodule update --init --recursive
git clone https://github.com/UniXNU/UniXNU.git UniXNU
git -C UniXNU checkout 0c1bac3d51a3009dca1708b15a5198f4b43d057a
cd UniXNU
python3 unixnu defconfig sheng_macos_defconfig -D ../device --os macos-27.3-26C5035r
python3 unixnu status -D ../device --os macos-27.3-26C5035r --json
# macOS/Xcode host, after installing the upstream build tools:
python3 unixnu build kernel -D ../device --os macos-27.3-26C5035r
```

Full image construction also needs the original macOS Data seed, firmware inputs, an appropriate UEFI checkout and a private device platform seed. No private seed or firmware is included. No image is offered as ready to flash.

## Evidence and limits

- Complete-import integrity and actual upstream macOS configuration resolution passed locally and in [the hosted import check](https://github.com/OliverGzh/macOS-ForSheng/actions/runs/43683738067): 18 components and 146 ordered patches. This check does not compile a kernel or run on a tablet.
- [PR #99](https://github.com/UniXNU/UniXNU-sheng/pull/99) reports a complete Intel macOS host image build, explicitly without device boot testing.
- Upstream hardware observations remain in porting.toml with their original revisions and limits; they are not tests of this import.
- [PR #97](https://github.com/UniXNU/UniXNU-sheng/pull/97) describes a Data persistence argument mismatch. The imported board arguments are unchanged, so that known issue must be addressed before any future device validation.
- The import adds no new hardware changes. In particular, macOS Bluetooth pairing, GPU stability, sleep and other pending areas are not promoted to verified support.
- Host configuration checks, host model tests, kernel compilation, image construction and device tests are separate checkpoints. This branch has no new device-test result.
- The earlier hosted macOS kernel check on 2026-11-15 stopped at `scripts/policies/macos-27.3-26C5035r/OS/trusted-key.bin`: that required signed-policy input is absent from the pinned device Git tree. The bootstrap pass reached linking and several driver archives built, but no complete kernel resulted. Original policy inputs must be restored or extracted through the upstream process before retrying; no substitute key is supplied.

The previous implementation is preserved in Git history and the `archive/pre-upstream-2026-11-15` branch at `145582b5c85f7422454fb30045893e44979d322f`. Its code is absent from the current source tree.

## Attribution

The root LICENSE is the upstream **BSD-2-Clause-Patent** license with the original UniXNU copyright. Preserve it and each component's own license. Earlier project notices and licenses remain in the historical versions, not as replacement terms for the imported code.

**项目尚未成熟，请勿刷机。**
