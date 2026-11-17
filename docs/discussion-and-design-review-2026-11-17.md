# Discussion review, design direction and continuation plan

Review date: **17 November 2026**. This document reconciles the complete supplied
conversation, the published v0.3 baseline, the interrupted v0.4 work, and the
subsequent request for wider bars, richer field selection and internationalization.
It supplements the [implementation audit](audit-2026-11-17.md), which retains the
detailed v0.4 findings and execution records. It does not replace those records or
turn earlier test results into evidence for later source changes.

## 1. Assessment

The project has a useful architecture worth extending: one inspectable Python
configurator, readable recipes, a small set of canonical runtime sources, and
standalone generated files. Workshop and home-lab are profiles over those
sources. The strongest next improvement is to make presentation and capability
choices clearer while completing the delivery and verification of the work
already present.

The original dense frame is one valid design. It should not determine every
presentation. The five v0.4 structures create meaningful alternatives, but
readability also depends on which facts appear first, how labels and values are
aligned, how much detail survives, and whether the eye can find a problem without
reading every abbreviation. More themes alone cannot settle that question.

The long-term goal is broad, explicit support for useful message surfaces.
Compatibility has several independent dimensions: generator Python/OS,
destination interpreter, available collectors, terminal/encoding, and the actual
login or prompt attachment. A successful render proves only part of that matrix.
The appropriate product promise is a growing set of verified combinations with
declared limits. It cannot be a promise about every untested past or future
computer.

### Evidence language used here

- **Observed:** directly present in the supplied transcript or reviewed repository.
- **Recorded execution:** an existing record identifies a command, source and
  environment. Its exact scope must be checked before being reused.
- **Design decision:** a maintainability or product recommendation adopted for
  continuation; it is not a claim of implementation.
- **Open:** a requested capability or verification gate remains incomplete.

The transcript contains 3,349 lines, including the earlier user's requests and
the v0.4 development updates. Its final entry stops during artifact publication,
after the reported gallery completion. The review therefore treats the existing
v0.4 branch and staged artifacts as work to reconcile and finish, rather than
starting another implementation of the same features. The transcript itself is
historical input; statements such as “tests passed” need matching repository or
CI evidence before becoming a current release claim.

## 2. Requirements lineage and decisions

This table preserves the intent of the successive requests. Later directions
supersede conflicting earlier proposals; they do not erase useful data and safety
requirements.

