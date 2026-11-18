#!/usr/bin/env python3
"""Upload and verify an owned draft before making an alpha release public.

GitHub has no transaction spanning refs, assets and publication. This publisher
rechecks the exact main/tag immediately before publication, never moves a tag,
and leaves any incomplete upload in a resumable draft. Existing public releases
are verified and preserved, never silently accepted when assets are missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote

from release_gate import GitHub, GateBlocked, ref_commit, verified_revision

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_assets(folder, version, revision):
    folder = Path(folder)
    record = json.loads((folder / 'release.json').read_text(encoding='utf-8'))
    if record['version'] != version or record['revision'] != revision:
        raise GateBlocked('Assets belong to another version or commit')
    expected = {'motd-' + version + '.zip', 'motd-gallery-' + version + '.zip'}
    if {item['name'] for item in record['assets']} != expected or len(record['assets']) != 2:
        raise GateBlocked('Release must contain exactly the source and gallery ZIPs')
    result = {}
    for item in record['assets']:
        path = folder / item['name']
        if path.is_symlink() or not path.is_file() or digest(path) != item['sha256'] or path.stat().st_size != item['bytes']:
            raise GateBlocked('Local release asset failed verification: ' + item['name'])
        result[item['name']] = {'path': path, 'sha256': item['sha256'], 'bytes': item['bytes']}
    checksums = ''.join(item['sha256'] + '  ' + item['name'] + '\n' for item in record['assets'])
    if (folder / 'SHA256SUMS').read_text(encoding='utf-8') != checksums:
        raise GateBlocked('SHA256SUMS differs from release.json')
    for name in ('SHA256SUMS', 'release.json'):
        path = folder / name
        if path.is_symlink(): raise GateBlocked('Release metadata must be regular files')
        result[name] = {'path': path, 'sha256': digest(path), 'bytes': path.stat().st_size}
    return result


def release_for_tag(client, tag):
    # Authenticated list includes drafts, including an interrupted previous run.
    for page in range(1, 101):
        releases = client.get('/releases?per_page=100&page=' + str(page))
        matches = [release for release in releases if release['tag_name'] == tag]
        if len(matches) > 1: raise GateBlocked('Multiple releases claim the alpha tag')
        if matches: return matches[0]
        if len(releases) < 100: return None
    raise GateBlocked('Release list exceeded the inspection limit')


def ensure_tag(client, tag, revision):
    observed = ref_commit(client, 'tags/' + tag, optional=True)
    if observed is None:
        try:
            client.request('POST', '/git/refs', payload={'ref': 'refs/tags/' + tag, 'sha': revision})
        except HTTPError as exc:
            if exc.code != 422: raise
        observed = ref_commit(client, 'tags/' + tag)
    if observed != revision:
        raise GateBlocked('Alpha tag was created or moved to another revision; refusing to change it')


def remote_assets(client, release_id):
    result = []
    for page in range(1, 101):
        items = client.get('/releases/' + str(release_id) + '/assets?per_page=100&page=' + str(page))
        result.extend(items)
        if len(items) < 100: return result
    raise GateBlocked('Asset list exceeded the inspection limit')


def check_asset(client, asset, expected):
    if asset.get('state') != 'uploaded' or asset['size'] != expected['bytes']:
        raise GateBlocked('Release asset is incomplete: ' + asset['name'])
    observed = asset.get('digest') or client.download_digest(asset['id'])
    if observed != 'sha256:' + expected['sha256']:
        raise GateBlocked('Release asset hash differs: ' + asset['name'])


def verify_assets(client, release_id, expected):
    assets = remote_assets(client, release_id)
    if len(assets) != len(expected) or {asset['name'] for asset in assets} != set(expected):
        raise GateBlocked('Release asset set is incomplete or contains unexpected files')
    for asset in assets: check_asset(client, asset, expected[asset['name']])


def publish(client, folder, version, revision, notes, *, event_sha=None):
    if not re.fullmatch(r'\d+\.\d+\.\d+-alpha\.\d+', version):
        raise GateBlocked('Publisher requires an explicit alpha version')
    assets = local_assets(folder, version, revision)
    manifest = {name: {key: item[key] for key in ('sha256', 'bytes')} for name, item in assets.items()}
    manifest_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    provenance = '<!-- motd-release-source:' + revision + ';assets:' + manifest_hash + ' -->'
    tag = 'v' + version
    verified_revision(client, revision, event_sha=event_sha)
    ensure_tag(client, tag, revision)
    release = release_for_tag(client, tag)
    if release is None:
        release = client.request('POST', '/releases', payload={
            'tag_name': tag, 'target_commitish': revision, 'name': 'MOTD ' + version,
            'body': notes.rstrip() + '\n\n' + provenance + '\n', 'draft': True, 'prerelease': True})
    if release['tag_name'] != tag or not release.get('prerelease'):
        raise GateBlocked('Existing release has conflicting metadata')
    release_id = release['id']
    if not release['draft']:
        verify_assets(client, release_id, assets)
        if ref_commit(client, 'tags/' + tag) != revision:
            raise GateBlocked('Published alpha tag no longer matches its assets')
        return {'status': 'already-published-and-verified', 'url': release['html_url'], 'revision': revision}
    if provenance not in (release.get('body') or ''):
        raise GateBlocked('Existing draft does not match these exact source and asset hashes')
    existing = remote_assets(client, release_id)
    names = [asset['name'] for asset in existing]
    if len(names) != len(set(names)) or set(names) - set(assets):
        raise GateBlocked('Owned draft contains duplicate or unexpected assets')
    for asset in existing:
        if asset.get('state') == 'starter' and asset['size'] == 0:
            # GitHub can leave a zero-byte starter after an interrupted upload.
            # Only this exact owned draft and expected filename may be repaired.
            client.request('DELETE', '/releases/assets/' + str(asset['id']))
        else:
            check_asset(client, asset, assets[asset['name']])
    uploaded = {asset['name'] for asset in remote_assets(client, release_id)}
    for name, item in assets.items():
        if name in uploaded: continue
        content_type = 'application/zip' if name.endswith('.zip') else 'application/json' if name.endswith('.json') else 'text/plain'
        client.request('POST', '/releases/' + str(release_id) + '/assets?name=' + quote(name, safe=''),
                       data=item['path'].read_bytes(), content_type=content_type)
    verify_assets(client, release_id, assets)
    # These reads happen after uploads; stale checkout refs cannot authorize a
    # later tag/main change. Concurrent privileged edits are detected, not forced.
    verified_revision(client, revision, event_sha=event_sha)
    if ref_commit(client, 'tags/' + tag) != revision:
        raise GateBlocked('Alpha tag moved during upload; draft remains unpublished')
    current = client.get('/releases/' + str(release_id))
    if current['tag_name'] != tag or provenance not in (current.get('body') or ''):
        raise GateBlocked('Draft ownership changed during upload')
    if not current['draft']:
        verify_assets(client, release_id, assets)
        return {'status': 'already-published-and-verified', 'url': current['html_url'], 'revision': revision}
    release = client.request('PATCH', '/releases/' + str(release_id),
                             payload={'draft': False, 'prerelease': True, 'make_latest': 'false'})
    try:
        if release['draft'] or ref_commit(client, 'tags/' + tag) != revision:
            raise GateBlocked('Publication did not preserve the verified revision')
        verify_assets(client, release_id, assets)
    except GateBlocked:
        # Withdraw only the draft this invocation just published; never move or
        # delete a tag, or replace the bytes of a public release.
        client.request('PATCH', '/releases/' + str(release_id), payload={'draft': True})
        raise
    return {'status': 'published', 'url': release['html_url'], 'revision': revision}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', default='dist')
    parser.add_argument('--notes', required=True)
    arguments = parser.parse_args()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    client = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN'])
    result = publish(client, Path(arguments.assets), motd.VERSION, revision,
                     Path(arguments.notes).read_text(encoding='utf-8'), event_sha=os.environ.get('EVENT_SHA'))
    print(json.dumps(result, indent=2))
