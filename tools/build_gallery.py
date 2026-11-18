#!/usr/bin/env python3
"""Capture actual MOTD terminal output and publish a lossless PNG gallery.

The classic matrix has 512 shell cases: two presets, four interpreters, four
themes, two character modes, two colour modes, and four real PTY sizes. A bounded
design sampler covers presentation choices separately. Identical rendered pixels
share one PNG, while every logical case keeps its transcript and recipe.

Build dependencies: Python, Pillow, wcwidth, the chosen interpreters, and optional
oxipng. These are developer/gallery dependencies, never login dependencies.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import errno
import fcntl
import hashlib
import html
import io
import itertools
import json
import os
from pathlib import Path
import platform
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import zipfile
from dataclasses import dataclass, asdict

from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION
from wcwidth import wcwidth, __version__ as WCWIDTH_VERSION

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd

SIZES = ((40, 25), (40, 50), (80, 25), (80, 50))
PRESENTATION_SIZES = ((80, 25), (80, 50), (120, 50), (160, 50))
PRESETS = ('workshop', 'home-lab')
SHELLS = ('bash', 'zsh', 'sh', 'powershell')
THEMES = ('cyan', 'green', 'amber', 'mono')
CHARSETS = ('ascii', 'unicode')
COLOURS = ('colour', 'plain')
DESIGNS = ('classic', 'cards', 'ledger', 'briefing', 'dashboard')
DENSITIES = ('compact', 'balanced', 'comfortable')
DETAILS = ('brief', 'normal', 'full')
BAR_LAYOUTS = ('inline', 'wide')
DEFAULT_PRESENTATION = ('classic', 'balanced', 'normal')
PALETTE = ('#171d2b', '#ed6a73', '#74d19b', '#edce77', '#76a9fa', '#c19deb', '#63d1df', '#e4e9f0',
           '#8390a3', '#ff8590', '#9beaaf', '#ffe599', '#9bc2ff', '#d7b5ff', '#8ae5ef', '#ffffff')
BACKGROUND = '#111827'
FOREGROUND = PALETTE[7]
DEFAULT_FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
CSI = re.compile(r'\x1b\[([?0-9;]*)([@-~])')


class GalleryError(Exception):
    """A missing runtime, bad capture, layout overflow or changed pixel image."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rgb(colour):
    return tuple(bytes.fromhex(colour.lstrip('#')))


@dataclass(frozen=True)
class Cell:
    text: str = ' '
    fg: str = FOREGROUND
    bg: str = BACKGROUND
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False
    continuation: bool = False