| Stage / request | Durable requirement | Present disposition |
|---|---|---|
| Static agetty inventory, 15 November | Keep pre-login inventory separate from the live authenticated dashboard; optionally capture Fastfetch once when generating inventory. | Static public output exists. The historic hardware-inventory generator and boot lifecycle are not equivalent to the current literal `public-console` preset; a managed inventory-refresh adapter remains separate work. |
| Wide memory, storage, services and hints, 16 November | Full-width sections, meaningful resource bars, logical service groups, optional attention, copy-one-file delivery. | The enhanced Linux renderer retains detailed observations. The continuation adds inline/wide bar placement across the existing renderer routes without changing the underlying resource meanings. |
| Workshop operational view | Host/domain/IP, common services, CPU/memory tasks, sessions, connections, issues and useful commands; AI is not the workshop emphasis. | Workshop and home-lab are presets. Collector capabilities vary by backend and host. |
| Process disk I/O and shared workshop account | Include I/O rankings; retain distinct session identities even when usernames match. | The enhanced Linux implementation has the richer sampled I/O path. Portable and PowerShell counters have different declared meanings. A username or socket count alone cannot identify a person. |
| Fast 25–50-row view | Fit useful detail into short terminals; target less than 100 ms where feasible, ideally nearer 10 ms, and test controlled stalls against 400 ms. | Responsive budgets exist. These numbers remain performance aspirations and test criteria on named hosts, not universal elapsed-time guarantees. Historical timing results do not measure v0.4. |
| Correction to “concise” | Preserve alignment, sections, framing and semantic colour; shorten content and record lists to fit. | The planner should remove optional detail or whole lower-priority sections deliberately and identify omissions. Losing structure merely to fit more text contradicts this request. |
| Unified repository proposal | One permanent home for source, reusable presets, tests, examples, documentation and future improvements. Remove the binary concise/verbose product split. | Implemented repository structure; density and detail are independent presentation controls. |
| Simplification decision | Avoid a large new platform. Use one downloadable configurator producing standalone shell scripts and static text; start from working code. | This supersedes the earlier provisional Go/native-runtime plan. Python is configuration-time work; the generated greeting does not need it. |
| Action-first lifecycle wizard | Create/install/import/reconfigure/inspect/audit/repair/recover/rollback/uninstall; preview and review before applying; recover recipes and keep archives. | Implemented for declared Linux managed-installation paths. Cross-platform create-only export has a narrower contract. |
| Explicit before/after calls | Literal argv, per-call behavior, optional Fastfetch and multiple calls; no hidden execution during preview or import inspection. | Shared hook contract, sample previews and literal `motd:print` action exist. Arbitrary opaque code remains a separately trusted execution path. |
| Historical shells and alternative login mechanisms | Broaden exact engine/OS evidence and specify non-agetty, SSH, Telnet, RDP and other consumers. | Version-specific execution and adapter contracts exist; several original systems and attachment routes remain open. |
| Four-size PNGs and fixed wizard questions | Real output at 40×25, 40×50, 80×25 and 80×50; ten control rows; preview responds to live resize; optional pre/post samples. | v0.3 introduced these; v0.4 retained captures and improved interaction. Current-source hashes, native-console scope and visual review remain independent gates. |
| Distinct designs and adjustable density | Offer structurally different designs with independent padding, gaps, detail, colour emphasis and retention priority. | v0.4 implements classic, cards, ledger, briefing and dashboard through shared backend observations. Inline/wide bar placement is implemented in the continuation; richer presentation labels/fields remain proposed. |
| Older cross-platform configurator | Explore Python compatibility down to 3.0 where practical; retain understandable, auditable code and robust writes. | Python 3.8 is the implemented lower boundary. Earlier Python remains a deferred feasibility request, not an owner-rejected idea or a current support claim. |
| Internationalization and more fields, latest request | Separate stable data from language and visual form; support explicit localized presentation without breaking older systems. | This document defines the extension policy. Full translated UI/catalogs and comprehensive Unicode layout are not implemented by a title override or Unicode border setting. |

The simplification request explicitly authorized use of `julesc013/motd`, with a
complete extractable package as a fallback if committing was unavailable. It did
not authorize changing users' real login services, execution policy, registry,
or authentication settings merely to demonstrate portability.

## 3. What to keep, and what to avoid repeating

### Keep the current division of responsibilities

1. **Configuration:** validate and normalize a recipe once; keep CLI and wizard
   on the same schema and plan functions.
2. **Collection:** obtain supported local observations with explicit units,
   identities, coverage and unavailable states.
3. **Interpretation:** calculate rates, thresholds and summaries using declared
   semantics. Do not mix cumulative values with interval rates.
4. **Presentation:** choose labels, visible fields, gauges, tables and section
   structure from the existing observations.
5. **Allocation and encoding:** account for cells, rows, borders, gaps, output
   capabilities and consumer-specific escaping.
6. **Delivery and installation:** generate portable files; attach them only
   through a supported ownership and recovery contract.

These responsibilities do not require six new frameworks or a file per field.
Use the existing modules until a stable boundary makes an extraction useful.
Build-time embedding preserves convenient one-file delivery without requiring
all maintenance to occur in one enormous hand-edited string.

The full Linux, portable Unix and native PowerShell backends have real platform
differences. Their existence is not automatically needless duplication. The
maintenance risk is duplicated policy and metric meaning drifting between them.
Use a small common contract and shared semantic fixtures. Zsh, Fish and CMD
entry points should continue to delegate to a compatible core instead of growing
another copy of the collectors.

### Superseded proposals

- A new Go or Rust telemetry engine was a candidate in the earlier research
  draft, not the final selected direction. Revisit only for a measured problem
  that cannot be solved proportionately in the existing design.
- The earlier concise/verbose split should not become two divergent products.
  Density, requested detail, collection policy and viewport are separate choices.
- An 80-column cap and a cyan outer frame were early defaults, not permanent
  requirements for all users or designs.
- A mandatory daemon, plugin host, package service, web designer or automatic
  updater has not been justified by the current use case.

## 4. Current scope and open gaps

The [compatibility guide](compatibility.md) and [v0.4 audit](audit-2026-11-17.md)
contain exact retained engine versions, source hashes and test counts. The table
below explains the remaining product boundaries without duplicating those totals.

