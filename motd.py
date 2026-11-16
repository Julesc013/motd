#!/usr/bin/env python3
"""MOTD: one configurator, reusable TOML recipes, standalone shell output.

Read this file in order: CONFIGURATION -> GENERATION -> INSTALLATION PLANS ->
TRANSACTIONS -> CLI/WIZARD. Only transaction apply functions change installed
files. Planning, inspection and configuration parsing do not execute artifacts.
Python 3.11+ is needed here; generated Bash files do not need Python or TOML.
"""
from __future__ import annotations

import argparse
import base64
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unicodedata

if sys.version_info < (3, 11):
    raise SystemExit('The configurator requires Python 3.11+. Generated Bash does not.')
import tomllib

VERSION = '0.2.0'
SHELLS = ('bash', 'zsh', 'sh', 'powershell')
TARGETS = ('shell', 'issue', 'ssh-banner', 'text')
SECTION_IDS = ('system', 'resources', 'services', 'processes', 'sessions',
               'connections', 'attention', 'hints', 'io')
PRESET_NAMES = ('workshop', 'home-lab', 'public-console')
MAX_ARTIFACT_BYTES = 2_000_000


class MotdError(Exception):
    """A user-visible validation or lifecycle error; never silently ignored."""


# ======================= 1. CONFIGURATION (NO EXECUTION) ======================

def preset_config(name='workshop', shell='bash'):
    """Return independent data. Presets select settings, never duplicate code."""
    if name not in PRESET_NAMES:
        raise MotdError(f'Unknown preset: {name}')
    c = {
        'schema_version': 1, 'preset': name, 'name': name, 'target': 'shell', 'shell': shell,
        'audience': 'all', 'frequency': 'login',
        'public_text': 'Authorised access only. Contact the system administrator.',
        'messages': [],
        'display': {'title': 'WORKSHOP STATUS', 'site': 'Workshop', 'theme': 'cyan',
                    'width': 132, 'rows': 25, 'top_entries': 3,
                    'sections': list(SECTION_IDS[:-1]), 'show_swap': True,
                    'show_compression': True, 'show_pressure': True},
        'services': {'required': [], 'exclude': ['ollama*', 'llama*', 'vllm*', 'lmstudio*']},
        'collection': {'budget_ms': 140, 'worker_ms': 220, 'process_limit': 512,
                       'io_scan_ms': 35, 'journal': False},
        'hooks': {'before': [], 'after': []},
        'hints': [
            {'id': 'tasks', 'label': 'Tasks', 'command': 'top', 'note': 'CPU and memory'},
            {'id': 'io', 'label': 'I/O', 'command': 'iotop -o', 'note': 'If installed and permitted'},
            {'id': 'services', 'label': 'Services', 'command': 'systemctl --failed', 'note': 'Failed units'},
            {'id': 'sessions', 'label': 'Sessions', 'command': 'loginctl list-sessions', 'note': 'Registered logins'},
        ],
    }
    if name == 'home-lab':
        c['display'].update(title='HOME LAB', site='Home lab', theme='green', width=100,
                            sections=['system', 'resources', 'services', 'attention', 'hints'])
        c['services']['exclude'] = []
    elif name == 'public-console':
        c.update(target='issue', public_text='Authorised access only.\nContact the system administrator.')
        c['display'].update(title='SYSTEM CONSOLE', site='', theme='mono', width=80)
    if shell == 'powershell':
        c['hints'] = [
            {'id': 'tasks', 'label': 'Tasks', 'command': 'Get-Process', 'note': 'Local processes'},
            {'id': 'services', 'label': 'Services', 'command': 'Get-Service', 'note': 'Windows services'},
            {'id': 'storage', 'label': 'Storage', 'command': 'Get-PSDrive -PSProvider FileSystem', 'note': 'Filesystem drives'},
        ]
    return c


def select_shell(config, shell):
    """Change output type; adapt only untouched built-in hint sets."""
    old = preset_config(config['preset'], config['shell'])['hints']
    if config['hints'] == old:
        config['hints'] = preset_config(config['preset'], shell)['hints']
    config['shell'] = shell


def _keys(table, allowed, label):
    if not isinstance(table, dict):
        raise MotdError(f'{label} must be a table')
    unknown = set(table) - set(allowed)
    if unknown:
        raise MotdError(f'Unknown {label} settings: {", ".join(sorted(unknown))}')


