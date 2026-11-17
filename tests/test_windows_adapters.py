"""Native CMD and cross-platform export checks; temporary files only."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import motd


class AdapterGenerationTests(unittest.TestCase):
    def test_fish_and_cmd_recover_the_exact_recipe(self):
        for shell in ('fish', 'cmd'):
            with self.subTest(shell=shell):
                config = motd.preset_config(shell=shell)
                config['display'].update(design='cards', density='comfortable',
                                         section_detail={'resources': 'full'})
                config['messages'] = ["Literal ' quote, \\ slash, $variable and β"]
                artifact = motd.generate_artifact(config)
                self.assertEqual(motd.extract_config(artifact), motd.validate_config(config))

    def test_cmd_recipe_is_after_the_batch_exit_not_a_command_length_hazard(self):
        config = motd.preset_config(shell='cmd')
        config['messages'] = ['x' * 500] * 24
        artifact = motd.generate_artifact(config)
        before, payload = artifact.split('# MOTD-POWERSHELL-BEGIN\n', 1)
        self.assertNotIn('# MOTD-CONFIG-BASE64:', before)
        self.assertIn('# MOTD-CONFIG-BASE64:', payload)
        self.assertLess(max(map(len, before.splitlines())), 2000)
        self.assertEqual(motd.extract_config(artifact), motd.validate_config(config))

    def test_native_batch_notice_refuses_ambiguous_unicode_code_pages(self):
        config = motd.preset_config('public-console')
        config['target'] = 'batch-text'
        config['public_text'] = 'Unicode β'
        with self.assertRaisesRegex(motd.MotdError, 'ASCII'):
            motd.generate_artifact(config)

    def test_create_only_cli_build_and_recover_do_not_create_install_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            output = root / 'message.cmd'; recipe = root / 'recipe.toml'
            recovered = root / 'recovered.toml'; state = root / 'state'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(motd.main(['build', '--shell', 'cmd', '--design', 'ledger',
                    '--output', str(output), '--save-config', str(recipe), '--create-only',
                    '--state-dir', str(state)]), 0)
                self.assertEqual(motd.main(['config', '--artifact', str(output), '--output', str(recovered),
                    '--create-only', '--state-dir', str(state)]), 0)
            self.assertEqual(motd.load_config(recipe), motd.load_config(recovered))
            self.assertEqual(motd.load_config(recipe)['display']['design'], 'ledger')
            self.assertTrue(Path(str(output) + '.export.json').is_file())
            self.assertFalse(state.exists())


@unittest.skipUnless(os.name == 'nt' and shutil.which('cmd'), 'Requires native Windows cmd.exe')
class NativeWindowsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='motd-cmd-native-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def execute(self, path, config=None):
        config = config or motd.preset_config(shell='cmd')
        environment = motd.preview_environment(config, path)
        environment['MOTD_ATTACK'] = 'this-must-not-replace-the-filename'
        command = motd.preview_command(config, path, width=40, rows=25, color=False)
        return subprocess.run(command, env=environment, capture_output=True,
                              encoding='utf-8', errors='replace', timeout=30)

    def test_cmd_launcher_runs_embedded_renderer_at_requested_geometry(self):
        config = motd.preset_config(shell='cmd')
        config['display']['design'] = 'dashboard'
        path = self.root / 'dashboard.cmd'; path.write_bytes(motd.generate_artifact(config).encode('utf-8'))
        result = self.execute(path, config)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = result.stdout.splitlines()
        self.assertTrue(rows)
        self.assertLessEqual(len(rows), 24)
        self.assertTrue(all(len(row) <= 40 for row in rows), result.stdout)
        self.assertIn('WORKSHOP', result.stdout)

    def test_cmd_filename_metacharacters_are_data(self):
        config = motd.preset_config(shell='cmd')
        path = self.root / "file %MOTD_ATTACK% ! & ^ ' space.cmd"
        path.write_bytes(motd.generate_artifact(config).encode('utf-8'))
        result = self.execute(path, config)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('WORKSHOP', result.stdout)

    def test_cmd_demo_suppresses_configured_hooks(self):
        config = motd.preset_config(shell='cmd')
        marker = self.root / 'must-not-exist.txt'
        config['hooks']['before'] = [{'argv': [sys.executable, '-c',
            'from pathlib import Path; Path(' + repr(str(marker)) + ').write_text("bad")']}]
        path = self.root / 'guarded.cmd'; path.write_bytes(motd.generate_artifact(config).encode('utf-8'))
        result = self.execute(path, config)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists())

    def test_batch_text_prints_metacharacters_literally_without_powershell(self):
        config = motd.preset_config('public-console')
        config['target'] = 'batch-text'
        config['public_text'] = 'A&B | <x> ^ %PATH% ! (ok) "quoted&text"'
        path = self.root / 'literal.cmd'
        path.write_bytes(motd.generate_artifact(config).encode('ascii'))
        result = self.execute(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(config['public_text'], result.stdout)

    def test_default_windows_export_uses_create_only_manifest(self):
        output = self.root / 'export.ps1'; state = self.root / 'state'
        with redirect_stdout(io.StringIO()):
            self.assertEqual(motd.main(['build', '--shell', 'powershell', '--output', str(output),
                                       '--state-dir', str(state)]), 0)
        manifest = json.loads(Path(str(output) + '.export.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['format'], 'motd-create-only-export-v1')
        self.assertFalse(state.exists())
        with self.assertRaises(motd.MotdError), redirect_stdout(io.StringIO()):
            motd.main(['build', '--shell', 'powershell', '--output', str(output), '--replace'])


if __name__ == '__main__':
    unittest.main()