| Area | Existing capability | Remaining work |
|---|---|---|
| Design choice | Five structures, separate density/detail, padding, gaps, emphasis, order and retention priority; inline/wide resource bars. | Complete fresh-source verification and visual review, evaluate scanability with representative tasks, and specify richer fields/labels. |
| Wizard | Descriptive choices, contextual help, explicit preview-then-accept hints, changed-row redraws, synthetic previews, safe line-mode call samples and a beginner walkthrough. | Fresh-source checks, a real Windows-console resize/input session and measurable cold/cached preview and redraw latency. |
| Unix outputs | Enhanced Linux path, portable core, actual historical Bash/Zsh and selected ash/ksh/Fish evidence. | Original historical OSes, Zsh1, earlier/non-POSIX Bourne variants, native csh/tcsh adapters and additional actual startup routes. |
| PowerShell | Native 2.0, 5.1, 6 and 7 evidence retained in v0.4 records. | Actual 1.0, 3.0, 4.0 and 5.0 engines; a later patch or 5.1 test cannot fill those rows. |
| Windows batch | PowerShell-backed CMD dashboard and separate literal ASCII NT-CMD notice. | Native DOS `COMMAND.COM`, Windows9x and OS/2 code-page/command-processor tests. |
| Generator | Python3.8+ with bundled readable TOML parser; portable generation and create-only export. | Older-Python feasibility, and native OS-specific lifecycle testing for any wider installer claim. |
| Managed installation | Linux transaction journal, backups, drift checks, repair, recovery, rollback and removal. | Windows/macOS native attachment and metadata contracts; actual SSH/PAM/getty service deployments. |
| Broader message surfaces | Static notices, authenticated greetings and displayed hints. | Persistent prompts, per-command hints, desktop/RDP notifications and sign-in policy adapters are separate features. |
| Fields and internationalization | User-provided text, a backend-specific Bash item registry and character/colour choices, with documented legacy text limits. | A cross-backend field/label contract, message catalogs, locale negotiation, localized formatting and verified grapheme/cell behavior. |
| Performance | Bounded full-Linux collection and per-operation protections elsewhere; preview cache. | Final-source comparative measurements, portable/PowerShell whole-render policy and cold-preview latency. |

### Independent follow-up findings

The continuation review found concrete user-path defects beyond the earlier audit:

- **Output suffix drift:** Fish/CMD generation existed, but the transaction's
  accepted artifact-suffix list had not expanded consistently. A supported
  generated file could therefore fail when entering an ordinary export or
  installation workflow. The correction gives output selection and archival
  validation one suffix registry. Acceptance must exercise generation through
  the real export/install path, not only call the generator directly.
- **Repeated required-service diagnostics:** overlapping service discovery and
  required-service checks could repeat the same missing-service observation.
  The correction keeps one observation per canonical identity while still
  distinguishing an unavailable query, a missing definition and an inactive
  required service. Deduplication must not hide different failures.
  A follow-up fixture also exposed names containing a colon: splitting at any
  colon merged `foo:one.service` and `foo:two.service`. All four portable name
  extractions now use the actual `: ` row delimiter. The regression covers
  distinct names, overlapping requirements, promotion and exact exclusions
  across all five designs.
- **Choice instructions disagreed with behavior:** screen menus with a live
  choice preview require number-plus-Enter to preview, then Enter to accept.
  Compact instructions now explain both steps, including paginated 40-column
  menus. Line-mode menus no longer advertise unavailable arrow selection.
- **Line-mode call samples were omitted:** toggling sample calls affected the
  screen interface but not the line-mode full preview. Both now display opted-in
  literal before samples, the synthetic MOTD and after samples in order, without
  executing the configured commands.
- **Batch-notice errors arrived too late:** Unicode text could survive recipe
  validation and fail during generation after editing. The shared validator now
  enforces native batch text's ASCII boundary before accepting a draft edit or
  imported recipe. Invalid edits leave the prior draft intact.
- **Imported static preview controls reached the terminal:** the display path
  now renders terminal controls visibly rather than applying their effects.
  Imported and exported artifact bytes retain their exact content; this is a
  preview-display policy, not a rewrite of consumer-specific serialized data.
- **Interactive reconfiguration skipped final UI cleanup:** the CLI path now
  calls the same `finish()` cleanup in a `finally` block as the main wizard,
  including when editing is cancelled. This restores the console output mode
  where applicable and leaves the cursor after the wizard grid.

