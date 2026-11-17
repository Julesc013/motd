"""Refuse ambiguous review paths and unbounded backup inputs before mutation."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import motd


class PathSafetyTests(unittest.TestCase):
    def test_displayed_paths_cannot_inject_terminal_controls_or_managed_markers(self):
        for suffix in ('\n# <<< motd name <<<', '\rnew', '\x1b[2J', '\x85text', '\x00'):
            with self.subTest(suffix=repr(suffix)), self.assertRaises(motd.MotdError):
                motd.absolute('message' + suffix)

    @unittest.skipUnless(os.name == 'posix', 'POSIX transaction path contract')
    def test_direct_transaction_path_checks_do_not_bypass_control_rejection(self):
        with self.assertRaises(motd.TxError) as caught:
            motd._tx_path('/tmp/message\nmisleading')
        self.assertEqual(caught.exception.code, 'invalid_path')

    @unittest.skipUnless(os.name == 'posix', 'POSIX snapshot contract')
    def test_large_existing_target_is_refused_without_creating_a_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); target = root / 'oversized'; state = root / 'state'
            size = motd._TX_MAX_FILE_BYTES + 1
            with target.open('wb') as stream: stream.truncate(size)
            with self.assertRaises(motd.TxError) as caught:
                motd.tx_plan([{'path': str(target), 'content': 'replacement', 'mode': 0o600}], str(state))
            self.assertEqual(caught.exception.code, 'target_too_large')
            self.assertEqual(target.stat().st_size, size)
            self.assertFalse(state.exists())


if __name__ == '__main__':
    unittest.main()
