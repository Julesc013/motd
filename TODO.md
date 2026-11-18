# MOTD implementation and verification checklist

Updated 17 November 2026. A checked implementation item does not certify every
OS; final-source evidence gates remain explicit. See [ROADMAP.md](ROADMAP.md)
and [the audit](docs/audit-2026-11-17.md) for rationale and scope.

## Current change: implementation

- [x] Vendor Tomli 2.3.2 with MIT license, archive/file hashes and primary source
  URLs; embed plain inspectable source without dynamic execution.
- [x] Add valid/invalid TOML, recipe round-trip and actual Python 3.8 tests.
- [x] Implement create-only export with exclusive creation, hash manifest and
  conservative compensation; preserve external edits after failure.
- [x] Test export collisions, partial writes and observed symlink/reparse parents
  under native Python 3.8.20 and 3.12.14 on Linux.
- [x] Implement all five design adapters and independent spacing/detail
  controls, including priority and per-section detail.
- [x] Implement Fish and cmd wrappers without adding another collector core.
- [x] Implement Windows bounded artifact reads, console input, default state
  location and create-only recipe/artifact export CLI paths.
- [x] Require explicit interpreter selection for opaque shell imports; keep
  inspection and safe previews non-executing.
- [x] Preflight generated Unix options before configured before-calls; retain a
  regression test proving invalid arguments do not execute hooks.
- [x] Bound imports before allocation and POSIX target snapshots at 16 MiB;
  reject newlines and C0/C1 controls in managed paths, with path-safety tests.
- [x] Update help and compatibility documentation so Python, export, installation,
  runtime syntax and tested host boundaries are distinct.

## Current change: release gates

- [x] Check canonical runtime and TOML embedding on final sources.
- [x] Run the relevant full suite under the final Python 3.8 configurator and a
  maintained current Python; retain counts, skips, logs and exact source hashes.
- [x] Run all changed backends on available actual historical/current engines.
- [x] Run native Windows PowerShell/cmd/export checks and macOS checks on the
  published commit; retain failures/skips rather than inferring success.
- [x] Verify all requested designs at short/wide/tall geometries with attention,
  whole frames, omission messages and meaningful populated details.
- [x] Resolve final visual-QA context loss in Unix ledger/dashboard: host identity,
  uptime and an explicit demo marker should survive presentation changes.
- [x] Regenerate the 524-case classic gallery after the source freeze.
- [x] Generate the bounded five-design sampler with density/detail contrasts;
  include `runtime/designs.sh` in source provenance.
- [x] Rebuild four wizard-size PNGs and the before/after sample PNG.
- [x] Verify every retained transcript, regenerated artifact, cell grid and PNG;
  inspect representative narrow/tall and wide layouts visually.
- [x] Update the audit verification section and one current release evidence
  record; label earlier records historical.

## Remaining coverage and design decisions

- [ ] Execute actual PowerShell 1.0/3.0/4.0/5.0 harnesses when those hosts are
  available; prepared CI/manual scripts do not count as completed execution.
- [x] Retain the actual PS2/Server2022 evidence and repeat its exact-engine
  harness on the final source; a prior branch result does not verify later edits.
- [ ] Add representative disposable real SSH/PAM/getty and shell/profile
  deployment checks; record exact integration and permission scope.
- [ ] Exercise typed-answer preservation and resizing in a real Windows console,
  including VT-capable screen mode and the old-console line-mode fallback.
  Native cmd/PowerShell/export tests do not perform this interactive check.
- [ ] Keep ACL/xattr/security-label restoration limitations explicit; implement
  additional metadata only for a concrete supported filesystem requirement.
- [ ] Add shared telemetry semantic fixtures across backends where evidence
  reveals drift, rather than introducing a generic collector framework.
- [ ] Evaluate an end-to-end collection deadline separately from per-command
  timeouts; document kernel/WMI initialization and descendant-process limits.
- [ ] Decide whether a native Windows installation engine is required. If so,
  design native handle/ACL/reparse/journal semantics before writing to profiles
  or system settings; do not reuse create-only export as installation safety.
- [ ] Specify and test a native macOS startup/profile installation adapter;
  exported Unix output and a working POSIX file primitive are not that adapter.
- [ ] Specify persistent prompt customization separately from the MOTD greeting;
  preserve existing shell prompt functions, handlers and user settings.
- [ ] Specify per-command/contextual hints and their triggering event before
  attaching completion or command-entry handlers; current hints are display-only.
- [ ] Add csh/tcsh or non-POSIX Bourne targets only with an actual interpreter,
  literal-data quoting tests and the correct startup semantics.
- [ ] Add selected BSD/BusyBox getty, PAM/update-motd, Telnet, RDP or Windows policy
  adapters only for concrete deployment routes, with disposable native tests.
- [ ] Obtain the repository owner's project-license decision; keep vendored
  component notices and historical reference provenance intact.

## Intentional non-goals

Python 3.0 support, universal certification of all operating systems/minor shell
versions, lossless “100% size reduction,” every gallery option crossproduct,
automatic package installation, a daemon and a plugin platform are not implied
by this work. Revisit only with a concrete requirement and evidence budget.
