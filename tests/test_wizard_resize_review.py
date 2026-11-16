"""Input integrity and tty restoration in the real screen reader.

These cases use a temporary child and PTY. They never execute hooks, install
files, or write the user's terminal settings. No renderer is needed to exercise
the editor's handling of terminal bytes.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WizardInputReviewTests(unittest.TestCase):
    def run_reader(self, chunks, *, resize_before_interrupt=False, resize_walkthrough=False):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 25, 80, 0, 0))
        original = termios.tcgetattr(slave)
        program = (
            'import json, sys\n'
            'sys.path.insert(0, ' + repr(str(ROOT)) + ')\n'
            'import motd\n'
            'ui = motd.WizardUI("screen")\n'
            'ui.page("Input integrity", ["Type an answer."], config='
            + ('motd.preset_config()' if resize_walkthrough else 'None') + ')\n'
            'try:\n'
            '    result = {"answer": ui.read("Name: ")}\n'
            'except (KeyboardInterrupt, EOFError) as exc:\n'
            '    result = {"exception": type(exc).__name__}\n'
            'print("\\nINPUT_RESULT=" + json.dumps(result), flush=True)\n'
        )

        def controlling_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        process = subprocess.Popen(
            [sys.executable, '-c', program], cwd=ROOT, stdin=slave, stdout=slave,
            stderr=slave, env=dict(os.environ, TERM='xterm-256color', COLUMNS='200', LINES='90'),
            preexec_fn=controlling_terminal,
        )
        output = bytearray()

        def drain(wait=0.05):
            ready, _, _ = select.select([master], [], [], wait)
            if ready:
                try: output.extend(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO: raise

        try:
            deadline = time.monotonic() + 8

            def await_output(marker, start=0):
                while marker not in output[start:]:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        self.fail('Missing ' + repr(marker) + ': ' + output.decode(errors='replace'))
                    drain()
                return output[start:].decode(errors='replace')

            # Wait for the actual noncanonical reader; early keystrokes must
            # not race the terminal's previous canonical input discipline.
            while termios.tcgetattr(slave)[3] & termios.ICANON:
                if process.poll() is not None or time.monotonic() >= deadline:
                    self.fail('Screen reader did not start: ' + output.decode(errors='replace'))
                drain()
            for delay, data in chunks:
                until = time.monotonic() + delay
                while time.monotonic() < until: drain(max(0, min(0.05, until - time.monotonic())))
                os.write(master, data)
            if resize_walkthrough:
                # No key is sent after each resize until its reflowed frame has
                # appeared. Inherited COLUMNS/LINES deliberately disagree.
                await_output(b'PREVIEW 80x15')
                await_output(b'partial')
                start = len(output)
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 50, 40, 0, 0))
                resized = await_output(b'PREVIEW 40x40', start)
                self.assertIn('Name: partial', resized)
                self.assertNotIn('Preview unavailable', resized)
                start = len(output)
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 12, 30, 0, 0))
                await_output(b'Resize to at least 40x18', start)
                start = len(output)
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 25, 80, 0, 0))
                restored = await_output(b'PREVIEW 80x15', start)
                self.assertIn('Name: partial', restored)
                os.write(master, b'-done\n')
            if resize_before_interrupt:
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 12, 30, 0, 0))
                until = time.monotonic() + 0.2
                while time.monotonic() < until: drain(0.05)
                os.write(master, b'\x03')
            while process.poll() is None and time.monotonic() < deadline: drain()
            if process.poll() is None:
                self.fail('Screen reader did not finish: ' + output.decode(errors='replace'))
            drain(0)
            self.assertEqual(process.returncode, 0, output.decode(errors='replace'))
            self.assertEqual(termios.tcgetattr(slave), original, 'TTY flags were not restored')
            text = output.decode(errors='replace')
            marker = 'INPUT_RESULT='
            self.assertIn(marker, text)
            return json.loads(text.rsplit(marker, 1)[1].splitlines()[0])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            os.close(master)
            os.close(slave)

    def test_modified_arrow_never_inserts_escape_parameters(self):
        result = self.run_reader([(0, b'alpha\x1b[1;5DX\n')])
        # Ignoring an unsupported modified arrow or implementing word-left are
        # both safe. Inserting pieces of its escape sequence into a recipe is not.
        self.assertIn(result['answer'], ('alphaX', 'Xalpha'))

    def test_bare_escape_does_not_swallow_later_printable_input(self):
        result = self.run_reader([(0, b'alpha\x1b'), (0.25, b'X\n')])
        self.assertEqual(result['answer'], 'alphaX')

    def test_interrupt_after_resize_restores_terminal_flags(self):
        result = self.run_reader([(0, b'unfinished')], resize_before_interrupt=True)
        self.assertEqual(result, {'exception': 'KeyboardInterrupt'})

    def test_resize_reflows_preview_without_enter_and_preserves_answer(self):
        result = self.run_reader([(0, b'partial')], resize_walkthrough=True)
        self.assertEqual(result, {'answer': 'partial-done'})

    def test_eof_restores_terminal_flags(self):
        result = self.run_reader([(0, b'\x04')])
        self.assertEqual(result, {'exception': 'EOFError'})


if __name__ == '__main__':
    unittest.main()
