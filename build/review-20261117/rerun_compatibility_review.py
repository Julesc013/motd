"""Replay the bounded release-candidate checks; all writes stay in scratch.

Usage: python work/rerun_compatibility_review.py --expected-source SHA256
No package installation, profile attachment or repository mutation occurs.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent / 'motd'
PRIOR = Path('/workspace/scratch/c65930e4593e/work')
BASE = PRIOR / 'unix-extra-engines'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(name, record):
    (WORK / name).write_text(json.dumps(record, indent=2) + '\n')


def assert_source(expected):
    actual = digest(ROOT / 'motd.py')
    assert actual == expected, ('Generator changed during verification', expected, actual)


def archive_previous():
    folder = WORK / 'compatibility-1639-lineage'
    folder.mkdir(exist_ok=True)
    names = ['compatibility-review-final.json', 'unix-compatibility-frozen.json',
             'python38-lifecycle-frozen.json', 'legacy-version-final-evidence.json',
             'bash32-startup-frozen.json', 'unix-shell-guards-frozen.log',
             'unix-fish-startup-frozen.log']
    names += [p.name for p in WORK.glob('python38-frozen-*.log')]
    for name in names:
        source = WORK / name
        destination = folder / name
        if source.exists() and not destination.exists():
            shutil.copy2(source, destination)
    return folder


def unix_matrix(motd, expected):
    folder = WORK / 'unix-final-inputs'
    folder.mkdir(exist_ok=True)
    bash = WORK / 'bash-3.2-build/bash-3.2/bash'
    engines = [
        ('bash3.2-dispatch', 'bash', [str(bash)], [str(bash), '--version']),
        ('bash3.2-portable', 'sh', [str(bash)], [str(bash), '--version']),
        ('dash', 'sh', ['/usr/bin/dash'], ['dpkg-query', '-W', '-f=${Version}', 'dash']),
        ('busybox-ash', 'sh', [str(BASE / 'busybox/usr/bin/busybox'), 'ash'],
         [str(BASE / 'busybox/usr/bin/busybox')]),
        ('mksh', 'sh', [str(BASE / 'mksh/usr/bin/mksh')],
         [str(BASE / 'mksh/usr/bin/mksh'), '-c', 'echo "$KSH_VERSION"']),
        ('ksh93', 'sh', [str(BASE / 'ksh/usr/bin/ksh93')],
         [str(BASE / 'ksh/usr/bin/ksh93'), '-c', 'echo "$KSH_VERSION"']),
        ('fish2', 'fish', [str(BASE / 'fish2/usr/bin/fish')],
         [str(BASE / 'fish2/usr/bin/fish'), '--version']),
        ('fish3', 'fish', [str(BASE / 'fish3/usr/bin/fish')],
         [str(BASE / 'fish3/usr/bin/fish'), '--version']),
        ('fish4', 'fish', [str(BASE / 'fish4/usr/bin/fish'), '--no-config'],
         [str(BASE / 'fish4/usr/bin/fish'), '--version']),
    ]
    names = ['motd.py', 'runtime/motd.bash', 'runtime/motd.sh', 'runtime/designs.sh']
    start = {name: digest(ROOT / name) for name in names}
    marker = folder / 'unexpected-hook'
    assert not marker.exists(), 'A prior marker must not be silently removed'
    artifacts = {}
    for shell in ('bash', 'sh', 'fish'):
        for design in motd.DESIGNS:
            for bars in ('inline', 'wide'):
                config = motd.preset_config('workshop', shell=shell)
                config['display'].update(design=design, bar_layout=bars,
                                         sections=list(motd.SECTION_IDS))
                config['hooks']['before'] = [{'argv': ['/bin/sh', '-c', ': > ' + str(marker)],
                                              'timeout_seconds': 1, 'on_failure': 'stop'}]
                path = folder / (shell + '-' + design + '-' + bars + motd.artifact_suffix(config))
                path.write_text(motd.generate_artifact(config), encoding='utf-8')
                artifacts[(shell, design, bars)] = path
    results, probes, failures = [], [], []
    for label, shell, command, probe in engines:
        env = dict(os.environ, TERM='xterm-256color', LC_ALL='C.UTF-8')
        if label == 'fish2':
            env['LD_LIBRARY_PATH'] = str(BASE / 'fish2-libraries/lib/x86_64-linux-gnu')
        p = subprocess.run(probe, capture_output=True, text=True, timeout=10, env=env)
        probes.append({'engine': label, 'command': command,
                       'version_stdout': p.stdout.splitlines()[0] if p.stdout else '',
                       'version_stderr': p.stderr.splitlines()[0] if p.stderr else '',
                       'executable_sha256': digest(command[0]),
                       'environment': {k: env[k] for k in ('TERM', 'LC_ALL', 'LD_LIBRARY_PATH') if k in env}})
        for design in motd.DESIGNS:
            for bars in ('inline', 'wide'):
                path = artifacts[(shell, design, bars)]
                for width, rows in ((40, 8), (40, 25), (80, 50), (81, 50)):
                    args = command + [str(path), '--demo-alerts', '--plain', '--ascii',
                                      '--width', str(width), '--rows', str(rows)]
                    began = time.monotonic()
                    p = subprocess.run(args, capture_output=True, text=True, timeout=15,
                                       env=env, cwd=folder)
                    elapsed = time.monotonic() - began
                    lines = p.stdout.splitlines()
                    maxwidth = max(map(len, lines), default=0)
                    ok = (p.returncode == 0 and p.stderr == '' and bool(lines)
                          and len(lines) <= rows - 1 and maxwidth <= width
                          and p.stdout.isascii() and '\x1b' not in p.stdout
                          and 'DEMO' in p.stdout and not marker.exists())
                    fraction = None
                    if design == 'cards' and bars == 'wide' and width == 80:
                        matches = re.findall(r'^\| ([#.]+) \|$', p.stdout, re.M)
                        if matches:
                            fraction = matches[0].count('#') / len(matches[0])
                            ok = ok and abs(fraction - .75) <= 1 / len(matches[0])
                        else:
                            ok = False
                    entry = {'engine': label, 'design': design, 'bar_layout': bars,
                             'width': width, 'rows': rows, 'exit_code': p.returncode,
                             'stderr': p.stderr, 'rendered_rows': len(lines),
                             'maximum_columns': maxwidth,
                             'stdout_sha256': hashlib.sha256(p.stdout.encode()).hexdigest(),
                             'seconds': round(elapsed, 4), 'passed': ok}
                    if fraction is not None:
                        entry['observed_memory_available_fraction'] = fraction
                    results.append(entry)
                    if not ok:
                        failures.append(dict(entry, stdout=p.stdout, command=args))
        print(label, sum(r['passed'] for r in results if r['engine'] == label), '/ 40', flush=True)
    record = {'recorded_at_utc': now(),
              'scope': 'Current Linux host. Real interpreters and generated artifacts; synthetic alerts, ASCII/plain, guarded hooks. Fish delegates to /bin/sh. Not original-OS verification.',
              'source_start_sha256': start,
              'source_end_sha256': {name: digest(ROOT / name) for name in names},
              'engines': probes,
              'artifact_sha256': {path.name: digest(path) for path in artifacts.values()},
              'cases': len(results), 'failed': len(failures), 'results': results,
              'failures': failures, 'marker_exists': marker.exists(),
              'verification_script': str(Path(__file__).resolve()),
              'verification_script_sha256': digest(__file__)}
    save('unix-compatibility-frozen.json', record)
    assert_source(expected)
    assert not failures, json.dumps(failures[:2], indent=2)


def python38_lifecycle(expected):
    python = PRIOR / 'python-runtimes/cpython-3.8.20-linux-x86_64-gnu/bin/python3.8'
    patterns = ['test_transactions.py', 'test_installation.py', 'test_output_lifecycle.py',
                'test_path_safety.py', 'test_portable_export.py']
    results = []
    for name in patterns:
        command = [str(python), '-m', 'unittest', 'discover', '-s', 'tests', '-p', name, '-v']
        p = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=120)
        log = WORK / ('python38-frozen-' + name[:-3] + '.log')
        log.write_text(p.stdout)
        count = re.search(r'Ran (\d+) tests? in', p.stdout)
        skips = re.search(r'OK \(skipped=(\d+)\)', p.stdout)
        results.append({'test_pattern': name, 'command': command, 'exit_code': p.returncode,
                        'tests_run': int(count.group(1)) if count else None,
                        'skipped': int(skips.group(1)) if skips else 0, 'log': str(log),
                        'test_source_sha256': digest(ROOT / 'tests' / name),
                        'output_sha256': digest(log)})
        print(name, p.returncode, flush=True)
    record = {'recorded_at_utc': now(),
              'python': subprocess.check_output([str(python), '--version'], text=True).strip(),
              'motd_source_start_sha256': expected, 'motd_source_end_sha256': digest(ROOT / 'motd.py'),
              'results': results, 'verification_script': str(Path(__file__).resolve()),
              'verification_script_sha256': digest(__file__)}
    save('python38-lifecycle-frozen.json', record)
    assert_source(expected)
    assert all(r['exit_code'] == 0 for r in results), results


def revalidate_powershell(motd, expected):
    path = WORK / 'legacy-version-final-evidence.json'
    record = json.loads(path.read_text())
    checks = {}
    for name, observed in record['artifact_sha256'].items():
        text = (WORK / 'legacy-final-inputs' / name).read_text(encoding='ascii')
        regenerated = motd.generate_artifact(motd.extract_config(text)).encode('ascii')
        actual = hashlib.sha256(regenerated).hexdigest()
        checks[name] = {'evidence_sha256': observed, 'final_generator_sha256': actual,
                        'matches': actual == observed}
    assert all(check['matches'] for check in checks.values()), checks
    if 'final_generator_revalidation' in record:
        record.setdefault('previous_generator_revalidations', []).append(record['final_generator_revalidation'])
    record['final_generator_revalidation'] = {
        'recorded_at_utc': now(), 'motd_sha256': expected,
        'powershell_runtime_sha256': digest(ROOT / 'runtime/motd.ps1'),
        'all_generated_artifacts_match': True,
        'reason': 'Subsequent changes were Unix-only embedding fixes. Every PowerShell input was regenerated from its own embedded recipe using this final generator and exactly matched the executed artifact bytes.',
        'artifacts': checks, 'verification_script': str(Path(__file__).resolve()),
        'verification_script_sha256': digest(__file__)}
    save(path.name, record)
    assert_source(expected)
    print('All 10 PowerShell artifact hashes still match', flush=True)


def update_index(expected, archive):
    path = WORK / 'compatibility-review-final.json'
    record = json.loads(path.read_text())
    record['recorded_at_utc'] = now()
    record['final_source_sha256'] = {name: digest(ROOT / name)
                                     for name in record['final_source_sha256']}
    for item in record['records'].values():
        item['sha256'] = digest(item['path'])
    record['latest_rerun'] = {'motd_sha256': expected, 'phases': ['unix360', 'python38_lifecycle59',
                                                               'powershell_artifact_hash_revalidation'],
                              'previous_record_directory': str(archive),
                              'script': str(Path(__file__).resolve()), 'script_sha256': digest(__file__),
                              'startup_and_ps_execution_lineage': 'Startup guards and actual PowerShell execution were not rerun for the Unix service-name parser correction. Their earlier source lineage remains in their original records; all PowerShell artifact bytes match the final generator.'}
    save(path.name, record)
    assert_source(expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--phase', choices=['all', 'unix', 'python38', 'revalidate-powershell'], default='all')
    args = parser.parse_args()
    assert_source(args.expected_source)
    previous = archive_previous()
    sys.path.insert(0, str(ROOT))
    import motd
    if args.phase in ('all', 'unix'):
        unix_matrix(motd, args.expected_source)
    if args.phase in ('all', 'python38'):
        python38_lifecycle(args.expected_source)
    if args.phase in ('all', 'revalidate-powershell'):
        revalidate_powershell(motd, args.expected_source)
    if args.phase == 'all':
        update_index(args.expected_source, previous)
