# MOTD implementation and verification checklist

Updated 17 November 2026. A checked implementation item does not certify every
OS; final-source evidence gates remain explicit. See [ROADMAP.md](ROADMAP.md)
and [the audit](docs/audit-2026-11-17.md) for rationale and scope. The
[discussion review](docs/discussion-and-design-review-2026-11-17.md) preserves
requirements from the complete transcript and the subsequent design requests.

## V0.4 foundation: recorded implementation

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

## V0.4 foundation: retained verification

The checked items below refer to the source hashes and runs retained in the
v0.4 records. They do not automatically certify the continuation's later source
edits; its relevant follow-up gates are listed separately below.

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

## Continuation: implemented and locally verified

- [x] Reconcile the complete supplied transcript with the current documentation;
  retain the simplification decision and superseded Go/concise-verbose proposals.
- [x] Unify artifact suffix selection and archive validation for Fish/CMD and
  literal batch outputs; deduplicate required-service observations by identity.
- [x] Add `display.bar_layout = "inline" | "wide"` to recipe, CLI, wizard and
  runtime controls, reusing existing observations and retaining numeric labels.
- [x] Explain preview-then-accept in 40-column screen menus; show supported input
  keys in line mode and include opted-in before/after samples in its full preview.
- [x] Enforce batch notice ASCII in shared configuration validation so invalid
  imported recipes fail early and invalid wizard edits preserve the prior draft.
- [x] Display static preview control characters visibly while preserving exact
  imported/exported bytes; always finish the UI on interactive reconfiguration.
- [x] Add the [beginner walkthrough](docs/quickstart.md) for create, preview,
  save, build and reopen, with explicit temporary-workspace CLI output paths.

The [current review evidence](build/verification-review-20261117.json) records
258 local tests (247 passed, 11 explicit skips), actual Python3.8 lifecycle
checks, 360 additional Unix cases and 712 retained gallery captures. Native
workflow and publication status are recorded separately in that same index.

## Remaining coverage and design decisions

- [x] Verify the follow-up suffix-registry correction through ordinary export,
  archive and supported installation paths for Fish/CMD as applicable; preserve
  the unsupported Windows managed-installation boundary.
- [x] Verify required-service findings are unique by canonical identity without
  merging missing, inactive and query-unavailable states.
- [x] Verify inline/wide resource bars across available backends,
  accounting for framing/padding/row budgets without adding collectors.
- [x] Run final-source regressions for narrow menu instructions, safe line-mode
  samples, invalid batch edits/imports, static control previews and cancellation
  cleanup; preserve installation state when reconfiguration is cancelled.
- [ ] Design and later verify cross-backend fields and bounded section-title
  overrides under an explicit text/width policy; preserve stable IDs and reject
  controls/multiline headings. The Bash item registry alone is not this contract.
- [x] Exercise the documented novice save/build/reopen path in a temporary directory.
- [ ] Measure cold preview, cached selection and resize latency with exact host/backend details.
- [ ] Reconcile the interrupted publication against remote refs and local staged
  artifacts; publish exact current evidence and refresh changed-source galleries.
- [ ] Measure current-source live/render performance against the historical
  <100 ms aspiration and 400 ms controlled-stall target on named hosts. Retain
  sample counts, timings, coverage, unavailable data and fallback counts.

- [ ] Execute actual PowerShell 1.0/3.0/4.0/5.0 harnesses when those hosts are
  available; prepared CI/manual scripts do not count as completed execution.
- [x] Retain the actual PS2/Server2022 evidence with its original source scope.
- [ ] Repeat the PS2 exact-engine harness on the final source; a prior branch
  result does not verify later edits.
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
- [ ] Specify static public hardware inventory separately from literal notices:
  field allow-list, generation timestamp, manual/boot refresh, optional captured
  Fastfetch, ownership and actual consumer attachment tests.
- [ ] Preserve shared-account session identity and resource-accounting semantics
  in shared fixtures while extending field selection and designs.
- [ ] Introduce stable untranslated field/message IDs and reviewed catalogs;
  keep typed values, units, availability and identity separate from labels.
- [ ] Implement and test explicit locale fallback and requested/effective-locale
  reporting; fail invalid placeholders and preserve literal commands/paths.
- [ ] Test English and one reviewed additional locale through config, wizard,
  generation and output; use invariant provider inputs before localized format.
- [ ] Define and test terminal-cell/grapheme handling for claimed Unicode paths,
  including long labels, combining text and CJK; keep ASCII fallback explicit.
- [ ] Keep RTL shaping/order, ambiguous widths, emoji and old code pages marked
  unverified until actual terminal fixtures and visual checks establish support.
- [ ] Evaluate Python3.0–3.7 feasibility only with a concrete deployment benefit,
  language/API inventory and actual-engine tests; retain Python3.8 as the current
  implemented minimum until that evidence exists.
- [ ] Obtain the repository owner's project-license decision; keep vendored
  component notices and historical reference provenance intact.

## Intentional non-goals

Universal certification of all operating systems/minor shell versions,
lossless “100% size reduction,” every gallery option crossproduct,
automatic package installation, a daemon and a plugin platform are not implied
by this work. Revisit only with a concrete requirement and evidence budget.

Earlier Python support is a deferred feasibility request rather than an
intentional permanent exclusion. The implemented floor and evidence remain
Python3.8+; neither this checklist nor a lower version guard establishes 3.0 support.
