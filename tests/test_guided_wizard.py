"""Guided decisions and responsive generated-script preview lifecycle."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


class GuidedWizardTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(motd, 'resolve_presentation'), 'Requires shared presentation schema')
    def test_visiting_guided_setup_preserves_explicit_layout_and_text(self):
        config = motd.preset_config()
        config['display'].update(panel_layout='columns', panel_frame='separate',
            border_style='double', heading_style='inline', theme='amber',
            section_titles={'resources': 'Capacity'}, section_notes={'services': 'Literal $name'})

        class KeepCurrent:
            def select(self, title, choices, default=0, **kwargs):
                value = choices[default][1]
                self.last_preview = kwargs['preview_factory'](value)
                return '@next', value

        result = motd._configure(config, KeepCurrent())
        self.assertEqual(result, motd.validate_config(config))
        changed = motd._wizard_variant(config, 'display.design', 'ledger')
        self.assertEqual(changed['display']['panel_layout'], 'auto')
        self.assertEqual(changed['display']['panel_frame'], 'auto')
        self.assertEqual(motd.resolve_presentation(changed['display'])['panel_frame'], 'none')
        for field in ('border_style', 'heading_style', 'theme', 'section_titles', 'section_notes'):
            self.assertEqual(changed['display'][field], config['display'][field])

    def test_each_guided_decision_has_related_fine_controls(self):
        steps = motd._guided_steps(motd.preset_config())
        self.assertIn('display.design', [path for _, path, _ in steps])
        self.assertIn('display.theme', [path for _, path, _ in steps])
        self.assertIn('display.sections', [path for _, path, _ in steps])
        self.assertTrue(all(fields for _, _, fields in steps))
        for _, path, _ in steps:
            if path not in (None, 'display.sections'):
                self.assertIn(path, motd._wizard_choices(motd.preset_config()))

    def test_guided_change_preserves_other_settings_and_back_retains_draft(self):
        config = motd.preset_config()
        config['messages'] = ['Keep this notice.']
        config['display'].update(title='MY HOSTS', width=120, padding=2)
        pages = []

        class ScriptedUI:
            def select(self, title, choices, default=0, **kwargs):
                pages.append(title)
                current = choices[default][1]
                # Choose green, go back to detail, then return to colours.
                if title.startswith('Choose the colours') and sum(x.startswith('Choose the colours') for x in pages) == 1:
                    self.preview = kwargs['preview_factory']('green')
                    return '@b', 'green'
                return '@next', current

        ui = ScriptedUI()
        result = motd._configure(config, ui)
        self.assertEqual(result['display']['theme'], 'green')
        self.assertEqual(result['display']['width'], 120)
        self.assertEqual(result['display']['padding'], 2)
        self.assertEqual(result['display']['title'], 'MY HOSTS')
        self.assertEqual(result['messages'], config['messages'])
        self.assertEqual(ui.preview['display']['theme'], 'green')
        self.assertGreater(sum(x.startswith('Choose the amount of detail') for x in pages), 1)
        self.assertEqual(config['display']['theme'], 'cyan', 'Input recipe must remain independent')

    def test_line_guided_setup_shows_actual_generated_output(self):
        config = motd.preset_config('home-lab')
        ui = motd.WizardUI('line')
        capture = io.StringIO()
        with patch('builtins.input', return_value=''), patch('sys.stdout', capture):
            result = motd._configure(config, ui)
        text = capture.getvalue()
        self.assertIn('Synthetic preview', text)
        self.assertIn('ws-bench-07', text)
        self.assertIn('Choose the colours', text)
        self.assertEqual(result, motd.validate_config(config))

    def test_preview_child_is_cancellable_and_stale_result_cannot_win(self):
        ui = motd.WizardUI('line')
        ui._interactive_preview = True
        config = motd.preset_config()
        try:
            command = [sys.executable, '-c', 'import time; time.sleep(10); print("OLD")']
            with patch.object(motd, 'preview_command', return_value=command):
                start = time.monotonic()
                self.assertIn('Rendering', ui.sample(config, 80, 25)[0])
                self.assertLess(time.monotonic() - start, 1)
                old = ui._preview_job['process']
            config['display']['theme'] = 'green'
            command = [sys.executable, '-c', 'print("CURRENT")']
            with patch.object(motd, 'preview_command', return_value=command):
                ui.sample(config, 80, 25)
            self.assertIsNotNone(old.poll(), 'Obsolete preview child must be reaped')
            deadline = time.monotonic() + 3
            while ui._preview_job and time.monotonic() < deadline:
                ui._poll_preview(); time.sleep(.01)
            self.assertEqual(ui.sample(config, 80, 25), ['CURRENT'])
            self.assertFalse(any('OLD' in line for lines in ui.cache.values() for line in lines))
        finally:
            ui.finish()

    def test_slow_preview_times_out_and_finish_cleans_child(self):
        ui = motd.WizardUI('line'); ui._interactive_preview = True
        ui.PREVIEW_TIMEOUT = .05
        try:
            command = [sys.executable, '-c', 'import time; time.sleep(10)']
            with patch.object(motd, 'preview_command', return_value=command):
                ui.sample(motd.preset_config(), 80, 25)
            child = ui._preview_job['process']
            time.sleep(.08)
            self.assertTrue(ui._poll_preview())
            self.assertIsNotNone(child.poll())
            self.assertIn('timed out', ui.sample(motd.preset_config(), 80, 25)[0])
            self.assertIsNone(ui._preview_job)
        finally:
            ui.finish()


@unittest.skipUnless(os.name == 'posix', 'Real terminal contract requires POSIX PTY')
class GuidedTerminalTests(unittest.TestCase):
    def test_number_key_previews_generated_output_before_enter(self):
        import errno
        import fcntl
        import pty
        import select
        import struct
        import termios
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 50, 80, 0, 0))
        original = termios.tcgetattr(slave)
        program = '''import sys, json
sys.path.insert(0, ROOT)
import motd
c = motd.preset_config()
ui = motd.WizardUI('screen')
try:
    result = ui.select('Choose the colours', [('Cyan','cyan'),('Green','green')],
        preview_factory=lambda choice: motd._wizard_variant(c, 'display.theme', choice), guided=True)
    print('RESULT=' + json.dumps(result), flush=True)
finally:
    ui.finish()
'''.replace('ROOT', repr(str(ROOT)))
        environment = dict(os.environ, TERM='xterm-256color')
        environment.pop('NO_COLOR', None)
        process = subprocess.Popen([sys.executable, '-c', program], stdin=slave,
            stdout=slave, stderr=slave, start_new_session=True,
            env=environment)
        output = bytearray()
        deadline = time.monotonic() + 8

        def await_bytes(marker, start=0):
            while marker not in output[start:]:
                if process.poll() is not None or time.monotonic() >= deadline:
                    self.fail('Missing ' + repr(marker) + ': ' + output.decode(errors='replace'))
                ready, _, _ = select.select([master], [], [], .05)
                if ready:
                    try: output.extend(os.read(master, 65536))
                    except OSError as exc:
                        if exc.errno != errno.EIO: raise
            return bytes(output[start:])
        try:
            await_bytes(b'ws-bench-07')
            start = len(output)
            os.write(master, b'2')  # No newline: selection and preview must react.
            await_bytes(b'> 2. Green', start)
            await_bytes(b'ws-bench-07', start)
            self.assertIsNone(process.poll())
            self.assertIn(b'\x1b[32m', bytes(output[start:]))
            os.write(master, b'\n')
            await_bytes(b'RESULT=')
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(termios.tcgetattr(slave), original)
            self.assertLess(bytes(output).count(b'\x1b[2J'), 2, 'Choice changes must not clear the screen')
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=3)
            os.close(master); os.close(slave)


if __name__ == '__main__':
    unittest.main()