These are evidence for testing complete user paths and semantic identities. A
passing layout matrix alone cannot reveal a downstream archive-validation error.
The exact corrected-source checks belong in the continuation's verification
record under `build/`; earlier totals are not assertions about these fixes.
These corrections and the wide-bar setting are implemented. Final combined
source verification and regenerated gallery provenance are now recorded in the
[current review evidence](../build/verification-review-20261117.json): 258 local
tests (247 passed, 11 explicit skips), 59 actual Python3.8 lifecycle checks
(58 passed, one root-only skip), 360 additional Unix cases and 712 gallery
captures. PowerShell6.2.7 and7.6.10 each passed81 harness cases; every executed
PowerShell artifact was regenerated byte-for-byte from the final generator
after subsequent Unix-only edits. Native workflow/publication status is tracked
in the [publication addendum](#11-publication-and-native-ci-addendum); these counts
do not establish unavailable historical hosts.

## 5. Presentation and field contract

### Structural alternatives should answer different reading tasks

| Presentation | Reading task | Useful emphasis |
|---|---|---|
| Classic | Scan a dense operational overview familiar to existing users. | Stable aligned sections, compact labels and complete frames. |
| Cards | Find one topic without reading a continuous wall of text. | Clearly separated headings, moderate whitespace and local summaries. |
| Ledger | Compare names and values in predictable positions. | Open rows, strong label/value alignment and restrained decoration. |
| Briefing | Understand what needs attention on arrival. | Host context, actionable summary, followed by optional detail. |
| Dashboard | Compare several categories when columns are available. | Paired panels and prominent resource indicators; stack on narrow screens. |

The implemented `display.bar_layout = "inline" | "wide"` setting consumes the
same numeric observations. An inline bar trades horizontal length for a shorter
section; a wide bar places its label/value and gauge on separate rows using the
panel's available content width. CLI generation accepts `--bar-layout`; generated
Unix outputs accept the same switch, and PowerShell accepts `-BarLayout`.
The wizard exposes Usage bars under Characters and colour. Existing recipes
retain `inline` by default. No additional memory/disk collector or greater
measurement precision is implied. Row allocation retains a numeric reading
when there is not enough space for its gauge.

“Full width” means the available width after that design's borders and padding,
not an instruction to overwrite an adjacent panel or the terminal edge. In a
paired dashboard, the gauge fills its own card. A future section that spans both
columns would be a separate explicit layout decision.

### Prefer a small vocabulary of fields and views

A useful extension model is a small set of presentation primitives: key/value
facts, percentage or allocation gauges, aligned tables, lists, and notices.
Do not add an arbitrary layout programming language merely to rearrange these.
Stable field IDs can later expose visibility, ordering, label and format options
without creating another collector per style.

Use the following field policy for new work:

| Property | Required meaning |
|---|---|
| Identity | Stable untranslated ID such as `resources.memory_available`; never use its current English label as the lookup key. |
| Value | Typed number, boolean, timestamp, duration, state, identifier or text. Avoid storing a decorated string as the only copy of a measurement. |
| Unit and scale | Explicit bytes/KiB, seconds, percent, count, bytes/second, or another defined unit; preserve the denominator and sample interval. |
| Availability | Present, unavailable, partial or stale with a useful reason where available; never coerce an unknown value to zero. |
| Scope | Relevant host/namespace, process identity, filesystem/device identity or session identity, with coverage limits. |
| Label | A catalog key or bounded literal override, separately encoded and measured for the destination. |
| Presentation | Preferred view, alignment and useful minimum/maximum width; a request subject to viewport allocation. |
| Visibility and priority | Independent from collection and health policy; hiding a field should not silently disable a required-service check. |

This is a continuation contract, not a claim that the current backends already
implement a single typed record schema everywhere. Introduce it at boundaries
that currently duplicate meaning. Keep the representation small enough for
legacy shells; no JSON parser, Python runtime or locale database should become
a mandatory dependency of every generated MOTD.

Bounded section-title overrides are a proposed later step, not implemented by
this continuation. The Bash backend's existing item registry is not a common
cross-backend field contract. Future label overrides should change
presentation labels while preserving section IDs, order, priority and collector
meaning. They are not equivalent to translating every value, state, hint or
wizard message. Reject terminal controls and ambiguous multiline headings before
generation; apply each interpreter's literal-data encoding.

## 6. Internationalization and localization policy

**Status: design policy for subsequent implementation.** The current release
must not advertise complete localization, right-to-left layout, emoji-safe
truncation or universal Unicode support because it accepts a Unicode string.
Internationalization is the architecture that makes localization possible;
localization supplies and verifies a particular language/formatting experience.

### Stable data, translated labels

1. Keep configuration keys, section/field IDs, internal states, metric units and
   machine-readable evidence stable and locale-independent.
2. Give user-facing messages stable catalog IDs. Translate full phrases or
   structured message templates rather than concatenating English fragments.
3. Keep raw values and label lookup separate. Never translate the completed
   terminal output using regular-expression substitutions: that can alter host
   names, process names, commands and data, and breaks alignment after the fact.
4. Commands, paths, service identifiers and host/user names are data, not prose
   to translate. Localized explanatory text must not silently rewrite a command
   into an untested platform-specific alternative.
5. Resolve the selected catalog when generating the standalone output where
   practical. Embed only required messages and bounded formatting data. Keep
   generation offline and retain one-file runtime delivery.
6. Treat pluralized counts and unit formatting as message/format operations,
   not English suffix rules. Unicode CLDR documents locale identifiers,
   inheritance and distinct number/date/message-formatting concerns; it is a
   reference for a deliberately chosen subset, not a requirement to bundle its
   entire database in every script.[^cldr]

### Parse invariant observations before formatting them

Prefer machine-readable APIs and explicit output columns. Where a provider's
text grammar is documented in a fixed locale, set that locale for the provider
process only and parse that known grammar. Do not change the user's whole shell
locale just to collect a measurement. If an old or localized command cannot
produce a supported grammar, identify the observation as unavailable rather than
guessing from translated headings or punctuation.

Formatting comes after validation and arithmetic. A comma decimal separator, a
localized date or a translated unit label must never be fed back into shell
arithmetic or collector parsing. Retained timestamps, durations and counters in
evidence use a stable machine format; the human view may use a separately chosen
display convention. Display time zone and unit choices must remain explicit.

### Explicit locale fallback

The first implementation should support a small enumerated set of reviewed
catalogs. Record the requested and effective locale in inspection/build metadata.
Use a documented lookup order: exact supported locale, an explicitly listed
language fallback, then the built-in English catalog. Do not guess script or
region equivalence by repeatedly cutting characters from a locale name.

A missing optional message may fall back to English with an inspectable warning;
a malformed catalog or invalid placeholder must fail generation. A user who
requests strict locale completeness should receive a clear error instead of a
silently mixed-language artifact. No missing catalog should trigger a network
download during login.

ASCII capability is a separate decision from language. A destination unable to
display a requested translation needs a reviewed ASCII-compatible catalog or an
explicit English/plain fallback, reported at generation or inspection. Replacing
arbitrary non-ASCII text with `?` is not a localized experience.

### Width and text boundaries

Byte length, Unicode code-point count, user-perceived characters and terminal
cell width are different quantities. Unicode's text segmentation annex defines
grapheme-cluster boundaries; its East Asian width property supplies useful width
information but is not a complete terminal-layout specification.[^graphemes][^width]

For any backend advertised as supporting general Unicode labels:

- Decode input using a stated encoding before layout, and reject or visibly
  replace invalid data according to a documented policy.
- Measure printable terminal cells after style codes are removed from width
  accounting. Keep ANSI control generation separate from text.
- Clip only at supported grapheme boundaries, then add an omission marker whose
  cell width is included in the budget.
- Pin the Unicode/width-policy version used by the generator and gallery. State
  how ambiguous-width characters are treated; test representative terminal hosts
  instead of assuming every host agrees.
- Include decomposed accents, combining sequences, CJK characters, long
  translated labels, and unsupported characters in fixtures.
- Keep ASCII/plain output first-class. Older byte-oriented runtime paths retain
  their declared reduced policy until an actual implementation and tests justify
  broader claims.

Bidirectional text, shaping and terminal order are a separate boundary. Never
reverse strings to “support RTL.” Keep machine identifiers and commands in a
predictable order, and avoid inserting bidi controls into executable command
examples. Full right-to-left UI needs a declared terminal policy and visual
tests with mixed text and numbers. Emoji, variation selectors, joined sequences
and font-dependent glyphs likewise need explicit tests; decorative emoji should
not be required to understand a health state.

### Minimum localization acceptance cases

The first catalog release should demonstrate English plus one reviewed second
language through config save/reload, generation, preview and output. Test long
labels at 40 columns, decimal/date formatting separately from raw values,
missing keys, malformed placeholders, fallback disclosure, ASCII-only output,
combining/CJK cases for any claimed Unicode path, and literal command preservation.
Record the limitations of RTL and emoji rather than counting them as passed.

## 7. Historical semantic contracts that must survive new designs

The early conversation contains important domain requirements not fully captured
by a screenshot's appearance:

- **RAM:** an allocation bar and an “available” estimate are different views.
  Do not add overlapping free/cache/available counters as if all were disjoint.
  Compression consumes RAM; logical swap is a separate scale. A cosmetic change
  must not change the documented formula or double-count a compressed pool.
- **Storage:** aggregate only a declared eligible scope. Bind mounts, aliases,
  shared pools and thin provisioning can invalidate a naive capacity sum. Keep
  individual-full-filesystem findings even when the aggregate has spare space.
- **I/O:** cumulative bytes, a sampled rate, system-call bytes and physical
  device activity are different observations. Preserve interval, identity,
  reset/exit handling and readable-process coverage.
- **Services:** installed, loaded, enabled, active and required are separate
  facts. A missing optional service is not automatically an incident. Repeated
  aliases should not become duplicate health findings.
- **Sessions:** retain the native session ID, terminal/display, recorded peer
  and state. Several sessions using `workshop` remain distinct. A TCP socket is
  not proof of an authenticated session, and a shared account is not a human ID.
- **Public inventory:** deliberate public fields, generation timestamp and
  refresh policy belong to a static artifact. An optional Fastfetch call runs
  when that artifact is generated, not because agetty executes text. Static
  inventory generation, boot refresh and attachment require separate acceptance
  evidence from a literal notice export.

The [metric coverage table](compatibility.md#shared-sections-explicit-metric-semantics)
and historical guides under `reference/` document the current backend limits.
Extend shared fixtures around these meanings before adding another view of them.

## 8. Usability and performance acceptance

A novice should be able to answer “where will this appear?”, “what do I want to
see?” and “how should it look?” before learning interpreter or installation
terminology. Show a recommended choice with a short reason, retain an advanced
path, and explain unavailable options in terms of the destination's capabilities.
Avoid offering an installer action that the host cannot perform.

The wizard provides visible navigation and contextual help, coherent defaults,
back navigation that preserves edits, and a review of output paths before
installation. The [beginner walkthrough](quickstart.md) covers choosing a preset,
changing design/density and bars, showing a sample, saving a recipe, generating a
file and reopening it. It explains the two Enter steps in screen choice previews
and the immediate number-plus-Enter choice in ordinary menus and line mode.
Continue testing cancellation at each meaningful boundary. Resizing should preserve both
the answer and focus; reduced flashing is a behavior to inspect, not merely a
claim based on using a row cache.

Retain the historical performance wishes as a measured programme:

| Boundary | Goal / required reporting |
|---|---|
| Normal live invocation | Aim below 100 ms on named representative machines, with approximately 10 ms a longer-term aspiration where the requested work permits it. |
| Controlled stalled helpers | Test the 400 ms target with explicitly killable faults; report every outlier and which collectors/fallbacks were used. |
| Render-only work | Measure separately from process startup and collection; preserve equal content, styling and geometry when comparing designs. |
| Wizard interaction | Record first-preview latency, cached selection latency and resize latency; distinguish cold PowerShell startup from screen painting. |
| Output transport | Identify whether measurements exclude SSH/PAM, terminal painting and slow serial/network output. |

Report median, a declared percentile method, maximum, sample count, exact source,
host, selected content, unavailable observations and fallback count. Avoid
comparing a full live observation with a faster reduced fallback as if they did
the same work. A timeout cannot promise a hard bound under arbitrary scheduler,
kernel, WMI initialization or output-backpressure conditions.

No new latency target is claimed achieved by this review. The saved Workshop1.2
measurements remain measurements of that older artifact. Add an optional cache
or refresh service only if a measured requirement justifies its freshness,
permissions and lifecycle cost; do not make it the default shortcut to a speed
claim.

## 9. Delivery sequence and decision gates

1. **Reconcile the interrupted delivery.** Preserve the existing work; compare
   local sources, retained artifacts and remote refs. Publish one complete,
   reviewable change with the exact tested code and evidence. A green source-only
   branch does not by itself publish all galleries or update `main`.
2. **Verify the implemented user-path corrections.** Exercise suffix handling
   through real exports/install archives, required-service identity, batch text
   validation, safe static previews and reconfiguration cleanup. Keep ordinary
   saved recipes compatible.
3. **Verify the bounded readability extension.** Inline/wide resource bars now
   use existing observations. Exercise all
   backends that advertise the setting and inspect narrow, tall and paired-panel
   views. Keep new settings independent of collection.
4. **Make configuration approachable.** Retain the action-first wizard, visible
   help and preview safeguards. Use the new concise walkthrough to test the
   complete save/build/reopen path; measure cold/cached preview behavior.
5. **Implement fields and localization in a small verified slice.** Adopt stable
   catalog and field IDs, validated label overrides, exact fallback rules and one
   reviewed additional language. The current byte-oriented legacy layouts need
   an explicit text policy before wider label support can be promised.
   Keep general Unicode/RTL capability claims bounded by actual tests.
6. **Expand real environment evidence.** Use legitimate runnable old Windows
   environments for PowerShell1/3/4/5.0. Add real login-service deployments and
   native-console checks. An unavailable environment remains an explicit gate,
   not a reason to fabricate a pass or silently change the requested engine.
7. **Add integrations one at a time.** macOS profiles, Windows profiles/CMD,
   static inventory refresh, getty/PAM/Telnet, RDP and prompt events each need
   ownership, safety, rollback and native-session tests appropriate to that
   mechanism. Reuse a renderer when the target merely launches it.
8. **Reassess older Python on evidence.** The user's Python3.0 request remains
   recorded. Python3.8 is the practical current boundary; earlier targets need
   an explicit benefit, dependency/language inventory and actual execution
   before changes to the generator or filesystem guarantees. F-strings alone
   are syntax introduced after Python3.0, as the Python3.6 release notes
   document.[^python36] Generating elsewhere already serves many old destination
   systems without carrying an older Python port.

The concrete checklist is [TODO.md](../TODO.md); [ROADMAP.md](../ROADMAP.md)
retains the delivery sequence. The owner must still choose the project's
licensing terms. A vendored component's license and the availability of source
do not select the license of the whole project.

## 10. Review coverage and source references

This discussion review read the entire supplied transcript and every current
document under `docs/` and `specs/`, plus `README.md`, `ROADMAP.md`, `TODO.md` and
`AGENTS.md`. The parallel source reviews and execution checks have their own
scope; this statement is not a claim that reading documentation proves the
absence of code defects. No arbitrary static-analysis score or test count is a
substitute for a particular demonstrated behavior.

The original v0.4 audit remains the source for its findings, implementation
locations, existing test counts and known limitations. New source edits require
fresh relevant checks and refreshed artifact provenance. Do not retitle old
records, combine historical totals with new totals, or mark a prepared workflow
as executed. The final user-facing report should identify the delivered commit,
what changed, actual checks, representative previews and remaining boundaries.

Primary references consulted for the proposed text/locale policy on
17 November 2026:

[^width]: Unicode, [UAX11: East Asian Width](https://www.unicode.org/reports/tr11/).
[^graphemes]: Unicode, [UAX29: Unicode Text Segmentation](https://www.unicode.org/reports/tr29/).
[^cldr]: Unicode, [UTS35 / CLDR specification](https://www.unicode.org/reports/tr35/).
[^python36]: Python, [What's New in Python3.6: formatted string literals](https://docs.python.org/3/whatsnew/3.6.html#pep-498-formatted-string-literals).

## 11. Publication and native CI addendum

Status recorded **17 November 2026**. Publication commit
[`9cefbdd775372a8ee3cfb5ce64fbfcbbbd7aef27`](https://github.com/Julesc013/motd/commit/9cefbdd775372a8ee3cfb5ce64fbfcbbbd7aef27)
contains the complete source, documentation, evidence and gallery artifacts;
its tree is `a2abb596491e62abc518325bb725dc80ca809d52`. Keep the initial failure and
subsequent correction visible when interpreting the CI results:

| Evidence | Observed result | Scope |
|---|---|---|
| [Verify run 44041772342](https://github.com/Julesc013/motd/actions/runs/44041772342) | All five jobs passed. | Publication commit `9cefbdd775372a8ee3cfb5ce64fbfcbbbd7aef27`. |
| [Native PowerShell run 44041771990](https://github.com/Julesc013/motd/actions/runs/44041771990) | Windows PowerShell 5.1/current `pwsh` and actual PowerShell 2.0 passed; macOS failed a new assertion. | This run was not wholly green. Its successful jobs remain evidence for their own environments. |
| [Test correction `0f16e88d1406f0b6e87a9ea7e263887c2eb7d057`](https://github.com/Julesc013/motd/commit/0f16e88d1406f0b6e87a9ea7e263887c2eb7d057) | The expected bar semantics now follow the selected Unix collector. | Test-only change; tree `8a65d8d40526256de6323adbd4f307ca99f9478d`. Runtime, generator and galleries are unchanged. |

The macOS failure exposed an incorrect test assumption. The Bash launcher on
macOS correctly selects the portable collector, whose fixture displays **75%
available**. The test had expected the enhanced Linux collector's **25% used**
reading. The correction checks the declared meaning for the selected collector;
it does not relabel the metric or alter collection and rendering behavior.

The first native run established **81/81 cases on an actual PowerShell 2.0
engine**: ten generated artifacts (five designs × two bar styles), each exercised
at four terminal sizes and two character sets, plus one live case. That is 80
synthetic cases and one live case. This is engine-specific execution evidence;
it does not establish PowerShell 1.0, 3.0, 4.0, 5.0 or real interactive Windows
console resizing.

**Native follow-up at `0f16e88d1406f0b6e87a9ea7e263887c2eb7d057`: passed.**
[Verify run 44042319329](https://github.com/Julesc013/motd/actions/runs/44042319329)
passed Linux, Python 3.8, macOS, Windows PowerShell and Windows `pwsh`.
[Native run 44042319335](https://github.com/Julesc013/motd/actions/runs/44042319335)
passed Windows PowerShell, Windows `pwsh`, macOS `pwsh` and actual PowerShell 2.
All nine jobs succeeded. Linux regenerated examples without a diff and verified
all 524 classic, 140 design and 48 bar captures, including decoded PNG pixels.

The final native versions were Windows PowerShell 5.1.26100.33648 and
PowerShell 7.6.9 on both Windows and macOS 26.7.2. The final PS2 run again passed
81/81 cases, with zero skips; its actual-version probe and all ten artifact hashes
were checked. Individual test skips, exact host versions and the original failed
run remain in the [current evidence index](../build/verification-review-20261117.json).
The follow-up evidence/documentation commit changes no generator, runtime,
test, workflow, recipe or generated preview from this tested implementation.

## 12. Bounded synthetic performance observation

The [measured record](../build/review-20261117/synthetic-render-benchmark-20261117.json)
and retained environment-specific runner add a current-source baseline. On the
recorded Debian 13 / AMD EPYC host, each route ran one discarded warmup followed
by 20 measured fresh processes. Settings were home-lab, Cards, Comfortable,
Brief, wide bars, 80×25, plain ASCII and no hooks. These routes use their own
backend fixtures; this is not a controlled comparison of language performance.

| Generated route | Median | p95 | Observed range |
|---|---:|---:|---:|
| Bash 5.2.37 | 45.8 ms | 51.1 ms | 41.6–55.4 ms |
| `/bin/sh` → dash, exact executable hash retained | 10.1 ms | 12.8 ms | 8.7–12.9 ms |
| PowerShell 7.6.10 | 625.1 ms | 673.6 ms | 562.8–681.9 ms |

The p95 is nearest-rank, observation 19 of 20. Every invocation exited zero with
empty stderr. Measurements include interpreter startup, synthetic rendering and
output capture, with warmed OS caches and no exclusive host scheduling. They
exclude live collection, CLI preview, interactive wizard redraw, terminal
painting and real login transport. The dash package version was unavailable;
the executable SHA256 identifies what actually ran.

The PowerShell observation is a concrete reason to measure process startup,
cached preview reuse and redraw separately before promising a smooth resize
experience on every backend. It does not identify which component consumes the
time. The earlier less-than-100-ms live aspiration and 400-ms controlled-stall
target remain unverified for this release. Keep the next performance work
focused on measured user paths, including a real Windows console, rather than
introducing a daemon or weakening data-quality checks.
