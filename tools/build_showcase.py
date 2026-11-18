#!/usr/bin/env python3
"""Select reproducible, diverse terminal captures without inventing output."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SIZES = ('80x25', '80x50', '120x50', '160x50')
GROUPS = ('axes', 'compositions')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def choose(cases, seed, per_size):
    rng = random.Random(seed)
    result = []
    for size in SIZES:
        pool = [case for case in cases if case['size'] == size]
        rng.shuffle(pool)
        # One image from each randomized axis/composition before repeating a
        # category; also reject identical decoded pictures within each size.
        categories = list(dict.fromkeys(c.get('axis') or c.get('variant') for c in pool))
        rng.shuffle(categories)
        chosen = []; pixels = set()
        while len(chosen) < per_size:
            before = len(chosen)
            for category in categories:
                candidate = next((c for c in pool if (c.get('axis') or c.get('variant')) == category
                                  and c['rgba_sha256'] not in pixels), None)
                if candidate is None: continue
                chosen.append(candidate); pixels.add(candidate['rgba_sha256'])
                if len(chosen) == per_size: break
            if before == len(chosen):
                raise ValueError('Not enough distinct terminal pictures at ' + size)
        result.extend(chosen)
    return result


def sources():
    cases = []; evidence = {}
    for group in GROUPS:
        path = ROOT / 'gallery' / group / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        evidence[group] = sha(path)
        for original in manifest['cases']:
            case = dict(original)
            case['source_group'] = group
            for key in ('png', 'transcript', 'recipe'):
                case[key] = '../' + group + '/' + case[key]
            cases.append(case)
    return cases, evidence


def verify():
    output = ROOT / 'gallery/showcase'
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    cases, evidence = sources()
    if manifest['source_manifests_sha256'] != evidence:
        raise ValueError('Showcase source manifest changed; regenerate selection')
    selected = choose(cases, manifest['seed'], manifest['per_size'])
    if [c['id'] for c in selected] != [c['id'] for c in manifest['cases']]:
        raise ValueError('Selection does not match the recorded random seed')
    for case in manifest['cases']:
        for key, digest in (('png', 'png_sha256'), ('transcript', 'transcript_sha256'), ('recipe', 'recipe_sha256')):
            if sha(output / case[key]) != case[digest]:
                raise ValueError('Changed selected capture: ' + case['id'])
    for sheet in manifest['contact_sheets']:
        if sha(output / sheet['path']) != sheet['sha256']:
            raise ValueError('Changed contact sheet: ' + sheet['path'])
    print(json.dumps({'selected_captures': len(selected), 'sizes': list(SIZES), 'seed': manifest['seed'], 'verified': True}))


def build(seed=20261118, per_size=16):
    output = ROOT / 'gallery/showcase'; output.mkdir(parents=True, exist_ok=True)
    all_cases, evidence = sources()
    cases = choose(all_cases, seed, per_size)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 18)
    sheets = []
    for size in SIZES:
        selected = [c for c in cases if c['size'] == size]
        thumb_width = 480; label_rows = 54; gap = 18; columns = 4
        with Image.open(output / selected[0]['png']) as image:
            thumb_height = round(image.height * thumb_width / image.width)
        rows = (len(selected) + columns - 1) // columns
        sheet = Image.new('RGB', (columns * (thumb_width + gap) + gap,
                                 rows * (thumb_height + label_rows + gap) + gap + 48), '#0b1220')
        draw = ImageDraw.Draw(sheet)
        draw.text((gap, gap), f'MOTD {size} | 16 seeded selections | reduced overview; originals linked', font=font, fill='#dce6f3')
        for i, case in enumerate(selected):
            x = gap + i % columns * (thumb_width + gap)
            y = gap + 48 + i // columns * (thumb_height + label_rows + gap)
            label = (case.get('axis') or 'composition') + ': ' + case.get('variant', '')
            draw.text((x, y), label[:44], font=font, fill='#66d1df')
            draw.text((x, y + 23), case['size'] + ' / ' + case['shell'], font=font, fill='#93a6bf')
            with Image.open(output / case['png']) as image:
                sheet.paste(image.convert('RGB').resize((thumb_width, thumb_height), Image.Resampling.LANCZOS), (x, y + label_rows))
        path = 'contact-' + size + '.png'
        sheet.save(output / path, optimize=True, compress_level=9)
        sheets.append({'path': path, 'size': size, 'sha256': sha(output / path),
                       'note': 'Reduced navigation overview. Full terminal originals are never resized.'})
    manifest = {'schema_version': 1, 'seed': seed, 'per_size': per_size,
                'source_manifests_sha256': evidence, 'cases': cases, 'contact_sheets': sheets}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    payload = json.dumps(cases).replace('</', '<\\/')
    (output / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MOTD selected captures</title>
<style>:root{color-scheme:dark;font:16px system-ui;background:#0b1220;color:#e4e9f0}body{max-width:1600px;margin:auto;padding:24px}a{color:#79d9ce}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}article{background:#142033;border:1px solid #30405b;padding:14px;border-radius:10px}img{width:100%;height:auto}select{font:inherit;padding:8px;background:#142033;color:white}p{line-height:1.5}</style>
<h1>64 reproducible terminal selections</h1><p>Actual generated-script output with synthetic observations and hooks disabled. Seed SEED. Each original PNG retains the full terminal grid. The contact sheets are reduced navigation overviews.</p><p><a href="../index.html">All galleries</a> · <a href="manifest.json">Selection evidence</a></p><label>Terminal <select id="size"><option>All</option><option>80x25</option><option>80x50</option><option>120x50</option><option>160x50</option></select></label><div id="grid" class="grid"></div>
<script>const cases=PAYLOAD;const size=document.getElementById('size');function render(){const grid=document.getElementById('grid');grid.replaceChildren();for(const c of cases.filter(c=>size.value==='All'||c.size===size.value)){const card=document.createElement('article');const h=document.createElement('h2');h.textContent=c.size+' · '+(c.axis||'composition')+' · '+c.variant;card.append(h);const a=document.createElement('a');a.href=c.png;const im=document.createElement('img');im.loading='lazy';im.src=c.png;im.alt=c.id;a.append(im);card.append(a);const p=document.createElement('p');for(const [label,key] of [['Full PNG','png'],['Recipe','recipe'],['ANSI transcript','transcript']]){const link=document.createElement('a');link.href=c[key];link.textContent=label;p.append(link,document.createTextNode(' · '))}card.append(p);grid.append(card)}}size.addEventListener('change',render);render()</script></html>'''.replace('SEED', str(seed)).replace('PAYLOAD', payload), encoding='utf-8')
    overview = ['# Selected terminal captures', '', f'{len(cases)} captures, {per_size} at each requested size. Random seed: `{seed}`.', '',
                '[Open the searchable showcase](index.html). Originals retain the entire terminal grid. Contact sheets are reduced overviews.', '',
                '| Size | Contact sheet |', '|---|---|']
    overview += [f'| {s["size"]} | [PNG]({s["path"]}) |' for s in sheets]
    (output / 'README.md').write_text('\n'.join(overview) + '\n', encoding='utf-8')
    verify()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--seed', type=int, default=20261118)
    args = parser.parse_args()
    verify() if args.verify else build(args.seed)
