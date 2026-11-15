#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the pinned UniXNU macOS 27 route without deploying to a device."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'out/macos27'
PROFILE = 'macos-27.3-26C5035r'
SOURCE_NAMES = {'UniXNU', 'UniXNU-sheng', 'sm8550', 'uefi-sheng'}
HOST_SUITES = ('battery', 'geni-i2c', 'wn8030', 'keyboard-cover', 'keyboard-service', 'cs35l43')


def load_lock(path: Path = ROOT / 'config/macos27-upstream.json') -> dict:
    """Read one complete, commit-pinned macOS build identity."""
    lock = json.loads(path.read_text(encoding='utf-8'))
    sources = lock.get('sources', [])
    if (lock.get('schema_version') != 1 or lock.get('profile') != PROFILE
            or lock.get('build') != '26C5035r'
            or lock.get('defconfig') != 'sheng_macos_defconfig'
            or lock.get('hardware_verified') is not False
            or len(sources) != len(SOURCE_NAMES)
            or {entry.get('name') for entry in sources} != SOURCE_NAMES):
        raise ValueError('requires the complete, unqualified macOS 27.3 source lock')
    for entry in sources:
        repository = 'UniXNU-sm8550-common' if entry['name'] == 'sm8550' else entry['name']
        if (entry.get('url') != f'https://github.com/UniXNU/{repository}.git'
                or not re.fullmatch(r'[0-9a-f]{40}', entry.get('commit', ''))):
            raise ValueError('requires an official repository and full commit: ' + entry['name'])
    return lock


def git(directory: Path, *arguments: str) -> str:
    """Run Git and preserve its failure instead of silently changing sources."""
    return subprocess.check_output(
        ['git', '-C', str(directory), *arguments], text=True, encoding='utf-8',
    ).rstrip('\r\n')


def source_path(out: Path, entry: dict) -> Path:
    """Match the SoC cache path used by UniXNU's own source resolver."""
    if entry['name'] == 'sm8550':
        key = hashlib.sha1(f"{entry['url']}\n{entry['commit']}".encode()).hexdigest()[:8]
        return out / 'build/feeds' / f'UniXNU-sm8550-common-{key}'
    return out / 'sources' / entry['name']


def adapted_board(original: str) -> str:
    """Apply bounded macOS-only policy edits to the pinned board, preserving other profiles."""
    board = tomllib.loads(original)
    section = board['os_overrides'][PROFILE]['payload']
    arguments = section['kernel_args']
    if arguments.count('data-persist=2') != 1 or any(
        argument.startswith('sheng-data-persist=') for argument in arguments
    ) or arguments.count('bluetooth=1') != 1:
        raise ValueError('the pinned macOS boot-argument contract changed')
    replacement = [
        'bluetooth=0' if argument == 'bluetooth=1' else argument for argument in arguments
    ]
    replacement.append('sheng-data-persist=2')
    heading = f'["os_overrides"."{PROFILE}"."payload"]'
    if original.count(heading) != 1:
        raise ValueError('requires exactly one macOS payload table')
    start = original.index(heading) + len(heading)
    following = re.search(r'^\[', original[start:], re.M)
    end = start + following.start() if following else len(original)
    block, changed = re.subn(
        r'^"kernel_args" = \[[^\n]*\]$',
        lambda _: '"kernel_args" = ' + json.dumps(replacement, ensure_ascii=False),
        original[start:end], flags=re.M,
    )
    if changed != 1:
        raise ValueError('requires exactly one macOS kernel argument list')
    return original[:start] + block + original[end:]


def verify_source(path: Path, entry: dict) -> None:
    """Reject mismatched revisions and edits beyond our explicit board adaptation."""
    if (git(path, 'config', '--get', 'remote.origin.url').removesuffix('.git')
            != entry['url'].removesuffix('.git')
            or git(path, 'rev-parse', 'HEAD') != entry['commit']):
        raise ValueError('source identity differs from lock: ' + str(path))
    # Ignore generated files; check initialized child repositories against their gitlinks below.
    changed = set(filter(None, git(path, 'diff', 'HEAD', '--name-only', '--ignore-submodules=all').splitlines()))
    allowed = {'board.toml', 'unixnu.lock'} if entry['name'] == 'UniXNU-sheng' else set()
    if changed - allowed:
        raise ValueError('preserve unexpected source edits before continuing: ' + str(path))
    for line in git(path, 'submodule', 'status', '--recursive').splitlines():
        if line[:1] not in (' ', '-'):
            raise ValueError('submodule revision differs from its pinned gitlink: ' + line)
        if line.startswith(' '):
            child = (path / line.split()[1]).resolve()
            if not child.is_relative_to(path.resolve()) or git(
                child, 'diff', 'HEAD', '--name-only', '--ignore-submodules=all',
            ):
                raise ValueError('preserve modified submodule sources before continuing: ' + str(child))
    if entry['name'] == 'UniXNU-sheng':
        original = git(path, 'show', 'HEAD:board.toml') + '\n'
        actual = (path / 'board.toml').read_text(encoding='utf-8')
        if actual not in (original, adapted_board(original)):
            raise ValueError('refusing to replace an unknown board modification')


