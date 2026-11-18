"""Regressions found while reviewing the portable runtime and new designs."""
import os
from pathlib import Path
import re
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


@unittest.skipUnless(os.name == 'posix', 'Portable service runtime needs a Unix shell')
class PortableServiceReviewTests(unittest.TestCase):
    def test_colon_service_names_remain_distinct_with_requirements_and_exclusions(self):
        config = motd.preset_config('workshop', shell='sh')
        config['display'].update(sections=['services'], detail='full')
        config['services']['required'] = ['foo:two.service', 'foo:*']
        template = (ROOT / 'runtime/motd.sh').read_text(encoding='utf-8')
        marker = "motd_service_rows='sshd: running\n"
        self.assertEqual(template.count(marker), 1)
        template = template.replace(marker, "motd_service_rows='foo:one.service: running\nfoo:two.service: running\nsshd: running\n")
        templates = {'SH_TEMPLATE': template,
                     'DESIGNS_TEMPLATE': (ROOT / 'runtime/designs.sh').read_text(encoding='utf-8')}
        with tempfile.TemporaryDirectory(prefix='motd-colon-services-') as folder, patch.multiple(motd, **templates):
            source = Path(folder) / 'message.sh'
            for excluded in ([], ['foo:one.service']):
                config['services']['exclude'] = excluded
                for design in DESIGNS:
                    config['display']['design'] = design
                    source.write_text(motd.generate_artifact(config), encoding='utf-8')
                    result = subprocess.run(
                        ['/bin/sh', str(source), '--demo', '--plain', '--ascii', '--width', '100', '--rows', '60'],
                        capture_output=True, text=True, timeout=5,
                        env=dict(os.environ, TERM='xterm', LC_ALL='C'))
                    with self.subTest(design=design, excluded=excluded):
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, '')
                        self.assertEqual(result.stdout.count('foo:two.service: running'), 1, result.stdout)
                        self.assertNotIn('unavailable (not reported)', result.stdout)
                        if excluded:
                            self.assertNotIn('foo:one.service', result.stdout)
                        else:
                            self.assertEqual(result.stdout.count('foo:one.service: running'), 1, result.stdout)
                            self.assertLess(result.stdout.index('foo:two.service'), result.stdout.index('foo:one.service'))

    def test_required_services_are_promoted_once_when_patterns_overlap(self):
        config = motd.preset_config('workshop', shell='sh')
        config['display'].update(sections=['services'], detail='full')
        config['services']['required'] = ['cron', 'ss*', 'sshd', 'missing-*']
        templates = {
            'SH_TEMPLATE': (ROOT / 'runtime/motd.sh').read_text(encoding='utf-8'),
            'DESIGNS_TEMPLATE': (ROOT / 'runtime/designs.sh').read_text(encoding='utf-8'),
        }
        with tempfile.TemporaryDirectory(prefix='motd-service-review-') as folder, patch.multiple(motd, **templates):
            source = Path(folder) / 'message.sh'
            for design in DESIGNS:
                config['display']['design'] = design
                source.write_text(motd.generate_artifact(config), encoding='utf-8')
                result = subprocess.run(
                    ['/bin/sh', str(source), '--demo', '--plain', '--ascii', '--width', '100', '--rows', '60'],
                    capture_output=True, text=True, timeout=5,
                    env=dict(os.environ, TERM='xterm', LC_ALL='C'))
                with self.subTest(design=design):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, '')
                    self.assertEqual(result.stdout.count('cron: running'), 1)
                    self.assertEqual(result.stdout.count('sshd: running'), 1)
                    self.assertEqual(result.stdout.count('missing-*: unavailable (not reported)'), 1)
                    self.assertLess(result.stdout.index('cron: running'), result.stdout.index('sshd: running'))
                    self.assertLess(result.stdout.index('sshd: running'), result.stdout.index('docker: running'))


class WideResourceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='motd-wide-bars-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.templates = patch.multiple(motd, **{
            name + '_TEMPLATE': (ROOT / 'runtime' / filename).read_text(encoding='utf-8')
            for name, filename in (('BASH', 'motd.bash'), ('SH', 'motd.sh'),
                                   ('PS', 'motd.ps1'), ('DESIGNS', 'designs.sh'))})
        self.templates.start()
        self.addCleanup(self.templates.stop)

    def run_view(self, shell, design, columns, rows, *, sections=None, swap=True, extra=()):
        config = motd.preset_config('workshop', shell=shell)
        config['display'].update(design=design, detail='full', bar_layout='wide',
                                 show_swap=swap, sections=sections or ['resources'])
        source = self.root / ('message' + motd.artifact_suffix(config))
        source.write_text(motd.generate_artifact(config), encoding='utf-8')
        if shell == 'powershell':
            engine = os.environ.get('MOTD_TEST_POWERSHELL') or shutil.which('pwsh') or shutil.which('powershell')
            if not engine: self.skipTest('PowerShell is not available')
            args = [engine, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(source),
                    '-Demo', '-Plain', '-Ascii', '-Width', str(columns), '-Rows', str(rows)]
        else:
            args = [shell, str(source), '--demo', '--plain', '--ascii', '--width', str(columns), '--rows', str(rows)]
        result = subprocess.run(args + list(extra), capture_output=True, text=True, timeout=12,
                                env=dict(os.environ, TERM='xterm', LC_ALL='C',
                                         POWERSHELL_TELEMETRY_OPTOUT='1', DOTNET_CLI_TELEMETRY_OPTOUT='1'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertTrue(result.stdout.isascii())
        lines = result.stdout.splitlines()
        self.assertLessEqual(len(lines), rows - 1, result.stdout)
        self.assertLessEqual(max(map(len, lines)), columns, result.stdout)
        return result.stdout

    @unittest.skipUnless(os.name == 'posix', 'Unix bar contracts need Unix shells')
    def test_wide_unix_bars_use_full_panel_width_and_numeric_observations(self):
        for shell in ('bash', 'sh'):
            for columns in (40, 80):
                for design in ('cards', 'briefing'):
                    text = self.run_view(shell, design, columns, 50)
                    pattern = r'^\| ([#.]+) \|$' if design == 'cards' else r'^ ([#.]+) $'
                    bars = re.findall(pattern, text, re.M)
                    with self.subTest(shell=shell, columns=columns, design=design):
                        self.assertEqual(len(bars), 3, text)
                        self.assertTrue(all(len(bar) == columns - (4 if design == 'cards' else 2) for bar in bars))
                        # The filled part depicts the quantity actually named.
                        # A Bash launcher selects the portable backend on macOS
                        # and older Bash, so its filename cannot identify the
                        # collector. Dispatch has its own compatibility tests;
                        # this assertion verifies the displayed metric contract.
                        portable = 'RAM available ' in text
                        expected = .75 if portable else .25
                        self.assertLessEqual(abs(bars[0].count('#') / len(bars[0]) - expected), 1 / len(bars[0]))
                        self.assertIn('12582912/16777216 KiB' if portable else 'RAM 8.0Gi/32.0Gi', text)
                        self.assertIn('Root: 42% used' if portable else '220Gi/600Gi used', text)

    @unittest.skipUnless(os.name == 'posix', 'Unix bar contracts need Unix shells')
    def test_wide_unix_bars_fit_all_designs_and_small_viewports(self):
        all_sections = ['system', 'resources', 'services', 'processes', 'sessions', 'connections', 'attention', 'hints', 'io']
        for shell in ('bash', 'sh'):
            for design in DESIGNS:
                for columns, rows in ((40, 8), (40, 25), (80, 50)):
                    with self.subTest(shell=shell, design=design, columns=columns, rows=rows):
                        self.run_view(shell, design, columns, rows, sections=all_sections)

    @unittest.skipUnless(os.name == 'posix', 'Unix bar contracts need Unix shells')
    def test_wide_unix_bars_honor_swap_visibility_and_cli_override(self):
        for shell in ('bash', 'sh'):
            text = self.run_view(shell, 'cards', 80, 50, swap=False)
            self.assertNotIn('SWAP', text)
            self.assertNotIn('Swap free', text)
            self.assertEqual(len(re.findall(r'^\| [#.]+ \|$', text, re.M)), 2)
            inline = self.run_view(shell, 'cards', 80, 50, extra=('--bar-layout', 'inline'))
            self.assertNotRegex(inline, r'(?m)^\| [#.]{76} \|$')

    def test_power_shell_wide_bars_fit_layouts_and_use_existing_totals(self):
        for design in DESIGNS:
            for columns, rows in ((40, 25), (80, 50)):
                with self.subTest(design=design, columns=columns, rows=rows):
                    output = self.run_view('powershell', design, columns, rows)
                    self.assertIn('6.0G/16.0G used', output)
                    self.assertIn('120.0G/512.0G used', output)
                    self.assertNotIn('unavailable', output)
                    bars = re.findall(r'\[([#-]+)\]', output)
                    self.assertGreaterEqual(len(bars), 2, output)
                    self.assertGreater(len(bars[0]), 12)
                    self.assertLessEqual(abs(bars[0].count('#') / len(bars[0]) - .375), 1 / len(bars[0]))
                    if design in ('classic', 'cards', 'dashboard'):
                        self.assertTrue(all(len(bar) == columns - 6 for bar in bars), output)
        output = self.run_view('powershell', 'cards', 80, 50, swap=False)
        self.assertNotIn('Swap/pagefile', output)
        self.assertEqual(len(re.findall(r'\[([#-]+)\]', output)), 2)
        paired = self.run_view('powershell', 'dashboard', 81, 50, sections=['system', 'resources'])
        self.assertTrue(all(len(bar) == 34 for bar in re.findall(r'\[([#-]+)\]', paired)), paired)

    @unittest.skipUnless(os.name == 'posix', 'The fraction formatter is a POSIX shell function')
    def test_fraction_formatter_does_not_invent_bars_for_missing_or_invalid_values(self):
        commands = '''. "$1"
for invalid in unavailable -1 2:3; do
    motd_view_fraction_bar 100 "$invalid" 40
    [ "$MV_BAR_VALID" = 0 ] || exit 9
done
motd_view_fraction_bar 0 0 40
[ "$MV_BAR_VALID" = 0 ] || exit 10
motd_view_fraction_bar 100 101 40
[ "$MV_BAR_VALID" = 0 ] || exit 11
motd_view_fraction_bar 999999999999998 999999999999999 40
[ "$MV_BAR_VALID" = 0 ] || exit 12
motd_view_fraction_bar 999999999999999 249999999999999 40
printf '%s\\n' "$MV_BAR_VALID" "$MV_BAR"
'''
        result = subprocess.run(['/bin/sh', '-c', commands, 'sh', str(ROOT / 'runtime/designs.sh')],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '1\n' + '#' * 10 + '.' * 30 + '\n')

    def test_invalid_bar_layout_is_rejected_before_before_hook(self):
        engines = [('bash', ['bash']), ('sh', ['/bin/sh'])] if os.name == 'posix' else []
        powershell = os.environ.get('MOTD_TEST_POWERSHELL') or shutil.which('pwsh') or shutil.which('powershell')
        if powershell:
            engines.append(('powershell', [powershell, '-NoLogo', '-NoProfile', '-NonInteractive', '-File']))
        if not engines:
            self.skipTest('No requested runtime is available')
        for shell, command in engines:
            config = motd.preset_config('workshop', shell=shell)
            config['hooks']['before'] = [
                {'argv': ['motd:print', 'UNEXPECTED_BEFORE_HOOK'], 'timeout_seconds': 1, 'on_failure': 'stop'}]
            source = self.root / ('invalid' + motd.artifact_suffix(config))
            source.write_text(motd.generate_artifact(config), encoding='utf-8')
            flag = '-BarLayout' if shell == 'powershell' else '--bar-layout'
            with self.subTest(shell=shell):
                result = subprocess.run(command + [str(source), flag, 'invalid'], capture_output=True,
                                        text=True, timeout=8, env=dict(os.environ,
                                            POWERSHELL_TELEMETRY_OPTOUT='1', DOTNET_CLI_TELEMETRY_OPTOUT='1'))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('UNEXPECTED_BEFORE_HOOK', result.stdout)
                self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
