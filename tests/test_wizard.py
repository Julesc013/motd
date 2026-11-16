"""Preview/navigation contracts: no installed file or real profile is changed."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


class Terminal(io.StringIO):
    def isatty(self): return True


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.output = Terminal()
        self.terminal = os.terminal_size((80, 24))
        self.stack = []
        for context in (patch('sys.stdin', Terminal()), patch('sys.stdout', self.output),
                        patch.dict(os.environ, {'TERM': 'xterm-256color'}),
                        patch('shutil.get_terminal_size', return_value=self.terminal)):
            context.__enter__(); self.stack.append(context)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for context in reversed(self.stack): context.__exit__(None, None, None)

    def test_auto_screen_falls_back_for_dumb_small_and_redirected_terminals(self):
        self.assertTrue(motd.WizardUI().screen)
        self.assertFalse(motd.WizardUI('line').screen)
        with patch.dict(os.environ, {'TERM': 'dumb'}):
            self.assertFalse(motd.WizardUI().screen)
            self.assertTrue(motd.WizardUI('screen').screen)
        with patch('shutil.get_terminal_size', return_value=os.terminal_size((40, 12))):
            self.assertFalse(motd.WizardUI('screen').screen)
        with patch('sys.stdout', io.StringIO()):
            self.assertFalse(motd.WizardUI('screen').screen)

    def test_page_preview_is_actual_fixture_bounded_to_screen(self):
        config = motd.preset_config('workshop')
        motd.WizardUI('screen').page('Appearance | page 2/5',
            [' 1. Heading: WORKSHOP STATUS', ' 2. Site: Workshop', ' 3. Theme: cyan',
             ' 4. Columns: 132', ' 5. Rows: 25'], config=config,
            footer='Number edits | Enter next | B back | P preview | Q cancel')
        output = self.output.getvalue()
        self.assertIn('\x1b[2J\x1b[H', output)
        self.assertIn('PREVIEW | synthetic data', output)
        self.assertIn('WORKSHOP STATUS', output)
        lines = motd._SGR.sub('', output.replace('\x1b[2J\x1b[H', '')).splitlines()
        self.assertLess(len(lines), 24, output)
        self.assertTrue(all(len(line) <= 79 for line in lines), output)

    def test_theme_selection_redraws_preview_before_accepting(self):
        config = motd.preset_config()
        def variation(theme):
            c = motd.copy.deepcopy(config); c['display']['theme'] = theme; return c
        with patch('builtins.input', side_effect=['2', '']):
            theme = motd.WizardUI('screen').select('Theme', [('Cyan', 'cyan'), ('Green', 'green')],
                                                   preview_factory=variation)
        self.assertEqual(theme, 'green')
        output = self.output.getvalue()
        self.assertGreaterEqual(output.count('\x1b[2J\x1b[H'), 2)
        self.assertIn('Green [selected]', output)
        self.assertNotIn('Preview unavailable', output)

    def test_navigation_back_retains_edits_and_invalid_value_does_not_replace_draft(self):
        # Destination -> Appearance; invalid width -> valid width -> Back -> Next.
        answers = ['n', '4', 'bad', '4', '80', 'b', 'n', 'n', 'n', 'n', 'n']
        with patch('builtins.input', side_effect=answers):
            c = motd._configure(motd.preset_config(), motd.WizardUI('line'))
        self.assertEqual(c['display']['width'], 80)
        self.assertIn('invalid literal', self.output.getvalue())
        self.assertNotIn('\x1b', self.output.getvalue())

    def test_cancel_and_demo_do_not_execute_configured_calls(self):
        with tempfile.TemporaryDirectory(prefix='motd-wizard-contract-') as folder:
            sentinel = Path(folder) / 'should-not-exist'
            config = motd.preset_config()
            config['hooks']['before'] = [{'argv': ['touch', str(sentinel)]}]
            text = motd.demo_text(config, 80)
            self.assertIn('WORKSHOP STATUS', text)
            self.assertFalse(sentinel.exists())
            with patch('builtins.input', return_value='q'), self.assertRaises(motd.WizardCancelled):
                motd._configure(config, motd.WizardUI('screen'))
            self.assertFalse(sentinel.exists())
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_missing_interpreter_is_labelled_instead_of_substituted(self):
        config = motd.preset_config(); config['shell'] = 'powershell'
        with patch('shutil.which', return_value=None):
            lines = motd.WizardUI('screen').sample(config, 80)
        self.assertIn('Preview unavailable', lines[0])
        self.assertIn('powershell', lines[0])
        self.assertNotIn('WORKSHOP STATUS', '\n'.join(lines))

    def test_public_demo_shows_literal_text_before_consumer_serialization(self):
        config = motd.preset_config('public-console')
        config['public_text'] = r'Literal \h and \n'
        self.assertIn(r'Literal \h and \n', motd.demo_text(config))
        self.assertIn(r'Literal \\h and \\n', motd.generate_artifact(config))
        config['target'] = 'text'
        self.assertEqual(motd.demo_text(config), motd.generate_artifact(config))

    def test_preview_clips_wide_cells_and_drops_terminal_control(self):
        result = motd.terminal_line('A\u754cB\x07\x1b[31mC', 3, color=False)
        self.assertEqual(result, 'A\u754c')


if __name__ == '__main__': unittest.main()
