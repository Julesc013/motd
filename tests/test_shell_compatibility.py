"""Real shell execution and startup guards; all written files are temporary.

The portable renderer can retain core procfs observations without helpers.
Old Bash versions render through automatic fallback; Zsh deliberately shares
the Unix dispatcher. No real startup file is installed.
"""
from __future__ import annotations

import errno
import fcntl
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import pty
import shlex
import shutil
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


class ShellCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='motd-shell-compat-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = str(self.root / 'state')

    def config(self, shell='sh'):
        config = motd.preset_config('home-lab')
        config['shell'] = shell
        config['name'] = 'compat-test'
        return config

    def artifact(self, config):
        path = self.root / ('dashboard.' + config['shell'])
        path.write_text(motd.generate_artifact(config), encoding='utf-8')
        return path

    def run_shell(self, shell, path, *arguments, no_helpers=False):
        executable = shutil.which(shell)
        if not executable: self.skipTest(f'{shell} is not installed')
        environment = os.environ.copy()
        if no_helpers: environment['PATH'] = str(self.root / 'no-helpers')
        return subprocess.run([executable, str(path), *arguments],
                              capture_output=True, text=True, timeout=8, env=environment)

    def pty_shell(self, shell, command, login=False, interactive=True):
        executable = shutil.which(shell)
        if not executable: self.skipTest(f'{shell} is not installed')
        master, slave = pty.openpty()
        try:
            options = ['-f'] if shell == 'zsh' else []
            if interactive: options.append('-i')
            if login: options.append('-l')
            result = subprocess.run([executable, *options, '-c', command],
                                    stdin=slave, stdout=slave, stderr=slave, timeout=8)
            os.close(slave)
            slave = None
            chunks = []
            while True:
                try: chunk = os.read(master, 4096)
                except OSError as error:
                    if error.errno == errno.EIO: break
                    raise
                if not chunk: break
                chunks.append(chunk)
            return result.returncode, b''.join(chunks).decode(errors='replace')
        finally:
            if slave is not None: os.close(slave)
            os.close(master)

    def test_short_row_budgets_replan_without_cropping_and_keep_attention(self):
        # The wizard reserves ten rows: a 25-row terminal leaves fifteen for
        # the actual renderer. Smaller viewports omit whole sections visibly.
        for shell in ('bash', 'sh', 'zsh'):
            config = motd.preset_config('workshop', shell=shell)
            path = self.artifact(config)
            for width, rows in ((40, 8), (40, 15), (80, 12), (80, 15), (80, 200)):
                with self.subTest(shell=shell, width=width, rows=rows):
                    result = self.run_shell(shell, path, '--demo-alerts', '--plain', '--ascii',
                                            '--width', str(width), '--rows', str(rows))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, '')
                    lines = result.stdout.splitlines()
                    self.assertLessEqual(len(lines), rows - 1)
                    self.assertTrue(lines[-1].startswith('+') and lines[-1].endswith('+'))
                    self.assertLessEqual(max(map(len, lines)), width)
                    self.assertIn('ATTENTION', result.stdout)
                    if rows < 20:
                        self.assertIn('Hidden:', result.stdout)
                        self.assertIn('hints', result.stdout)
                        self.assertTrue('DEMO WARNING:' in result.stdout or 'ERROR:' in result.stdout)
                    else:
                        self.assertNotIn('Hidden:', result.stdout)

    def test_saved_charset_and_color_preferences_and_cli_overrides(self):
        for shell in ('bash', 'sh', 'zsh'):
            config = motd.preset_config('workshop', shell=shell)
            config['display'].update(charset='ascii', color='never')
            path = self.artifact(config)
            environment = dict(os.environ, TERM='xterm-256color', LC_ALL='C.UTF-8')
            environment.pop('NO_COLOR', None)
            for flags, color, unicode in (([], False, False),
                                         (['--color', '--unicode'], True, True),
                                         (['--plain', '--color', '--unicode'], False, True)):
                with self.subTest(shell=shell, flags=flags):
                    result = subprocess.run([shell, str(path), '--demo', *flags],
                                            env=environment, capture_output=True, text=True, timeout=8)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual('\x1b[' in result.stdout, color)
                    self.assertEqual(not result.stdout.isascii(), unicode)
            config['display'].update(charset='unicode', color='always')
            path = self.artifact(config)
            result = subprocess.run([shell, str(path), '--demo'], env=environment,
                                    capture_output=True, text=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('\x1b[', result.stdout)
            self.assertFalse(result.stdout.isascii())
            result = subprocess.run([shell, str(path), '--demo', '--ascii'],
                                    env=dict(environment, NO_COLOR=''), capture_output=True,
                                    text=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('\x1b[', result.stdout)
            self.assertTrue(result.stdout.isascii())

    def test_old_recipe_still_defaults_to_bash(self):
        config = motd.preset_config('home-lab')
        config.pop('shell', None)
        self.assertEqual(motd.validate_config(config)['shell'], 'bash')
        self.assertTrue(motd.generate_artifact(config).startswith('#!/usr/bin/env bash\n'))

    def test_cli_does_not_relabel_an_existing_generated_interpreter(self):
        source = self.artifact(self.config('zsh'))
        destination = self.root / 'relabeled.sh'
        with self.assertRaises(motd.MotdError):
            motd.main(['build', '--artifact', str(source), '--shell', 'sh',
                       '--output', str(destination), '--state-dir', self.state])
        self.assertFalse(destination.exists())
        self.assertFalse(Path(self.state).exists())

    def test_cli_can_rebuild_a_recipe_for_another_interpreter(self):
        config = self.config('bash')
        config['display']['title'] = 'PRESERVED RECIPE SETTINGS'
        recipe = self.root / 'recipe.toml'
        recipe.write_text(motd.dump_config(config), encoding='utf-8')
        destination = self.root / 'rebuilt.sh'
        with redirect_stdout(io.StringIO()):
            status = motd.main(['build', '--config', str(recipe), '--shell', 'sh',
                                '--output', str(destination), '--state-dir', self.state])
        self.assertEqual(status, 0)
        recovered = motd.extract_config(destination.read_text())
        self.assertEqual(recovered['shell'], 'sh')
        self.assertEqual(recovered['display']['title'], config['display']['title'])
        self.assertEqual(motd.load_config(recipe)['shell'], 'bash')
        result = self.run_shell('dash', destination, '--demo', '--plain')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(config['display']['title'], result.stdout)

    def test_bash_missing_timeout_uses_the_explicit_partial_fallback(self):
        # The runtime intentionally fixes PATH. A Bash command-lookup fixture
        # models an absent timeout without altering any host binaries or files.
        startup = self.root / 'missing-timeout.bash'
        startup.write_text(
            'command() {\n'
            '  if [[ ${1-} == -v && ${2-} == timeout ]]; then return 1; fi\n'
            '  builtin command "$@"\n'
            '}\n', encoding='utf-8')
        environment = os.environ.copy()
        environment['BASH_ENV'] = str(startup)
        path = self.artifact(self.config('bash'))
        result = subprocess.run(['bash', str(path), '--plain'],
                                capture_output=True, text=True, timeout=5, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Full display unavailable', result.stdout)
        self.assertNotIn('command not found', result.stderr)

    @unittest.skipUnless(os.environ.get('MOTD_TEST_BASH32'),
                         'Set MOTD_TEST_BASH32 to an actual Bash 3.2 binary for the historical boundary test')
    def test_bash32_automatically_renders_with_portable_backend(self):
        interpreter = os.environ['MOTD_TEST_BASH32']
        version = subprocess.run([interpreter, '--version'], capture_output=True,
                                 text=True, timeout=5)
        self.assertIn('version 3.2.', version.stdout)
        sentinel = self.root / 'old-interpreter-hook'
        for shell in ('bash', 'zsh'):
            with self.subTest(shell=shell):
                config = self.config(shell)
                config['hooks']['before'] = [{
                    'argv': ['/bin/sh', '-c', ': > ' + shlex.quote(str(sentinel))],
                    'timeout_seconds': 1, 'on_failure': 'continue'}]
                path = self.artifact(config)
                result = subprocess.run([interpreter, str(path), '--demo', '--plain'],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Portable Unix', result.stdout)
                self.assertIn('demo-host', result.stdout)
                self.assertNotIn('Bash 4.3 or newer', result.stderr)
                self.assertFalse(sentinel.exists(), 'A demo reached executable hooks')
        portable = self.artifact(self.config('sh'))
        result = subprocess.run([interpreter, str(portable), '--demo', '--plain'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('demo-host', result.stdout)
        self.assertIn('Portable Unix', result.stdout)

    def test_optional_historical_bash_binaries_render_instead_of_rejecting(self):
        found = False
        for variable, prefix in [('MOTD_TEST_BASH1', '1.'), ('MOTD_TEST_BASH2', '2.'),
                                  ('MOTD_TEST_BASH32', '3.2.'), ('MOTD_TEST_BASH43', '4.3.')]:
            interpreter = os.environ.get(variable)
            if not interpreter:
                continue
            found = True
            version = subprocess.run([interpreter, '-c', 'echo "$BASH_VERSION"'],
                                     capture_output=True, text=True, timeout=5)
            self.assertTrue(version.stdout.startswith(prefix), version.stdout)
            with self.subTest(interpreter=version.stdout.strip()):
                config = motd.preset_config('workshop')
                for shell in ('bash', 'sh'):
                    config['shell'] = shell
                    path = self.artifact(config)
                    result = subprocess.run([interpreter, str(path), '--demo', '--plain',
                                             '--ascii', '--width', '40', '--rows', '25'],
                                            capture_output=True, text=True, timeout=8)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('SYSTEM', result.stdout)
                    self.assertLessEqual(len(result.stdout.splitlines()), 24)
                    self.assertTrue(all(len(line) <= 40 for line in result.stdout.splitlines()))
                    if prefix in ('1.', '2.', '3.2.') or shell == 'sh':
                        self.assertIn('Portable Unix', result.stdout)
                        for section in ('SERVICES', 'PROCESSES', 'SESSIONS', 'CONNECTIONS', 'HINTS'):
                            self.assertIn(section, result.stdout)
        if not found:
            self.skipTest('Set MOTD_TEST_BASH1/2/32/43 to real historical Bash executables')

    def test_optional_historical_zsh_launchers_and_no_bash_fallback(self):
        found = False
        config = motd.preset_config('workshop', shell='zsh')
        path = self.artifact(config)
        fallback = self.root / 'no-bash.zsh'
        # Model an absent /bin/bash in a temporary copy, never the host paths.
        fallback.write_text(path.read_text().replace('[ -x /bin/bash ]',
                                                     '[ -x /nonexistent-motd-test/bash ]', 1))
        for variable, prefix in [('MOTD_TEST_ZSH2', '2.'), ('MOTD_TEST_ZSH3', '3.'),
                                  ('MOTD_TEST_ZSH4', '4.')]:
            interpreter = os.environ.get(variable)
            if not interpreter:
                continue
            found = True
            version = subprocess.run([interpreter, '-c', 'echo "${ZSH_VERSION:-$VERSION}"'],
                                     capture_output=True, text=True, timeout=5)
            display_version = version.stdout[5:] if version.stdout.startswith('zsh v') else version.stdout
            self.assertTrue(display_version.startswith(prefix), version.stdout)
            for candidate in (path, fallback):
                with self.subTest(interpreter=version.stdout.strip(), fallback=candidate == fallback):
                    result = subprocess.run([interpreter, str(candidate), '--demo', '--plain',
                                             '--ascii', '--width', '40', '--rows', '25'],
                                            capture_output=True, text=True, timeout=8)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('SYSTEM', result.stdout)
                    self.assertLessEqual(len(result.stdout.splitlines()), 24)
                    self.assertTrue(all(len(line) <= 40 for line in result.stdout.splitlines()))
                    if candidate == fallback:
                        self.assertIn('Portable Unix', result.stdout)
                        self.assertIn('demo-host', result.stdout)
        if not found:
            self.skipTest('Set MOTD_TEST_ZSH2/3/4 to actual historical Zsh executables')

    def test_optional_historical_startup_guards_on_a_real_pty(self):
        """Check the actual old shell, not a modern shell with a fake version.

        The attachment runs a temporary marker script; no real profile is
        written. Bash 1's login convention is exercised with leading '-' argv0.
        """
        found = False
        display = self.root / "old shell's display"
        display.write_text("#!/bin/sh\nprintf '%s\\n' HISTORICAL-DISPLAY\n")

        def invoke(interpreter, kind, startup, interactive, login, first_family):
            master, slave = pty.openpty()
            arguments = ['-' + kind if login and first_family else kind]
            if kind == 'zsh': arguments.append('-f')
            if interactive: arguments.append('-i')
            if login and not first_family: arguments.append('-l')
            command = '. ' + shlex.quote(str(startup)) + '; . ' + shlex.quote(str(startup))
            if not interactive:
                arguments += ['-c', command]
            environment = os.environ.copy()
            environment.update(HOME=str(self.root), TERM='xterm')

            def controlling_terminal():
                os.setsid()
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)

            try:
                process = subprocess.Popen(arguments, executable=interpreter, stdin=slave,
                                           stdout=slave, stderr=slave, env=environment,
                                           preexec_fn=controlling_terminal)
                try:
                    if interactive:
                        # Zsh 2's -c explicitly clears its interactive flag even
                        # with -i, so feed a genuine interactive terminal.
                        os.write(master, (command + '; exit\n').encode())
                    status = process.wait(timeout=8)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=3)
                os.close(slave); slave = None
                chunks = []
                while True:
                    try: chunk = os.read(master, 4096)
                    except OSError as error:
                        if error.errno == errno.EIO: break
                        raise
                    if not chunk: break
                    chunks.append(chunk)
                return status, b''.join(chunks).decode(errors='replace')
            finally:
                if slave is not None: os.close(slave)
                os.close(master)

        for variable, kind, first_family in [('MOTD_TEST_BASH1', 'bash', True),
                                             ('MOTD_TEST_BASH2', 'bash', False),
                                             ('MOTD_TEST_ZSH2', 'zsh', False)]:
            interpreter = os.environ.get(variable)
            if not interpreter: continue
            found = True
            interpreter = str(Path(interpreter).resolve())
            config = self.config(kind)
            startup = self.root / (variable + '.profile')
            for frequency, interactive, login, hush, count in [
                ('interactive', False, False, False, 0),
                ('interactive', True, False, False, 1),
                ('interactive', True, False, True, 0),
                ('login', True, False, False, 0),
                ('login', True, True, False, 1),
                ('login', True, True, True, 0),
            ]:
                with self.subTest(shell=variable, frequency=frequency, interactive=interactive,
                                  login=login, hush=hush):
                    config['frequency'] = frequency
                    startup.write_text(motd.shell_block(config, str(display)))
                    hushfile = self.root / '.hushlogin'
                    if hush: hushfile.touch()
                    elif hushfile.exists(): hushfile.unlink()
                    status, output = invoke(interpreter, kind, startup, interactive, login, first_family)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(output.count('HISTORICAL-DISPLAY'), count, output)
        if not found:
            self.skipTest('Set MOTD_TEST_BASH1/2 or MOTD_TEST_ZSH2 for real historical startup tests')

    def test_sh_is_recoverable_and_runs_under_dash_without_helpers(self):
        config = self.config()
        sentinel = self.root / 'must-not-exist'
        config['display']['title'] = f'Literal $(touch {sentinel})'
        config['messages'] = ["quotes ' \" and `touch " + str(sentinel) + '`']
        path = self.artifact(config)
        recovered = motd.extract_config(path.read_text())
        self.assertEqual(recovered, motd.validate_config(config))
        syntax = subprocess.run(['dash', '-n', str(path)], capture_output=True, text=True, timeout=5)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        result = self.run_shell('dash', path, '--demo', '--plain', no_helpers=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('demo-host', result.stdout)
        self.assertIn('12582912 KiB', result.stdout)
        self.assertIn('Services: 8 running; 0 failed', result.stdout)
        self.assertFalse(sentinel.exists(), 'Displayed text executed as shell code')
        self.assertNotIn('\x1b', result.stdout)

    def test_sh_live_mode_has_no_external_collector_dependency(self):
        path = self.artifact(self.config())
        result = self.run_shell('dash', path, '--plain', no_helpers=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Host:', result.stdout)
        self.assertIn('Memory', result.stdout)
        self.assertNotIn('demo-host', result.stdout)
        self.assertNotIn('command not found', result.stderr)

    def test_sh_captured_preview_color_respects_theme_and_plain_preferences(self):
        config = self.config()
        environment = os.environ.copy()
        environment['TERM'] = 'xterm-256color'
        environment.pop('NO_COLOR', None)
        for theme, code in (('cyan', '36'), ('green', '32'), ('amber', '33'), ('mono', None)):
            with self.subTest(theme=theme):
                config['display']['theme'] = theme
                path = self.artifact(config)
                for options, no_color in ((['--color'], False), ([], False),
                                          (['--color', '--plain'], False),
                                          (['--plain', '--color'], False),
                                          (['--color'], True)):
                    with self.subTest(options=options, no_color=no_color):
                        active_environment = environment.copy()
                        if no_color: active_environment['NO_COLOR'] = ''
                        result = subprocess.run(['dash', str(path), '--demo', *options],
                                                capture_output=True, text=True, timeout=5,
                                                env=active_environment)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('HOME LAB', result.stdout)
                        if code and options == ['--color'] and not no_color:
                            self.assertIn('\x1b[1;' + code + 'm', result.stdout)
                            self.assertIn('\x1b[0m', result.stdout)
                        else:
                            self.assertNotIn('\x1b', result.stdout)

    def test_sh_hooks_run_once_and_preview_options_suppress_them(self):
        config = self.config()
        trace = self.root / "hook trace's.txt"
        for phase in ('before', 'after'):
            command = 'printf "%s\\n" ' + shlex.quote(phase) + ' >> ' + shlex.quote(str(trace))
            config['hooks'][phase] = [{'argv': ['/bin/sh', '-c', command],
                                       'timeout_seconds': 1, 'on_failure': 'stop'}]
        path = self.artifact(config)
        for options in (('--demo',), ('--demo-alerts',), ('--no-hooks',), ('--help',)):
            result = self.run_shell('dash', path, *options)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(trace.exists(), f'Hook ran for {options}')
        result = self.run_shell('dash', path, '--plain')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(trace.read_text().splitlines(), ['before', 'after'])

    def test_sh_missing_timeout_does_not_execute_the_hook(self):
        config = self.config()
        sentinel = self.root / 'hook-was-run'
        config['hooks']['before'] = [{'argv': ['/bin/sh', '-c', ': > ' + shlex.quote(str(sentinel))],
                                      'timeout_seconds': 0.1, 'on_failure': 'continue'}]
        result = self.run_shell('dash', self.artifact(config), '--plain', no_helpers=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('hook 1 failed (127)', result.stderr)
        self.assertFalse(sentinel.exists())
        self.assertIn('HOME LAB', result.stdout)
        self.assertIn('Storage: unavailable', result.stdout)

    def test_sh_hook_deadline_keeps_partial_output_and_stops_when_requested(self):
        config = self.config()
        config['hooks']['before'] = [{'argv': ['/bin/sh', '-c', 'printf partial; sleep 5'],
                                      'timeout_seconds': 0.05, 'on_failure': 'stop'}]
        started = time.monotonic()
        result = self.run_shell('dash', self.artifact(config), '--plain')
        self.assertLess(time.monotonic() - started, 3)
        self.assertIn(result.returncode, (124, 137))
        self.assertEqual(result.stdout, 'partial')
        self.assertIn('hook 1 failed', result.stderr)

    def test_sh_rejects_invalid_width_before_hooks_or_arithmetic(self):
        config = self.config()
        path = self.artifact(config)
        for value in ('$(id)', '-1', '999999999999999999999999', '12', '241'):
            with self.subTest(value=value):
                result = self.run_shell('dash', path, '--width', value)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')

    @unittest.skipUnless(shutil.which('zsh'), 'Zsh is not installed')
    def test_zsh_launcher_matches_the_shared_bash_demo(self):
        bash_config = self.config('bash')
        zsh_config = self.config('zsh')
        bash = self.artifact(bash_config)
        zsh = self.artifact(zsh_config)
        expected = self.run_shell('bash', bash, '--demo', '--plain', '--ascii')
        actual = self.run_shell('zsh', zsh, '--demo', '--plain', '--ascii')
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(actual.stdout, expected.stdout)
        self.assertEqual(motd.extract_config(zsh.read_text())['shell'], 'zsh')

    @unittest.skipUnless(shutil.which('zsh'), 'Zsh is not installed')
    def test_zsh_before_and_after_hooks_are_not_repeated_by_bash_workers(self):
        config = self.config('zsh')
        trace = self.root / 'zsh-hook-trace'
        for phase in ('before', 'after'):
            config['hooks'][phase] = [{
                'argv': ['/bin/sh', '-c', 'printf "%s\\n" ' + shlex.quote(phase)
                         + ' >> ' + shlex.quote(str(trace))],
                'timeout_seconds': 1, 'on_failure': 'stop'}]
        path = self.artifact(config)
        result = self.run_shell('zsh', path, '--demo', '--plain')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(trace.exists())
        result = self.run_shell('zsh', path, '--plain')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(trace.read_text().splitlines(), ['before', 'after'])

    def test_zsh_launcher_does_not_reexec_forever_for_inherited_version_text(self):
        path = self.artifact(self.config('zsh'))
        environment = os.environ.copy()
        environment['ZSH_VERSION'] = 'inherited-environment-text'
        result = subprocess.run(['bash', str(path), '--demo', '--plain'],
                                capture_output=True, text=True, timeout=3, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('HOME LAB', result.stdout)

    def test_startup_guards_require_interactivity_and_run_once(self):
        for shell in ('sh', 'zsh'):
            if not shutil.which(shell): continue
            with self.subTest(shell=shell):
                config = self.config(shell)
                config['frequency'] = 'interactive'
                script = self.root / f"quoted {shell}'s output"
                script.write_text("#!/bin/sh\nprintf '%s\\n' COMPAT-DISPLAY\n")
                startup = self.root / f'{shell}rc'
                startup.write_text(motd.shell_block(config, str(script)))
                command = '. ' + shlex.quote(str(startup)) + '; . ' + shlex.quote(str(startup))
                code, text = self.pty_shell(shell, command, interactive=False)
                self.assertEqual(code, 0, text)
                self.assertNotIn('COMPAT-DISPLAY', text)
                code, text = self.pty_shell(shell, command)
                self.assertEqual(code, 0, text)
                self.assertEqual(text.count('COMPAT-DISPLAY'), 1, text)

    @unittest.skipUnless(shutil.which('zsh'), 'Zsh is not installed')
    def test_zsh_login_frequency_does_not_run_in_nonlogin_interactive_shell(self):
        config = self.config('zsh')
        script = self.root / 'zsh-output'
        script.write_text("#!/bin/sh\nprintf '%s\\n' LOGIN-ONLY-DISPLAY\n")
        startup = self.root / 'zshrc'
        startup.write_text(motd.shell_block(config, str(script)))
        command = '. ' + shlex.quote(str(startup))
        code, text = self.pty_shell('zsh', command)
        self.assertEqual(code, 0, text)
        self.assertNotIn('LOGIN-ONLY-DISPLAY', text)
        code, text = self.pty_shell('zsh', command, login=True)
        self.assertEqual(code, 0, text)
        self.assertEqual(text.count('LOGIN-ONLY-DISPLAY'), 1, text)

    def test_zsh_default_startup_files_respect_zdotdir(self):
        directory = self.root / 'zsh-settings'
        directory.mkdir()
        config = self.config('zsh')
        with patch.object(Path, 'home', return_value=self.root), patch.dict(os.environ, {'ZDOTDIR': str(directory)}):
            plan = motd.installation_plan(config, motd.generate_artifact(config), state_dir=self.state)
        self.assertEqual(set(plan['metadata']['hook_paths']),
                         {str(directory / '.zshrc'), str(directory / '.zprofile')})
        self.assertFalse(Path(self.state).exists())
        self.assertFalse((directory / '.zshrc').exists())

    def test_zsh_refuses_empty_or_relative_zdotdir(self):
        config = self.config('zsh')
        for value in ('', 'relative-directory'):
            with self.subTest(value=value), patch.dict(os.environ, {'ZDOTDIR': value}), self.assertRaises(motd.MotdError):
                motd.installation_plan(config, motd.generate_artifact(config), state_dir=self.state)

    def test_sh_interactive_frequency_requires_explicit_startup_location(self):
        config = self.config()
        config['frequency'] = 'interactive'
        with patch.object(Path, 'home', return_value=self.root), self.assertRaises(motd.MotdError):
            motd.installation_plan(config, motd.generate_artifact(config), state_dir=self.state)

    def test_sh_and_zsh_installation_restore_explicit_startup_files(self):
        for shell in ('sh', 'zsh'):
            with self.subTest(shell=shell):
                config = self.config(shell)
                config['name'] = 'lifecycle-' + shell
                startup = self.root / (shell + 'rc')
                original = '# Existing local configuration\n'
                startup.write_text(original)
                destination = self.root / ('installed.' + shell)
                plan = motd.installation_plan(config, motd.generate_artifact(config),
                                              destination=str(destination), shell_file=str(startup),
                                              state_dir=self.state)
                motd.tx_apply(plan)
                self.assertTrue(destination.exists())
                self.assertIn('# >>> motd', startup.read_text())
                motd.tx_apply(motd.uninstall_plan(config['name'], self.state))
                self.assertFalse(destination.exists())
                self.assertEqual(startup.read_text(), original)


if __name__ == '__main__':
    unittest.main()
