"""Portable Unix observations, geometry and deadlines on isolated fixtures.

Darwin/BSD fixtures verify parser behavior, not execution on those operating
systems. Live OS claims belong to the separate native-platform CI evidence.
"""
from __future__ import annotations

import errno
import fcntl
import os
from pathlib import Path
import pty
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


class UnixCollectorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='motd-unix-fixtures-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = os.environ.copy()
        self.env.update(PATH=str(self.bin), LC_ALL='C', TERM='xterm')
        self.env.pop('NO_COLOR', None)
        for name in ('awk', 'cat', 'rm', 'mktemp', 'timeout', 'sleep'):
            real = shutil.which(name)
            if real:
                (self.bin / name).symlink_to(real)

    def helper(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)
        return path

    def script(self, config=None, fake_os=False):
        config = config or motd.preset_config('workshop', shell='sh')
        source = (ROOT / 'runtime' / 'motd.sh').read_text()
        source = source.replace('# @MOTD_CONFIG@', motd.portable_runtime_assignments(config))
        if fake_os:
            # Redirect fixed kernel reads only in this test copy. The installed
            # runtime has no environment-controlled procfs/path override.
            source = source.replace('/proc/', str(self.root / 'absent-proc') + '/')
            source = source.replace('/sys/', str(self.root / 'absent-sys') + '/')
        path = self.root / 'fixture.sh'
        path.write_text(source)
        return path

    def run_script(self, path, *options):
        return subprocess.run(['/bin/sh', str(path), '--plain', *options],
                              env=self.env, capture_output=True, text=True, timeout=9)

    def unix_helpers(self, os_name):
        self.helper('uname', 'case "$1" in -s) echo ' + shlex.quote(os_name)
                    + ' ;; -n) echo fixture-host ;; -r) echo fixture-release ;; esac')
        self.helper('df', "printf '%s\\n' 'Filesystem 1024-blocks Used Available Capacity Mounted' '/dev/fixture 1000000 400000 600000 40% /'")
        self.helper('ps', "printf '%s\\n' '1 0.1 400 init' '22 4.5 2048 compiler' '33 1.2 8192 database'")
        self.helper('who', "printf '%s\\n' 'jules pts/0 Nov 16 11:20 (192.0.2.10)' 'jules pts/1 Nov 16 11:23 (192.0.2.20)'")
        self.helper('netstat', "printf '%s\\n' 'Active Internet connections' 'tcp4 0 0 *.22 *.* LISTEN' 'tcp4 0 0 192.0.2.1.22 192.0.2.10.1234 ESTABLISHED'")
        self.helper('date', 'echo 10000')

    def test_darwin_collectors_keep_free_memory_and_idle_jobs_distinct(self):
        self.unix_helpers('Darwin')
        self.helper('sysctl', '''case "$*" in
          '-n hw.memsize') echo 17179869184 ;;
          '-n vm.loadavg') echo '{ 0.25 0.50 0.75 }' ;;
          '-n kern.boottime') echo '{ sec = 1000, usec = 0 }' ;;
          *) exit 1 ;; esac''')
        self.helper('vm_stat', "printf '%s\\n' 'Mach Virtual Memory Statistics: (page size of 16384 bytes)' 'Pages free: 12345.'")
        self.helper('launchctl', "printf '%s\\n' 'PID Status Label' '25 0 com.example.running' '- 0 com.example.idle' '- 7 com.example.exited'")
        config = motd.preset_config('workshop', shell='sh')
        config['display']['sections'] += ['io']
        result = self.run_script(self.script(config, fake_os=True), '--width', '132', '--rows', '60')
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ('Darwin fixture-release', 'Memory free: 197520 KiB (not available)',
                     'Up: 9000 s', 'Launchd: 1 running; 2 idle; 1 nonzero exit',
                     'compiler 4.5%', 'database 8192 KiB',
                     'Sessions: 2 logged-in terminals', 'TCP: 1 established; 1 listening',
                     'unavailable: per-process I/O needs Linux procfs'):
            self.assertIn(text, result.stdout)
        self.assertNotIn('Memory available:', result.stdout)

    def test_bsd_enabled_scripts_are_not_reported_running(self):
        self.unix_helpers('FreeBSD')
        self.helper('sysctl', '''case "$*" in
          '-n hw.physmem') echo 8589934592 ;;
          '-n vm.stats.vm.v_free_count hw.pagesize') printf '%s\\n' 20000 4096 ;;
          '-n vm.loadavg') echo '{ 0.10 0.20 0.30 }' ;;
          '-n kern.boottime') echo '{ sec = 1000, usec = 0 }' ;;
          *) exit 1 ;; esac''')
        self.helper('service', "printf '%s\\n' '/etc/rc.d/sshd'")
        result = self.run_script(self.script(fake_os=True), '--width', '132', '--rows', '60')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Memory free: 80000 KiB', result.stdout)
        self.assertIn('BSD rc: enabled scripts; state unqueried', result.stdout)
        self.assertIn('/etc/rc.d/sshd: enabled', result.stdout)
        self.assertNotIn('sshd: running', result.stdout)

    def test_failed_and_missing_queries_do_not_become_healthy_zeros(self):
        self.unix_helpers('UnknownUnix')
        for name in ('df', 'ps', 'who', 'netstat'):
            self.helper(name, 'exit 7')
        result = self.run_script(self.script(fake_os=True), '--width', '100', '--rows', '50')
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ('Memory: unavailable', 'Storage: unavailable', 'Service state: unavailable',
                     'CPU: unavailable', 'RSS: unavailable', 'Sessions: unavailable',
                     'Connections: unavailable'):
            self.assertIn(text, result.stdout)
        self.assertNotIn('0 failed', result.stdout)
        self.assertNotIn('0 logged-in', result.stdout)

    def test_service_exclusions_and_required_patterns_are_data(self):
        self.helper('systemctl', "printf '%s\\n' 'sshd.service loaded active running SSH' 'backup.service loaded failed failed Backup' 'ollama.service loaded active running Model'")
        config = motd.preset_config('workshop', shell='sh')
        config['services']['required'] = ['backup', 'missing-*']
        result = self.run_script(self.script(config), '--width', '132', '--rows', '60')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Services: 1 active; 1 failed', result.stdout)
        self.assertIn('Required service: backup.service: failed/failed', result.stdout)
        self.assertIn('missing-*: unavailable (not reported)', result.stdout)
        self.assertNotIn('ollama.service', result.stdout)

    def test_direct_helper_deadline_works_without_gnu_timeout(self):
        timeout = self.bin / 'timeout'
        if timeout.exists():
            timeout.unlink()
        self.helper('df', 'exec sleep 20')
        started = time.monotonic()
        result = self.run_script(self.script(), '--width', '80', '--rows', '25')
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 4)
        self.assertIn('Storage: unavailable', result.stdout)
        self.assertFalse(list(Path(self.env.get('TMPDIR', '/tmp')).glob('motd.this-test-*')))

    def test_real_pty_geometry_clamps_defaults_and_explicit_flags_win(self):
        path = self.script()
        environment = os.environ.copy()
        environment.update(COLUMNS='200', LINES='60', TERM='xterm')
        for options, expected_width, overrides in [
            ([], 40, {}), (['--width', '80', '--rows', '50'], 80, {}),
            ([], 80, {'PATH': str(self.root / 'no-helpers'), 'COLUMNS': '080', 'LINES': '025'}),
        ]:
            with self.subTest(options=options):
                active_environment = dict(environment, **overrides)
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 25, 40, 0, 0))
                try:
                    result = subprocess.run(['/bin/sh', str(path), '--demo', '--plain', '--ascii', *options],
                                            stdin=slave, stdout=slave, stderr=slave, env=active_environment, timeout=8)
                    os.close(slave); slave = None
                    output = b''
                    while True:
                        try: chunk = os.read(master, 4096)
                        except OSError as error:
                            if error.errno == errno.EIO: break
                            raise
                        if not chunk: break
                        output += chunk
                finally:
                    if slave is not None: os.close(slave)
                    os.close(master)
                lines = output.decode().splitlines()
                self.assertEqual(result.returncode, 0, output)
                self.assertTrue(lines)
                self.assertTrue(all(len(line) == expected_width for line in lines), lines)
                self.assertLessEqual(len(lines), 24 if not options else 49)


if __name__ == '__main__':
    unittest.main()