def prepare(lock: dict, out: Path) -> None:
    """Fetch only the four fixed source commits; device and Apple inputs remain untouched."""
    for entry in lock['sources']:
        path = source_path(out, entry)
        if path.exists():
            verify_source(path, entry)
        else:
            path.mkdir(parents=True)
            git(path, 'init', '-q')
            git(path, 'remote', 'add', 'origin', entry['url'])
            git(path, 'fetch', '--depth=1', 'origin', entry['commit'])
            git(path, 'checkout', '--detach', 'FETCH_HEAD')
            verify_source(path, entry)
    device = out / 'sources/UniXNU-sheng'
    original = git(device, 'show', 'HEAD:board.toml') + '\n'
    desired = adapted_board(original)
    if (device / 'board.toml').read_text(encoding='utf-8') != desired:
        (device / 'board.toml').write_text(desired, encoding='utf-8', newline='\n')


def upstream_command(out: Path, *arguments: str) -> list[str]:
    """Always select the full macOS profile and an isolated output directory."""
    return [
        sys.executable, str(out / 'sources/UniXNU/unixnu'), *arguments,
        '-D', str(out / 'sources/UniXNU-sheng'), '--os', PROFILE,
        '--out', str(out / 'build'),
    ]


def validate_status(status: dict, lock: dict) -> None:
    """Check the actual resolved build rather than inferring support from filenames."""
    board = status['board']
    runtime = board['payload']['runtime']
    arguments = board['payload']['kernel_args']
    required_arguments = {
        'data-persist=2', 'sheng-data-persist=2', 'gpu-metal=1', 'gpu-addon=1',
        'gpu-power=9', 'fb-gpu=1', 'dpu-scanout=2', 'touch=4', 'touch-hid=1',
        'smp=1', 'wifi=5', 'usb=1', 'audio=12', 'bluetooth=0',
    }
    required_components = {'ArmCpu', 'ShengUfs', 'Adreno740', 'AdrenoMetal', 'DarwinBoot'}
    roots = set(board['kernel']['prelink']['roots'])
    archives = board['kernel']['archives']
    if (board['board']['os_profile'] != lock['profile']
            or board['os']['target'] != 'macosx' or board['os']['arch'] != 'arm64e'
            or board['arch']['page_size'] != 4096
            or board['ipsw']['build'] != lock['build']
            or runtime['target'] != 'macos27' or runtime['build'] != lock['build']
            or runtime.get('appsync', False)
            or not runtime.get('gpu_addon') or not runtime.get('boot_shims')
            or not required_arguments <= set(arguments)
            or not required_components <= {item['id'] for item in status['components']}
            or 'build-gop-legacy-display-27.py' not in archives
            or 'component:Adreno740' not in archives
            or 'build-sheng-source-storage.py --policy-dir scripts/policies/' + PROFILE not in archives
            or not {'com.apple.iokit.IONetworkingFamily', 'com.apple.iokit.IOUSBHostFamily',
                    'com.apple.iokit.IOMobileGraphicsFamily'} <= roots
            or board['adt']['defaults']['u32']['sleep-disabled'] != 1):
        raise ValueError('resolved configuration does not select the paired macOS hardware route')
    names = [argument.split('=', 1)[0] for argument in arguments]
    if len(names) != len(set(names)) or len(' '.join(arguments).encode('utf-8')) >= 1000:
        raise ValueError('duplicate or oversized kernel argument list')
    device_entry = next(entry for entry in lock['sources'] if entry['name'] == 'sm8550')
    # The SoC profile is fetched at its feed pin, never selected through a local module override.
    if Path(status['profiles']['soc']).name != source_path(Path('.'), device_entry).name:
        raise ValueError('SoC source does not come from the pinned feed cache')
    if not status.get('patch_order') or any(not Path(path).is_file() for path in status['patch_order']):
        raise ValueError('a selected kernel patch is missing')


