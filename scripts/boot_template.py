# SPDX-License-Identifier: GPL-3.0-or-later
"""Read OS metadata from a verified current-slot Android or Linux boot backup."""
import hashlib
import json
from pathlib import Path
import struct
import zlib


def os_version_from_backup(path: Path, *, linux_v0: bool = False) -> int:
    manifest = json.loads((path.parent / 'manifest.json').read_text())
    expected = manifest['images'].get(path.stem)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        stream.seek(0)
        header = stream.read(4096)
    if (not expected or expected['file'] != path.name
            or expected['bytes'] != path.stat().st_size or expected['sha256'] != digest):
        raise ValueError('boot template differs from its verified backup')
    if len(header) != 4096 or header[:8] != b'ANDROID!':
        raise ValueError('invalid Android boot container')
    version, = struct.unpack_from('<I', header, 40)
    kernel_bytes, = struct.unpack_from('<I', header, 8)
    if version == 4 and not linux_v0:
        os_version, = struct.unpack_from('<I', header, 16)
        if struct.unpack_from('<I', header, 20)[0] != 1584 or not os_version:
            raise ValueError('requires the recorded versioned Android v4 template')
        page = 4096
    elif version == 0 and linux_v0:
        page, os_version = struct.unpack_from('<I', header, 36)[0], struct.unpack_from('<I', header, 44)[0]
        if page not in (2048, 4096, 8192, 16384):
            raise ValueError('invalid Linux v0 page size')
        with path.open('rb') as stream:
            stream.seek(page)
            prefix = stream.read(min(kernel_bytes, 1 << 20))
        if prefix.startswith(b'\x1f\x8b'):
            prefix = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(prefix, 4096)
        if len(prefix) < 64 or prefix[56:60] != b'ARM\x64':
            raise ValueError('Linux v0 template lacks an ARM64 Image header')
    else:
        raise ValueError('boot template version requires an explicit matching mode')
    if not 0 < kernel_bytes <= path.stat().st_size - page:
        raise ValueError('kernel payload exceeds the boot backup')
    return os_version
