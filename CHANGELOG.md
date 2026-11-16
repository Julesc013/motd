# Changelog

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
