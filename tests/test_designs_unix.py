"""Execute real generated designs; check geometry, observations and policy.

The shared planner is loaded from its canonical source so this suite can run
before embedding. The separate embed --check gate verifies the distributed
one-file configurator. Historical engines are opt-in, never simulated by
changing a version variable in a modern shell.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd

DESIGNS = ('classic', 'cards', 'ledger', 'briefing', 'dashboard')
SECTIONS = ('system', 'resources', 'services', 'processes', 'sessions',
            'connections', 'attention', 'hints', 'io')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


class UnixDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = patch.multiple(motd, **{
            name + '_TEMPLATE': (ROOT / 'runtime' / filename).read_text(encoding='utf-8')
            for name, filename in (('BASH', 'motd.bash'), ('SH', 'motd.sh'),
                                   ('DESIGNS', 'designs.sh'))})
        cls.templates.start()
        cls.addClassCleanup(cls.templates.stop)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='motd-design-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.environment = dict(os.environ, TERM='xterm-256color', LC_ALL='C.UTF-8')
        self.environment.pop('NO_COLOR', None)

    def config(self, shell='bash', **display):
        config = motd.preset_config('workshop', shell=shell)
        config['display'].update(sections=list(SECTIONS), border_style='single', separator_text='none')
        config['display'].update(display)
        return config

    def artifact(self, config):
        path = self.root / ('view.' + config['shell'])
        path.write_text(motd.generate_artifact(config), encoding='utf-8')
        return path

    def execute(self, shell='bash', *, config=None, width=80, rows=50,
                flags=(), engine=None, demo=True, environment=None):
        if engine is None:
            executable = shutil.which(shell)
            if not executable:
                self.skipTest(f'{shell} is unavailable')
            engine = [executable]
        elif isinstance(engine, str):
            engine = [engine]
        config = config or self.config(shell)
        path = self.artifact(config)
        arguments = ['--demo-alerts'] if demo else []
        result = subprocess.run([*engine, str(path), *arguments,
                                 '--width', str(width), '--rows', str(rows), *flags],
                                capture_output=True, text=True, timeout=15,
                                env=environment or self.environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return result.stdout

    def assert_geometry(self, output, width, rows):
        clean = ANSI.sub('', output)
        lines = clean.splitlines()
        self.assertTrue(lines, 'Renderer produced no output')
        self.assertLessEqual(len(lines), rows - 1, repr(clean))
        self.assertLessEqual(max(map(len, lines)), width, repr(clean))
        self.assertNotRegex(clean, r'[\x00-\x08\x0b-\x1f\x7f]')
        return lines

    def test_every_design_fits_extreme_spacing_and_terminal_budgets(self):
        for shell in ('bash', 'sh'):
            for design in DESIGNS:
                config = self.config(shell, design=design, detail='full',
                                     density='comfortable', padding=3, section_gap=2)
                for width, rows in ((40, 8), (40, 15), (40, 25), (80, 25),
                                    (80, 50), (240, 200)):
                    with self.subTest(shell=shell, design=design, width=width, rows=rows):
                        output = self.execute(shell, config=config, width=width, rows=rows,
                                              flags=('--plain', '--ascii'))
                        lines = self.assert_geometry(output, width, rows)
                        self.assertTrue(output.isascii())
                        if rows == 8:
                            self.assertIn('ATTENTION', output)
                            self.assertIn('Hidden:', output)
                            self.assertTrue('ERROR:' in output or 'WARNING:' in output)
                            for section in set(SECTIONS) - {'attention'}:
                                self.assertRegex(output, r'\b' + section + r'\b')
                        if design in ('classic', 'cards', 'dashboard'):
                            # Full-width single-column frames finish with their
                            # bottom border; omission text may follow the cards.
                            borders = [line for line in lines if line.startswith('+')]
                            self.assertTrue(borders)
                            self.assertTrue(all(line.endswith('+') for line in borders))

    def test_designs_have_distinct_structures_and_dashboard_stacks(self):
        for shell in ('bash', 'sh'):
            outputs = {}
            for design in DESIGNS:
                outputs[design] = self.execute(shell, config=self.config(shell, design=design),
                                               rows=100, flags=('--plain', '--ascii'))
            with self.subTest(shell=shell):
                self.assertEqual(len(set(outputs.values())), len(DESIGNS))
                rule = re.compile(r'^\+-+\+$', re.MULTILINE)
                self.assertTrue(outputs['classic'].splitlines()[-1].startswith('+'))
                self.assertEqual(len(re.findall(r'(?m)^\+[-=]+\+$', outputs['classic'])), 1)
                self.assertEqual(len(rule.findall(outputs['cards'])), len(SECTIONS))
                self.assertNotIn('+---', outputs['ledger'])
                self.assertRegex(outputs['ledger'], r'(?m)^ SYSTEM\s+\|')
                self.assertLess(outputs['briefing'].index('SYSTEM'),
                                outputs['briefing'].index('ATTENTION'))
                paired = [line for line in outputs['dashboard'].splitlines()
                          if re.fullmatch(r'\+-+\+  \+-+\+', line)]
                self.assertEqual(len(paired), len(SECTIONS) // 2)
                self.assertIn('ws-bench-07' if shell == 'bash' else 'demo-host', outputs['dashboard'].splitlines()[1])
                narrow = self.execute(shell, config=self.config(shell, design='dashboard'),
                                      width=40, rows=100, flags=('--plain', '--ascii'))
                self.assertNotRegex(narrow, r'\+  \+')
                self.assertEqual(len(rule.findall(narrow)), len(SECTIONS))

    def test_detail_and_spacing_are_independent_controls(self):
        for shell in ('bash', 'sh'):
            config = self.config(shell, design='cards', detail='brief', density='compact')
            config['display']['sections'] = ['system', 'resources', 'attention']
            compact = self.execute(shell, config=config, rows=100, flags=('--plain', '--ascii'))
            config['display'].update(density='comfortable', padding=3, section_gap=2)
            spacious = self.execute(shell, config=config, rows=100, flags=('--plain', '--ascii'))
            self.assertEqual(len(spacious.splitlines()) - len(compact.splitlines()), 9)
            self.assertEqual(len([line for line in compact.splitlines() if line.startswith('|')]), 3)
            self.assertIn('|   ', spacious)
            config['display'].update(density='compact', padding=1, section_gap=0,
                                     section_detail={'resources': 'full'})
            expanded = self.execute(shell, config=config, rows=100, flags=('--plain', '--ascii'))
            self.assertGreater(len(expanded.splitlines()), len(compact.splitlines()))
            self.assertIn('Total RAM:' if shell == 'sh' else 'Cache', expanded)
            # Only the requested section gains detail; system keeps one row.
            system = expanded.split('+ SYSTEM ', 1)[1].split('+ RESOURCES ', 1)[0]
            self.assertEqual(len([line for line in system.splitlines() if line.startswith('|')]), 1)

    def test_priority_protects_detail_without_reordering_sections(self):
        for shell in ('bash', 'sh'):
            config = self.config(shell, design='cards', detail='full',
                                 section_detail={'attention': 'brief'})
            config['display']['sections'] = ['system', 'resources', 'attention']
            first = self.execute(shell, config=config, rows=16, flags=('--plain', '--ascii'))
            config['display']['priority'] = ['attention', 'system', 'resources']
            second = self.execute(shell, config=config, rows=16, flags=('--plain', '--ascii'))
            with self.subTest(shell=shell):
                self.assertNotEqual(first, second)
                for output in (first, second):
                    self.assertLess(output.index('SYSTEM'), output.index('RESOURCES'))
                    self.assertLess(output.index('RESOURCES'), output.index('ATTENTION'))
                    self.assertNotIn('Hidden:', output)
                detail = 'Total RAM:' if shell == 'sh' else 'Cache'
                self.assertIn(detail, first)
                self.assertLess(len(second.splitlines()), len(first.splitlines()) + 1)
                # The higher-priority System section now has more detail.
                self.assertNotEqual(first, second)

    def test_explicit_priority_can_preserve_hints_before_attention(self):
        # Attention leads the default retention list, but an explicit recipe
        # can choose another first section. This is shared with PowerShell.
        for shell in ('bash', 'sh'):
            for design in DESIGNS:
                config = self.config(shell, design=design, detail='full')
                config['display']['priority'] = ['hints']
                output = self.execute(shell, config=config, width=40, rows=8,
                                      flags=('--plain', '--ascii'))
                with self.subTest(shell=shell, design=design):
                    self.assert_geometry(output, 40, 8)
                    self.assertIn('HINTS', output)
                    self.assertIn('Hidden:', output)
                    self.assertNotIn('ATTENTION', output)
                    self.assertRegex(output, r'\battention\b')

    def test_populated_rows_do_not_duplicate_portable_attention_or_pad_empty_cards(self):
        output = self.execute('sh', config=self.config('sh', design='cards', detail='full'),
                              rows=200, flags=('--plain', '--ascii'))
        self.assertEqual(output.count('DEMO WARNING:'), 1)
        self.assertNotRegex(output, r'(?m)^\| +\|$')

    def test_briefing_retains_first_observations_and_neutral_attention_title(self):
        output = self.execute('bash', config=self.config('bash', design='briefing', detail='full'),
                              rows=200, flags=('--plain', '--ascii'), demo=False)
        self.assertIn('ATTENTION', output)
        self.assertNotIn('Needs attention:', output)
        output = self.execute('bash', config=self.config('bash', design='briefing', detail='full'),
                              rows=200, flags=('--plain', '--ascii'))
        for observation in ('Domain workshop.example', 'SSH', 'RDP', '#c11', '192.0.2.24:51422'):
            self.assertIn(observation, output)
        portable = self.execute('sh', config=self.config('sh', design='briefing', detail='full'),
                                rows=200, flags=('--plain', '--ascii'))
        self.assertIn('sshd: running', portable)
        self.assertIn('demo-kernel', portable)

    def test_headers_retain_machine_context_and_visible_demo_label(self):
        for shell in ('bash', 'sh'):
            for design in DESIGNS:
                config = self.config(shell, design=design, detail='full', density='comfortable')
                # Context must remain useful when the System panel is disabled.
                config['display']['sections'] = ['resources', 'attention']
                config['display']['title'] = 'A' * 100
                for width, rows in ((40, 25), (80, 50)):
                    with self.subTest(shell=shell, design=design, width=width, rows=rows):
                        output = self.execute(shell, config=config, width=width, rows=rows,
                                              flags=('--plain', '--ascii'))
                        self.assert_geometry(output, width, rows)
                        self.assertIn('DEMO', output.splitlines()[0])
                        self.assertIn('ws-bench-07' if shell == 'bash' else 'demo-host', output)
                        self.assertIn('up 4d 06h 12m' if shell == 'bash' else 'up 86400 s', output)

        # Classic also uses the shared renderer and must still
        # identify synthetic output even with Attention and System omitted.
        config = self.config('sh', title='A' * 100)
        config['display']['sections'] = ['resources', 'hints']
        output = self.execute('sh', config=config, width=40, rows=50,
                              flags=('--plain', '--ascii'))
        self.assertIn('DEMO', output.splitlines()[0])

    def test_saved_controls_and_runtime_overrides_use_the_same_layout(self):
        for shell in ('bash', 'sh'):
            for design in DESIGNS:
                saved = self.config(shell, design=design, density='compact', detail='brief',
                                    padding=2, section_gap=1, color_emphasis='quiet')
                expected = self.execute(shell, config=saved, flags=('--plain', '--ascii'))
                actual = self.execute(shell, flags=('--plain', '--ascii', '--design', design,
                                     '--density', 'compact', '--detail', 'brief', '--padding', '2',
                                     '--section-gap', '1', '--color-emphasis', 'quiet'))
                self.assertEqual(expected, actual)

    def test_color_emphasis_charsets_and_no_color(self):
        for shell in ('bash', 'sh'):
            config = self.config(shell, design='cards', color='always', charset='unicode')
            balanced = self.execute(shell, config=config)
            self.assert_geometry(balanced, 80, 50)
            self.assertIn('\x1b[36m┌', balanced)
            self.assertNotIn('\x1b[1;31m0 failed', balanced)
            config['display']['color_emphasis'] = 'vivid'
            vivid = self.execute(shell, config=config)
            self.assertIn('\x1b[1;36m┌', vivid)
            config['display']['color_emphasis'] = 'quiet'
            quiet = self.execute(shell, config=config)
            self.assertNotIn('\x1b[36m┌', quiet)
            self.assertNotIn('\x1b[1;36m┌', quiet)
            plain = self.execute(shell, config=config, flags=('--ascii',),
                                 environment=dict(self.environment, NO_COLOR=''))
            self.assertNotIn('\x1b', plain)
            self.assertTrue(plain.isascii())
            config['display']['theme'] = 'mono'
            mono = self.execute(shell, config=config, flags=('--color',))
            self.assertNotIn('\x1b', mono)

    def test_compact_and_dashboard_summaries_honor_item_visibility(self):
        for design in DESIGNS:
            config = self.config(design=design, detail='brief')
            config['display']['sections'] = ['resources', 'hints']
            output = self.execute(config=config, rows=25,
                                  flags=('--plain', '--ascii', '--hide-item',
                                         'resources.memory,resources.storage,header.title,header.host'))
            with self.subTest(design=design):
                self.assertNotIn('WORKSHOP STATUS', output)
                self.assertNotIn('ws-bench-07', output)
                self.assertNotIn('31.0Gi', output)
                self.assertNotIn('286Gi', output)

    def test_demo_and_invalid_style_options_never_run_hooks(self):
        sentinel = self.root / 'hook-ran'
        for shell in ('bash', 'sh'):
            config = self.config(shell)
            config['hooks']['before'] = [{'argv': ['/bin/sh', '-c',
                ': > ' + shlex.quote(str(sentinel))], 'timeout_seconds': 1, 'on_failure': 'continue'}]
            path = self.artifact(config)
            for design in DESIGNS:
                self.execute(shell, config=config, flags=('--design', design, '--plain'))
                self.assertFalse(sentinel.exists())
            for flags in (('--design', 'invalid'), ('--density', 'very'),
                          ('--detail', '2'), ('--padding', '-1'), ('--section-gap', '3'),
                          ('--color-emphasis', 'invalid')):
                with self.subTest(shell=shell, flags=flags):
                    result = subprocess.run([shell, str(path), *flags], capture_output=True,
                                            text=True, timeout=10, env=self.environment)
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(sentinel.exists())

    def test_real_optional_interpreters_execute_generated_outputs(self):
        engines = []
        for version in (1, 2, 3, 4, 5):
            key = f'MOTD_TEST_BASH{version}'
            if os.environ.get(key): engines.append((key, 'bash', [os.environ[key]]))
        for version in (2, 3, 4, 5):
            key = f'MOTD_TEST_ZSH{version}'
            if os.environ.get(key): engines.append((key, 'zsh', [os.environ[key]]))
        for name in ('dash', 'ksh', 'mksh', 'ash'):
            executable = os.environ.get('MOTD_TEST_' + name.upper()) or shutil.which(name)
            if executable: engines.append((name, 'sh', [executable]))
        busybox = os.environ.get('MOTD_TEST_BUSYBOX') or shutil.which('busybox')
        if busybox: engines.append(('busybox ash', 'sh', [busybox, 'ash']))
        for version in (2, 3, 4):
            key = f'MOTD_TEST_FISH{version}'
            if os.environ.get(key): engines.append((key, 'fish', [os.environ[key]]))
        for name, shell, engine in engines:
            for design in DESIGNS:
                for width, rows in ((40, 8), (80, 50)):
                    with self.subTest(engine=name, design=design, width=width, rows=rows):
                        output = self.execute(shell, engine=engine,
                                              config=self.config(shell, design=design),
                                              width=width, rows=rows, flags=('--plain', '--ascii'))
                        self.assert_geometry(output, width, rows)


if __name__ == '__main__':
    unittest.main()