def check(lock: dict, out: Path) -> dict:
    """Resolve the real upstream profile and write a host-only qualification report."""
    for entry in lock['sources']:
        verify_source(source_path(out, entry), entry)
    subprocess.run(upstream_command(out, 'defconfig', lock['defconfig']), check=True)
    completed = subprocess.run(
        upstream_command(out, 'status', '--json'), check=True, capture_output=True,
        text=True, encoding='utf-8',
    )
    status = json.loads(completed.stdout)
    validate_status(status, lock)
    report = {
        'profile': lock['profile'], 'build': lock['build'], 'configuration_verified': True,
        'kernel_built': False, 'images_built': False, 'hardware_verified': False,
        'device_deployment': False, 'sources': lock['sources'],
        'component_gitlinks': {
            entry['name']: {
                line.split('\t', 1)[1]: line.split()[2]
                for line in git(source_path(out, entry), 'ls-tree', '-r', 'HEAD').splitlines()
                if line.startswith('160000 ')
            } for entry in lock['sources']
        },
        'components': [entry['id'] for entry in status['components']],
        'kernel_arguments': status['board']['payload']['kernel_args'],
        'patches': {str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for path in status['patch_order']},
        'board_sha256': hashlib.sha256(
            (out / 'sources/UniXNU-sheng/board.toml').read_bytes(),
        ).hexdigest(),
        'limits': ['GPU hangs remain unresolved upstream', 'system sleep disabled',
                   'camera unavailable', 'macOS Bluetooth disabled pending qualification',
                   'charging and input recovery require device qualification'],
    }
    (out / 'resolved.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    (out / 'check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def build(lock: dict, out: Path, action: str, data_seed: Path | None = None) -> None:
    """Build host artifacts through UniXNU; never invoke device deployment tools."""
    if platform.system() != 'Darwin':
        raise ValueError('the macOS 27 build requires macOS and Xcode; prepare/check also work on Linux')
    if action == 'images':
        if data_seed is None or not data_seed.is_file():
            raise ValueError('images requires --data-seed pointing to the ORIGINAL packed APFS Data seed')
        if not re.fullmatch(r'[0-9a-fA-F]{8}', os.environ.get('UNIXNU_UNIQUE_CHIP_ID', '')):
            raise ValueError('images requires UNIXNU_UNIQUE_CHIP_ID (8 hex digits); it is never recorded here')
    prepare(lock, out)
    report = check(lock, out)
    if action == 'kernel':
        command = upstream_command(out, 'build', 'kernel')
    else:
        command = upstream_command(
            out, 'release', '--uefi', str(out / 'sources/uefi-sheng'),
            '--data-ramdisk', str(data_seed.resolve()),
        )
    subprocess.run(command, check=True)
    output = out / 'build/sheng' / PROFILE / 'sheng_macos'
    kernel = output / 'kernel/kernel.macho'
    if not kernel.is_file() or not kernel.stat().st_size:
        raise ValueError('upstream completed without the expected kernel')
    report['kernel_built'] = True
    report['kernel_sha256'] = hashlib.sha256(kernel.read_bytes()).hexdigest()
    if action == 'images':
        subprocess.run(upstream_command(out, 'build', 'userdata'), check=True)
        artifacts = [output / name for name in (
            'boot/boot.img', 'payload/payload.img', 'userdata/userdata-root.img', 'package.manifest.json',
        )]
        if any(not path.is_file() or not path.stat().st_size for path in artifacts):
            raise ValueError('upstream completed without all required image artifacts')
        report['images_built'] = True
    (out / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def host_tests(lock: dict, out: Path) -> None:
    """Compile and exercise the adopted board code with upstream ASan/UBSan model tests."""
    if platform.system() != 'Linux':
        raise ValueError('run the upstream sanitizer model suites on Linux or in the Ubuntu CI job')
    for entry in lock['sources']:
        verify_source(source_path(out, entry), entry)
    device = out / 'sources/UniXNU-sheng'
    results = {}
    for name in HOST_SUITES:
        completed = subprocess.run(
            [sys.executable, str(device / f'scripts/check-{name}-host.py')],
            check=True, capture_output=True, text=True, encoding='utf-8',
        )
        print(completed.stdout, end='')
        results[name] = completed.stdout.strip().splitlines()
    report = {
        'profile': lock['profile'], 'hardware_verified': False,
        'registers_and_io_simulated': True, 'suites': results,
        'qualification': 'upstream production code with host stubs and address/undefined sanitizers',
    }
    (out / 'host-tests.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    """Expose only host-side source, verification and build operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'prepare', 'check', 'host-tests', 'kernel', 'images'))
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--data-seed', type=Path)
    args = parser.parse_args()
    lock, out = load_lock(), args.out.resolve()
    if args.action == 'plan':
        print(json.dumps(lock, indent=2, ensure_ascii=False))
    elif args.action == 'prepare':
        prepare(lock, out)
    elif args.action == 'check':
        report = check(lock, out)
        print(f"PASS: {report['profile']}; {len(report['patches'])} patches; hardware NOT verified")
    elif args.action == 'host-tests':
        host_tests(lock, out)
    else:
        build(lock, out, args.action, args.data_seed)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(f'macos27: {error}', file=sys.stderr)
        raise SystemExit(1) from error
