"""Create-only export behavior; no profile or system directory is modified."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd as exporter


class PortableExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='motd-create-only-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.output = self.root/'message.ps1'
        self.recipe = self.root/'recipe.toml'
        self.manifest = self.root/'export.json'
        self.files = [{'path': str(self.output), 'content': 'Write-Output "β"\n'},
                      {'path': str(self.recipe), 'content': 'title = "β"\n'}]

    def test_new_utf8_files_and_hash_manifest(self):
        result = exporter.portable_export_new_files(self.files, self.manifest, {'name': 'test'})
        self.assertEqual(result['status'], 'exported')
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        self.assertEqual(manifest['format'], 'motd-create-only-export-v1')
        self.assertEqual(manifest['metadata'], {'name': 'test'})
        for item, entry in zip(self.files, manifest['files']):
            data = item['content'].encode('utf-8')
            self.assertEqual(Path(item['path']).read_bytes(), data)
            self.assertEqual(entry['bytes'], len(data))
            self.assertEqual(entry['sha256'], hashlib.sha256(data).hexdigest())

    def test_existing_destination_is_not_overwritten_and_other_files_are_not_created(self):
        self.recipe.write_bytes(b'keep me')
        with self.assertRaises(exporter.MotdError):
            exporter.portable_export_new_files(self.files, self.manifest)
        self.assertEqual(self.recipe.read_bytes(), b'keep me')
        self.assertFalse(self.output.exists())
        self.assertFalse(self.manifest.exists())

    def test_failure_compensates_only_owned_new_files(self):
        original_open = os.open
        def fail_second(path, flags, *args, **kwargs):
            if str(path) == str(self.recipe) and flags & os.O_CREAT:
                raise OSError('Injected second-file failure')
            return original_open(path, flags, *args, **kwargs)
        with patch.object(exporter.os, 'open', side_effect=fail_second):
            with self.assertRaises(OSError):
                exporter.portable_export_new_files(self.files, self.manifest)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.recipe.exists())
        self.assertFalse(self.manifest.exists())

    def test_failure_preserves_an_external_edit_instead_of_deleting_it(self):
        original_open = os.open
        def modify_then_fail(path, flags, *args, **kwargs):
            if str(path) == str(self.recipe) and flags & os.O_CREAT:
                self.output.write_bytes(b'external edit')
                raise OSError('Injected failure after external edit')
            return original_open(path, flags, *args, **kwargs)
        with patch.object(exporter.os, 'open', side_effect=modify_then_fail):
            with self.assertRaisesRegex(exporter.MotdError, 'preserved'):
                exporter.portable_export_new_files(self.files, self.manifest)
        self.assertEqual(self.output.read_bytes(), b'external edit')
        self.assertFalse(self.recipe.exists())
        self.assertFalse(self.manifest.exists())

    def test_partial_write_can_remove_only_its_exact_prefix(self):
        original_write = os.write
        calls = []
        def partial_then_fail(fd, data):
            calls.append(fd)
            if len(calls) == 1:
                return original_write(fd, data[:2])
            raise OSError('Injected partial-write failure')
        with patch.object(exporter.os, 'write', side_effect=partial_then_fail):
            with self.assertRaises(OSError):
                exporter.portable_export_new_files(self.files, self.manifest)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.recipe.exists())
        self.assertFalse(self.manifest.exists())

    @unittest.skipUnless(os.name == 'posix', 'Open-file rename race uses POSIX file sharing')
    def test_verification_refuses_a_filename_replaced_while_reading_its_old_descriptor(self):
        data = b'owned bytes'
        self.output.write_bytes(data)
        record = {'path': str(self.output),
                  'identity': exporter._export_identity(self.output.stat()),
                  'parents': exporter._export_parent_state(self.output),
                  'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        original_read = os.read
        replaced = []
        def replace_name_after_read(fd, size):
            block = original_read(fd, size)
            if not replaced:
                self.output.rename(self.root/'retired-owned-file')
                self.output.write_bytes(b'external replacement')
                replaced.append(True)
            return block
        with patch.object(exporter.os, 'read', side_effect=replace_name_after_read):
            self.assertFalse(exporter._export_matches_created(record))
        self.assertEqual(self.output.read_bytes(), b'external replacement')

    def test_symlink_parent_is_refused(self):
        real = self.root/'real'; real.mkdir()
        link = self.root/'alias'
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError as exc:
            self.skipTest('This host cannot create a test directory symlink: ' + str(exc))
        with self.assertRaises(exporter.MotdError):
            exporter.portable_export_new_files(
                [{'path': str(link/'message.ps1'), 'content': 'test'}], self.manifest)
        self.assertEqual(list(real.iterdir()), [])

    def test_observed_windows_reparse_parent_is_refused(self):
        original_lstat = Path.lstat
        def reparse_info(path):
            info = original_lstat(path)
            if path != self.root: return info
            return SimpleNamespace(st_mode=info.st_mode, st_dev=info.st_dev,
                                   st_ino=info.st_ino, st_file_attributes=0x400)
        with patch.object(exporter.Path, 'lstat', reparse_info):
            with self.assertRaises(exporter.MotdError):
                exporter.portable_export_new_files(self.files, self.manifest)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_manifest_collision_is_rejected_before_creation(self):
        with self.assertRaises(exporter.MotdError):
            exporter.portable_export_new_files(self.files, self.output)
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