class TerminalGrid:
    """Strict terminal-cell decoder for the renderer's emitted control set.

    SGR, CR/LF, tabs, backspace and harmless keypad/cursor visibility modes are
    understood. Unknown sequences and any automatic wrap/scroll are errors. A
    preview must demonstrate a fitting layout, not silently crop an overflow.
    """
    def __init__(self, columns, rows, *, reserve_prompt=True):
        self.columns, self.rows = columns, rows
        self.reserve_prompt = reserve_prompt
        self.cells = [[Cell() for _ in range(columns)] for _ in range(rows)]
        self.x = self.y = 0
        self.highest_row = -1
        self.max_columns = 0
        self.style = dict(fg=FOREGROUND, bg=BACKGROUND, bold=False, dim=False,
                          italic=False, underline=False, reverse=False)
        self.ignored_modes = []

    @staticmethod
    def indexed_colour(index):
        if not 0 <= index <= 255: raise GalleryError('Invalid indexed colour')
        if index < 16: return PALETTE[index]
        if index >= 232:
            value = 8 + (index - 232) * 10
            return '#{0:02x}{0:02x}{0:02x}'.format(value)
        value = index - 16; levels = (0, 95, 135, 175, 215, 255)
        return '#%02x%02x%02x' % (levels[value // 36], levels[(value // 6) % 6], levels[value % 6])

    def sgr(self, raw):
        codes = [int(x or 0) for x in raw.split(';')]; i = 0
        while i < len(codes):
            code = codes[i]; i += 1
            if code == 0:
                self.style.update(fg=FOREGROUND, bg=BACKGROUND, bold=False, dim=False,
                                  italic=False, underline=False, reverse=False)
            elif code == 1: self.style['bold'] = True
            elif code == 2: self.style['dim'] = True
            elif code == 3: self.style['italic'] = True
            elif code == 4: self.style['underline'] = True
            elif code == 7: self.style['reverse'] = True
            elif code == 22: self.style.update(bold=False, dim=False)
            elif code == 23: self.style['italic'] = False
            elif code == 24: self.style['underline'] = False
            elif code == 27: self.style['reverse'] = False
            elif code == 39: self.style['fg'] = FOREGROUND
            elif code == 49: self.style['bg'] = BACKGROUND
            elif 30 <= code <= 37: self.style['fg'] = PALETTE[code - 30]
            elif 40 <= code <= 47: self.style['bg'] = PALETTE[code - 40]
            elif 90 <= code <= 97: self.style['fg'] = PALETTE[code - 90 + 8]
            elif 100 <= code <= 107: self.style['bg'] = PALETTE[code - 100 + 8]
            elif code in (38, 48):
                key = 'fg' if code == 38 else 'bg'
                if i + 1 < len(codes) and codes[i] == 5:
                    self.style[key] = self.indexed_colour(codes[i + 1]); i += 2
                elif i + 3 < len(codes) and codes[i] == 2:
                    channels = codes[i + 1:i + 4]
                    if any(not 0 <= c <= 255 for c in channels): raise GalleryError('Invalid true colour')
                    self.style[key] = '#%02x%02x%02x' % tuple(channels); i += 4
                else: raise GalleryError('Incomplete SGR colour')
            else: raise GalleryError(f'Unsupported SGR code {code}')

    def put(self, character):
        width = wcwidth(character)
        if width < 0: raise GalleryError(f'Unsupported control character U+{ord(character):04X}')
        if width == 0:
            if self.x == 0: raise GalleryError('Combining character without a preceding cell')
            column = self.x - 1
            while column and self.cells[self.y][column].continuation: column -= 1
            old = asdict(self.cells[self.y][column]); old['text'] += character
            self.cells[self.y][column] = Cell(**old)
            return
        if self.y >= self.rows - int(self.reserve_prompt):
            reason = f'row {self.rows} is reserved for the prompt' if self.reserve_prompt else 'outside the terminal'
            raise GalleryError(f'Output reaches row {self.y + 1}; {reason}')
        if self.x + width > self.columns:
            raise GalleryError(f'Output would wrap at row {self.y + 1}, column {self.x + width} (limit {self.columns})')
        self.cells[self.y][self.x] = Cell(character, **self.style)
        if width == 2: self.cells[self.y][self.x + 1] = Cell('', continuation=True, **self.style)
        self.x += width
        self.highest_row = max(self.highest_row, self.y)
        self.max_columns = max(self.max_columns, self.x)

    def feed(self, text):
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\x1b':
                match = CSI.match(text, i)
                if match:
                    params, final = match.groups()
                    if final == 'm' and not params.startswith('?'): self.sgr(params)
                    elif final in ('h', 'l') and params in ('?1', '?25'):
                        self.ignored_modes.append(match[0])
                    else: raise GalleryError(f'Unsupported terminal sequence {match[0]!r}')
                    i = match.end(); continue
                if text[i:i + 2] in ('\x1b=', '\x1b>'):
                    self.ignored_modes.append(text[i:i + 2]); i += 2; continue
                raise GalleryError(f'Unsupported escape sequence near {text[i:i + 24]!r}')
            if ch == '\r': self.x = 0
            elif ch == '\n':
                self.y += 1; self.x = 0
                if self.y >= self.rows: raise GalleryError('Output would scroll the terminal')
            elif ch == '\t':
                for _ in range(8 - self.x % 8): self.put(' ')
            elif ch == '\b': self.x = max(0, self.x - 1)
            else: self.put(ch)
            i += 1
        return self

    def fingerprint(self):
        serial = [[asdict(cell) for cell in row] for row in self.cells]
        return digest(json.dumps(serial, ensure_ascii=False, separators=(',', ':')).encode())

    def plain_text(self):
        return '\n'.join(''.join(c.text for c in row if not c.continuation).rstrip() for row in self.cells)


def capture_pty(command, columns, rows, *, timeout=12, cwd=None):
    """Run an actual child in a sized controlling PTY; capture output verbatim."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))
    settings = termios.tcgetattr(slave); settings[3] &= ~(termios.ECHO | termios.ECHONL)
    termios.tcsetattr(slave, termios.TCSANOW, settings)
    env = os.environ.copy()
    env.update(TERM='xterm-256color', COLUMNS=str(columns), LINES=str(rows), LANG='C.UTF-8', LC_ALL='C.UTF-8')
    env.pop('NO_COLOR', None)

    def controlling_terminal():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    chunks = []; process = None; start = time.monotonic()
    with tempfile.TemporaryFile() as error_stream:
        try:
            process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=error_stream,
                                       env=env, cwd=cwd, preexec_fn=controlling_terminal)
            os.close(slave); slave = None
            while True:
                if time.monotonic() - start > timeout:
                    os.killpg(process.pid, signal.SIGKILL)
                    raise GalleryError(f'Capture exceeded {timeout}s: {command[0]}')
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try: chunk = os.read(master, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO: break
                        raise
                    if not chunk: break
                    chunks.append(chunk)
                    if sum(map(len, chunks)) > 2_000_000: raise GalleryError('Unexpectedly large terminal output')
                elif process.poll() is not None: break
            process.wait(timeout=2)
            error_stream.seek(0); stderr = error_stream.read()
            if process.returncode or stderr:
                raise GalleryError(f'Capture failed ({process.returncode}): {stderr.decode(errors="replace")[:1000]}')
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=2)
            os.close(master)
            if slave is not None: os.close(slave)
    return b''.join(chunks), round(time.monotonic() - start, 4)


def output_command(shell, interpreter, artifact, columns, rows, charset, colour):
    if shell == 'powershell':
        command = [interpreter, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(artifact),
                   '-Demo', '-NoHooks', '-Width', str(columns), '-Rows', str(rows)]
        command.append('-Ascii' if charset == 'ascii' else '-Unicode')
        command.append('-Plain' if colour == 'plain' else '-Color')
    else:
        command = [interpreter, str(artifact), '--demo', '--width', str(columns), '--rows', str(rows)]
        command.append('--ascii' if charset == 'ascii' else '--unicode')
        if colour == 'plain': command.append('--plain')
        elif shell == 'sh': command.append('--color')
    return command


class Renderer:
    """A fixed two-times-resolution terminal raster; never resize for compression."""
    def __init__(self, font=DEFAULT_FONT, *, font_size=30):
        self.path = Path(font)
        if not self.path.is_file(): raise GalleryError('Choose an installed monospace --font')
        self.font_size = font_size
        self.fonts = {(False, False): ImageFont.truetype(str(self.path), font_size)}
        for key, suffix in [((True, False), '-Bold'), ((False, True), '-Oblique'), ((True, True), '-BoldOblique')]:
            candidate = self.path.with_name(self.path.stem + suffix + self.path.suffix)
            self.fonts[key] = ImageFont.truetype(str(candidate if candidate.exists() else self.path), font_size)
        self.small = ImageFont.truetype(str(self.path), 18)
        self.cell_width = round(self.fonts[(False, False)].getlength('M'))
        ascent, descent = self.fonts[(False, False)].getmetrics()
        self.cell_height = ascent + descent + 2
        self.ascent = ascent
        self.pad = 24; self.header = 68; self.footer = 44

    def image(self, grid, *, title='MOTD | actual terminal output',
              footer='2x raster | lossless PNG | hooks skipped'):
        width = self.pad * 2 + grid.columns * self.cell_width
        height = self.header + self.pad + grid.rows * self.cell_height + self.footer
        image = Image.new('RGB', (width, height), BACKGROUND); draw = ImageDraw.Draw(image)
        draw.text((self.pad, 15), title, font=self.small, fill=PALETTE[6])
        draw.text((self.pad, 38), f'{grid.columns} columns x {grid.rows} rows | synthetic fixture', font=self.small, fill=PALETTE[8])
        for row, cells in enumerate(grid.cells):
            for column, cell in enumerate(cells):
                if cell.continuation: continue
                x = self.pad + column * self.cell_width; y = self.header + row * self.cell_height
                fg, bg = (cell.bg, cell.fg) if cell.reverse else (cell.fg, cell.bg)
                if cell.dim:
                    fg = '#%02x%02x%02x' % tuple(round(a * .6 + b * .4) for a, b in zip(rgb(fg), rgb(bg)))
                span = max(1, sum(max(0, wcwidth(c)) for c in cell.text))
                if bg != BACKGROUND: draw.rectangle((x, y, x + span * self.cell_width - 1, y + self.cell_height - 1), fill=bg)
                if cell.text and cell.text != ' ':
                    draw.text((x, y + self.ascent), cell.text, anchor='ls', font=self.fonts[(cell.bold, cell.italic)], fill=fg)
                if cell.underline: draw.line((x, y + self.ascent + 2, x + span * self.cell_width - 1, y + self.ascent + 2), fill=fg, width=1)
        draw.text((self.pad, height - 30), footer, font=self.small, fill=PALETTE[8])
        return image


def rgba_digest(image):
    return digest(image.convert('RGBA').tobytes())


def optimize_png(path, *, optimizer=None, opt_level='max', zopfli=False):
    """Optimize an existing PNG, checking the full decoded image before/after."""
    with Image.open(path) as initial:
        before = rgba_digest(initial); size = initial.size
    initial_size = path.stat().st_size
    if optimizer:
        command = [optimizer, '-o', opt_level, '--fast', '--strip', 'safe', '--threads', '2', '--timeout', '30', str(path)]
        if zopfli: command[1:1] = ['--zopfli', '--zi', '5', '--ziwi', '2']
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if result.returncode: raise GalleryError('PNG optimizer failed: ' + result.stderr[-500:])
    with Image.open(path) as after:
        if after.size != size or rgba_digest(after) != before:
            raise GalleryError('PNG optimization changed dimensions or decoded pixels')
    return {'png_sha256': digest(path.read_bytes()), 'rgba_sha256': before,
            'pixels': list(size), 'bytes': path.stat().st_size,
            'before_optimization_bytes': initial_size}


def save_lossless(image, path, *, optimizer=None, opt_level='max', zopfli=False):
    """Encode every original pixel, then optionally optimize its lossless encoding."""
    before = rgba_digest(image)
    image.save(path, format='PNG', compress_level=9, optimize=True)
    details = optimize_png(path, optimizer=optimizer, opt_level=opt_level, zopfli=zopfli)
    if details['rgba_sha256'] != before:
        raise GalleryError('PNG encoding changed decoded pixels')
    return details


def optimize_gallery(output, cases, comparisons, optimizer, opt_level, zopfli, jobs):
    """Bounded parallel compression after all PTY children have exited.

    Deduplication is complete before workers start. Keeping this phase separate
    also avoids forking a controlling-terminal child while Python threads exist.
    Each worker owns one file and each optimizer uses at most two worker threads.
    """
    if not optimizer: return
    paths = sorted({c['png'] for c in cases} | {c['path'] for c in comparisons})
    results = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        pending = {pool.submit(optimize_png, output / path, optimizer=optimizer,
                               opt_level=opt_level, zopfli=zopfli): path for path in paths}
        for number, future in enumerate(as_completed(pending), 1):
            results[pending[future]] = future.result()
            if number % 16 == 0 or number == len(paths):
                print(f'Optimized {number}/{len(paths)} unique PNG files; decoded pixels verified', flush=True)
    for case in cases: case.update(results[case['png']])
    for comparison in comparisons: comparison.update(results[comparison['path']])


def write_index(output, manifest):
    payload = json.dumps(manifest['cases'], ensure_ascii=False).replace('</', '<\\/')
    total = len(manifest['cases']); unique = manifest['summary']['unique_pngs']
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MOTD terminal gallery</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#0b1220;color:#e4e9f0}body{max-width:1500px;margin:0 auto;padding:24px}h1{margin-bottom:8px}p{line-height:1.5;color:#b6c2d9}a{color:#79d9ce}.filters{display:flex;gap:12px;flex-wrap:wrap;position:sticky;top:0;background:#0b1220ee;padding:16px 0}label{display:flex;flex-direction:column;gap:5px;font-size:13px}select{background:#172338;color:#fff;border:1px solid #42516d;border-radius:5px;padding:8px;min-width:125px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,370px),1fr));gap:18px}.card{background:#111827;border:1px solid #28364e;border-radius:10px;overflow:hidden}.card img{display:block;width:100%;height:auto}.meta{padding:14px}.meta h2{font-size:16px;margin:0 0 6px}.meta p{font-size:13px;margin:6px 0}.status{margin:12px 0;color:#94a6c4}code{font-family:monospace}.actions{display:flex;gap:14px;font-size:13px}</style>
<h1>MOTD terminal gallery</h1><p>Actual output captured through sized pseudo-terminals, with synthetic data and disabled hooks. Each PNG preserves the entire requested terminal grid, including unused rows. Every PNG is lossless; identical pictures share a file without losing their individual capture records.</p>
<p>CASES logical captures · UNIQUE unique PNGs · <a href="manifest.json">Evidence manifest</a> · <a href="README.md">Reproduction notes</a></p>
<div class="filters" id="filters"></div><div class="status" id="status"></div><div class="cards" id="cards"></div>
<script>const cases=PAYLOAD;const keys=['sample_group','axis','variant','size','preset','shell','design','density','detail','bar_layout','theme','charset','colour'];const filters=document.getElementById('filters');for(const key of keys){const label=document.createElement('label');label.textContent=key;const select=document.createElement('select');select.dataset.key=key;for(const value of ['All',...new Set(cases.map(c=>c[key]))]){const option=document.createElement('option');option.textContent=value;select.append(option)}select.addEventListener('change',render);label.append(select);filters.append(label)}function render(){const selected=cases.filter(c=>[...filters.querySelectorAll('select')].every(s=>s.value==='All'||c[s.dataset.key]===s.value));document.getElementById('status').textContent=selected.length+' cases shown';const cards=document.getElementById('cards');cards.replaceChildren();for(const c of selected){const card=document.createElement('article');card.className='card';const link=document.createElement('a');link.href=c.png;link.target='_blank';const image=document.createElement('img');image.loading='lazy';image.src=c.png;image.alt=c.id;link.append(image);card.append(link);const meta=document.createElement('div');meta.className='meta';const h=document.createElement('h2');h.textContent=c.preset+' · '+c.shell+' · '+c.size;meta.append(h);const p=document.createElement('p');p.textContent=(c.axis ? c.axis+' = '+c.variant+' · ' : c.variant ? c.variant+' · ' : '')+c.design+' / '+c.density+' / '+c.detail+' / '+c.bar_layout+' bars · '+c.theme+' / '+c.charset+' / '+c.colour+' · '+c.content_rows+' used rows';meta.append(p);const actions=document.createElement('div');actions.className='actions';for(const [text,path]of[['PNG',c.png],['ANSI transcript',c.transcript],['Recipe',c.recipe]]){const a=document.createElement('a');a.textContent=text;a.href=path;actions.append(a)}meta.append(actions);card.append(meta);cards.append(card)}}render();</script></html>'''
    document = document.replace('CASES', str(total)).replace('UNIQUE', str(unique)).replace('PAYLOAD', payload)
    (output / 'index.html').write_text(document, encoding='utf-8')
    overview = ['# Actual terminal PNG gallery', '',
                f'{total} logical captures; {unique} unique lossless PNGs.', '',
                'Open [index.html](index.html) locally to filter by preset, interpreter, size, design, density, detail, theme, character set and colour mode.', '',
                'Terminal sizes: **' + ', '.join(dict.fromkeys(c['size'].replace('x', '×') for c in manifest['cases'])) + '**. The full grid is preserved; no terminal output was cropped or resized to make a layout fit. The final row is reserved for the shell prompt.', '',
                'Each record in [manifest.json](manifest.json) links its raw ANSI transcript, effective recipe, exact command, interpreter version, source hashes, cell geometry and lossless PNG pixel hash. Records may share a PNG when their actual output is identical.', '',
                'Fixtures are synthetic. Configured before/after commands do not run. Static public notices have no invented colour/theme variants.', '',
                '## Size comparisons', '']
    if manifest.get('selection') in ('axis-sampler', 'composition-sampler'):
        overview[-2:] = ['## Controlled comparisons', '',
            'Axis comparisons change one setting against the baseline recorded in the manifest. Context needed to make a setting visible (for example custom separator notes) is held constant within that axis. Combined recipes keep design=classic and set the independent policies directly.', '',
            '| Setting / combination | Choice | Size | Evidence |', '|---|---|---|---|']
        overview += [f'| {c.get("axis") or "composition"} | {c.get("variant", "")} | {c["size"]} | [PNG]({c["png"]}) · [Recipe]({c["recipe"]}) · [ANSI]({c["transcript"]}) |' for c in manifest['cases']]
        (output / 'README.md').write_text('\n'.join(overview) + '\n', encoding='utf-8')
        return
    if manifest.get('selection') == 'design-sampler':
        overview[-2:] = ['## Design comparisons', '',
            'This bounded sampler has 120 structural comparisons (five designs × four sizes × two presets × three backends), 15 full-detail density contrasts, and five brief-detail views. Colors and character modes are covered by the separate 524-case classic gallery.', '',
            'Density/detail contrasts use workshop/Bash at 80×50: all three densities at full detail, plus balanced/brief. The structural group supplies the balanced/normal reference. These are requested detail levels; actual row allocation still depends on available terminal space.', '',
            '| Terminal | Five-design comparison |', '|---|---|']
        overview += [f'| {c["size"]} | [Open PNG]({c["path"]}) |' for c in manifest['comparisons'] if c.get('kind') == 'designs']
        overview += ['', 'Use the HTML filters for individual Bash, sh and PowerShell captures and their exact recipes.', '']
        (output / 'README.md').write_text('\n'.join(overview) + '\n', encoding='utf-8')
        return
    if any(c.get('bar_layout') == 'wide' for c in manifest['cases']):
        overview += ['## Usage-bar comparisons', '',
            'Wide bars occupy their available panel width. The numeric reading survives when the viewport is too short for an extra bar row. These layouts reuse the same observations; the memory/storage meaning remains backend-specific and explicitly labelled.', '',
            '| Preset / backend | Design | Bars | Terminal | Preview |', '|---|---|---|---|---|']
        overview += [f'| {c["preset"]} / {c["shell"]} | {c["design"]} | {c["bar_layout"]} | {c["size"]} | [PNG]({c["png"]}) · [Recipe]({c["recipe"]}) |' for c in manifest['cases']]
        (output / 'README.md').write_text('\n'.join(overview) + '\n', encoding='utf-8')
        return
    for preset in PRESETS:
        for shell in SHELLS:
            matching = [c for c in manifest['cases'] if c['preset'] == preset and c['shell'] == shell and c['theme'] == 'cyan' and c['charset'] == 'unicode' and c['colour'] == 'colour' and presentation(c) == DEFAULT_PRESENTATION]
            if not matching: continue
            overview += [f'### {preset} / {shell}', '']
            comparison = next((c for c in manifest['comparisons'] if c['preset'] == preset and c['shell'] == shell), None)
            if comparison: overview += [f'[Open four-size comparison]({comparison["path"]})', '']
            overview += ['| Terminal | PNG | Captured output |', '|---|---|---|']
            overview += [f'| {c["size"]} | [Open PNG]({c["png"]}) | [ANSI]({c["transcript"]}) |' for c in matching]
            overview += ['']
    (output / 'README.md').write_text('\n'.join(overview) + '\n', encoding='utf-8')


def contact_sheets(output, cases, renderer, optimizer, opt_level, zopfli):
    records = []
    for preset in PRESETS:
        for shell in SHELLS:
            selected = [c for c in cases if c['preset'] == preset and c['shell'] == shell and c['theme'] == 'cyan' and c['charset'] == 'unicode' and c['colour'] == 'colour' and presentation(c) == DEFAULT_PRESENTATION]
            if len(selected) != 4: continue
            selected.sort(key=lambda c: (c['columns'], c['rows']))
            images = [Image.open(output / c['png']).convert('RGB') for c in selected]
            # Contact sheets paste original pixels at 1:1; different cell grids
            # remain visibly different sizes. No resampling changes their text.
            gap = 32; label_height = 34
            widths = [max(images[0].width, images[1].width), max(images[2].width, images[3].width)]
            heights = [max(images[0].height, images[2].height), max(images[1].height, images[3].height)]
            sheet = Image.new('RGB', (sum(widths) + gap * 3, sum(heights) + gap * 3 + label_height * 2), '#080f1b')
            draw = ImageDraw.Draw(sheet)
            for i, (record, image) in enumerate(zip(selected, images)):
                col, row = i // 2, i % 2
                x = gap + (widths[0] + gap if col else 0)
                y = gap + (heights[0] + label_height + gap if row else 0)
                draw.text((x, y), f'{preset} / {shell} / {record["size"]}', font=renderer.small, fill=FOREGROUND)
                sheet.paste(image, (x, y + label_height))
            path = output / 'comparisons' / f'{preset}-{shell}-four-sizes.png'
            path.parent.mkdir(exist_ok=True)
            details = save_lossless(sheet, path, optimizer=optimizer, opt_level=opt_level, zopfli=zopfli)
            records.append({'preset': preset, 'shell': shell, 'path': str(path.relative_to(output)), **details})
    return records


def design_sheets(output, cases, renderer):
    """Compare five complete terminal grids at native pixels, one sheet per size."""
    records = []
    for columns, rows in SIZES:
        selected = [c for c in cases if c['preset'] == 'workshop' and c['shell'] == 'bash'
                    and c['columns'] == columns and c['rows'] == rows and c['theme'] == 'cyan'
                    and c['charset'] == 'unicode' and c['colour'] == 'colour'
                    and c['density'] == 'balanced' and c['detail'] == 'normal']
        if {c['design'] for c in selected} != set(DESIGNS) or len(selected) != len(DESIGNS): continue
        selected.sort(key=lambda c: DESIGNS.index(c['design']))
        images = [Image.open(output / c['png']).convert('RGB') for c in selected]
        gap = 32; label_height = 34; width, height = images[0].size
        sheet = Image.new('RGB', (3 * width + 4 * gap, 2 * (height + label_height) + 3 * gap), '#080f1b')
        draw = ImageDraw.Draw(sheet)
        for index, (case, picture) in enumerate(zip(selected, images)):
            x = gap + (index % 3) * (width + gap)
            y = gap + (index // 3) * (height + label_height + gap)
            draw.text((x, y), case['design'] + ' / ' + case['size'], font=renderer.small, fill=FOREGROUND)
            sheet.paste(picture, (x, y + label_height))
        path = output / 'comparisons' / f'five-designs-{columns}x{rows}.png'
        path.parent.mkdir(exist_ok=True)
        records.append({'kind': 'designs', 'preset': 'workshop', 'shell': 'bash',
                        'size': f'{columns}x{rows}', 'source_cases': [c['id'] for c in selected],
                        'path': str(path.relative_to(output)), **save_lossless(sheet, path)})
    return records


def presentation(case):
    return tuple(case.get(key, default) for key, default in
                 zip(('design', 'density', 'detail'), DEFAULT_PRESENTATION))


def case_identifier(case):
    columns, rows = case['geometry']
    if case.get('sample_name'):
        return case['sample_name'] + f'-{columns}x{rows}'
    name = '-'.join(case[key] for key in ('preset', 'shell', 'theme', 'charset', 'colour'))
    name += f'-{columns}x{rows}'
    if presentation(case) != DEFAULT_PRESENTATION:
        name += '-' + '-'.join(presentation(case))
    if case.get('bar_layout', 'inline') != 'inline':
        name += '-bars-' + case['bar_layout']
    return name


def design_sampler_specs():
    """A fixed evidence budget, not a crossproduct of every configuration knob."""
    specs = []
    for preset, shell, design, geometry in itertools.product(PRESETS, ('bash', 'sh', 'powershell'), DESIGNS, SIZES):
        specs.append({'preset': preset, 'shell': shell, 'theme': 'cyan', 'charset': 'unicode',
                      'colour': 'colour', 'geometry': geometry, 'design': design,
                      'density': 'balanced', 'detail': 'normal', 'sample_group': 'structure'})
    for design, density in itertools.product(DESIGNS, DENSITIES):
        specs.append({'preset': 'workshop', 'shell': 'bash', 'theme': 'cyan', 'charset': 'unicode',
                      'colour': 'colour', 'geometry': (80, 50), 'design': design,
                      'density': density, 'detail': 'full', 'sample_group': 'density-at-full-detail'})
    for design in DESIGNS:
        specs.append({'preset': 'workshop', 'shell': 'bash', 'theme': 'cyan', 'charset': 'unicode',
                      'colour': 'colour', 'geometry': (80, 50), 'design': design,
                      'density': 'balanced', 'detail': 'brief', 'sample_group': 'brief-detail'})
    return specs


def capture_specs(args):
    if getattr(args, 'axis_sampler', False): return axis_sampler_specs()
    if getattr(args, 'composition_sampler', False): return composition_sampler_specs()
    if args.design_sampler: return design_sampler_specs()
    keys = ('preset', 'shell', 'theme', 'charset', 'colour', 'geometry', 'design', 'density', 'detail', 'bar_layout')
    return [dict(zip(keys, values)) for values in itertools.product(args.presets, args.shells,
            args.themes, args.charsets, args.colours, args.sizes, args.designs, args.densities, args.details, args.bar_layouts)]


def presentation_spec(name, patch, geometry, *, group, axis='', variant='', baseline=None):
    """A literal recipe delta, never a new renderer or mock screenshot."""
    return {'preset': 'workshop', 'shell': 'bash', 'theme': patch.get('theme', 'cyan'),
            'charset': patch.get('charset', 'unicode'),
            'colour': 'plain' if patch.get('color') == 'never' else 'colour',
            'geometry': geometry, 'design': patch.get('design', 'classic'),
            'density': patch.get('density', 'balanced'), 'detail': patch.get('detail', 'full'),
            'bar_layout': patch.get('bar_layout', 'inline'), 'sample_group': group,
            'sample_name': name, 'display_patch': patch, 'axis': axis, 'variant': variant,
            'baseline': baseline or {}}


def axis_sampler_specs():
    """Change one setting at a time against a declared per-axis baseline."""
    axes = {
        'design': list(DESIGNS), 'theme': list(THEMES),
        'density': list(DENSITIES), 'detail': list(DETAILS),
        'panel_layout': ['stack', 'columns'],
        'panel_frame': ['continuous', 'separate', 'none'],
        'border_style': ['single', 'rounded', 'double', 'heavy', 'ascii'],
        'border_visibility': ['all', 'outer', 'sections', 'none'],
        'heading_style': ['rule', 'plain', 'inline', 'hidden'],
        'heading_align': ['left', 'center', 'right'],
        'separator_text': ['none', 'summary', 'custom'],
        'label_style': ['full', 'short'], 'overflow': ['ellipsis', 'clip'],
        'padding': [0, 1, 2, 3], 'section_gap': [0, 1, 2],
        'bar_layout': ['inline', 'wide'],
        'color_emphasis': ['quiet', 'balanced', 'vivid'],
        'charset': ['ascii', 'unicode'], 'color': ['always', 'never'],
        'top_entries': [1, 3, 5], 'show_swap': [True, False],
        'show_compression': [True, False], 'show_pressure': [True, False],
        'section_titles': [{}, {'system': 'Machine identity', 'resources': 'Capacity',
                               'services': 'Service health', 'processes': 'Busy programs'}],
        'section_notes': [{}, {'resources': 'One snapshot; bounded collection',
                              'services': 'Required services remain visible'}],
        'section_detail': [{}, {'resources': 'brief', 'services': 'full', 'processes': 'full'}],
        'sections': [list(motd.SECTION_IDS), ['system', 'resources', 'services', 'attention', 'hints']],
        'priority': [list(motd.DEFAULT_PRIORITY), list(reversed(motd.DEFAULT_PRIORITY))],
    }
    specs = []
    for axis, values in axes.items():
        baseline = {'width': 160, 'rows': 50, 'detail': 'full',
                    'sections': list(motd.SECTION_IDS)}
        if axis == 'separator_text':
            baseline['section_notes'] = {'system': 'Workshop / local observations',
                                         'resources': 'Capacity overview', 'services': 'Service health'}
        if axis == 'section_notes': baseline['separator_text'] = 'custom'
        if axis == 'overflow':
            baseline['section_titles'] = {'resources': 'A deliberately long resource heading to demonstrate terminal-cell clipping without changing the measurements'}
        for index, value in enumerate(values):
            label = str(value).lower() if not isinstance(value, (dict, list)) else ('default' if index == 0 else 'custom')
            patch = dict(baseline); patch[axis] = value
            name = 'axis-' + axis.replace('_', '-') + '-' + label
            for geometry in PRESENTATION_SIZES:
                specs.append(presentation_spec(name, patch, geometry, group='axis', axis=axis,
                                               variant=label, baseline=baseline))
    return specs


def composition_sampler_specs():
    """All combinations keep Classic and compose explicit low-level policies."""
    recipes = {
        'classic-workshop': {},
        'rounded-green': {'theme': 'green', 'border_style': 'rounded', 'separator_text': 'summary'},
        'double-amber': {'theme': 'amber', 'border_style': 'double', 'heading_align': 'center'},
        'open-inventory': {'panel_frame': 'none', 'heading_style': 'inline', 'label_style': 'short'},
        'quiet-rules': {'panel_frame': 'none', 'heading_style': 'rule', 'color_emphasis': 'quiet'},
        'wide-capacity': {'bar_layout': 'wide', 'sections': ['system', 'resources', 'services', 'attention', 'hints']},
        'paired-panels': {'panel_layout': 'columns', 'panel_frame': 'separate', 'bar_layout': 'wide', 'border_style': 'rounded'},
        'spacious-cards': {'panel_frame': 'separate', 'density': 'comfortable', 'padding': 2},
        'compact-operations': {'density': 'compact', 'padding': 0, 'label_style': 'short', 'separator_text': 'summary'},
        'mono-ascii': {'theme': 'mono', 'charset': 'ascii', 'color': 'never', 'panel_frame': 'separate'},
        'headline-briefing': {'panel_frame': 'none', 'heading_style': 'plain', 'detail': 'brief', 'section_gap': 1},
        'annotated-rules': {'heading_align': 'right', 'separator_text': 'custom',
                            'section_notes': {'resources': 'Capacity', 'services': 'Local service observations'}},
    }
    result = []
    for name, overrides in recipes.items():
        patch = {'width': 160, 'rows': 50, 'design': 'classic', 'detail': 'full',
                 'sections': list(motd.SECTION_IDS)}
        patch.update(overrides)
        for geometry in PRESENTATION_SIZES:
            result.append(presentation_spec('composition-' + name, patch, geometry,
                                           group='composition', variant=name))
    return result


def parse_csv(raw, allowed, name):
    selected = tuple(x.strip() for x in raw.split(',') if x.strip())
    if not selected or set(selected) - set(allowed): raise GalleryError(f'Invalid {name}: {raw}')
    if len(selected) != len(set(selected)): raise GalleryError(f'Duplicate {name}: {raw}')
    return selected


def source_hashes():
    paths = [ROOT/'motd.py', Path(__file__)] + sorted(path for path in (ROOT/'runtime').iterdir()
            if path.is_file() and path.suffix in ('.bash', '.sh', '.ps1'))
    return {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in paths}


def font_metadata(renderer):
    records = []
    for style, font in renderer.fonts.items():
        path = Path(font.path)
        record = {'style': {'bold': style[0], 'italic': style[1]}, 'path': str(path),
                  'sha256': digest(path.read_bytes()), 'family': font.getname()[0], 'face': font.getname()[1]}
        if shutil.which('fc-query'):
            record['fontconfig_version'] = subprocess.check_output(
                ['fc-query', '--format=%{fontversion}', str(path)], text=True, timeout=3)
        records.append(record)
    return records


def inside(directory, relative):
    path = (directory / relative).resolve()
    try: path.relative_to(directory.resolve())
    except ValueError:
        raise GalleryError('Manifest path escapes the gallery or repository')
    return path


def verify_gallery(output, *, require_full=False, require_sampler=False):
    """Validate retained evidence without running imported scripts or hooks."""
    output = Path(output).resolve()
    manifest = json.loads((output/'manifest.json').read_text())
    for relative, expected in manifest['source_sha256'].items():
        if digest(inside(ROOT, relative).read_bytes()) != expected:
            raise GalleryError('Source hash mismatch: ' + relative)
    cases = manifest['cases']; identifiers = [c['id'] for c in cases]
    if len(identifiers) != len(set(identifiers)):
        raise GalleryError('Duplicate logical capture identifier')
    if require_full:
        expected = {f'{p}-{s}-{t}-{c}-{m}-{w}x{h}' for p,s,t,c,m,(w,h) in
                    itertools.product(PRESETS,SHELLS,THEMES,CHARSETS,COLOURS,SIZES)}
        expected |= {f'public-{t}-{w}x{h}' for t in ('issue','ssh-banner','text') for w,h in SIZES}
        if set(identifiers) != expected:
            raise GalleryError('The gallery does not contain the complete 524-case matrix')
        if any(presentation(c) != DEFAULT_PRESENTATION for c in cases if not c['shell'].startswith('static-')):
            raise GalleryError('The complete classic matrix must use classic/balanced/normal presentation')
    if require_sampler and set(identifiers) != {case_identifier(c) for c in design_sampler_specs()}:
        raise GalleryError('The gallery does not contain the complete 140-case design sampler')
    recipes = {}; images = {}
    for case in cases:
        raw = inside(output, case['transcript']).read_bytes()
        if digest(raw) != case['transcript_sha256']:
            raise GalleryError('Transcript hash mismatch: ' + case['id'])
        grid = TerminalGrid(case['columns'], case['rows']).feed(raw.decode('utf-8'))
        if (grid.fingerprint() != case['cell_grid_sha256'] or
                grid.highest_row + 1 != case['content_rows'] or
                grid.max_columns != case['maximum_columns_used']):
            raise GalleryError('Terminal-cell evidence mismatch: ' + case['id'])
        if case['charset'] == 'ascii' and any(ord(c) > 127 for c in grid.plain_text()):
            raise GalleryError('Non-ASCII terminal cell: ' + case['id'])
        recipe = case['recipe']
        if recipe not in recipes:
            path = inside(output, recipe)
            config = motd.load_config(path)
            recipes[recipe] = (digest(path.read_bytes()), digest(motd.generate_artifact(config).encode()),
                               presentation(config['display']), config['display']['bar_layout'])
        if recipes[recipe][:2] != (case['recipe_sha256'], case['artifact_sha256']):
            raise GalleryError('Recipe or generated-source mismatch: ' + recipe)
        if not case['shell'].startswith('static-') and recipes[recipe][2] != presentation(case):
            raise GalleryError('Presentation metadata differs from the captured recipe: ' + recipe)
        if not case['shell'].startswith('static-') and recipes[recipe][3] != case.get('bar_layout', 'inline'):
            raise GalleryError('Bar metadata differs from the captured recipe: ' + recipe)
        if case.get('display_patch'):
            effective = motd.load_config(inside(output, recipe))['display']
            if any(effective[key] != value for key, value in case['display_patch'].items()):
                raise GalleryError('Customization metadata differs from captured recipe: ' + recipe)
        png = case['png']
        if png not in images:
            path = inside(output, png)
            with Image.open(path) as im:
                images[png] = (digest(path.read_bytes()), rgba_digest(im), list(im.size), path.stat().st_size)
        if images[png] != (case['png_sha256'], case['rgba_sha256'], case['pixels'], case['bytes']):
            raise GalleryError('PNG hash, decoded pixels, dimensions or size mismatch: ' + png)
        cell_width, cell_height = manifest['raster']['cell_pixels']
        expected_size = [48 + case['columns']*cell_width, 136 + case['rows']*cell_height]
        if case['pixels'] != expected_size:
            raise GalleryError('PNG does not preserve the full terminal grid: ' + png)
    for comparison in manifest['comparisons']:
        path = inside(output, comparison['path'])
        with Image.open(path) as im:
            actual = (digest(path.read_bytes()), rgba_digest(im), list(im.size), path.stat().st_size)
        if actual != (comparison['png_sha256'],comparison['rgba_sha256'],comparison['pixels'],comparison['bytes']):
            raise GalleryError('Comparison sheet mismatch: ' + comparison['path'])
    summary = manifest['summary']
    if (summary['logical_cases'] != len(cases) or summary['unique_pngs'] != len(images) or
            summary['png_bytes'] != sum(details[3] for details in images.values())):
        raise GalleryError('Gallery summary does not match the retained files')
    result = {'verified_logical_cases': len(cases), 'verified_unique_pngs': len(images),
              'verified_comparisons': len(manifest['comparisons']), 'all_decoded_pixels_verified': True}
    print(json.dumps(result, indent=2)); return result


def build(args):
    output = Path(args.output).resolve()
    if args.zip:
        try: Path(args.zip).resolve().relative_to(output)
        except ValueError: pass
        else: raise GalleryError('The gallery archive must be outside the gallery directory')
    output.mkdir(parents=True, exist_ok=True)
    try: recipe_root = str(output.relative_to(ROOT))
    except ValueError: recipe_root = str(output)
    for name in ('png', 'transcripts', 'recipes'): (output / name).mkdir(exist_ok=True)
    sources = source_hashes()
    matrix = capture_specs(args)
    renderer = Renderer(args.font)
    interpreters = {}
    for shell in dict.fromkeys(case['shell'] for case in matrix):
        exe = args.powershell if shell == 'powershell' else shutil.which(shell)
        if not exe: raise GalleryError(f'{shell} is required to capture this gallery; no simulated substitute is used')
        if shell == 'powershell': query = [exe, '-NoProfile', '-NonInteractive', '-Command', '$PSVersionTable.PSVersion.ToString()']
        elif shell == 'sh': query = [exe, '-c', 'printf "%s\\n" "POSIX sh via $0"']
        else: query = [exe, '--version']
        version = subprocess.check_output(query, text=True, timeout=8).strip().splitlines()[0]
        interpreters[shell] = {'path': exe, 'resolved_path': str(Path(exe).resolve()),
                               'version': version, 'binary_sha256': digest(Path(exe).read_bytes())}
    optimizer = args.optimizer or shutil.which('oxipng')
    if optimizer and not Path(optimizer).is_file(): raise GalleryError('PNG optimizer not found')
    optimizer_version = subprocess.check_output([optimizer, '--version'], text=True).strip() if optimizer else None
    cases = []; png_cache = {}; templates = {}; bytes_before = 0
    with tempfile.TemporaryDirectory(prefix='motd-gallery-') as folder:
        temporary = Path(folder)
        for number, specification in enumerate(matrix, 1):
            preset, shell, theme, charset, colour = (specification[x] for x in ('preset', 'shell', 'theme', 'charset', 'colour'))
            columns, rows = specification['geometry']
            design, density, detail = presentation(specification)
            bar_layout = specification.get('bar_layout', 'inline')
            key = (preset, shell, theme, design, density, detail, bar_layout,
                   specification.get('sample_name', ''))
            if key not in templates:
                config = motd.preset_config(preset); motd.select_shell(config, shell)
                config['display'].update(theme=theme, design=design, density=density, detail=detail,
                                         bar_layout=bar_layout)
                config['display'].update(specification.get('display_patch', {}))
                config = motd.validate_config(config)
                artifact = motd.generate_artifact(config)
                stem = specification.get('sample_name') or '-'.join(key[:3] if presentation(specification) == DEFAULT_PRESENTATION else key[:6])
                if bar_layout != 'inline' and not specification.get('sample_name'): stem += '-bars-' + bar_layout
                path = temporary / (stem + motd.artifact_suffix(config))
                path.write_text(artifact, encoding='utf-8')
                group = specification.get('axis', '').replace('_', '-')
                recipe = Path('recipes') / group / (stem + '.toml')
                (output / recipe).parent.mkdir(parents=True, exist_ok=True)
                (output / recipe).write_text(motd.dump_config(config), encoding='utf-8')
                templates[key] = (path, recipe, digest(artifact.encode()))
            artifact, recipe, artifact_hash = templates[key]
            identifier = case_identifier(specification)
            command = output_command(shell, interpreters[shell]['path'], artifact, columns, rows, charset, colour)
            raw, elapsed = capture_pty(command, columns, rows, cwd=temporary)
            text = raw.decode('utf-8', errors='strict')
            grid = TerminalGrid(columns, rows).feed(text)
            visible = grid.plain_text()
            if charset == 'ascii' and any(ord(ch) > 127 for ch in visible):
                raise GalleryError(identifier + ': ASCII output contains non-ASCII cells')
            group = specification.get('axis', '').replace('_', '-')
            transcript = Path('transcripts') / group / (identifier + '.ansi')
            (output / transcript).parent.mkdir(parents=True, exist_ok=True)
            (output / transcript).write_bytes(raw)
            grid_hash = grid.fingerprint()
            if grid_hash in png_cache: png, details = png_cache[grid_hash]
            else:
                image = renderer.image(grid)
                pixel_hash = rgba_digest(image)
                # Equal cell styles may have no visible effect on blank cells.
                # Pixel dedup is the final authority, and is still lossless.
                same = next((item for item in png_cache.values() if item[1]['rgba_sha256'] == pixel_hash), None)
                if same: png, details = same
                else:
                    png = Path('png') / group / (identifier + '.png')
                    (output / png).parent.mkdir(parents=True, exist_ok=True)
                    details = save_lossless(image, output / png)
                    bytes_before += details['before_optimization_bytes']
                png_cache[grid_hash] = (png, details)
            normalized_command = [str(x).replace(str(artifact), '<generated-script>') for x in command]
            cases.append({'id': identifier, 'preset': preset, 'shell': shell, 'theme': theme,
                          'design': design, 'density': density, 'detail': detail, 'bar_layout': bar_layout,
                          'sample_group': specification.get('sample_group', 'matrix'),
                          **{key: specification[key] for key in ('axis', 'variant', 'baseline', 'display_patch') if key in specification},
                          'charset': charset, 'colour': colour, 'size': f'{columns}x{rows}', 'columns': columns, 'rows': rows,
                          'content_rows': grid.highest_row + 1, 'maximum_columns_used': grid.max_columns,
                          'png': str(png), 'transcript': str(transcript), 'recipe': str(recipe),
                          'command': normalized_command, 'artifact_sha256': artifact_hash,
                          'generate_command': ['python3', 'motd.py', 'build', '--config',
                                               str(Path(recipe_root) / recipe), '--output', '<generated-script>'],
                          'recipe_sha256': digest((output / recipe).read_bytes()),
                          'transcript_sha256': digest(raw), 'cell_grid_sha256': grid_hash,
                          'terminal_modes_ignored': sorted(set(grid.ignored_modes)), 'observed_capture_seconds': elapsed, **details})
            if number % 16 == 0 or number == len(matrix): print(f'Captured {number}/{len(matrix)} shell cases', flush=True)
        if args.static and not (args.design_sampler or args.axis_sampler or args.composition_sampler):
            for target in ('issue', 'ssh-banner', 'text'):
                config = motd.preset_config('public-console'); config['target'] = target
                artifact = motd.generate_artifact(config)
                path = temporary / ('public-' + target + '.txt'); path.write_text(artifact, encoding='utf-8')
                recipe = Path('recipes') / ('public-' + target + '.toml')
                (output / recipe).write_text(motd.dump_config(config), encoding='utf-8')
                for columns, rows in args.sizes:
                    identifier = f'public-{target}-{columns}x{rows}'
                    raw, elapsed = capture_pty(['/bin/cat', str(path)], columns, rows, cwd=temporary)
                    grid = TerminalGrid(columns, rows).feed(raw.decode())
                    transcript = Path('transcripts') / (identifier + '.ansi'); (output / transcript).write_bytes(raw)
                    image = renderer.image(grid); pixel_hash = rgba_digest(image)
                    same = next((item for item in png_cache.values() if item[1]['rgba_sha256'] == pixel_hash), None)
                    if same: png, details = same
                    else:
                        png = Path('png') / (identifier + '.png')
                        details = save_lossless(image, output / png)
                        bytes_before += details['before_optimization_bytes']
                        png_cache[grid.fingerprint()] = (png, details)
                    cases.append({'id': identifier, 'preset': 'public-console', 'shell': 'static-' + target,
                                  'theme': 'literal', 'charset': 'literal', 'colour': 'plain',
                                  'design': 'literal', 'density': 'literal', 'detail': 'literal',
                                  'bar_layout': 'literal', 'sample_group': 'static',
                                  'size': f'{columns}x{rows}', 'columns': columns, 'rows': rows,
                                  'content_rows': grid.highest_row + 1, 'maximum_columns_used': grid.max_columns,
                                  'png': str(png), 'transcript': str(transcript), 'recipe': str(recipe),
                                  'command': ['/bin/cat', '<generated-static-file>'], 'artifact_sha256': digest(artifact.encode()),
                                  'generate_command': ['python3', 'motd.py', 'build', '--config',
                                                       str(Path(recipe_root) / recipe), '--output', '<generated-static-file>'],
                                  'recipe_sha256': digest((output / recipe).read_bytes()),
                                  'transcript_sha256': digest(raw), 'cell_grid_sha256': grid.fingerprint(),
                                  'terminal_modes_ignored': [], 'observed_capture_seconds': elapsed,
                                  'note': 'Literal bytes displayed by cat; no real getty or SSH server is claimed.', **details})
    comparisons = contact_sheets(output, cases, renderer, None, args.opt_level, False) if args.comparisons and not (args.design_sampler or args.axis_sampler or args.composition_sampler) else []
    if args.comparisons: comparisons += design_sheets(output, cases, renderer)
    optimize_gallery(output, cases, comparisons, optimizer, args.opt_level, args.zopfli, args.jobs)
    unique = {c['png']: c for c in cases}
    if source_hashes() != sources:
        raise GalleryError('Source files changed during capture; rebuild from stable sources')
    manifest = {'schema_version': 2, 'generator': motd.VERSION, 'source_sha256': sources,
                'selection': 'axis-sampler' if args.axis_sampler else 'composition-sampler' if args.composition_sampler else 'design-sampler' if args.design_sampler else 'matrix',
                'environment': {'system': platform.platform(), 'python': platform.python_version(), 'pillow': PILLOW_VERSION,
                                'wcwidth': WCWIDTH_VERSION, 'interpreters': interpreters},
                'raster': {'font': str(renderer.path), 'font_sha256': digest(renderer.path.read_bytes()), 'font_size_px': renderer.font_size, 'font_variants': font_metadata(renderer),
                           'cell_pixels': [renderer.cell_width, renderer.cell_height], 'display_scale': 2,
                           'colour_palette': PALETTE, 'font_license': 'https://dejavu-fonts.github.io/License.html'},
                'compression': {'pillow': {'compress_level': 9, 'optimize': True}, 'optimizer': optimizer_version,
                                'optimizer_level': args.opt_level if optimizer else None, 'zopfli': bool(optimizer and args.zopfli),
                                'fast_filter_evaluation': bool(optimizer),
                                'optimizer_budget_seconds': 30 if optimizer else None,
                                'parallel_files': args.jobs if optimizer else 0, 'threads_per_optimizer': 2 if optimizer else 0,
                                'lossy_operations': [], 'decoded_rgba_verified': True},
                'summary': {'logical_cases': len(cases), 'shell_cases': len(matrix), 'unique_pngs': len(unique),
                            'png_bytes': sum(c['bytes'] for c in unique.values()), 'png_bytes_before_optimization': bytes_before,
                            'comparison_pngs': len(comparisons),
                            'comparison_png_bytes': sum(c['bytes'] for c in comparisons),
                            'all_png_bytes': sum(c['bytes'] for c in unique.values()) + sum(c['bytes'] for c in comparisons)},
                'cases': cases}
    manifest['comparisons'] = comparisons
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_index(output, manifest)
    # Remove stale generated captures from a previous matrix, never other files.
    expected = {c['png'] for c in cases} | {c['transcript'] for c in cases} | {c['recipe'] for c in cases} | {c['path'] for c in comparisons}
    for directory in ('png', 'transcripts', 'recipes', 'comparisons'):
        if not (output/directory).is_dir(): continue
        for path in (output/directory).rglob('*'):
            if path.is_file() and str(path.relative_to(output)) not in expected: path.unlink()
    if args.zip:
        archive = Path(args.zip).resolve(); archive.parent.mkdir(parents=True, exist_ok=True)
        try: archive_root = str(output.relative_to(ROOT))
        except ValueError: archive_root = output.name
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for path in sorted(output.rglob('*')):
                if path.is_file():
                    info = zipfile.ZipInfo(archive_root + '/' + str(path.relative_to(output)), date_time=(2026, 11, 17, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_STORED if path.suffix == '.png' else zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    z.writestr(info, path.read_bytes())
        print('Archive:', archive, archive.stat().st_size, 'bytes')
    print(json.dumps(manifest['summary'], indent=2))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', help='Destination (default: examples/gallery, or examples/designs for the sampler)')
    parser.add_argument('--verify', action='store_true', help='Verify retained evidence without executing scripts or recapturing')
    parser.add_argument('--require-full', action='store_true', help='With --verify, require all 512 shell and 12 static cases')
    parser.add_argument('--require-sampler', action='store_true', help='With --verify, require the fixed 140-case design sampler')
    parser.add_argument('--design-sampler', action='store_true', help='Capture a fixed 140-case presentation sampler; excludes static notices')
    parser.add_argument('--axis-sampler', action='store_true', help='Capture independent controls at 80x25, 80x50, 120x50 and 160x50')
    parser.add_argument('--composition-sampler', action='store_true', help='Capture 12 combined Classic recipes at the four presentation sizes')
    parser.add_argument('--presets', default=','.join(PRESETS))
    parser.add_argument('--shells', default=','.join(SHELLS))
    parser.add_argument('--themes', default=','.join(THEMES))
    parser.add_argument('--charsets', default=','.join(CHARSETS))
    parser.add_argument('--colours', default=','.join(COLOURS))
    parser.add_argument('--designs', default='classic', help='Comma-separated presentation designs (default: classic)')
    parser.add_argument('--densities', default='balanced', help='Comma-separated spacing densities (default: balanced)')
    parser.add_argument('--details', default='normal', help='Comma-separated requested detail levels (default: normal)')
    parser.add_argument('--bar-layouts', default='inline', help='Comma-separated bar layouts: inline, wide')
    parser.add_argument('--sizes', default=','.join(f'{c}x{r}' for c, r in SIZES))
    parser.add_argument('--powershell', default=shutil.which('pwsh') or shutil.which('powershell'))
    parser.add_argument('--font', default=DEFAULT_FONT)
    parser.add_argument('--optimizer', help='Path to optional oxipng executable')
    parser.add_argument('--opt-level', choices=('0','1','2','3','4','5','6','max'), default='max')
    parser.add_argument('--zopfli', action='store_true', help='Use slower five-iteration lossless Zopfli optimization')
    parser.add_argument('--jobs', type=int, choices=range(1, 9), default=4, help='Concurrent PNG optimizers after capture (default: 4)')
    parser.add_argument('--no-static', dest='static', action='store_false')
    parser.add_argument('--no-comparisons', dest='comparisons', action='store_false')
    parser.add_argument('--zip', help='Write a repository-root-extractable gallery archive')
    args = parser.parse_args(argv)
    if sum((args.design_sampler, args.axis_sampler, args.composition_sampler)) > 1:
        raise GalleryError('Select one sampler per output directory')
    if not args.output:
        args.output = str(ROOT / ('gallery/axes' if args.axis_sampler else 'gallery/compositions' if args.composition_sampler else 'gallery/designs' if args.design_sampler or args.require_sampler else 'gallery/compatibility'))
    if args.verify: return verify_gallery(args.output, require_full=args.require_full, require_sampler=args.require_sampler)
    for name, allowed in [('presets', PRESETS), ('shells', SHELLS), ('themes', THEMES), ('charsets', CHARSETS), ('colours', COLOURS), ('designs', DESIGNS), ('densities', DENSITIES), ('details', DETAILS), ('bar_layouts', BAR_LAYOUTS)]:
        setattr(args, name, parse_csv(getattr(args, name), allowed, name))
    if args.design_sampler and args.bar_layouts != ('inline',):
        raise GalleryError('The fixed design sampler uses inline bars; use a separate --output for a wide-bar matrix')
    sizes = parse_csv(args.sizes, tuple(dict.fromkeys(f'{c}x{r}' for c, r in SIZES + PRESENTATION_SIZES)), 'sizes')
    args.sizes = tuple(tuple(map(int, x.split('x'))) for x in sizes)
    return build(args)


if __name__ == '__main__':
    try: main()
    except (GalleryError, OSError, subprocess.TimeoutExpired) as exc:
        print('Gallery:', exc, file=sys.stderr)
        raise SystemExit(2)
