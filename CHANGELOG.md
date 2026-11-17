# Changelog

## 0.4.0 - 2026-11-17

- Add five genuinely different presentation structures: classic, cards, ledger,
  briefing and dashboard. Separate density, detail, padding, section gaps, colour
  emphasis, retention priority and per-section detail from theme selection.
  Preserve classic defaults for older recipes, allow 8–200 saved rows, reserve
  a prompt row and name whole sections omitted under space pressure.
- Share the Unix presentation engine between enhanced Bash and portable sh;
  keep native PowerShell on the same layout contract. Dashboard panels pair on
  wider terminals and stack on narrow ones. Fix briefing summaries so they do
  not discard the first meaningful service/network observation.
- Add Fish and Windows CMD launch adapters over the existing renderers, plus
  literal ASCII `batch-text` notices without PowerShell or live collection.
  Add the data-only `motd:print` before/after operation.
- Make wizard choices descriptive, add context help and arrow selection,
  preserve ten control rows and live resize, and buffer only changed rows.
  Add Windows console-input/VT capability handling and platform-aware menus.
  Cold interpreter startup remains a documented performance boundary.
- Lower the configurator floor to actual Python 3.8, using bundled readable,
  MIT-licensed Tomli 2.3.2 on versions without standard-library `tomllib`.
  Python 3.0 is not claimed. Add create-only exports and hash manifests for
  Windows and other trusted-directory generation workflows.
- Bound source reads to 2 MB and transaction snapshots to 16 MiB per file;
  reject terminal-control/newline paths before writes; require an explicit
  interpreter for opaque executable imports; validate runtime options before
  invoking configured hooks.
- Expand actual-engine and native-host verification, including a standalone
  historical PowerShell harness and an exact-version PS2 CI probe. The evidence
  records distinguish real passes, skips and blocked engines; PS1/3/4/5.0 and
  untested OS releases are not certified by modern parser compatibility.
- Refresh the original 524-case terminal gallery and add a fixed 140-case
  design/density/detail sampler with retained PTY transcripts, source hashes,
  original-pixel comparison sheets and lossless PNG verification.
- Update the specification and compatibility contracts; add a dated audit,
  decision record, implementation roadmap and concrete outstanding work.

## 0.3.0 - 2026-11-17

- Keep wizard questions in ten fixed control rows and re-render the remaining
  viewport while the terminal resizes, preserving a partially typed answer.
  Paginate long menus and support compact 8–200-row runtime overrides without
  cropping complete dashboard sections or borders.
- Optional before/after sample previews include Fastfetch and per-call literal
  preview_text, remain hidden by default, and never execute configured commands.
  Five wizard PNG views demonstrate the four requested sizes and call samples.
- Save character-set and colour defaults in TOML and expose them in the wizard.
  Runtime flags remain explicit overrides; NO_COLOR and mono suppress colour.
- Fix malformed Darwin memory-query results being treated as zero, and apply
  shared required/excluded service rules to native PowerShell service providers.

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
