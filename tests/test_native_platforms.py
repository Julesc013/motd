"""Native Unix host evidence, deliberately separate from Linux installer tests.

These tests also run on macOS CI. They create only temporary generated outputs,
never modify startup files, and distinguish an actual host observation from demo
data. Historical shells on modern Linux remain a different evidence category.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


@unittest.skipUnless(os.name == 'posix', 'Native Unix host test')
class NativePlatformTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='motd-native-platform-')
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def artifact(self, shell):
        config = motd.preset_config('workshop', shell=shell)
        config['display']['sections'] = list(motd.SECTION_IDS)
        config['display']['width'] = 100
        config['display']['rows'] = 50
        path = self.folder / ('message' + motd.artifact_suffix(config))
        path.write_text(motd.generate_artifact(config), encoding='utf-8')
        return path

    def invoke(self, executable, path, *arguments):
        return subprocess.run([executable, str(path), *arguments], capture_output=True,
                              text=True, encoding='utf-8', timeout=30)

    def test_native_bash_dispatch_runs_a_generated_file(self):
        executable = '/bin/bash'
        if not Path(executable).exists():
            self.skipTest('/bin/bash is unavailable')
        result = self.invoke(executable, self.artifact('bash'), '--demo', '--plain',
                             '--ascii', '--width', '80', '--rows', '50')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertIn('SYSTEM', result.stdout)
        self.assertIn('RESOURCES', result.stdout)
        if platform.system() != 'Linux':
            self.assertIn('Portable Unix', result.stdout)
            self.assertNotIn('Bash 4.3 or newer', result.stdout)

    def test_portable_sections_fit_and_use_additional_rows(self):
        path = self.artifact('sh')
        counts = {}
        for width, rows in ((40, 25), (40, 50), (80, 25), (80, 50)):
            with self.subTest(width=width, rows=rows):
                result = self.invoke('/bin/sh', path, '--demo', '--plain', '--ascii',
                                     '--width', str(width), '--rows', str(rows))
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = result.stdout.splitlines()
                self.assertLessEqual(len(lines), rows - 1)
                self.assertTrue(all(len(line) == width for line in lines), result.stdout)
                for title in ('SYSTEM', 'RESOURCES', 'SERVICES', 'PROCESSES',
                              'SESSIONS', 'CONNECTIONS', 'ATTENTION', 'HINTS', 'I/O'):
                    self.assertIn(title, result.stdout)
                counts[width, rows] = len(lines)
        for width in (40, 80):
            self.assertGreater(counts[width, 50], counts[width, 25])

    def test_live_portable_identity_comes_from_this_host(self):
        result = self.invoke('/bin/sh', self.artifact('sh'), '--no-hooks', '--plain',
                             '--ascii', '--width', '120', '--rows', '50')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('demo-host', result.stdout)
        self.assertIn(platform.system(), result.stdout)
        self.assertIn('Memory', result.stdout)
        self.assertNotIn('command not found', result.stderr)
        self.assertNotIn('syntax error', result.stderr)

    @unittest.skipUnless(shutil.which('zsh'), 'Actual Zsh executable unavailable')
    def test_zsh_delegation_matches_the_same_hosts_bash(self):
        if not Path('/bin/bash').exists():
            self.skipTest('/bin/bash comparison is unavailable')
        options = ('--demo', '--plain', '--ascii', '--width', '80', '--rows', '50')
        bash = self.invoke('/bin/bash', self.artifact('bash'), *options)
        zsh = self.invoke(shutil.which('zsh'), self.artifact('zsh'), *options)
        self.assertEqual(bash.returncode, 0, bash.stderr)
        self.assertEqual(zsh.returncode, 0, zsh.stderr)
        self.assertEqual(zsh.stdout, bash.stdout)


if __name__ == '__main__':
    unittest.main()
