"""Configuration and generation contracts; no installation or host mutation."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


class GenerationTests(unittest.TestCase):
    def test_embedded_runtime_is_exact_tracked_template(self):
        expected = (ROOT / 'runtime' / 'motd.bash').read_text(encoding='utf-8')
        self.assertEqual(motd.BASH_TEMPLATE, expected)
        self.assertEqual(expected.count('# @MOTD_CONFIG@'), 1)

    def test_presets_are_independent_and_all_round_trip(self):
        for name in motd.PRESET_NAMES:
            with self.subTest(preset=name):
                config = motd.validate_config(motd.preset_config(name))
                encoded = motd.dump_config(config)
                self.assertEqual(motd.validate_config(tomllib.loads(encoded)), config)
                self.assertEqual(motd.dump_config(config), encoded)
                self.assertTrue(motd.generate_artifact(config))
        first = motd.preset_config('workshop')
        first['display']['sections'].clear()
        first['hooks']['before'].append({'argv': ['false']})
        self.assertTrue(motd.preset_config('workshop')['display']['sections'])
        self.assertEqual(motd.preset_config('workshop')['hooks']['before'], [])

    def test_nonempty_hooks_and_empty_hints_round_trip(self):
        config = motd.preset_config('home-lab')
        config['hints'] = []
        config['hooks'] = {
            'before': [{'argv': ['printf', '%s', 'before'], 'timeout_seconds': 0.2}],
            'after': [{'argv': ['printf', '%s', 'after'], 'on_failure': 'stop'}],
        }
        validated = motd.validate_config(config)
        self.assertEqual(motd.validate_config(tomllib.loads(motd.dump_config(config))), validated)
        self.assertEqual(motd.extract_config(motd.generate_artifact(config)), validated)

    def test_each_hook_phase_combination_has_valid_bash(self):
        with tempfile.TemporaryDirectory(prefix='motd-hook-syntax-') as tmp:
            path = Path(tmp) / 'generated.bash'
            for before, after in ((False, False), (True, False), (False, True), (True, True)):
                with self.subTest(before=before, after=after):
                    config = motd.preset_config()
                    config['hooks'] = {
                        'before': [{'argv': ['printf', 'before']}] if before else [],
                        'after': [{'argv': ['printf', 'after']}] if after else [],
                    }
                    path.write_text(motd.generate_artifact(config), encoding='utf-8')
                    result = subprocess.run(['bash', '-n', str(path)], capture_output=True,
                                            text=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_artifact_digest_and_embedded_recipe_are_exact(self):
        config = motd.validate_config(motd.preset_config('workshop'))
        artifact = motd.generate_artifact(config)
        self.assertEqual(artifact, motd.generate_artifact(config))
        self.assertTrue(artifact.startswith('#!/usr/bin/env bash\n'))
        self.assertEqual(artifact.count('# MOTD-BODY-BEGIN\n'), 1)
        body = artifact.split('# MOTD-BODY-BEGIN\n', 1)[1]
        digest = re.search(r'^# MOTD-BODY-SHA256: ([0-9a-f]{64})$', artifact, re.M)
        self.assertIsNotNone(digest)
        self.assertEqual(digest[1], hashlib.sha256(body.encode()).hexdigest())
        recipe = re.search(r'^# MOTD-CONFIG-BASE64: ([A-Za-z0-9+/=]+)$', artifact, re.M)
        self.assertIsNotNone(recipe)
        text = base64.b64decode(recipe[1], validate=True).decode()
        self.assertEqual(motd.validate_config(tomllib.loads(text)), config)
        self.assertEqual(motd.extract_config(artifact), config)

    def test_changed_body_cannot_silently_supply_configuration(self):
        artifact = motd.generate_artifact(motd.preset_config())
        with self.assertRaises(motd.MotdError):
            motd.extract_config(artifact + '\n# accidental local edit\n')

    def test_changed_recipe_cannot_silently_describe_unchanged_body(self):
        artifact = motd.generate_artifact(motd.preset_config())
        other = motd.preset_config('home-lab')
        encoded = base64.b64encode(motd.dump_config(other).encode()).decode()
        changed = re.sub(r'(?m)^# MOTD-CONFIG-BASE64: [A-Za-z0-9+/=]+$',
                         '# MOTD-CONFIG-BASE64: ' + encoded, artifact)
        with self.assertRaises(motd.MotdError):
            motd.extract_config(changed)

    def test_recovery_rejects_invalid_and_oversized_input(self):
        for artifact in ('#!/bin/bash\nprintf hello\n', '# MOTD-CONFIG-BASE64: !!!!\n',
                         'x' * (motd.MAX_ARTIFACT_BYTES + 1)):
            with self.subTest(size=len(artifact)), self.assertRaises(motd.MotdError):
                motd.extract_config(artifact)

    def test_non_numeric_and_out_of_range_settings_are_rejected(self):
        fields = [('display', 'width'), ('display', 'rows'), ('display', 'top_entries'),
                  ('collection', 'budget_ms'), ('collection', 'worker_ms'),
                  ('collection', 'process_limit'), ('collection', 'io_scan_ms')]
        for table, field in fields:
            for bad in (True, '25', '1+1', '$(touch SHOULD_NOT_EXIST)', 1.5, -1, 10**12):
                with self.subTest(field=f'{table}.{field}', value=bad):
                    config = motd.preset_config()
                    config[table][field] = bad
                    with self.assertRaises(motd.MotdError):
                        motd.validate_config(config)
        # The default section set needs at least twenty rows including framing.
        config = motd.preset_config()
        config['display']['rows'] = 18
        with self.assertRaises(motd.MotdError):
            motd.validate_config(config)

    def test_invalid_boolean_ids_and_text_are_rejected(self):
        cases = [
            {'display': {'show_swap': 'false'}},
            {'display': {'title': 'bad\x1b[2J'}},
            {'display': {'site': 'bad\nline'}},
            {'display': {'sections': ['system', 'system']}},
            {'display': {'sections': ['not-a-section']}},
            {'display': {'colour_typo': 'green'}},
            {'services': {'required': ['ssh.service; touch /tmp/nope']}},
            {'schema_version': True},
            {'name': '../../elsewhere'},
        ]
        for config in cases:
            with self.subTest(config=config), self.assertRaises(motd.MotdError):
                motd.validate_config(config)
        config = motd.preset_config()
        config['hints'][0]['command'] = 'ps | sort'
        with self.assertRaises(motd.MotdError):
            motd.validate_config(config)

    def test_strings_are_literal_bash_data(self):
        with tempfile.TemporaryDirectory(prefix='motd-generation-') as tmp:
            sentinel = Path(tmp) / 'injected'
            config = motd.preset_config()
            payload = f'$(touch {sentinel})'
            config['display']['title'] = payload
            config['display']['site'] = f'`touch {sentinel}`'
            config['messages'] = ["quotes ' \" ; " + payload]
            config['hints'][0]['command'] = payload
            path = Path(tmp) / 'generated.bash'
            path.write_text(motd.generate_artifact(config), encoding='utf-8')
            syntax = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True, timeout=5)
            self.assertEqual(syntax.returncode, 0, syntax.stderr)
            result = subprocess.run(['bash', str(path), '--demo', '--plain', '--width', '132', '--rows', '50'],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists(), 'Configuration text was executed')
            self.assertEqual(motd.extract_config(path.read_text()), motd.validate_config(config))

    def test_public_issue_escapes_backslashes_and_banner_preserves_them(self):
        config = motd.preset_config('public-console')
        config['display']['title'] = r'Console \h'
        config['public_text'] = 'Literal \\n and \\l; $HOME and $(id).\nSecond line.'
        plain = config['display']['title'] + '\n\n' + config['public_text'] + '\n'
        issue = motd.generate_artifact(config)
        self.assertEqual(issue, plain.replace('\\', '\\\\'))
        self.assertNotIn('#!/bin', issue)
        config['target'] = 'ssh-banner'
        self.assertEqual(motd.generate_artifact(config), plain)

    def test_public_presets_reject_executable_hooks(self):
        for target in ('issue', 'ssh-banner'):
            config = motd.preset_config('public-console')
            config['target'] = target
            config['hooks']['before'] = [{'argv': ['printf', 'private']}]
            with self.subTest(target=target), self.assertRaises(motd.MotdError):
                motd.generate_artifact(config)


if __name__ == '__main__':
    unittest.main()
