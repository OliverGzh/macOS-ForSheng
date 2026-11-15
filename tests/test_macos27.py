# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('macos27', ROOT / 'scripts/macos27.py')
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

BOARD = '''[board]
os_profile = "ipados-27.0.1-24A446"
[payload]
kernel_args = ["data-persist=2", "bluetooth=1"]
["os_overrides"."macos-27.3-26C5035r"."payload"]
# Preserve this board annotation.
"kernel_args" = ["data-persist=2", "bluetooth=1", "gpu-metal=1"]
[os_overrides.other.payload]
kernel_args = ["bluetooth=1"]
'''


class MacOS27Migration(unittest.TestCase):
    def test_lock_requires_a_complete_official_pairing(self):
        lock = migration.load_lock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lock.json'
            for change in (
                {'profile': 'ipados-27.0.1-24A446'}, {'build': '25F71'},
                {'hardware_verified': True}, {'sources': lock['sources'][:-1]},
                {'sources': lock['sources'] + [lock['sources'][0]]},
            ):
                path.write_text(json.dumps(lock | change))
                with self.assertRaises(ValueError):
                    migration.load_lock(path)
            unsafe = copy.deepcopy(lock)
            unsafe['sources'][0]['url'] = 'https://example.com/UniXNU.git'
            path.write_text(json.dumps(unsafe))
            with self.assertRaises(ValueError):
                migration.load_lock(path)

    def test_storage_compatibility_and_bluetooth_policy_are_macos_only(self):
        result = migration.adapted_board(BOARD)
        before, after = migration.tomllib.loads(BOARD), migration.tomllib.loads(result)
        self.assertEqual(before['payload'], after['payload'])
        self.assertEqual(before['os_overrides']['other'], after['os_overrides']['other'])
        arguments = after['os_overrides'][migration.PROFILE]['payload']['kernel_args']
        self.assertIn('data-persist=2', arguments)
        self.assertIn('sheng-data-persist=2', arguments)
        self.assertIn('bluetooth=0', arguments)
        self.assertNotIn('bluetooth=1', arguments)
        self.assertIn('# Preserve this board annotation.', result)

    def test_changed_board_contract_is_rejected(self):
        for changed in (
            BOARD.replace('data-persist=2', 'data-persist=1'),
            BOARD.replace('bluetooth=1', 'bluetooth=0'),
            migration.adapted_board(BOARD),
        ):
            with self.assertRaises(ValueError):
                migration.adapted_board(changed)

    def test_unknown_local_modifications_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(['git', 'init', '-q', repository], check=True)
            entry = migration.load_lock()['sources'][1].copy()
            migration.git(repository, 'remote', 'add', 'origin', entry['url'])
            (repository / 'board.toml').write_text(BOARD)
            migration.git(repository, 'add', 'board.toml')
            migration.git(repository, '-c', 'user.name=Fixture', '-c',
                          'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
            entry['commit'] = migration.git(repository, 'rev-parse', 'HEAD')
            migration.verify_source(repository, entry)
            (repository / 'board.toml').write_text(migration.adapted_board(BOARD))
            migration.verify_source(repository, entry)
            damaged = BOARD.replace('gpu-metal=1', 'gpu-metal=0')
            (repository / 'board.toml').write_text(damaged)
            with self.assertRaisesRegex(ValueError, 'unknown board'):
                migration.verify_source(repository, entry)
            self.assertEqual((repository / 'board.toml').read_text(), damaged)

    def test_commands_always_select_the_same_profile(self):
        command = migration.upstream_command(Path('/fixture'), 'build', 'kernel')
        self.assertEqual(command[command.index('--os') + 1], migration.PROFILE)
        self.assertEqual(command[command.index('-D') + 1], str(Path('/fixture/sources/UniXNU-sheng')))
        self.assertEqual(command[command.index('--out') + 1], str(Path('/fixture/build')))

    def test_image_build_requires_original_seed_before_source_or_build_mutation(self):
        with patch.object(migration.platform, 'system', return_value='Darwin'), \
                patch.object(migration, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'ORIGINAL'):
                migration.build(migration.load_lock(), Path('/unused'), 'images')
            prepare.assert_not_called()

    def test_kernel_build_rejects_an_unsupported_host(self):
        with patch.object(migration.platform, 'system', return_value='Windows'), \
                patch.object(migration, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'macOS and Xcode'):
                migration.build(migration.load_lock(), Path('/unused'), 'kernel')
            prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
