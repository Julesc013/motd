"""Plain embedded TOML and the configurator's actual older-Python boundary."""
from __future__ import annotations

from decimal import Decimal
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd

try:
    import tomllib as standard_toml
except ImportError:
    standard_toml = None


class BundledTomlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = motd._motd_vendored_tomli()

    def test_all_presets_round_trip_through_bundled_parser(self):
        for preset in motd.PRESET_NAMES:
            for shell in motd.SHELLS:
                with self.subTest(preset=preset, shell=shell):
                    config = motd.preset_config(preset, shell)
                    text = motd.dump_config(config)
                    self.assertEqual(motd.validate_config(self.parser.loads(text)), config)

    def test_plain_string_is_data_and_binary_file_load_uses_utf8(self):
        text = 'title = "Workshop β"\npayload = "__import__(\\\"os\\\").system(\\\"example\\\")"\n'
        value = self.parser.load(io.BytesIO(text.encode('utf-8')))
        self.assertEqual(value['title'], 'Workshop β')
        self.assertEqual(value['payload'], '__import__("os").system("example")')
        with self.assertRaises(TypeError):
            self.parser.load(io.StringIO(text))

    def test_invalid_documents_are_rejected(self):
        invalid = ['key=1\nkey=2', 'key = null', 'key = {"a": 1}',
                   'key = "unterminated', 'key = 01', 'key = "\\q"',
                   '[table]\n[table]', 'key="\x00"']
        for document in invalid:
            with self.subTest(document=repr(document)):
                with self.assertRaises(self.parser.TOMLDecodeError):
                    self.parser.loads(document)
                if standard_toml is not None:
                    with self.assertRaises(standard_toml.TOMLDecodeError):
                        standard_toml.loads(document)

    @unittest.skipIf(standard_toml is None, 'Differential reference needs Python 3.11+ stdlib tomllib')
    def test_toml_one_zero_values_match_standard_library(self):
        fixtures = [
            'string="line\\nUnicode \\u03b2"\narray=[1, 2.5, true, "x"]\n',
            'date=1979-05-27\ntime=07:32:00.123456\nstamp=1979-05-27T07:32:00-07:00\n',
            'table={ key="value", nested={ x=1 } }\nquoted."a.b"=2\n',
            'integer=1_000\nhex=0xff\nbin=0b101\noct=0o755\nfloat=1.25e-3\n',
            '[[hooks.before]]\nargv=["printf", "%s\\n", "Ready"]\n'
            '[[hooks.before]]\nargv=["example", "quoted \\\" text"]\n',
            "multi='''first\nsecond'''\n# a trailing comment\nempty=[]\n",
        ]
        for document in fixtures:
            with self.subTest(document=document):
                self.assertEqual(self.parser.loads(document), standard_toml.loads(document))
        document = 'value = 0.982492'
        self.assertEqual(self.parser.loads(document, parse_float=Decimal),
                         standard_toml.loads(document, parse_float=Decimal))

    def test_generated_plain_embedding_matches_licensed_source(self):
        result = subprocess.run([sys.executable, str(ROOT/'tools/embed_toml.py'), '--check'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(os.environ.get('MOTD_TEST_PYTHON38'), 'Set MOTD_TEST_PYTHON38 for actual Python 3.8 execution')
class Python38ExecutionTests(unittest.TestCase):
    def test_single_file_import_and_recipe_round_trip_in_real_python38(self):
        executable = os.environ['MOTD_TEST_PYTHON38']
        program = (
            'import sys,json;sys.path.insert(0,sys.argv[1]);import motd;'
            'assert sys.version_info[:2]==(3,8);'
            'assert motd.tomllib.__version__=="2.3.2";'
            'c=motd.preset_config("workshop");'
            'assert motd.validate_config(motd.tomllib.loads(motd.dump_config(c)))==c;'
            'print(json.dumps({"python":sys.version,"parser":motd.tomllib.__version__}))'
        )
        result = subprocess.run([executable, '-c', program, str(ROOT)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['parser'], '2.3.2')


if __name__ == '__main__':
    unittest.main()
