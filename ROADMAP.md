# MOTD roadmap

Updated 17 November 2026. This is a delivery sequence with evidence gates, not a
promise of support for every historical or future OS. The detailed assessment is
[the portability and architecture audit](docs/audit-2026-11-17.md).

## Product boundary

Maintain one downloadable Python configurator, a portable TOML recipe and
standalone generated outputs. Generation happens once; login does not need
Python, package installation, a network connection or a background service.
Capability differences stay visible. Installation safety must not be weakened to
make a platform list longer.

## 1. Finish presentation and practical portability

Deliver classic, cards, ledger, briefing and dashboard as different structures.
Keep density, detail, per-section detail, padding, section gaps, emphasis and
allocation priority independently configurable. Wide dashboards can use paired
cards; narrow layouts must preserve whole sections and explain omissions.

Support Python 3.8+ for configuration through a plain licensed TOML fallback;
use the standard library parser where available. Keep native Windows reads,
input and create-only export usable while describing automatic installation's
separate platform boundary. Fish and cmd entry points reuse existing collectors.

Completion evidence:

- Native Python 3.8 generation, round-trip parsing and relevant CLI tests.
- Current and historical shell geometry tests for changed renderers.
- Native PowerShell and Windows wrapper/export/input jobs with exact versions.
- The original 524-case classic gallery rebuilt from frozen sources.
- A bounded design sampler covering five styles, four sizes and representative
  backends/presets, plus density/detail contrasts; all transcripts and PNG hashes.
- Wizard frames at the four sizes, including safe before/after sample mode.

The local implementation and retained verification gates above are complete for
0.4.0: 524 classic cases, 140 sampler cases, five wizard frames, native Python
3.8/current-Python suites, and the recorded shell/native-host matrices. See
`build/verification-gallery-v04.json` and the audit for exact hashes, counts,
skips and the example-builder qualification on the current-Python run. Native
interactive Windows console resizing remains an explicit coverage gap below.

## 2. Close the highest-value native coverage gaps

Run the legacy PowerShell harness on actual 1.0, 3.0, 4.0 and 5.0 engines
when those environments are available. Retain and repeat the actual PS2/Server
2022 check obtained during this review for the final source. A prepared harness is not a test pass.
Record host OS, engine, encoding, terminal capability, source hashes and skipped
collectors. Investigate actual failures before widening a support claim.

Add representative real login deployments in disposable systems: one Linux
profile integration, one SSH/PAM path, one getty/static notice, macOS shell
startup, and Windows PowerShell/profile or cmd usage. Test the selected workflow
and permissions; do not infer all distributions from it.

Keep contributor setup optional: normal generation must not acquire gallery,
historical-engine or test dependencies.

Drive the wizard in a real Windows console, resizing with a partially typed
answer, and check its old-console line-mode fallback. Pure frame rendering and
native cmd/PowerShell/export jobs do not establish that interactive behavior.

## 3. Add only explicit, tested integration adapters

Native macOS profile installation is separate from running the existing Unix
output there. It needs startup-file selection, existing customization preservation
and tested upgrade/uninstall behavior. Windows profiles, CMD AutoRun and sign-in
or RDP policy routes are separate mechanisms, each requiring an explicit scope
and native safety contract. A text export must never imply that a service or
policy was configured.

Persistent shell prompts and per-command hints are also separate from an arrival
MOTD. First specify which shell event and information the user wants, how an
existing prompt/completion system is preserved, and whether any command runs.
Keep prompt work lightweight and avoid collecting the whole dashboard per
command. Implement one demonstrably useful native adapter with reversible
ownership before expanding to another shell.

Treat csh/tcsh and older non-POSIX Bourne shells as separate grammar/startup
targets. Invoking a compatible exported sh script manually can already be useful,
but is not proof of native generation or installation support. A future native
adapter needs an actual engine and startup test; do not duplicate the collector
merely to add an entry point.

## 4. Harden remaining bounded correctness risks

Retain the implemented 16 MiB POSIX snapshot limit and bounded import reads, with
their negative tests. Document exactly which file metadata is restored. Add ACL/xattr preservation
only with a concrete requirement, filesystem semantics and tests; do not imply
it from a byte-for-byte rollback test.

Use small common telemetry fixtures to check meaning across backends: missing,
partial and stale data; CPU sampling intervals; process memory; disk I/O scope;
service filtering and permission failures. Add a total collection time budget
only when all subprocess and descendant semantics can be bounded honestly.

If native Windows installation becomes a confirmed requirement, first design
handle-based path checks, reparse-point policy, ACL/ownership behavior, crash
recovery and profile ownership. The create-only exporter is not a starting
transaction engine and must not silently grow into one.

## 5. Keep maintenance proportional to the product

Check canonical runtime/TOML embedding in CI and build examples mechanically.
Keep one current release evidence index; retain older logs with historical scope.
Review the vendored parser pin through its documented license/provenance/update
procedure. Review the current Python floor periodically without claiming that
running on an end-of-life interpreter makes that interpreter maintained.

Split stable source components only when the boundary improves review and
reduces actual duplication. Continue distributing one inspectable file. Avoid a
daemon, plugin platform, web designer or package repository unless an explicit
new use case justifies that independent product.

The repository owner must choose project licensing terms before the project is
described as openly licensed. Vendored component licenses remain intact.
