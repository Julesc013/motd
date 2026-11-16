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
        ui = motd.WizardUI('screen')
        frame = ui.frame('Appearance | page 2/5',
            [' 1. Heading: WORKSHOP STATUS', ' 2. Site: Workshop', ' 3. Theme: cyan',
             ' 4. Columns: 132', ' 5. Rows: 25'], config=config,
            footer='Num edit | N next B back P view H calls Q', prompt='Page choice: ')
        output = '\n'.join(frame)
        self.assertIn('PREVIEW 80x14 | demo | calls off', output)
        self.assertIn('WORKSHOP STATUS', output)
        lines = [motd._SGR.sub('', line) for line in frame]
        self.assertEqual(len(lines), 24, output)
        self.assertTrue(all(len(line) <= 80 for line in lines), output)
        self.assertEqual(lines[8], 'Page choice: ')
        self.assertTrue(lines[9].startswith('PREVIEW '))
        self.assertTrue(any('resize for more' in line for line in lines[10:]))
        self.assertTrue(any(line.startswith(('╚', '+')) for line in lines[10:]))

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
        answers = ['n', '4', 'bad', '4', '80', 'b', 'n', 'n', 'n', 'n', 'n', 'n', 'n']
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

    def test_all_configuration_pages_fit_five_question_rows(self):
        for preset in motd.PRESET_NAMES:
            pages = motd._configuration_pages(motd.preset_config(preset))
            self.assertTrue(all(0 < len(fields) <= 5 for _, fields in pages))

    def test_preview_replans_all_four_terminal_geometries_without_editing_recipe(self):
        config = motd.preset_config()
        original = motd.dump_config(config)
        ui = motd.WizardUI('screen')
        for width, height in ((40,25), (40,50), (80,25), (80,50)):
            with self.subTest(width=width, height=height), patch('shutil.get_terminal_size', return_value=os.terminal_size((width,height))):
                self.assertTrue(ui.screen)
                frame = ui.frame('Appearance', ['1. Theme: cyan'], config=config, prompt='Page choice: ')
                self.assertEqual(len(frame), height)
                self.assertIn(f'{width}x{height-10}', frame[9])
                self.assertIn('ws-bench-07', frame[10])
                self.assertTrue(any(line.startswith(('╚', '+')) for line in (motd._SGR.sub('', line) for line in frame[10:])))
                self.assertFalse(any('Preview unavailable' in line for line in frame))
        self.assertEqual(motd.dump_config(config), original)

    def test_call_samples_are_opt_in_ordered_and_never_execute(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'must-not-run'
            config = motd.preset_config()
            config['hooks']['before'] = [{'argv':['fastfetch']},
                {'argv':['touch', str(marker)], 'preview_text':'Custom before sample'}]
            config['hooks']['after'] = [{'argv':['echo', 'Session ready']}]
            config = motd.validate_config(config)
            ui = motd.WizardUI('screen')
            with patch('shutil.get_terminal_size', return_value=os.terminal_size((80,50))):
                hidden = '\n'.join(ui.frame('Theme', config=config))
                self.assertNotIn('fastfetch', hidden)
                self.assertNotIn('Session ready', hidden)
                ui.show_calls = True
                shown = '\n'.join(ui.frame('Theme', config=config))
            self.assertLess(shown.index('fastfetch'), shown.index('WORKSHOP STATUS'))
            self.assertLess(shown.index('Custom before sample'), shown.index('WORKSHOP STATUS'))
            self.assertLess(shown.index('WORKSHOP STATUS'), shown.index('Session ready'))
            self.assertFalse(marker.exists())
            self.assertEqual(motd.validate_config(motd.tomllib.loads(motd.dump_config(config))), config)

    def test_long_call_samples_are_labelled_and_scrollable(self):
        config = motd.preset_config()
        config['hooks']['before'] = [{'argv':['example'], 'preview_text':'\n'.join(f'Sample row {i}' for i in range(30))}]
        ui = motd.WizardUI('screen'); ui.show_calls = True
        with patch('shutil.get_terminal_size', return_value=os.terminal_size((40,25))):
            first = ui.frame('Preview', config=config)
            self.assertIn('J/K scroll', first[9])
            ui.preview_offset = 25
            later = ui.frame('Preview', config=config)
            self.assertNotEqual(first[10:], later[10:])
            self.assertTrue(any('ws-bench-07' in line for line in later))


if __name__ == '__main__': unittest.main()
