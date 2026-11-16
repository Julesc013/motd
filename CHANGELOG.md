# Changelog

## 0.3.0 - 2026-11-16

- Generated Bash files now dispatch to enhanced Linux collection or an embedded
  portable Unix renderer before historical engines parse modern Bash syntax.
  Zsh entry points fall back to `/bin/sh` when `/bin/bash` is absent.
- Portable Unix output now implements the shared nine-section model, adaptive
  geometry, themes, framed ASCII/Unicode output, local collector adapters and
  explicit missing-data states. Historical Bash builds are executed in tests;
  source/build qualifications are retained in the verification record.
- Native PowerShell uses PowerShell 1-era grammar and data-only literal recipe
  encoding, with guarded WMI/CIM/.NET capability paths and more detailed native
  collectors. PS1–4 are targeted, not execution-verified. Actual PS6, PS7 LTS,
  current PS7 and Windows5.1 are distinct verification environments.
- Workshop and home-lab examples are generated for Bash, Zsh, sh and PowerShell.
- Actual-PTY PNG gallery: 512 dashboard cases plus 12 static notices, covering
  four terminal sizes, four themes, ASCII/Unicode and colour/plain output.
  Retained recipes/transcripts, source/engine/pixel hashes, lossless optimization,
  deduplication, an HTML filter and original-pixel size comparisons make the
  screenshots reproducible and inspectable.
- Add macOS native-host CI and retained-gallery integrity verification. The
  installer still targets Linux; other login-surface integrations remain explicit
  contracts rather than inferred support for every OS and transport.

## 0.2.0 - 2026-11-16

- Page-by-page terminal wizard with synthetic previews, grouped settings,
  navigation and a line-interface fallback; `--ui auto|screen|line`.
- Additive schema1 `shell` setting and `--shell bash|zsh|sh|powershell`.
- Zsh launcher/integration reuses the Bash renderer and declares that dependency.
- Reduced native POSIX-sh and native PowerShell output templates. Collector
  coverage and version boundaries are documented rather than assumed identical.
- Generic static `text` export for explicitly chosen consumers/destinations.
- Compatibility and surface specification covering other gettys, PAM, SSH,
  existing Telnet sessions, RDP, Windows profiles/policy and legacy platforms.

The configurator and transaction engine remain Linux-specific. Native PowerShell
generation does not imply automatic Windows or PowerShell-profile installation.
Exact tested interpreters and host limitations belong in the verification record.

## 0.1.0 - 2026-11-16

Initial development version for `Julesc013/motd`.

- One Python 3.11+ configurator with an embedded, readable Bash runtime.
- Action-first wizard and equivalent command-line build/preview/management paths.
- TOML recipes; workshop, home-lab and public-console starting presets.
- Standalone Bash outputs and literal public issue/SSH-banner exports.
- Before/after argv calls with explicit timeouts and failure policy.
- One adaptive display interface replacing public concise/verbose modes.
- Read-only plans, private configuration/output archives, journalled file changes,
  drift detection, installation audit, missing-file repair, uninstall and undo/recovery.
- Original Workshop 1.2.0 and home-lab files preserved unchanged in `reference/`.

This version is a tested starting point. Real machine SSH/agetty/systemd
integration, root-specific ownership restoration and non-Linux execution are
not established by the temporary-directory test suite.
