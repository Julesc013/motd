"""Native shared-composer behavior, including cosmetic invariance and literals.

MOTD_TEST_CONFIGURATOR can select a parallel integration checkout during development;
ordinary CI uses this repository. The canonical PS template is tested directly.
"""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
MODULE = Path(os.environ.get('MOTD_TEST_CONFIGURATOR', str(ROOT / 'motd.py')))
_spec = importlib.util.spec_from_file_location('motd_presentation_ps_subject', MODULE)
motd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motd)
motd.PS_TEMPLATE = (ROOT / 'runtime/motd.ps1').read_text(encoding='utf-8')
POWERSHELL = os.environ.get('MOTD_TEST_POWERSHELL') or shutil.which('pwsh') or shutil.which('powershell')
SGR = re.compile(r'\x1b\[[0-9;]*m')


def cells(line):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF' else 1
               for c in SGR.sub('', line))


@unittest.skipUnless(POWERSHELL, 'Set MOTD_TEST_POWERSHELL for native presentation evidence')
class PowerShellPresentationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='motd-presentation-ps-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.script = self.root / 'view.ps1'
        self.config = motd.preset_config('workshop', shell='powershell')
        self.config['display']['sections'] = list(motd.SECTION_IDS)

    def render(self, width=80, rows=50, extra=(), unicode=True, colored=False):
        self.script.write_text(motd.generate_artifact(self.config), encoding='utf-8')
        env = os.environ.copy(); env.pop('NO_COLOR', None); env['TERM'] = 'xterm-256color'
        result = subprocess.run([POWERSHELL, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(self.script),
                                 '-DemoAlerts', '-NoHooks', '-Color' if colored else '-Plain',
                                 '-Unicode' if unicode else '-Ascii', '-Width', str(width), '-Rows', str(rows), *extra],
                                capture_output=True, text=True, encoding='utf-8', timeout=25, env=env, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        lines = result.stdout.splitlines()
        self.assertTrue(lines)
        self.assertLessEqual(len(lines), rows - 1)
        self.assertTrue(all(cells(line) == width for line in lines), repr(result.stdout))
        return result.stdout

    def test_all_presets_use_requested_grids_and_retain_alerts(self):
        for design in motd.DESIGN_POLICIES:
            self.config['display']['design'] = design
            for width, rows in ((80,25), (80,50), (120,50), (160,50), (40,8)):
                with self.subTest(design=design, width=width, rows=rows):
                    text = self.render(width, rows)
                    self.assertIn('DEMO', text)
                    self.assertIn('Host demo-host', text)
                    if rows >= 25:
                        self.assertIn('91%', text)
                    else:
                        self.assertIn('Hidden:', text)

    def test_named_presets_equal_explicit_classic_axes(self):
        for design, policy in motd.DESIGN_POLICIES.items():
            self.config['display'].update(design=design, panel_layout='auto', panel_frame='auto', heading_style='auto')
            named = self.render(rows=100)
            self.config['display'].update(design='classic', panel_layout=policy[0], panel_frame=policy[1], heading_style=policy[2])
            explicit = self.render(rows=100)
            self.assertEqual(named, explicit, design)

    def test_border_style_preserves_body_allocation_and_semantic_tones(self):
        outputs = []
        for style in ('single', 'rounded', 'double', 'heavy', 'ascii'):
            self.config['display']['border_style'] = style
            text = self.render(colored=True)
            self.assertIn('\x1b[33m', text)
            self.assertIn('91%', text)
            normalized = re.sub(r'[\u2500-\u257f+|\-]', '#', text)
            outputs.append(normalized)
        self.assertEqual(len(set(outputs)), 1)
        forced_ascii = [self.render(extra=('-BorderStyle', style), unicode=False) for style in ('single','rounded','double','heavy','ascii')]
        self.assertEqual(len(set(forced_ascii)), 1)
        forced_ascii[0].encode('ascii')

    def test_heading_frame_visibility_and_notes_remain_bounded(self):
        self.config['display']['section_notes'] = {'resources': 'Measured once; bytes remain in the body'}
        for frame, visibility, heading, alignment, notes in (
                ('continuous','all','rule','left','none'),
                ('continuous','outer','plain','center','custom'),
                ('separate','sections','rule','right','summary'),
                ('separate','none','inline','left','custom'),
                ('none','none','hidden','center','custom')):
            self.config['display'].update(panel_frame=frame, border_visibility=visibility, heading_style=heading,
                                          heading_align=alignment, separator_text=notes)
            for width, rows in ((80,25),(160,50),(40,8)):
                self.render(width, rows)
        self.config['display'].update(panel_frame='none', border_visibility='none', heading_style='hidden', separator_text='none')
        text = self.render(160,100)
        self.assertNotRegex(text, '[\u2500-\u257f]')
        for value in ('6.0 GiB', '120.0 GiB', '152.4s', '80.0G', '91%'):
            self.assertIn(value, text)

    def test_literal_titles_and_notes_never_evaluate(self):
        literal = "Literal $(New-Item should-not-exist) ` $env:PATH ; ' note"
        self.config['display'].update(section_titles={'system': 'My host'}, section_notes={'system': literal},
                                      separator_text='custom', heading_style='plain', panel_frame='none')
        text = self.render(160,100)
        self.assertIn('My host', text)
        self.assertIn(literal, text)
        self.assertFalse((self.root / 'should-not-exist').exists())
        self.config['display']['separator_text'] = 'none'
        text = self.render(160,100)
        self.assertNotIn(literal, text)
        self.assertIn('demo-host | 8 logical CPUs', text)

    def test_short_labels_do_not_rewrite_values_and_clip_is_independent(self):
        self.config['display']['section_titles'] = {'system': 'S' * 120}
        full = self.render()
        short = self.render(extra=('-LabelStyle','short'))
        self.assertIn(motd.SECTION_TEXT['resources'][0], full)
        self.assertIn(motd.SECTION_TEXT['resources'][1], short)
        self.assertIn('storage-worker', short)
        self.assertIn('...', full)
        clipped = self.render(extra=('-Overflow','clip'))
        self.assertNotIn('...', clipped)
        self.assertIn('demo-host', clipped)

    def test_columns_reflow_and_wide_bars_follow_actual_cells(self):
        self.config['display'].update(panel_layout='columns', panel_frame='continuous', bar_layout='wide', detail='full')
        wide = self.render(160,100, unicode=False)
        self.assertIn('+  +', wide)
        self.assertIn('6.0G/16.0G', wide)
        self.assertIn('120.0G/512.0G', wide)
        narrow = self.render(40,100, unicode=False)
        self.assertNotIn('+  +', narrow)
        self.assertIn('6.0G/16.0G', narrow)

    def test_invalid_runtime_override_refuses_before_configured_calls(self):
        self.config['hooks']['before'] = [{'argv': ['motd:print','UNEXPECTED BEFORE'], 'timeout_seconds': 1, 'on_failure':'stop'}]
        self.script.write_text(motd.generate_artifact(self.config), encoding='utf-8')
        for args in (('-BorderStyle','wrong'), ('-PanelLayout','wrong'), ('-HeadingStyle','wrong'), ('-Padding','-2')):
            result = subprocess.run([POWERSHELL,'-NoProfile','-NonInteractive','-File',str(self.script),*args],
                                    capture_output=True,text=True,encoding='utf-8',timeout=20,cwd=self.root)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('UNEXPECTED BEFORE',result.stdout)


if __name__ == '__main__':
    unittest.main()
