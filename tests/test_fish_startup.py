"""Exercise native Fish attachment guards in temporary PTYs.

No real startup file or HOME is changed. The hushlogin path in the generated
block is redirected to a temporary fixture. Optional MOTD_TEST_FISH2/3/4 paths
let the same behavior checks run on actual historical interpreters.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

if os.name == 'posix':
    import pty

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


@unittest.skipUnless(os.name == 'posix', 'Fish startup uses a Unix terminal')
class FishStartupTests(unittest.TestCase):
    def test_native_guards_filter_sessions_and_prevent_duplicate_display(self):
        engines = []
        for key in ('MOTD_TEST_FISH2', 'MOTD_TEST_FISH3', 'MOTD_TEST_FISH4'):
            if os.environ.get(key):
                engines.append((key, os.environ[key]))
        installed = shutil.which('fish')
        if installed and installed not in [path for _, path in engines]:
            engines.append(('fish', installed))
        if not engines:
            self.skipTest('Install Fish or set MOTD_TEST_FISH2/3/4')

        with tempfile.TemporaryDirectory(prefix='motd-fish-startup-') as name:
            folder = Path(name)
            shim_directory = folder / 'bin'
            shim_directory.mkdir()
            xdg = folder / 'xdg'
            xdg.mkdir()
            display = folder / "O'Reilly's % notice.fish"
            display.write_text('echo MOTD-FISH-GUARD-DISPLAY\n', encoding='utf-8')
            startup = folder / 'fixture-config.fish'
            hush = folder / 'fixture-hushlogin'
            # frequency, interactive, login, hush, audience, SSH marker,
            # terminal stdout, expected display count when sourced twice.
            scenarios = [
                ('interactive', False, False, False, 'all', 'none', True, 0),
                ('interactive', True, False, False, 'all', 'none', True, 1),
                ('login', True, False, False, 'all', 'none', True, 0),
                ('login', True, True, False, 'all', 'none', True, 1),
                ('interactive', True, False, True, 'all', 'none', True, 0),
                ('interactive', True, False, False, 'ssh', 'connection', True, 1),
                ('interactive', True, False, False, 'ssh', 'none', True, 0),
                ('interactive', True, False, False, 'local', 'none', True, 1),
                ('interactive', True, False, False, 'local', 'connection', True, 0),
                ('interactive', True, False, False, 'all', 'none', False, 0),
                ('interactive', True, False, False, 'ssh', 'empty-connection', True, 0),
                ('interactive', True, False, False, 'local', 'empty-connection', True, 1),
                ('interactive', True, False, False, 'ssh', 'empty-tty', True, 0),
                ('interactive', True, False, False, 'local', 'empty-tty', True, 1),
            ]
            for label, executable in engines:
                environment = dict(os.environ, TERM='xterm', XDG_CONFIG_HOME=str(xdg),
                                   XDG_DATA_HOME=str(xdg), XDG_CACHE_HOME=str(xdg),
                                   PATH=str(shim_directory) + os.pathsep + os.environ.get('PATH', ''))
                for key in ('SSH_CONNECTION', 'SSH_TTY'):
                    environment.pop(key, None)
                version = subprocess.run([executable, '--version'], capture_output=True,
                                         text=True, env=environment, timeout=8)
                self.assertEqual(version.returncode, 0, version.stderr)
                # --no-config is unavailable in Fish2. Scratch-extracted Fish4
                # packages otherwise search their compiled absolute asset path.
                options = ['--no-config'] if 'version 4.' in version.stdout else []
                shim = shim_directory / 'fish'
                shim.write_text('#!/bin/sh\nexec ' + shlex.quote(executable) + ' ' +
                                ' '.join(options) + ' "$@"\n', encoding='utf-8')
                shim.chmod(0o700)
                for frequency, interactive, login, quiet, audience, ssh, terminal, count in scenarios:
                    with self.subTest(engine=label, frequency=frequency, interactive=interactive,
                                      login=login, hush=quiet, audience=audience, ssh=ssh,
                                      terminal=terminal):
                        config = motd.preset_config('home-lab', shell='fish')
                        config.update(frequency=frequency, audience=audience)
                        block = motd.shell_block(config, str(display))
                        self.assertIn('"$HOME/.hushlogin"', block)
                        block = block.replace('"$HOME/.hushlogin"', motd.fish_literal(str(hush)))
                        startup.write_text(block, encoding='utf-8')
                        if hush.exists():
                            hush.unlink()
                        if quiet:
                            hush.write_text('', encoding='utf-8')
                        run_environment = dict(environment)
                        if ssh == 'connection':
                            run_environment['SSH_CONNECTION'] = '192.0.2.1 22 192.0.2.2 111'
                        elif ssh == 'empty-connection':
                            run_environment['SSH_CONNECTION'] = ''
                        elif ssh == 'empty-tty':
                            run_environment['SSH_TTY'] = ''
                        command = [executable, *options]
                        if interactive:
                            command.append('-i')
                        if login:
                            command.append('-l')
                        source = 'source ' + motd.fish_literal(str(startup))
                        command.extend(['-c', source + '; ' + source])
                        code, output = self.invoke(command, run_environment, terminal)
                        self.assertEqual(code, 0, output)
                        self.assertEqual(output.count('MOTD-FISH-GUARD-DISPLAY'), count, output)

    def invoke(self, command, environment, terminal):
        if not terminal:
            result = subprocess.run(command, capture_output=True, text=True,
                                    env=environment, timeout=8)
            return result.returncode, result.stdout + result.stderr
        master, slave = pty.openpty()
        try:
            result = subprocess.run(command, stdin=slave, stdout=slave, stderr=slave,
                                    env=environment, timeout=8)
            os.close(slave)
            slave = None
            chunks = []
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                chunks.append(chunk)
            return result.returncode, b''.join(chunks).decode(errors='replace')
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)


if __name__ == '__main__':
    unittest.main()
