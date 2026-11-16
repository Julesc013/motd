"""Bounded integration checks of generated Bash, hooks and adaptive rendering.

The JSON record describes this local test environment only. It is not evidence
of a real Debian login, functioning systemd/logind or positive storage I/O attribution.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd

ANSI_SGR = re.compile(r'\x1b\[[0-9;]*m')


@unittest.skipUnless(shutil.which('bash'), 'Bash is required for runtime validation')
class RuntimeTests(unittest.TestCase):
    records = []
    test_results = []

    @classmethod
    def setUpClass(cls):
        cls.records = []
        cls.test_results = []
        cls.started_at = datetime.now(timezone.utc).isoformat()
        cls.configurator_sha256 = hashlib.sha256(Path(motd.__file__).read_bytes()).hexdigest()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='motd-runtime-')
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'generated.bash'
        self._previous_failures = len(self._outcome.result.failures) + len(self._outcome.result.errors)

    def tearDown(self):
        failed = len(self._outcome.result.failures) + len(self._outcome.result.errors) > self._previous_failures
        self.test_results.append({'test': self._testMethodName, 'status': 'failed' if failed else 'passed'})

    @classmethod
    def tearDownClass(cls):
        # Development reruns can defer replacing the audit record until a freeze.
        if os.environ.get('MOTD_TEST_WRITE_RECORD', '1') != '1':
            return
        result = subprocess.run(['bash', '--version'], capture_output=True, text=True, timeout=3)
        record = {
            'schema_version': 1,
            'started_at_utc': cls.started_at,
            'completed_at_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'Synthetic demos, local execution smoke checks and controlled killable faults only.',
            'not_validated': ['real Debian SSH/PAM/agetty integration', 'usable systemd/logind providers',
                              'positive storage I/O attribution', 'reference-host latency',
                              'hard elapsed-time guarantee under uninterruptible waits/backpressure'],
            'python_version': sys.version.split()[0],
            'bash_version': result.stdout.splitlines()[0] if result.stdout else 'unknown',
            'configurator_sha256': cls.configurator_sha256,
            'configurator_unchanged_during_suite': cls.configurator_sha256 ==
                hashlib.sha256(Path(motd.__file__).read_bytes()).hexdigest(),
            'template_sha256': hashlib.sha256(motd.BASH_TEMPLATE.encode()).hexdigest(),
            'template_matches_runtime_file': motd.BASH_TEMPLATE == (ROOT / 'runtime' / 'motd.bash').read_text(),
            'summary': {'tests_run': len(cls.test_results),
                        'passed': sum(t['status'] == 'passed' for t in cls.test_results),
                        'failed': sum(t['status'] == 'failed' for t in cls.test_results),
                        'observations': len(cls.records)},
            'tests': cls.test_results,
            'observations': cls.records,
            'timing_note': 'Elapsed samples are smoke-test observations, not a performance benchmark.',
        }
        destination = ROOT / 'build' / 'verification-runtime.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')

    def run_artifact(self, config, *args, label=None, timeout=5):
        self.path.write_text(motd.generate_artifact(config), encoding='utf-8')
        start = time.monotonic()
        result = subprocess.run(['bash', str(self.path), *args], capture_output=True,
                                text=True, timeout=timeout,
                                env={**os.environ, 'LC_ALL': 'C.UTF-8', 'TERM': 'xterm-256color'})
        self.records.append({'case': label or self._testMethodName,
                             'arguments': list(args), 'returncode': result.returncode,
                             'elapsed_ms': round((time.monotonic() - start) * 1000, 3),
                             'output_rows': len(result.stdout.splitlines()),
                             'partial_fallback': 'Full display unavailable' in result.stdout})
        return result

    @staticmethod
    def hook(text, timeout=1, failure='continue'):
        return {'argv': ['/usr/bin/printf', r'%s\n', text],
                'timeout_seconds': timeout, 'on_failure': failure}

    def with_hooks(self):
        config = motd.preset_config()
        config['hooks'] = {'before': [self.hook('BEFORE_ONE'), self.hook('BEFORE_TWO')],
                           'after': [self.hook('AFTER_ONE'), self.hook('AFTER_TWO')]}
        return config

    def assert_hook_order_once(self, output):
        tokens = ('BEFORE_ONE', 'BEFORE_TWO', 'AFTER_ONE', 'AFTER_TWO')
        for token in tokens:
            self.assertEqual(output.count(token), 1, token)
        positions = [output.index(t) for t in tokens]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(output.index('BEFORE_TWO'), output.index('RESOURCES'))
        self.assertLess(output.index('RESOURCES'), output.index('AFTER_ONE'))

    def test_adaptive_geometry_preserves_sections_and_rankings(self):
        for width, rows in ((40, 25), (80, 25), (100, 32), (132, 50)):
            for flag in ('--demo', '--demo-alerts'):
                with self.subTest(width=width, rows=rows, demo=flag):
                    config = motd.preset_config()
                    result = self.run_artifact(config, flag, '--width', str(width), '--rows', str(rows),
                                               label=f'geometry-{width}x{rows}-{flag}')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    lines = [ANSI_SGR.sub('', line) for line in result.stdout.splitlines()]
                    self.assertLessEqual(len(lines), rows - 1)
                    self.assertLessEqual(max(map(len, lines)), width)
                    for section in ('RESOURCES', 'SERVICES', 'SESSIONS', 'ATTENTION'):
                        self.assertIn(section, result.stdout)
                    if width >= 80:
                        for label in ('CPU avg', 'RAM RSS', 'I/O'):
                            self.assertIn(label, result.stdout)
                    self.assertNotIn('__WORKSHOP_COMPLETE_V2__', result.stdout)

    def test_home_lab_and_plain_ascii(self):
        result = self.run_artifact(motd.preset_config('home-lab'), '--demo', '--plain', '--ascii',
                                   '--width', '80', '--rows', '25')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('HOME LAB', result.stdout)
        self.assertNotIn('\x1b', result.stdout)
        self.assertTrue(result.stdout.isascii())

    def test_terminal_size_handoff_and_configured_width_cap(self):
        config = motd.preset_config()
        config['display']['width'] = 80
        # Deterministic supervisor-to-worker size handoff, not a real TTY test.
        result = self.run_artifact(config, '--demo', '--plain', '--_tty-size', '20 40')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout.splitlines()), 19)
        self.assertLessEqual(max(map(len, result.stdout.splitlines())), 40)
        for label in ('CPU avg', 'RAM RSS', 'I/O'):
            self.assertIn(label, result.stdout)
        result = self.run_artifact(config, '--demo', '--plain', '--width', '132', '--rows', '25')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(max(map(len, result.stdout.splitlines())), 80)
        self.assertLessEqual(len(result.stdout.splitlines()), 24)

    def test_runtime_rejects_non_numeric_options_and_removed_modes(self):
        sentinel = Path(self.directory.name) / 'argument-injection'
        cases = [('--width', '1+1'), ('--rows', f'$(touch {sentinel})'),
                 ('--top', '0'), ('--verbose',), ('--concise',)]
        for args in cases:
            with self.subTest(arguments=args):
                result = self.run_artifact(motd.preset_config(), '--demo', *args)
                self.assertEqual(result.returncode, 2)
        self.assertFalse(sentinel.exists())

    def test_visibility_and_custom_order(self):
        config = motd.preset_config()
        config['display']['sections'] = ['system', 'processes', 'sessions', 'attention']
        result = self.run_artifact(config, '--demo', '--plain', '--width', '80')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('RESOURCES', result.stdout)
        self.assertNotIn('CONNECTIONS', result.stdout)
        positions = [result.stdout.index(s) for s in ('SYSTEM', 'TOP PROCESSES', 'SESSIONS', 'ATTENTION')]
        self.assertEqual(positions, sorted(positions))

    def test_hooks_skip_demos_and_informational_commands(self):
        for flag in ('--demo', '--demo-alerts', '--help', '--version', '--list-sections'):
            with self.subTest(flag=flag):
                result = self.run_artifact(self.with_hooks(), flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                for marker in ('BEFORE_ONE', 'BEFORE_TWO', 'AFTER_ONE', 'AFTER_TWO'):
                    self.assertNotIn(marker, result.stdout)

    def test_cli_recipe_and_known_artifact_previews_skip_hooks(self):
        config = self.with_hooks()
        recipe = Path(self.directory.name) / 'recipe.toml'
        recipe.write_text(motd.dump_config(config), encoding='utf-8')
        self.path.write_text(motd.generate_artifact(config), encoding='utf-8')
        for source, path in (('--config', recipe), ('--artifact', self.path)):
            for live in (False, True):
                with self.subTest(source=source, live=live):
                    args = ['preview', source, str(path)] + (['--live'] if live else [])
                    start = time.monotonic()
                    result = subprocess.run([sys.executable, str(ROOT / 'motd.py'), *args],
                                            capture_output=True, text=True, timeout=5)
                    self.records.append({'case': 'cli-preview-hooks-skipped',
                                         'source': source, 'live': live,
                                         'returncode': result.returncode,
                                         'elapsed_ms': round((time.monotonic() - start) * 1000, 3),
                                         'output_rows': len(result.stdout.splitlines())})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('RESOURCES', result.stdout)
                    for marker in ('BEFORE_ONE', 'BEFORE_TWO', 'AFTER_ONE', 'AFTER_TWO'):
                        self.assertNotIn(marker, result.stdout)

    def test_worker_reentry_skips_hooks(self):
        result = self.run_artifact(self.with_hooks(), '--_worker', '--plain', '--width', '80')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('__WORKSHOP_COMPLETE_V2__', result.stdout)
        for marker in ('BEFORE_ONE', 'BEFORE_TWO', 'AFTER_ONE', 'AFTER_TWO'):
            self.assertNotIn(marker, result.stdout)

    def test_live_hooks_run_once_around_supervised_display(self):
        result = self.run_artifact(self.with_hooks(), '--plain', '--width', '80')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_hook_order_once(result.stdout)
        self.assertNotIn('__WORKSHOP_COMPLETE_V2__', result.stdout)

    def test_no_hooks_flag_skips_all_calls(self):
        result = self.run_artifact(self.with_hooks(), '--no-hooks', '--plain', '--width', '80')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('BEFORE_ONE', result.stdout)
        self.assertNotIn('AFTER_ONE', result.stdout)

    @unittest.skipUnless(shutil.which('timeout'), 'GNU timeout is required for fault tests')
    def test_timed_out_hook_keeps_partial_output_and_runs_after_once(self):
        config = motd.preset_config()
        config['hooks'] = {
            'before': [{'argv': ['/bin/sh', '-c', 'printf PARTIAL_HOOK; sleep 2'],
                        'timeout_seconds': 0.05, 'on_failure': 'continue'}],
            'after': [self.hook('AFTER_TIMEOUT')],
        }
        result = self.run_artifact(config, '--plain', '--width', '80')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('PARTIAL_HOOK'), 1)
        self.assertEqual(result.stdout.count('AFTER_TIMEOUT'), 1)
        self.assertIn('before hook 1 failed', result.stderr)

    @unittest.skipUnless(shutil.which('timeout'), 'GNU timeout is required for fault tests')
    def test_display_timeout_runs_outer_hooks_once(self):
        original = motd.BASH_TEMPLATE
        delayed = original.replace('collect_all() {\n',
            'collect_all() {\n    if (( ${WORKSHOP_BUDGET_FALLBACK:-0} == 0 )); then sleep 2; fi\n', 1)
        self.assertNotEqual(delayed, original)
        config = self.with_hooks()
        config['collection'].update(budget_ms=40, worker_ms=80)
        with mock.patch.object(motd, 'BASH_TEMPLATE', delayed):
            result = self.run_artifact(config, '--plain', '--width', '132', '--rows', '50',
                                       label='controlled-killable-display-timeout')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Full display unavailable', result.stdout)
        self.assert_hook_order_once(result.stdout)
        self.assertNotIn('__WORKSHOP_COMPLETE_V2__', result.stdout)

    def test_hook_stop_policy_preserves_exit_code(self):
        config = self.with_hooks()
        config['hooks']['before'] = [{'argv': ['/bin/sh', '-c', 'exit 7'],
                                     'timeout_seconds': 1, 'on_failure': 'stop'}]
        result = self.run_artifact(config, '--plain')
        self.assertEqual(result.returncode, 7)
        self.assertNotIn('AFTER_ONE', result.stdout)
        self.assertNotIn('RESOURCES', result.stdout)

    def test_hook_argv_does_not_implicitly_execute_shell_text(self):
        sentinel = Path(self.directory.name) / 'hook-injection'
        literal = f'$(touch {sentinel})'
        config = motd.preset_config()
        config['hooks']['before'] = [self.hook(literal)]
        result = self.run_artifact(config, '--plain', '--width', '80')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(literal, result.stdout)
        self.assertFalse(sentinel.exists())

    def test_help_has_one_layout_and_no_old_mode_options(self):
        result = self.run_artifact(motd.preset_config(), '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--rows', result.stdout)
        self.assertIn('--width', result.stdout)
        self.assertNotIn('--verbose', result.stdout)
        self.assertNotIn('--concise', result.stdout)


if __name__ == '__main__':
    unittest.main()
