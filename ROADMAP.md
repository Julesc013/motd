# MOTD roadmap

Updated 17 November 2026. This is a delivery sequence with evidence gates, not a
promise of support for every historical or future OS. The detailed assessment is
[the portability and architecture audit](docs/audit-2026-11-17.md). The
[discussion and design review](docs/discussion-and-design-review-2026-11-17.md)
traces the complete supplied history, superseded proposals, the interrupted
v0.4 delivery and the newer bar/field/localization requests.

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
Those records describe their own source hashes. Follow-up runtime/generator
changes require relevant new checks and refreshed artifact provenance; an old
checked gate does not certify a changed tree. The continuation reconciled remote
refs, local sources and retained galleries, then published the complete tree.
Its corrected implementation commit `0f16e88` passed all nine native CI jobs;
the [current evidence index](build/verification-review-20261117.json) retains
the initial failure, correction, exact engines and final gallery verification.

### Readability follow-up

The shared suffix-registry correction and required-service deduplication are
implemented. The current review verifies complete build/export/install paths for each generated output
suffix, including Fish and CMD, and preserves distinct missing/inactive/unavailable
service findings. A generation-only test does not exercise archival validation.

Inline/wide bars now use existing numeric observations through the recipe, CLI,
wizard and renderer routes. Current-source checks cover bounds, row budgets,
accounting meanings and unavailable states. A dashboard gauge fills its own
panel. Defer a common
field/heading override contract to the text-policy work below; the existing
Bash item registry does not establish cross-backend field support.
Inspect 40/80-column short/tall output and wide paired panels, not only line counts.

The [beginner walkthrough](docs/quickstart.md) now covers destination choices,
visible keys and the save/build/reopen path. Screen choice hints explain preview
then acceptance; line-mode previews include opted-in call samples. Shared batch
validation preserves the prior draft on invalid Unicode edits, static previews
display terminal controls visibly, and interactive reconfiguration always runs
UI cleanup. The [current review evidence](build/verification-review-20261117.json)
records the combined-source local suite and regenerated visual evidence;
native workflow results and publication status remain separately identifiable.

Record cold preview, cached choice and resize latency separately. Preserve the historical live-runtime aspiration
of less than 100 ms (ideally nearer 10 ms) and the controlled-stall 400 ms target
as measured goals on named hosts, with coverage and fallback counts disclosed.
No historic Workshop1.2 benchmark establishes current-release performance.
The current [synthetic baseline](build/review-20261117/synthetic-render-benchmark-20261117.json)
measured 20 fresh processes per route after a warmup on one Linux host: median
45.8 ms for Bash, 10.1 ms for sh/dash and 625.1 ms for PowerShell 7.6.10. Those
include startup/render/capture, not live queries or interactive redraw. Profile
those components separately before applying one latency promise to every route.

## 2. Close the highest-value native coverage gaps

Run the legacy PowerShell harness on actual 1.0, 3.0, 4.0 and 5.0 engines
when those environments are available. The final-source PS2/Server 2022 check
passed 81/81 cases on the actual 2.0 engine; retain that evidence and repeat it
when its runtime changes. A prepared harness is not a test pass.
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

## 6. Localize presentation without changing observations

Implement a small reviewed message catalog and stable field IDs before claiming
localized UI or data formatting. Bounded literal heading overrides are a proposed
extension at that stage, not part of the immediate wide-bar correction.
Raw numbers, units, identities, timestamps and
availability stay separate from translated labels. Parse a supported invariant
provider format before human formatting; never translate rendered output with
regular-expression substitutions or localize command/path data.

Resolve catalogs at generation time where practical and embed only needed data.
Publish requested/effective locale and an explicit exact-locale, declared
language-fallback, English-fallback policy. Missing translations must be visible
in inspection; invalid placeholders must fail generation. No runtime download or
mandatory destination-side locale package should be introduced.

Use terminal-cell widths and supported grapheme boundaries for any general
Unicode claim. Retain an explicit ASCII/legacy policy; combining text, CJK,
ambiguous widths, emoji sequences and right-to-left layout need their own cases.
A Unicode border setting or custom heading is not full localization. The
[discussion review](docs/discussion-and-design-review-2026-11-17.md#6-internationalization-and-localization-policy)
defines the detailed policy and minimum acceptance cases.

## 7. Keep earlier Python as a recorded feasibility request

Python3.8 is the implemented lower boundary, with actual execution evidence.
The request to explore Python3.0 and intervening versions remains deferred;
it has not been rejected by the user or demonstrated feasible. A lower floor
requires an inventory of syntax/library/OS dependencies, a measured deployment
benefit and real-engine tests of generation and any claimed filesystem behavior.
Do not weaken the transaction engine merely to lower a version guard. Generating
on a supported machine and copying standalone outputs remains the preferred
route for destinations that cannot run the configurator.
