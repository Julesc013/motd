"""Readability preferences, safe imports and CLI recipe preservation."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import motd


class DesignConfigurationTests(unittest.TestCase):
    def test_design_preferences_survive_toml_and_all_executable_exports(self):
        config = motd.preset_config()
        config['display'].update(design='briefing', density='comfortable', detail='brief', padding=2,
                                 section_gap=1, color_emphasis='quiet', priority=['attention', 'io'],
                                 section_detail={'resources': 'full', 'services': 'normal'})
        for shell in motd.SHELLS:
            with self.subTest(shell=shell):
                config['shell'] = shell
                expected = motd.validate_config(config)
                self.assertEqual(motd.validate_config(motd.tomllib.loads(motd.dump_config(config))), expected)
                self.assertEqual(motd.extract_config(motd.generate_artifact(config)), expected)

    def test_legacy_recipe_gets_classic_defaults_without_inventing_a_new_design(self):
        config = motd.validate_config({'preset': 'home-lab', 'display': {'theme': 'amber'}})
        self.assertEqual(config['display']['design'], 'classic')
        self.assertEqual(config['display']['theme'], 'amber')
        self.assertEqual(config['display']['section_detail'], {})

    def test_invalid_layout_data_is_rejected_before_literal_serialization(self):
        cases = [{'padding': '1+$(touch bad)'}, {'section_gap': True}, {'design': 'missing'},
                 {'priority': ['attention', 'attention']}, {'priority': ['not-a-section']},
                 {'section_detail': {'resources': 'execute'}}, {'section_detail': {'missing': 'full'}}]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(motd.MotdError):
                motd.validate_config({'display': case})

    def test_cli_readability_choices_are_saved_and_recovered(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); artifact = root / 'message.sh'; recipe = root / 'recipe.toml'
            with redirect_stdout(io.StringIO()):
                motd.main(['build', '--shell', 'sh', '--design', 'ledger', '--density', 'compact',
                    '--detail', 'brief', '--section-detail', 'resources=full', '--priority', 'attention,resources',
                    '--padding', '0', '--section-gap', '1', '--rows', '15', '--color-emphasis', 'quiet',
                    '--output', str(artifact), '--save-config', str(recipe), '--create-only'])
            config = motd.load_config(recipe)
            self.assertEqual(config['display']['section_detail'], {'resources': 'full'})
            self.assertEqual(config['display']['rows'], 15)
            self.assertEqual(config['display']['design'], 'ledger')
            self.assertEqual(motd.extract_config(artifact.read_text()), config)

    def test_opaque_shell_import_does_not_guess_bash(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'unknown'; source.write_text('Write-Output "hello"\n')
            args = motd.parser().parse_args(['build', '--artifact', str(source), '--target', 'shell', '--output', '-'])
            with self.assertRaisesRegex(motd.MotdError, '--shell'):
                motd.resolve_input(args)

    def test_imported_artifact_cannot_be_relabelled_as_a_different_design(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'message.sh'; source.write_text(motd.generate_artifact(motd.preset_config(shell='sh')))
            args = motd.parser().parse_args(['build', '--artifact', str(source), '--design', 'cards', '--output', '-'])
            with self.assertRaisesRegex(motd.MotdError, 'Recover the recipe'):
                motd.resolve_input(args)

    def test_oversized_input_is_refused_before_opening_its_content(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'oversized'
            with source.open('wb') as stream: stream.truncate(motd.MAX_ARTIFACT_BYTES + 1)
            with patch.object(motd.os, 'open', side_effect=AssertionError('Content was opened')):
                with self.assertRaisesRegex(motd.MotdError, '2 MB'):
                    motd._source_text(source)


if __name__ == '__main__':
    unittest.main()