def _text(value, label, maximum=500, multiline=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise MotdError(f'{label} must be text of at most {maximum} characters')
    if any(ord(ch) < 32 and not (multiline and ch == '\n') or ord(ch) == 127 for ch in value):
        raise MotdError(f'{label} contains control characters')
    return value


def _number(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise MotdError(f'{label} must be an integer from {low} to {high}')


def _strings(value, label, maximum=64):
    if not isinstance(value, list) or len(value) > maximum:
        raise MotdError(f'{label} must be a list of at most {maximum} strings')
    for item in value:
        _text(item, label)


def validate_config(data):
    """Validate a small fixed schema before any value reaches Bash arithmetic.

    Shell quoting alone does not make Bash arithmetic safe. Numeric fields are
    real bounded integers; keys/IDs and enum values are checked independently.
    Unknown keys are errors, which makes misspelled security/settings visible.
    """
    if not isinstance(data, dict):
        raise MotdError('Configuration must be a TOML table')
    base = preset_config(data.get('preset', 'workshop'), data.get('shell', 'bash'))
    _keys(data, base, 'top-level')
    for key, value in data.items():
        if key in ('display', 'services', 'collection', 'hooks'):
            _keys(value, base[key], key)
            base[key].update(copy.deepcopy(value))
        else:
            base[key] = copy.deepcopy(value)
    c = base
    if type(c['schema_version']) is not int or c['schema_version'] != 1:
        raise MotdError('Only schema_version = 1 is supported')
    if not isinstance(c['name'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', c['name']):
        raise MotdError('name must be a lower-case identifier, at most 40 characters')
    for key, choices in [('target', TARGETS), ('shell', SHELLS),
                         ('audience', ('all', 'ssh', 'local')),
                         ('frequency', ('login', 'interactive'))]:
        if c[key] not in choices:
            raise MotdError(f'{key} must be one of {", ".join(choices)}')
    _text(c['public_text'], 'public_text', 16000, multiline=True)
    _strings(c['messages'], 'messages', 24)
    d = c['display']
    for key in ('title', 'site'):
        _text(d[key], f'display.{key}', 100)
    if d['theme'] not in ('cyan', 'green', 'amber', 'mono'):
        raise MotdError('Theme must be cyan, green, amber or mono')
    for key, lo, hi in [('width', 40, 240), ('rows', 20, 60), ('top_entries', 1, 10)]:
        _number(d[key], lo, hi, f'display.{key}')
    _strings(d['sections'], 'display.sections', 9)
    if not d['sections'] or len(set(d['sections'])) != len(d['sections']) or set(d['sections']) - set(SECTION_IDS):
        raise MotdError('Sections must be unique supported section IDs')
    minimum = {'system': 2, 'resources': 3, 'services': 2, 'processes': 3,
               'sessions': 2, 'connections': 1, 'attention': 2, 'hints': 1, 'io': 2}
    required_rows = 3 + sum(minimum[x] for x in d['sections'])
    if d['rows'] < required_rows:
        raise MotdError(f'These sections need at least {required_rows} rows including borders/prompt')
    for key in ('show_swap', 'show_compression', 'show_pressure'):
        if type(d[key]) is not bool:
            raise MotdError(f'display.{key} must be true or false')
    for key in ('required', 'exclude'):
        _strings(c['services'][key], f'services.{key}')
        for item in c['services'][key]:
            if not re.fullmatch(r'[A-Za-z0-9_.@*?\[\]:\\-]+', item):
                raise MotdError(f'Unsupported service identifier/pattern: {item!r}')
    for key, lo, hi in [('budget_ms', 20, 5000), ('worker_ms', 50, 10000),
                        ('process_limit', 32, 65536), ('io_scan_ms', 5, 1000)]:
        _number(c['collection'][key], lo, hi, f'collection.{key}')
    if c['collection']['worker_ms'] <= c['collection']['budget_ms']:
        raise MotdError('worker_ms must exceed budget_ms to leave time for rendering')
    if type(c['collection']['journal']) is not bool:
        raise MotdError('collection.journal must be true or false')
    if not isinstance(c['hints'], list) or len(c['hints']) > 32:
        raise MotdError('hints must be a list of at most 32 records')
    seen = set()
    for hint in c['hints']:
        _keys(hint, ('id', 'label', 'command', 'note'), 'hint')
        if set(hint) != {'id', 'label', 'command', 'note'}:
            raise MotdError('Each hint requires id, label, command and note')
        for key, value in hint.items():
            _text(value, f'hint.{key}')
            if '|' in value:
                raise MotdError('Displayed hint fields cannot contain |; use hooks for executable pipelines')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', hint['id']) or hint['id'] in seen:
            raise MotdError('Hint IDs must be unique lower-case identifiers')
        seen.add(hint['id'])
    for phase in ('before', 'after'):
        hooks = c['hooks'][phase]
        if not isinstance(hooks, list) or len(hooks) > 12:
            raise MotdError(f'hooks.{phase} must contain at most 12 calls')
        for hook in hooks:
            _keys(hook, ('argv', 'timeout_seconds', 'on_failure'), f'hooks.{phase}')
            hook.setdefault('timeout_seconds', 1)
            hook.setdefault('on_failure', 'continue')
            _strings(hook.get('argv'), 'hook.argv', 64)
            if not hook['argv'] or not hook['argv'][0] or hook['argv'][0].startswith('-'):
                raise MotdError('hook.argv needs a command as its first argument')
            sec = hook['timeout_seconds']
            if type(sec) not in (int, float) or not 0.05 <= sec <= 60:
                raise MotdError('Hook timeout_seconds must be between 0.05 and 60')
            if hook['on_failure'] not in ('continue', 'stop'):
                raise MotdError('Hook on_failure must be continue or stop')
    if c['target'] != 'shell' and any(c['hooks'].values()):
        raise MotdError('Public static banners cannot execute before/after hooks')
    return c


def load_config(path):
    return validate_config(tomllib.loads(Path(path).read_text(encoding='utf-8')))


def dump_config(config):
    """Write our fixed schema, not arbitrary TOML; comments are regenerated."""
    c = validate_config(config)
    def value(v):
        if isinstance(v, bool): return 'true' if v else 'false'
        return json.dumps(v, ensure_ascii=False)
    out = ['# MOTD recipe. Edit by hand or pass back to motd.py.',
           '# Hooks are explicit executable calls; hints are display-only text.']
    for key in ('schema_version', 'preset', 'name', 'target', 'shell', 'audience', 'frequency', 'public_text', 'messages'):
        out.append(f'{key} = {value(c[key])}')
    for table in ('display', 'services', 'collection'):
        out += ['', f'[{table}]']
        out.extend(f'{key} = {value(v)}' for key, v in c[table].items())
    out += ['', '[hooks]']
    for phase in ('before', 'after'):
        if not c['hooks'][phase]: out.append(f'{phase} = []')
    for phase in ('before', 'after'):
        for hook in c['hooks'][phase]:
            out += ['', f'[[hooks.{phase}]]']
            out.extend(f'{key} = {value(v)}' for key, v in hook.items())
    # Empty arrays must be declared at root rather than inside the last table.
    if not c['hints']:
        out.insert(2, 'hints = []')
    for hint in c['hints']:
        out += ['', '[[hints]]']
        out.extend(f'{key} = {value(v)}' for key, v in hint.items())
    return '\n'.join(out) + '\n'


# ======================== 2. GENERATION (NO INSTALL) ==========================

def _assignment(key, value):
    if isinstance(value, list):
        return key + '=(' + ' '.join(shlex.quote(str(v)) for v in value) + ')'
    return key + '=' + shlex.quote(str(int(value) if isinstance(value, bool) else value))


def runtime_assignments(config):
    c = validate_config(config); d = c['display']; p = c['collection']
    values = {'TITLE': d['title'], 'SITE_LABEL': d['site'], 'THEME': d['theme'],
              'MAX_WIDTH': d['width'], 'COMPACT_ROWS': d['rows'],
              'TOP_N': d['top_entries'], 'IO_TOP_N': d['top_entries'],
              'SECTIONS': d['sections'], 'SHOW_SWAP': d['show_swap'],
              'SHOW_COMPRESSION': d['show_compression'], 'SHOW_PRESSURE': d['show_pressure'],
              'SHOW_JOURNAL': p['journal'], 'MOTD_FASTFETCH': 0,
              'REQUIRED_UNITS': c['services']['required'],
              'SERVICE_EXCLUDE_PATTERNS': c['services']['exclude'],
              'COLLECTION_BUDGET_MS': p['budget_ms'],
              'CONCISE_WORKER_SECONDS': f"{p['worker_ms']/1000:.3f}",
              'IO_PROCESS_LIMIT': p['process_limit'], 'IO_SCAN_BUDGET_MS': p['io_scan_ms'],
              'MESSAGES': ['INFO|' + x for x in c['messages']],
              'HINTS': ['|'.join(h[k] for k in ('id', 'label', 'command', 'note')) for h in c['hints']]}
    return '\n'.join(_assignment(k, v) for k, v in values.items())


def hook_wrapper(config):
    """Calls run once in the outer process, never during demo or worker re-entry.

    Commands are Bash arrays, not eval strings. An intentional pipeline must use
    explicit ['bash', '-c', '...'] in the recipe. No command runs during planning.
    Hook time is additional to the dashboard's collection budget.
    """
    if not any(config['hooks'].values()):
        return ''
    lines = [
        '# Explicit user hooks. This wrapper runs only in the outer invocation.',
        'motd_core=0; motd_hooks_enabled=1; motd_args=()',
        'for motd_arg in "$@"; do',
        '  case "$motd_arg" in',
        '    --_motd-core) motd_core=1 ;;',
        '    --_worker) motd_core=1; motd_args+=("$motd_arg") ;;',
        '    --no-hooks) motd_hooks_enabled=0 ;;',
        '    --demo|--demo-alerts|--help|-h|--version|--list-sections|--list-items)',
        '      motd_hooks_enabled=0; motd_args+=("$motd_arg") ;;',
        '    *) motd_args+=("$motd_arg") ;;',
        '  esac', 'done', 'set -- "${motd_args[@]}"',
        'if (( ! motd_core )); then',
    ]
    def calls(phase):
        if not config['hooks'][phase]: return []
        result = ['  if (( motd_hooks_enabled )); then']
        for i, hook in enumerate(config['hooks'][phase], 1):
            argv = ' '.join(shlex.quote(a) for a in hook['argv'])
            sec = str(hook['timeout_seconds'])
            result += [f'    motd_call=({argv})', '    motd_hook_rc=0',
                       '    if command -v timeout >/dev/null 2>&1; then',
                       f'      timeout --kill-after=0.2s {sec}s "${{motd_call[@]}}" || motd_hook_rc=$?',
                       '    else motd_hook_rc=127; fi',
                       f'    if (( motd_hook_rc )); then printf "%s\\n" "MOTD {phase} hook {i} failed ($motd_hook_rc)." >&2;']
            if hook['on_failure'] == 'stop': result.append('      exit "$motd_hook_rc"')
            result.append('    fi')
        result += ['  fi']
        return result
    lines += calls('before')
    lines += ['  /bin/bash "${BASH_SOURCE[0]}" --_motd-core "$@"', '  motd_result=$?']
    lines += calls('after')
    lines += ['  exit "$motd_result"', 'fi', 'unset motd_core motd_arg motd_args motd_hooks_enabled']
    return '\n'.join(lines) + '\n'


def portable_runtime_assignments(config):
    """Render validated data as POSIX assignments and literal display calls."""
    c = validate_config(config)
    d = c['display']
    settings = {'TITLE': d['title'], 'SITE_LABEL': d['site'], 'THEME': d['theme'],
                'MAX_WIDTH': d['width'], 'ROWS': d['rows'],
                'SECTIONS': ' '.join(d['sections'])}
    lines = [f'{key}={shlex.quote(str(value))}' for key, value in settings.items()]
    for name, items in [('motd_messages', c['messages']),
                        ('motd_hints', [f"{h['label']}: {h['command']} - {h['note']}" for h in c['hints']])]:
        lines.append(name + '() {')
        lines.extend('    motd_line ' + shlex.quote(item) for item in items)
        if not items: lines.append('    :')
        lines.append('}')
    return '\n'.join(lines) + '\n' + portable_hook_wrapper(c)


def portable_hook_wrapper(config):
    """Explicit argv, once per phase; no eval and no unbounded fallback.

    A missing or incompatible timeout causes hook failure before its command is
    run. The native sh renderer has no worker reinvocation, so it needs no Bash
    array wrapper. The renderer suppresses hooks for demo and --no-hooks.
    """
    lines = []
    for phase in ('before', 'after'):
        lines += [f'motd_{phase}_hooks() {{',
                  '    if [ "$MOTD_HOOKS_ENABLED" -ne 1 ]; then return 0; fi']
        for index, hook in enumerate(config['hooks'][phase], 1):
            argv = ' '.join(shlex.quote(argument) for argument in hook['argv'])
            lines += ['    motd_hook_rc=0',
                      '    if command -v timeout >/dev/null 2>&1; then',
                      f'        timeout --kill-after=0.2s {hook["timeout_seconds"]}s {argv} || motd_hook_rc=$?',
                      '    else motd_hook_rc=127; fi',
                      '    if [ "$motd_hook_rc" -ne 0 ]; then',
                      f'        printf "%s\\n" "MOTD {phase} hook {index} failed ($motd_hook_rc)." >&2']
            if hook['on_failure'] == 'stop': lines.append('        return "$motd_hook_rc"')
            lines.append('    fi')
        lines += ['    return 0', '}']
    return '\n'.join(lines) + '\n'


def zsh_launcher():
    """Execute the same standalone file with Bash before Zsh parses its body.

    Keep this before Bash-specific hook/collector syntax. Zsh integration uses
    the shared Bash runtime; it is not a promise of a native Zsh collector port.
    """
    return ('# Zsh entry point; the shared dashboard requires /bin/bash 4.3+.\n'
            'if [ -n "${ZSH_VERSION-}" ] && [ -z "${BASH_VERSION-}" ]; then\n'
            '    exec /bin/bash "$0" "$@"\n'
            'fi\n')


def powershell_assignments(config):
    """Use literal ASCII JSON so UTF-8 without BOM works in Windows PS 5.1.

    Single quotes are doubled for PowerShell's literal string. JSON handles all
    remaining quoting and Unicode, and ConvertFrom-Json only parses data.
    """
    c = validate_config(config)
    payload = json.dumps(c, ensure_ascii=True, separators=(',', ':')).replace("'", "''")
    return f"$MotdVersion = '{VERSION}'\n$MotdConfig = ConvertFrom-Json -InputObject '{payload}'"


def generate_powershell_body(config):
    """Return body only; caller adds the usual checked metadata/header."""
    if PS_TEMPLATE.count('# @MOTD_CONFIG@') != 1:
        raise MotdError('Embedded PowerShell template has an invalid configuration marker')
    return PS_TEMPLATE.replace('# @MOTD_CONFIG@', powershell_assignments(config))


def artifact_suffix(config):
    return {"bash": ".bash", "zsh": ".zsh", "sh": ".sh", "powershell": ".ps1"}[config["shell"]] if config["target"] == "shell" else ".txt"


def generate_artifact(config):
    c = validate_config(config)
    if c['target'] != 'shell':
        text = c['display']['title'] + '\n\n' + c['public_text'].strip() + '\n'
        # agetty interprets backslash escapes. Public user text is literal.
        return text.replace('\\', '\\\\') if c['target'] == 'issue' else text
    recipe = base64.b64encode(dump_config(c).encode()).decode()
    body = f'# MOTD-CONFIG-BASE64: {recipe}\n'
    if c['shell'] == 'powershell':
        body += generate_powershell_body(c)
        header = '# Native PowerShell output; invoke with & ./message.ps1\n'
    elif c['shell'] == 'sh':
        if SH_TEMPLATE.count('# @MOTD_CONFIG@') != 1:
            raise MotdError('Embedded sh template has an invalid configuration marker')
        body += SH_TEMPLATE.replace('# @MOTD_CONFIG@', portable_runtime_assignments(c))
        header = '#!/bin/sh\n'
    else:
        if BASH_TEMPLATE.count('# @MOTD_CONFIG@') != 1 or BASH_TEMPLATE.count('# @MOTD_HOOKS@') != 1:
            raise MotdError('Embedded Bash template has invalid configuration/hook markers')
        if c['shell'] == 'zsh': body += zsh_launcher()
        # The canonical minimum-version guard runs before any configured call.
        body += BASH_TEMPLATE.replace('# @MOTD_CONFIG@', runtime_assignments(c)).replace('# @MOTD_HOOKS@', hook_wrapper(c))
        header = '#!/usr/bin/env ' + c['shell'] + '\n'
    digest = hashlib.sha256(body.encode()).hexdigest()
    return (header + f'# Generated by MOTD {VERSION}; standalone {c["shell"]} output.\n'
            f'# MOTD-BODY-SHA256: {digest}\n'
            '# MOTD-BODY-BEGIN\n' + body)


def extract_config(artifact):
    """Read data only. The digest detects changes; it is not authentication."""
    if len(artifact.encode()) > MAX_ARTIFACT_BYTES:
        raise MotdError('Artifact is too large')
    matches = list(re.finditer(r'^# MOTD-CONFIG-BASE64: ([A-Za-z0-9+/=]+)$', artifact, re.M))
    match = matches[0] if len(matches) == 1 else None
    digest = re.search(r'^# MOTD-BODY-SHA256: ([0-9a-f]{64})$', artifact, re.M)
    marker = '# MOTD-BODY-BEGIN\n'
    if not match or not digest or artifact.count(marker) != 1:
        raise MotdError('No recoverable MOTD recipe; supply a TOML recipe or import the bytes explicitly')
    body = artifact.split(marker, 1)[1]
    if match.start() < artifact.index(marker):
        raise MotdError('Recipe must be inside the checked artifact body')
    if hashlib.sha256(body.encode()).hexdigest() != digest[1]:
        raise MotdError('Artifact body changed since generation; inspect and explicitly import it as modified code')
    try:
        return validate_config(tomllib.loads(base64.b64decode(match[1], validate=True).decode()))
    except (ValueError, UnicodeError) as exc:
        raise MotdError(f'Invalid embedded recipe: {exc}') from exc


# ====================== 3. INSTALLATION PLANS (READ ONLY) =====================

def absolute(path):
    return os.path.abspath(os.path.expanduser(str(path)))


def default_state(scope='user'):
    if scope == 'system':
        return '/var/lib/motd-wizard'
    base = os.environ.get('XDG_STATE_HOME') or str(Path.home() / '.local/state')
    if not Path(base).is_absolute():
        raise MotdError('XDG_STATE_HOME must be absolute')
    return absolute(Path(base) / 'motd')


def _file_text(path):
    # The transaction reader rejects symlinks, hardlinks and non-regular files.
    snapshot, data = _tx_read(absolute(path))
    try:
        return snapshot, data.decode('utf-8') if data is not None else ''
    except UnicodeDecodeError as exc:
        raise MotdError(f'Expected a UTF-8 text file: {path}') from exc


def _source_text(path):
    state, text = _file_text(path)
    if not state['exists']:
        raise MotdError(f'Input artifact does not exist: {path}')
    return text


def _trusted_system_path(path):
    """A root-owned script inside somebody else's writable directory is unsafe."""
    for parent in Path(path).parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise MotdError(f'System files require root-owned, non-writable-by-others ancestors: {parent}')


def active_installs(state_dir):
    """Replay install/uninstall intents, allowing rollback of a rollback."""
    records = tx_history(state_dir)
    undone = set()
    for record in reversed(records):
        if record['status'] not in ('applied', 'noop') or record['id'] in undone:
            continue
        meta = record.get('metadata', {})
        if meta.get('operation') == 'rollback':
            undone.add(meta.get('source_transaction_id'))
    active = {}
    for record in records:
        if record['status'] not in ('applied', 'noop') or record['id'] in undone:
            continue
        meta = record.get('metadata', {})
        name = meta.get('name')
        if meta.get('operation') in ('install', 'upgrade') and name:
            active[name] = record
        elif meta.get('operation') == 'uninstall' and name:
            active.pop(name, None)
    return active


def shell_block(config, artifact_path):
    """Interactive, terminal-only startup attachment for the selected shell.

    POSIX sh has no portable login-shell query. Its login-frequency attachment
    belongs in .profile; explicit custom locations retain that documented
    responsibility. Bash and Zsh additionally test their native login option.
    """
    c = validate_config(config)
    kind = c.get('shell', 'bash')
    marker = '_MOTD_SEEN_' + c['name'].replace('-', '_')
    tests = ['[ -t 1 ]', '[ ! -e "$HOME/.hushlogin" ]']
    if kind == 'bash': tests.insert(0, '[ -n "${BASH_VERSION-}" ]')
    elif kind == 'zsh': tests.insert(0, '[ -n "${ZSH_VERSION-}" ]')
    elif kind != 'sh': raise MotdError('This helper supports Bash, Zsh and POSIX sh startup files')
    if c['audience'] == 'ssh': tests.append('[ -n "${SSH_CONNECTION-}${SSH_TTY-}" ]')
    if c['audience'] == 'local': tests.append('[ -z "${SSH_CONNECTION-}${SSH_TTY-}" ]')
    frequency = ':'
    if c['frequency'] == 'login':
        if kind == 'bash': frequency = 'shopt -q login_shell'
        elif kind == 'zsh': frequency = '[[ -o login ]]'
    executable = '/bin/bash' if kind == 'bash' else ('zsh' if kind == 'zsh' else '/bin/sh')
    return '\n'.join([
        f'# >>> motd {c["name"]} >>>',
        f'# Managed by motd.py; interactive {kind}, once per shell process.',
        'if ' + ' && '.join(tests) + '; then',
        '  case $- in', '    *i*)',
        f'      if {frequency} && [ "${{{marker}-}}" != "$$" ]; then',
        f'        {marker}=$$; export {marker}',
        f'        {executable} {shlex.quote(artifact_path)} || :',
        '      fi', '      ;;', '  esac', 'fi',
        f'# <<< motd {c["name"]} <<<',
    ]) + '\n'


def _block_pattern(name):
    return re.compile(r'^# >>> motd ' + re.escape(name) + r' >>>\n.*?^# <<< motd '
                      + re.escape(name) + r' <<<\n?', re.M | re.S)


def _put_block(text, block, name, expected=None):
    pattern = _block_pattern(name)
    matches = list(pattern.finditer(text))
    if len(matches) > 1:
        raise MotdError('Duplicate managed blocks; inspect before changing this file')
    if matches:
        old = matches[0].group()
        if expected is None or old.rstrip('\n') != expected.rstrip('\n'):
            raise MotdError('Managed hook was changed or has no ownership record; inspect it first')
        return text[:matches[0].start()] + block + text[matches[0].end():]
    # An unmatched marker is never treated as permission to append another block.
    if f'# >>> motd {name} >>>' in text or f'# <<< motd {name} <<<' in text:
        raise MotdError('Incomplete managed hook markers; repair them manually')
    return text + ('\n' if text and not text.endswith('\n') else '') + block


def installation_plan(config, artifact, *, scope='user', destination=None,
                      shell_file=None, state_dir=None, replace=False, opaque_artifact=False):
    """Resolve exact files, preserve outside text, then call read-only tx_plan.

    Shell output is executable; issue/banner output is literal static text. No
    daemon is restarted, no package is installed and no privilege is requested.
    Parent directories must already exist so creation cannot escape review.
    """
    if os.name != 'posix' or not sys.platform.startswith('linux'):
        raise MotdError('Installation currently supports Linux; build/export is separate')
    c = validate_config(config); name = c['name']; target = c['target']
    kind = c['shell']
    if target == 'shell' and kind == 'powershell':
        raise MotdError('Native PowerShell output can be built and previewed; profile installation is not implemented. Export the .ps1 and attach it explicitly in the intended $PROFILE.')
    if scope == 'system' and os.geteuid() != 0:
        raise MotdError('System installation/planning requires root; export first and run the reviewed installer as root')
    state_dir = absolute(state_dir or default_state(scope))
    previous = active_installs(state_dir).get(name)
    old_meta = previous['metadata'] if previous else {}
    if previous and (old_meta['target'] != target or old_meta['scope'] != scope
                     or (target == 'shell' and old_meta.get('shell', 'bash') != kind)):
        raise MotdError('Uninstall the existing name before changing its target, shell or scope')
    if destination:
        output = absolute(destination)
    elif target == 'shell':
        output = f'/usr/local/bin/motd-{name}' if scope == 'system' else str(Path.home() / (f'.motd-{name}' + artifact_suffix(c)))
    elif target == 'text':
        raise MotdError('Generic text needs an explicit --destination; consumer paths and formatting are not guessed')
    elif scope != 'system':
        raise MotdError('Static user installs require --destination; use --scope system for system paths')
    elif target == 'issue':
        output = '/etc/issue'
    else:
        output = f'/etc/ssh/motd-{name}.banner'
    output = absolute(output)
    if scope == 'system': _trusted_system_path(output)
    if previous and output != old_meta['artifact_path']:
        raise MotdError('Uninstall before changing an installed artifact path')
    existing, old_output = _file_text(output)
    if scope == 'system' and existing['exists'] and (existing['uid'] != 0 or existing['mode'] & 0o022):
        raise MotdError('System target must be root-owned and not writable by group/others')
    if previous:
        prior_change = next(x for x in previous['changes'] if x['path'] == output)
        if existing['exists'] and existing.get('sha256') != prior_change['after'].get('sha256'):
            raise MotdError('Installed artifact was modified; inspect it before upgrading')
    elif existing['exists'] and not replace and target != 'issue':
        raise MotdError(f'Unmanaged file exists: {output}. Review it and use --replace to take ownership with backup.')
    mode = (0o755 if scope == 'system' else 0o700) if target == 'shell' else 0o644
    changes = [{'path': output, 'content': artifact, 'mode': mode}]
    hook_paths = []
    if target == 'shell':
        if shell_file:
            hook_paths = [absolute(shell_file)]
        elif scope == 'system':
            if kind == 'zsh':
                raise MotdError('System Zsh startup paths vary; choose an explicit --shell-file')
            if c['frequency'] == 'interactive':
                raise MotdError('System non-login startup needs an explicit --shell-file')
            hook_paths = [f'/etc/profile.d/70-motd-{name}.sh']
        elif kind == 'zsh':
            zdotdir = os.environ.get('ZDOTDIR', str(Path.home()))
            if not zdotdir or not Path(zdotdir).is_absolute():
                raise MotdError('ZDOTDIR must be an absolute existing directory, or unset')
            hook_paths = [str(Path(zdotdir) / '.zshrc'), str(Path(zdotdir) / '.zprofile')]
        elif kind == 'sh':
            if c['frequency'] == 'interactive':
                raise MotdError('POSIX sh interactive startup needs an explicit --shell-file; ENV is not changed automatically')
            hook_paths = [str(Path.home() / '.profile')]
        else:
            home = Path.home()
            login = next((home / x for x in ('.bash_profile', '.bash_login', '.profile')
                          if (home / x).exists()), home / '.bash_profile')
            hook_paths = [str(home / '.bashrc'), str(login)]
        if previous and hook_paths != old_meta['hook_paths']:
            raise MotdError('Uninstall before changing hook locations')
        block = shell_block(c, output)
        for path in hook_paths:
            if scope == 'system': _trusted_system_path(path)
            old, text = _file_text(path)
            if scope == 'system' and old['exists'] and (old['uid'] != 0 or old['mode'] & 0o022):
                raise MotdError('System hook must be root-owned and not writable by group/others')
            new = _put_block(text, block, name, old_meta.get('hook_block'))
            changes.append({'path': path, 'content': new,
                            'mode': old.get('mode', 0o644)})
    else:
        block = ''
    baseline_id = _initial_install(state_dir, previous)['id'] if previous else None
    metadata = {'operation': 'upgrade' if previous else 'install', 'name': name,
                'target': target, 'shell': kind, 'scope': scope, 'artifact_path': output,
                'hook_paths': hook_paths, 'hook_block': block,
                'baseline_transaction_id': baseline_id,
                'config_toml': dump_config(c), 'artifact_text': artifact,
                'artifact_suffix': artifact_suffix(c),
                'generator_version': VERSION,
                'artifact_origin': 'opaque-import' if opaque_artifact else 'recipe'}
    if opaque_artifact:
        # Installation selections are not a reconstruction of somebody else's code.
        metadata.pop('config_toml')
    return tx_plan(changes, state_dir, metadata)


def _initial_install(state_dir, current):
    baseline_id = current['metadata'].get('baseline_transaction_id')
    if not baseline_id: return current
    return next(r for r in tx_history(state_dir) if r['id'] == baseline_id)


def uninstall_plan(name, state_dir):
    current = active_installs(state_dir).get(name)
    if not current:
        raise MotdError(f'No active managed installation named {name}')
    meta = current['metadata']; baseline = _initial_install(state_dir, current)
    originals = {x['path']: x for x in baseline['changes']}
    changes = []
    for path in [meta['artifact_path']] + meta['hook_paths']:
        observed, text = _file_text(path)
        expected = next(x for x in current['changes'] if x['path'] == path)
        original = originals[path]
        retain_current_mode = path in meta['hook_paths']
        if path == meta['artifact_path']:
            if observed['exists'] and observed.get('sha256') != expected['after'].get('sha256'):
                raise MotdError('Modified artifact is preserved; inspect before uninstalling')
            data = _tx_blob(baseline, original, 'before')
            replacement = data.decode('utf-8') if data is not None else None
        else:
            matches = list(_block_pattern(name).finditer(text))
            if len(matches) != 1 or matches[0].group().rstrip('\n') != meta['hook_block'].rstrip('\n'):
                raise MotdError(f'Hook missing or changed; inspect before uninstalling: {path}')
            # Always remove only our block. An upgrade can already contain a
            # user's edits or another dashboard; an exact match to that upgrade
            # does NOT justify restoring the first installation's entire file.
            replacement = text[:matches[0].start()] + text[matches[0].end():]
            data = _tx_blob(baseline, original, 'before')
            if data is None and not replacement:
                replacement = None
            elif data is not None:
                original_text = data.decode('utf-8')
                separator = '\n' if original_text and not original_text.endswith('\n') else ''
                if replacement == original_text + separator:
                    replacement = original_text
        changes.append({'path': path, 'content': replacement,
                        'mode': observed.get('mode', 0o644) if retain_current_mode else original['before'].get('mode', observed.get('mode', 0o644))})
        if not retain_current_mode and original['before']['exists']:
            changes[-1]['owner'] = [original['before']['uid'], original['before']['gid']]
    return tx_plan(changes, state_dir, {'operation': 'uninstall', 'name': name,
                                       'source_transaction_id': current['id']})


def repair_installation_plan(name, state_dir):
    """Repair a current installation across upgrades/no-ops/inverse transactions.

    A transaction can change only the runtime while leaving its hook unchanged.
    Repair therefore uses the complete current manifest, and additionally checks
    the latest intended state of each path so newer unrelated writes/deletions win.
    """
    current = active_installs(state_dir).get(name)
    if not current: raise MotdError(f'No active installation named {name}')
    latest = _tx_latest(tx_history(state_dir))
    changes = []; preserved = []
    for item in current['changes']:
        path = item['path']; actual, _ = _tx_read(path)
        owner = latest.get(path)
        if not owner or not _tx_equal(owner[1]['after'], item['after']):
            preserved.append({'path': path, 'reason': 'newer intended state differs'}); continue
        if actual['exists']:
            if not _tx_equal(actual, item['after']):
                preserved.append({'path': path, 'reason': 'existing content or metadata differs'})
            continue
        if item['after']['exists']:
            data = _tx_blob(current, item, 'after')
            changes.append({'path': path, 'content': data.decode('utf-8'), 'mode': item['after']['mode'],
                            'owner': [item['after']['uid'], item['after']['gid']]})
    metadata = {'operation': 'repair-installation', 'name': name, 'owner_transaction_id': current['id'],
                'source_transaction_id': current['id'], 'preserved': preserved}
    return tx_plan(changes, state_dir, metadata)


def describe_plan(plan, *, json_output=False):
    if json_output:
        print(json.dumps(plan, indent=2))
        return
    print(f"Plan: {plan['metadata'].get('operation', 'write')} | {plan['change_count']} file changes")
    print('State and recovery archive:', plan['state_dir'])
    for item in plan['changes']:
        before, after = item['before'], item['after']
        print(f"  {item['operation'].upper():6} {item['path']}")
        print('    SHA256:', before.get('sha256', '<absent>'), '->', after.get('sha256', '<absent>'))
        print('    Mode:', oct(before.get('mode', 0)), '->', oct(after.get('mode', 0)))
        if item['operation'] == 'noop': continue
        _, old = _file_text(item['path'])
        new = base64.b64decode(item['content_b64']).decode() if item['content_b64'] is not None else ''
        if max(len(old), len(new)) > 24000:
            print('    Large artifact: inspect the generated file; full bytes are archived on apply.')
        else:
            diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                            fromfile='before', tofile='after', lineterm=''))
            print('\n'.join('    ' + x for x in diff[:120]))
            if len(diff) > 120: print('    ... further diff lines omitted; use --json for complete intended bytes.')
    print('Apply uses per-file replacement plus a recovery journal; the group is not filesystem-atomic.')


def confirm(prompt, yes=False):
    if yes: return True
    if not sys.stdin.isatty():
        raise MotdError('Confirmation requires a terminal; inspect the plan and pass --yes for noninteractive apply')
    return input(prompt + ' [y/N] ').strip().lower() in ('y', 'yes')


def apply_reviewed(plan, yes=False):
    describe_plan(plan)
    if not confirm('Apply this exact plan?', yes):
        print('Cancelled. Installed files were not changed.')
        return None
    result = tx_apply(plan)
    print(f"{result['status']}: {result['id']}")
    print('Recovery archive:', result['directory'])
    if plan['metadata'].get('target') == 'ssh-banner':
        print('Banner text installed. SSH configuration and daemon state were not changed.')
        print('Set Banner to this file using your existing sshd configuration, then validate/reload separately.')
    return result



# ====================== 4. TRANSACTIONS (DISK WRITES) ======================
# Transaction support: standard-library Python 3.11+, POSIX only.
# Target parents must already exist. The state tree may be created privately.
# File replacement is atomic; a transaction spanning several files is not.
import base64 as _tx_base64
import contextlib as _tx_contextlib
import datetime as _tx_datetime
try:
    import fcntl as _tx_fcntl
except ImportError:
    _tx_fcntl = None  # Generation/preview remain importable; mutation is POSIX-only.
import hashlib as _tx_hashlib
import json as _tx_json
import os as _tx_os
import stat as _tx_stat
import uuid as _tx_uuid

_TX_FORMAT = "motd-transactions-v1"
_TX_PENDING = {"staging", "applying", "compensating", "needs_recovery", "recovering"}
_TX_DANGEROUS_STATE = {
    "/", "/etc", "/usr", "/usr/local", "/var", "/var/lib", "/var/cache",
    "/var/tmp", "/tmp", "/home", "/root", "/run", "/opt", "/dev", "/proc", "/sys",
}


class TxError(Exception):
    """An actionable transaction error; record is present after durable staging."""

    def __init__(self, code, message, *, record=None, details=None):
        super().__init__(message)
        self.code = code
        self.record = record
        self.details = details or {}


def tx_error(error):
    """Return a JSON-compatible error object for CLI callers."""
    record = getattr(error, "record", None)
    return {
        "error": getattr(error, "code", "transaction_error"),
        "message": str(error),
        "transaction_id": record.get("id") if record else None,
        "status": record.get("status") if record else None,
        "recoverable": bool(record and record.get("status") in _TX_PENDING),
        "details": getattr(error, "details", {}),
    }


def _tx_now():
    return _tx_datetime.datetime.now(_tx_datetime.timezone.utc).isoformat()


def _tx_hash(data):
    return _tx_hashlib.sha256(data).hexdigest()


def _tx_json_bytes(value):
    try:
        return (_tx_json.dumps(value, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise TxError("invalid_data", "Transaction data must be valid UTF-8 JSON.") from exc


def _tx_path(path, *, state=False):
    if _tx_fcntl is None:
        raise TxError("unsupported_platform", "Journalled file operations require Linux/POSIX; generate on a supported host or use build --output -")
    if not isinstance(path, str) or not path or "\x00" in path or not path.startswith("/"):
        raise TxError("invalid_path", "Paths must be nonempty absolute paths without NUL bytes.")
    if any(part in (".", "..") for part in path.split("/")):
        raise TxError("invalid_path", "Dot and traversal components are not accepted: " + path)
    path = _tx_os.path.normpath(path)
    if path.startswith("//"):
        raise TxError("invalid_path", "Double-root paths are not accepted.")
    if state and (path in _TX_DANGEROUS_STATE or path == _tx_os.path.expanduser("~")):
        raise TxError("unsafe_state", "Choose a dedicated state subdirectory, not " + path)
    if any(path == base or path.startswith(base + "/") for base in ("/proc", "/sys", "/dev")):
        raise TxError("invalid_path", "Virtual device/kernel paths are not supported: " + path)
    return path


def _tx_parent(path, *, create=False):
    """Open every directory with O_NOFOLLOW; return pinned parent fd and leaf."""
    parts = path.split("/")[1:]
    if not parts or not parts[-1]:
        raise TxError("invalid_path", "A file or dedicated subdirectory path is required.")
    flags = _tx_os.O_RDONLY | _tx_os.O_DIRECTORY | _tx_os.O_NOFOLLOW
    fd = _tx_os.open("/", flags)
    try:
        for part in parts[:-1]:
            try:
                next_fd = _tx_os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise TxError("missing_parent", "Parent directory does not exist for " + path)
                try:
                    _tx_os.mkdir(part, 0o700, dir_fd=fd)
                    _tx_os.fsync(fd)
                except FileExistsError:
                    pass
                next_fd = _tx_os.open(part, flags, dir_fd=fd)
            _tx_os.close(fd)
            fd = next_fd
        return fd, parts[-1]
    except TxError:
        _tx_os.close(fd)
        raise
    except OSError as exc:
        _tx_os.close(fd)
        raise TxError("unsafe_path", "Cannot safely open parent of " + path,
                      details={"errno": exc.errno}) from exc


def _tx_read_at(parent_fd, name, path):
    try:
        initial = _tx_os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return {"exists": False}, None
    if not _tx_stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
        raise TxError("unsafe_target", "Expected one ordinary, non-hardlinked file: " + path)
    try:
        fd = _tx_os.open(name, _tx_os.O_RDONLY | _tx_os.O_NOFOLLOW | _tx_os.O_NONBLOCK,
                         dir_fd=parent_fd)
    except OSError as exc:
        raise TxError("unsafe_target", "Cannot safely read " + path,
                      details={"errno": exc.errno}) from exc
    try:
        start = _tx_os.fstat(fd)
        if not _tx_stat.S_ISREG(start.st_mode) or start.st_nlink != 1:
            raise TxError("unsafe_target", "Target changed type while reading: " + path)
        chunks = []
        while True:
            chunk = _tx_os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        data = b"".join(chunks)
        end = _tx_os.fstat(fd)
        try:
            named = _tx_os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise TxError("drift", "Target disappeared while reading: " + path) from exc
        keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(start, k) != getattr(end, k) for k in keys) or (
            named.st_dev, named.st_ino) != (end.st_dev, end.st_ino):
            raise TxError("drift", "Target changed while reading: " + path)
        return {
            "exists": True, "sha256": _tx_hash(data), "size": len(data),
            "mode": _tx_stat.S_IMODE(end.st_mode), "uid": end.st_uid, "gid": end.st_gid,
            "device": end.st_dev, "inode": end.st_ino,
            "mtime_ns": end.st_mtime_ns, "ctime_ns": end.st_ctime_ns,
        }, data
    finally:
        _tx_os.close(fd)


def _tx_read(path):
    fd, name = _tx_parent(path)
    try:
        return _tx_read_at(fd, name, path)
    finally:
        _tx_os.close(fd)


def _tx_equal(actual, expected, *, identity=False):
    if actual.get("exists") != expected.get("exists"):
        return False
    if not expected.get("exists"):
        return True
    keys = ["sha256", "size", "mode", "uid", "gid"]
    if identity:
        keys += ["device", "inode", "mtime_ns", "ctime_ns"]
    return all(actual.get(key) == expected.get(key) for key in keys)


def _tx_check_expected(actual, expected, path, *, identity=True):
    if not _tx_equal(actual, expected, identity=identity):
        raise TxError("drift", "File changed since the plan was reviewed: " + path,
                      details={"path": path, "expected": expected, "actual": actual})


def _tx_write_all(fd, data):
    view = memoryview(data)
    while view:
        count = _tx_os.write(fd, view)
        if count <= 0:
            raise OSError("Short write")
        view = view[count:]


def _tx_replace(path, data, desired, expected, *, identity=True):
    """One file only. Project lock cannot exclude non-cooperating external editors."""
    parent_fd, name = _tx_parent(path)
    temporary = None
    try:
        current, _ = _tx_read_at(parent_fd, name, path)
        _tx_check_expected(current, expected, path, identity=identity)
        if data is None:
            if current["exists"]:
                _tx_os.unlink(name, dir_fd=parent_fd)
                _tx_os.fsync(parent_fd)
            return {"exists": False}
        temporary = ".motd-tx-" + _tx_uuid.uuid4().hex + ".tmp"
        fd = _tx_os.open(temporary, _tx_os.O_WRONLY | _tx_os.O_CREAT | _tx_os.O_EXCL |
                         _tx_os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            _tx_write_all(fd, data)
            existing = _tx_os.fstat(fd)
            if (existing.st_uid, existing.st_gid) != (desired["uid"], desired["gid"]):
                _tx_os.fchown(fd, desired["uid"], desired["gid"])
            _tx_os.fchmod(fd, desired["mode"])
            _tx_os.fsync(fd)
        finally:
            _tx_os.close(fd)
        current, _ = _tx_read_at(parent_fd, name, path)
        _tx_check_expected(current, expected, path, identity=identity)
        _tx_os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temporary = None
        _tx_os.fsync(parent_fd)
        actual, _ = _tx_read_at(parent_fd, name, path)
        if not _tx_equal(actual, desired):
            raise TxError("post_write_drift", "File changed immediately after replacement: " + path)
        return actual
    finally:
        if temporary is not None:
            try:
                _tx_os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        _tx_os.close(parent_fd)


def _tx_private_write(path, data):
    before, _ = _tx_read(path)
    if before["exists"] and (before["uid"] != _tx_os.geteuid() or before["mode"] != 0o600):
        raise TxError("unsafe_state", "State file has unexpected ownership/permissions: " + path)
    after = {"exists": True, "sha256": _tx_hash(data), "size": len(data),
             "mode": 0o600, "uid": _tx_os.geteuid(), "gid": _tx_os.getegid()}
    return _tx_replace(path, data, after, before)


def _tx_mkdir(path, *, ancestors=False):
    fd, name = _tx_parent(path, create=ancestors)
    try:
        try:
            _tx_os.mkdir(name, 0o700, dir_fd=fd)
            _tx_os.fsync(fd)
        except FileExistsError:
            pass
        child = _tx_os.open(name, _tx_os.O_RDONLY | _tx_os.O_DIRECTORY | _tx_os.O_NOFOLLOW,
                            dir_fd=fd)
        try:
            info = _tx_os.fstat(child)
            if info.st_uid != _tx_os.geteuid() or _tx_stat.S_IMODE(info.st_mode) != 0o700:
                raise TxError("unsafe_state", "State directories must be owned by this user and mode 0700: " + path)
        finally:
            _tx_os.close(child)
    except OSError as exc:
        raise TxError("unsafe_state", "Cannot safely create/open state directory: " + path,
                      details={"errno": exc.errno}) from exc
    finally:
        _tx_os.close(fd)


def _tx_state_exists(state_dir):
    try:
        parent, name = _tx_parent(state_dir)
    except TxError as exc:
        if exc.code == "missing_parent":
            return False
        raise
    try:
        try:
            info = _tx_os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return False
        if not _tx_stat.S_ISDIR(info.st_mode) or info.st_uid != _tx_os.geteuid() or (
            _tx_stat.S_IMODE(info.st_mode) != 0o700):
            raise TxError("unsafe_state", "Existing state directory must be owned by this user and mode 0700.")
        return True
    finally:
        _tx_os.close(parent)


def _tx_read_json(path):
    snapshot, data = _tx_read(path)
    if not snapshot["exists"] or snapshot["uid"] != _tx_os.geteuid() or snapshot["mode"] != 0o600:
        raise TxError("unsafe_state", "Missing or unprotected state record: " + path)
    try:
        return _tx_json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise TxError("invalid_state", "Invalid JSON in " + path) from exc


def _tx_validate_state(state_dir, *, create=False):
    state_dir = _tx_path(state_dir, state=True)
    exists = _tx_state_exists(state_dir)
    if not exists:
        if not create:
            return False
        _tx_mkdir(state_dir, ancestors=True)
    marker = _tx_os.path.join(state_dir, "state.json")
    snapshot, _ = _tx_read(marker)
    if not snapshot["exists"]:
        # Never adopt an arbitrary populated directory as transaction state.
        if _tx_os.listdir(state_dir):
            raise TxError("unsafe_state", "State directory is not empty and has no valid state marker.")
        if not create:
            return False
        _tx_private_write(marker, _tx_json_bytes({"format": _TX_FORMAT, "uid": _tx_os.geteuid()}))
    else:
        value = _tx_read_json(marker)
        if value != {"format": _TX_FORMAT, "uid": _tx_os.geteuid()}:
            raise TxError("invalid_state", "Unrecognized transaction state marker.")
    transactions = _tx_os.path.join(state_dir, "transactions")
    if create:
        _tx_mkdir(transactions)
    elif not _tx_state_exists(transactions):
        # State initialization may have ended before its empty transaction tree.
        return False
    return True


@_tx_contextlib.contextmanager
def _tx_locked(state_dir, *, create=False):
    if not _tx_validate_state(state_dir, create=create):
        raise TxError("missing_state", "No transaction state exists at " + state_dir)
    path = _tx_os.path.join(state_dir, "lock")
    parent, name = _tx_parent(path)
    fd = None
    try:
        fd = _tx_os.open(name, _tx_os.O_RDWR | _tx_os.O_CREAT | _tx_os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
        info = _tx_os.fstat(fd)
        if not _tx_stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (
            info.st_uid != _tx_os.geteuid() or _tx_stat.S_IMODE(info.st_mode) != 0o600):
            raise TxError("unsafe_state", "Unsafe state lock file.")
        try:
            _tx_fcntl.flock(fd, _tx_fcntl.LOCK_EX | _tx_fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise TxError("busy", "Another transaction is using this state directory.") from exc
        yield
    finally:
        if fd is not None:
            _tx_os.close(fd)
        _tx_os.close(parent)


def _tx_id(transaction_id):
    if not isinstance(transaction_id, str) or len(transaction_id) != 32 or any(
        char not in "0123456789abcdef" for char in transaction_id):
        raise TxError("invalid_id", "Transaction IDs are 32 lowercase hexadecimal characters.")
    return transaction_id


def _tx_record_path(state_dir, transaction_id):
    return _tx_os.path.join(state_dir, "transactions", _tx_id(transaction_id), "record.json")


def _tx_load(state_dir, transaction_id):
    record = _tx_read_json(_tx_record_path(state_dir, transaction_id))
    if not isinstance(record, dict) or record.get("format") != _TX_FORMAT or (
        record.get("kind") != "transaction" or record.get("id") != transaction_id or
        record.get("state_dir") != state_dir or
        record.get("record_path") != _tx_record_path(state_dir, transaction_id) or
        record.get("directory") != _tx_os.path.dirname(_tx_record_path(state_dir, transaction_id))):
        raise TxError("invalid_state", "Transaction identity does not match its record.")
    for change in record.get("changes", []):
        path = _tx_path(change["path"])
        _tx_check_target_state(path, state_dir)
        for side in ("before", "after"):
            blob = change.get(side + "_blob")
            if blob is not None and (not isinstance(blob, str) or "/" in blob or blob in (".", "..")):
                raise TxError("invalid_state", "Invalid blob reference.")
    return record


def _tx_save(record):
    record["updated_at"] = _tx_now()
    _tx_private_write(_tx_record_path(record["state_dir"], record["id"]), _tx_json_bytes(record))


def _tx_all(state_dir):
    records = []
    directory = _tx_os.path.join(state_dir, "transactions")
    for name in _tx_os.listdir(directory):
        if name.startswith("."):
            continue
        _tx_id(name)
        records.append(_tx_load(state_dir, name))
    return sorted(records, key=lambda record: (record.get("sequence", 0), record["id"]))


def _tx_no_pending(records, exclude=None):
    pending = [r for r in records if r["id"] != exclude and r.get("status") in _TX_PENDING]
    if pending:
        raise TxError("recovery_required", "An interrupted transaction must be recovered first.",
                      record=pending[-1], details={"ids": [r["id"] for r in pending]})


def _tx_check_target_state(path, state_dir):
    if path == state_dir or path.startswith(state_dir + "/") or state_dir.startswith(path + "/"):
        raise TxError("unsafe_target", "A transaction target cannot overlap its state tree.")


def _tx_metadata(metadata):
    metadata = _tx_json.loads(_tx_json_bytes(metadata if metadata is not None else {}))
    if not isinstance(metadata, dict):
        raise TxError("invalid_metadata", "Metadata must be a JSON object.")
    for key in ("config_toml", "artifact_text"):
        if key in metadata and not isinstance(metadata[key], str):
            raise TxError("invalid_metadata", key + " must be text.")
    if metadata.get("artifact_suffix", ".txt") not in (".bash", ".zsh", ".sh", ".ps1", ".txt"):
        raise TxError("invalid_metadata", "Unsupported generated output suffix.")
    return metadata


def _tx_plan_bytes(changes, state_dir, metadata):
    state_dir = _tx_path(state_dir, state=True)
    _tx_validate_state(state_dir)
    prepared = []
    seen = set()
    for item in changes:
        path = _tx_path(item["path"])
        _tx_check_target_state(path, state_dir)
        if path in seen:
            raise TxError("duplicate_target", "Duplicate transaction target: " + path)
        seen.add(path)
        mode = item["mode"]
        if isinstance(mode, bool) or not isinstance(mode, int) or not (0 <= mode <= 0o7777):
            raise TxError("invalid_mode", "Invalid file mode.")
        before, _ = _tx_read(path)
        data = item["data"]
        after = {"exists": False}
        if data is not None:
            parent, _ = _tx_parent(path)
            try:
                parent_stat = _tx_os.fstat(parent)
            finally:
                _tx_os.close(parent)
            default_owner = (before["uid"], before["gid"]) if before["exists"] else (
                _tx_os.geteuid(), parent_stat.st_gid if parent_stat.st_mode & _tx_stat.S_ISGID else _tx_os.getegid())
            uid, gid = item.get("owner", default_owner)
            after = {"exists": True, "sha256": _tx_hash(data), "size": len(data),
                     "mode": mode, "uid": uid, "gid": gid}
        operation = "noop" if _tx_equal(before, after) else ("write" if data is not None else "remove")
        prepared.append({"path": path, "before": before, "after": after, "operation": operation,
                         "content_b64": _tx_base64.b64encode(data).decode("ascii") if data is not None else None})
    plan = {"format": _TX_FORMAT, "kind": "plan", "id": _tx_uuid.uuid4().hex,
            "created_at": _tx_now(), "state_dir": state_dir, "metadata": _tx_metadata(metadata),
            "changes": prepared, "change_count": sum(c["operation"] != "noop" for c in prepared)}
    plan["plan_sha256"] = _tx_hash(_tx_json_bytes(plan))
    return plan


def tx_plan(changes, state_dir, metadata=None):
    """Read-only plan: {path:absolute, content:str|None, mode:int, owner?:[uid,gid]}.

    None deletes the file; an absent deletion is a no-op. Existing parent
    directories are required. Symlinks and hardlinked/nonregular files fail.
    Explicit ownership is applied only with the caller's existing OS privileges.
    """
    if not isinstance(changes, list):
        raise TxError("invalid_changes", "Changes must be a list.")
    normalized = []
    for change in changes:
        if not isinstance(change, dict) or not {"path", "content", "mode"} <= change.keys():
            raise TxError("invalid_change", "Each change requires path, content and mode.")
        content = change["content"]
        if content is not None and not isinstance(content, str):
            raise TxError("invalid_content", "File content must be text or None.")
        mode = change["mode"]
        if isinstance(mode, bool) or not isinstance(mode, int) or not (0 <= mode <= 0o777):
            raise TxError("invalid_mode", "New file modes must be between 0000 and 0777.")
        try:
            data = content.encode("utf-8") if content is not None else None
        except UnicodeError as exc:
            raise TxError("invalid_content", "File content must be valid UTF-8.") from exc
        item = {"path": change["path"], "data": data, "mode": mode}
        if "owner" in change:
            owner = change["owner"]
            if not isinstance(owner, (list, tuple)) or len(owner) != 2 or any(
                    type(value) is not int or value < 0 or value >= 2**32 - 1 for value in owner):
                raise TxError("invalid_owner", "owner must contain two nonnegative UID/GID integers below 4294967295.")
            item["owner"] = tuple(owner)
        normalized.append(item)
    return _tx_plan_bytes(normalized, state_dir, metadata)


def _tx_validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("kind") != "plan" or plan.get("format") != _TX_FORMAT:
        raise TxError("invalid_plan", "Expected a transaction plan.")
    expected = plan.get("plan_sha256")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if expected != _tx_hash(_tx_json_bytes(unsigned)):
        raise TxError("invalid_plan", "Plan changed after creation; make a new plan.")
    _tx_id(plan["id"])
    _tx_path(plan["state_dir"], state=True)
    _tx_metadata(plan["metadata"])
    seen = set()
    for change in plan["changes"]:
        path = _tx_path(change["path"])
        _tx_check_target_state(path, plan["state_dir"])
        if path in seen:
            raise TxError("duplicate_target", "Duplicate target in plan.")
        seen.add(path)
        if change["after"]["exists"]:
            try:
                data = _tx_base64.b64decode(change["content_b64"], validate=True)
            except (ValueError, TypeError) as exc:
                raise TxError("invalid_plan", "Invalid staged content encoding.") from exc
            if _tx_hash(data) != change["after"]["sha256"] or len(data) != change["after"]["size"]:
                raise TxError("invalid_plan", "Content does not match plan digest.")


def _tx_stage_locked(plan):
    _tx_validate_plan(plan)
    records = _tx_all(plan["state_dir"])
    existing = next((r for r in records if r["id"] == plan["id"]), None)
    if existing:
        if existing.get("plan_sha256") != plan["plan_sha256"]:
            raise TxError("id_collision", "Transaction ID belongs to a different plan.")
        return existing
    _tx_no_pending(records)
    snapshots = []
    for change in plan["changes"]:
        current, original = _tx_read(change["path"])
        _tx_check_expected(current, change["before"], change["path"])
        snapshots.append((current, original))
    directory = _tx_os.path.dirname(_tx_record_path(plan["state_dir"], plan["id"]))
    _tx_mkdir(directory)
    entries = []
    for index, (change, (current, original)) in enumerate(zip(plan["changes"], snapshots)):
        entry = {key: value for key, value in change.items() if key != "content_b64"}
        entry["step"] = "staged"
        entry["before_blob"] = f"{index:04d}.before" if current["exists"] else None
        entry["after_blob"] = f"{index:04d}.after" if change["after"]["exists"] else None
        entries.append(entry)
    record = {"format": _TX_FORMAT, "kind": "transaction", "id": plan["id"],
              "sequence": max((r.get("sequence", 0) for r in records), default=0) + 1,
              "created_at": plan["created_at"], "state_dir": plan["state_dir"],
              "directory": directory, "record_path": _tx_os.path.join(directory, "record.json"),
              "status": "staging", "writer_pid": _tx_os.getpid(), "plan_sha256": plan["plan_sha256"],
              "metadata": plan["metadata"], "archives": {}, "changes": entries,
              "change_count": plan["change_count"], "events": [{"event": "stage_intent", "at": _tx_now()}]}
    _tx_save(record)
    try:
        for index, (change, (current, original)) in enumerate(zip(plan["changes"], snapshots)):
            for side, data in (("before", original), ("after", _tx_base64.b64decode(change["content_b64"])
                                                    if change["content_b64"] is not None else None)):
                filename = f"{index:04d}.{side}" if data is not None else None
                if filename is not None:
                    _tx_private_write(_tx_os.path.join(directory, filename), data)
        archives = {}
        for key, filename in (("config_toml", "config.toml"),
                              ("artifact_text", "output" + plan["metadata"].get("artifact_suffix", ".txt"))):
            if key in plan["metadata"]:
                data = plan["metadata"][key].encode("utf-8")
                path = _tx_os.path.join(directory, filename)
                _tx_private_write(path, data)
                archives[key] = {"path": path, "sha256": _tx_hash(data), "size": len(data)}
        record["status"] = "staged"
        record["archives"] = archives
        record["events"].append({"event": "staged", "at": _tx_now()})
        _tx_save(record)
        return record
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        record["failure"] = tx_error(exc)
        try:
            _tx_save(record)
        except Exception:
            pass
        raise TxError("stage_failed", "Staging failed before target changes; recover/cancel this transaction.",
                      record=record, details={"cause": tx_error(exc)}) from exc


def tx_stage(plan):
    """Persist intent, exact original bytes/ownership and intended bytes; touch no target."""
    _tx_validate_plan(plan)
    with _tx_locked(plan["state_dir"], create=True):
        return _tx_stage_locked(plan)


def _tx_blob(record, change, side):
    expected = change[side]
    if not expected["exists"]:
        return None
    filename = change[side + "_blob"]
    path = _tx_os.path.join(record["directory"], filename)
    snapshot, data = _tx_read(path)
    if (not snapshot["exists"] or snapshot["uid"] != _tx_os.geteuid() or snapshot["mode"] != 0o600
            or _tx_hash(data) != expected["sha256"] or len(data) != expected["size"]):
        raise TxError("corrupt_backup", "Missing or altered transaction blob: " + path, record=record)
    return data


def _tx_compensate(record, *, recovery=False):
    record["status"] = "recovering" if recovery else "compensating"
    record["recovery_goal"] = "before"
    _tx_save(record)
    conflicts = []
    for index in range(len(record["changes"]) - 1, -1, -1):
        change = record["changes"][index]
        if change["operation"] == "noop" or change["step"] in ("staged", "unchanged"):
            continue
        try:
            current, _ = _tx_read(change["path"])
            if _tx_equal(current, change["before"]):
                change["step"] = "restored"
                continue
            if not _tx_equal(current, change["after"]):
                raise TxError("drift", "Recovery preserves a file that no longer matches this transaction: " + change["path"])
            record["pending_index"] = index
            change["step"] = "restore_intent"
            _tx_save(record)
            _tx_replace(change["path"], _tx_blob(record, change, "before"), change["before"], current)
            change["step"] = "restored"
            record["pending_index"] = None
            _tx_save(record)
        except Exception as exc:
            conflicts.append({"path": change["path"], **tx_error(exc)})
    record["conflicts"] = conflicts
    record["status"] = "needs_recovery" if conflicts else ("recovered" if recovery else "failed_rolled_back")
    record["completed_at"] = _tx_now()
    record["events"].append({"event": record["status"], "at": _tx_now()})
    _tx_save(record)
    return record


def _tx_apply_locked(record):
    record = _tx_load(record["state_dir"], record["id"])
    if record["status"] in ("applied", "noop"):
        return record
    if record["status"] != "staged":
        raise TxError("invalid_status", "Only a staged transaction can be applied; recover interrupted work first.", record=record)
    _tx_no_pending(_tx_all(record["state_dir"]), exclude=record["id"])
    # Validate everything before the first mutation; then recheck each replace.
    try:
        for change in record["changes"]:
            current, _ = _tx_read(change["path"])
            _tx_check_expected(current, change["before"], change["path"])
            if change["operation"] != "noop":
                _tx_blob(record, change, "before")
                _tx_blob(record, change, "after")
    except TxError as exc:
        exc.record = record
        raise
    record["status"] = "applying"
    record["recovery_goal"] = "before"
    record["events"].append({"event": "apply_intent", "at": _tx_now()})
    _tx_save(record)
    try:
        for index, change in enumerate(record["changes"]):
            if change["operation"] == "noop":
                change["step"] = "unchanged"
                continue
            record["pending_index"] = index
            change["step"] = "write_intent"
            _tx_save(record)
            change["observed_after"] = _tx_replace(change["path"], _tx_blob(record, change, "after"),
                                                   change["after"], change["before"])
            change["step"] = "applied"
            record["pending_index"] = None
            _tx_save(record)
        record["status"] = "applied" if record["change_count"] else "noop"
        record["completed_at"] = _tx_now()
        record["events"].append({"event": record["status"], "at": _tx_now()})
        _tx_save(record)
        return record
    except Exception as exc:
        record["failure"] = tx_error(exc)
        try:
            _tx_compensate(record)
        except Exception as recovery_error:
            record["status"] = "needs_recovery"
            record["compensation_error"] = tx_error(recovery_error)
            try:
                _tx_save(record)
            except Exception:
                pass
        raise TxError("apply_failed", "Apply failed; inspect transaction status before retrying.",
                      record=record, details={"cause": tx_error(exc)}) from exc
    except (KeyboardInterrupt, SystemExit) as exc:
        # Leave the durable intent intact. Recovery reverses only unchanged owned data.
        raise TxError("interrupted", "Apply interrupted. Run recovery for this transaction before new mutations.",
                      record=record) from exc


def tx_apply(plan_or_record):
    """Apply a plan (auto-stage) or an existing staged record under one process lock."""
    if not isinstance(plan_or_record, dict):
        raise TxError("invalid_plan", "Expected a plan or staged transaction record.")
    if plan_or_record.get("kind") == "plan":
        _tx_validate_plan(plan_or_record)
        with _tx_locked(plan_or_record["state_dir"], create=True):
            return _tx_apply_locked(_tx_stage_locked(plan_or_record))
    state_dir = _tx_path(plan_or_record.get("state_dir"), state=True)
    transaction_id = _tx_id(plan_or_record.get("id"))
    with _tx_locked(state_dir):
        return _tx_apply_locked(_tx_load(state_dir, transaction_id))


def tx_history(state_dir):
    """Read-only chronological records, including complete metadata and archive paths."""
    state_dir = _tx_path(state_dir, state=True)
    if not _tx_validate_state(state_dir):
        return []
    records = _tx_all(state_dir)
    by_id = {r["id"]: r for r in records}
    for source_id, inverse_id in _tx_undone(records).items():
        if source_id in by_id:
            by_id[source_id]["rolled_back_by"] = inverse_id
    return records


def _tx_undone(records):
    """Effective inverse relationships, including inverses that are themselves undone."""
    undone = {}
    for record in reversed(records):
        if record.get("status") not in ("applied", "noop") or record["id"] in undone:
            continue
        if record["metadata"].get("operation") == "rollback":
            source = record["metadata"].get("source_transaction_id")
            if source is not None:
                undone.setdefault(source, record["id"])
    return undone


def _tx_latest(records):
    latest = {}
    for record in records:
        if record.get("status") != "applied":
            continue
        for change in record["changes"]:
            if change["operation"] != "noop":
                latest[change["path"]] = (record, change)
    return latest


def _tx_owner(record, path=None):
    # An inverse physically writes a file while restoring an earlier owner's
    # intended bytes. Ownership can differ per path, so it is recorded per path.
    restored = record["metadata"].get("restored_owners", {})
    if path is not None and path in restored:
        return restored[path]
    return record["metadata"].get("owner_transaction_id", record["id"])


def tx_audit(state_dir):
    """Read-only findings: state, path, severity, transaction_id and message."""
    state_dir = _tx_path(state_dir, state=True)
    if not _tx_validate_state(state_dir):
        return []
    findings = []
    records = []
    for transaction_id in _tx_os.listdir(_tx_os.path.join(state_dir, "transactions")):
        if transaction_id.startswith("."):
            continue
        try:
            record = _tx_load(state_dir, transaction_id)
            records.append(record)
            if record["status"] in _TX_PENDING:
                findings.append({"state": "recovery_required", "severity": "error", "transaction_id": transaction_id,
                                 "path": record["record_path"], "message": "Unfinished transaction; check whether its writer is active before recovery."})
            if record["status"] not in ("staging", "cancelled"):
                for change in record["changes"]:
                    for side in ("before", "after"):
                        _tx_blob(record, change, side)
        except Exception as exc:
            findings.append({"state": "invalid_record", "severity": "error", "transaction_id": transaction_id,
                             "path": _tx_os.path.join(state_dir, "transactions", transaction_id), "message": str(exc)})
    records.sort(key=lambda r: (r.get("sequence", 0), r["id"]))
    for path, (record, change) in _tx_latest(records).items():
        try:
            current, _ = _tx_read(path)
            state = "ok" if _tx_equal(current, change["after"]) else ("missing" if not current["exists"] else "modified")
            findings.append({"state": state, "severity": "info" if state == "ok" else "warning",
                             "transaction_id": record["id"], "owner_transaction_id": _tx_owner(record, path),
                             "path": path, "message": "Matches intended state." if state == "ok" else "Current file differs from intended state."})
        except Exception as exc:
            findings.append({"state": "unsafe_target", "severity": "error", "transaction_id": record["id"],
                             "path": path, "message": str(exc)})
    return findings


def tx_recover(state_dir, transaction_id):
    """Reverse an interrupted apply. Preserve external edits and report conflicts."""
    state_dir = _tx_path(state_dir, state=True)
    transaction_id = _tx_id(transaction_id)
    with _tx_locked(state_dir):
        snapshot, _ = _tx_read(_tx_record_path(state_dir, transaction_id))
        if not snapshot["exists"]:
            # A crash can occur between mkdir and the initial durable journal.
            # With no journal, do not infer or touch *any* destination path.
            directory = _tx_os.path.dirname(_tx_record_path(state_dir, transaction_id))
            if not _tx_state_exists(directory):
                raise TxError("missing_transaction", "No transaction directory exists.")
            for filename in _tx_os.listdir(directory):
                archived, _ = _tx_read(_tx_os.path.join(directory, filename))
                if archived["uid"] != _tx_os.geteuid() or archived["mode"] != 0o600:
                    raise TxError("unsafe_state", "Unprotected file in orphan transaction directory.")
            known = []
            for other in _tx_os.listdir(_tx_os.path.join(state_dir, "transactions")):
                if other == transaction_id or other.startswith("."):
                    continue
                try:
                    known.append(_tx_load(state_dir, other))
                except TxError:
                    continue
            record = {"format": _TX_FORMAT, "kind": "transaction", "id": transaction_id,
                      "state_dir": state_dir, "directory": directory,
                      "record_path": _tx_record_path(state_dir, transaction_id),
                      "sequence": max((r.get("sequence", 0) for r in known), default=0) + 1,
                      "created_at": _tx_now(), "completed_at": _tx_now(), "status": "abandoned",
                      "metadata": {"operation": "recover_orphan", "warning":
                                   "Missing journal: preserved archive files; no destination state inferred or changed."},
                      "archives": {}, "changes": [], "change_count": 0,
                      "events": [{"event": "orphan_abandoned_without_target_changes", "at": _tx_now()}]}
            _tx_save(record)
            return record
        record = _tx_load(state_dir, transaction_id)
        if record["status"] in ("recovered", "failed_rolled_back", "cancelled", "abandoned"):
            return record
        if record["status"] in ("staging", "staged"):
            record["status"] = "cancelled"
            record["completed_at"] = _tx_now()
            record["events"].append({"event": "cancelled_before_apply", "at": _tx_now()})
            _tx_save(record)
            return record
        if record["status"] not in _TX_PENDING:
            raise TxError("invalid_status", "Recovery is only for an interrupted transaction.", record=record)
        _tx_no_pending(_tx_all(state_dir), exclude=transaction_id)
        return _tx_compensate(record, recovery=True)


def tx_rollback(state_dir, transaction_id):
    """Create a journalled inverse transaction; refuse drift or superseded ownership."""
    state_dir = _tx_path(state_dir, state=True)
    transaction_id = _tx_id(transaction_id)
    with _tx_locked(state_dir):
        records = _tx_all(state_dir)
        _tx_no_pending(records)
        source = _tx_load(state_dir, transaction_id)
        undone = _tx_undone(records)
        completed = [r for r in records if r["status"] in ("applied", "noop") and
                     r["id"] not in undone and
                     r["metadata"].get("operation") == "rollback" and
                     r["metadata"].get("source_transaction_id") == transaction_id]
        if completed:
            return completed[-1]
        if source["status"] not in ("applied", "noop"):
            raise TxError("invalid_status", "Only completed transactions can be rolled back.", record=source)
        latest = _tx_latest(records)
        preceding = _tx_latest([r for r in records if r.get("sequence", 0) < source.get("sequence", 0)])
        changes = []
        restored_owners = {}
        for change in reversed(source["changes"]):
            if change["operation"] == "noop":
                continue
            owner = latest.get(change["path"])
            if owner is None or (owner[0]["id"] != transaction_id and
                                 _tx_owner(owner[0], change["path"]) != transaction_id):
                raise TxError("superseded", "A newer transaction owns " + change["path"], record=source)
            current, _ = _tx_read(change["path"])
            _tx_check_expected(current, change["after"], change["path"], identity=False)
            before = change["before"]
            item = {"path": change["path"], "data": _tx_blob(source, change, "before"),
                    "mode": before.get("mode", 0o600)}
            if before["exists"]:
                item["owner"] = (before["uid"], before["gid"])
            changes.append(item)
            prior = preceding.get(change["path"])
            restored_owners[change["path"]] = (_tx_owner(prior[0], change["path"])
                                               if prior and _tx_equal(prior[1]["after"], before) else None)
        plan = _tx_plan_bytes(changes, state_dir, {"operation": "rollback", "source_transaction_id": transaction_id,
                                                 "restored_owners": restored_owners})
        return _tx_apply_locked(_tx_stage_locked(plan))


def tx_repair(state_dir, transaction_id):
    """Restore latest-owned missing files. Preserve modified/superseded files; no force."""
    state_dir = _tx_path(state_dir, state=True)
    transaction_id = _tx_id(transaction_id)
    with _tx_locked(state_dir):
        records = _tx_all(state_dir)
        _tx_no_pending(records)
        source = _tx_load(state_dir, transaction_id)
        if source["status"] != "applied":
            raise TxError("invalid_status", "Repair requires a completed applied transaction.", record=source)
        latest = _tx_latest(records)
        changes, preserved, unchanged = [], [], []
        for change in source["changes"]:
            if change["operation"] == "noop":
                continue
            owned = latest.get(change["path"])
            if owned is None or _tx_owner(owned[0], change["path"]) != transaction_id:
                preserved.append({"path": change["path"], "reason": "superseded"})
                continue
            try:
                current, _ = _tx_read(change["path"])
            except TxError as exc:
                preserved.append({"path": change["path"], "reason": exc.code})
                continue
            if _tx_equal(current, change["after"]):
                unchanged.append(change["path"])
            elif not current["exists"] and change["after"]["exists"]:
                after = change["after"]
                changes.append({"path": change["path"], "data": _tx_blob(source, change, "after"),
                                "mode": after["mode"], "owner": (after["uid"], after["gid"])})
            else:
                preserved.append({"path": change["path"], "reason": "modified"})
        metadata = {"operation": "repair", "source_transaction_id": transaction_id,
                    "owner_transaction_id": transaction_id, "preserved": preserved, "unchanged": unchanged}
        plan = _tx_plan_bytes(changes, state_dir, metadata)
        return _tx_apply_locked(_tx_stage_locked(plan))

# ============================= 5. CLI AND WIZARD =============================

def resolve_input(args):
    """Return configuration plus bytes. Importing does not execute those bytes."""
    imported = bool(getattr(args, 'artifact', None))
    if imported:
        artifact = _source_text(args.artifact)
        if len(artifact.encode()) > MAX_ARTIFACT_BYTES:
            raise MotdError('Artifact exceeds 2 MB')
        try:
            config = extract_config(artifact)
        except MotdError:
            args.opaque_artifact = True
            config = preset_config('workshop')
            if not getattr(args, 'target', None):
                raise MotdError('Unrecognized artifact: choose --target explicitly; inspection never guesses execution type')
        if getattr(args, 'target', None) and args.target != config['target']:
            if '# MOTD-BODY-BEGIN' in artifact:
                raise MotdError('Recover the recipe and rebuild to change the type of a generated artifact')
            config['target'] = args.target
        if getattr(args, 'shell', None) and args.shell != config['shell'] and '# MOTD-BODY-BEGIN' in artifact:
            raise MotdError('Recover the recipe and rebuild to change a generated artifact interpreter')
    elif getattr(args, 'config', None):
        config = load_config(args.config); artifact = None
    else:
        config = preset_config(getattr(args, 'preset', None) or 'workshop'); artifact = None
    for key in ('name', 'target', 'shell', 'audience'):
        if getattr(args, key, None) is not None:
            if key == 'shell': select_shell(config, args.shell)
            else: config[key] = getattr(args, key)
    config = validate_config(config)
    if imported and config['target'] == 'shell' and args.command in ('install', 'upgrade', 'reconfigure'):
        if not args.trust_artifact:
            raise MotdError('Imported shell output is executable code, even with metadata. Inspect it, then use --trust-artifact to install its exact bytes.')
    return config, artifact if artifact is not None else generate_artifact(config)


def export_files(config, artifact, output, recipe_path=None, *, state_dir=None, replace=False, opaque_artifact=False):
    if opaque_artifact and recipe_path:
        raise MotdError('An opaque output has no reconstructable recipe; retain the exact archived output')
    changes = []
    if output == '-':
        sys.stdout.write(artifact)
    else:
        changes.append({'path': absolute(output), 'content': artifact,
                        'mode': 0o755 if config['target'] == 'shell' else 0o644})
    if recipe_path:
        changes.append({'path': absolute(recipe_path), 'content': dump_config(config), 'mode': 0o600})
    for change in changes:
        old, _ = _file_text(change['path'])
        if old['exists'] and old['sha256'] != hashlib.sha256(change['content'].encode()).hexdigest() and not replace:
            raise MotdError(f'Output exists: {change["path"]}; choose another path or --replace (with backup)')
    if not changes: return None
    metadata = {'operation': 'build', 'name': config['name'],
                'artifact_text': artifact, 'artifact_suffix': artifact_suffix(config),
                'artifact_origin': 'opaque-import' if opaque_artifact else 'recipe'}
    if not opaque_artifact: metadata['config_toml'] = dump_config(config)
    plan = tx_plan(changes, absolute(state_dir or default_state()), metadata)
    result = tx_apply(plan)
    stream = sys.stderr if output == '-' else sys.stdout
    for change in changes: print('Wrote:', change['path'], file=stream)
    print('Recovery archive:', result['directory'], file=stream)
    return result


def preview(config, artifact, *, live=False, imported=False, trust=False):
    if config['target'] != 'shell':
        print(artifact, end='')
        return 0
    if imported:
        try:
            config = extract_config(artifact)
            artifact = generate_artifact(config)
            imported = False
            print('Preview regenerated from the checked recipe; original imported code is not executed.', file=sys.stderr)
        except MotdError:
            if not (trust and live):
                raise MotdError('Unknown executable output cannot provide a safe demo. Explicit --live --trust-artifact executes its code.')
            print('Executing explicitly trusted imported code; its side effects cannot be suppressed.', file=sys.stderr)
    if not live: print('Synthetic demonstration; before/after hooks are skipped.', file=sys.stderr)
    elif not imported: print('Live observations; configured before/after calls are skipped.', file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix='motd-preview-') as folder:
        script = Path(folder) / ('preview' + artifact_suffix(config)); script.write_text(artifact, encoding='utf-8')
        cmd = preview_command(config, script, live=live, no_hooks=not imported)
        budget = 8 + sum(h['timeout_seconds'] + 0.3 for phase in config['hooks'].values() for h in phase)
        return subprocess.run(cmd, check=False, timeout=budget).returncode


def save_recipe(config, path, state_dir, replace=False):
    path = absolute(path)
    existing, _ = _file_text(path)
    if existing['exists'] and not replace:
        raise MotdError('Recipe output exists; choose another path or --replace')
    text = dump_config(config)
    plan = tx_plan([{'path': path, 'content': text, 'mode': 0o600}], state_dir,
                   {'operation': 'save-config', 'name': config['name'], 'config_toml': text})
    result = tx_apply(plan)
    print('Saved recipe:', path)
    return result


def _select(label, choices, default=0):
    print('\n' + label)
    for i, (text, value) in enumerate(choices, 1): print(f'  {i}. {text}')
    while True:
        raw = input(f'Choice [{default + 1}]: ').strip()
        if not raw: return choices[default][1]
        if raw.isdigit() and 1 <= int(raw) <= len(choices): return choices[int(raw) - 1][1]
        print('Choose a listed number.')


def _ask(label, default):
    answer = input(f'{label} [{default}]: ').strip()
    return answer if answer else default


class WizardCancelled(Exception):
    """Leave the draft without changing installed files."""


def preview_command(config, path, *, live=False, no_hooks=True, width=None, color=None):
    """One interpreter decision shared by CLI previews and wizard previews."""
    kind = config['shell']
    executable = (shutil.which('pwsh') or shutil.which('powershell')) if kind == 'powershell' else shutil.which(kind)
    if not executable:
        raise MotdError(f'{kind} is unavailable on this computer; build here and preview on a compatible host')
    if kind == 'powershell':
        command = [executable, '-NoLogo', '-NoProfile', '-File', str(path)]
        if not live: command.append('-Demo')
        if no_hooks: command.append('-NoHooks')
        if width: command += ['-Width', str(width)]
        if color and not live and 'NO_COLOR' not in os.environ: command.append('-Color')
        if color is False or 'NO_COLOR' in os.environ: command.append('-Plain')
    else:
        command = [executable, str(path)]
        if not live: command.append('--demo')
        if no_hooks and (kind == 'sh' or any(config['hooks'].values())): command.append('--no-hooks')
        if width: command += ['--width', str(width)]
        if color is False: command.append('--plain')
        elif color and kind == 'sh': command.append('--color')
    return command


def demo_text(config, width=None, *, color=False):
    """Render our checked template with fixture data; never execute imported code.

    This uses a temporary output only, not the transaction state directory. No
    configured hook or live collector is enabled. Missing interpreters produce
    an explicit unavailable preview instead of a different renderer's picture.
    """
    c = validate_config(config)
    artifact = generate_artifact(c)
    if c['target'] != 'shell':
        # Show intended public text; agetty serialization is inspected in plan.
        return c['display']['title'] + '\n\n' + c['public_text'].strip() + '\n'
    with tempfile.TemporaryDirectory(prefix='motd-demo-') as folder:
        path = Path(folder) / ('preview' + artifact_suffix(c))
        path.write_text(artifact, encoding='utf-8')
        command = preview_command(c, path, width=width, color=color)
        result = subprocess.run(command, capture_output=True, text=True, timeout=8,
                                encoding='utf-8', errors='replace')
    if result.returncode:
        raise MotdError('Preview failed: ' + (result.stderr.strip() or str(result.returncode))[:500])
    return result.stdout


_SGR = re.compile(r'\x1b\[[0-9;]*m')


def terminal_line(text, columns, *, color=True):
    """Clip by terminal cells and allow only SGR, never arbitrary terminal codes."""
    output = []; used = 0; position = 0
    while position < len(text):
        match = _SGR.match(text, position)
        if match:
            if color: output.append(match[0])
            position = match.end(); continue
        ch = text[position]; position += 1
        if ord(ch) < 32 or 0x7f <= ord(ch) < 0xa0: continue
        cells = 0 if unicodedata.combining(ch) else (2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1)
        if used + cells > columns: break
        output.append(ch); used += cells
    if color: output.append('\x1b[0m')
    return ''.join(output)


class WizardUI:
    """Small page renderer; normal line input keeps the terminal recoverable.

    No raw keyboard mode, curses dependency, hidden cursor or alternate screen.
    The same choices and draft work in screen and transcript-friendly line mode.
    Terminal size is re-read for every page, including after resize.
    """
    def __init__(self, mode='auto'):
        self.mode = mode
        self.cache = {}

    @property
    def screen(self):
        if self.mode == 'line': return False
        if not (sys.stdin.isatty() and sys.stdout.isatty()): return False
        size = shutil.get_terminal_size((80, 24))
        if size.columns < 60 or size.lines < 20: return False
        term = os.environ.get('TERM', '')
        supported = term.startswith(('xterm', 'screen', 'tmux', 'linux', 'vt', 'ansi', 'rxvt', 'alacritty', 'foot', 'wezterm', 'kitty'))
        return self.mode == 'screen' or supported

    def sample(self, config, width):
        color = self.screen and 'NO_COLOR' not in os.environ
        key = (dump_config(config), width, color)
        if key not in self.cache:
            try: self.cache[key] = demo_text(config, width, color=color).splitlines()
            except (MotdError, OSError, subprocess.TimeoutExpired) as exc:
                self.cache[key] = ['Preview unavailable: ' + str(exc)]
            if len(self.cache) > 24: self.cache.pop(next(iter(self.cache)))
        return self.cache[key]

    def page(self, title, lines=(), *, config=None, notice='', footer=''):
        size = shutil.get_terminal_size((80, 24))
        width = max(20, size.columns - 1)
        screen = self.screen
        color = screen and 'NO_COLOR' not in os.environ
        if screen: print('\x1b[2J\x1b[H', end='')
        accent = '\x1b[1;36m' if color else ''
        reset = '\x1b[0m' if color else ''
        body = [accent + f'MOTD {VERSION} | {title}' + reset, '-' * min(width, 78)]
        body.extend(lines)
        if notice: body.extend(textwrap.wrap(notice, width)[:2])
        if config is not None and screen:
            sample = self.sample(config, max(40, min(width, config['display']['width'])))
            available = max(0, size.lines - len(body) - 6)
            if available:
                body += ['', accent + 'PREVIEW | synthetic data; configured calls skipped' + reset]
                body += sample[:available]
                if len(sample) > available:
                    body.append(f'... showing {available}/{len(sample)} lines; P opens the full preview.')
        if footer: body += ['', footer]
        for line in body:
            print(terminal_line(line, width, color=color) if screen else _SGR.sub('', line))

    def select(self, title, choices, default=0, *, preview_factory=None, config=None):
        selected = default
        while True:
            current = preview_factory(choices[selected][1]) if preview_factory else config
            self.page(title, [f' {i}. {label}' + (' [selected]' if i - 1 == selected and preview_factory else '')
                              for i, (label, _) in enumerate(choices, 1)], config=current,
                      footer='Number changes the preview; Enter accepts. P preview | Q cancel' if preview_factory and self.screen else '')
            raw = input(f'Choice [{selected + 1}]: ').strip().lower()
            if raw == 'q': raise WizardCancelled()
            if raw == 'p' and current is not None: self.full_preview(current); continue
            if not raw: return choices[selected][1]
            if raw.isdigit() and 1 <= int(raw) <= len(choices):
                selected = int(raw) - 1
                if not (preview_factory and self.screen): return choices[selected][1]

    def full_preview(self, config):
        size = shutil.get_terminal_size((80, 24))
        lines = self.sample(config, max(40, min(size.columns - 1, config['display']['width'])))
        if not self.screen:
            print('Synthetic demonstration; before/after hooks are skipped.')
            print('\n'.join(lines)); return
        start = 0
        while True:
            size = shutil.get_terminal_size((80, 24)); count = max(5, size.lines - 6)
            self.page('Full preview', lines[start:start + count],
                      footer=f'Lines {start + 1}-{min(start + count, len(lines))}/{len(lines)} | N next | B previous | Enter return')
            raw = input('Preview: ').strip().lower()
            if not raw: return
            if raw == 'q': raise WizardCancelled()
            if raw == 'n': start = min(max(0, len(lines) - count), start + count)
            elif raw == 'b': start = max(0, start - count)

    def pause(self):
        if self.screen: input('Press Enter to return to the wizard: ')


def _get_setting(config, path):
    value = config
    for part in path.split('.'): value = value[part]
    return value


def _set_setting(config, path, value):
    if path == 'shell': select_shell(config, value); return
    parts = path.split('.'); table = config
    for part in parts[:-1]: table = table[part]
    table[parts[-1]] = value


def _configuration_pages(config):
    """A short list of data-driven pages, shared by both UI modes."""
    destination = [('Name', 'name', 'text'), ('Placement', 'target', 'choice')]
    if config['target'] == 'shell':
        destination += [('Output interpreter', 'shell', 'choice'), ('Session filter', 'audience', 'choice'),
                        ('Display frequency', 'frequency', 'choice')]
    appearance = [('Heading', 'display.title', 'text')]
    pages = [('Destination', destination), ('Appearance', appearance)]
    if config['target'] == 'shell':
        appearance += [('Site label', 'display.site', 'text'), ('Theme', 'display.theme', 'choice'),
                       ('Maximum columns', 'display.width', 'int'), ('Row budget', 'display.rows', 'int')]
        pages.append(('Sections', [(name, name, 'section') for name in SECTION_IDS]))
        pages.append(('Content', [('Required services', 'services.required', 'list'),
                                  ('Excluded service patterns', 'services.exclude', 'list'),
                                  ('Displayed notices', 'messages', 'messages')]))
        pages.append(('Before and after calls', [('Add a before call', 'before', 'hook'), ('Add an after call', 'after', 'hook'),
                                                ('Clear before calls', 'before', 'clear'), ('Clear after calls', 'after', 'clear')]))
    else:
        pages.append(('Public notice', [('Public text', 'public_text', 'multiline')]))
    return pages


def _configure(config, ui=None):
    """Edit a validated in-memory draft. Back retains choices; cancel writes nothing."""
    ui = ui or WizardUI()
    c = validate_config(config); page_index = 0; notice = ''
    choices = {
        'target': [('Authenticated shell greeting', 'shell'), ('agetty pre-login issue text', 'issue'),
                   ('SSH pre-authentication banner file', 'ssh-banner'), ('Generic static text', 'text')],
        'shell': [('Bash: full Linux dashboard', 'bash'), ('Zsh: shared Bash dashboard', 'zsh'),
                  ('POSIX sh: reduced portable display', 'sh'), ('PowerShell: native baseline', 'powershell')],
        'audience': [('All eligible sessions', 'all'), ('SSH environment markers present', 'ssh'),
                     ('Non-SSH sessions (not proof of a physical console)', 'local')],
        'frequency': [('Login startup', 'login'), ('Every interactive shell', 'interactive')],
        'display.theme': [(x.title(), x) for x in ('cyan', 'green', 'amber', 'mono')],
    }
    while True:
        pages = _configuration_pages(c); page_index = min(page_index, len(pages) - 1)
        title, fields = pages[page_index]
        lines = []
        for number, (label, path, kind) in enumerate(fields, 1):
            if kind == 'section': value = '[x]' if path in c['display']['sections'] else '[ ]'
            elif kind in ('hook', 'clear'): value = f'{len(c["hooks"][path])} configured'
            else:
                value = _get_setting(c, path)
                if isinstance(value, list): value = ', '.join(value) or '(none)'
                value = str(value).replace('\n', ' / ')
            lines.append(f' {number}. {label}: {value}')
        ui.page(f'{title} | page {page_index + 1}/{len(pages)}', lines, config=c, notice=notice,
                footer='Number edits | Enter/N next | B back | P full preview | Q cancel')
        notice = ''; raw = input('Page choice: ').strip().lower()
        if raw == 'q': raise WizardCancelled()
        if raw == 'p': ui.full_preview(c); continue
        if raw == 'b': page_index = max(0, page_index - 1); continue
        if raw in ('', 'n'):
            if page_index == len(pages) - 1: return validate_config(c)
            page_index += 1; continue
        if not raw.isdigit() or not 1 <= int(raw) <= len(fields):
            notice = 'Choose a listed field or navigation command.'; continue
        label, path, kind = fields[int(raw) - 1]; candidate = copy.deepcopy(c)
        try:
            if kind == 'section':
                selected = candidate['display']['sections']
                if path in selected: selected.remove(path)
                else: selected.append(path)
            elif kind == 'choice':
                values = choices[path]; current = _get_setting(c, path)
                def variation(value):
                    result = copy.deepcopy(c); _set_setting(result, path, value)
                    if path == 'target' and value != 'shell': result['hooks'] = {'before': [], 'after': []}
                    return result
                value = ui.select(label, values, [v for _, v in values].index(current), preview_factory=variation)
                _set_setting(candidate, path, value)
                if path == 'target' and value != 'shell': candidate['hooks'] = {'before': [], 'after': []}
            elif kind == 'hook':
                print('Explicit argv as JSON, e.g. ["fastfetch"] or ["bash", "-c", "command | other"].')
                argv = json.loads(input('Arguments: '))
                seconds = float(_ask('Timeout seconds', '1'))
                policy = ui.select('On call failure', [('Continue the display', 'continue'), ('Stop this display', 'stop')])
                candidate['hooks'][path].append({'argv': argv, 'timeout_seconds': seconds, 'on_failure': policy})
            elif kind == 'clear':
                if confirm(f'Clear {path} calls in this draft?'): candidate['hooks'][path] = []
            else:
                current = _get_setting(c, path)
                if kind == 'list': default = ','.join(current)
                elif kind == 'messages': default = '\\n'.join(current)
                else: default = str(current).replace('\n', '\\n')
                print('Blank keeps the value; - clears text/lists. Use \\n between notice lines.' if kind != 'int' else 'Enter a whole number; blank keeps the value.')
                value = _ask(label, default)
                if kind != 'int' and value == '-': value = ''
                if kind == 'int': value = int(value)
                elif kind == 'list': value = [v.strip() for v in value.split(',') if v.strip()]
                elif kind == 'messages': value = value.split('\\n') if value else []
                elif kind == 'multiline': value = value.replace('\\n', '\n')
                _set_setting(candidate, path, value)
            c = validate_config(candidate)
        except (MotdError, ValueError, TypeError) as exc:
            notice = str(exc)


def _choose_record(state_dir, *, installs=False, ui=None):
    records = list(active_installs(state_dir).values()) if installs else tx_history(state_dir)
    if not records: raise MotdError('No matching transactions or installations in this state directory')
    records.reverse()
    return (ui.select if ui else _select)('Choose the item', [(f"{r['id'][:12]} {r['status']} {r['metadata'].get('operation')} {r['metadata'].get('name', '')}", r) for r in records])


def _manage(command, state_dir, transaction_id=None, name=None, yes=False):
    if command == 'uninstall':
        return apply_reviewed(uninstall_plan(name, state_dir), yes)
    if command == 'recover':
        # Recovery must remain reachable when a partially staged directory has no
        # journal and history cannot yet be read. The engine validates the ID.
        print('Recover interrupted transaction:', transaction_id)
        print('Recorded states are reversed conservatively; orphan archives are preserved.')
        if not confirm('Proceed with recovery?', yes): print('Cancelled.'); return None
        result = tx_recover(state_dir, transaction_id)
        print(result['status'] + ': ' + result['id'])
        for conflict in result.get('conflicts', []): print('Recovery conflict:', conflict)
        return result
    if command == 'repair':
        if not name:
            source = next((r for r in tx_history(state_dir) if r['id'] == transaction_id), None)
            name = source.get('metadata', {}).get('name') if source else None
        if name and name in active_installs(state_dir):
            plan = repair_installation_plan(name, state_dir)
            for item in plan['metadata']['preserved']: print('Preserved:', item['path'], item['reason'])
            return apply_reviewed(plan, yes)
    records = tx_history(state_dir)
    source = next((r for r in records if r['id'] == transaction_id), None)
    if not source: raise MotdError('Unknown transaction ID')
    print(f'{command}: {source["id"]} ({source["status"]})')
    for item in source['changes']:
        print(' ', item['path'], '|', item['operation'])
    if command == 'repair':
        print('Only missing latest-owned files are restored; modified files are preserved.')
    elif command == 'recover':
        print('Reverse an interrupted apply where the recorded pre/postimage permits it.')
    else:
        print('Restore the recorded before-state. Later ownership or drift rejects rollback.')
    if not confirm('Proceed with this operation?', yes):
        print('Cancelled.'); return None
    result = {'repair': tx_repair, 'rollback': tx_rollback, 'recover': tx_recover}[command](state_dir, transaction_id)
    print(result['status'] + ': ' + result['id'])
    for preserved in result.get('metadata', {}).get('preserved', []): print('Preserved:', preserved)
    for conflict in result.get('conflicts', []): print('Recovery conflict:', conflict)
    return result


def wizard(args):
    if not sys.stdin.isatty():
        raise MotdError('The wizard needs a terminal. Use --help for noninteractive commands.')
    ui = WizardUI(getattr(args, 'ui', 'auto'))
    action = ui.select('What do you want to do?', [
        ('Create/customise a message', 'create'), ('Install existing recipe or output', 'existing'),
        ('Reconfigure/upgrade an installed message', 'reconfigure'), ('Inspect/audit', 'audit'),
        ('Repair missing files', 'repair'), ('Recover interrupted changes', 'recover'),
        ('Roll back a transaction', 'rollback'), ('Uninstall', 'uninstall'), ('Exit', 'exit')])
    if action == 'exit': return 0
    scope = ui.select('Installation scope', [('This user', 'user'), ('System-wide', 'system')],
                      1 if args.scope == 'system' else 0)
    state_dir = absolute(args.state_dir or default_state(scope))
    if action == 'audit':
        print(json.dumps(tx_audit(state_dir), indent=2)); return 0
    if action in ('repair', 'rollback', 'recover', 'uninstall'):
        try:
            r = _choose_record(state_dir, installs=action in ('uninstall', 'repair'), ui=ui)
        except TxError:
            if action != 'recover': raise
            transaction_id = input('History is incomplete. Enter the interrupted transaction ID: ').strip()
            _manage(action, state_dir, transaction_id); return 0
        _manage(action, state_dir, r['id'], r['metadata'].get('name')); return 0
    artifact = None; imported = False; trusted = False; opaque = False
    install_options = {}
    if action == 'reconfigure':
        r = _choose_record(state_dir, installs=True, ui=ui)
        if r['metadata'].get('artifact_origin') == 'opaque-import':
            raise MotdError('This is an opaque import. Install a replacement artifact or supply an explicit new recipe.')
        config = validate_config(tomllib.loads(r['metadata']['config_toml']))
        install_options = {'destination': r['metadata']['artifact_path']}
        if len(r['metadata']['hook_paths']) == 1: install_options['shell_file'] = r['metadata']['hook_paths'][0]
        config = _configure(config, ui)
    elif action == 'existing':
        kind = ui.select('What do you have?', [('A TOML recipe', 'config'), ('An existing generated/other output file', 'artifact')])
        path = absolute(input('Path: ').strip())
        if kind == 'config': config = load_config(path)
        else:
            imported = True; artifact = _source_text(path)
            try: config = extract_config(artifact)
            except MotdError:
                opaque = True; config = preset_config()
                config['target'] = ui.select('Output type', [('Executable shell output', 'shell'),
                    ('agetty issue text', 'issue'), ('SSH banner text', 'ssh-banner'), ('Generic text', 'text')])
                if config['target'] == 'shell': config['shell'] = ui.select('Output interpreter', [(x, x) for x in SHELLS])
                config['name'] = _ask('Installation name', 'imported')
            print('File SHA256:', hashlib.sha256(artifact.encode()).hexdigest())
            if config['target'] == 'shell':
                trusted = confirm('I have inspected this executable file and want to install its exact bytes')
                if not trusted: print('Cancelled.'); return 0
    else:
        name = ui.select('Start with a preset', [(x, x) for x in PRESET_NAMES], preview_factory=preset_config)
        config = _configure(preset_config(name), ui)
    config = validate_config(config)
    artifact = artifact if artifact is not None else generate_artifact(config)
    while True:
        choice = ui.select('Review and finish', [('Preview (synthetic; no configured calls)', 'preview'),
            ('Show install plan / dry run', 'plan'), ('Save TOML recipe', 'save'),
            ('Build portable output', 'build'), ('Install', 'install'),
            ('Change draft settings', 'settings'), ('Cancel', 'cancel')],
            config=None if opaque else config)
        if choice == 'cancel': print('Cancelled. Previously requested exports remain.'); return 0
        try:
            if choice == 'preview':
                if opaque and config['target'] == 'shell':
                    print('Opaque scripts have no synthetic preview. Inspect the source; trusted live execution is a separate CLI action.')
                    ui.pause()
                elif opaque:
                    print(artifact, end=''); ui.pause()
                else: ui.full_preview(config)
                continue
            if choice == 'settings':
                if opaque: raise MotdError('Opaque outputs have no reconstructable settings; keep or replace their exact bytes.')
                config = _configure(config, ui)
                artifact = generate_artifact(config); imported = False
                continue
            if choice == 'save':
                if opaque: raise MotdError('This output has no reconstructable recipe. Build/copy the exact output instead.')
                path = absolute(_ask('Recipe path', config['name'] + '.toml'))
                save_recipe(config, path, state_dir)
            elif choice == 'build':
                path = absolute(_ask('Output path', config['name'] + artifact_suffix(config)))
                export_files(config, artifact, path, state_dir=state_dir, opaque_artifact=opaque)
            else:
                if config['target'] != 'shell' and (scope == 'user' or config['target'] == 'text') and 'destination' not in install_options:
                    install_options['destination'] = absolute(_ask('Destination file (parent must exist)', str(Path.home() / (config['name'] + '.txt'))))
                explicit_startup = config['target'] == 'shell' and (
                    (scope == 'system' and config['shell'] == 'zsh') or
                    (config['frequency'] == 'interactive' and (scope == 'system' or config['shell'] == 'sh')))
                if explicit_startup and 'shell_file' not in install_options:
                    selected = input('Startup file path for this shell (existing parent required): ').strip()
                    if not selected: raise MotdError('Choose an explicit startup file; its location is not guessed')
                    install_options['shell_file'] = absolute(selected)
                plan = installation_plan(config, artifact, scope=scope, state_dir=state_dir,
                                         opaque_artifact=opaque, **install_options)
                if choice == 'plan': describe_plan(plan)
                elif apply_reviewed(plan): return 0
        except (MotdError, ValueError) as exc:
            print('Draft retained:', exc)
        ui.pause()


def parser():
    root = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root.add_argument('--version', action='version', version=VERSION)
    commands = root.add_subparsers(dest='command')
    for name in ('wizard', 'build', 'preview', 'plan', 'install', 'upgrade', 'reconfigure',
                 'inspect', 'audit', 'history', 'repair', 'rollback', 'recover', 'uninstall', 'config'):
        p = commands.add_parser(name)
        p.add_argument('--scope', choices=('user', 'system'), default='user')
        p.add_argument('--state-dir')
        p.add_argument('--json', action='store_true')
        p.add_argument('--yes', action='store_true')
        p.add_argument('--name')
        if name in ('wizard', 'reconfigure'): p.add_argument('--ui', choices=('auto', 'screen', 'line'), default='auto')
        if name in ('repair', 'rollback', 'recover'): p.add_argument('--transaction', required=name != 'repair')
        if name in ('build', 'preview', 'plan', 'install', 'upgrade', 'reconfigure', 'inspect', 'config'):
            source = p.add_mutually_exclusive_group()
            source.add_argument('--preset', choices=PRESET_NAMES)
            source.add_argument('--config')
            source.add_argument('--artifact')
            p.add_argument('--target', choices=TARGETS)
            p.add_argument('--shell', choices=SHELLS)
            p.add_argument('--audience', choices=('all', 'ssh', 'local'))
            p.add_argument('--trust-artifact', action='store_true')
            p.add_argument('--replace', action='store_true')
            p.add_argument('--destination')
            p.add_argument('--shell-file')
        if name in ('build', 'config'): p.add_argument('--output', required=True)
        if name == 'build': p.add_argument('--save-config')
        if name == 'preview': p.add_argument('--live', action='store_true')
    return root


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = parser().parse_args(argv or ['wizard'])
    state_dir = absolute(args.state_dir or default_state(args.scope))
    if args.command == 'wizard': return wizard(args)
    if args.command == 'history':
        records = tx_history(state_dir)
        if args.json: print(json.dumps(records, indent=2))
        else:
            for r in records: print(r['id'], r['status'], r['metadata'].get('operation'), r['metadata'].get('name', ''))
        return 0
    if args.command in ('inspect', 'audit'):
        if getattr(args, 'artifact', None):
            artifact = _source_text(args.artifact)
            print('SHA256:', hashlib.sha256(artifact.encode()).hexdigest())
            print(dump_config(extract_config(artifact)), end='')
        else:
            findings = tx_audit(state_dir)
            if args.json: print(json.dumps(findings, indent=2))
            elif not findings: print('No managed changes in', state_dir)
            else:
                for item in findings: print(item['state'], item['path'], '-', item['message'])
            return 1 if any(x['state'] != 'ok' for x in findings) else 0
        return 0
    if args.command in ('repair', 'rollback', 'recover', 'uninstall'):
        if args.command == 'uninstall' and not args.name: raise MotdError('uninstall requires --name')
        if args.command == 'repair' and not (args.name or args.transaction): raise MotdError('repair requires --name or --transaction')
        result = _manage(args.command, state_dir, getattr(args, 'transaction', None), args.name, args.yes)
        return 1 if result and result['status'] == 'needs_recovery' else 0
    if args.command == 'config':
        if not args.artifact: raise MotdError('config requires --artifact')
        artifact = _source_text(args.artifact); c = extract_config(artifact)
        plan = tx_plan([{'path': absolute(args.output), 'content': dump_config(c), 'mode': 0o600}], state_dir,
                       {'operation': 'recover-config', 'name': c['name'], 'config_toml': dump_config(c)})
        if Path(args.output).exists() and not args.replace: raise MotdError('Recipe output exists; choose another path or --replace')
        result = tx_apply(plan); print('Recovered:', absolute(args.output)); return 0
    if args.command in ('reconfigure', 'upgrade') and not any((args.config, args.preset, args.artifact)):
        if not args.name: raise MotdError('reconfigure/upgrade requires --name or an explicit recipe')
        prior = active_installs(state_dir).get(args.name)
        if not prior: raise MotdError('No matching installed message')
        if prior['metadata'].get('artifact_origin') == 'opaque-import':
            raise MotdError('Opaque imports need an explicit replacement --artifact or new --config; settings cannot be inferred')
        c = validate_config(tomllib.loads(prior['metadata']['config_toml']))
        if args.command == 'reconfigure' and not args.yes: c = _configure(c, WizardUI(args.ui))
        for key in ('target', 'shell', 'audience'):
            if getattr(args, key, None) is not None:
                if key == 'shell': select_shell(c, args.shell)
                else: c[key] = getattr(args, key)
        c = validate_config(c)
        artifact = generate_artifact(c)
        if args.destination and absolute(args.destination) != prior['metadata']['artifact_path']:
            raise MotdError('Uninstall before changing an installed artifact path')
        args.destination = prior['metadata']['artifact_path']
        if not args.shell_file and len(prior['metadata']['hook_paths']) == 1:
            args.shell_file = prior['metadata']['hook_paths'][0]
    else: c, artifact = resolve_input(args)
    if args.command == 'build':
        export_files(c, artifact, args.output, args.save_config, state_dir=state_dir, replace=args.replace,
                     opaque_artifact=getattr(args, 'opaque_artifact', False)); return 0
    if args.command == 'preview':
        return preview(c, artifact, live=args.live, imported=bool(args.artifact), trust=args.trust_artifact)
    plan = installation_plan(c, artifact, scope=args.scope, destination=args.destination,
                             shell_file=args.shell_file, state_dir=state_dir, replace=args.replace,
                             opaque_artifact=getattr(args, 'opaque_artifact', False))
    if args.command == 'plan': describe_plan(plan, json_output=args.json)
    else: apply_reviewed(plan, args.yes)
    return 0


def entrypoint():
    try:
        return main()
    except (MotdError, TxError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f'MOTD: {exc}', file=sys.stderr)
        if isinstance(exc, TxError) and exc.record:
            print('Transaction:', exc.record.get('id'), exc.record.get('status'), file=sys.stderr)
        return 2
    except WizardCancelled:
        print("Cancelled. Draft discarded; previously requested exports remain.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print('\nCancelled. Inspect history before retrying an interrupted apply.', file=sys.stderr)
        return 130




# BEGIN EMBEDDED BASH — regenerated by tools/embed_runtime.py
BASH_TEMPLATE = r'''#!/bin/bash
# MOTD Bash runtime 0.2.0 | derived from Workshop MOTD 1.2.0, 2026-11-16.
# Bash 4.3+ and GNU timeout; optional GNU df, procps ps, iproute2, systemd.
# Standalone output: generate settings with motd.py, then use --demo or --help.
# No daemon, installation side effects, network requests, recursive disk scans,
# privilege escalation, commands from data, or state-changing system actions.
# External helpers have deadlines; kernel I/O stalls cannot have a hard deadline.

if ((BASH_VERSINFO[0]<4 || (BASH_VERSINFO[0]==4 && BASH_VERSINFO[1]<3))); then
    printf '%s\n' 'MOTD status needs Bash 4.3 or newer.' >&2
    exit 0
fi

# Generated explicit hooks belong after the version guard: unsupported Bash
# must return to the login shell before any configured command can execute.
# @MOTD_HOOKS@

# =========================== 1. SETTINGS =====================================
# Legacy internal value retained for tested collectors/components. Public output
# always uses the adaptive row planner; there is no concise/verbose CLI switch.
MODE=concise
COMPACT_ROWS=25                  # Includes one row reserved for the shell prompt.
CONCISE_WORKER_SECONDS=0.20      # Whole worker deadline, not per-query timeout.
CONCISE_KILL_SECONDS=0.02        # Reserve parent/fallback time below a 400ms target.
COLLECTION_BUDGET_MS=140         # Stop starting collectors before worker deadline.
CONCISE_HELPER_MAX_MS=75


IO_TOP_N=3
IO_PROCESS_LIMIT=512            # Maximum PID directories examined per snapshot.
IO_SCAN_BUDGET_MS=35            # Cooperative budget per PID pass, checked per 8 PIDs.
IO_MIN_SAMPLE_MS=20             # Shorter natural intervals use cumulative totals.
IO_MAX_SAMPLE_MS=30000          # Counter comparison only within this invocation.
IO_DEVICE_LIMIT=64
IO_SHOW_DEVICES=3
IO_VERBOSE_PROCESS_LIMIT=8192
IO_VERBOSE_SCAN_BUDGET_MS=200

TITLE='SYSTEM STATUS'
MAX_WIDTH=132                   # Use available width up to this cap.
THEME=cyan                     # cyan | amber | mono
MOTD_FASTFETCH=0                # External before/after hooks are owned by motd.py.
FASTFETCH_TIMEOUT=1s
STORAGE_TIMEOUT=0.4s
IDENTITY_TIMEOUT=0.3s
JOURNAL_TIMEOUT=0.4s
RAM_WARN=85 RAM_CRITICAL=95
DISK_WARN=90 DISK_CRITICAL=95
INODE_WARN=90 INODE_CRITICAL=95
PSI_WARN=10                     # >=10% memory/I/O full stall, avg10; observation.
SHOW_SWAP=1 SHOW_COMPRESSION=1 SHOW_ATTENTION=1
SHOW_PRESSURE=1 SHOW_JOURNAL=0   # Journal access is an explicit optional collector.
JOURNAL_WINDOW=1h JOURNAL_LIMIT=20
# Host domain is local configuration, never a claim of AD membership or DNS health.
SITE_LABEL=''                   # Change freely for each site or machine role.
DOMAIN_OVERRIDE=''             # e.g. workshop.example; blank = local DNS config.
STORAGE_MOUNTS=()              # Empty = eligible local mounted filesystems.
MAX_IPS=4 MAX_DISK_DETAILS=4 MAX_ATTENTION=12
# Comments and commands are data; the MOTD never executes these suggestions.
MESSAGES=()                    # Example: ('INFO|Bench 3: storage test in progress.')
declare -A COLOR_CODE=(
    [border]=36 [heading]='1;37' [other]='1;34' [cache]=36
    [compressed]=35 [free]=90 [reserved]=33 [ok]=32 [warn]='1;33'
    [error]='1;31' [muted]=90 [text]=37
    [cpu]='1;33' [rss]='1;35' [io]='1;36' [label]='1;37' [value]=37
)
DISK_COLOR_CODES=('1;34' 36 35 32 33 37)

SERVICE_TIMEOUT=0.4s
SERVICES_MODE=common             # common | all; inventory still uses the work budget.
SERVICE_EXTRA_LIMIT=6            # Extra active units in the installed-unit inventory.
SERVICE_ALERT_LIMIT=8            # Failure details; the total is always reported.
# Explicitly required unit names only. Inactive/disabled optional units are normal.
# For socket activation, require the .socket rather than its idle .service.
REQUIRED_UNITS=()               # Example: (ssh.socket cron.service)
SERVICE_EXCLUDE_PATTERNS=('ollama*' 'llama*' 'vllm*' 'lmstudio*')
# Optional classification overrides: [your-backup.service]=System
declare -A SERVICE_GROUP_OVERRIDE=()
SERVICE_GROUPS=(Access Files Web Data Mail Network Identity Security Virtual System Time Local)

TOP_N=3
MAX_SESSIONS=6
MAX_CONNECTIONS=4
ACTIVITY_TIMEOUT=0.4s
SESSION_QUERY_LIMIT=128
# These are port hints, not protocol verification. Change for nonstandard ports.
declare -A CONNECTION_PORT_LABEL=(
    [22]=SSH [3389]=RDP [5900]=VNC [5901]=VNC [5902]=VNC
    [21]=FTP [445]=SMB [2049]=NFS [80]=HTTP [443]=HTTPS
)
CONNECTION_ADMIN_PORTS=(22 3389 5900 5901 5902)
# PAM service names reported by logind; a session can outlive its connection.
declare -A SESSION_SERVICE_KIND=([sshd]=SSH [ssh]=SSH [xrdp-sesman]=RDP)


# One adaptive display order. Hiding is presentation-only; alerts still collect.
SECTIONS=(system resources services processes sessions connections attention hints)
# ID = title | renderer | base rows | minimum rows | maximum rows.
# A row budget includes its named divider. Outer borders and prompt are separate.
declare -A SECTION_SPEC=(
    [system]='SYSTEM|ui_system|3|2|6'
    [resources]='RESOURCES|ui_resources|4|3|10'
    [services]='SERVICES|ui_services|3|2|10'
    [processes]='TOP PROCESSES|ui_tasks|5|3|10'
    [sessions]='SESSIONS|ui_sessions|3|2|10'
    [connections]='CONNECTIONS|ui_connections|1|1|8'
    [attention]='ATTENTION|ui_attention|2|2|14'
    [hints]='HINTS|ui_hints|1|1|10'
    [io]='DISK I/O|ui_io|4|2|12'
)
# Optional overrides: SECTION_VISIBLE[services]=0; SECTION_TITLE[sessions]='USERS'
# Explicit row overrides are hard caps, including the section's divider.
# SECTION_ROWS[processes]=6; SECTION_ROWS[services]=4
# ITEM_VISIBLE[resources.swap]=0; ITEM_VISIBLE[services.FTP]=0
# ITEM_VISIBLE[sessions.peer]=0; ITEM_VISIBLE[hints.devices]=0
# Legacy mode-prefixed row keys remain accepted for imported configurations.
declare -A SECTION_VISIBLE=() SECTION_TITLE=() SECTION_ROWS=() ITEM_VISIBLE=()
COMPACT_TRIM_ORDER=(resources services sessions system processes attention connections hints)
COMPACT_EXPAND_ORDER=(processes services sessions attention resources connections system hints)

THEME_NAMES=(cyan amber green mono)
declare -A THEME_COLOR_CODE=(
    [amber.border]=33 [amber.heading]='1;33' [amber.label]='1;33'
    [green.border]=32 [green.heading]='1;32' [green.label]='1;32'
)
# Common role aliases are data; append a role and its units to extend the overview.
SERVICE_ROLE_ORDER=(SSH RDP SMB FTP TFTP GUI OOM WEB DB NET DNS AUTH CONTAINERS CRON TIME NFS PRINT VPN VM LOG)
declare -A SERVICE_ROLE_UNITS=(
    [SSH]='ssh.service sshd.service ssh.socket sshd.socket'
    [RDP]='xrdp.service gnome-remote-desktop.service'
    [SMB]='smbd.service smb.service samba.service samba-ad-dc.service'
    [FTP]='vsftpd.service proftpd.service pure-ftpd.service vsftpd.socket'
    [TFTP]='tftpd-hpa.service tftp.service tftp.socket atftpd.service'
    [GUI]='display-manager.service lightdm.service gdm.service gdm3.service sddm.service xdm.service'
    [OOM]='earlyoom.service systemd-oomd.service'
    [WEB]='nginx.service apache2.service httpd.service caddy.service'
    [DB]='postgresql.service mariadb.service mysql.service mongod.service redis-server.service redis.service'
    [NET]='NetworkManager.service systemd-networkd.service networking.service'
    [DNS]='named.service bind9.service unbound.service dnsmasq.service systemd-resolved.service'
    [AUTH]='sssd.service winbind.service nslcd.service'
    [CONTAINERS]='docker.service containerd.service podman.service'
    [CRON]='cron.service crond.service'
    [TIME]='chrony.service chronyd.service systemd-timesyncd.service ntp.service ntpd.service'
    [NFS]='nfs-server.service nfs-kernel-server.service'
    [PRINT]='cups.service cups.socket'
    [VPN]='openvpn.service wg-quick@wg0.service tailscaled.service'
    [VM]='libvirtd.service virtqemud.service'
    [LOG]='rsyslog.service syslog-ng.service systemd-journald.service'
)
declare -A SERVICE_ROLE_LABEL=([CONTAINERS]='CTR')
# id | label | displayed command | longer explanation. Commands are NEVER executed.
HINTS=(
    'more|More|--rows 50|show more rows within the same layout'
    'tasks|Tasks|top|live CPU and memory'
    'io|I/O|iotop -o|live process I/O; if installed and permitted'
    'devices|Devices|iostat -xz 1|live device I/O; if installed'
    'services|Services|systemctl --failed|failed units'
    'logs|Logs|journalctl -b -p warning -n 30|visible journal'
    'sessions|Sessions|loginctl list-sessions|registered logins'
    'sockets|Sockets|ss -nt|established TCP sockets'
)

# Generated settings are literal assignments; no additional config file is read.
# @MOTD_CONFIG@

# MODE is a private compatibility detail, never an alternative public renderer.
MODE=concise

# This bootstrap runs before parsing the large function body on a normal adaptive
# invocation. A private regular file avoids pipe EOF waits on a stuck descendant.
# No persistent cache, daemon, or privilege escalation. Settings above stay shared.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    ws_guard=1; ws_guard_worker=0
    for ws_arg in "$@"; do
        case $ws_arg in
            --demo|--demo-alerts|--help|-h|--version|--list-sections|--list-items) ws_guard=0 ;;
            --_worker) ws_guard=0; ws_guard_worker=1 ;;
        esac
    done
    if ((ws_guard)); then
        export PATH=/usr/sbin:/usr/bin:/sbin:/bin
        ws_tmp=''; ws_dir=/tmp; ws_tty=''; ws_rc=0; ws_result=''
        [[ ! -d /dev/shm || ! -w /dev/shm || ! -x /dev/shm ]] || ws_dir=/dev/shm
        if [[ -t 1 ]]; then ws_tty=$( { stty size </dev/tty; } 2>/dev/null); fi
        if command -v timeout >/dev/null 2>&1 && command -v mktemp >/dev/null 2>&1; then
            ws_tmp=$(mktemp "$ws_dir/motd-status.XXXXXXXX" 2>/dev/null) || ws_tmp=''
        fi
        if [[ -n $ws_tmp ]]; then
            # A killed descendant may retain this unlinked regular file, never
            # the login's stdout pipe. Do not change this command to $(timeout...).
            trap 'rm -f -- "$ws_tmp"' EXIT
            {
                timeout --kill-after="$CONCISE_KILL_SECONDS" "$CONCISE_WORKER_SECONDS" \
                    /bin/bash "${BASH_SOURCE[0]}" --_worker --_tty-size "$ws_tty" "$@" \
                    >"$ws_tmp" 2>/dev/null || ws_rc=$?
            } 2>/dev/null
            if ((ws_rc==0)); then
                ws_result=$(<"$ws_tmp")
                if [[ $ws_result == *$'\n__WORKSHOP_COMPLETE_V2__' ]]; then
                    printf '%s\n' "${ws_result%$'\n__WORKSHOP_COMPLETE_V2__'}"
                    exit 0
                fi
            elif ((ws_rc==2)); then
                printf '%s\n' 'Invalid MOTD options or configuration; use --help.' >&2
                exit 2
            fi
            rm -f -- "$ws_tmp"; trap - EXIT; ws_tmp=''
        fi
        # Keep login usable if the collector cannot finish: a fresh small local
        # snapshot clearly marks omitted sections instead of publishing partial bytes.
        WORKSHOP_BUDGET_FALLBACK=1
    fi
fi


# ===================== 2. CORE COLLECTION / CONTROL ==========================
ROWS_OVERRIDE='' TTY_SIZE_OVERRIDE='' WORKER=0
BUDGET_START_MS=0 BUDGET_ACTIVE=0 LOCAL_ONLY=0
budget_clock() {
    # /proc/uptime is monotonic and available on Bash4.3; centisecond resolution.
    local now rest whole fraction
    if read -r now rest <"$PROC_ROOT/uptime" 2>/dev/null && [[ $now =~ ^([0-9]+)\.([0-9]+)$ ]]; then
        whole=${BASH_REMATCH[1]}; fraction=${BASH_REMATCH[2]}00; fraction=${fraction:0:3}
        REPLY=$((10#$whole*1000+10#$fraction)); return 0
    fi
    REPLY=0; return 1
}
budget_start() {
    BUDGET_ACTIVE=0; MODEL[budget_limited]=0
    [[ $MODE == concise && $DEMO == 0 ]] || return 0
    if budget_clock; then BUDGET_START_MS=$REPLY; BUDGET_ACTIVE=1; fi
}
budget_remaining() {
    REPLY=$COLLECTION_BUDGET_MS
    ((BUDGET_ACTIVE)) || return 0
    if budget_clock; then REPLY=$((COLLECTION_BUDGET_MS-(REPLY-BUDGET_START_MS))); fi
    ((REPLY>0))
}
budget_allow() {
    if budget_remaining; then return 0; fi
    MODEL[budget_limited]=1; return 1
}


initialize_optional_model() {
    MODEL[services_state]=budget; MODEL[svc_runtime_state]=budget; MODEL[svc_files_state]=skipped
    MODEL[services_scope]=runtime; svc_finalize
    MODEL[process_state]=budget; MODEL[process_count]=0; MODEL[process_running]=0
    MODEL[process_blocked]=0; MODEL[process_zombies]=0
    MODEL[session_state]=budget; MODEL[session_source]=none
    MODEL[session_records]=0; MODEL[session_parsed]=0; MODEL[session_count]=0; MODEL[session_users]=0; MODEL[session_limited]=0
    MODEL[connection_state]=budget; MODEL[tcp_established]=0; MODEL[tcp_admin]=0
    MODEL[journal_state]=skipped; MODEL[journal_count]=0; MODEL[journal_capped]=0
    MODEL[storage_state]=budget; MODEL[storage_skipped]=0; MODEL[storage_skipped_shared]=0
    MODEL[io_state]=budget; MODEL[io_mode]=unavailable
    ACT_PROC=(); ACT_CPU_IDS=(); ACT_RAM_IDS=(); ACT_SESSION=(); ACT_SESSION_IDS=(); ACT_CONN=(); ACT_CONN_IDS=()
}


# Plain numbers are KiB unless a key says otherwise; unknown is never zero.
declare -A MODEL=() DISK=() COLOR=() VIEW=()
DISK_IDS=() ATTENTION=() HEALTH_NOTES=() HOST_IPS=()
FASTFETCH_TEXT='' OUTPUT='' REPLY=''
DEMO=0 PLAIN=0 ASCII=0 WIDTH_OVERRIDE='' FETCH_OVERRIDE='' THEME_OVERRIDE=''
PROC_ROOT=/proc SYS_ROOT=/sys ETC_ROOT=/etc RUN_ROOT=/run
VERSION=0.2.0

usage() {
    printf '%s\n' \
      'MOTD adaptive runtime 0.1.0 - standalone Linux status display.' \
      'Usage: motd.bash [--rows 20..60]' \
      '       [--width 24..240] [--theme cyan|amber|green|mono] [--plain] [--ascii]' \
      '       [--sections system,resources,services,processes,sessions,connections,attention,hints]' \
      '       [--hide SECTION,...] [--show SECTION,...]' \
      '       [--hide-item SECTION.ITEM,...] [--show-item SECTION.ITEM,...]' \
      '       [--list-sections] [--list-items] [--demo|--demo-alerts]' \
      '       [--services common|all] [--top 1..10] [--sessions 1..30]' \
      '       [--connections 1..30] [--journal|--no-journal]' \
      '' \
      'One adaptive layout keeps section frames and aligned rankings.' \
      'The default budget is 25 rows including a prompt row; --rows 50 adds detail.' \
      '--services all requests installed-unit inventory within the collection budget.' \
      '--journal explicitly requests the recent visible journal summary.' \
      'Section order, item visibility, titles, themes and hints share one renderer.' \
      'Hiding a panel does not disable its underlying warning checks.' \
      'I/O rates use two reads during other collection; no sampling sleep.' \
      'Collection uses a bounded worker and a clearly marked reduced fallback.' \
      'Optional hooks configured by motd.py run outside this display budget.' \
      'Elapsed time is not guaranteed under scheduler starvation or kernel stalls.'
}
parse_options() {
    local n candidate found
    while (($#)); do
        case $1 in
            --_worker) WORKER=1; shift ;;
            --_tty-size)
                (($#>=2)) || return 2
                [[ -z $2 || $2 =~ ^[0-9]{1,3}[[:space:]][0-9]{1,3}$ ]] || return 2
                TTY_SIZE_OVERRIDE=$2; shift 2 ;;
            --demo) DEMO=1; shift ;;
            --demo-alerts) DEMO=2; shift ;;
            --plain) PLAIN=1; shift ;;
            --ascii) ASCII=1; shift ;;
            --no-fastfetch) FETCH_OVERRIDE=0; shift ;;
            --journal) SHOW_JOURNAL=1; shift ;;
            --no-journal) SHOW_JOURNAL=0; shift ;;
            --services)
                case ${2-} in common|all) SERVICES_MODE=$2 ;; *) usage >&2; return 2 ;; esac
                shift 2 ;;
            --width|--rows|--top|--sessions|--connections)
                [[ ${2-} =~ ^[0-9]{1,3}$ ]] || { usage >&2; return 2; }
                n=$((10#$2))
                case $1 in
                    --width) ((n>=24 && n<=240)) || return 2; WIDTH_OVERRIDE=$n ;;
                    --rows) ((n>=20 && n<=60)) || return 2; ROWS_OVERRIDE=$n ;;
                    --top) ((n>=1 && n<=10)) || return 2; TOP_N=$n; IO_TOP_N=$n ;;
                    --sessions) ((n>=1 && n<=30)) || return 2; MAX_SESSIONS=$n ;;
                    --connections) ((n>=1 && n<=30)) || return 2; MAX_CONNECTIONS=$n ;;
                esac; shift 2 ;;
            --theme)
                found=0
                for candidate in "${THEME_NAMES[@]}"; do [[ ${2-} != "$candidate" ]] || found=1; done
                ((found)) || { usage >&2; return 2; }
                THEME_OVERRIDE=$2; shift 2 ;;
            --sections|--hide|--show)
                (($#>=2)) || return 2
                ui_set_sections "$1" "$2" || return 2; shift 2 ;;
            --hide-item|--show-item)
                (($#>=2)) || return 2
                ui_set_items "$1" "$2" || return 2; shift 2 ;;
            --list-sections)
                ui_registry_init || return 2; ui_section_list; return 3 ;;
            --list-items)
                ui_registry_init || return 2; ui_item_list; return 3 ;;
            --help|-h) usage; return 3 ;;
            --version) printf '%s\n' "$VERSION"; return 3 ;;
            *) usage >&2; return 2 ;;
        esac
    done
    [[ -z $ROWS_OVERRIDE ]] || COMPACT_ROWS=$ROWS_OVERRIDE
}
safe_text() {
    # External names may contain terminal escapes. Render printable ASCII only;
    # never modify raw paths used as command arguments. Fixed cap bounds rendering.
    local LC_ALL=C value=${1:0:1024}
    REPLY=${value//[! -~]/?}
}
collect_display_context() {
    local cols=$WIDTH_OVERRIDE rows='' size=$TTY_SIZE_OVERRIDE language=${LC_ALL:-${LC_CTYPE:-${LANG:-C.UTF-8}}}
    MODEL[color]=1; MODEL[unicode]=0
    ((PLAIN)) || [[ ! -v NO_COLOR ]] || PLAIN=1
    [[ ${TERM-} != dumb ]] || PLAIN=1
    [[ -z $THEME_OVERRIDE ]] || THEME=$THEME_OVERRIDE
    (( ! PLAIN )) && [[ $THEME != mono ]] || MODEL[color]=0
    # Reuse an active UTF-8 locale; do not spawn two locale probes per login.
    if ((!ASCII)) && [[ $language == *UTF-8* || $language == *utf8* || $language == *utf-8* ]]; then
        export LC_ALL=$language 2>/dev/null
        local unicode_probe='═'
        if ((${#unicode_probe}==1)); then MODEL[unicode]=1; else export LC_ALL=C; fi
    else export LC_ALL=C; fi
    if [[ -z $size && -t 1 ]]; then size=$( { stty size </dev/tty; } 2>/dev/null); fi
    if [[ $size =~ ^([0-9]{1,3})[[:space:]]+([0-9]{1,3})$ ]]; then
        rows=$((10#${BASH_REMATCH[1]})); [[ -n $cols ]] || cols=${BASH_REMATCH[2]}
    fi
    [[ $cols =~ ^[0-9]{1,3}$ ]] || cols=80
    cols=$((10#$cols)); ((cols>=24)) || cols=24
    if [[ -z $ROWS_OVERRIDE && $rows =~ ^[0-9]+$ ]] && ((rows>=20 && rows<COMPACT_ROWS)); then COMPACT_ROWS=$rows; fi
    MODEL[terminal_rows]=${rows:-$COMPACT_ROWS}
    MODEL[terminal_columns]=$cols; MODEL[columns]=$((cols<MAX_WIDTH ? cols : MAX_WIDTH))
    MODEL[fastfetch_enabled]=${FETCH_OVERRIDE:-$MOTD_FASTFETCH}
}
collect_fastfetch() {
    FASTFETCH_TEXT=''
    ((!DEMO && MODEL[fastfetch_enabled] && MODEL[terminal_columns]>=76)) || return 0
    command -v fastfetch >/dev/null 2>&1 || return 0
    local pipe=true
    (( ! MODEL[color] )) || pipe=false
    FASTFETCH_TEXT=$(run_bounded "$FASTFETCH_TIMEOUT" fastfetch --pipe "$pipe" 2>/dev/null) || FASTFETCH_TEXT=''
}
read_config_value() {
    # os-release values are data: no eval, source, or shell expansion.
    REPLY=$1
    if [[ $REPLY == \"*\" || $REPLY == \'*\' ]]; then REPLY=${REPLY:1:${#REPLY}-2}; fi
    safe_text "$REPLY"
}
collect_identity() {
    local key value line iface family address rest output rc=0 search='' hostdomain=''
    MODEL[host]=Unknown; MODEL[os]=Linux; MODEL[kernel]=Unknown
    MODEL[domain]='not configured locally'; MODEL[domain_source]='local config'
    HOST_IPS=(); MODEL[ip_state]=unavailable
    if [[ -r $PROC_ROOT/sys/kernel/hostname ]]; then read -r value <"$PROC_ROOT/sys/kernel/hostname"; safe_text "$value"; MODEL[host]=$REPLY; fi
    if [[ -r $PROC_ROOT/sys/kernel/osrelease ]]; then read -r value <"$PROC_ROOT/sys/kernel/osrelease"; safe_text "$value"; MODEL[kernel]=$REPLY; fi
    if [[ -r $ETC_ROOT/os-release ]]; then
        while IFS='=' read -r key value; do
            [[ $key == PRETTY_NAME ]] || continue
            read_config_value "$value"; MODEL[os]=$REPLY; break
        done <"$ETC_ROOT/os-release"
    fi
    if [[ ${MODEL[host]} == *.* ]]; then hostdomain=${MODEL[host]#*.}; fi
    if [[ -r $ETC_ROOT/resolv.conf ]]; then
        while read -r key value rest; do
            case $key in domain|search) [[ -z $value ]] || search=$value ;; esac
        done <"$ETC_ROOT/resolv.conf"
    fi
    if [[ -n $DOMAIN_OVERRIDE ]]; then MODEL[domain]=$DOMAIN_OVERRIDE; MODEL[domain_source]=configured
    elif [[ -n $hostdomain ]]; then MODEL[domain]=$hostdomain; MODEL[domain_source]='hostname suffix'
    elif [[ -n $search && $search != '~.' ]]; then MODEL[domain]=$search; MODEL[domain_source]='DNS search'
    fi
    safe_text "${MODEL[domain]}"; MODEL[domain]=$REPLY
    if (( ! LOCAL_ONLY )) && command -v ip >/dev/null 2>&1; then
        output=$(run_bounded "$IDENTITY_TIMEOUT" ip -o address show scope global 2>/dev/null) || rc=$?
        if ((rc==0)); then
            MODEL[ip_state]=ok
            while read -r key iface family address rest; do
                [[ $family == inet || $family == inet6 ]] || continue
                [[ -n $address ]] || continue
                safe_text "$iface $address"; HOST_IPS+=("$REPLY")
            done <<<"$output"
        fi
    fi
    printf -v 'MODEL[sampled]' '%(%Y-%m-%d %H:%M:%S %Z)T' -1
}
collect_health() {
    local key value rest line scope avg10 attr total cpu=0 up='' dev mask
    HEALTH_NOTES=(); MODEL[cpus]='?'; MODEL[uptime]='?'
    MODEL[load1]='?'; MODEL[load5]='?'; MODEL[load15]='?'
    if [[ -r $PROC_ROOT/loadavg ]]; then
        read -r 'MODEL[load1]' 'MODEL[load5]' 'MODEL[load15]' rest <"$PROC_ROOT/loadavg"
        for key in load1 load5 load15; do
            [[ ${MODEL[$key]} =~ ^[0-9]+([.][0-9]+)?$ ]] || MODEL[$key]='?'
        done
    fi
    # The online range list is the same host-online CPU scope as /proc/stat.
    # Count ranges arithmetically instead of scanning one line per logical CPU.
    local online='' range first last previous=-1 online_valid=1
    local -a cpu_ranges=()
    if { read -r online <"$SYS_ROOT/devices/system/cpu/online"; } 2>/dev/null && [[ -n $online ]]; then
        IFS=, read -r -a cpu_ranges <<<"$online"
        [[ $online != ,* && $online != *, && $online != *,,* ]] || online_valid=0
        for range in "${cpu_ranges[@]}"; do
            first=${range%%-*}; last=${range#*-}
            collector_uint "$first" || { online_valid=0; break; }; first=$REPLY
            collector_uint "$last" || { online_valid=0; break; }; last=$REPLY
            ((first<=last && first>previous && last<=2147483647)) || { online_valid=0; break; }
            cpu=$((cpu+last-first+1)); previous=$last
        done
        ((online_valid && cpu>0)) && MODEL[cpus]=$cpu
    fi
    if [[ ${MODEL[cpus]} == '?' && -r $PROC_ROOT/stat ]]; then
        cpu=0
        while read -r key rest; do
            case $key in
                cpu) ;;
                cpu[0-9]*) collector_uint "${key#cpu}" && ((cpu+=1)) ;;
                *) ((cpu==0)) || break ;;
            esac
        done <"$PROC_ROOT/stat"
        ((cpu==0)) || MODEL[cpus]=$cpu
    fi
    if [[ -r $PROC_ROOT/uptime ]]; then
        read -r up rest <"$PROC_ROOT/uptime"; up=${up%%.*}
        if collector_uint "$up"; then
            printf -v 'MODEL[uptime]' '%dd %02dh %02dm' "$((up/86400))" "$((up/3600%24))" "$((up/60%60))"
        fi
    fi
    MODEL[oom_kills]=''
    if [[ -r $PROC_ROOT/vmstat ]]; then
        while read -r key value rest; do
            [[ $key == oom_kill ]] || continue
            if collector_uint "$value"; then MODEL[oom_kills]=$REPLY; fi; break
        done <"$PROC_ROOT/vmstat"
    fi
    for key in cpu memory io; do
        MODEL[psi_$key]=''
        [[ -r $PROC_ROOT/pressure/$key ]] || continue
        while read -r scope avg10 rest; do
            [[ $scope == full && $key != cpu || $scope == some && $key == cpu ]] || continue
            value=${avg10#avg10=}
            [[ $value =~ ^[0-9]{1,3}\.[0-9]{2}$ ]] || continue
            MODEL[psi_$key]=$value; break
        done <"$PROC_ROOT/pressure/$key"
    done
    MODEL[reboot_marker]=0
    [[ ! -e $RUN_ROOT/reboot-required && ! -e $RUN_ROOT/reboot-needed ]] || MODEL[reboot_marker]=1
    MODEL[md_degraded]=0
    if [[ -r $PROC_ROOT/mdstat ]]; then
        dev=''
        while IFS= read -r line; do
            if [[ $line =~ ^(md[^[:space:]]+)[[:space:]]*: ]]; then dev=${BASH_REMATCH[1]}; fi
            if [[ $line =~ \[([U_]+)\] ]]; then
                mask=${BASH_REMATCH[1]}
                if [[ $mask == *_* ]]; then
                    MODEL[md_degraded]=$((MODEL[md_degraded]+1))
                    safe_text "$dev"; HEALTH_NOTES+=("ERROR|MD RAID $REPLY reports missing members ($mask). Check /proc/mdstat.")
                fi
            fi
        done <"$PROC_ROOT/mdstat"
    fi
    MODEL[root_readonly]=0
    if [[ -r $PROC_ROOT/self/mountinfo ]]; then
        while read -r _ _ _ _ value rest; do
            [[ $value == / ]] || continue
            read -r value rest <<<"$rest"
            case ,$value, in *,ro,*) MODEL[root_readonly]=1 ;; *) MODEL[root_readonly]=0 ;; esac
        done <"$PROC_ROOT/self/mountinfo"
    fi
}
collect_journal() {
    MODEL[journal_state]=off; MODEL[journal_count]=0; MODEL[journal_capped]=0
    ((SHOW_JOURNAL)) || return 0
    MODEL[journal_state]=unavailable
    command -v journalctl >/dev/null 2>&1 || return 0
    local output rc=0 key value count=0
    # Metadata only: no log message bodies in a potentially shared PAM MOTD cache.
    output=$(run_bounded "$JOURNAL_TIMEOUT" journalctl --system --boot \
        --since="-$JOURNAL_WINDOW" --priority=err --lines="$((JOURNAL_LIMIT+1))" \
        --output=export --output-fields=PRIORITY --no-pager --quiet 2>/dev/null) || rc=$?
    ((rc==0)) || { [[ $rc != 124 && $rc != 137 ]] || MODEL[journal_state]=timeout; return 0; }
    MODEL[journal_state]=ok
    while IFS='=' read -r key value; do [[ $key != __CURSOR ]] || ((count+=1)); done <<<"$output"
    MODEL[journal_count]=$count
    ((count<=JOURNAL_LIMIT)) || MODEL[journal_capped]=1
}
prepare_view() {
    local key id code theme_key i=0
    local -a disk_palette=("${DISK_COLOR_CODES[@]}")
    # An empty customization still gets a usable local colour; keep its config.
    ((${#disk_palette[@]})) || disk_palette=(37)
    # A declaration without assignment preserves a configured associative map.
    # Resolve into COLOR; never mutate the base palette while selecting a theme.
    declare -gA THEME_COLOR_CODE
    RST=''; COLOR=()
    (( ! MODEL[color] )) || RST=$'\033[0m'
    for key in "${!COLOR_CODE[@]}"; do
        code=${COLOR_CODE[$key]}; theme_key="$THEME.$key"
        [[ $THEME != amber || $key != border ]] || code=33
        code=${THEME_COLOR_CODE[$theme_key]-$code}
        COLOR[$key]=''
        if ((MODEL[color])) && [[ -n $code ]]; then COLOR[$key]=$'\033['${code}m; fi
    done
    COLS=${MODEL[columns]}; INNER=$((COLS-2)); TEXT_WIDTH=$((INNER-2))
    BORDER=${COLOR[border]}
    H='═'; V='║'; TL='╔'; TR='╗'; BL='╚'; BR='╝'; LEFT='╠'; RIGHT='╣'
    GLYPH_USED='█'; GLYPH_FREE='░'
    if ((!MODEL[unicode])); then H='='; V='|'; TL='+'; TR='+'; BL='+'; BR='+'; LEFT='+'; RIGHT='+'; GLYPH_USED='#'; GLYPH_FREE='.'; fi
    repeat_char "$H" "$INNER"; RULE_FULL=$REPLY
    for key in mem_total mem_used mem_available mem_free mem_cache mem_compressed mem_other \
               swap_total swap_used swap_free swap_zram_used swap_other_used \
               zram_pool_kib zram_original_kib zswap_pool_kib zswap_original_kib; do
        format_number "${MODEL[$key]-}"; VIEW[$key]=$REPLY
    done
    VIEW[mem_percent]='?'
    if ((MODEL[mem_valid])); then printf -v 'VIEW[mem_percent]' '%d.%d' "$((MODEL[mem_tenths]/10))" "$((MODEL[mem_tenths]%10))"; fi
    for id in "${DISK_IDS[@]}"; do
        code=${disk_palette[i%${#disk_palette[@]}]}; VIEW[$id.color]=''
        (( ! MODEL[color] )) || VIEW[$id.color]=$'\033['${code}m
        human_kib "${DISK[$id.used_kib]}"; VIEW[$id.used]=$REPLY
        safe_text "${DISK[$id.target]}"; VIEW[$id.target]=$REPLY
        ((i+=1))
    done
    for key in storage_total storage_used storage_avail storage_reserved; do human_kib "${MODEL[$key]}"; VIEW[$key]=$REPLY; done
    prepare_attention
}
prepare_attention() {
    local key id percent denom entry level message count info='' shown=0
    ATTENTION=()
    service_attention
    for entry in "${HEALTH_NOTES[@]}"; do ATTENTION+=("$entry"); done
    if ((MODEL[mem_valid])); then
        if ((MODEL[mem_tenths]>=RAM_CRITICAL*10)); then ATTENTION+=("ERROR|Available RAM ${VIEW[mem_available]}; investigate top RSS processes.")
        elif ((MODEL[mem_tenths]>=RAM_WARN*10)); then ATTENTION+=("WARN|Available RAM ${VIEW[mem_available]}; check memory pressure and tasks."); fi
    else ATTENTION+=('INFO|Memory usage unavailable.'); fi
    for id in "${DISK_IDS[@]}"; do
        denom=$((${DISK[$id.used_kib]}+${DISK[$id.avail_kib]})); ((denom>0)) || continue
        percent=$((${DISK[$id.used_kib]}*100/denom))
        if ((percent>=DISK_CRITICAL)); then ATTENTION+=("ERROR|${VIEW[$id.target]}: $percent% usable space used. Inspect with df -h.")
        elif ((percent>=DISK_WARN)); then ATTENTION+=("WARN|${VIEW[$id.target]}: $percent% usable space used. Check free space."); fi
        if [[ ${DISK[$id.inodes_total]-} =~ ^[0-9]+$ && ${DISK[$id.inodes_free]-} =~ ^[0-9]+$ ]] && ((${DISK[$id.inodes_total]}>0)); then
            percent=$((100-100*${DISK[$id.inodes_free]}/${DISK[$id.inodes_total]}))
            if ((percent>=INODE_CRITICAL)); then ATTENTION+=("ERROR|${VIEW[$id.target]}: $percent% inodes used. Inspect with df -i.")
            elif ((percent>=INODE_WARN)); then ATTENTION+=("WARN|${VIEW[$id.target]}: $percent% inodes used. Inspect with df -i."); fi
        fi
    done
    for key in memory io; do
        if [[ ${MODEL[psi_$key]-} =~ ^([0-9]+)\. ]]; then
            percent=$((10#${BASH_REMATCH[1]}))
            ((percent<PSI_WARN)) || ATTENTION+=("WARN|$key full-stall pressure ${MODEL[psi_$key]}% (10s average); inspect workload.")
        fi
    done
    ((${MODEL[reboot_marker]:-0}==0)) || ATTENTION+=('WARN|OS reboot marker present. Review and schedule a restart.')
    ((${MODEL[oom_kills]:-0}==0)) || ATTENTION+=("WARN|Kernel recorded ${MODEL[oom_kills]} OOM-kill event(s) since boot; review kernel logs.")
    ((${MODEL[root_readonly]:-0}==0)) || ATTENTION+=('INFO|Root is mounted read-only; verify this is intended.')
    case ${MODEL[storage_state]-unavailable} in
        ok) ;;
        partial) ATTENTION+=('INFO|Storage aggregate incomplete; available filesystem details shown.') ;;
        *) ATTENTION+=("INFO|Storage statistics ${MODEL[storage_state]:-unavailable}.") ;;
    esac
    activity_attention
    io_attention
    if ((${MODEL[budget_limited]:-0})); then
        ATTENTION+=('INFO|Collection budget reached; omitted measurements remain unknown.')
    fi
    if ((${MODEL[deadline_fallback]:-0})); then
        ATTENTION+=('WARN|Full display unavailable (deadline or helper failure); fresh local counters only.')
    fi
    if ((SHOW_JOURNAL)); then
        if [[ ${MODEL[journal_state]} == ok ]]; then
            count=${MODEL[journal_count]}
            if ((count>0)); then
                ((MODEL[journal_capped]==0)) || count="$JOURNAL_LIMIT+"
                ATTENTION+=("WARN|$count visible system journal error(s) in the last $JOURNAL_WINDOW; review journalctl -b -p err.")
            fi
        else ATTENTION+=("INFO|System journal summary ${MODEL[journal_state]}; log access may be restricted."); fi
    fi
    for entry in "${MESSAGES[@]}"; do
        IFS='|' read -r level message <<<"$entry"; safe_text "$message"
        case $level in ERROR|WARN|INFO) ;; *) level=INFO ;; esac
        ATTENTION+=("$level|$REPLY")
    done
    # Errors first, then warnings, then information. This avoids hiding urgent
    # findings behind missing optional tools when MAX_ATTENTION limits the view.
    local -a ordered=()
    for level in ERROR WARN INFO; do
        for entry in "${ATTENTION[@]}"; do [[ $entry == "$level|"* ]] && ordered+=("$entry"); done
    done
    ATTENTION=("${ordered[@]}")
}


collect_all() {
    collect_display_context
    budget_start
    if ((DEMO)); then
        demo_model; demo_services; demo_activity; demo_io
        # Keep the example workload and shared-account sessions internally consistent.
        ACT_LOCAL_USER[1000]=workshop; ACT_PROC[2418.name]=badblocks
        ACT_SESSION_IDS=(0 1 2 3)
        for demo_i in 0 1 2 3; do
            ACT_SESSION[$demo_i.Name]=workshop; ACT_SESSION[$demo_i.User]=1000
            ACT_SESSION[$demo_i.Id]=c$((11+demo_i)); ACT_SESSION[$demo_i.State]=online
            ACT_SESSION[$demo_i.Kind]=SSH
        done
        ACT_SESSION[0.TTY]=pts/0; ACT_SESSION[0.RemoteHost]=192.0.2.24
        ACT_SESSION[1.TTY]=pts/1; ACT_SESSION[1.Display]=''; ACT_SESSION[1.RemoteHost]=192.0.2.41
        ACT_SESSION[2.TTY]=''; ACT_SESSION[2.Display]=:10; ACT_SESSION[2.Kind]=RDP; ACT_SESSION[2.RemoteHost]=192.0.2.58
        ACT_SESSION[3.TTY]=tty2; ACT_SESSION[3.Kind]=TTY; ACT_SESSION[3.RemoteHost]=''
        MODEL[session_users]=1; MODEL[session_count]=4; MODEL[session_records]=4; MODEL[session_parsed]=4
        MODEL[tcp_admin]=3
        ACT_CONN[1.local]=192.0.2.17:22; ACT_CONN[1.label]=SSH
        ACT_CONN[2.local]=192.0.2.17:3389; ACT_CONN[2.peer]=192.0.2.58:55001; ACT_CONN[2.label]=RDP
        if [[ $SERVICES_MODE == all ]]; then MODEL[services_scope]=full
        else MODEL[services_scope]=runtime; fi
        ((SHOW_JOURNAL)) || MODEL[journal_state]=skipped
    else
        initialize_optional_model
        if (( ${WORKSHOP_BUDGET_FALLBACK:-0} )); then
            LOCAL_ONLY=1; SHOW_JOURNAL=0
            collect_identity; collect_health; collect_memory; collect_swap; collect_zram; collect_zswap
            MODEL[budget_limited]=1; MODEL[deadline_fallback]=1
        else
            io_begin
            collect_identity; collect_health; collect_memory; collect_swap; collect_zram; collect_zswap
            if budget_allow; then collect_storage; fi
            if budget_allow; then
                if [[ $SERVICES_MODE == all ]]; then collect_services; MODEL[services_scope]=full
                else collect_services_fast; fi
            fi
            if budget_allow; then collect_processes; fi
            if budget_allow; then collect_sessions; fi
            if budget_allow; then collect_connections; fi
            io_finish
            if ((SHOW_JOURNAL)) && budget_allow; then collect_journal; fi
        fi
    fi
    derive_model
}
main() {
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
    export SYSTEMD_PAGER=cat SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 SYSTEMD_PAGERSECURE=1 SYSTEMD_ASK_PASSWORD_AGENT=0
    local rc=0
    parse_options "$@" || rc=$?
    ((rc!=3)) || return 0; ((rc==0)) || return "$rc"
    if ! ui_registry_init; then
        printf '%s\n' 'Invalid section registry or display configuration; inspect SETTINGS.' >&2
        return 2
    fi
    ui_plan_layout || return $?
    collect_all; prepare_view
    render_adaptive || return $?
    printf '%s' "$OUTPUT"
    ((WORKER==0)) || printf '%s\n' '__WORKSHOP_COMPLETE_V2__'
}

# ===================== 3. RESOURCE COLLECTION ================================
run_bounded() {
    command -v timeout >/dev/null 2>&1 || return 127
    local duration=$1 limit remain number
    shift
    if [[ $MODE == concise ]]; then
        budget_remaining || return 125
        remain=$REPLY; limit=$CONCISE_HELPER_MAX_MS
        ((limit<=remain)) || limit=$remain
        ((limit>0)) || return 125
        printf -v duration '%d.%03ds' "$((limit/1000))" "$((limit%1000))"
        LC_ALL=C timeout --kill-after=0.02s "$duration" "$@" </dev/null
    else LC_ALL=C timeout --kill-after=0.2s "$duration" "$@" </dev/null; fi
}

collector_uint() {
    # Bounded ASCII digits keep signed arithmetic safe without regex compilation.
    [[ -n $1 && ${#1} -le 15 && $1 != *[!0123456789]* ]] || return 1
    REPLY=$((10#$1))
}

mount_unescape() {
    REPLY=${1//\\040/ }; REPLY=${REPLY//\\011/$'\t'}
    REPLY=${REPLY//\\012/$'\n'}; REPLY=${REPLY//\\134/\\}
}

collect_memory() {
    local key value unit field
    local -A names=([MemTotal]=mem_total [MemFree]=mem_free
        [MemAvailable]=mem_available [Buffers]=mem_buffers [Cached]=mem_cached
        [Shmem]=mem_shmem [SReclaimable]=mem_sreclaimable
        [SwapTotal]=swap_total [SwapFree]=swap_free
        [Zswap]=zswap_pool_kib [Zswapped]=zswap_original_kib)
    for field in "${names[@]}"; do MODEL[$field]=''; done
    MODEL[meminfo_state]=unavailable
    [[ -r $PROC_ROOT/meminfo ]] || return 0
    while read -r key value unit; do
        [[ -n $key ]] || continue
        key=${key%:}; field=${names[$key]-}
        [[ -n $field && $unit == kB ]] || continue
        if collector_uint "$value"; then MODEL[$field]=$REPLY; fi
    done 2>/dev/null <"$PROC_ROOT/meminfo"
    MODEL[meminfo_state]=ok
    for field in mem_total mem_free mem_available mem_buffers mem_cached mem_shmem mem_sreclaimable swap_total swap_free; do
        [[ -n ${MODEL[$field]} ]] || MODEL[meminfo_state]=partial
    done
}

collect_zswap() {
    local value='' enabled_file=$SYS_ROOT/module/zswap/parameters/enabled
    MODEL[zswap_enabled]=''; MODEL[zswap_state]=unavailable; MODEL[zswap_present]=1
    if [[ -r $enabled_file ]]; then
        read -r value 2>/dev/null <"$enabled_file" || :
        case $value in Y|y|1) MODEL[zswap_enabled]=1 ;; N|n|0) MODEL[zswap_enabled]=0 ;; esac
    fi
    if [[ -n ${MODEL[zswap_pool_kib]-} && -n ${MODEL[zswap_original_kib]-} ]]; then
        MODEL[zswap_state]=ok
    elif [[ -n ${MODEL[zswap_pool_kib]-} || -n ${MODEL[zswap_original_kib]-} ]]; then
        MODEL[zswap_state]=partial
    elif [[ ! -e $enabled_file ]]; then
        # No exposed interface is treated as absent, not proof of kernel configuration.
        MODEL[zswap_state]=absent; MODEL[zswap_present]=0
    fi
    # Disabled does not mean empty. Unreadable/missing counters stay unknown.
}

collect_swap() {
    local path type size used priority extra total=0 occupied=0
    MODEL[swap_devices_state]=unavailable; MODEL[swap_state]=unavailable
    MODEL[swap_snapshot_mismatch]=0
    MODEL[swap_zram_used]=''; MODEL[swap_other_used]=''
    MODEL[swap_zram_total]=''; MODEL[swap_other_total]=''
    [[ -r $PROC_ROOT/swaps ]] || return 0
    MODEL[swap_devices_state]=ok
    MODEL[swap_zram_used]=0; MODEL[swap_other_used]=0
    MODEL[swap_zram_total]=0; MODEL[swap_other_total]=0
    while read -r path type size used priority extra; do
        [[ $path == Filename ]] && continue
        if ! collector_uint "$size"; then MODEL[swap_devices_state]=partial; continue; fi
        size=$REPLY
        if ! collector_uint "$used"; then MODEL[swap_devices_state]=partial; continue; fi
        used=$REPLY
        if ((used > size)); then MODEL[swap_devices_state]=partial; continue; fi
        # /proc/swaps counts occupied swap slots, not zram's stored byte total.
        if [[ $path =~ ^/dev/zram[0-9]+$ ]]; then type=zram; else type=other; fi
        MODEL[swap_${type}_total]=$((MODEL[swap_${type}_total] + size))
        MODEL[swap_${type}_used]=$((MODEL[swap_${type}_used] + used))
        total=$((total + size)); occupied=$((occupied + used))
    done 2>/dev/null <"$PROC_ROOT/swaps"
    if [[ -n ${MODEL[swap_total]-} && -n ${MODEL[swap_free]-} ]] &&
       ((total != MODEL[swap_total] || occupied != MODEL[swap_total] - MODEL[swap_free])); then
        MODEL[swap_snapshot_mismatch]=1
    fi
    MODEL[swap_state]=${MODEL[swap_devices_state]}
    ((MODEL[swap_snapshot_mismatch] == 0)) || MODEL[swap_state]=partial
}

collect_zram() {
    local dir original compressed pool rest backing count=0 valid=0
    local original_sum=0 compressed_sum=0 pool_sum=0
    MODEL[zram_state]=unavailable; MODEL[zram_partial]=0
    MODEL[zram_pool_kib]=''; MODEL[zram_original_kib]=''; MODEL[zram_compressed_kib]=''
    MODEL[zram_count]=0; MODEL[zram_valid_count]=0
    MODEL[zram_writeback]=0; MODEL[zram_writeback_unknown]=0
    [[ -d $SYS_ROOT/block && -r $SYS_ROOT/block ]] || return 0
    for dir in "$SYS_ROOT"/block/zram[0-9]*; do
        [[ -d $dir ]] || continue
        count=$((count + 1))
        original=''; compressed=''; pool=''
        if [[ -r $dir/mm_stat ]]; then
            read -r original compressed pool rest 2>/dev/null <"$dir/mm_stat" || :
        fi
        if collector_uint "$original"; then original=$REPLY; else original=''; fi
        if collector_uint "$compressed"; then compressed=$REPLY; else compressed=''; fi
        if collector_uint "$pool"; then pool=$REPLY; else pool=''; fi
        if [[ -n $original && -n $compressed && -n $pool ]]; then
            original_sum=$((original_sum + original)); compressed_sum=$((compressed_sum + compressed))
            pool_sum=$((pool_sum + pool)); valid=$((valid + 1))
        else MODEL[zram_partial]=1; fi
        backing=''
        if [[ -r $dir/backing_dev ]]; then read -r backing 2>/dev/null <"$dir/backing_dev" || :; fi
        if [[ $backing == none ]]; then :
        elif [[ -n $backing ]]; then MODEL[zram_writeback]=1
        else MODEL[zram_writeback_unknown]=1; fi
    done
    MODEL[zram_count]=$count; MODEL[zram_valid_count]=$valid
    MODEL[zram_state]=ok
    if ((valid == count)); then
        MODEL[zram_pool_kib]=$((pool_sum / 1024))
        MODEL[zram_original_kib]=$((original_sum / 1024))
        MODEL[zram_compressed_kib]=$((compressed_sum / 1024))
    else MODEL[zram_state]=partial; fi
    # Pool RAM is already part of MemTotal usage; never add it to RAM/swap capacity.
    # Ratios require nonzero denominators and known-disabled writeback.
}

collect_storage() {
    local line before after id parent dev root target options type source rest key index
    local total used avail raw_avail itotal iused ifree output rc=0 skipped=0 shared=0 invalid=0
    local -a order=() targets=() requested=()
    local -A devices=() sources=() types=() seen_dev=() seen_source=() seen_target=()
    DISK=(); DISK_IDS=(); MODEL[storage_state]=unavailable
    MODEL[storage_complete]=0; MODEL[storage_skipped]=0; MODEL[storage_skipped_shared]=0
    MODEL[storage_shared_pool]=0; MODEL[storage_count]=0
    [[ -r $PROC_ROOT/self/mountinfo ]] || return 0
    while IFS= read -r line; do
        [[ $line == *' - '* ]] || continue
        before=${line%%' - '*}; after=${line#*' - '}
        read -r id parent dev root target options rest <<<"$before"
        read -r type source rest <<<"$after"
        mount_unescape "$target"; target=$REPLY
        mount_unescape "$source"; source=$REPLY
        [[ -n $target && $target != *[$'\n\r\t']* ]] || continue
        [[ ${devices[$target]+set} ]] || order+=("$target")
        devices[$target]=$dev; sources[$target]=$source; types[$target]=$type
    done 2>/dev/null <"$PROC_ROOT/self/mountinfo"
    if ((${#STORAGE_MOUNTS[@]})); then requested=("${STORAGE_MOUNTS[@]}")
    else requested=("${order[@]}"); fi
    for target in "${requested[@]}"; do
        if [[ -z $target || ! ${devices[$target]+set} ]]; then skipped=$((skipped + 1)); continue; fi
        dev=${devices[$target]}; source=${sources[$target]}; type=${types[$target]}
        case $type in
            zfs) shared=$((shared + 1)); continue ;;
            btrfs) if ((${#STORAGE_MOUNTS[@]} == 0)); then shared=$((shared + 1)); continue; fi
                   MODEL[storage_shared_pool]=1 ;;
            tmpfs|devtmpfs|overlay|squashfs|ramfs|proc|sysfs|cgroup*|autofs|fuse.portal|fuse.gvfsd-fuse) continue ;;
            nfs*|cifs|smb*|9p|ceph|afs|fuse.sshfs|fuse.rclone|fuse.s3fs|fuse.glusterfs|fuse.davfs*)
                ((${#STORAGE_MOUNTS[@]} == 0)) || skipped=$((skipped + 1)); continue ;;
        esac
        [[ $source != /dev/zram* && $source != /dev/loop* && $source != /dev/ram* && $dev != 7:* && $dev != 1:* ]] || continue
        case $type in
            ext2|ext3|ext4|xfs|btrfs|f2fs|vfat|msdos|exfat|ntfs|ntfs3|fuseblk|jfs|reiserfs|bcachefs|ufs) ;;
            *) if [[ $source == /dev/* || $type == fuse.* ]] || ((${#STORAGE_MOUNTS[@]})); then
                   skipped=$((skipped + 1))
               fi
               continue ;;
        esac
        [[ $source == /dev/* ]] || { skipped=$((skipped + 1)); continue; }
        [[ $dev =~ ^[0-9]+:[0-9]+$ && -n $source && $source != none ]] || { skipped=$((skipped + 1)); continue; }
        # Device identity merges bind mounts/aliases. Btrfs sources also merge subvolumes.
        key=$dev
        [[ $type != btrfs || ! ${seen_source[$source]+set} ]] || key=${seen_source[$source]}
        if [[ ${seen_dev[$key]+set} ]]; then
            index=${seen_dev[$key]}
            if ((${#target} < ${#targets[$index]})); then targets[$index]=$target; fi
        else
            seen_dev[$key]=${#targets[@]}; targets+=("$target")
        fi
        [[ $type != btrfs ]] || seen_source[$source]=$key
    done
    # Skipped counters count mount entries, not disks or unique storage pools.
    MODEL[storage_skipped]=$skipped; MODEL[storage_skipped_shared]=$shared
    if ((${#targets[@]} == 0)); then
        MODEL[storage_state]=ok
        ((skipped + shared == 0)) || MODEL[storage_state]=partial
        ((skipped + shared != 0)) || MODEL[storage_complete]=1
        return 0
    fi
    command -v df >/dev/null 2>&1 || return 0
    # Explicit mount targets avoid recursive traversal. --local filters known remote types.
    # Numeric-first output preserves spaces in target paths; no per-mount child processes.
    output=$(run_bounded "${STORAGE_TIMEOUT:-0.5s}" df --local --no-sync --block-size=1024 \
        --output=size,used,avail,itotal,iused,iavail,target -- "${targets[@]}" 2>/dev/null) || rc=$?
    while IFS= read -r line; do
        [[ $line =~ ^[[:space:]]*([0-9]+)[[:space:]]+([0-9]+)[[:space:]]+(-?[0-9]+)[[:space:]]+([0-9-]+)[[:space:]]+([0-9-]+)[[:space:]]+([0-9-]+)[[:space:]]+(.*)$ ]] || continue
        total=${BASH_REMATCH[1]}; used=${BASH_REMATCH[2]}; avail=${BASH_REMATCH[3]}; itotal=${BASH_REMATCH[4]}; iused=${BASH_REMATCH[5]}; ifree=${BASH_REMATCH[6]}; target=${BASH_REMATCH[7]}
        if ! collector_uint "$total"; then invalid=1; continue; fi; total=$REPLY
        if ! collector_uint "$used"; then invalid=1; continue; fi; used=$REPLY
        raw_avail=$avail
        if [[ $avail == -* ]]; then
            if ! collector_uint "${avail#-}"; then invalid=1; continue; fi
            avail=0
        else
            if ! collector_uint "$avail"; then invalid=1; continue; fi; avail=$REPLY
        fi
        if ((total == 0 || used + avail > total)) || [[ ! ${devices[$target]+set} ]]; then invalid=1; continue; fi
        [[ ! ${seen_target[$target]+set} ]] || continue
        seen_target[$target]=1; id=${#DISK_IDS[@]}; DISK_IDS+=("$id")
        DISK[$id.target]=$target; DISK[$id.source]=${sources[$target]}; DISK[$id.fstype]=${types[$target]}
        DISK[$id.total_kib]=$total; DISK[$id.used_kib]=$used; DISK[$id.avail_kib]=$avail
        DISK[$id.reserved_kib]=$((total - used - avail)); DISK[$id.valid]=1
        DISK[$id.raw_avail_kib]=$raw_avail
        DISK[$id.inodes_total]=''; DISK[$id.inodes_free]=''
        if collector_uint "$itotal"; then
            itotal=$REPLY
            if [[ $ifree =~ ^-[0-9]+$ ]] && collector_uint "${ifree#-}"; then ifree=0; fi
            if collector_uint "$ifree" && ((REPLY<=itotal)); then
                DISK[$id.inodes_total]=$itotal; DISK[$id.inodes_free]=$REPLY
            fi
        fi
    done <<<"$output"
    MODEL[storage_count]=${#DISK_IDS[@]}; MODEL[storage_state]=ok
    if ((rc || invalid || skipped || shared || MODEL[storage_shared_pool] || ${#DISK_IDS[@]} != ${#targets[@]})); then
        MODEL[storage_state]=partial
    else MODEL[storage_complete]=1; fi
    if ((rc == 124 || rc == 137)); then MODEL[storage_state]=timeout
    elif ((rc && ! ${#DISK_IDS[@]})); then MODEL[storage_state]=unavailable; fi
}

derive_model() {
    local total=${MODEL[mem_total]:-0} free=${MODEL[mem_free]-} cache comp other
    local id disk_total=0 disk_used=0 disk_avail=0 disk_reserved=0
    MODEL[mem_valid]=0; MODEL[mem_parts_valid]=0; MODEL[swap_valid]=0
    if [[ $total =~ ^[0-9]+$ && ${MODEL[mem_available]-} =~ ^[0-9]+$ ]] &&
        ((total > 0 && MODEL[mem_available] <= total)); then
        MODEL[mem_valid]=1; MODEL[mem_used]=$((total-MODEL[mem_available]))
        MODEL[mem_tenths]=$(((MODEL[mem_used]*1000+total/2)/total))
    fi
    if [[ $free =~ ^[0-9]+$ && ${MODEL[mem_buffers]-} =~ ^[0-9]+$ &&
          ${MODEL[mem_cached]-} =~ ^[0-9]+$ && ${MODEL[mem_shmem]-} =~ ^[0-9]+$ &&
          ${MODEL[mem_sreclaimable]-} =~ ^[0-9]+$ &&
          ${MODEL[zram_state]-} == ok && ( ${MODEL[zswap_state]-} == ok || ${MODEL[zswap_state]-} == absent ) ]] &&
          ((MODEL[mem_cached] >= MODEL[mem_shmem])); then
        cache=$((MODEL[mem_cached]-MODEL[mem_shmem]))
        cache=$((cache+MODEL[mem_buffers]+MODEL[mem_sreclaimable]))
        comp=$((${MODEL[zram_pool_kib]:-0}+${MODEL[zswap_pool_kib]:-0}))
        other=$((total-free-cache-comp))
        if ((total > 0 && other >= 0 && free <= total)); then
            MODEL[mem_parts_valid]=1; MODEL[mem_cache]=$cache
            MODEL[mem_compressed]=$comp; MODEL[mem_other]=$other
        fi
    fi
    if [[ ${MODEL[swap_total]-} =~ ^[0-9]+$ && ${MODEL[swap_free]-} =~ ^[0-9]+$ ]] &&
        ((MODEL[swap_free] <= MODEL[swap_total])); then
        MODEL[swap_valid]=1; MODEL[swap_used]=$((MODEL[swap_total]-MODEL[swap_free]))
    fi
    MODEL[storage_overflow]=0
    for id in "${DISK_IDS[@]}"; do
        if ((${DISK[$id.total_kib]}>900000000000000-disk_total)); then
            MODEL[storage_overflow]=1; MODEL[storage_state]=partial; continue
        fi
        disk_total=$((disk_total+${DISK[$id.total_kib]})); disk_used=$((disk_used+${DISK[$id.used_kib]}))
        disk_avail=$((disk_avail+${DISK[$id.avail_kib]})); disk_reserved=$((disk_reserved+${DISK[$id.reserved_kib]}))
    done
    MODEL[storage_total]=$disk_total; MODEL[storage_used]=$disk_used
    MODEL[storage_avail]=$disk_avail; MODEL[storage_reserved]=$disk_reserved
}

# ===================== 4. SERVICES AND ACTIVITY ==============================

# Runtime state and installation state are independent snapshots. SVC keys are
# "unit.field". An absent runtime record never becomes STOP unless actually read.
declare -A SVC=() SVC_GROUP_MEMBERS=()
SVC_KEYS=() SVC_FAILURES=() SVC_EXTRA=()

svc_add_key() {
    [[ -n ${SVC[$1.seen]-} ]] && return 0
    SVC[$1.seen]=1
    SVC_KEYS+=("$1")
}
svc_excluded() {
    local pattern
    for pattern in "${SERVICE_EXCLUDE_PATTERNS[@]}"; do
        [[ $1 == $pattern ]] && return 0
    done
    return 1
}
svc_group() {
    local u=$1
    REPLY=${SERVICE_GROUP_OVERRIDE[$u]-}
    [[ -z $REPLY ]] || return 0
    case $u in
        ssh.service|sshd.service|ssh.socket|sshd.socket|sshd@*.service|dropbear*|xrdp*|vncserver*|tigervnc*|x11vnc*|wayvnc*|gnome-remote-desktop*|cockpit*|webmin*) REPLY=Access ;;
        vsftpd*|proftpd*|pure-ftpd*|tftpd*|tftp.*|tftp@*|atftpd*|smbd.*|nmbd.*|smb.*|nmb.*|samba.service|nfs-server.*|nfs-kernel-server.*|nfs-mountd.*|rpcbind.*|rsync.*|rsyncd.*) REPLY=Files ;;
        apache2.*|httpd.*|nginx.*|caddy.*|haproxy.*|squid.*|traefik.*) REPLY=Web ;;
        postgresql*|mysql.*|mysqld.*|mariadb.*|redis*|memcached.*|mongod.*|mongodb.*|elasticsearch.*|opensearch.*|influxdb.*|clickhouse*) REPLY=Data ;;
        postfix*|exim*|sendmail*|dovecot*) REPLY=Mail ;;
        NetworkManager.*|systemd-networkd.*|networking.*|wicked*|connman.*|systemd-resolved.*|dnsmasq.*|unbound.*|named.*|bind9.*|dhcpd*|isc-dhcp*|kea-*|openvpn*|wg-quick*|tailscaled.*|zerotier-one.*|strongswan*|charon*) REPLY=Network ;;
        sssd*|winbind.*|realmd.*|krb5-kdc.*|slapd.*|samba-ad-dc.*) REPLY=Identity ;;
        ufw.*|firewalld.*|nftables.*|iptables.*|ip6tables.*|fail2ban.*|apparmor.*|auditd.*) REPLY=Security ;;
        docker.*|containerd.*|podman.*|libvirtd.*|virtqemud.*|virtlogd.*|virtlockd.*|virtnetworkd.*|virtstoraged.*|virtproxyd.*|qemu-guest-agent.*|vmtoolsd.*|vboxservice.*|lxc.*|lxcfs.*|kubelet.*|k3s*) REPLY=Virtual ;;
        chrony.*|chronyd.*|ntp.*|ntpd.*|ntpsec.*|systemd-timesyncd.*) REPLY=Time ;;
        systemd-journald.*|systemd-logind.*|systemd-udevd.*|dbus.*|dbus-broker.*|rsyslog.*|syslog-ng.*|cron.*|crond.*|earlyoom.*|systemd-oomd.*|smartd.*|smartmontools.*|mdmonitor.*|irqbalance.*|zabbix-agent*|prometheus*|node_exporter.*|nagios*|nrpe.*|netdata.*) REPLY=System ;;
        display-manager.*|lightdm.*|gdm.*|gdm3.*|sddm.*|xdm.*|cups.*|cups-browsed.*|bluetooth.*|avahi-daemon.*) REPLY=Local ;;
        *) REPLY='' ;;
    esac
}
svc_parse_runtime() {
    local unit load active sub ignored
    while read -r unit load active sub ignored; do
        [[ -n $unit ]] || continue
        # --plain removes systemctl's bullet; no unit names or descriptions run.
        [[ $unit == *.* && -n $load && -n $active && -n $sub ]] || continue
        safe_text "$unit"; unit=$REPLY
        [[ -n $unit ]] || continue
        svc_add_key "$unit"
        safe_text "$load"; SVC[$unit.load]=$REPLY
        safe_text "$active"; SVC[$unit.active]=$REPLY
        safe_text "$sub"; SVC[$unit.sub]=$REPLY
        SVC[$unit.runtime]=1
    done <<<"$1"
}
svc_parse_files() {
    local unit state preset ignored
    while read -r unit state preset ignored; do
        [[ -n $unit ]] || continue
        case $unit in *.service|*.socket|*.timer) ;; *) continue ;; esac
        [[ -n $state ]] || continue
        safe_text "$unit"; unit=$REPLY
        [[ -n $unit ]] || continue
        svc_add_key "$unit"
        safe_text "$state"; SVC[$unit.file]=$REPLY
        # The optional PRESET column is policy, not current enablement; ignore it.
    done <<<"$1"
}
svc_finalize() {
    local unit group active load
    SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[svc_loaded]=0; MODEL[svc_running]=0; MODEL[svc_installed]=0
    MODEL[svc_failed]=0; MODEL[svc_aliases]=0
    for unit in "${SVC_KEYS[@]}"; do
        svc_excluded "$unit" && continue
        active=${SVC[$unit.active]-}; load=${SVC[$unit.load]-}
        if [[ $active == failed || $load == error || $load == bad-setting || ${SVC[$unit.file]-} == bad ]]; then
            SVC_FAILURES+=("$unit"); ((MODEL[svc_failed]+=1))
        fi
        case $unit in *.service|*.socket|*.timer) ;; *) continue ;; esac
        [[ $load != loaded ]] || ((MODEL[svc_loaded]+=1))
        [[ -z ${SVC[$unit.file]-} ]] || ((MODEL[svc_installed]+=1))
        [[ $active != active || ${SVC[$unit.sub]-} != running ]] || ((MODEL[svc_running]+=1))
        if [[ ${SVC[$unit.file]-} == alias && -z ${SVC[$unit.runtime]-} ]]; then
            ((MODEL[svc_aliases]+=1)); continue
        fi
        svc_group "$unit"; group=$REPLY
        # Template files are available definitions, not stopped instances.
        if [[ $unit == *@.service || $unit == *@.socket || $unit == *@.timer ]]; then continue; fi
        if [[ -n $group ]]; then
            SVC_GROUP_MEMBERS[$group]+="$unit"$'\n'
        else
            case $active in active|reloading|activating|deactivating|failed|maintenance) SVC_EXTRA+=("$unit") ;; esac
        fi
    done
}
collect_services() {
    local output rc
    SVC=(); SVC_KEYS=(); SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[services_state]=unavailable
    MODEL[svc_runtime_state]=unavailable; MODEL[svc_files_state]=unavailable
    if ! command -v systemctl >/dev/null 2>&1; then svc_finalize; return 0; fi
    # Includes every unit type so a failed mount/swap is not lost in Attention.
    if output=$(LC_ALL=C SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 \
        run_bounded "$SERVICE_TIMEOUT" systemctl --no-ask-password --no-pager \
        --no-legend --plain --full list-units --all 2>/dev/null); then
        MODEL[svc_runtime_state]=ok; svc_parse_runtime "$output"
    else
        rc=$?; [[ $rc != 124 && $rc != 137 ]] || MODEL[svc_runtime_state]=timeout
    fi
    if output=$(LC_ALL=C SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 \
        run_bounded "$SERVICE_TIMEOUT" systemctl --no-ask-password --no-pager \
        --no-legend --full list-unit-files --type=service,socket,timer 2>/dev/null); then
        MODEL[svc_files_state]=ok; svc_parse_files "$output"
    else
        rc=$?; [[ $rc != 124 && $rc != 137 ]] || MODEL[svc_files_state]=timeout
    fi
    if [[ ${MODEL[svc_runtime_state]} == ok && ${MODEL[svc_files_state]} == ok ]]; then MODEL[services_state]=ok
    elif [[ ${MODEL[svc_runtime_state]} == ok || ${MODEL[svc_files_state]} == ok ]]; then MODEL[services_state]=partial
    elif [[ ${MODEL[svc_runtime_state]} == timeout || ${MODEL[svc_files_state]} == timeout ]]; then MODEL[services_state]=timeout; fi
    svc_finalize
}

# Both terse and full views preserve separate runtime, load and boot information.
# The compact suffix is an installation flag, never a claim about running state.
svc_state() {
    local unit=$1 active=${SVC[$1.active]-} sub=${SVC[$1.sub]-}
    local load=${SVC[$1.load]-} file=${SVC[$1.file]-}
    SVC_COLOR=${COLOR[muted]}; REPLY='?'
    if [[ $active == failed || $load == bad-setting || $load == error || $file == bad ]]; then
        REPLY=FAIL; SVC_COLOR=${COLOR[error]}
    elif [[ -n ${SVC[$unit.runtime]-} ]]; then
        case $active/$sub in
            active/running) REPLY=RUN; SVC_COLOR=${COLOR[ok]} ;;
            active/exited) REPLY=DONE; SVC_COLOR=${COLOR[ok]} ;;
            active/listening) REPLY=LISTEN; SVC_COLOR=${COLOR[ok]} ;;
            active/waiting) REPLY=WAIT; SVC_COLOR=${COLOR[ok]} ;;
            reloading/*) REPLY=RELOAD; SVC_COLOR=${COLOR[ok]} ;;
            activating/*) REPLY=START; SVC_COLOR=${COLOR[warn]} ;;
            deactivating/*) REPLY=STOPPING; SVC_COLOR=${COLOR[warn]} ;;
            maintenance/*) REPLY=MAINT; SVC_COLOR=${COLOR[warn]} ;;
            active/*) REPLY=ACTIVE; SVC_COLOR=${COLOR[ok]} ;;
            inactive/*)
                if [[ $load == masked || $file == masked* ]]; then REPLY=MASK
                elif [[ $load == not-found ]]; then REPLY=N/A
                else REPLY=STOP; fi ;;
        esac
    elif [[ $unit == *@.service || $unit == *@.socket || $unit == *@.timer ]]; then REPLY=TEMPLATE
    elif [[ $file == alias ]]; then REPLY=ALIAS
    elif [[ $file == masked* ]]; then REPLY=MASK
    elif [[ ${MODEL[svc_runtime_state]-} == ok && -n $file ]]; then REPLY=UNLOADED
    fi
}
svc_file_flag() {
    case ${SVC[$1.file]-} in
        enabled) REPLY=e ;; enabled-runtime) REPLY=er ;;
        disabled) REPLY=d ;; static) REPLY=s ;;
        masked) REPLY=m ;; masked-runtime) REPLY=mr ;;
        generated) REPLY=g ;; transient) REPLY=t ;; alias) REPLY=a ;;
        linked) REPLY=l ;; linked-runtime) REPLY=lr ;; indirect) REPLY=i ;;
        bad) REPLY=b ;; *) REPLY='?' ;;
    esac
}


service_attention() {
    local unit count=0 total=${#SVC_FAILURES[@]} quoted_unit
    case ${MODEL[services_state]-unavailable} in
        ok) ;;
        partial) ATTENTION+=('INFO|Service inventory is partial; some runtime/installation states are unknown.') ;;
        timeout) ATTENTION+=('INFO|Service inventory timed out; states are unknown.') ;;
        *) ATTENTION+=('INFO|Systemd service inventory unavailable on this system.') ;;
    esac
    for unit in "${SVC_FAILURES[@]}"; do
        ((count < SERVICE_ALERT_LIMIT)) || break
        safe_text "$unit"; printf -v quoted_unit '%q' "$REPLY"
        ATTENTION+=("ERROR|Unit needs review: systemctl status -- $quoted_unit")
        ((count+=1))
    done
    if ((total > count)); then ATTENTION+=("ERROR|$((total-count)) additional failed/bad units; run systemctl --failed."); fi
    for unit in "${REQUIRED_UNITS[@]}"; do
        safe_text "$unit"; unit=$REPLY
        if [[ ${MODEL[svc_runtime_state]-} != ok ]]; then
            ATTENTION+=("INFO|Required unit cannot be checked: $unit")
        elif [[ ${SVC[$unit.active]-} != active && ${SVC[$unit.active]-} != reloading ]]; then
            # Alias listings do not resolve canonical runtime state: say unknown.
            if [[ ${SVC[$unit.file]-} == alias ]]; then
                ATTENTION+=("INFO|Required alias needs a canonical unit name: $unit")
            else
                ATTENTION+=("WARN|Required unit is not recorded active: $unit")
            fi
        fi
    done
}
demo_services() {
    SVC=(); SVC_KEYS=(); SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[services_state]=ok; MODEL[svc_runtime_state]=ok; MODEL[svc_files_state]=ok
    svc_parse_runtime 'ssh.service loaded active running OpenBSD Secure Shell
xrdp.service loaded active running Remote Desktop
xrdp-sesman.service loaded active running Remote sessions
vsftpd.service loaded inactive dead FTP server
tftpd-hpa.service loaded active running TFTP server
smbd.service loaded active running SMB server
nginx.service loaded active running Web server
mariadb.service loaded active running Database
NetworkManager.service loaded active running Network manager
systemd-resolved.service loaded active running Resolver
sssd.service loaded active running Identity
nftables.service loaded active exited Packet rules
docker.service loaded active running Containers
systemd-journald.service loaded active running Journal
cron.service loaded active running Scheduled jobs
earlyoom.service loaded active running Memory guardian
chrony.service loaded active running Time sync
lightdm.service loaded inactive dead Display manager
cups.socket loaded active listening Print activation
workshop-agent.service loaded active running Workshop agent
apt-daily.timer loaded active waiting Package metadata timer'
    svc_parse_files 'ssh.service enabled enabled
sshd.service alias -
xrdp.service enabled enabled
xrdp-sesman.service enabled enabled
vsftpd.service disabled enabled
tftpd-hpa.service enabled enabled
smbd.service enabled enabled
nginx.service enabled enabled
mariadb.service enabled enabled
NetworkManager.service enabled enabled
systemd-resolved.service enabled enabled
sssd.service enabled enabled
nftables.service enabled disabled
docker.service enabled enabled
systemd-journald.service static -
cron.service enabled enabled
earlyoom.service enabled enabled
chrony.service enabled enabled
lightdm.service disabled enabled
display-manager.service alias -
cups.socket enabled enabled
workshop-agent.service enabled enabled
apt-daily.timer enabled enabled
getty@.service indirect enabled'
    if [[ ${DEMO:-0} == 2 ]]; then
        svc_parse_runtime 'nginx.service loaded failed failed Web server
mnt-backup.mount loaded failed failed Backup volume'
    fi
    svc_finalize
}


declare -A ACT_PROC ACT_SESSION ACT_CONN ACT_LOCAL_USER
declare -a ACT_CPU_IDS ACT_RAM_IDS ACT_SESSION_IDS ACT_CONN_IDS

activity_top_insert() {
    # Fixed-size insertion: O(processes * TOP_N), never sort a full PID table.
    local -n list=$1
    local field=$2 pid=$3 score=$4 i j
    for ((i=0; i<${#list[@]}; i++)); do
        ((score > ${ACT_PROC[${list[i]}.$field]:-0})) && break
    done
    ((i < TOP_N)) || return 0
    for ((j=${#list[@]}; j>i; j--)); do
        ((j < TOP_N)) && list[j]=${list[j-1]}
    done
    list[i]=$pid
}

collect_processes() {
    ACT_PROC=(); ACT_CPU_IDS=(); ACT_RAM_IDS=(); ACT_LOCAL_USER=()
    MODEL[process_state]=unavailable
    MODEL[process_count]=0; MODEL[process_running]=0
    MODEL[process_blocked]=0; MODEL[process_zombies]=0
    local snapshot rc pid uid cpu rss state name integer fraction score bad=0
    snapshot=$(run_bounded "$ACTIVITY_TIMEOUT" ps -eo pid=,euid=,pcpu=,rss=,stat=,comm= -ww 2>/dev/null); rc=$?
    if ((rc != 0)); then
        ((rc == 124 || rc == 137)) && MODEL[process_state]=timeout
        return 0
    fi
    [[ -n $snapshot ]] || return 0
    while read -r pid uid cpu rss state name; do
        [[ -n $pid ]] || continue
        if ! collector_uint "$pid" || ! collector_uint "$uid" || ! collector_uint "$rss" ||
            [[ ! $cpu =~ ^([0-9]{1,9})\.([0-9])$ ]]; then
            ((bad+=1)); continue
        fi
        integer=${BASH_REMATCH[1]}; fraction=${BASH_REMATCH[2]}
        score=$((10#$integer*10+10#$fraction))
        ((MODEL[process_count]+=1))
        case ${state:0:1} in
            R) ((MODEL[process_running]+=1)) ;;
            D) ((MODEL[process_blocked]+=1)) ;;
            Z) ((MODEL[process_zombies]+=1)) ;;
        esac
        # The reporting script and its ps snapshot are not useful workload rows.
        [[ $pid != "$$" && $name != ps ]] || continue
        ACT_PROC[$pid.uid]=$uid; ACT_PROC[$pid.cpu]=$cpu
        ACT_PROC[$pid.score]=$score; ACT_PROC[$pid.rss]=$rss
        safe_text "$name"; ACT_PROC[$pid.name]=$REPLY
        safe_text "$state"; ACT_PROC[$pid.state]=$REPLY
        activity_top_insert ACT_CPU_IDS score "$pid" "$score"
        activity_top_insert ACT_RAM_IDS rss "$pid" "$rss"
    done <<<"$snapshot"
    if ((MODEL[process_count] == 0)); then return 0; fi
    MODEL[process_state]=ok
    ((bad == 0)) || MODEL[process_state]=partial
    # Only local files: do not trigger LDAP/SSSD/NIS lookups for every PID.
    if [[ -r ${ETC_ROOT:-/etc}/passwd ]]; then
        while IFS=: read -r name _ uid _; do
            [[ $uid =~ ^[0-9]+$ ]] || continue
            safe_text "$name"; ACT_LOCAL_USER[$uid]=$REPLY
        done <"${ETC_ROOT:-/etc}/passwd"
    fi
}

activity_session_record() {
    local -n rec=$1
    local sid=${rec[Id]-} uid=${rec[User]-} class=${rec[Class]-}
    local field value kind index name service
    [[ -n $sid && $uid =~ ^[0-9]+$ ]] || return 0
    ((MODEL[session_parsed]+=1))
    case $class in greeter|lock-screen|background*|manager*) return 0 ;; esac
    # Unknown classes remain visible with their explicit type, not discarded.
    index=${#ACT_SESSION_IDS[@]}; ACT_SESSION_IDS+=("$index")
    for field in Id Name User Service Type Class State Remote RemoteHost TTY Display; do
        safe_text "${rec[$field]-}"; ACT_SESSION[$index.$field]=$REPLY
    done
    service=${ACT_SESSION[$index.Service]}
    kind=''
    [[ -z $service ]] || kind=${SESSION_SERVICE_KIND[$service]-}
    if [[ -z $kind ]]; then
        if [[ ${ACT_SESSION[$index.Remote]} == yes ]]; then kind=Remote
        else
            case ${ACT_SESSION[$index.Type]} in
                tty) kind=TTY ;; x11|wayland|mir|web) kind=GUI ;; *) kind=Other ;;
            esac
        fi
    fi
    ACT_SESSION[$index.Kind]=$kind
    name=${ACT_SESSION[$index.Name]}
    [[ -n $name ]] || ACT_SESSION[$index.Name]="UID $uid"
    ACT_SESSION_SEEN[$uid]=1
}

collect_sessions() {
    ACT_SESSION=(); ACT_SESSION_IDS=()
    MODEL[session_state]=unavailable; MODEL[session_source]=none
    MODEL[session_records]=0; MODEL[session_parsed]=0
    MODEL[session_count]=0; MODEL[session_users]=0; MODEL[session_limited]=0
    local listing details rc sid rest key value name tty date clock endpoint index
    local -a ids=()
    local -A record=() ACT_SESSION_SEEN=()
    listing=$(run_bounded "$ACTIVITY_TIMEOUT" loginctl list-sessions --no-legend --no-pager 2>/dev/null); rc=$?
    if ((rc == 0)); then
        while read -r sid rest; do
            [[ -n $sid ]] || continue
            [[ $sid =~ ^[A-Za-z0-9_][A-Za-z0-9_.:-]*$ ]] || continue
            ((MODEL[session_records]+=1))
            if ((${#ids[@]} < SESSION_QUERY_LIMIT)); then ids+=("$sid")
            else MODEL[session_limited]=1; fi
        done <<<"$listing"
        MODEL[session_source]=logind
        if ((${#ids[@]} == 0)); then MODEL[session_state]=ok; return 0; fi
        details=$(run_bounded "$ACTIVITY_TIMEOUT" loginctl show-session --all --no-pager \
            -p Id -p Name -p User -p Service -p Type -p Class -p State \
            -p Remote -p RemoteHost -p TTY -p Display "${ids[@]}" 2>/dev/null); rc=$?
        # Exiting sessions can make the batch return nonzero; retain complete
        # records but mark the inventory partial. Discard timed-out output.
        if ((rc != 124 && rc != 137)) && [[ -n $details ]]; then
            while IFS= read -r rest; do
                if [[ -z $rest ]]; then activity_session_record record; record=(); continue; fi
                [[ $rest == *=* ]] || continue
                key=${rest%%=*}; value=${rest#*=}
                case $key in Id|Name|User|Service|Type|Class|State|Remote|RemoteHost|TTY|Display) record[$key]=$value ;; esac
            done <<<"$details"
            activity_session_record record
            if ((MODEL[session_parsed] > 0)); then
                MODEL[session_count]=${#ACT_SESSION_IDS[@]}
                MODEL[session_users]=${#ACT_SESSION_SEEN[@]}
                MODEL[session_state]=ok
                if ((rc != 0 || MODEL[session_parsed] != MODEL[session_records] || MODEL[session_limited])); then
                    MODEL[session_state]=partial
                fi
                return 0
            fi
        fi
    fi
    # utmp is a fallback, not proof of complete SSH/GUI/RDP coverage.
    listing=$(run_bounded "$ACTIVITY_TIMEOUT" who 2>/dev/null); rc=$?
    if ((rc != 0)); then
        MODEL[session_source]=none
        ((rc == 124 || rc == 137)) && MODEL[session_state]=timeout
        return 0
    fi
    MODEL[session_source]=utmp; MODEL[session_state]=fallback
    ACT_SESSION_SEEN=(); ACT_SESSION=(); ACT_SESSION_IDS=()
    while read -r name tty date clock endpoint; do
        [[ -n $name && -n $tty ]] || continue
        index=${#ACT_SESSION_IDS[@]}; ACT_SESSION_IDS+=("$index")
        safe_text "$name"; ACT_SESSION[$index.Name]=$REPLY; ACT_SESSION_SEEN[$REPLY]=1
        safe_text "$tty"; ACT_SESSION[$index.TTY]=$REPLY
        safe_text "$endpoint"; ACT_SESSION[$index.RemoteHost]=$REPLY
        ACT_SESSION[$index.Kind]=utmp; ACT_SESSION[$index.State]=recorded
        ACT_SESSION[$index.Type]=tty; ACT_SESSION[$index.User]=''
    done <<<"$listing"
    MODEL[session_count]=${#ACT_SESSION_IDS[@]}
    MODEL[session_users]=${#ACT_SESSION_SEEN[@]}
}

collect_connections() {
    ACT_CONN=(); ACT_CONN_IDS=()
    MODEL[connection_state]=unavailable
    MODEL[tcp_established]=0; MODEL[tcp_admin]=0
    local snapshot rc recv send local_ep peer extra port label index key bad=0
    local -a admin=() other=()
    local -A admin_ports=()
    for port in "${CONNECTION_ADMIN_PORTS[@]}"; do admin_ports[$port]=1; done
    snapshot=$(run_bounded "$ACTIVITY_TIMEOUT" ss -Hnt state established 2>/dev/null); rc=$?
    if ((rc != 0)); then
        ((rc == 124 || rc == 137)) && MODEL[connection_state]=timeout
        return 0
    fi
    MODEL[connection_state]=ok
    while read -r recv send local_ep peer extra; do
        [[ -n $recv ]] || continue
        # The explicit state filter suppresses ss's State column.
        if [[ ! $recv =~ ^[0-9]+$ || ! $send =~ ^[0-9]+$ || $local_ep != *:* || $peer != *:* ]]; then
            ((bad+=1)); continue
        fi
        port=${local_ep##*:}
        if [[ ! $port =~ ^[0-9]+$ ]]; then ((bad+=1)); continue; fi
        index=${MODEL[tcp_established]}; ((MODEL[tcp_established]+=1))
        label=${CONNECTION_PORT_LABEL[$port]-TCP}
        if [[ -n ${admin_ports[$port]-} ]]; then
            ((MODEL[tcp_admin]+=1))
            ((${#admin[@]} < MAX_CONNECTIONS)) || continue
            admin+=("$index")
        else
            ((${#other[@]} < MAX_CONNECTIONS)) || continue
            other+=("$index")
        fi
        safe_text "$local_ep"; ACT_CONN[$index.local]=$REPLY
        safe_text "$peer"; ACT_CONN[$index.peer]=$REPLY
        ACT_CONN[$index.label]=$label
    done <<<"$snapshot"
    ((bad == 0)) || MODEL[connection_state]=partial
    for key in "${admin[@]}" "${other[@]}"; do
        ((${#ACT_CONN_IDS[@]} < MAX_CONNECTIONS)) || break
        ACT_CONN_IDS+=("$key")
    done
}

collect_activity() {
    collect_processes
    collect_sessions
    collect_connections
}


activity_attention() {
    case ${MODEL[process_state]-unavailable} in
        ok) ;;
        *) ATTENTION+=("INFO|Process snapshot ${MODEL[process_state]-unavailable}; rankings may be incomplete.") ;;
    esac
    case ${MODEL[session_state]-unavailable} in
        ok|fallback) ;;
        *) ATTENTION+=("INFO|Session inventory ${MODEL[session_state]-unavailable}; review loginctl or who.") ;;
    esac
    case ${MODEL[connection_state]-unavailable} in
        ok) ;;
        *) ATTENTION+=("INFO|TCP socket snapshot ${MODEL[connection_state]-unavailable}.") ;;
    esac
    if ((${MODEL[process_zombies]:-0} > 0)); then
        ATTENTION+=("INFO|${MODEL[process_zombies]} zombie process(es) observed; inspect their parent processes.")
    fi
    if ((${MODEL[process_blocked]:-0} >= 3)); then
        ATTENTION+=("INFO|${MODEL[process_blocked]} processes in uninterruptible wait at this snapshot; inspect if persistent.")
    fi
}

demo_activity() {
    ACT_PROC=(); ACT_SESSION=(); ACT_CONN=(); ACT_LOCAL_USER=([1000]=tech [1001]=alex [33]=www-data [999]=postgres)
    local pid uid cpu rss name score index
    while read -r pid uid cpu rss name; do
        ACT_PROC[$pid.uid]=$uid; ACT_PROC[$pid.cpu]=$cpu
        ACT_PROC[$pid.rss]=$rss; ACT_PROC[$pid.name]=$name; ACT_PROC[$pid.state]=S
    done <<'ACTIVITY_DEMO'
2418 1000 82.4 841728 stress-ng
1632 999 12.8 1355776 postgres
2109 33 3.1 196608 nginx
3920 1001 1.2 622592 firefox
ACTIVITY_DEMO
    ACT_CPU_IDS=(2418 1632 2109); ACT_RAM_IDS=(1632 2418 3920)
    while ((${#ACT_CPU_IDS[@]} > TOP_N)); do unset 'ACT_CPU_IDS[${#ACT_CPU_IDS[@]}-1]'; done
    while ((${#ACT_RAM_IDS[@]} > TOP_N)); do unset 'ACT_RAM_IDS[${#ACT_RAM_IDS[@]}-1]'; done
    MODEL[process_state]=ok; MODEL[process_count]=184; MODEL[process_running]=2
    MODEL[process_blocked]=0; MODEL[process_zombies]=0
    MODEL[session_state]=ok; MODEL[session_source]=logind
    MODEL[session_records]=3; MODEL[session_parsed]=3; MODEL[session_count]=3
    MODEL[session_users]=2; MODEL[session_limited]=0; ACT_SESSION_IDS=(0 1 2)
    ACT_SESSION[0.Name]=tech; ACT_SESSION[0.Kind]=SSH; ACT_SESSION[0.State]=active
    ACT_SESSION[0.TTY]=pts/0; ACT_SESSION[0.RemoteHost]=192.0.2.24
    ACT_SESSION[1.Name]=alex; ACT_SESSION[1.Kind]=RDP; ACT_SESSION[1.State]=online
    ACT_SESSION[1.Display]=:10; ACT_SESSION[1.RemoteHost]=192.0.2.41
    ACT_SESSION[2.Name]=tech; ACT_SESSION[2.Kind]=TTY; ACT_SESSION[2.State]=online
    ACT_SESSION[2.TTY]=tty2; ACT_SESSION[2.RemoteHost]=''
    MODEL[connection_state]=ok; MODEL[tcp_established]=8; MODEL[tcp_admin]=2
    ACT_CONN_IDS=(0 1 2)
    ACT_CONN[0.local]=192.0.2.17:22; ACT_CONN[0.peer]=192.0.2.24:51422; ACT_CONN[0.label]=SSH
    ACT_CONN[1.local]=192.0.2.17:3389; ACT_CONN[1.peer]=192.0.2.41:60108; ACT_CONN[1.label]=RDP
    ACT_CONN[2.local]=192.0.2.17:443; ACT_CONN[2.peer]=198.51.100.8:50322; ACT_CONN[2.label]=HTTPS
    while ((${#ACT_CONN_IDS[@]} > MAX_CONNECTIONS)); do unset 'ACT_CONN_IDS[${#ACT_CONN_IDS[@]}-1]'; done
    if ((${DEMO:-1} == 2)); then MODEL[process_zombies]=2; MODEL[process_blocked]=3; fi
}

# ===================== 5. FORMAT AND LAYOUT ==================================
repeat_char() { printf -v REPLY '%*s' "$2" ''; REPLY=${REPLY// /$1}; }

strip_ansi() {
    REPLY=$1; local pattern=$'\033''\[[0-9;]*m'
    while [[ $REPLY =~ $pattern ]]; do REPLY=${REPLY/"${BASH_REMATCH[0]}"/}; done
}

pad_cell() {
    local text=$1 width=$2 align=${3:-left} length
    ((width>0)) || { REPLY=''; return 0; }
    strip_ansi "$text"; length=${#REPLY}
    if ((length>width)); then
        clip_sgr_cell "$text" "$width"; text=$REPLY; length=$width
    fi
    if [[ $align == right ]]; then printf -v REPLY '%*s%s' "$((width-length))" '' "$text"
    else printf -v REPLY '%s%*s' "$text" "$((width-length))" ''; fi
}

human_kib() {
    local kb=$1 div=1 suffix=Ki n
    if ((kb == 0)); then REPLY=0B; return; fi
    if ((kb >= 1073741824)); then div=1073741824; suffix=Ti
    elif ((kb >= 1048576)); then div=1048576; suffix=Gi
    elif ((kb >= 1024)); then div=1024; suffix=Mi; fi
    n=$(((kb*10+div/2)/div))
    if ((div == 1 || n >= 1000)); then printf -v REPLY '%d%s' "$((kb/div))" "$suffix"
    else printf -v REPLY '%d.%d%s' "$((n/10))" "$((n%10))" "$suffix"; fi
}

format_number() { if [[ ${1-} =~ ^[0-9]+$ ]]; then human_kib "$1"; else REPLY='?'; fi; }

line() { OUTPUT+="$1"$'\n'; }

rule_full() { ((COLS < 24)) || line "$BORDER$1$RULE_FULL$2$RST"; }


segmented_bar() {
    # Closed-form cumulative rounding: one operation per category, never per cell.
    # Arguments after total are triples: KiB, colour, plain-mode character.
    local total=$1 count=$TEXT_WIDTH sum=0 end=0 last=0 bar='' value color symbol glyph
    shift; ((total > 0 && count > 0)) || { REPLY=''; return; }
    while (($# >= 3)); do
        value=$1 color=$2 symbol=$3; shift 3
        sum=$((sum+value)); end=$(((sum*count+total/2)/total))
        ((end <= count)) || end=$count
        glyph=$GLYPH_USED
        [[ $symbol != . ]] || glyph=$GLYPH_FREE
        ((MODEL[color])) || glyph=$symbol
        repeat_char "$glyph" "$((end-last))"; bar+=$color$REPLY$RST; last=$end
    done
    REPLY=$bar
}


demo_model() {
    MODEL[host]=ws-bench-07; MODEL[domain]=workshop.example; MODEL[domain_source]='DNS search'
    MODEL[os]='Debian GNU/Linux 13 (trixie)'; MODEL[kernel]=6.12.57-amd64
    MODEL[ip_state]=ok; HOST_IPS=('eno1 192.0.2.17/24')
    MODEL[cpus]=8; MODEL[uptime]='4d 06h 12m'; MODEL[load1]=1.42; MODEL[load5]=1.18; MODEL[load15]=0.97
    MODEL[sampled]='2026-11-16 13:30:00 AEDT'
    MODEL[psi_cpu]=1.20; MODEL[psi_memory]=0.00; MODEL[psi_io]=0.15
    MODEL[oom_kills]=0; MODEL[reboot_marker]=0; MODEL[root_readonly]=0; MODEL[md_degraded]=0
    MODEL[journal_state]=ok; MODEL[journal_count]=0; MODEL[journal_capped]=0
    MODEL[mem_total]=33554432; MODEL[mem_available]=25165824
    MODEL[mem_free]=17563648; MODEL[mem_buffers]=262144
    MODEL[mem_cached]=8388608; MODEL[mem_shmem]=524288; MODEL[mem_sreclaimable]=524288
    MODEL[zram_pool_kib]=655360; MODEL[zram_original_kib]=2097152
    MODEL[zram_compressed_kib]=589824; MODEL[zram_count]=1; MODEL[zram_state]=ok
    MODEL[zswap_pool_kib]=0; MODEL[zswap_original_kib]=0; MODEL[zswap_state]=ok
    MODEL[swap_total]=8388608; MODEL[swap_free]=6291456
    MODEL[swap_zram_used]=2097152; MODEL[swap_other_used]=0; MODEL[swap_state]=ok
    MODEL[storage_state]=ok; MODEL[storage_skipped]=0; MODEL[storage_skipped_shared]=0
    DISK_IDS=(root data); local id
    DISK[root.target]=/; DISK[root.total_kib]=104857600; DISK[root.used_kib]=31457280; DISK[root.avail_kib]=68157440
    DISK[root.inodes_total]=6553600; DISK[root.inodes_free]=5898240
    DISK[data.target]=/srv/images; DISK[data.total_kib]=524288000; DISK[data.used_kib]=199229440; DISK[data.avail_kib]=325058560
    DISK[data.inodes_total]=32768000; DISK[data.inodes_free]=30474240
    for id in "${DISK_IDS[@]}"; do
        DISK[$id.fstype]=ext4
        DISK[$id.reserved_kib]=$((${DISK[$id.total_kib]}-${DISK[$id.used_kib]}-${DISK[$id.avail_kib]}))
    done
    HEALTH_NOTES=()
    if ((DEMO==2)); then
        MODEL[mem_available]=1048576; MODEL[mem_free]=524288; MODEL[mem_cached]=786432
        MODEL[mem_shmem]=262144; MODEL[mem_buffers]=65536; MODEL[mem_sreclaimable]=196608
        MODEL[reboot_marker]=1; MODEL[oom_kills]=2; MODEL[journal_count]=3
        MODEL[psi_memory]=12.25
        DISK[root.used_kib]=100663296; DISK[root.avail_kib]=2097152
        DISK[root.reserved_kib]=$((104857600-100663296-2097152))
    fi
}

# ==================== 6. BOUNDED COLLECTION AND DISK I/O =====================
# Normal collection omits installed-unit scanning and journal I/O. Explicit
# options request these providers without changing the layout or work budget.
collect_services_fast() {
    local output rc
    SVC=(); SVC_KEYS=(); SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[services_scope]=runtime
    MODEL[services_state]=unavailable
    MODEL[svc_runtime_state]=unavailable; MODEL[svc_files_state]=skipped
    if ! command -v systemctl >/dev/null 2>&1; then svc_finalize; return 0; fi
    # Include every resident type so failures of mounts/swaps still surface.
    # Installed-unit scanning is an explicitly requested acquisition policy.
    if output=$(LC_ALL=C SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 \
        run_bounded "${SERVICE_TIMEOUT:-0.10s}" systemctl --no-ask-password --no-pager \
        --no-legend --plain --full list-units --all 2>/dev/null); then
        MODEL[svc_runtime_state]=ok
        MODEL[services_state]=ok
        svc_parse_runtime "$output"
    else
        rc=$?
        if ((rc==124 || rc==137)); then
            MODEL[svc_runtime_state]=timeout; MODEL[services_state]=timeout
        elif ((rc==125)); then
            MODEL[svc_runtime_state]=budget; MODEL[services_state]=budget
        fi
    fi
    svc_finalize
}


# Kernel storage attribution, not file-space use or raw syscall byte counts.
# read_bytes/write_bytes include waited-for children. Never sum these rows as a
# host-wide total, or subtract cancelled writes as if that were physical traffic.
declare -A IO_PROC=() IO_DEV=() IO_BASE_PROC=() IO_BASE_DEV=()
IO_TOP_IDS=() IO_DEV_IDS=() IO_SCAN_IDS=()
IO_HAVE_BASE=0

io_now_us() {
    local value=${EPOCHREALTIME-} whole frac ignored
    if [[ $value =~ ^([0-9]{1,12})\.([0-9]{1,6})$ ]]; then
        whole=${BASH_REMATCH[1]}; frac=${BASH_REMATCH[2]}000000; frac=${frac:0:6}
        REPLY=$((10#$whole*1000000+10#$frac)); return 0
    fi
    io_monotonic_us
}
io_monotonic_us() {
    local value whole frac ignored
    # Bash 4.3 has no EPOCHREALTIME. /proc/uptime gives a monotonic centisecond
    # fallback without launching date; sub-20ms intervals remain unavailable.
    if { read -r value ignored <"$PROC_ROOT/uptime"; } 2>/dev/null &&
       [[ $value =~ ^([0-9]{1,12})\.([0-9]{1,6})$ ]]; then
        whole=${BASH_REMATCH[1]}; frac=${BASH_REMATCH[2]}000000; frac=${frac:0:6}
        REPLY=$((10#$whole*1000000+10#$frac)); return 0
    fi
    REPLY=''; return 1
}
io_uint() {
    [[ -n $1 && ${#1} -le 18 && $1 != *[!0123456789]* ]] || return 1
    REPLY=$((10#$1))
}
io_rate_kib() {
    # bytes/usec * 1e6/1024 = bytes/usec * 15625/16; split the quotient
    # before multiplying to avoid overflow on large cumulative counters.
    local bytes=$1 us=$2
    REPLY=$(( ((bytes/us)*15625 + (bytes%us)*15625/us) / 16 ))
}
io_amount() { human_kib "$(( $1 / 1024 ))"; }
io_pid_stat() {
    local pid=$1 raw tail
    local -a fields=()
    IO_STAT_START=''; IO_STAT_NAME=''
    { IFS= read -r raw <"$PROC_ROOT/$pid/stat"; } 2>/dev/null || return 1
    [[ $raw == "$pid ("* && $raw == *') '* ]] || return 1
    tail=${raw##*) }; read -r -a fields <<<"$tail"
    ((${#fields[@]}>=20)) && io_uint "${fields[19]}" || return 1
    IO_STAT_START=$REPLY
    raw=${raw#*'('}; IO_STAT_NAME=${raw%') '*}
}
io_read_pid() {
    local pid=$1 target=$2 key value extra start name r='' w='' c='' stamp
    local -n out=$target
    io_pid_stat "$pid" || return 2
    start=$IO_STAT_START; name=$IO_STAT_NAME
    if ! {
        while read -r key value extra; do
            case $key in
                read_bytes:) io_uint "$value" && r=$REPLY ;;
                write_bytes:) io_uint "$value" && w=$REPLY ;;
                cancelled_write_bytes:) io_uint "$value" && c=$REPLY ;;
            esac
        done <"$PROC_ROOT/$pid/io"
    } 2>/dev/null; then return 1; fi
    [[ -n $r && -n $w && -n $c ]] || return 1
    io_now_us; stamp=$REPLY
    io_pid_stat "$pid" || return 2
    [[ $IO_STAT_START == "$start" ]] || return 2
    safe_text "$name"
    out[$pid.name]=$REPLY; out[$pid.starttime]=$start; out[$pid.stamp_us]=$stamp
    out[$pid.read_bytes]=$r; out[$pid.write_bytes]=$w; out[$pid.cancelled_bytes]=$c
}
io_scan_processes() {
    local target=$1 path pid begin='' now='' rc i=0
    local -n out=$target
    local -a paths=()
    out=(); IO_SCAN_IDS=()
    MODEL[io_candidates]=0; MODEL[io_examined]=0; MODEL[io_readable]=0
    MODEL[io_denied]=0; MODEL[io_gone]=0; MODEL[io_capped]=0
    MODEL[io_state]=unavailable
    [[ -d $PROC_ROOT && -r $PROC_ROOT ]] || return 0
    paths=("$PROC_ROOT"/[0-9]*)
    if [[ ! -d ${paths[0]} ]]; then paths=(); fi
    MODEL[io_candidates]=${#paths[@]}
    io_now_us && begin=$REPLY
    for path in "${paths[@]}"; do
        ((i<IO_PROCESS_LIMIT)) || { MODEL[io_capped]=1; break; }
        if ((i%8==0)) && [[ -n $begin ]]; then
            io_now_us; now=$REPLY
            if [[ -n $now ]] && ((now-begin>=IO_SCAN_BUDGET_MS*1000)); then MODEL[io_capped]=1; break; fi
        fi
        pid=${path##*/}; [[ $pid =~ ^[0-9]+$ ]] || continue
        ((i+=1)); MODEL[io_examined]=$i
        [[ $pid != "$$" ]] || continue
        io_read_pid "$pid" "$target"; rc=$?
        case $rc in
            0) IO_SCAN_IDS+=("$pid"); ((MODEL[io_readable]+=1)) ;;
            1) ((MODEL[io_denied]+=1)) ;;
            *) ((MODEL[io_gone]+=1)) ;;
        esac
    done
    if ((MODEL[io_readable]>0)); then
        MODEL[io_state]=ok
        ((MODEL[io_denied]+MODEL[io_gone]+MODEL[io_capped]==0)) || MODEL[io_state]=partial
    elif ((MODEL[io_capped])); then MODEL[io_state]=budget; fi
}
io_scan_devices() {
    local target=$1 major minor name rd rm rs rt wd wm ws wt inflight busy weighted rest
    local slave leaf seq stamp count=0 rbytes wbytes
    local -n out=$target
    out=(); IO_DEV_IDS=(); MODEL[diskstats_state]=unavailable
    MODEL[disk_inflight]=0; MODEL[disk_device_count]=0; MODEL[diskstats_capped]=0
    [[ -r $PROC_ROOT/diskstats && -d $SYS_ROOT/block && -r $SYS_ROOT/block ]] || return 0
    MODEL[diskstats_state]=ok; io_now_us; stamp=$REPLY
    while read -r major minor name rd rm rs rt wd wm ws wt inflight busy weighted rest; do
        [[ -n $name && -d $SYS_ROOT/block/$name ]] || continue  # No partitions.
        case $name in loop*|ram*|zram*|dm-*|md*) continue ;; esac
        # Whole leaf block devices only: avoid summing a virtual stack and its
        # backing disks. Device totals are scoped; they are not all hardware I/O.
        [[ -e $SYS_ROOT/block/$name/device ]] || continue
        leaf=1
        for slave in "$SYS_ROOT/block/$name/slaves/"*; do [[ ! -e $slave ]] || { leaf=0; break; }; done
        ((leaf)) || continue
        ((count<IO_DEVICE_LIMIT)) || { MODEL[diskstats_capped]=1; MODEL[diskstats_state]=partial; break; }
        io_uint "$rs" || { MODEL[diskstats_state]=partial; continue; }; rs=$REPLY
        io_uint "$ws" || { MODEL[diskstats_state]=partial; continue; }; ws=$REPLY
        io_uint "$inflight" || { MODEL[diskstats_state]=partial; continue; }; inflight=$REPLY
        # Kernel sectors are 512 bytes, independently of hardware sector size.
        ((rs<=18000000000000000 && ws<=18000000000000000 && inflight<=1000000000)) || { MODEL[diskstats_state]=partial; continue; }
        rbytes=$((rs*512)); wbytes=$((ws*512))
        seq=''
        { read -r seq <"$SYS_ROOT/block/$name/diskseq"; } 2>/dev/null || seq=''
        [[ -z $seq ]] || io_uint "$seq" || seq=''
        IO_DEV_IDS+=("$name"); ((count+=1))
        out[$name.read_bytes]=$rbytes; out[$name.write_bytes]=$wbytes
        out[$name.inflight]=$inflight; out[$name.stamp_us]=$stamp
        out[$name.identity]="$major:$minor:$seq"; out[$name.diskseq]=$seq
        MODEL[disk_inflight]=$((MODEL[disk_inflight]+inflight))
    done 2>/dev/null <"$PROC_ROOT/diskstats"
    MODEL[disk_device_count]=$count
}
io_top_insert() {
    local pid=$1 score=$2 i j other
    for ((i=0;i<${#IO_TOP_IDS[@]};i++)); do
        other=${IO_TOP_IDS[i]}; ((score>${IO_PROC[$other.score]:-0})) && break
    done
    ((i<IO_TOP_N)) || return 0
    for ((j=${#IO_TOP_IDS[@]};j>i;j--)); do ((j>=IO_TOP_N)) || IO_TOP_IDS[j]=${IO_TOP_IDS[j-1]}; done
    IO_TOP_IDS[i]=$pid
}
io_derive() {
    local pid dev elapsed r w stamp old paired=0 shortest=0 longest=0
    IO_TOP_IDS=(); MODEL[io_basis]=lifetime; MODEL[io_interval_ms]=0
    MODEL[io_interval_min_ms]=0; MODEL[io_interval_max_ms]=0
    MODEL[io_unpaired]=0; MODEL[io_reset]=0; MODEL[diskstats_basis]=lifetime
    for pid in "${IO_SCAN_IDS[@]}"; do
        IO_PROC[$pid.score]=$((${IO_PROC[$pid.read_bytes]}+${IO_PROC[$pid.write_bytes]}))
        IO_PROC[$pid.read_kib_s]=''; IO_PROC[$pid.write_kib_s]=''
        ((IO_HAVE_BASE)) || continue
        if [[ ${IO_BASE_PROC[$pid.starttime]-} != "${IO_PROC[$pid.starttime]}" || -z ${IO_BASE_PROC[$pid.stamp_us]-} || -z ${IO_PROC[$pid.stamp_us]-} ]]; then
            ((MODEL[io_unpaired]+=1)); continue
        fi
        elapsed=$((${IO_PROC[$pid.stamp_us]}-${IO_BASE_PROC[$pid.stamp_us]}))
        ((elapsed>=IO_MIN_SAMPLE_MS*1000 && elapsed<=IO_MAX_SAMPLE_MS*1000)) || { ((MODEL[io_unpaired]+=1)); continue; }
        r=$((${IO_PROC[$pid.read_bytes]}-${IO_BASE_PROC[$pid.read_bytes]}))
        w=$((${IO_PROC[$pid.write_bytes]}-${IO_BASE_PROC[$pid.write_bytes]}))
        if ((r<0 || w<0)); then ((MODEL[io_reset]+=1)); continue; fi
        io_rate_kib "$r" "$elapsed"; IO_PROC[$pid.read_kib_s]=$REPLY
        io_rate_kib "$w" "$elapsed"; IO_PROC[$pid.write_kib_s]=$REPLY
        IO_PROC[$pid.interval_ms]=$((elapsed/1000))
        ((paired+=1))
        ((shortest!=0 && elapsed>=shortest)) || shortest=$elapsed
        ((elapsed<=longest)) || longest=$elapsed
    done
    if ((paired>0)); then
        MODEL[io_basis]=interval; MODEL[io_interval_min_ms]=$((shortest/1000)); MODEL[io_interval_max_ms]=$((longest/1000))
        MODEL[io_interval_ms]=$(((shortest+longest)/2000))
    fi
    for pid in "${IO_SCAN_IDS[@]}"; do
        if [[ ${MODEL[io_basis]} == interval ]]; then
            [[ -n ${IO_PROC[$pid.read_kib_s]} && -n ${IO_PROC[$pid.write_kib_s]} ]] || continue
            IO_PROC[$pid.score]=$((${IO_PROC[$pid.read_kib_s]}+${IO_PROC[$pid.write_kib_s]}))
        fi
        io_top_insert "$pid" "${IO_PROC[$pid.score]}"
    done
    MODEL[io_rate_processes]=$paired
    if ((MODEL[io_reset]>0)) || { [[ ${MODEL[io_basis]} == interval ]] && ((MODEL[io_unpaired]>0)); }; then MODEL[io_state]=partial; fi
    for dev in "${IO_DEV_IDS[@]}"; do
        IO_DEV[$dev.read_kib_s]=''; IO_DEV[$dev.write_kib_s]=''
        ((IO_HAVE_BASE)) || continue
        # diskseq detects hot-unplug/replacement even if the name/devt is reused.
        [[ -n ${IO_DEV[$dev.diskseq]} && ${IO_DEV[$dev.identity]} == "${IO_BASE_DEV[$dev.identity]-}" && -n ${IO_BASE_DEV[$dev.stamp_us]-} && -n ${IO_DEV[$dev.stamp_us]-} ]] || continue
        elapsed=$((${IO_DEV[$dev.stamp_us]}-${IO_BASE_DEV[$dev.stamp_us]}))
        ((elapsed>=IO_MIN_SAMPLE_MS*1000 && elapsed<=IO_MAX_SAMPLE_MS*1000)) || continue
        r=$((${IO_DEV[$dev.read_bytes]}-${IO_BASE_DEV[$dev.read_bytes]})); w=$((${IO_DEV[$dev.write_bytes]}-${IO_BASE_DEV[$dev.write_bytes]}))
        ((r>=0 && w>=0)) || continue
        io_rate_kib "$r" "$elapsed"; IO_DEV[$dev.read_kib_s]=$REPLY
        io_rate_kib "$w" "$elapsed"; IO_DEV[$dev.write_kib_s]=$REPLY
        MODEL[diskstats_basis]=interval
    done
}
io_begin() {
    IO_HAVE_BASE=0; IO_BASE_PROC=(); IO_BASE_DEV=()
    MODEL[io_clock_discontinuity]=0
    io_now_us; IO_BEGIN_CLOCK_US=$REPLY
    io_monotonic_us; IO_BEGIN_MONO_US=$REPLY
    io_scan_devices IO_BASE_DEV
    io_scan_processes IO_BASE_PROC
    IO_HAVE_BASE=1
}
io_finish() {
    io_scan_devices IO_DEV
    io_scan_processes IO_PROC
    # Detect a wall-clock step during collection before trusting a short rate.
    # /proc/uptime quantization allows a 30ms difference between elapsed clocks.
    local end_clock end_mono divergence
    io_now_us; end_clock=$REPLY; io_monotonic_us; end_mono=$REPLY
    if ((IO_HAVE_BASE)) && [[ -n ${IO_BEGIN_CLOCK_US:-} && -n ${IO_BEGIN_MONO_US:-} && -n $end_clock && -n $end_mono ]]; then
        divergence=$(( (end_clock-IO_BEGIN_CLOCK_US)-(end_mono-IO_BEGIN_MONO_US) ))
        if ((divergence>30000 || divergence < -30000)); then
            IO_HAVE_BASE=0; MODEL[io_clock_discontinuity]=1
        fi
    fi
    io_derive
}
collect_io() {
    # One-shot fallback. The caller may instead bracket normal work with
    # io_begin / io_finish to obtain a short measured interval, with no sleep.
    IO_HAVE_BASE=0; io_finish
}


io_attention() {
    if ((${MODEL[io_clock_discontinuity]:-0})); then
        ATTENTION+=('INFO|Clock changed during I/O sampling; cumulative totals shown.')
    fi
    case ${MODEL[io_state]-unavailable} in
        ok) ;;
        partial) ATTENTION+=('INFO|Process I/O is partial; rankings cover readable, identity-checked tasks.') ;;
        budget) ATTENTION+=('INFO|Process I/O budget exhausted; no usable task rows collected.') ;;
        *) ATTENTION+=('INFO|Process I/O counters unavailable; permissions may restrict visibility.') ;;
    esac
}
demo_io() {
    IO_PROC=(); IO_DEV=(); IO_TOP_IDS=(2418 4301 1632); IO_DEV_IDS=(sdb sdc)
    MODEL[io_state]=ok; MODEL[io_basis]=interval; MODEL[io_interval_ms]=42
    MODEL[io_interval_min_ms]=40; MODEL[io_interval_max_ms]=44
    MODEL[io_candidates]=184; MODEL[io_examined]=184; MODEL[io_readable]=184
    MODEL[io_denied]=0; MODEL[io_gone]=0; MODEL[io_capped]=0; MODEL[io_rate_processes]=184
    local pid name r w total
    while read -r pid name r w total; do
        IO_PROC[$pid.name]=$name; IO_PROC[$pid.read_kib_s]=$r; IO_PROC[$pid.write_kib_s]=$w
        IO_PROC[$pid.read_bytes]=$total; IO_PROC[$pid.write_bytes]=$total
        IO_PROC[$pid.cancelled_bytes]=0; IO_PROC[$pid.score]=$((r+w)); IO_PROC[$pid.starttime]=100
    done <<'IO_DEMO'
2418 badblocks 185344 0 214748364800
4301 fio 4096 120832 107374182400
1632 postgres 128 512 4294967296
IO_DEMO
    while ((${#IO_TOP_IDS[@]}>IO_TOP_N)); do unset 'IO_TOP_IDS[${#IO_TOP_IDS[@]}-1]'; done
    MODEL[diskstats_state]=ok; MODEL[diskstats_basis]=interval; MODEL[disk_inflight]=4; MODEL[disk_device_count]=2
    IO_DEV[sdb.inflight]=1; IO_DEV[sdb.read_kib_s]=185344; IO_DEV[sdb.write_kib_s]=0
    IO_DEV[sdc.inflight]=3; IO_DEV[sdc.read_kib_s]=4096; IO_DEV[sdc.write_kib_s]=120832
    for name in sdb sdc; do IO_DEV[$name.read_bytes]=214748364800; IO_DEV[$name.write_bytes]=107374182400; done
}


# This renderer consumes the validated collection model.
# It never collects, samples, sleeps, executes a hint, or queries a service.
# Fixed-height rows deliberately truncate long display values with an ellipsis.
# Counts, explicit missing states and adjustable rows preserve reviewability.


# ==================== 7. SHARED DISPLAY COMPONENTS ==========================
# Shared presentation primitives and section callbacks.
# Every callback accepts a maximum row count, INCLUDING its titled divider.
# The dispatcher owns section order/visibility and assigns each row budget.
# These functions consume the validated model; they never collect or execute hints.
UI_REMAIN=0 UI_EMITTED=0 UI_SECTION_ID=''
UI_SEPARATOR=' | '
declare -a UI_COL_WIDTHS UI_CELLS

ui_enabled() { ui_item_enabled "$1" "$2"; }

ui_colour() { REPLY=${COLOR[$1]:-${COLOR[$2]:-}}; }
ui_plain_cell() {
    local value=$1 width=$2 colour=${3-} align=${4-left}
    safe_text "$value"; value=$REPLY
    if ((${#value}>width)); then
        if ((width>=3)); then value=${value:0:width-3}'...'; else value=${value:0:width}; fi
    fi
    if [[ $align == right ]]; then printf -v REPLY '%*s%s' "$((width-${#value}))" '' "$value"
    else printf -v REPLY '%s%*s' "$value" "$((width-${#value}))" ''; fi
    REPLY=$colour$REPLY$RST
}
ui_value_cell() {
    # Label and numeric/state value align independently; clipping precedes colour.
    local width=$1 label=$2 value=$3 shade=${4-} label_width
    safe_text "$value"; value=$REPLY
    ((width>${#value})) || { ui_plain_cell "$value" "$width" "$shade" right; return; }
    label_width=$((width-${#value}-1))
    ui_plain_cell "$label" "$label_width" "${COLOR[label]:-${COLOR[text]}}"
    REPLY="$REPLY $shade$value$RST"
}
ui_emit() {
    ((UI_REMAIN>0)) || return 0
    line "$BORDER$V$RST $1 $BORDER$V$RST"
    ((UI_REMAIN-=1)); ((UI_EMITTED+=1)); return 0
}
ui_row() {
    ((UI_REMAIN>0)) || return 0
    ui_plain_cell "$1" "$TEXT_WIDTH" "${2-${COLOR[text]}}"
    ui_emit "$REPLY"
}
ui_rich_row() {
    ((UI_REMAIN>0)) || return 0
    pad_cell "$1" "$TEXT_WIDTH"; ui_emit "$REPLY"
}
ui_text() {
    local text=$1 shade=${2-${COLOR[text]}} part cut
    safe_text "$text"; text=$REPLY
    while [[ -n $text ]] && ((UI_REMAIN>0)); do
        if ((${#text}<=TEXT_WIDTH)); then ui_row "$text" "$shade"; break; fi
        part=${text:0:TEXT_WIDTH}; cut=${part% *}
        [[ -n $cut && $cut != "$part" ]] || cut=$part
        ui_row "$cut" "$shade"; text=${text:${#cut}}; text=${text# }
    done
}
ui_rule() {
    local title=$1 summary=${2-} left=${3-$LEFT} right=${4-$RIGHT} colour=${5-${COLOR[muted]}}
    local room=$((INNER-4)) tail='' title_room fill
    safe_text "$title"; title=$REPLY; safe_text "$summary"; summary=$REPLY
    # Keep the section title recognizable and let the right summary use spare width.
    title_room=$((room/2)); ((${#title}<=title_room)) || title=${title:0:title_room-3}'...'
    room=$((room-${#title}))
    if [[ -n $summary ]] && ((room>4)); then
        ((room>=${#summary}+2)) || summary=${summary:0:room-5}'...'
        tail=" $colour$summary$RST"; room=$((room-${#summary}-1))
    fi
    repeat_char "$H" "$((room>0 ? room : 0))"; fill=$REPLY
    line "$BORDER$left$H$RST ${COLOR[heading]}$title$RST $BORDER$fill$RST$tail $BORDER$right$RST"
}
ui_heading() {
    ((UI_REMAIN>0)) || return 0
    ui_rule "$1" "${2-}" "$LEFT" "$RIGHT" "${3-${COLOR[muted]}}"
    ((UI_REMAIN-=1)); ((UI_EMITTED+=1)); return 0
}
ui_begin() {
    UI_SECTION_ID=$1; UI_REMAIN=${2:-0}; UI_EMITTED=0
    local title=${UI_SECTION_TITLE:-${SECTION_TITLE[$1]:-$1}}
    ui_heading "$title" "${3-}" "${4-${COLOR[muted]}}"
}
ui_top() {
    local host=${MODEL[host]:-?} clock=${MODEL[sampled]-} title=''
    ui_enabled header title && title=$TITLE
    clock=${clock#* }; clock=${clock%% *}
    [[ $clock != "${MODEL[sampled]-}" ]] || clock=''
    if ui_enabled system identity && ui_enabled header host; then
        if ((TEXT_WIDTH>=60)); then title+="${title:+ | }$host"; else title="$host${title:+ | $title}"; fi
    fi
    if ui_enabled header site && [[ -n $SITE_LABEL && $SITE_LABEL != Workshop ]]; then title+="${title:+ | }$SITE_LABEL"; fi
    ui_enabled header time || clock=''
    ((DEMO==0)) || clock="DEMO $clock"
    ui_rule "$title" "$clock" "$TL" "$TR"
}
ui_bottom() { rule_full "$BL" "$BR"; }
ui_columns() {
    local count=$1 i width available
    UI_COL_WIDTHS=(); UI_CELLS=()
    UI_SEPARATOR=' | '; ((${MODEL[unicode]:-0}==0)) || UI_SEPARATOR=' │ '
    available=$((TEXT_WIDTH-3*(count-1))); width=$((available/count))
    for ((i=0;i<count;i++)); do
        UI_COL_WIDTHS+=("$width"); ((i!=count-1)) || UI_COL_WIDTHS[i]=$((available-width*(count-1)))
    done
}
ui_grid() {
    local cell row='' i=0
    for cell in "${UI_CELLS[@]}"; do
        ((i==0)) || row+="${COLOR[muted]}$UI_SEPARATOR$RST"
        row+=$cell; ((i+=1))
    done
    ui_emit "$row"
}
ui_system() {
    local budget=$1 summary='' ip=${MODEL[ip_state]:-unknown} os=${MODEL[os]:-Linux} row='' item shown=0 room domain
    ui_enabled system identity && summary="up ${MODEL[uptime]:-?}"
    ui_begin system "$budget" "$summary"
    if [[ $MODE == verbose ]]; then
        ui_enabled system identity && ui_row "Host ${MODEL[host]:-?}  |  Site $SITE_LABEL"
        ui_enabled system domain && ui_row "Domain ${MODEL[domain]:-?} (${MODEL[domain_source]:-local configuration})"
        ui_enabled system platform && { ui_row "OS     ${MODEL[os]:-Linux}"; ui_row "Kernel ${MODEL[kernel]:-?}"; }
        if ui_enabled system addresses; then
            if ((${#HOST_IPS[@]})); then
                for item in "${HOST_IPS[@]}"; do ((shown<MAX_IPS)) || break; ui_row "IP     $item"; ((shown+=1)); done
                ((${#HOST_IPS[@]}<=shown)) || ui_row "$(( ${#HOST_IPS[@]}-shown )) additional address(es) not shown." "${COLOR[muted]}"
            else ui_row "IP     ${MODEL[ip_state]:-unavailable}" "${COLOR[muted]}"; fi
        fi
        ui_enabled system load && ui_row "CPU ${MODEL[cpus]:-?}  |  Load ${MODEL[load1]:-?} / ${MODEL[load5]:-?} / ${MODEL[load15]:-?} (1/5/15m)"
        ui_enabled system pressure && ui_row "Stall avg10: CPU ${MODEL[psi_cpu]:-?}%  RAM ${MODEL[psi_memory]:-?}%  I/O ${MODEL[psi_io]:-?}%"
        ui_row "Sample ${MODEL[sampled]:-?}" "${COLOR[muted]}"
        return
    fi
    ((${#HOST_IPS[@]}==0)) || ip=${HOST_IPS[0]}
    if ((TEXT_WIDTH>=60)); then
        ui_columns 2
        if ui_enabled system domain; then ui_plain_cell "Domain ${MODEL[domain]:-?}" "${UI_COL_WIDTHS[0]}" "${COLOR[label]:-${COLOR[text]}}"; UI_CELLS+=("$REPLY"); else ui_plain_cell '' "${UI_COL_WIDTHS[0]}"; UI_CELLS+=("$REPLY"); fi
        if ui_enabled system addresses; then ui_plain_cell "IP $ip" "${UI_COL_WIDTHS[1]}" "${COLOR[value]:-${COLOR[text]}}"; UI_CELLS+=("$REPLY"); else ui_plain_cell '' "${UI_COL_WIDTHS[1]}"; UI_CELLS+=("$REPLY"); fi
        ui_grid
        if ui_enabled system platform; then
            ui_columns 2; ui_plain_cell "$os" "${UI_COL_WIDTHS[0]}"; UI_CELLS+=("$REPLY")
            ui_plain_cell "Kernel ${MODEL[kernel]:-?}" "${UI_COL_WIDTHS[1]}"; UI_CELLS+=("$REPLY"); ui_grid
        fi
        if ((UI_REMAIN>0)) && ui_enabled system load; then ui_row "CPU ${MODEL[cpus]:-?} | load ${MODEL[load1]:-?}/${MODEL[load5]:-?}/${MODEL[load15]:-?}"; fi
    else
        if ((UI_REMAIN==1)) && ui_enabled system addresses; then
            row="IP $ip"; room=$((TEXT_WIDTH-${#row}-3))
            if ((room>=8)) && ui_enabled system domain; then
                safe_text "${MODEL[domain]:-?}"; domain=$REPLY
                ((${#domain}<=room)) || domain=${domain:0:room-3}'...'
                row+=" | $domain"
            fi
            ui_row "$row"
        else
            ui_enabled system domain && ui_row "Domain ${MODEL[domain]:-?}"
            ui_enabled system addresses && ui_row "IP $ip"
            ui_enabled system platform && ui_row "$os | ${MODEL[kernel]:-?}"
        fi
    fi
    if ((UI_REMAIN>0)) && ui_enabled system pressure; then ui_row "Stall: CPU ${MODEL[psi_cpu]:-?}% RAM ${MODEL[psi_memory]:-?}% I/O ${MODEL[psi_io]:-?}%"; fi
}
ui_small_bar() { local TEXT_WIDTH=$1; shift; segmented_bar "$@"; }
ui_memory_bar() {
    local width=$1 other=${MODEL[mem_other]:-0}
    UI_MEMORY_OTHER=$other; REPLY=''
    if ((${MODEL[mem_parts_valid]:-0})); then
        if ui_enabled resources compression; then
            ui_small_bar "$width" "${MODEL[mem_total]}" "$other" "${COLOR[other]}" O "${MODEL[mem_cache]}" "${COLOR[cache]}" C "${MODEL[mem_compressed]}" "${COLOR[compressed]}" Z "${MODEL[mem_free]}" "${COLOR[free]}" .
        else
            UI_MEMORY_OTHER=$((other+${MODEL[mem_compressed]:-0}))
            ui_small_bar "$width" "${MODEL[mem_total]}" "$UI_MEMORY_OTHER" "${COLOR[other]}" O "${MODEL[mem_cache]}" "${COLOR[cache]}" C "${MODEL[mem_free]}" "${COLOR[free]}" .
        fi
    elif ((${MODEL[mem_valid]:-0})); then
        ui_small_bar "$width" "${MODEL[mem_total]}" "${MODEL[mem_used]}" "${COLOR[other]}" U "${MODEL[mem_available]}" "${COLOR[free]}" .
    fi
}
ui_storage_bar() {
    local width=$1 id index=0 symbol
    local -a parts=()
    REPLY=''
    [[ ${MODEL[storage_state]-} == ok ]] && ((${MODEL[storage_total]:-0}>0)) || return
    for id in "${DISK_IDS[@]}"; do
        symbol=$((index%9+1)); ((index+=1))
        parts+=("${DISK[$id.used_kib]}" "${VIEW[$id.color]}" "$symbol")
    done
    parts+=("${MODEL[storage_reserved]}" "${COLOR[reserved]}" R "${MODEL[storage_avail]}" "${COLOR[free]}" .)
    ui_small_bar "$width" "${MODEL[storage_total]}" "${parts[@]}"
}
ui_memory_details() {
    local row other
    ui_row MEMORY "${COLOR[heading]}"
    ui_row "Total ${VIEW[mem_total]:-?} | available ${VIEW[mem_available]:-?} | used ${VIEW[mem_percent]:-?}%"
    ui_memory_bar "$TEXT_WIDTH"; ui_rich_row "$REPLY"
    if ((${MODEL[mem_parts_valid]:-0})); then
        human_kib "$UI_MEMORY_OTHER"; other=$REPLY
        row="${COLOR[other]}Other $other$RST | ${COLOR[cache]}Cache ${VIEW[mem_cache]:-?}$RST"
        ui_enabled resources compression && row+=" | ${COLOR[compressed]}Comp ${VIEW[mem_compressed]:-?}$RST"
        row+=" | Free ${VIEW[mem_free]:-?}"
        if ((TEXT_WIDTH>=60)); then ui_rich_row "$row"
        else ui_row "Other $other | Cache ${VIEW[mem_cache]:-?}"; ui_enabled resources compression && ui_row "Comp ${VIEW[mem_compressed]:-?} | Free ${VIEW[mem_free]:-?}"; fi
    else ui_row 'Bar uses available/unavailable RAM.' "${COLOR[muted]}"; fi
}
ui_compression_details() {
    if ((${MODEL[zram_count]:-0}>0)); then ui_row "Zram ${VIEW[zram_original_kib]:-?} data | ${VIEW[zram_pool_kib]:-?} RAM pool" "${COLOR[compressed]}"; fi
    if ((${MODEL[zswap_pool_kib]:-0}>0)) || [[ ${MODEL[zswap_state]-} != ok && ${MODEL[zswap_state]-} != absent ]]; then
        ui_row "Zswap ${VIEW[zswap_original_kib]:-?} data | ${VIEW[zswap_pool_kib]:-?} RAM pool" "${COLOR[compressed]}"
    fi
}
ui_swap_details() {
    local bar
    ui_row SWAP "${COLOR[heading]}"
    if ((${MODEL[swap_valid]:-0}==0)); then ui_row 'Swap unavailable.' "${COLOR[muted]}"; return; fi
    if ((${MODEL[swap_total]:-0}==0)); then ui_row 'Swap not configured.' "${COLOR[muted]}"; return; fi
    ui_row "Used ${VIEW[swap_used]} / ${VIEW[swap_total]} | free ${VIEW[swap_free]}"
    if ui_enabled resources compression && [[ ${MODEL[swap_state]-} == ok ]] && ((${MODEL[swap_zram_used]:-0}+${MODEL[swap_other_used]:-0}==${MODEL[swap_used]:-0})); then
        ui_small_bar "$TEXT_WIDTH" "${MODEL[swap_total]}" "${MODEL[swap_zram_used]}" "${COLOR[compressed]}" Z "${MODEL[swap_other_used]}" "${COLOR[other]}" O "${MODEL[swap_free]}" "${COLOR[free]}" .
        ui_rich_row "$REPLY"; ui_row "Zram ${VIEW[swap_zram_used]} | other swap ${VIEW[swap_other_used]}" "${COLOR[muted]}"
    else
        ui_small_bar "$TEXT_WIDTH" "${MODEL[swap_total]}" "${MODEL[swap_used]}" "${COLOR[other]}" U "${MODEL[swap_free]}" "${COLOR[free]}" .
        ui_rich_row "$REPLY"
    fi
}
ui_storage_details() {
    local id shown=0 denom percent inode
    ui_row STORAGE "${COLOR[heading]}"
    if [[ ${MODEL[storage_state]-} == ok ]] && ((${MODEL[storage_total]:-0}>0)); then
        ui_row "Used ${VIEW[storage_used]} / ${VIEW[storage_total]} | available ${VIEW[storage_avail]}"
        ui_storage_bar "$TEXT_WIDTH"; ui_rich_row "$REPLY"
        ui_row "Reserved ${VIEW[storage_reserved]} | available ${VIEW[storage_avail]}" "${COLOR[muted]}"
    else ui_row "Storage ${MODEL[storage_state]:-unavailable}" "${COLOR[muted]}"; fi
    ui_enabled resources filesystem_detail || return
    for id in "${DISK_IDS[@]}"; do
        ((shown<MAX_DISK_DETAILS)) || break; ((shown+=1))
        denom=$((${DISK[$id.used_kib]}+${DISK[$id.avail_kib]})); percent='?'; inode=''
        ((denom<=0)) || percent=$((${DISK[$id.used_kib]}*100/denom))
        if ((${DISK[$id.inodes_total]:-0}>0)); then inode=" | inodes $((100-100*${DISK[$id.inodes_free]}/${DISK[$id.inodes_total]}))%"; fi
        human_kib "${DISK[$id.avail_kib]}"; ui_text "$shown:${VIEW[$id.target]} $percent% used | $REPLY available$inode" "${VIEW[$id.color]}"
    done
    ((${#DISK_IDS[@]}<=shown)) || ui_row "$(( ${#DISK_IDS[@]}-shown )) additional filesystem(s) not shown." "${COLOR[muted]}"
}

ui_storage_worst() {
    UI_WORST='' UI_WORST_PCT=-1
    local id denominator percent
    for id in "${DISK_IDS[@]}"; do
        denominator=$((${DISK[$id.used_kib]}+${DISK[$id.avail_kib]})); ((denominator>0)) || continue
        percent=$((${DISK[$id.used_kib]}*100/denominator))
        if ((percent>UI_WORST_PCT)); then UI_WORST=$id; UI_WORST_PCT=$percent; fi
    done
}
ui_resources() {
    local budget=$1 summary='' bar='' width=18 row='' value tail='' id inode='' shade=${COLOR[muted]} comp_label=Comp swap_label=Swap
    ui_storage_worst
    if [[ -n $UI_WORST ]] && ui_enabled resources storage && ui_enabled resources filesystem_detail; then
        summary="Max FS $UI_WORST_PCT%"
        ((UI_WORST_PCT<DISK_WARN)) || shade=${COLOR[warn]}
        ((UI_WORST_PCT<DISK_CRITICAL)) || shade=${COLOR[error]}
    fi
    ui_begin resources "$budget" "$summary" "$shade"
    if [[ $MODE == verbose ]]; then
        ui_enabled resources memory && ui_memory_details
        ui_enabled resources compression && ui_compression_details
        ui_enabled resources swap && ui_swap_details
        ui_enabled resources storage && ui_storage_details
        return
    fi
    ((TEXT_WIDTH>=60)) || width=8
    if ui_enabled resources memory; then
        ui_memory_bar "$width"; bar=$REPLY
        ui_plain_cell RAM 5 "${COLOR[heading]}"; row=$REPLY
        ui_plain_cell "${VIEW[mem_used]:-?}/${VIEW[mem_total]:-?}" 15 "${COLOR[value]:-${COLOR[text]}}"; row+="$REPLY $bar"
        ((TEXT_WIDTH<60)) || row+="  avail ${VIEW[mem_available]:-?}  ${VIEW[mem_percent]:-?}%"
        ui_rich_row "$row"
    fi
    if ui_enabled resources storage; then
        bar=''
        if [[ ${MODEL[storage_state]-} == ok ]] && ((${MODEL[storage_total]:-0}>0)); then
            ui_storage_bar "$width"; bar=$REPLY
            ui_plain_cell DISK 5 "${COLOR[heading]}"; row=$REPLY
            ui_plain_cell "${VIEW[storage_used]:-?}/${VIEW[storage_total]:-?}" 15 "${COLOR[value]:-${COLOR[text]}}"; row+="$REPLY $bar"
            ((TEXT_WIDTH<60)) || row+="  free ${VIEW[storage_avail]:-?}"
            ui_rich_row "$row"
        else ui_row "DISK ${MODEL[storage_state]:-unavailable}" "${COLOR[muted]}"; fi
    fi
    row=''
    if ((TEXT_WIDTH<60)); then comp_label=Z; swap_label=S; fi
    if ui_enabled resources memory; then row="${COLOR[cache]}Cache ${VIEW[mem_cache]:-?}$RST"; fi
    if ui_enabled resources compression; then row+="${row:+  }${COLOR[compressed]}$comp_label${comp_label:+ }${VIEW[mem_compressed]:-?}$RST"; fi
    if ui_enabled resources swap; then row+="${row:+  }$swap_label ${VIEW[swap_used]:-?}/${VIEW[swap_total]:-?}"; fi
    [[ -z $row ]] || ui_rich_row "$row"
    if [[ -n $UI_WORST ]] && ui_enabled resources storage && ui_enabled resources filesystem_detail; then
        id=$UI_WORST
        if ((${DISK[$id.inodes_total]:-0}>0)); then inode=" | inodes $((100-100*${DISK[$id.inodes_free]}/${DISK[$id.inodes_total]}))%"; fi
        ui_row "Fullest ${VIEW[$id.target]:-?} $UI_WORST_PCT%$inode" "$shade"
    fi
}
ui_role_state() {
    local role=$1 unit candidate='' chosen='' units=${SERVICE_ROLE_UNITS[$1]-}
    for unit in $units; do
        ui_enabled services "$unit" || continue
        [[ -n ${SVC[$unit.seen]-} ]] || continue
        [[ -n $candidate ]] || candidate=$unit
        if [[ -n ${SVC[$unit.runtime]-} && -z ${SVC[$candidate.runtime]-} ]]; then candidate=$unit; fi
        svc_state "$unit"
        if [[ $REPLY == FAIL ]]; then chosen=$unit; break; fi
        case ${SVC[$unit.active]-} in active|reloading) [[ -n $chosen ]] || chosen=$unit ;; esac
    done
    chosen=${chosen:-$candidate}; [[ -n $chosen ]] || return 1
    UI_ROLE_UNIT=$chosen; svc_state "$chosen"; UI_ROLE_STATE=$REPLY; UI_ROLE_COLOUR=$SVC_COLOR
}
ui_services() {
    local budget=$1 summary='' role count=0 columns capacity shown=0 omitted=0 state shade unit group label i flag raw
    local -a roles=() failed=() normal=() units=()
    local -A states=() colours=()
    if [[ $SERVICES_MODE == all ]]; then ui_services_inventory "$budget"; return; fi
    columns=$(((TEXT_WIDTH+3)/15)); ((columns>=1)) || columns=1
    capacity=$(((budget>0 ? budget-1 : 0)*columns))
    for role in "${SERVICE_ROLE_ORDER[@]}"; do
        ui_enabled services "$role" || continue
        ui_role_state "$role" || continue
        states[$role]=$UI_ROLE_STATE; colours[$role]=$UI_ROLE_COLOUR
        if [[ $UI_ROLE_STATE == FAIL ]]; then failed+=("$role"); else normal+=("$role"); fi
    done
    roles=("${failed[@]}" "${normal[@]}")
    if [[ ${MODEL[svc_runtime_state]-} == ok ]]; then summary="${MODEL[svc_running]:-?} run / ${MODEL[svc_loaded]:-?} load / ${MODEL[svc_failed]:-?} fail"
    else summary="${MODEL[svc_runtime_state]:-unavailable}"; fi
    omitted=$((${#roles[@]}-capacity)); ((omitted<=0)) || summary+=" +$omitted roles"
    shade=${COLOR[muted]}; ((${MODEL[svc_failed]:-0}==0)) || shade=${COLOR[error]}
    ui_enabled services summary || summary=''
    ui_begin services "$budget" "$summary" "$shade"
    if ((${#roles[@]}==0)); then ui_row 'No observed configured service roles.' "${COLOR[muted]}"; return; fi
    while ((shown<${#roles[@]} && UI_REMAIN>0)); do
        ui_columns "$columns"
        for ((i=0;i<columns;i++)); do
            role=${roles[shown]-}
            if [[ -n $role ]]; then
                label=${SERVICE_ROLE_LABEL[$role]:-$role}
                ui_value_cell "${UI_COL_WIDTHS[i]}" "$label" "${states[$role]}" "${colours[$role]}"; ((shown+=1))
            else ui_plain_cell '' "${UI_COL_WIDTHS[i]}"; fi
            UI_CELLS+=("$REPLY")
        done
        ui_grid
    done
}
ui_service_visible() {
    local unit=$1 role member
    ui_enabled services "$unit" || return 1
    for role in "${SERVICE_ROLE_ORDER[@]}"; do
        ui_enabled services "$role" && continue
        for member in ${SERVICE_ROLE_UNITS[$role]-}; do [[ $unit != "$member" ]] || return 1; done
    done
    return 0
}
ui_services_inventory() {
    local budget=$1 unit group state shade flag label i columns=2 shown=0 summary excess=0
    local -a units=() filtered=()
    summary="${MODEL[svc_running]:-?} running / ${MODEL[svc_loaded]:-?} loaded / ${MODEL[svc_failed]:-?} failed"
    ui_enabled services summary || summary=''
    ui_begin services "$budget" "$summary"
    if [[ ${MODEL[svc_runtime_state]-} != ok && ${MODEL[svc_files_state]-} != ok ]]; then ui_row 'Service inventory unavailable.' "${COLOR[muted]}"; return; fi
    if [[ $SERVICES_MODE == all ]]; then
        if ((TEXT_WIDTH>=68)); then
            UI_COL_WIDTHS=("$((TEXT_WIDTH-54))" 8 14 8 12); UI_CELLS=()
            i=0; for label in UNIT STATE ACTIVE/SUB LOAD BOOT; do ui_plain_cell "$label" "${UI_COL_WIDTHS[i]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY"); ((i+=1)); done; ui_grid
        fi
        for unit in "${SVC_KEYS[@]}"; do
            case $unit in *.service|*.socket|*.timer) ;; *) continue ;; esac
            svc_excluded "$unit" && continue
            ui_service_visible "$unit" || continue
            svc_state "$unit"; state=$REPLY; shade=$SVC_COLOR
            if ((TEXT_WIDTH>=68)); then
                UI_CELLS=(); ui_plain_cell "$unit" "${UI_COL_WIDTHS[0]}"; UI_CELLS+=("$REPLY")
                ui_plain_cell "$state" 8 "$shade"; UI_CELLS+=("$REPLY")
                ui_plain_cell "${SVC[$unit.active]:-?}/${SVC[$unit.sub]:-?}" 14; UI_CELLS+=("$REPLY")
                ui_plain_cell "${SVC[$unit.load]:-?}" 8; UI_CELLS+=("$REPLY")
                ui_plain_cell "${SVC[$unit.file]:-?}" 12; UI_CELLS+=("$REPLY"); ui_grid
                ((${#unit}<=UI_COL_WIDTHS[0])) || ui_text "  $unit" "${COLOR[muted]}"
            else ui_text "$unit" "${COLOR[heading]}"; ui_text "$state | ${SVC[$unit.active]:-?}/${SVC[$unit.sub]:-?} | ${SVC[$unit.file]:-?}" "$shade"; fi
        done
    else
        ((TEXT_WIDTH>=60)) || columns=1
        for group in "${SERVICE_GROUPS[@]}" Other; do
            units=()
            if [[ $group == Other ]]; then units=("${SVC_EXTRA[@]}")
            else while IFS= read -r unit; do [[ -z $unit ]] || units+=("$unit"); done <<<"${SVC_GROUP_MEMBERS[$group]-}"; fi
            filtered=()
            for unit in "${units[@]}"; do ui_service_visible "$unit" && filtered+=("$unit"); done
            units=("${filtered[@]}"); excess=0
            if [[ $group == Other ]] && ((${#units[@]}>SERVICE_EXTRA_LIMIT)); then
                excess=$((${#units[@]}-SERVICE_EXTRA_LIMIT)); units=("${units[@]:0:SERVICE_EXTRA_LIMIT}")
            fi
            ((${#units[@]})) || continue
            ui_row "$group" "${COLOR[heading]}"; shown=0
            while ((shown<${#units[@]} && UI_REMAIN>0)); do
                ui_columns "$columns"
                for ((i=0;i<columns;i++)); do
                    unit=${units[shown]-}
                    if [[ -n $unit ]]; then
                        svc_state "$unit"; state=$REPLY; shade=$SVC_COLOR
                        svc_file_flag "$unit"; flag=$REPLY; label=${unit%.service}
                        ui_value_cell "${UI_COL_WIDTHS[i]}" "$label" "$state/$flag" "$shade"; ((shown+=1))
                    else ui_plain_cell '' "${UI_COL_WIDTHS[i]}"; fi
                    UI_CELLS+=("$REPLY")
                done
                ui_grid
            done
            ((excess==0)) || ui_row "$excess further other units; use --services all." "${COLOR[muted]}"
        done
        ui_text 'Boot /e enabled  /d disabled  /s static  /m masked  /? unknown' "${COLOR[muted]}"
        ui_text 'RUN running; DONE exited; WAIT/LISTEN armed; STOP inactive.' "${COLOR[muted]}"
        ui_text 'UNLOADED: installed, not resident. MASK: activation blocked.' "${COLOR[muted]}"
    fi
}
ui_process_value() {
    local kind=$1 pid=$2 value total
    UI_PROCESS_LABEL=''; UI_PROCESS_VALUE='?'
    [[ -n $pid ]] || return
    if [[ $kind == io ]]; then
        UI_PROCESS_LABEL="$pid ${IO_PROC[$pid.name]:-?}"
        if [[ ${MODEL[io_basis]-} == interval ]]; then
            total=$((${IO_PROC[$pid.read_kib_s]:-0}+${IO_PROC[$pid.write_kib_s]:-0})); human_kib "$total"; UI_PROCESS_VALUE=$REPLY/s
        else
            total=$((${IO_PROC[$pid.read_bytes]:-0}/1024+${IO_PROC[$pid.write_bytes]:-0}/1024)); human_kib "$total"; UI_PROCESS_VALUE=$REPLY
        fi
    else
        UI_PROCESS_LABEL="$pid ${ACT_PROC[$pid.name]:-?}"
        if [[ $kind == cpu ]]; then UI_PROCESS_VALUE=${ACT_PROC[$pid.cpu]:-?}%
        else human_kib "${ACT_PROC[$pid.rss]:-0}"; UI_PROCESS_VALUE=$REPLY; fi
    fi
}
ui_task_ids() {
    case $1 in cpu) UI_TASK_IDS=("${ACT_CPU_IDS[@]}") ;; rss) UI_TASK_IDS=("${ACT_RAM_IDS[@]}") ;; io) UI_TASK_IDS=("${IO_TOP_IDS[@]}") ;; esac
}
ui_tasks() {
    local budget=$1 summary='' count='?' d='?' z='?' kind label pid rank=0 i limit title shade dev r w shown=0 inflight='?'
    local -a kinds=() UI_TASK_IDS=()
    case ${MODEL[process_state]-} in ok|partial) count=${MODEL[process_count]:-?}; d=${MODEL[process_blocked]:-?}; z=${MODEL[process_zombies]:-?} ;; esac
    summary="$count tasks D$d Z$z"
    ui_enabled system load && summary+=" | ${MODEL[cpus]:-?}C L${MODEL[load1]:-?}"
    if ui_enabled processes io && [[ ${MODEL[io_basis]-} == interval ]]; then summary+=" | I/O ${MODEL[io_interval_ms]:-?}ms"; fi
    ui_begin processes "$budget" "$summary"
    if [[ $MODE == verbose ]]; then
        ui_enabled processes cpu && ui_process_table cpu 'CPU average since process start'
        ui_enabled processes rss && ui_process_table rss 'Resident memory (RSS)'
        ui_enabled processes io && ui_io_body
        ui_enabled processes details && ui_text 'CPU is a lifetime average; RSS includes shared pages.' "${COLOR[muted]}"
        return
    fi
    for kind in cpu rss io; do ui_enabled processes "$kind" && kinds+=("$kind"); done
    ((${#kinds[@]})) || return
    if ((TEXT_WIDTH>=60)); then
        ui_columns "${#kinds[@]}"; i=0
        for kind in "${kinds[@]}"; do
            case $kind in cpu) title='CPU avg / PID name' ;; rss) title='RAM RSS / PID name' ;; io) title="I/O R+W/s [${MODEL[io_readable]:-?}/${MODEL[io_candidates]:-?}]"; [[ ${MODEL[io_basis]-} == interval ]] || title="I/O total [${MODEL[io_readable]:-?}/${MODEL[io_candidates]:-?}]" ;; esac
            ((${MODEL[unicode]:-0}!=0)) || title=${title//·/|}
            ui_colour "$kind" heading; shade=$REPLY; ui_plain_cell "$title" "${UI_COL_WIDTHS[i]}" "$shade"; UI_CELLS+=("$REPLY"); ((i+=1))
        done
        ui_grid
        limit=$UI_REMAIN; ((limit<=TOP_N)) || limit=$TOP_N
        for ((rank=0;rank<limit;rank++)); do
            ui_columns "${#kinds[@]}"; i=0
            for kind in "${kinds[@]}"; do
                ui_task_ids "$kind"; pid=${UI_TASK_IDS[rank]-}; ui_process_value "$kind" "$pid"
                ui_colour "$kind" heading; shade=$REPLY
                if [[ -n $pid ]]; then ui_value_cell "${UI_COL_WIDTHS[i]}" "$UI_PROCESS_LABEL" "$UI_PROCESS_VALUE" "$shade"
                else ui_plain_cell '-' "${UI_COL_WIDTHS[i]}" "${COLOR[muted]}"; fi
                UI_CELLS+=("$REPLY"); ((i+=1))
            done
            ui_grid
        done
    else
        for kind in "${kinds[@]}"; do
            ui_task_ids "$kind"; pid=${UI_TASK_IDS[0]-}; ui_process_value "$kind" "$pid"; ui_colour "$kind" heading; shade=$REPLY
            case $kind in cpu) label='CPU avg' ;; rss) label='RAM RSS' ;; io) label='I/O /s'; [[ ${MODEL[io_basis]-} == interval ]] || label='I/O total' ;; esac
            ui_value_cell "$TEXT_WIDTH" "$label $UI_PROCESS_LABEL" "$UI_PROCESS_VALUE" "$shade"; ui_emit "$REPLY"
        done
    fi
    if ((UI_REMAIN>0)) && ui_enabled processes io; then
        if [[ ${MODEL[io_basis]-} == interval ]]; then summary="I/O ~${MODEL[io_interval_ms]:-?}ms"
        else summary='I/O lifetime totals'; fi
        summary+=" | ${MODEL[io_readable]:-?}/${MODEL[io_candidates]:-?} readable PIDs"
        ui_row "$summary" "${COLOR[muted]}"
        if [[ ${MODEL[diskstats_state]-} == ok || ${MODEL[diskstats_state]-} == partial ]]; then
            ((${MODEL[disk_device_count]:-0}==0)) || inflight=${MODEL[disk_inflight]:-?}
            summary="Devices ${MODEL[disk_device_count]:-?} | in flight $inflight"
            ui_enabled system pressure && summary+=" | I/O stall ${MODEL[psi_io]:-?}%"
            ui_row "$summary" "${COLOR[muted]}"
            for dev in "${IO_DEV_IDS[@]}"; do
                ((shown<IO_SHOW_DEVICES && UI_REMAIN>0)) || break; ((shown+=1))
                if [[ -n ${IO_DEV[$dev.read_kib_s]-} && -n ${IO_DEV[$dev.write_kib_s]-} ]]; then
                    human_kib "${IO_DEV[$dev.read_kib_s]}"; r=$REPLY/s
                    human_kib "${IO_DEV[$dev.write_kib_s]}"; w=$REPLY/s
                    ui_row "$dev  R$r  W$w  q${IO_DEV[$dev.inflight]:-?}"
                else ui_row "$dev  q${IO_DEV[$dev.inflight]:-?}; rate unavailable" "${COLOR[muted]}"; fi
            done
        fi
    fi
}
ui_process_table() {
    local kind=$1 title=$2 pid uid user i label shade
    local -a UI_TASK_IDS=()
    ui_colour "$kind" heading; shade=$REPLY; ui_row "$title" "$shade"
    ui_task_ids "$kind"
    if ((${#UI_TASK_IDS[@]}==0)); then ui_row "Process ranking ${MODEL[process_state]:-unavailable}." "${COLOR[muted]}"; return; fi
    if ((TEXT_WIDTH>=60)); then
        UI_COL_WIDTHS=(7 11 8 9 "$((TEXT_WIDTH-47))"); UI_CELLS=(); i=0
        for label in PID USER 'CPU avg' RSS COMMAND; do ui_plain_cell "$label" "${UI_COL_WIDTHS[i]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY"); ((i+=1)); done; ui_grid
    fi
    for pid in "${UI_TASK_IDS[@]}"; do
        uid=${ACT_PROC[$pid.uid]-?}; user=${ACT_LOCAL_USER[$uid]:-#$uid}
        if ((TEXT_WIDTH>=60)); then
            UI_CELLS=(); ui_plain_cell "$pid" 7; UI_CELLS+=("$REPLY")
            ui_plain_cell "$user" 11; UI_CELLS+=("$REPLY")
            ui_plain_cell "${ACT_PROC[$pid.cpu]:-?}%" 8 "${COLOR[cpu]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY")
            human_kib "${ACT_PROC[$pid.rss]:-0}"; ui_plain_cell "$REPLY" 9 "${COLOR[rss]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY")
            ui_plain_cell "${ACT_PROC[$pid.name]:-?}" "${UI_COL_WIDTHS[4]}"; UI_CELLS+=("$REPLY"); ui_grid
        else
            ui_text "$pid ${ACT_PROC[$pid.name]:-?} ($user)" "${COLOR[heading]}"
            human_kib "${ACT_PROC[$pid.rss]:-0}"; ui_row "CPU ${ACT_PROC[$pid.cpu]:-?}% | RSS $REPLY"
        fi
    done
}
ui_io_body() {
    local pid dev r w total label i shown=0 inflight='?'
    if [[ ${MODEL[io_basis]-} == interval ]]; then label="Disk I/O / ${MODEL[io_interval_min_ms]:-?}-${MODEL[io_interval_max_ms]:-?}ms sample"
    else label='Disk I/O / cumulative storage bytes'; fi
    ((${MODEL[unicode]:-0}!=0)) || label=${label//·/|}
    ui_row "$label" "${COLOR[io]:-${COLOR[heading]}}"
    if ((TEXT_WIDTH>=60)); then
        UI_COL_WIDTHS=(7 "$((TEXT_WIDTH-40))" 12 12); UI_CELLS=(); i=0
        for label in PID COMMAND READ WRITE; do ui_plain_cell "$label" "${UI_COL_WIDTHS[i]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY"); ((i+=1)); done; ui_grid
    fi
    for pid in "${IO_TOP_IDS[@]}"; do
        if [[ ${MODEL[io_basis]-} == interval ]]; then human_kib "${IO_PROC[$pid.read_kib_s]:-0}"; r=$REPLY/s; human_kib "${IO_PROC[$pid.write_kib_s]:-0}"; w=$REPLY/s
        else io_amount "${IO_PROC[$pid.read_bytes]:-0}"; r=$REPLY; io_amount "${IO_PROC[$pid.write_bytes]:-0}"; w=$REPLY; fi
        if ((TEXT_WIDTH>=60)); then
            UI_CELLS=(); ui_plain_cell "$pid" 7; UI_CELLS+=("$REPLY")
            ui_plain_cell "${IO_PROC[$pid.name]:-?}" "${UI_COL_WIDTHS[1]}"; UI_CELLS+=("$REPLY")
            ui_plain_cell "$r" 12 "${COLOR[io]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY")
            ui_plain_cell "$w" 12 "${COLOR[io]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY"); ui_grid
        else ui_text "$pid ${IO_PROC[$pid.name]:-?}"; ui_row "Read $r  Write $w" "${COLOR[io]:-${COLOR[heading]}}"; fi
        if ((${IO_PROC[$pid.cancelled_bytes]:-0}>0)); then io_amount "${IO_PROC[$pid.cancelled_bytes]}"; ui_text "Cancelled write accounting: $REPLY cumulative" "${COLOR[muted]}"; fi
    done
    ((${#IO_TOP_IDS[@]})) || ui_row "Process I/O ${MODEL[io_state]:-unavailable}" "${COLOR[muted]}"
    if ui_enabled processes details; then
        ui_text "Readable ${MODEL[io_readable]:-?}/${MODEL[io_examined]:-?} examined; denied/incomplete ${MODEL[io_denied]:-?}; exited/changed ${MODEL[io_gone]:-?}." "${COLOR[muted]}"
        ((${MODEL[io_capped]:-0}==0)) || ui_row 'PID pass capped; rankings cover the measured subset.' "${COLOR[warn]}"
        ui_text 'Includes waited-for children; buffering/cancellation affect attribution.' "${COLOR[muted]}"
    fi
    if [[ ${MODEL[diskstats_state]-} == ok || ${MODEL[diskstats_state]-} == partial ]]; then
        ((${MODEL[disk_device_count]:-0}==0)) || inflight=${MODEL[disk_inflight]:-?}
        ui_row "Devices ${MODEL[disk_device_count]:-?} | requests in flight $inflight" "${COLOR[heading]}"
        for dev in "${IO_DEV_IDS[@]}"; do
            ((shown<IO_SHOW_DEVICES)) || break; ((shown+=1))
            if [[ -n ${IO_DEV[$dev.read_kib_s]-} && -n ${IO_DEV[$dev.write_kib_s]-} ]]; then human_kib "${IO_DEV[$dev.read_kib_s]}"; r=$REPLY/s; human_kib "${IO_DEV[$dev.write_kib_s]}"; w=$REPLY/s; label=''
            else io_amount "${IO_DEV[$dev.read_bytes]:-0}"; r=$REPLY; io_amount "${IO_DEV[$dev.write_bytes]:-0}"; w=$REPLY; label=' totals'; fi
            ui_text "$dev  read $r  write $w  q${IO_DEV[$dev.inflight]:-?}$label"
        done
    else ui_row 'Block-device counters unavailable.' "${COLOR[muted]}"; fi
}
ui_io() { ui_begin io "$1"; ui_io_body; }
ui_session_row() {
    local index=$1 user=${ACT_SESSION[$1.Name]:-?} kind=${ACT_SESSION[$1.Kind]:-?}
    local sid=${ACT_SESSION[$1.Id]-} place=${ACT_SESSION[$1.TTY]:-${ACT_SESSION[$1.Display]:--}}
    local peer=${ACT_SESSION[$1.RemoteHost]:-(local/unknown)} state=${ACT_SESSION[$1.State]:-?} text='' i=0
    if ((TEXT_WIDTH>=60)); then
        UI_COL_WIDTHS=(6 8 8 13 "$((TEXT_WIDTH-47))"); UI_CELLS=()
        ui_plain_cell "$kind" 6 "${COLOR[heading]}"; UI_CELLS+=("$REPLY")
        text=''; ui_enabled sessions id && text=${sid:+#$sid}; ui_plain_cell "$text" 8; UI_CELLS+=("$REPLY")
        ui_plain_cell "$place" 8; UI_CELLS+=("$REPLY")
        text=''; ui_enabled sessions user && text=$user; ui_plain_cell "$text" 13; UI_CELLS+=("$REPLY")
        text=''; ui_enabled sessions peer && text=$peer
        ui_enabled sessions state && text+=" [$state]"
        ui_plain_cell "$text" "${UI_COL_WIDTHS[4]}"; UI_CELLS+=("$REPLY"); ui_grid
        if [[ $MODE == verbose ]]; then
            if ui_enabled sessions peer && ((${#text}>UI_COL_WIDTHS[4])); then ui_text "Peer $peer"; fi
            if ui_enabled sessions user && ((${#user}>13)); then ui_text "User $user"; fi
        fi
    else
        text=$kind; ui_enabled sessions id && text+=" ${sid:+#$sid}"
        text+=" $place"; ui_enabled sessions user && text+=" $user"
        if ((UI_REMAIN<2)); then text+=' ...'; fi
        ui_row "$text" "${COLOR[heading]}"
        text=''; ui_enabled sessions peer && text=$peer
        ui_enabled sessions state && text+=" [$state]"
        [[ -z $text ]] || ui_row "$text"
    fi
}
ui_sessions() {
    local budget=$1 summary='' index shown=0 total=${MODEL[session_count]:-0} per=1 capacity
    ((TEXT_WIDTH>=60)) || per=2
    capacity=$(((budget>0 ? budget-1+per-1 : 0)/per)); ((capacity<=MAX_SESSIONS)) || capacity=$MAX_SESSIONS
    case ${MODEL[session_state]-} in
        ok|partial|fallback)
            summary="$total sessions / ${MODEL[session_users]:-?} users"
            ((total<=capacity)) || summary+=" +$((total-capacity))"
            [[ ${MODEL[session_state]} != partial ]] || summary+=' partial'
            [[ ${MODEL[session_source]-} != utmp ]] || summary+=' utmp' ;;
        *) summary=${MODEL[session_state]:-unavailable} ;;
    esac
    ui_begin sessions "$budget" "$summary"
    case ${MODEL[session_state]-} in ok|partial|fallback) ;; *) ui_row 'Session records unavailable.' "${COLOR[muted]}"; return ;; esac
    for index in "${ACT_SESSION_IDS[@]}"; do
        ((UI_REMAIN>0 && shown<MAX_SESSIONS)) || break
        ui_session_row "$index"; ((shown+=1))
    done
    ((total!=0)) || ui_row 'No session records in the available source.' "${COLOR[muted]}"
    if [[ $MODE == verbose ]]; then
        ((total<=shown)) || ui_row "$((total-shown)) additional sessions not shown." "${COLOR[muted]}"
        ui_text 'Session records do not prove an attached SSH/RDP client.' "${COLOR[muted]}"
    fi
}
ui_connections() {
    local budget=$1 summary index
    case ${MODEL[connection_state]-} in ok|partial) summary="${MODEL[tcp_established]:-?} TCP / ${MODEL[tcp_admin]:-?} admin" ;; *) summary=${MODEL[connection_state]:-unavailable} ;; esac
    ui_begin connections "$budget" "$summary"
    if ui_enabled connections records; then
        for index in "${ACT_CONN_IDS[@]}"; do ui_text "${ACT_CONN[$index.label]:-TCP}  ${ACT_CONN[$index.local]:-?}  <->  ${ACT_CONN[$index.peer]:-?}"; done
    fi
    if [[ $MODE == verbose ]]; then ui_text 'Port labels are hints; sockets do not identify authenticated users.' "${COLOR[muted]}"; fi
}
ui_attention() {
    local budget=$1 entry level message shade summary='' errors=0 warnings=0 infos=0 shown=0
    local -a entries=()
    for entry in "${ATTENTION[@]}"; do
        level=${entry%%|*}; ui_enabled attention "$level" || continue
        entries+=("$entry")
        case $level in ERROR) ((errors+=1)) ;; WARN) ((warnings+=1)) ;; *) ((infos+=1)) ;; esac
    done
    summary="E$errors W$warnings I$infos"; shade=${COLOR[ok]}
    if ((${#entries[@]}==0 && ${#ATTENTION[@]}>0)); then summary="${#ATTENTION[@]} hidden"; shade=${COLOR[muted]}; fi
    ((errors+warnings+infos==0)) || shade=${COLOR[muted]}
    ((warnings==0)) || shade=${COLOR[warn]}; ((errors==0)) || shade=${COLOR[error]}
    ui_begin attention "$budget" "$summary" "$shade"
    if ((${#entries[@]}==0)); then
        if ((${#ATTENTION[@]}==0)); then ui_row 'No configured alerts in collected scope.' "${COLOR[ok]}"
        else ui_row "${#ATTENTION[@]} notice(s) hidden by display settings." "${COLOR[muted]}"; fi
        return
    fi
    for entry in "${entries[@]}"; do
        ((shown<MAX_ATTENTION && UI_REMAIN>0)) || break; ((shown+=1))
        IFS='|' read -r level message <<<"$entry"
        if [[ $MODE == concise ]]; then
            case $message in 'Unit needs review: systemctl status -- '*) message="${message#'Unit needs review: systemctl status -- '}: inspect unit" ;; esac
        fi
        shade=${COLOR[muted]}; [[ $level != ERROR ]] || shade=${COLOR[error]}; [[ $level != WARN ]] || shade=${COLOR[warn]}
        if [[ $MODE == concise ]]; then ui_row "$level: $message" "$shade"
        else ui_text "$level: $message" "$shade"; fi
    done
    ((${#entries[@]}<=shown)) || ui_row "$(( ${#entries[@]}-shown )) additional notice(s) not shown." "${COLOR[muted]}"
}
ui_hints() {
    local budget=$1 entry label command note id summary='' candidate available
    local -a entries=()
    available=$((INNER-4-${#UI_SECTION_TITLE}-2))
    for entry in "${HINTS[@]}"; do
        ui_hint_parse "$entry"; id=$UI_HINT_ID; label=$UI_HINT_LABEL; command=$UI_HINT_COMMAND; note=$UI_HINT_NOTE
        ui_enabled hints "$id" || continue
        entries+=("$label|$command|$note")
        candidate="$summary${summary:+ | }$command"
        if ((${#candidate}<=available)); then summary=$candidate; fi
    done
    ui_begin hints "$budget" "$summary"
    ((budget>1)) || return
    for entry in "${entries[@]}"; do
        IFS='|' read -r label command note <<<"$entry"
        if [[ $MODE == verbose ]]; then
            ui_columns 2; ui_plain_cell "$label" "${UI_COL_WIDTHS[0]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY")
            ui_plain_cell "$note" "${UI_COL_WIDTHS[1]}" "${COLOR[muted]}"; UI_CELLS+=("$REPLY"); ui_grid
            ui_text "$command" "${COLOR[value]:-${COLOR[text]}}"
        else ui_value_cell "$TEXT_WIDTH" "$label" "$command" "${COLOR[value]:-${COLOR[text]}}"; ui_emit "$REPLY"; fi
    done
}

# ==================== 8. DISPLAY POLICY AND SECTION REGISTRY =================

# The registry is display policy, not collection policy. A hidden panel must not
# silently disable a resource/service warning. User data is never evaluated as code.
declare -A SECTION_RENDERER=() SECTION_BASE_ROWS=() SECTION_MIN_ROWS=() SECTION_MAX_ROWS=() UI_PLAN=()
UI_ITEM_KEYS=(header.title header.site header.host header.time
    system.identity system.domain system.addresses system.platform system.load system.pressure
    resources.memory resources.swap resources.compression resources.storage resources.filesystem_detail
    services.summary processes.cpu processes.rss processes.io processes.details
    sessions.id sessions.user sessions.peer sessions.state connections.records
    attention.ERROR attention.WARN attention.INFO)
UI_SECTION_TITLE='' UI_REGISTRY_READY=0
UI_HINT_ID='' UI_HINT_LABEL='' UI_HINT_COMMAND='' UI_HINT_NOTE=''

ui_hint_parse() {
    local entry=$1 a b c d
    IFS='|' read -r a b c d <<<"$entry"
    if [[ $entry == *'|'*'|'*'|'* ]]; then
        UI_HINT_ID=$a; UI_HINT_LABEL=$b; UI_HINT_COMMAND=$c; UI_HINT_NOTE=$d
    else
        UI_HINT_ID=$a; UI_HINT_LABEL=$a; UI_HINT_COMMAND=$b; UI_HINT_NOTE=$c
    fi
}

ui_registry_init() {
    local id title renderer base minimum maximum key value
    for id in "${!SECTION_SPEC[@]}"; do
        IFS='|' read -r title renderer base minimum maximum <<<"${SECTION_SPEC[$id]}"
        [[ $id =~ ^[a-z][a-z0-9_]*$ && $renderer =~ ^[a-z_][a-z0-9_]*$ ]] || return 2
        declare -F "$renderer" >/dev/null || return 2
        for value in "$base" "$minimum" "$maximum"; do
            [[ -n $value && ${#value} -le 5 && $value != *[!0123456789]* ]] || return 2
        done
        base=$((10#$base)); minimum=$((10#$minimum)); maximum=$((10#$maximum))
        ((minimum<=base && base<=maximum && maximum<=10000)) || return 2
        [[ ${SECTION_TITLE[$id]+set} ]] || SECTION_TITLE[$id]=$title
        SECTION_RENDERER[$id]=$renderer
        SECTION_BASE_ROWS[$id]=$base
        SECTION_MIN_ROWS[$id]=$minimum; SECTION_MAX_ROWS[$id]=$maximum
    done
    local -A seen=()
    for id in "${SECTIONS[@]}"; do
        [[ ${SECTION_SPEC[$id]+set} && ! ${seen[$id]+set} ]] || return 2
        seen[$id]=1
    done
    for key in "${!SECTION_ROWS[@]}"; do
        value=${SECTION_ROWS[$key]}
        case $key in
            concise.*|verbose.*) [[ ${SECTION_SPEC[${key#*.}]+set} ]] || return 2 ;;
            *) [[ ${SECTION_SPEC[$key]+set} ]] || return 2 ;;
        esac
        [[ -n $value && ${#value} -le 5 && $value != *[!0123456789]* ]] && ((10#$value<=10000)) || return 2
        SECTION_ROWS[$key]=$((10#$value))
    done
    for key in "${!SECTION_VISIBLE[@]}"; do
        [[ ${SECTION_SPEC[$key]+set} && ${SECTION_VISIBLE[$key]} =~ ^[01]$ ]] || return 2
    done
    for key in "${!ITEM_VISIBLE[@]}"; do
        [[ ${ITEM_VISIBLE[$key]} =~ ^[01]$ ]] && ui_item_known "$key" || return 2
    done
    UI_REGISTRY_READY=1
}

ui_item_enabled() {
    local section=$1 item=$2
    [[ ${ITEM_VISIBLE[$section.$item]-1} == 1 ]] || return 1
    case $section.$item in
        resources.swap) ((SHOW_SWAP)) ;;
        resources.compression) ((SHOW_COMPRESSION)) ;;
        system.pressure|resources.pressure) ((SHOW_PRESSURE)) ;;
        *) return 0 ;;
    esac
}

ui_section_enabled() {
    local id=$1 entry found=0
    [[ ${SECTION_VISIBLE[$id]-1} == 1 ]] || return 1
    [[ $id != attention ]] || ((SHOW_ATTENTION)) || return 1
    if [[ $id == hints ]]; then
        for entry in "${HINTS[@]}"; do
            ui_hint_parse "$entry"
            if [[ -n $UI_HINT_COMMAND ]] && ui_item_enabled hints "$UI_HINT_ID"; then found=1; break; fi
        done
        ((found)) || return 1
    fi
    ui_section_rows "$id"
    ((REPLY>0))
}

ui_section_rows() {
    local id=$1
    if [[ ${SECTION_ROWS[$id]+set} ]]; then REPLY=${SECTION_ROWS[$id]}
    elif [[ ${SECTION_ROWS[$MODE.$id]+set} ]]; then REPLY=${SECTION_ROWS[$MODE.$id]}
    elif [[ $MODE == concise ]]; then REPLY=${SECTION_BASE_ROWS[$id]}
    else REPLY=10000; fi
}

ui_plan_layout() {
    local id available total=0 changed=1 minimum rows reduction
    UI_PLAN=()
    ((UI_REGISTRY_READY)) || ui_registry_init || return 2
    for id in "${SECTIONS[@]}"; do
        ui_section_enabled "$id" || continue
        rows=$REPLY
        UI_PLAN[$id]=$((10#$rows)); ((total+=10#$rows))
    done
    [[ $MODE == concise ]] || return 0
    available=$((COMPACT_ROWS-3)); ((available>=0)) || available=0
    # Reduce content, never the named framing. Attention retains its first notice.
    for id in "${COMPACT_TRIM_ORDER[@]}" "${SECTIONS[@]}"; do
        ((total>available)) || break
        [[ ${UI_PLAN[$id]+set} ]] || continue
        minimum=${SECTION_MIN_ROWS[$id]:-1}
        if [[ $id == processes ]] && ((${TEXT_WIDTH:-76}<60 && minimum<4)); then minimum=4; fi
        reduction=$((UI_PLAN[$id]-minimum)); ((reduction>0)) || continue
        ((reduction<=total-available)) || reduction=$((total-available))
        ((UI_PLAN[$id]-=reduction,total-=reduction))
    done
    # A deliberately overloaded custom layout needs a larger --rows value.
    if ((total>available)); then
        printf '%s\n' 'Configured section minimums exceed the row budget; use --rows 50 or hide a section.' >&2
        return 2
    fi
    # Only an explicitly larger row budget expands the compact baseline.
    if ((COMPACT_ROWS>25)); then
        changed=1
        while ((total<available && changed)); do
            changed=0
            for id in "${COMPACT_EXPAND_ORDER[@]}" "${SECTIONS[@]}"; do
                [[ ${UI_PLAN[$id]+set} ]] || continue
                [[ ! ${SECTION_ROWS[$id]+set} && ! ${SECTION_ROWS[$MODE.$id]+set} ]] || continue
                if ((${UI_PLAN[$id]}<${SECTION_MAX_ROWS[$id]:-1})); then
                    ((UI_PLAN[$id]+=1,total+=1)); changed=1
                    ((total<available)) || break
                fi
            done
        done
    fi
}

ui_render_sections() {
    local id
    ui_plan_layout || return $?
    OUTPUT=''
    ui_top
    for id in "${SECTIONS[@]}"; do
        [[ ${UI_PLAN[$id]+set} ]] || continue
        UI_SECTION_TITLE=${SECTION_TITLE[$id]}
        "${SECTION_RENDERER[$id]}" "${UI_PLAN[$id]}"
    done
    ui_bottom
}

# Legacy branches within individual components remain private during this
# bounded migration. All public entry points use the same adaptive dispatcher.
render_adaptive() { local MODE=concise; ui_render_sections; }

ui_section_list() {
    local id state
    printf '%-13s %-9s %-7s %s\n' ID DISPLAY ROWS TITLE
    for id in "${SECTIONS[@]}"; do
        state=shown; ui_section_enabled "$id" || state=hidden
        ui_section_rows "$id"
        printf '%-13s %-9s %-7s %s\n' "$id" "$state" "$REPLY" "${SECTION_TITLE[$id]}"
    done
}

ui_item_list() {
    local key id entry
    for key in "${UI_ITEM_KEYS[@]}"; do
        printf '%-34s %s\n' "$key" "${ITEM_VISIBLE[$key]-1}"
    done
    for id in "${SERVICE_ROLE_ORDER[@]}"; do printf '%-34s %s\n' "services.$id" "${ITEM_VISIBLE[services.$id]-1}"; done
    for entry in "${HINTS[@]}"; do
        ui_hint_parse "$entry"
        printf '%-34s %s\n' "hints.$UI_HINT_ID" "${ITEM_VISIBLE[hints.$UI_HINT_ID]-1}"
    done
}

ui_item_known() {
    local key=$1 known section=${1%%.*} item=${1#*.} entry
    for known in "${UI_ITEM_KEYS[@]}"; do [[ $key != "$known" ]] || return 0; done
    case $section in
        services)
            [[ ${SERVICE_ROLE_UNITS[$item]+set} ]] && return 0
            case $item in *.service|*.socket|*.timer) return 0 ;; esac ;;
        hints)
            for entry in "${HINTS[@]}"; do
                ui_hint_parse "$entry"
                [[ $UI_HINT_ID != "$item" ]] || return 0
            done ;;
        header|system|resources|processes|sessions|connections|attention|io) ;;
        *) [[ ${SECTION_SPEC[$section]+set} && -n $item ]] && return 0 ;;
    esac
    return 1
}

ui_set_sections() {
    local action=$1 value=$2 id present key section
    local -a requested=()
    [[ $value != ,* && $value != *, && $value != *,,* ]] || return 2
    IFS=',' read -r -a requested <<<"$value"
    ((${#requested[@]})) || return 2
    if [[ $action == --sections ]]; then SECTIONS=(); fi
    for id in "${requested[@]}"; do
        [[ -n $id && ${SECTION_SPEC[$id]+set} ]] || return 2
        case $action in
            --sections) SECTIONS+=("$id") ;;
            --hide) SECTION_VISIBLE[$id]=0 ;;
            --show)
                SECTION_VISIBLE[$id]=1; present=0
                for key in "${SECTIONS[@]}"; do [[ $key != "$id" ]] || present=1; done
                ((present)) || SECTIONS+=("$id") ;;
        esac
    done
    ui_registry_init
}

ui_set_items() {
    local action=$1 value=$2 key section item enabled=0
    local -a requested=()
    [[ $action != --show-item ]] || enabled=1
    [[ $value != ,* && $value != *, && $value != *,,* ]] || return 2
    IFS=',' read -r -a requested <<<"$value"
    ((${#requested[@]})) || return 2
    for key in "${requested[@]}"; do
        section=${key%%.*}; item=${key#*.}
        [[ $key == *.* && -n $item ]] || return 2
        [[ $section == header || ${SECTION_SPEC[$section]+set} ]] || return 2
        ui_item_known "$key" || { printf 'Unknown display item: %s\n' "$key" >&2; return 2; }
        ITEM_VISIBLE[$key]=$enabled
    done
}
# END REGISTRY

clip_sgr_cell() {
    local text=$1 width=$2 remaining suffix='' prefix token out='' styled=0
    local pattern=$'\033''\[[0-9;]*m'
    ((width>0)) || { REPLY=''; return 0; }
    remaining=$width
    if ((width>=3)); then remaining=$((width-3)); suffix='...'; fi
    while [[ $text =~ $pattern ]]; do
        token=${BASH_REMATCH[0]}; prefix=${text%%"$token"*}
        if [[ -n $prefix ]] && ((${#prefix}>=remaining)); then
            out+=${prefix:0:remaining}; remaining=0; break
        fi
        out+="$prefix$token"; styled=1
        remaining=$((remaining-${#prefix})); text=${text#*"$token"}
    done
    if ((remaining>0)); then out+=${text:0:remaining}; fi
    REPLY=$out$suffix
    ((styled==0)) || REPLY+=$'\033[0m'
}

# ==================== 9. EXECUTION ===========================================
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
'''
# END EMBEDDED BASH

# BEGIN EMBEDDED SH — regenerated by tools/embed_runtime.py
SH_TEMPLATE = r'''#!/bin/sh
# Portable MOTD baseline. POSIX shell syntax; no Bash, Python or service manager.
# This deliberately small renderer does not reproduce the Linux Bash collectors.
# Linux /proc files provide cheap local observations when available. Missing
# counters stay unavailable; no external command or network lookup fills them in.
# GNU-compatible timeout is required only for explicitly configured hooks.

TITLE='SYSTEM STATUS'
SITE_LABEL=''
THEME=mono
MAX_WIDTH=80
ROWS=25
SECTIONS='system resources attention hints'
motd_messages() { :; }
motd_hints() { :; }
motd_before_hooks() { :; }
motd_after_hooks() { :; }

# @MOTD_CONFIG@

MOTD_DEMO=0
MOTD_DEMO_ALERTS=0
MOTD_HOOKS_ENABLED=1
MOTD_PLAIN=0
MOTD_FORCE_COLOR=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --demo) MOTD_DEMO=1; MOTD_HOOKS_ENABLED=0 ;;
        --demo-alerts) MOTD_DEMO=1; MOTD_DEMO_ALERTS=1; MOTD_HOOKS_ENABLED=0 ;;
        --no-hooks) MOTD_HOOKS_ENABLED=0 ;;
        --plain) MOTD_PLAIN=1 ;;
        --color) MOTD_FORCE_COLOR=1 ;;
        --ascii) : ;; # The baseline already uses ASCII framing.
        --width|--rows)
            motd_option=$1
            shift
            case "${1-}" in
                ''|*[!0-9]*) printf '%s\n' 'Width/rows require an integer.' >&2; exit 2 ;;
            esac
            # Check length first: never feed an unbounded integer into old shells.
            if [ "${#1}" -gt 3 ]; then
                printf '%s\n' 'Width/rows are outside the supported range.' >&2
                exit 2
            fi
            motd_number=$1
            # Old shells may read leading-zero arithmetic as octal.
            while [ "${motd_number#0}" != "$motd_number" ] && [ "${#motd_number}" -gt 1 ]; do
                motd_number=${motd_number#0}
            done
            if [ "$motd_option" = --width ]; then
                if [ "$motd_number" -lt 40 ] || [ "$motd_number" -gt 240 ]; then exit 2; fi
                MAX_WIDTH=$motd_number
            else
                if [ "$motd_number" -lt 20 ] || [ "$motd_number" -gt 60 ]; then exit 2; fi
                ROWS=$motd_number
            fi ;;
        --version) printf '%s\n' 'MOTD portable sh baseline'; exit 0 ;;
        --list-sections) printf '%s\n' 'system resources services processes sessions connections attention hints io'; exit 0 ;;
        --help|-h)
            printf '%s\n' 'Portable MOTD: --demo --demo-alerts --plain --color --ascii --no-hooks --width N --rows N' \
                'Basic identity, Linux memory/load/uptime where available, messages and hints.' \
                'Advanced service, process, session, connection and I/O collectors are unavailable.'
            exit 0 ;;
        *) printf '%s\n' "Unknown portable MOTD option: $1" >&2; exit 2 ;;
    esac
    shift
done

# No arbitrary helper programs run during data collection. Configuration text is
# quoted by the generator; the display helper also replaces terminal controls.
# Width clipping is by shell characters, not a Unicode grapheme-width engine.
motd_remaining=$((ROWS - 1))
motd_line() {
    if [ "$motd_remaining" -le 0 ]; then return; fi
    if [ "$motd_remaining" -eq 1 ]; then
        printf '%s\n' '[More content omitted]'
        motd_remaining=0
        return
    fi
    motd_rest=$1
    motd_clean=''
    motd_count=0
    while [ -n "$motd_rest" ] && [ "$motd_count" -lt "$MAX_WIDTH" ]; do
        motd_character=${motd_rest%"${motd_rest#?}"}
        motd_rest=${motd_rest#?}
        case "$motd_character" in [[:cntrl:]]) motd_character='?' ;; esac
        motd_clean=$motd_clean$motd_character
        motd_count=$((motd_count + 1))
    done
    printf '%s\n' "$motd_clean"
    motd_remaining=$((motd_remaining - 1))
}

motd_heading() {
    # Colour is an optional enhancement. NO_COLOR and dumb/redirected terminals
    # remain plain; no terminal escape sequence is sourced from configuration.
    if [ "$MOTD_PLAIN" -eq 0 ] && [ "$THEME" != mono ] && { [ -t 1 ] || [ "$MOTD_FORCE_COLOR" -eq 1 ]; } && [ -z "${NO_COLOR+x}" ] && [ "${TERM-dumb}" != dumb ]; then
        case "$THEME" in
            cyan) printf '\033[1;36m' ;;
            green) printf '\033[1;32m' ;;
            amber) printf '\033[1;33m' ;;
        esac
        motd_line "$1"
        printf '\033[0m'
    else
        motd_line "$1"
    fi
}

motd_host=unavailable
motd_os=unavailable
motd_release=unavailable
motd_uptime=unavailable
motd_load=unavailable
motd_total=unavailable
motd_available=unavailable
motd_free=unavailable
if [ "$MOTD_DEMO" -eq 1 ]; then
    motd_host=demo-host
    motd_os=Linux
    motd_release=demo-kernel
    motd_uptime=86400
    motd_load='0.25 0.18 0.12'
    motd_total=16777216
    motd_available=12582912
    motd_free=8388608
else
    # All reads are of fixed local procfs files. The scan has a hard line-count
    # bound; kernel/filesystem stalls are still outside a shell's timing control.
    if [ -r /proc/sys/kernel/hostname ]; then IFS= read -r motd_host < /proc/sys/kernel/hostname || :; fi
    if [ -r /proc/sys/kernel/ostype ]; then IFS= read -r motd_os < /proc/sys/kernel/ostype || :; fi
    if [ -r /proc/sys/kernel/osrelease ]; then IFS= read -r motd_release < /proc/sys/kernel/osrelease || :; fi
    if [ -r /proc/uptime ]; then
        read -r motd_uptime motd_unused < /proc/uptime || :
        motd_uptime=${motd_uptime%%.*}
        case "$motd_uptime" in ''|*[!0-9]*) motd_uptime=unavailable ;; esac
    fi
    if [ -r /proc/loadavg ]; then
        read -r motd_load1 motd_load5 motd_load15 motd_unused < /proc/loadavg || :
        if [ -n "$motd_load1" ] && [ -n "$motd_load5" ] && [ -n "$motd_load15" ]; then
            motd_load="$motd_load1 $motd_load5 $motd_load15"
        fi
    fi
    if [ -r /proc/meminfo ]; then
        motd_mem_lines=0
        while read -r motd_key motd_value motd_unit; do
            motd_mem_lines=$((motd_mem_lines + 1))
            if [ "$motd_mem_lines" -gt 128 ]; then break; fi
            case "$motd_value" in ''|*[!0-9]*) continue ;; esac
            case "$motd_key" in
                MemTotal:) motd_total=$motd_value ;;
                MemAvailable:) motd_available=$motd_value ;;
                MemFree:) motd_free=$motd_value ;;
            esac
        done < /proc/meminfo
    fi
fi
motd_host=${motd_host:-unavailable}
motd_os=${motd_os:-unavailable}
motd_release=${motd_release:-unavailable}

motd_before_hooks || exit "$?"
motd_heading "$TITLE"
if [ -n "$SITE_LABEL" ]; then motd_line "$SITE_LABEL"; fi
motd_line 'Portable sh baseline'
for motd_section in $SECTIONS; do
    case "$motd_section" in
        system)
            motd_heading 'SYSTEM'
            motd_line "Host: $motd_host | OS: $motd_os $motd_release"
            motd_line "Uptime: $motd_uptime s | Load (1/5/15 min): $motd_load" ;;
        resources)
            motd_heading 'RESOURCES'
            if [ "$motd_available" != unavailable ]; then
                motd_line "Memory available: $motd_available KiB / $motd_total KiB total"
            elif [ "$motd_free" != unavailable ]; then
                motd_line "Memory free: $motd_free KiB / $motd_total KiB total (available: unavailable)"
            else
                motd_line 'Memory: unavailable'
            fi
            motd_line 'Storage, swap detail and pressure: unavailable in portable baseline' ;;
        attention)
            motd_heading 'NOTICES'
            if [ "$MOTD_DEMO_ALERTS" -eq 1 ]; then motd_line 'DEMO: Example warning; no live fault is implied.'; fi
            motd_messages ;;
        hints)
            motd_heading 'HINTS'
            motd_hints ;;
        services|processes|sessions|connections|io)
            motd_line "$motd_section: not collected by the portable sh backend" ;;
    esac
done
motd_after_hooks || exit "$?"
'''
# END EMBEDDED SH

# BEGIN EMBEDDED PS — regenerated by tools/embed_runtime.py
PS_TEMPLATE = r'''# Native PowerShell baseline: Windows PowerShell 5.1 and PowerShell 7 syntax.
# This backend has its own local capability checks. It does not run Bash or
# pretend that unavailable Windows/Linux observations are healthy or zero.
# Use the call operator (& ./message.ps1), not dot-sourcing, to keep its scope local.
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch] $Demo,
    [switch] $Plain,
    [switch] $Color,
    [switch] $Ascii,
    [Alias('no-hooks')] [switch] $NoHooks,
    [ValidateRange(0, 240)] [int] $Width = 0,
    [ValidateRange(0, 60)] [int] $Rows = 0,
    [switch] $Version,
    [switch] $Help
)

# @MOTD_CONFIG@

if ($Version) { Write-Output ('MOTD ' + $MotdVersion + ' (native PowerShell)'); return }
if ($Help) {
    Write-Output 'MOTD native PowerShell: -Demo -Plain -Color -Ascii -NoHooks -Width 40..240 -Rows 20..60'
    Write-Output 'Demo uses synthetic data and never runs configured before/after calls.'
    return
}
if ($Width -ne 0 -and $Width -lt 40) { throw 'Width must be 40..240, or 0 for the recipe.' }
if ($Rows -ne 0 -and $Rows -lt 20) { throw 'Rows must be 20..60, or 0 for the recipe.' }
$MotdWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
$MotdWidth = if ($Width) { $Width } else { [int]$MotdConfig.display.width }
$MotdHeight = if ($Rows) { $Rows } else { [int]$MotdConfig.display.rows }
$MotdLines = New-Object 'System.Collections.Generic.List[object]'
$MotdNotices = New-Object 'System.Collections.Generic.List[string]'
$MotdColor = -not $Plain -and -not $env:NO_COLOR -and $MotdConfig.display.theme -ne 'mono'
if (-not $Color) {
    try { $MotdColor = $MotdColor -and $Host.UI.SupportsVirtualTerminal -and -not [Console]::IsOutputRedirected }
    catch { $MotdColor = $false }
}
$MotdEscape = [char]27
$MotdAccent = switch ($MotdConfig.display.theme) { 'green' { '32' } 'amber' { '33' } default { '36' } }

function ConvertTo-MotdText([object] $Value) {
    # Runtime observations are also untrusted display text. Drop terminal control
    # characters rather than allowing a process/service name to move the cursor.
    $safe = [regex]::Replace([string]$Value, '[\x00-\x1f\x7f-\x9f]', '?')
    if ($Ascii) { $safe = [regex]::Replace($safe, '[^\x20-\x7e]', '?') }
    return $safe
}

function Add-MotdLine([string] $Text, [string] $Tone = 'normal') {
    [void]$MotdLines.Add(@{ Text = (ConvertTo-MotdText $Text); Tone = $Tone })
}

function Format-MotdBytes([double] $Bytes) {
    if ($Bytes -lt 0) { return 'unavailable' }
    if ($Bytes -ge 1GB) { return ('{0:N1} GiB' -f ($Bytes / 1GB)) }
    return ('{0:N0} MiB' -f ($Bytes / 1MB))
}

function Format-MotdBar([double] $Used, [double] $Total) {
    if ($Total -le 0 -or $Used -lt 0) { return '[unavailable]' }
    $filled = [int][Math]::Round(12 * [Math]::Max(0.0, [Math]::Min(1.0, $Used / $Total)))
    return '[' + ('#' * $filled) + ('-' * (12 - $filled)) + ']'
}

function ConvertTo-MotdWindowsArgument([string] $Argument) {
    # Windows PowerShell's .NET Framework lacks ProcessStartInfo.ArgumentList.
    # Quote one argv element using the standard Windows C-runtime rules. No
    # shell, Invoke-Expression, string interpolation or implicit cmd.exe is used.
    $quoted = [regex]::Replace($Argument, '(\\*)"', '${1}${1}\"')
    $quoted = [regex]::Replace($quoted, '(\\+)$', '${1}${1}')
    return '"' + $quoted + '"'
}

function Invoke-MotdHooks([string] $Phase) {
    if ($Demo -or $NoHooks) { return }
    $number = 0
    foreach ($hook in @($MotdConfig.hooks.$Phase)) {
        $number++
        $process = New-Object Diagnostics.Process
        $status = 127
        try {
            $info = New-Object Diagnostics.ProcessStartInfo
            $info.FileName = [string]$hook.argv[0]
            $info.UseShellExecute = $false
            # Inherit output; redirected pipe buffers cannot deadlock this wait.
            # A hook must name an executable, or explicitly name an interpreter
            # for a script/cmdlet. Existing execution policy remains in force.
            $arguments = @($hook.argv | Select-Object -Skip 1)
            if ($null -ne $info.PSObject.Properties['ArgumentList']) {
                foreach ($argument in $arguments) { [void]$info.ArgumentList.Add([string]$argument) }
            } else {
                $info.Arguments = (@($arguments | ForEach-Object { ConvertTo-MotdWindowsArgument $_ }) -join ' ')
            }
            $process.StartInfo = $info
            [void]$process.Start()
            $milliseconds = [int][Math]::Ceiling(1000 * [double]$hook.timeout_seconds)
            if ($process.WaitForExit($milliseconds)) { $status = $process.ExitCode }
            else {
                $status = 124
                # Process-tree termination is available in PowerShell 7's .NET.
                # Windows PowerShell 5.1 can terminate only the direct child;
                # descendants are not claimed to be contained by this timeout.
                if ($PSVersionTable.PSVersion.Major -ge 7) { $process.Kill($true) }
                else { $process.Kill() }
                [void]$process.WaitForExit(250)
            }
        } catch { [Console]::Error.WriteLine('MOTD hook could not complete: ' + $_.Exception.Message) }
        finally { $process.Dispose() }
        if ($status -ne 0) {
            $message = 'MOTD ' + $Phase + ' hook ' + $number + ' failed (' + $status + ').'
            [Console]::Error.WriteLine($message)
            if ($hook.on_failure -eq 'stop') { throw $message }
        }
    }
}

function Add-MotdSystem {
    if ($Demo) {
        Add-MotdLine 'SYSTEM     demo-host | Windows / Linux | PowerShell 7 (synthetic)' 'accent'
        Add-MotdLine '           8 logical CPUs | User operator | Local or SSH session'
    } else {
        Add-MotdLine ('SYSTEM     ' + [Environment]::MachineName + ' | ' + [Environment]::OSVersion.VersionString) 'accent'
        $session = if ($env:SSH_CONNECTION -or $env:SSH_TTY) { 'SSH' } else { 'Local/other transport' }
        Add-MotdLine ('           ' + [Environment]::ProcessorCount + ' logical CPUs | User ' + [Environment]::UserName + ' | ' + $session)
    }
}

function Add-MotdResources {
    if ($Demo) {
        Add-MotdLine ('MEMORY     6.0 GiB / 16.0 GiB ' + (Format-MotdBar 6 16)) 'accent'
        Add-MotdLine ('STORAGE    System volume 120.0 GiB / 512.0 GiB ' + (Format-MotdBar 120 512))
        Add-MotdLine '           Swap/compression/pressure detail unavailable in this backend'
        return
    }
    $total = -1.0; $used = -1.0
    try {
        if ($MotdWindows) {
            # A local CIM query supplies actual physical memory, not this
            # PowerShell process's managed heap. Its one-second operation timeout
            # is not a hard whole-render deadline (module startup is additional).
            $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem -OperationTimeoutSec 1 -ErrorAction Stop
            $total = 1024.0 * $osInfo.TotalVisibleMemorySize
            $used = $total - 1024.0 * $osInfo.FreePhysicalMemory
        } elseif ([IO.File]::Exists('/proc/meminfo')) {
            $memory = @{}
            foreach ($line in [IO.File]::ReadAllLines('/proc/meminfo')) {
                if ($line -match '^(MemTotal|MemAvailable):\s+(\d+)\s+kB') { $memory[$matches[1]] = 1024.0 * [double]$matches[2] }
            }
            if ($memory.ContainsKey('MemTotal') -and $memory.ContainsKey('MemAvailable')) {
                $total = $memory.MemTotal; $used = $total - $memory.MemAvailable
            }
        }
    } catch { [void]$MotdNotices.Add('Physical memory observation unavailable.') }
    if ($total -gt 0) {
        Add-MotdLine ('MEMORY     ' + (Format-MotdBytes $used) + ' / ' + (Format-MotdBytes $total) + ' ' + (Format-MotdBar $used $total)) 'accent'
    } else { Add-MotdLine 'MEMORY     unavailable (no supported physical-memory source)' 'warning' }
    try {
        # Inspect only the system volume. Do not probe network or removable drives.
        $rootPath = if ($MotdWindows) { $env:SystemDrive + '\' } else { '/' }
        $drive = New-Object IO.DriveInfo($rootPath)
        $diskUsed = [double]$drive.TotalSize - [double]$drive.TotalFreeSpace
        Add-MotdLine ('STORAGE    ' + $rootPath + ' ' + (Format-MotdBytes $diskUsed) + ' / ' + (Format-MotdBytes $drive.TotalSize) + ' ' + (Format-MotdBar $diskUsed $drive.TotalSize))
    } catch { Add-MotdLine 'STORAGE    unavailable (system volume could not be read)' 'warning' }
    if ($MotdConfig.display.show_swap -or $MotdConfig.display.show_compression -or $MotdConfig.display.show_pressure) {
        Add-MotdLine '           Swap/compression/pressure detail unavailable in this backend'
    }
}

function Add-MotdServices {
    if ($Demo) { Add-MotdLine 'SERVICES   [RUN] sshd   [RUN] example-worker   [STOP] optional-service' 'accent'; return }
    if (-not $MotdWindows) { Add-MotdLine 'SERVICES   unavailable (native service collector currently Windows only)' 'warning'; return }
    try {
        $services = @(Get-Service -ErrorAction Stop | Sort-Object Name)
        $shown = New-Object 'System.Collections.Generic.List[string]'
        foreach ($service in $services) {
            $excluded = $false
            foreach ($pattern in @($MotdConfig.services.exclude)) { if ($service.Name -like $pattern) { $excluded = $true; break } }
            if ($excluded) { continue }
            $required = @($MotdConfig.services.required)
            if ($required.Count -gt 0 -and $service.Name -notin $required) { continue }
            [void]$shown.Add(('[' + $service.Status + '] ' + $service.Name))
        }
        if ($shown.Count) {
            Add-MotdLine ('SERVICES   ' + ((@($shown | Select-Object -First 6)) -join '   ')) 'accent'
            if ($shown.Count -gt 6) { Add-MotdLine ('           Showing 6 of ' + $shown.Count + ' matched services; stopped is not necessarily failed.') }
        } else { Add-MotdLine 'SERVICES   No services matched the configured selection.' }
        foreach ($name in @($MotdConfig.services.required)) {
            if ($name -notin @($services | ForEach-Object { $_.Name })) { [void]$MotdNotices.Add('Required service not found: ' + $name) }
        }
    } catch { Add-MotdLine 'SERVICES   unavailable (service query failed or access denied)' 'warning' }
}

function Add-MotdProcesses {
    Add-MotdLine 'PROCESSES  PID    CPU total (s)    Working set    Name' 'accent'
    if ($Demo) {
        Add-MotdLine '           812           152.4      768.0 MiB    example-worker'
        Add-MotdLine '           946            18.7      128.0 MiB    disk-check'
        return
    }
    $records = New-Object 'System.Collections.Generic.List[object]'
    $processes = @()
    $sampled = 0
    try {
        $processes = @([Diagnostics.Process]::GetProcesses())
        foreach ($process in $processes) {
            if ($sampled -ge [int]$MotdConfig.collection.process_limit) { break }
            $sampled++
            try {
                $cpu = -1.0
                try { $cpu = $process.TotalProcessorTime.TotalSeconds } catch { }
                [void]$records.Add(@{ Pid = $process.Id; Name = $process.ProcessName; Cpu = $cpu; Memory = $process.WorkingSet64 })
            } catch { }
        }
        foreach ($record in @($records | Sort-Object { $_.Cpu } -Descending | Select-Object -First ([int]$MotdConfig.display.top_entries))) {
            $cpuText = if ($record.Cpu -lt 0) { 'unavailable' } else { '{0:N1}' -f $record.Cpu }
            Add-MotdLine ('           {0,-6} {1,12}  {2,13}    {3}' -f $record.Pid, $cpuText, (Format-MotdBytes $record.Memory), $record.Name)
        }
        if (-not $records.Count) { Add-MotdLine '           unavailable (no readable process observations)' 'warning' }
        if ($sampled -lt $processes.Count) { Add-MotdLine ('           Partial sample: ' + $sampled + ' of ' + $processes.Count + ' processes.') 'warning' }
    } catch { Add-MotdLine '           unavailable (process enumeration failed)' 'warning' }
    finally { foreach ($process in $processes) { $process.Dispose() } }
}

function Write-MotdFrame {
    $inner = $MotdWidth - 4
    $border = '+' + ('-' * ($MotdWidth - 2)) + '+'
    Write-Output $border
    $title = [string]$MotdConfig.display.title
    if ($Demo) { $title += ' | DEMO - synthetic observations' }
    $visible = New-Object 'System.Collections.Generic.List[object]'
    [void]$visible.Add(@{ Text = $title; Tone = 'accent' })
    # Reserve the last terminal row for the next prompt, as the Bash renderer does.
    $capacity = $MotdHeight - 4
    $limited = $MotdLines.Count -gt $capacity
    $take = if ($limited) { $capacity - 1 } else { $capacity }
    foreach ($line in @($MotdLines | Select-Object -First $take)) { [void]$visible.Add($line) }
    if ($limited) { [void]$visible.Add(@{ Text = '... more rows omitted; increase -Rows or select fewer sections.'; Tone = 'warning' }) }
    foreach ($line in $visible) {
        $text = ConvertTo-MotdText $line.Text
        if ($text.Length -gt $inner) {
            $end = $inner - 3
            if ([char]::IsHighSurrogate($text[$end - 1])) { $end-- }
            $text = $text.Substring(0, $end) + '...'
        }
        $text = '| ' + $text.PadRight($inner) + ' |'
        if ($MotdColor -and $line.Tone -ne 'normal') {
            $color = if ($line.Tone -eq 'warning') { '33' } else { $MotdAccent }
            $text = [string]$MotdEscape + '[' + $color + 'm' + $text + [string]$MotdEscape + '[0m'
        }
        Write-Output $text
    }
    Write-Output $border
}

# A live baseline has fewer collectors than Bash. Unsupported sections remain
# visible as unavailable; it never invents zero values or claims full parity.
# Collection timings are local-call timings, not a hard renderer wall-clock cap.
Invoke-MotdHooks 'before'
foreach ($section in @($MotdConfig.display.sections)) {
    switch ($section) {
        'system' { Add-MotdSystem }
        'resources' { Add-MotdResources }
        'services' { Add-MotdServices }
        'processes' { Add-MotdProcesses }
        'sessions' {
            if ($Demo) { Add-MotdLine 'SESSIONS   operator (current); full session inventory unavailable' 'accent' }
            else { Add-MotdLine ('SESSIONS   ' + [Environment]::UserName + ' (current); other sessions unavailable') 'accent' }
        }
        'connections' { Add-MotdLine 'CONNECTIONS  unavailable (connection inventory not implemented)' 'warning' }
        'io' { Add-MotdLine 'I/O        unavailable (per-process rates not implemented)' 'warning' }
        'attention' {
            Add-MotdLine 'ATTENTION  Native PowerShell baseline; unsupported observations are unavailable.' 'accent'
            foreach ($message in @($MotdConfig.messages)) { Add-MotdLine ('           ' + $message) }
            foreach ($notice in $MotdNotices) { Add-MotdLine ('           ' + $notice) 'warning' }
            if ($MotdConfig.collection.journal) { Add-MotdLine '           Event log/journal collection unavailable in this backend.' 'warning' }
        }
        'hints' {
            foreach ($hint in @($MotdConfig.hints | Select-Object -First ([int]$MotdConfig.display.top_entries))) {
                Add-MotdLine ('HINT       ' + $hint.label + ': ' + $hint.command + ' - ' + $hint.note)
            }
        }
    }
}
Write-MotdFrame
Invoke-MotdHooks 'after'
'''
# END EMBEDDED PS

if __name__ == "__main__":
    raise SystemExit(entrypoint())
