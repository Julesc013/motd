#!/usr/bin/env python3
"""Build verifiable alpha assets from committed Git blobs and recorded modes.

ZIP bytes repeat for the same commit and Python/zlib toolchain. Compression
libraries may change their byte stream across versions; the manifest records
the toolchain instead of claiming universal bit-for-bit reproducibility.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
GALLERY_GROUPS = ('compatibility', 'designs', 'bars', 'axes', 'compositions', 'showcase')
REQUESTED_SIZES = {'80x25', '80x50', '120x50', '160x50'}


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT)


def committed_tree():
    result = {}
    for entry in git('ls-tree', '-rz', 'HEAD').split(b'\0'):
        if not entry: continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        result[name.decode('utf-8')] = (mode, kind, oid)
    return result


def blob(entry):
    if entry[1] != 'blob' or entry[0] not in ('100644', '100755'):
        raise ValueError('Release inputs must be regular tracked files')
    return git('cat-file', 'blob', entry[2])


def validate_galleries(tree):
    if 'gallery/index.html' not in tree:
        raise ValueError('The committed gallery entry point is missing')
    for group in GALLERY_GROUPS:
        name = 'gallery/' + group + '/manifest.json'
        if name not in tree: raise ValueError('Missing committed gallery: ' + group)
        manifest = json.loads(blob(tree[name]))
        cases = manifest.get('cases', [])
        if not cases: raise ValueError('Empty committed gallery: ' + group)
        if group in ('axes', 'compositions', 'showcase') and {case['size'] for case in cases} != REQUESTED_SIZES:
            raise ValueError('Requested terminal sizes are missing: ' + group)


def build(output):
    revision = git('rev-parse', 'HEAD').decode().strip()
    if git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Commit all tracked source and generated evidence before packaging')
    tree = committed_tree()
    version_match = re.search(rb"^VERSION = ['\"](\d+\.\d+\.\d+-alpha\.\d+)['\"]$", blob(tree['motd.py']), re.MULTILINE)
    if not version_match: raise ValueError('Release builder requires an explicit committed x.y.z-alpha.n version')
    version = version_match[1].decode('ascii')
    subprocess.run([sys.executable, 'tools/embed_runtime.py', '--check'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/embed_toml.py', '--check'], cwd=ROOT, check=True)
    validate_galleries(tree)
    source = []; gallery = []
    for name in tree:
        if name.startswith('gallery/'):
            gallery.append(name)
        elif name in ('motd.py', 'README.md', 'CHANGELOG.md', 'ROADMAP.md', 'TODO.md', 'AGENTS.md', 'requirements-dev.txt') or name.startswith(('runtime/', 'presets/', 'docs/', 'specs/', 'vendor/', 'tools/', 'tests/')):
            source.append(name)
        elif Path(name).parent == Path('examples'):
            source.append(name)
    timestamp = int(git('show', '-s', '--format=%ct', revision).decode())
    timestamp = min(4354819198, max(315532800, timestamp))  # ZIP supports 1980..2107.
    dt = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    zip_time = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second // 2 * 2)
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    assets = []
    for label, files in [('motd', source), ('motd-gallery', gallery)]:
        path = output / (label + '-' + version + '.zip')
        hashes = {}
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(files):
                data = blob(tree[name]); hashes[name] = hashlib.sha256(data).hexdigest()
                info = zipfile.ZipInfo(name, date_time=zip_time)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_STORED if name.endswith('.png') else zipfile.ZIP_DEFLATED
                info.external_attr = int(tree[name][0], 8) << 16
                archive.writestr(info, data, compresslevel=9)
            info = zipfile.ZipInfo('RELEASE.json', date_time=zip_time)
            info.create_system = 3; info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, json.dumps({'version': version, 'revision': revision,
                                             'files': hashes}, indent=2) + '\n', compresslevel=9)
        with zipfile.ZipFile(path) as archive:
            if archive.testzip(): raise ValueError('Archive CRC verification failed: ' + path.name)
        assets.append({'name': path.name, 'bytes': path.stat().st_size,
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'files': len(files)})
    (output / 'SHA256SUMS').write_text(''.join(item['sha256'] + '  ' + item['name'] + '\n' for item in assets), encoding='utf-8')
    record = {'version': version, 'revision': revision, 'assets': assets,
              'packaging': {'source': 'committed Git blobs and recorded modes',
                            'python': platform.python_version(), 'zlib': zlib.ZLIB_RUNTIME_VERSION,
                            'zip_deflate_level': 9, 'timestamps': 'commit time (ZIP 2-second precision)'}}
    (output / 'release.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='dist')
    build(parser.parse_args().output)
