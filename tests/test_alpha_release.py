"""Release ownership, interrupted upload, native evidence and archive contracts."""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_release
import publish_alpha
import release_gate

REVISION = 'a' * 40
OTHER = 'b' * 40
VERSION = '0.5.0-alpha.1'
TAG = 'v' + VERSION


class FakeGitHub:
    repository = 'example/motd'

    def __init__(self):
        self.main = REVISION; self.tag = None; self.release = None
        self.assets = []; self.events = []; self.fail_upload = None; self.change_main_after_upload = False
        self.change_tag_after_upload = False; self.native_step = 'success'
        self._counter = 0

    def optional(self, path):
        if path.startswith('/git/ref/tags/') and self.tag is None: return None
        return self.get(path)

    def get(self, path):
        if path == '/git/ref/heads/main':
            return {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': self.main}}
        if path.startswith('/git/ref/tags/'):
            return {'ref': 'refs/tags/' + TAG, 'object': {'type': 'commit', 'sha': self.tag}}
        if path.startswith('/actions/runs?'):
            return {'workflow_runs': [{'path': path, 'head_sha': REVISION, 'head_branch': 'main',
                'event': 'push', 'repository': {'full_name': self.repository}, 'run_number': i,
                'conclusion': 'success', 'id': i} for i, path in enumerate(
                    ('.github/workflows/ci.yml', '.github/workflows/powershell-compatibility.yml'), 1)]}
        if path.startswith('/actions/runs/2/jobs?'):
            return {'jobs': [{'name': 'actual-powershell-2', 'conclusion': 'success',
                'steps': [{'name': 'Execute and record the actual PowerShell2 engine', 'conclusion': self.native_step}]}]}
        if path.startswith('/releases?'): return [copy.deepcopy(self.release)] if self.release else []
        if path.startswith('/releases/7/assets?'): return copy.deepcopy(self.assets)
        if path == '/releases/7': return copy.deepcopy(self.release)
        raise AssertionError(path)

    def request(self, method, path, *, payload=None, data=None, content_type=None):
        self.events.append((method, path, copy.deepcopy(payload)))
        if method == 'POST' and path == '/git/refs':
            self.tag = payload['sha']; return {}
        if method == 'POST' and path == '/releases':
            self.release = dict(payload, id=7, html_url='https://github.com/example/motd/releases/tag/' + TAG)
            return copy.deepcopy(self.release)
        if method == 'POST' and path.startswith('/releases/7/assets?name='):
            name = path.split('name=', 1)[1]
            if self.fail_upload == name: raise OSError('Connection lost during upload')
            self._counter += 1
            self.assets.append({'name': name, 'id': self._counter, 'size': len(data),
                                'state': 'uploaded', 'digest': 'sha256:' + hashlib.sha256(data).hexdigest()})
            if self.change_main_after_upload: self.main = OTHER
            if self.change_tag_after_upload: self.tag = OTHER
            return copy.deepcopy(self.assets[-1])
        if method == 'PATCH' and path == '/releases/7':
            self.release.update(payload); return copy.deepcopy(self.release)
        if method == 'DELETE' and path.startswith('/releases/assets/'):
            asset_id = int(path.rsplit('/', 1)[1])
            self.assets = [asset for asset in self.assets if asset['id'] != asset_id]; return None
        raise AssertionError((method, path))

    def download_digest(self, asset_id):
        raise AssertionError('Unexpected asset download')


class AlphaLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='motd-release-test-')
        self.addCleanup(temporary.cleanup); self.folder = Path(temporary.name)
        assets = []
        for name in ('motd-' + VERSION + '.zip', 'motd-gallery-' + VERSION + '.zip'):
            data = name.encode(); (self.folder / name).write_bytes(data)
            assets.append({'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        (self.folder / 'release.json').write_text(json.dumps({'version': VERSION, 'revision': REVISION, 'assets': assets}))
        (self.folder / 'SHA256SUMS').write_text(''.join(item['sha256'] + '  ' + item['name'] + '\n' for item in assets))
        self.api = FakeGitHub()

    def publish(self):
        return publish_alpha.publish(self.api, self.folder, VERSION, REVISION, 'Verified alpha notes')

    def test_publish_happens_only_after_complete_draft_verification(self):
        result = self.publish()
        self.assertEqual(result['status'], 'published')
        self.assertFalse(self.api.release['draft'])
        self.assertEqual(len(self.api.assets), 4)
        updates = [event for event in self.api.events if event[0] == 'PATCH']
        self.assertEqual(updates, [('PATCH', '/releases/7', {'draft': False, 'prerelease': True, 'make_latest': 'false'})])
        before = list(self.api.events)
        self.assertEqual(self.publish()['status'], 'already-published-and-verified')
        self.assertEqual(self.api.events, before, 'A verified published release must remain untouched')

    def test_interrupted_upload_stays_draft_and_rerun_finishes_only_missing_assets(self):
        self.api.fail_upload = 'SHA256SUMS'
        with self.assertRaisesRegex(OSError, 'Connection lost'): self.publish()
        self.assertTrue(self.api.release['draft'])
        self.assertEqual(len(self.api.assets), 2)
        first_assets = copy.deepcopy(self.api.assets)
        self.api.fail_upload = None
        self.publish()
        self.assertEqual(self.api.assets[:2], first_assets)
        self.assertEqual(len(self.api.assets), 4)
        self.assertFalse(self.api.release['draft'])

    def test_partial_public_release_is_rejected_without_overwrite(self):
        self.publish(); self.api.assets.pop()
        before = list(self.api.events)
        with self.assertRaisesRegex(release_gate.GateBlocked, 'asset set'): self.publish()
        self.assertEqual(self.api.events, before)
        self.assertFalse(self.api.release['draft'])

    def test_wrong_existing_tag_is_never_moved(self):
        self.api.tag = OTHER
        with self.assertRaisesRegex(release_gate.GateBlocked, 'tag was created or moved'): self.publish()
        self.assertEqual(self.api.tag, OTHER)
        self.assertEqual(self.api.events, [])

    def test_main_advancing_during_upload_keeps_draft_private(self):
        self.api.change_main_after_upload = True
        with self.assertRaisesRegex(release_gate.GateBlocked, 'Main advanced'): self.publish()
        self.assertTrue(self.api.release['draft'])
        self.assertFalse(any(event[0] == 'PATCH' for event in self.api.events))

    def test_tag_moving_during_upload_keeps_draft_private(self):
        self.api.change_tag_after_upload = True
        with self.assertRaisesRegex(release_gate.GateBlocked, 'tag moved during upload'): self.publish()
        self.assertTrue(self.api.release['draft'])
        self.assertEqual(self.api.tag, OTHER)

    def test_skipped_native_engine_is_not_a_successful_compatibility_pass(self):
        self.api.native_step = 'skipped'
        with self.assertRaisesRegex(release_gate.GateBlocked, 'PowerShell2'): self.publish()
        self.assertEqual(self.api.events, [])

    def test_stale_workflow_event_cannot_authorize_current_source(self):
        with self.assertRaisesRegex(release_gate.GateBlocked, 'another revision'):
            release_gate.verified_revision(self.api, REVISION, event_sha=OTHER)

    def test_changed_uploaded_asset_is_rejected_without_deleting_it(self):
        self.api.fail_upload = 'SHA256SUMS'
        with self.assertRaises(OSError): self.publish()
        self.api.fail_upload = None
        self.api.assets[0]['digest'] = 'sha256:' + '0' * 64
        before = copy.deepcopy(self.api.assets)
        with self.assertRaisesRegex(release_gate.GateBlocked, 'hash differs'): self.publish()
        self.assertEqual(self.api.assets, before)
        self.assertTrue(self.api.release['draft'])

    def test_zero_byte_starter_is_repaired_only_in_owned_draft(self):
        self.api.fail_upload = 'SHA256SUMS'
        with self.assertRaises(OSError): self.publish()
        self.api.fail_upload = None
        self.api.assets.append({'id': 99, 'name': 'SHA256SUMS', 'size': 0, 'state': 'starter'})
        self.publish()
        self.assertIn(('DELETE', '/releases/assets/99', None), self.api.events)
        self.assertFalse(self.api.release['draft'])

    def test_unowned_draft_is_never_changed(self):
        self.api.tag = REVISION
        self.api.release = {'id': 7, 'tag_name': TAG, 'draft': True, 'prerelease': True, 'body': 'Manual draft'}
        with self.assertRaisesRegex(release_gate.GateBlocked, 'Existing draft'): self.publish()
        self.assertEqual(self.api.events, [])

    def test_cross_host_download_redirect_drops_credentials(self):
        handler = release_gate.CredentialSafeRedirect()
        request = Request('https://api.github.com/asset', headers={'Authorization': 'Bearer secret'})
        redirected = handler.redirect_request(request, None, 302, 'Found', {}, 'https://assets.example.test/data')
        self.assertIsNone(redirected.get_header('Authorization'))
        with self.assertRaises(release_gate.GateBlocked):
            handler.redirect_request(request, None, 302, 'Found', {}, 'http://assets.example.test/data')


class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='motd-package-test-')
        self.addCleanup(temporary.cleanup); self.folder = Path(temporary.name)
        self.root = self.folder / 'repo'; self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.email', 'release-test@example.test'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.name', 'Release test'], check=True)
        files = {'motd.py': "VERSION = '" + VERSION + "'\n", 'README.md': 'Example package\n',
                 'tests/test_example.py': 'assert True\n', 'tools/embed_runtime.py': 'pass\n',
                 'tools/embed_toml.py': 'pass\n', 'examples/workshop.bash': '#!/bin/sh\nprintf hi\n',
                 'gallery/index.html': '<h1>Gallery</h1>'}
        for group in build_release.GALLERY_GROUPS:
            files['gallery/' + group + '/manifest.json'] = json.dumps({'cases': [{'size': size} for size in sorted(build_release.REQUESTED_SIZES)]})
        for name, data in files.items():
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(data)
        (self.root / 'examples/workshop.bash').chmod(0o755)
        self.git('add', '.'); self.git('commit', '-qm', 'Package fixture')
        self.context = patch.object(build_release, 'ROOT', self.root)
        self.context.__enter__(); self.addCleanup(self.context.__exit__, None, None, None)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args])

    def test_package_repeats_and_uses_git_modes_not_local_filesystem(self):
        # Ignore a local chmod in Git's dirty-worktree check; committed mode must
        # still be used in the ZIP instead of whichever host built the package.
        self.git('config', 'core.filemode', 'false')
        (self.root / 'examples/workshop.bash').chmod(0o644)
        (self.root / 'untracked-secret.txt').write_text('Not an input')
        with redirect_stdout(io.StringIO()):
            a = build_release.build(self.folder / 'first')
            b = build_release.build(self.folder / 'second')
        self.assertEqual(a, b)
        for asset in a['assets']:
            self.assertEqual((self.folder/'first'/asset['name']).read_bytes(), (self.folder/'second'/asset['name']).read_bytes())
        with zipfile.ZipFile(self.folder/'first'/('motd-' + VERSION + '.zip')) as archive:
            self.assertIn('tests/test_example.py', archive.namelist())
            self.assertNotIn('untracked-secret.txt', archive.namelist())
            self.assertEqual(archive.getinfo('examples/workshop.bash').external_attr >> 16, 0o100755)
            proof = json.loads(archive.read('RELEASE.json'))
            for name, expected in proof['files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)

    def test_missing_committed_gallery_blocks_packaging(self):
        self.git('rm', '-q', 'gallery/axes/manifest.json'); self.git('commit', '-qm', 'Remove required gallery')
        with self.assertRaisesRegex(ValueError, 'Missing committed gallery'):
            build_release.build(self.folder/'output')

    def test_tracked_working_changes_cannot_leak_into_release(self):
        (self.root/'motd.py').write_text("VERSION = '9.9.9-alpha.1'\n")
        with self.assertRaisesRegex(ValueError, 'Commit all tracked'):
            build_release.build(self.folder/'output')


if __name__ == '__main__': unittest.main()
