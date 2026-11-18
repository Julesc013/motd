"""Evidence contracts for independent settings and the seeded showcase."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(importlib.util.find_spec(name) for name in ('PIL', 'wcwidth'))
if AVAILABLE:
    for name, filename in [('gallery_custom', 'build_gallery.py'), ('showcase_custom', 'build_showcase.py')]:
        spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / filename)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    gallery = sys.modules['gallery_custom']; showcase = sys.modules['showcase_custom']


@unittest.skipUnless(AVAILABLE, 'Gallery checks need Pillow and wcwidth')
class CustomGalleryTests(unittest.TestCase):
    def test_every_axis_has_requested_sizes_and_only_changes_its_declared_setting(self):
        cases = gallery.axis_sampler_specs()
        self.assertEqual(len({gallery.case_identifier(c) for c in cases}), len(cases))
        axes = {c['axis'] for c in cases}
        self.assertGreaterEqual(len(axes), 28)
        for axis in axes:
            selected = [c for c in cases if c['axis'] == axis]
            self.assertEqual({c['geometry'] for c in selected}, set(gallery.PRESENTATION_SIZES))
            for case in selected:
                delta = {k: v for k, v in case['display_patch'].items() if case['baseline'].get(k) != v}
                self.assertLessEqual(set(delta), {axis})
                config = gallery.motd.preset_config(); config['display'].update(case['display_patch'])
                gallery.motd.validate_config(config)

    def test_combinations_use_classic_and_independent_policies(self):
        cases = gallery.composition_sampler_specs()
        self.assertEqual(len(cases), 48)
        self.assertTrue(all(c['display_patch']['design'] == 'classic' for c in cases))
        self.assertEqual(len({c['variant'] for c in cases}), 12)
        for case in cases:
            config = gallery.motd.preset_config(); config['display'].update(case['display_patch'])
            gallery.motd.validate_config(config)

    def test_showcase_seed_is_reproducible_and_duplicates_do_not_pad_the_count(self):
        cases = [{'id': f'{size}-{i}', 'size': size, 'axis': 'axis-' + str(i % 7),
                  'rgba_sha256': f'{size}-{i // 2}'} for size in showcase.SIZES for i in range(50)]
        a = showcase.choose(cases, 20261118, 16); b = showcase.choose(cases, 20261118, 16)
        self.assertEqual(a, b); self.assertEqual(len(a), 64)
        for size in showcase.SIZES:
            self.assertEqual(len({c['rgba_sha256'] for c in a if c['size'] == size}), 16)
        with self.assertRaisesRegex(ValueError, 'Not enough distinct'):
            showcase.choose(cases[:1], 1, 16)


if __name__ == '__main__': unittest.main()
