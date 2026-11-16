# Changelog

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
