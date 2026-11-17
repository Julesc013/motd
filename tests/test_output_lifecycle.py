"""Every generated output must also survive export, archive and recovery.

These tests never execute generated scripts or use real startup files. They
exercise the public CLI and transaction lifecycle in private temporary paths,
including outputs whose generation used to succeed while their archive failed.
"""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import motd


@unittest.skipUnless(sys.platform.startswith('linux') and os.name == 'posix',
                     'Journalled export and installation require Linux')
class OutputLifecycleTests(unittest.TestCase):
    def test_each_output_builds_archives_and_rolls_back_with_its_recipe(self):
        cases = [('shell', shell) for shell in motd.SHELLS]
        cases += [(target, 'bash') for target in motd.TARGETS if target != 'shell']
        for target, shell in cases:
            with self.subTest(target=target, shell=shell), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                state = str(root / 'state')
                output = root / 'generated-output'
                recipe = root / 'recipe.toml'
                with redirect_stdout(io.StringIO()):
                    status = motd.main(['build', '--target', target, '--shell', shell,
                                        '--output', str(output), '--save-config', str(recipe),
                                        '--state-dir', state])
                self.assertEqual(status, 0)
                config = motd.load_config(recipe)
                artifact = output.read_text(encoding='utf-8')
                self.assertEqual(artifact, motd.generate_artifact(config))
                records = motd.tx_history(state)
                self.assertEqual(len(records), 1)
                record = records[0]
                archive = Path(record['archives']['artifact_text']['path'])
                self.assertEqual(archive.name, 'output' + motd.artifact_suffix(config))
                self.assertEqual(archive.read_bytes(), output.read_bytes())
                self.assertEqual(Path(record['archives']['config_toml']['path']).read_bytes(),
                                 recipe.read_bytes())
                if target == 'shell':
                    self.assertEqual(motd.extract_config(artifact), config)
                motd.tx_rollback(state, record['id'])
                self.assertFalse(output.exists())
                self.assertFalse(recipe.exists())
                # Rollback does not discard the archived output or its recipe.
                self.assertEqual(archive.read_text(encoding='utf-8'), artifact)

    def test_fish_install_upgrade_repair_and_uninstall_preserve_unowned_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            state = str(root / 'state')
            output = root / 'greeting.fish'
            startup = root / 'config.fish'
            original = '# Existing Fish configuration\nset -g existing_setting yes\n'
            startup.write_text(original, encoding='utf-8')
            config = motd.preset_config(shell='fish')
            first_artifact = motd.generate_artifact(config)

            def plan(artifact):
                return motd.installation_plan(config, artifact, destination=str(output),
                                              shell_file=str(startup), state_dir=state)

            proposed = plan(first_artifact)
            self.assertFalse(output.exists())
            self.assertFalse(Path(state).exists())
            first = motd.tx_apply(proposed)
            self.assertEqual(Path(first['archives']['artifact_text']['path']).suffix, '.fish')
            self.assertEqual(motd.tx_apply(plan(first_artifact))['status'], 'noop')

            external = '# Kept after upgrade and removal\n'
            startup.write_text(startup.read_text(encoding='utf-8') + external, encoding='utf-8')
            config['display']['title'] = 'Updated Fish greeting'
            upgraded_artifact = motd.generate_artifact(config)
            motd.tx_apply(plan(upgraded_artifact))
            self.assertEqual(output.read_text(encoding='utf-8'), upgraded_artifact)
            output.unlink()
            motd.tx_apply(motd.repair_installation_plan(config['name'], state))
            self.assertEqual(output.read_text(encoding='utf-8'), upgraded_artifact)

            motd.tx_apply(motd.uninstall_plan(config['name'], state))
            self.assertFalse(output.exists())
            self.assertEqual(startup.read_text(encoding='utf-8'), original + external)
            self.assertEqual(motd.active_installs(state), {})

    def test_archive_suffix_cannot_introduce_an_unregistered_path(self):
        for suffix in ('../../outside', '.fish/../../outside', '.exe', [], None):
            with self.subTest(suffix=suffix), self.assertRaises(motd.TxError) as caught:
                motd._tx_metadata({'artifact_suffix': suffix})
            self.assertEqual(caught.exception.code, 'invalid_metadata')


if __name__ == '__main__':
    unittest.main()
