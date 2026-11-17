"""Terminal capture and lossless gallery contracts; no login files are touched."""
from __future__ import annotations

import importlib.util
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = all(importlib.util.find_spec(name) for name in ('PIL', 'wcwidth'))
if DEPENDENCIES and os.name == 'posix':
    spec = importlib.util.spec_from_file_location('motd_gallery', ROOT/'tools/build_gallery.py')
    gallery = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = gallery
    spec.loader.exec_module(gallery)


@unittest.skipUnless(DEPENDENCIES and os.name == 'posix', 'Gallery developer checks need Pillow, wcwidth and POSIX PTYs')
class GalleryTests(unittest.TestCase):
    def test_bounded_sampler_covers_designs_geometries_and_independent_preferences(self):
        cases = gallery.design_sampler_specs()
        self.assertEqual(len(cases), 140)
        self.assertEqual(len({gallery.case_identifier(c) for c in cases}), 140)
        for design in gallery.DESIGNS:
            selected = [c for c in cases if c['design'] == design]
            structure = [c for c in selected if c['sample_group'] == 'structure']
            self.assertEqual(len(structure), 24)
            self.assertEqual({c['geometry'] for c in structure}, set(gallery.SIZES))
            self.assertEqual({c['shell'] for c in structure}, {'bash', 'sh', 'powershell'})
            self.assertEqual({c['preset'] for c in structure}, set(gallery.PRESETS))
            contrasts = [c for c in selected if c['sample_group'] == 'density-at-full-detail']
            self.assertEqual({c['density'] for c in contrasts}, set(gallery.DENSITIES))
            self.assertTrue(all(c['detail'] == 'full' and c['geometry'] == (80, 50) for c in contrasts))
            self.assertEqual({c['detail'] for c in selected}, set(gallery.DETAILS))

    def test_shared_presentation_source_is_in_provenance(self):
        sources = gallery.source_hashes()
        self.assertIn('runtime/designs.sh', sources)
        self.assertEqual(sources['runtime/designs.sh'], gallery.digest((ROOT/'runtime/designs.sh').read_bytes()))

    def test_ansi_styles_and_wide_combining_characters_map_to_cells(self):
        grid = gallery.TerminalGrid(10, 4).feed('\x1b[?1h\x1b=\x1b[1;32mA\x1b[0m\u754cE\u0301\r\nplain\r\n')
        self.assertEqual(grid.cells[0][0].fg, gallery.PALETTE[2])
        self.assertTrue(grid.cells[0][0].bold)
        self.assertEqual(grid.cells[0][1].text, '\u754c')
        self.assertTrue(grid.cells[0][2].continuation)
        self.assertEqual(grid.cells[0][3].text, 'E\u0301')
        self.assertEqual(grid.highest_row + 1, 2)
        self.assertEqual(grid.max_columns, 5)
        self.assertEqual(len(grid.cells), 4)
        self.assertEqual(len(grid.cells[-1]), 10)

    def test_wrapping_scrolling_prompt_overwrite_and_unknown_controls_fail(self):
        cases = [('123456', 5, 4), ('a\nb\nc', 5, 3), ('\n\n\n', 5, 3),
                 ('\x1b[2J', 5, 4), ('\x1b]0;title\x07', 5, 4), ('a\x07', 5, 4)]
        for text, width, height in cases:
            with self.subTest(text=repr(text)), self.assertRaises(gallery.GalleryError):
                gallery.TerminalGrid(width, height).feed(text)

    def test_exact_width_followed_by_newline_does_not_wrap(self):
        grid = gallery.TerminalGrid(5, 3).feed('12345\r\nabcde\r\n')
        self.assertEqual(grid.highest_row + 1, 2)
        self.assertEqual(grid.y, 2)
        self.assertEqual(''.join(c.text for c in grid.cells[-1]), '     ')

    def test_full_screen_wizard_frame_uses_last_row_without_scrolling(self):
        grid = gallery.TerminalGrid(5, 3, reserve_prompt=False).feed('first\r\nnext\r\nlast')
        self.assertEqual(grid.highest_row + 1, 3)
        self.assertEqual(''.join(c.text for c in grid.cells[-1]), 'last ')
        with self.assertRaisesRegex(gallery.GalleryError, 'scroll'):
            grid.feed('\r\n')

    def test_actual_child_observes_requested_pty_geometry(self):
        for columns, rows in gallery.SIZES:
            raw, _ = gallery.capture_pty([sys.executable, '-c',
                'import os; s=os.get_terminal_size(1); print(str(s.columns)+"x"+str(s.lines))'], columns, rows)
            self.assertEqual(raw.decode().strip(), f'{columns}x{rows}')

    @unittest.skipUnless(shutil.which('bash'), 'Actual Bash renderer unavailable')
    def test_four_requested_sizes_fit_actual_bash_without_postprocessing(self):
        with tempfile.TemporaryDirectory(prefix='motd-gallery-test-') as folder:
            path = Path(folder)/'message.bash'
            config = gallery.motd.preset_config('workshop')
            path.write_text(gallery.motd.generate_artifact(config), encoding='utf-8')
            for columns, rows in gallery.SIZES:
                with self.subTest(columns=columns, rows=rows):
                    command = gallery.output_command('bash', shutil.which('bash'), path,
                                                     columns, rows, 'ascii', 'plain')
                    raw, _ = gallery.capture_pty(command, columns, rows)
                    grid = gallery.TerminalGrid(columns, rows).feed(raw.decode())
                    self.assertLessEqual(grid.highest_row + 1, rows - 1)
                    self.assertLessEqual(grid.max_columns, columns)
                    self.assertIn('ws-bench-07', grid.plain_text())
                    self.assertTrue(all(ord(c) < 128 for c in grid.plain_text()))

    @unittest.skipUnless(Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf').exists(), 'Gallery font unavailable')
    def test_png_decodes_to_every_original_pixel_with_complete_terminal_grid(self):
        renderer = gallery.Renderer()
        grid = gallery.TerminalGrid(40, 25).feed('\x1b[32mSynthetic preview\x1b[0m\r\n')
        image = renderer.image(grid)
        expected = gallery.rgba_digest(image)
        with tempfile.TemporaryDirectory(prefix='motd-png-test-') as folder:
            path = Path(folder)/'preview.png'
            result = gallery.save_lossless(image, path)
            self.assertEqual(result['rgba_sha256'], expected)
            self.assertEqual(result['pixels'], [48 + 40*renderer.cell_width,
                                                renderer.header + renderer.pad + 25*renderer.cell_height + renderer.footer])
            with gallery.Image.open(path) as decoded:
                self.assertEqual(gallery.rgba_digest(decoded), expected)
                blank_row = renderer.header + 24*renderer.cell_height
                self.assertEqual(decoded.getpixel((renderer.pad, blank_row)), gallery.rgb(gallery.BACKGROUND))

    @unittest.skipUnless(Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf').exists(), 'Gallery font unavailable')
    def test_optimizer_that_changes_pixels_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='motd-bad-optimizer-') as folder:
            folder = Path(folder); optimizer = folder/'bad-optimizer'
            optimizer.write_text('#!' + sys.executable + '\nimport sys\nfrom PIL import Image\np=sys.argv[-1]\ni=Image.open(p).convert("RGB");i.putpixel((0,0),(255,0,0));i.save(p)\n')
            optimizer.chmod(0o755)
            image = gallery.Image.new('RGB', (10, 10), 'black')
            with self.assertRaises(gallery.GalleryError):
                gallery.save_lossless(image, folder/'image.png', optimizer=str(optimizer))

    @unittest.skipUnless(shutil.which('bash') and Path(gallery.DEFAULT_FONT if DEPENDENCIES and os.name == 'posix' else '/missing').exists(), 'Bash and gallery font unavailable')
    def test_manifest_verification_checks_retained_recipe_transcript_and_image(self):
        with tempfile.TemporaryDirectory(prefix='motd-gallery-evidence-') as folder:
            with contextlib.redirect_stdout(io.StringIO()):
                manifest = gallery.main(['--output', folder, '--presets', 'workshop', '--shells', 'bash',
                    '--themes', 'cyan', '--charsets', 'ascii', '--colours', 'plain', '--sizes', '40x25',
                    '--no-static', '--no-comparisons'])
                verified = gallery.verify_gallery(folder)
            self.assertEqual(verified['verified_logical_cases'], 1)
            with self.assertRaises(gallery.GalleryError):
                gallery.verify_gallery(folder, require_full=True)
            with self.assertRaises(gallery.GalleryError):
                gallery.verify_gallery(folder, require_sampler=True)
            case = manifest['cases'][0]
            self.assertEqual((case['design'], case['density'], case['detail']), gallery.DEFAULT_PRESENTATION)
            transcript = Path(folder)/case['transcript']
            original = transcript.read_bytes()
            transcript.write_bytes(original + b'tampered\r\n')
            with self.assertRaisesRegex(gallery.GalleryError, 'Transcript hash mismatch'):
                gallery.verify_gallery(folder)
            transcript.write_bytes(original)
            recipe = Path(folder)/case['recipe']
            recipe.write_text(recipe.read_text() + '\n# changed\n')
            with self.assertRaisesRegex(gallery.GalleryError, 'Recipe or generated-source mismatch'):
                gallery.verify_gallery(folder)


if __name__ == '__main__': unittest.main()
