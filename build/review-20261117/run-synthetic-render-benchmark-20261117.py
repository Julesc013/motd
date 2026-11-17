"""Bounded fresh-process synthetic rendering measurements; no login attachment."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path('/workspace/scratch/e6a94ceb1ad8/motd')
WORK = Path('/workspace/scratch/e6a94ceb1ad8/work')
OUTPUT = WORK / 'synthetic-render-benchmark-20261117.json'
ARTIFACTS = WORK / 'synthetic-render-benchmark-artifacts'
PWSH = WORK / 'powershell/7.6.10/pwsh'
EXPECTED_SOURCE = 'eda912a538325d00f798dc969f8da4389f5c34ad5d4d13f2caba99087622a130'
START = time.monotonic()
DEADLINE = START + 60


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args):
    remaining = DEADLINE - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Overall benchmark deadline reached')
    return subprocess.run(args, capture_output=True, timeout=min(8, remaining),
                          cwd=ROOT, env=dict(os.environ, NO_COLOR='1', TERM='dumb'))


def checked_text(args):
    result = command(args)
    assert result.returncode == 0, (args, result.returncode, result.stderr.decode(errors='replace'))
    assert not result.stderr, (args, result.stderr.decode(errors='replace'))
    return result.stdout.decode('utf-8').strip()


def save():
    OUTPUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


assert digest(ROOT / 'motd.py') == EXPECTED_SOURCE
ARTIFACTS.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location('motd_benchmark_subject', ROOT / 'motd.py')
motd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motd)
os_release = {}
for line in Path('/etc/os-release').read_text().splitlines():
    if '=' in line:
        key, value = line.split('=', 1)
        os_release[key] = value.strip('"')
cpu_model = next((line.split(':', 1)[1].strip() for line in
                  Path('/proc/cpuinfo').read_text().splitlines()
                  if line.startswith('model name')), 'unavailable')
report = {
    'status': 'running',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'git_commit': checked_text(['git', 'rev-parse', 'HEAD']),
    'git_source_blob': checked_text(['git', 'hash-object', 'motd.py']),
    'generator_sha256': EXPECTED_SOURCE,
    'runtime_sha256': {str(p.relative_to(ROOT)): digest(p) for p in
                       (ROOT/'runtime/designs.sh', ROOT/'runtime/motd.bash',
                        ROOT/'runtime/motd.sh', ROOT/'runtime/motd.ps1')},
    'host': {'os_release': os_release, 'platform': platform.platform(),
             'machine': platform.machine(), 'cpu_model': cpu_model,
             'logical_cpus': os.cpu_count()},
    'python': {'executable': sys.executable, 'version': sys.version},
    'settings': {'preset': 'home-lab', 'design': 'cards', 'density': 'comfortable',
                 'detail': 'brief', 'bar_layout': 'wide', 'width': 80, 'rows': 25,
                 'charset': 'ascii', 'color': 'never', 'hooks': {'before': [], 'after': []}},
    'method': {'warmup_invocations_per_route': 1, 'measured_invocations_per_route': 20,
               'clock': 'time.perf_counter_ns, elapsed wall time in milliseconds',
               'interval': 'Immediately before subprocess.run until process exit and stdout/stderr capture complete',
               'p95': 'Nearest rank: sorted[ceil(0.95*n)-1]; rank 19 of 20',
               'per_process_timeout_seconds': 8, 'overall_timeout_seconds': 60,
               'cache_state': 'Each invocation is a fresh process; one discarded warmup precedes each route. OS caches are warmed, not true cold boot.',
               'execution': 'Sequential routes and invocations; exclusive host scheduling was not controlled.',
               'scope': 'Synthetic generated-artifact rendering plus interpreter startup and output capture; no live observations, hook execution or installation.',
               'exclusions': ['CLI preview was not measured', 'Interactive wizard redraw was not measured',
                              'Terminal painting, SSH/PAM transport and real login attachment were not measured',
                              'These observations do not establish the 100 ms live target or 400 ms controlled-stall target']},
    'routes': [],
}
dash_package = command(['dpkg-query', '-W', '-f=${Version}', 'dash'])
dash_version = ('dash ' + dash_package.stdout.decode().strip() if dash_package.returncode == 0
                else 'dash; package version unavailable in this host image, exact binary SHA256 recorded')
engines = [
    ('bash', shutil.which('bash'), checked_text(['bash', '--version']).splitlines()[0]),
    ('sh', '/bin/sh', dash_version),
    ('powershell', str(PWSH), checked_text([str(PWSH), '-NoLogo', '-NoProfile', '-NonInteractive',
                                          '-Command', '[Console]::WriteLine($PSVersionTable.PSVersion.ToString())'])),
]
try:
    for shell, executable, version in engines:
        config = motd.preset_config('home-lab', shell=shell)
        config['display'].update(design='cards', density='comfortable', detail='brief',
                                 bar_layout='wide', width=80, rows=25, charset='ascii', color='never')
        config['hooks'] = {'before': [], 'after': []}
        config = motd.validate_config(config)
        artifact = ARTIFACTS / ('home-lab' + motd.artifact_suffix(config))
        artifact.write_text(motd.generate_artifact(config), encoding='utf-8')
        if shell == 'powershell':
            args = [executable, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(artifact),
                    '-Demo', '-NoHooks', '-Width', '80', '-Rows', '25', '-Ascii', '-Plain']
        else:
            args = [executable, str(artifact), '--demo', '--no-hooks', '--width', '80',
                    '--rows', '25', '--ascii', '--plain']
        route = {'shell': shell, 'executable': executable, 'resolved_executable': os.path.realpath(executable),
                 'version': version, 'executable_sha256': digest(Path(executable)),
                 'command': args, 'artifact': str(artifact),
                 'artifact_sha256': digest(artifact), 'elapsed_ms': []}
        output_hashes = set()
        for index in range(21):
            before = time.perf_counter_ns()
            result = command(args)
            elapsed = (time.perf_counter_ns() - before) / 1_000_000
            assert result.returncode == 0, (shell, index, result.returncode, result.stderr.decode(errors='replace'))
            assert not result.stderr, (shell, index, result.stderr.decode(errors='replace'))
            assert result.stdout and result.stdout.isascii() and b'\x1b' not in result.stdout
            output_hashes.add(hashlib.sha256(result.stdout).hexdigest())
            if index == 0:
                route['warmup_ms'] = elapsed
                route['stdout_bytes'] = len(result.stdout)
                route['stdout_lines'] = len(result.stdout.splitlines())
                (ARTIFACTS / (shell + '-demo.txt')).write_bytes(result.stdout)
            else:
                route['elapsed_ms'].append(elapsed)
        values = route['elapsed_ms']
        route['summary_ms'] = {'median': statistics.median(values),
                               'p95_nearest_rank': sorted(values)[math.ceil(.95*len(values))-1],
                               'min': min(values), 'max': max(values)}
        route['measured_invocations'] = len(values)
        route['stdout_sha256_values'] = sorted(output_hashes)
        route['all_exit_zero'] = True
        route['all_stderr_empty'] = True
        report['routes'].append(route)
        save()
    assert digest(ROOT/'motd.py') == EXPECTED_SOURCE, 'Source changed during benchmark'
    report['status'] = 'complete'
except BaseException as exc:
    report['status'] = 'failed'
    report['error'] = type(exc).__name__ + ': ' + str(exc)
    raise
finally:
    report['total_runner_seconds'] = time.monotonic() - START
    report['runner_sha256'] = digest(Path(__file__))
    save()
print(json.dumps({'status': report['status'], 'total_runner_seconds': report['total_runner_seconds'],
                  'routes': [{k: row[k] for k in ('shell','version','warmup_ms','measured_invocations','summary_ms')}
                             for row in report['routes']]}, indent=2))
