#!/usr/bin/env python3
"""Read-only release gate for the exact main revision and actual native evidence."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motd


class GateBlocked(ValueError):
    """A release condition is not satisfied; never mutate a ref to fix it."""


class CredentialSafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise GateBlocked('Release download redirected outside HTTPS')
        result = super().redirect_request(request, fp, code, message, headers, newurl)
        if result is not None and urlsplit(request.full_url).netloc != urlsplit(newurl).netloc:
            result.remove_header('Authorization')
        return result


class GitHub:
    """Small repository-scoped client used by the gate and draft publisher."""
    def __init__(self, repository, token):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Expected owner/repository')
        self.repository = repository
        self.token = token
        self.opener = build_opener(CredentialSafeRedirect())

    def request(self, method, path, *, payload=None, data=None, content_type=None):
        base = 'https://uploads.github.com' if data is not None else 'https://api.github.com'
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'motd-alpha-publisher'}
        if payload is not None:
            data = json.dumps(payload).encode('utf-8'); headers['Content-Type'] = 'application/json'
        elif content_type:
            headers['Content-Type'] = content_type
        request = Request(base + '/repos/' + self.repository + path, data=data, headers=headers, method=method)
        with self.opener.open(request, timeout=120) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    def get(self, path):
        return self.request('GET', path)

    def optional(self, path):
        try: return self.get(path)
        except HTTPError as exc:
            if exc.code == 404: return None
            raise

    def download_digest(self, asset_id):
        import hashlib
        request = Request('https://api.github.com/repos/' + self.repository + '/releases/assets/' + str(asset_id),
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/octet-stream',
                     'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'motd-alpha-publisher'})
        digest = hashlib.sha256()
        with self.opener.open(request, timeout=120) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b''): digest.update(chunk)
        return 'sha256:' + digest.hexdigest()


def ref_commit(client, ref, *, optional=False):
    data = client.optional('/git/ref/' + ref) if optional else client.get('/git/ref/' + ref)
    if data is None: return None
    if data.get('ref') != 'refs/' + ref:
        raise GateBlocked('GitHub returned a different ref: ' + ref)
    obj = data['object']; visited = set()
    while obj['type'] == 'tag':
        if obj['sha'] in visited or len(visited) >= 8:
            raise GateBlocked('Invalid nested annotated release tag')
        visited.add(obj['sha']); obj = client.get('/git/tags/' + obj['sha'])['object']
    if obj['type'] != 'commit': raise GateBlocked('Release ref does not identify a commit')
    return obj['sha']


def verified_revision(client, sha, *, event_sha=None):
    if event_sha and event_sha != sha:
        raise GateBlocked('Triggering workflow belongs to another revision')
    if ref_commit(client, 'heads/main') != sha:
        raise GateBlocked('Main advanced; the next verified revision must publish')
    expected = ('.github/workflows/ci.yml', '.github/workflows/powershell-compatibility.yml')
    runs = client.get('/actions/runs?head_sha=' + sha + '&per_page=100')['workflow_runs']
    verified = {}
    for workflow in expected:
        matching = [run for run in runs if run['path'] == workflow and run['head_sha'] == sha
                    and run['head_branch'] == 'main' and run['event'] == 'push'
                    and run['repository']['full_name'] == client.repository]
        latest = max(matching, key=lambda run: (run['run_number'], run.get('run_attempt', 1))) if matching else None
        if latest is None or latest['conclusion'] != 'success':
            raise GateBlocked('Current successful main run is missing: ' + workflow)
        verified[workflow] = latest
    run = verified['.github/workflows/powershell-compatibility.yml']
    jobs = client.get('/actions/runs/' + str(run['id']) + '/jobs?filter=latest&per_page=100')['jobs']
    if not any(job.get('name') == 'actual-powershell-2' and job['conclusion'] == 'success'
               and any(step['name'] == 'Execute and record the actual PowerShell2 engine'
                       and step['conclusion'] == 'success' for step in job['steps']) for job in jobs):
        raise GateBlocked('The actual PowerShell2 execution step did not pass')
    return verified


def main():
    if not re.fullmatch(r'\d+\.\d+\.\d+-alpha\.\d+', motd.VERSION):
        print('ready=false'); return
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    client = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN'])
    try:
        verified_revision(client, sha, event_sha=os.environ.get('EVENT_SHA'))
        tagged = ref_commit(client, 'tags/v' + motd.VERSION, optional=True)
        if tagged is not None and tagged != sha:
            raise GateBlocked('Existing alpha tag points elsewhere; bump the version')
    except GateBlocked as exc:
        print(str(exc), file=sys.stderr); print('ready=false'); return
    print('ready=true')


if __name__ == '__main__': main()
