"""Public CLI actually reaches the shared presentation schema and serializer."""
import unittest
import motd


class PresentationCliTests(unittest.TestCase):
    def test_independent_cli_axes_round_trip_into_generated_recipe(self):
        args = motd.parser().parse_args(['build', '--output', 'unused.bash',
            '--design', 'classic', '--theme', 'green', '--panel-layout', 'columns',
            '--panel-frame', 'separate', '--border-style', 'rounded', '--heading-style', 'rule',
            '--heading-align', 'right', '--separator-text', 'custom', '--label-style', 'short',
            '--overflow', 'clip', '--section-title', 'resources=Capacity $(literal)',
            '--section-note', 'resources=Keep `backticks` literal'])
        config, artifact = motd.resolve_input(args)
        recovered = motd.extract_config(artifact)
        self.assertEqual(config, recovered)
        self.assertEqual(config['display']['theme'], 'green')
        self.assertEqual(config['display']['panel_layout'], 'columns')
        self.assertEqual(config['display']['section_titles']['resources'], 'Capacity $(literal)')
        self.assertEqual(config['display']['section_notes']['resources'], 'Keep `backticks` literal')
        self.assertEqual(config['display']['detail'], motd.preset_config()['display']['detail'])

    def test_every_registered_enum_has_a_cli_argument(self):
        for name, choices in motd.PRESENTATION_OPTIONS.items():
            args = motd.parser().parse_args(['preview', '--' + name.replace('_', '-'), choices[-1]])
            config, _ = motd.resolve_input(args)
            self.assertEqual(config['display'][name], choices[-1])


if __name__ == '__main__': unittest.main()
