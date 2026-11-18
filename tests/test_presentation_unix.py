"""Cross-axis geometry, safe text, semantic colours and preset equivalence."""
import copy
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd

ANSI = re.compile(r'\x1b\[[0-9;]*m')


class PresentationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = patch.multiple(motd, **{
            kind + '_TEMPLATE': (ROOT / 'runtime' / name).read_text()
            for kind, name in [('DESIGNS', 'designs.sh'), ('BASH', 'motd.bash'), ('SH', 'motd.sh')]})
        cls.templates.start(); cls.addClassCleanup(cls.templates.stop)

    def execute(self, config, cols=80, rows=50, extra=(), mutate=None):
        with tempfile.NamedTemporaryFile('w', suffix='.' + config['shell']) as stream:
            text = motd.generate_artifact(config)
            stream.write(mutate(text) if mutate else text); stream.flush()
            env = dict(os.environ, TERM='xterm-256color', LC_ALL='C.UTF-8')
            env.pop('NO_COLOR', None)
            result = subprocess.run([config['shell'], stream.name, '--demo-alerts',
                '--width', str(cols), '--rows', str(rows), *extra],
                capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        plain = ANSI.sub('', result.stdout)
        self.assertLessEqual(len(plain.splitlines()), rows - 1, plain)
        for line in plain.splitlines(): self.assertLessEqual(len(line), cols, repr(line))
        return result.stdout

    def config(self, shell='bash', **settings):
        c = motd.preset_config(shell=shell)
        c['display'].update(color='always', charset='unicode', **settings)
        return c

    def test_named_designs_are_exactly_resolved_settings_of_classic(self):
        for shell in ('bash', 'sh'):
            for design, (layout, frame, heading) in motd.DESIGN_POLICIES.items():
                named = self.config(shell, design=design)
                explicit = copy.deepcopy(named)
                explicit['display'].update(design='classic', panel_layout=layout,
                    panel_frame=frame, heading_style=heading)
                with self.subTest(shell=shell, design=design):
                    self.assertEqual(self.execute(named), self.execute(explicit))

    def test_border_family_changes_only_glyphs_not_data_or_semantic_colours(self):
        translation = str.maketrans({char: '|' for char in '│║┃'})
        def body(text):
            return [line.translate(translation) for line in text.splitlines()
                    if ANSI.sub('', line).startswith(('│', '║', '┃'))]
        c = self.config()
        baseline = self.execute(c)
        self.assertIn('\x1b[35m', baseline)  # compression role
        self.assertIn('\x1b[32mRUN', baseline)  # service state
        self.assertIn('\x1b[1;35m', baseline)  # resident-memory rank
        for border in ('rounded', 'double', 'heavy'):
            c['display']['border_style'] = border
            self.assertEqual(body(baseline), body(self.execute(c)))

    def test_requested_sizes_accept_independent_axis_combinations(self):
        rng = random.Random(20261118)
        options = motd.PRESENTATION_OPTIONS
        for shell in ('bash', 'sh'):
            for cols, rows in ((80, 25), (80, 50), (120, 50), (160, 50)):
                for _ in range(5):
                    settings = {key: rng.choice(choices) for key, choices in options.items()}
                    settings.update(density=rng.choice(('compact','balanced','comfortable')),
                        detail=rng.choice(motd.DETAILS), padding=rng.randrange(4),
                        section_gap=rng.randrange(3), section_notes={'resources': 'Measured capacity'},
                        section_titles={'attention': 'Attention'})
                    with self.subTest(shell=shell, size=(cols, rows), settings=settings):
                        self.execute(self.config(shell, **settings), cols, rows)

    def test_literal_titles_notes_and_independent_metadata_visibility(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / 'never-created'
            literal = '$(touch ' + str(sentinel) + ')'
            for shell in ('bash', 'sh'):
                c = self.config(shell, sections=['resources'], section_titles={'resources': 'Capacity'},
                    section_notes={'resources': literal}, separator_text='custom')
                output = self.execute(c, 160)
                self.assertIn('Capacity', output); self.assertIn(literal, output)
                self.assertFalse(sentinel.exists())
                c['display']['separator_text'] = 'none'
                hidden = self.execute(c, 160)
                self.assertNotIn(literal, hidden)
                self.assertIn('31.0Gi' if shell == 'bash' else '12582912', hidden)
                c['display']['section_titles']['resources'] = ''
                untitled = self.execute(c, 160)
                self.assertNotIn('Capacity', untitled)
                self.assertNotIn('resources', untitled)

    def test_config_rejects_unknown_keys_bad_enums_and_terminal_controls(self):
        for data in ({'heading_align':'execute'}, {'section_titles':{'root':'x'}},
                     {'section_notes':{'system':'bad\x1b[2J'}}, {'border_style':['double']}):
            with self.subTest(data=data), self.assertRaises(motd.MotdError):
                motd.validate_config({'display':data})

    def test_ascii_overrides_border_family(self):
        for shell in ('bash', 'sh'):
            c = self.config(shell, border_style='double')
            output = self.execute(c, extra=('--ascii','--plain'))
            self.assertTrue(output.isascii()); self.assertNotIn('\x1b',output)

    def test_required_services_and_all_process_rankings_survive_normal_detail(self):
        for shell in ('bash', 'sh'):
            for design in motd.DESIGNS:
                c = self.config(shell, design=design, sections=['services','processes'], detail='normal')
                c['services']['required'] = ['first-required.service','second-required.service',
                    'first-required.service','third-required.service']
                with self.subTest(shell=shell,design=design):
                    output = ANSI.sub('',self.execute(c,160))
                    for required in ('first-required','second-required','third-required'):
                        self.assertIn(required,output)
                    for metric in ('CPU','RSS','I/O'): self.assertIn(metric,output)

    def test_legacy_row_cap_still_bounds_customized_section(self):
        c = self.config(sections=['services'], border_style='rounded', detail='full')
        def inject(text):
            return text.replace('declare -A SECTION_VISIBLE=() SECTION_TITLE=() SECTION_ROWS=() ITEM_VISIBLE=()',
                'declare -A SECTION_VISIBLE=() SECTION_TITLE=() SECTION_ROWS=() ITEM_VISIBLE=()\nSECTION_ROWS[services]=2')
        output = ANSI.sub('',self.execute(c,80,50,mutate=inject))
        # Header/context + section heading + one allowed body row + bottom.
        self.assertEqual(len(output.splitlines()),5)
        self.assertIn('SERVICES',output)

    def test_default_classic_preserves_service_roles_rankings_and_block_bars(self):
        output = self.execute(self.config(),80,25)
        plain = ANSI.sub('',output)
        for observation in ('SSH','WEB','TFTP','OOM','DB','82.4%','12.8%','3.1%',
                            '1.3Gi','822Mi','608Mi','181Mi/s','122Mi/s','640Ki/s'):
            self.assertIn(observation,plain)
        self.assertIn('█',plain); self.assertIn('░',plain)
        self.assertIn('╔',plain); self.assertIn('│',plain)
        self.assertIn('+7 roles',plain)
        self.assertIn('8 TCP / 3 admin',plain)
        self.assertIn('systemctl --failed',plain)

    def test_overflow_applies_to_body_fields_as_well_as_titles(self):
        for shell in ('bash','sh'):
            c = self.config(shell, sections=['hints'], detail='full', separator_text='none')
            c['hints'] = [{'id':'long','label':'Long','command':'X'*100,'note':''}]
            marked = self.execute(c,40)
            c['display']['overflow']='clip'
            clipped = self.execute(c,40)
            self.assertTrue('...' in marked or '~' in marked)
            self.assertNotIn('...',clipped); self.assertNotIn('~',clipped)

    def test_overflow_marker_can_be_disabled_without_changing_layout(self):
        for shell in ('bash','sh'):
            c = self.config(shell, sections=['system'], section_titles={'system':'X'*100})
            marked = self.execute(c,80)
            c['display']['overflow']='clip'
            clipped = self.execute(c,80)
            self.assertEqual(len(marked.splitlines()),len(clipped.splitlines()))
            self.assertIn('~',marked); self.assertNotIn('~',clipped)


if __name__ == '__main__': unittest.main()
